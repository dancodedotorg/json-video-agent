"""Helper utilities for Google API integration and content processing.

This module provides utility functions for interacting with Google Slides and Docs APIs,
processing educational content from various sources, and rendering content as PDFs.

Key Components:
    - Google Slides API integration (speaker notes and thumbnails)
    - Google Docs export functionality
    - Code.org curriculum markdown fetching (via GitHub)
    - PDF rendering from HTML (slide notes view)
    - ID extraction from Google URLs

Authentication is handled via service account credentials stored as a base64-encoded
JSON string in the GOOGLE_SERVICE_ACCOUNT_JSON environment variable.
"""

from typing import Any, Dict
from googleapiclient.discovery import build

import base64
import io
import json
import os
import logging
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession
import requests
import re
import httpx

# for HTML to PDF
from xhtml2pdf import pisa
from dotenv import load_dotenv
load_dotenv()

# --- Scopes: read-only is enough for notes + thumbnails ---
SLIDES_SCOPES = [
    "https://www.googleapis.com/auth/presentations.readonly",
    # Not always required for Slides API calls, but useful if you later look up by Drive file metadata
    "https://www.googleapis.com/auth/drive.readonly",
]


# -----------------------------
# Service account credentials
# -----------------------------
def get_service_account_creds_from_env(
    env_var: str = "GOOGLE_SERVICE_ACCOUNT_JSON",
    scopes=SLIDES_SCOPES,
):
    """
    Create service-account credentials from an environment variable containing JSON.

    Example:
      export GOOGLE_SERVICE_ACCOUNT_JSON='{"type":"service_account", ... }'
    """
    raw = os.environ.get(env_var)
    if not raw:
        raise ValueError(
            f"Missing env var {env_var}. Put the service account JSON into this env var "
            f"or use get_service_account_creds_from_file()."
        )
    decoded = base64.b64decode(raw).decode("utf-8")
    info = json.loads(decoded)
    return service_account.Credentials.from_service_account_info(info, scopes=scopes)


# -----------------------------
# Cached API client builders
# -----------------------------
def _build_slides_service(_creds):
    """
    Build and cache the Google Slides API service.

    Note: underscore prefix prevents Streamlit from keying cache on credentials.
    """
    return build("slides", "v1", credentials=_creds, cache_discovery=False)


def _build_authed_session(_creds):
    """
    Build and cache an AuthorizedSession for downloading thumbnail contentUrls.

    This avoids manually using creds.token (which can expire).
    AuthorizedSession applies auth headers and refreshes as needed.
    """
    return AuthorizedSession(_creds)


# -----------------------------
# Main orchestration functions
# -----------------------------
def get_slides_data(presentation_id):
    """
    Orchestrates fetching speaker notes + thumbnails, returning a single list
    of slide dicts.
    """
    creds = get_service_account_creds_from_env()
    slides = _get_slide_list(presentation_id, creds)
    notes_by_id = get_all_speaker_notes_by_slide_id(presentation_id, creds, slides=slides)
    thumbs_by_id = get_all_pngs_by_slide_id(presentation_id, creds, slides=slides)

    slides_data = []
    for i, slide in enumerate(slides):
        sid = slide["objectId"]
        slides_data.append(
            {
                "index": i,
                "slide_id": sid,
                "notes": notes_by_id.get(sid, ""),
                "png_base64": thumbs_by_id.get(sid, None),
            }
        )

    return slides_data

def render_pdf_bytes_from_slides(presentation_id):
    """
    Given a Google Slides presentation ID, fetches the slides data and
    returns a base64-encoded PDF string containing slide thumbnails and notes.
    """
    
    slides_data = get_slides_data(presentation_id)
    pdf_base64 = slides_to_pdf(slides_data)
    return pdf_base64

# -----------------------------
# Helpers: slide list + notes
# -----------------------------
def _get_slide_list(presentation_id, creds):
    service = _build_slides_service(creds)
    presentation = service.presentations().get(presentationId=presentation_id).execute()
    return presentation.get("slides", [])


def get_all_speaker_notes(presentation_id, creds):
    """
    Backwards-compatible function: returns notes as a list ordered by slide index.
    """
    slides = _get_slide_list(presentation_id, creds)
    notes_by_id = get_all_speaker_notes_by_slide_id(presentation_id, creds, slides=slides)
    return [notes_by_id.get(s["objectId"], "") for s in slides]


def get_all_speaker_notes_by_slide_id(presentation_id, creds, slides=None):
    """
    Preferred: returns notes keyed by slide objectId so you never misalign notes/thumbnails.
    """
    if slides is None:
        slides = _get_slide_list(presentation_id, creds)

    # (Service creation is cached)
    _ = _build_slides_service(creds)

    all_notes = {}

    for slide in slides:
        sid = slide["objectId"]
        notes_page = slide.get("slideProperties", {}).get("notesPage", {})
        note_texts = []

        for elem in notes_page.get("pageElements", []):
            shape = elem.get("shape")
            if not shape:
                continue

            placeholder = shape.get("placeholder", {})
            # Speaker notes text box
            if placeholder.get("type") != "BODY":
                continue

            text = shape.get("text", {})
            for te in text.get("textElements", []):
                text_run = te.get("textRun")
                if text_run and "content" in text_run:
                    note_texts.append(text_run["content"])

        all_notes[sid] = "".join(note_texts).strip()

    return all_notes


# -----------------------------
# Thumbnails
# -----------------------------
def get_all_pngs_from_presentation(presentation_id, creds):
    """
    Backwards-compatible: returns thumbnails as a list ordered by slide index.
    """
    slides = _get_slide_list(presentation_id, creds)
    thumbs_by_id = get_all_pngs_by_slide_id(presentation_id, creds, slides=slides)
    return [thumbs_by_id.get(s["objectId"], None) for s in slides]


def get_all_pngs_by_slide_id(presentation_id, creds, slides=None):
    """
    Preferred: returns data-URI PNG thumbnails keyed by slide objectId.

    Uses AuthorizedSession so auth works reliably without manual token handling.
    """
    if slides is None:
        slides = _get_slide_list(presentation_id, creds)

    service = _build_slides_service(creds)
    authed_session = _build_authed_session(creds)

    png_images = {}

    for i, slide in enumerate(slides):
        sid = slide["objectId"]

        thumbnail = (
            service.presentations()
            .pages()
            .getThumbnail(
                presentationId=presentation_id,
                pageObjectId=sid,
                thumbnailProperties_thumbnailSize="LARGE",
                thumbnailProperties_mimeType="PNG",
            )
            .execute()
        )

        image_content_url = thumbnail.get("contentUrl")
        if not image_content_url:
            png_images[sid] = None
            continue

        # Download with an AuthorizedSession (handles auth headers + refresh)
        resp = authed_session.get(image_content_url, stream=True, timeout=30)
        resp.raise_for_status()

        base64_string = base64.b64encode(resp.content).decode("utf-8")
        data_uri = f"data:image/png;base64,{base64_string}"
        png_images[sid] = data_uri

    return png_images


# -----------------------------
# PDF rendering
# -----------------------------
def slides_to_pdf(slides):
    """
    slides: list of dicts like:
      [{ "png_base64": "data:image/png;base64,...", "notes": "..." }, ...]
    Returns a base64-encoded PDF string.
    """
    rows_html = ""
    for slide in slides:
        png = slide.get("png_base64") or ""
        notes = (slide.get("notes") or "").replace("\n", "<br/>")
        rows_html += f"""
        <tr>
          <td style="width: 40%">
            <img src="{png}" />
          </td>
          <td style="width: 60%">
            {notes}
          </td>
        </tr>
        """

    html = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <style>
    body {{ font-family: Arial, sans-serif; margin: 20px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border: 1px solid #ccc; padding: 8px; vertical-align: top; }}
    th {{ background-color: #f5f5f5; text-align: left; }}
    img {{ max-width: 100%; height: auto; display: block; }}
  </style>
</head>
<body>
  <table>
    <tr>
      <th style="width: 40%">Slide</th>
      <th style="width: 60%">Lesson Guide</th>
    </tr>
    {rows_html}
  </table>
</body>
</html>
"""
    pdf_io = io.BytesIO()
    pisa.CreatePDF(io.StringIO(html), dest=pdf_io)
    return base64.b64encode(pdf_io.getvalue()).decode("utf-8")


def extract_slides_id(url: str) -> str | None:
    """
    Return the Google Slides ID from a URL, or None if not found.
    Matches typical patterns like:
      - https://docs.google.com/presentation/d/<ID>/edit
      - https://docs.google.com/presentation/u/0/d/<ID>/view
      - https://drive.google.com/file/d/<ID>/view
    """
    m = re.search(r'(?:docs\.google\.com\/presentation|drive\.google\.com\/file)?(?:\/u\/\d+)?\/d\/([A-Za-z0-9_-]+)', url)
    return m.group(1) if m else None

def extract_doc_id(url: str) -> str | None:
    """
    Extract a Google Docs document ID from a URL.
    Returns None if no valid ID is found.
    """
    match = re.search(
        r'docs\.google\.com\/document(?:\/u\/\d+)?\/d\/([A-Za-z0-9_-]+)',
        url
    )
    return match.group(1) if match else None

async def fetch_markdown_level(name: str) -> str | None:
    """
    When the user asks for a markdown level, fetches the level data from GitHub and extracts the markdown
    
    Args:
        name: name of level.

    Returns:
        markdown content as a string, or None if not found.
    """

    # LEVELURL: "https://raw.githubusercontent.com/code-dot-org/code-dot-org/refs/heads/staging/dashboard/config/levels/custom/pythonlab/{level_name}.level"
    # BUBBLEURL: "https://raw.githubusercontent.com/code-dot-org/code-dot-org/refs/heads/staging/dashboard/config/scripts/{level_name_with_dashes_to_underscores}.bubble_choice"
    # MARKDOWN: "https://raw.githubusercontent.com/code-dot-org/code-dot-org/refs/heads/staging/dashboard/config/scripts/{level_name_with_dashes_to_underscores}.external"

    
    name_no_dashes = name.replace("-", "_").lower()
    url = f"https://raw.githubusercontent.com/code-dot-org/code-dot-org/refs/heads/staging/dashboard/config/scripts/{name_no_dashes}.external"

    logging.info(f"Fetching file from: {url}")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url)
            # Raise an exception for bad status codes (4xx or 5xx)
            response.raise_for_status()
        raw_text = response.text
        # Extract markdown content between the markers <<MARKDOWN and MARKDOWN
        match = re.search(r"<<MARKDOWN\s*\n(.*?)\nMARKDOWN\s*$", raw_text, flags=re.DOTALL | re.MULTILINE)
        logging.info(f"Extracted markdown content: {match.group(1).strip() if match else 'No match found'}")
        return match.group(1).strip() if match else None
        
    except requests.exceptions.HTTPError as http_err:
        logging.error(f"HTTP error occurred: {http_err}")
    except requests.exceptions.RequestException as err:
        logging.error(f"An error occurred: {err}")
    return None

async def fetch_doc_as_pdf(export_url: str) -> Dict[str, Any]:
    """
    Fetch the PDF export of a Google Doc given its export URL.
    Args:
        export_url: The URL to export the Google Doc as PDF.
    Returns:
        A dict with either 'status': 'success' and 'pdf_bytes' keys, or 'status': 'error' and 'message'.
    """
    timeout_s = 30.0
    
    headers = {
        "Accept": "application/pdf",
        "User-Agent": "adk-agent/1.0",
    }

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(timeout_s),
        ) as client:
            resp = await client.get(export_url, headers=headers)

        if resp.status_code >= 400:
            return {"status": "error", "message": f"Failed to fetch PDF export (HTTP {resp.status_code})."}

        content_type = (resp.headers.get("content-type") or "").lower()
        pdf_bytes = resp.content

        # Guardrail: private docs often return HTML instead of PDF.
        if "application/pdf" not in content_type and not pdf_bytes.startswith(b"%PDF"):
            logging.error(
                "Export did not return PDF. "
                f"content-type={content_type!r}, first_bytes={pdf_bytes[:20]!r}"
            )
            return {
                "status": "error",
                "message": (
                    "I couldn't download a PDF. The doc may require authentication or "
                    "isn't accessible to this agent's runtime."
                )
            }

        # return success with pdf_bytes
        return {"status": "success", "pdf_bytes": pdf_bytes}

    except httpx.RequestError as e:
        logging.error(f"Network error fetching Google Doc export: {e}")
        return {"status": "error", "message": "Network error while fetching the Google Doc PDF export."}
    except Exception as e:
        logging.exception(f"Unexpected error saving Google Doc PDF artifact: {e}")
        return {"status": "error", "message": "Unexpected error while saving the PDF artifact."}