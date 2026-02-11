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

from typing import Any, Dict, List, Optional
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import AuthorizedSession as AuthSessionType

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

# Tango image extraction
from bs4 import BeautifulSoup

# Google API OAuth scopes (read-only access for Slides and Drive)
SLIDES_SCOPES = [
    "https://www.googleapis.com/auth/presentations.readonly",  # Access presentation content
    "https://www.googleapis.com/auth/drive.readonly",          # Access Drive file metadata
]


# -----------------------------
# Service account credentials
# -----------------------------
def get_service_account_creds_from_env(
    env_var: str = "GOOGLE_SERVICE_ACCOUNT_JSON",
    scopes: List[str] = SLIDES_SCOPES,
) -> Credentials:
    """Create service account credentials from base64-encoded JSON in environment variable.
    
    Loads Google service account credentials from an environment variable containing
    a base64-encoded JSON string. This is more secure than storing the JSON file directly.
    
    Args:
        env_var: Name of environment variable containing base64-encoded service account JSON
        scopes: List of Google API OAuth scopes to request
        
    Returns:
        Google service account Credentials object configured with specified scopes
        
    Raises:
        ValueError: If the environment variable is not set
        json.JSONDecodeError: If the decoded content is not valid JSON
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
def _build_slides_service(_creds: Credentials):
    """Build Google Slides API service client.
    
    Creates a Google Slides API v1 service object for making API calls.
    Cache discovery is disabled to avoid caching issues in ADK environment.
    
    Args:
        _creds: Google service account credentials
        
    Returns:
        Google Slides API service client
    """
    return build("slides", "v1", credentials=_creds, cache_discovery=False)


def _build_authed_session(_creds: Credentials) -> AuthSessionType:
    """Build authorized HTTP session for authenticated requests.
    
    Creates an AuthorizedSession that automatically handles authentication headers
    and token refresh. Useful for downloading content URLs that require auth.
    
    Args:
        _creds: Google service account credentials
        
    Returns:
        AuthorizedSession instance for making authenticated HTTP requests
    """
    return AuthorizedSession(_creds)


# -----------------------------
# Main orchestration functions
# -----------------------------
def get_slides_data(presentation_id: str) -> List[Dict[str, Any]]:
    """Fetch slide data including speaker notes and thumbnails from Google Slides.
    
    Orchestrates the retrieval of presentation data by combining slide metadata,
    speaker notes, and PNG thumbnails into a unified data structure.
    
    Args:
        presentation_id: Google Slides presentation ID (the ID portion from the URL)
            
    Returns:
        List of slide dictionaries, where each dict contains:
            - index (int): Zero-based slide index
            - slide_id (str): Google Slides object ID
            - notes (str): Speaker notes text content
            - png_base64 (str | None): Base64-encoded PNG data URI or None if unavailable
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

def render_pdf_bytes_from_slides(presentation_id: str) -> str:
    """Generate a PDF with slide thumbnails and notes from a Google Slides presentation.
    
    Fetches slide data (thumbnails and speaker notes) and renders them as a PDF
    with a two-column layout: slide image on left, notes on right.
    
    Args:
        presentation_id: Google Slides presentation ID
        
    Returns:
        Base64-encoded PDF string ready for saving or transmission
    """
    slides_data = get_slides_data(presentation_id)
    pdf_base64 = slides_to_pdf(slides_data)
    return pdf_base64

# -----------------------------
# Helpers: slide list + notes
# -----------------------------
def _get_slide_list(presentation_id: str, creds: Credentials) -> List[Dict[str, Any]]:
    """Get slide list from presentation metadata.
    
    Args:
        presentation_id: Google Slides presentation ID
        creds: Google service account credentials
        
    Returns:
        List of slide objects from Slides API
    """
    service = _build_slides_service(creds)
    presentation = service.presentations().get(presentationId=presentation_id).execute()
    return presentation.get("slides", [])


def get_all_speaker_notes(presentation_id: str, creds: Credentials) -> List[str]:
    """Get speaker notes for all slides as an ordered list.
    
    Backwards-compatible function that returns notes as a list ordered by slide index.
    Internally uses get_all_speaker_notes_by_slide_id for correctness.
    
    Args:
        presentation_id: Google Slides presentation ID
        creds: Google service account credentials
        
    Returns:
        List of speaker notes strings, one per slide in presentation order
    """
    slides = _get_slide_list(presentation_id, creds)
    notes_by_id = get_all_speaker_notes_by_slide_id(presentation_id, creds, slides=slides)
    return [notes_by_id.get(s["objectId"], "") for s in slides]


def get_all_speaker_notes_by_slide_id(
    presentation_id: str,
    creds: Credentials,
    slides: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, str]:
    """Get speaker notes for all slides keyed by slide object ID.
    
    Preferred method that returns notes keyed by slide objectId to prevent
    misalignment between notes and thumbnails.
    
    Args:
        presentation_id: Google Slides presentation ID
        creds: Google service account credentials
        slides: Optional pre-fetched slide list (fetched if not provided)
        
    Returns:
        Dictionary mapping slide objectId to speaker notes text
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
def get_all_pngs_from_presentation(presentation_id: str, creds: Credentials) -> List[Optional[str]]:
    """Get slide thumbnails as PNG data URIs in presentation order.
    
    Backwards-compatible function that returns thumbnails as a list ordered by slide index.
    
    Args:
        presentation_id: Google Slides presentation ID
        creds: Google service account credentials
        
    Returns:
        List of PNG data URIs (or None for slides without thumbnails)
    """
    slides = _get_slide_list(presentation_id, creds)
    thumbs_by_id = get_all_pngs_by_slide_id(presentation_id, creds, slides=slides)
    return [thumbs_by_id.get(s["objectId"], None) for s in slides]


def get_all_pngs_by_slide_id(
    presentation_id: str,
    creds: Credentials,
    slides: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Optional[str]]:
    """Get slide thumbnails as PNG data URIs keyed by slide object ID.
    
    Preferred method that returns thumbnails keyed by slide objectId to prevent
    misalignment. Uses AuthorizedSession for reliable auth with automatic token refresh.
    
    Args:
        presentation_id: Google Slides presentation ID
        creds: Google service account credentials
        slides: Optional pre-fetched slide list (fetched if not provided)
        
    Returns:
        Dictionary mapping slide objectId to PNG data URI (or None if unavailable)
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
def slides_to_pdf(slides: List[Dict[str, Any]]) -> str:
    """Render slides with notes as a two-column PDF layout.
    
    Generates an HTML table with slide thumbnails and speaker notes, then converts
    to PDF using xhtml2pdf. The layout shows slide images on the left (40% width)
    and notes on the right (60% width).
    
    Args:
        slides: List of slide dictionaries containing:
            - png_base64 (str): Base64 PNG data URI for slide thumbnail
            - notes (str): Speaker notes text
        
    Returns:
        Base64-encoded PDF string ready for saving or transmission
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


def extract_slides_id(url: str) -> Optional[str]:
    """Extract Google Slides presentation ID from a URL.
    
    Parses various Google Slides/Drive URL formats to extract the presentation ID.
    
    Supported URL patterns:
        - https://docs.google.com/presentation/d/<ID>/edit
        - https://docs.google.com/presentation/u/0/d/<ID>/view
        - https://drive.google.com/file/d/<ID>/view
    
    Args:
        url: Google Slides or Drive URL
        
    Returns:
        Presentation ID string, or None if no valid ID found in URL
    """
    m = re.search(r'(?:docs\.google\.com\/presentation|drive\.google\.com\/file)?(?:\/u\/\d+)?\/d\/([A-Za-z0-9_-]+)', url)
    return m.group(1) if m else None

def extract_doc_id(url: str) -> Optional[str]:
    """Extract Google Docs document ID from a URL.
    
    Parses Google Docs URLs to extract the document ID.
    
    Args:
        url: Google Docs URL (e.g., "https://docs.google.com/document/d/<ID>/edit")
        
    Returns:
        Document ID string, or None if no valid ID found in URL
    """
    match = re.search(
        r'docs\.google\.com\/document(?:\/u\/\d+)?\/d\/([A-Za-z0-9_-]+)',
        url
    )
    return match.group(1) if match else None

async def fetch_markdown_level(name: str) -> Optional[str]:
    """Fetch Code.org curriculum markdown from GitHub repository.
    
    Retrieves markdown content for a Code.org curriculum level from the public
    GitHub repository. Converts the level name to the expected file format and
    extracts markdown content from the .external file format.
    
    Args:
        name: Level name identifier (e.g., "Unit3-Lesson5", "CSD-U3-L5")
            Dashes are converted to underscores for file lookup

    Returns:
        Markdown content string extracted from the level file, or None if not found
        or if the request fails
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
    """Fetch PDF export of a Google Doc from its export URL.
    
    Downloads a Google Doc as PDF using the document's export URL. Includes
    guardrails to detect private/inaccessible documents that return HTML instead of PDF.
    
    Args:
        export_url: Google Docs export URL (format: https://docs.google.com/document/d/{ID}/export?format=pdf)
        
    Returns:
        Dictionary containing:
            - On success: {"status": "success", "pdf_bytes": bytes}
            - On error: {"status": "error", "message": str}
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

# Tango helpers

def get_as_base64(url):
    """Downloads an image from a URL and converts it to a base64 Data URI."""
    try:
        # Tango URLs often have complex query parameters; requests handles these well
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # Determine the mime type (usually image/png for Tango)
        content_type = response.headers.get('content-type', 'image/png')
        
        # Encode to base64
        encoded_string = base64.b64encode(response.content).decode('utf-8')
        return f"data:{content_type};base64,{encoded_string}"
    except Exception as e:
        print(f"  Warning: Could not process image at {url[:50]}... Error: {e}")
        return None

def parse_tango_to_json(html_content, output_file="workflow_steps.json"):
    logging.info("Starting Tango HTML extraction")
    soup = BeautifulSoup(html_content, 'html.parser')
    results = []
    
    # Tango exports usually wrap steps in <div> tags containing an <h3> and an <img>
    steps_headers = soup.find_all('h3')
    
    for header in steps_headers:
        description = header.get_text(strip=True)
        
        # Parse the step number (assumes format "1. Description")
        try:
            step_num = int(description.split('.')[0])
        except (ValueError, IndexError):
            step_num = 0
            
        # Find the image immediately following the header
        img_tag = header.find_next('img')
        
        if img_tag and img_tag.get('src'):
            img_url = img_tag['src']
            logging.info(f"Processing Step {step_num}: {description[:30]}...")
            
            base64_img = get_as_base64(img_url)
            
            results.append({
                "step": step_num,
                "notes": description,
                "png_base64": base64_img
            })

    
    
    logging.info(f"\nSuccess! {len(results)} steps saved")
    return results