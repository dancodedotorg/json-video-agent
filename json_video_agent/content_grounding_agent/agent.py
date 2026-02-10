"""Content grounding agent implementation and tool functions.

This module defines the content grounding agent which is responsible for importing
and processing educational resources (Google Slides, Docs, Code.org markdown) into
a format usable by the tutorial video generation system.

Key Tool Functions:
    - slides_id_to_artifacts: Import Google Slides presentations
    - create_markdown_artifact: Import Code.org curriculum markdown
    - save_google_doc_as_pdf_artifact: Import Google Docs
    - add_to_grounding_artifacts: Helper for state management

The agent saves large binary data (PDFs, JSON) as ADK artifacts and stores
references in state.grounding_artifacts for use by downstream agents.
"""

# Google ADK Imports
from google.adk.agents.llm_agent import Agent
from google.adk.tools import ToolContext
from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest, LlmResponse
from google.genai.types import Content, Part, Blob

# Shared Imports
from ..shared.constants import GEMINI_MODEL
from ..shared.tools import list_saved_artifacts, list_current_state, make_part
from .content_grounding_tools import get_slides_data, slides_to_pdf, fetch_markdown_level, fetch_doc_as_pdf, extract_slides_id, extract_doc_id

# Utility Imports
import logging
import json
from typing import Dict, Any, Optional, Iterable
import uuid

# Tool Definitions

async def slides_id_to_artifacts(presentation_id: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Generate JSON metadata and PDF artifacts from a Google Slides presentation.
    
    This tool fetches slide content from Google Slides API, extracts metadata including
    slide titles, text content, and speaker notes, then generates:
    1. A JSON artifact containing structured slide metadata
    2. A PDF artifact simulating the presentation with speaker notes
    
    Both artifacts are saved to the ADK artifact store and referenced in the agent state
    under 'slide_artifact_reference' and 'grounding_artifacts'.

    Args:
        presentation_id: The Google Slides presentation ID, either as a full URL or just the isolated ID after the /d/
        tool_context: ADK ToolContext automatically injected at runtime for state/artifact management
    
    Returns:
        Dict containing a status (str): "success" or "error", and additional information about the created artifacts
    """
    # Normalize presentation_id if it's a full URL
    presentation_id = (presentation_id or "").strip()
    # Use regular expressions to isolate the ID from the URL if needed
    if "docs.google.com/presentation" in presentation_id:
        presentation_id = extract_slides_id(presentation_id)
    if not presentation_id or presentation_id == "":
        return {"status": "error", "message": "No valid Google Slides presentation ID provided."}


    # Use helper functions to get slide info
    slides_data = get_slides_data(presentation_id)
    # use data to render a PDF simulating slides + speaker notes
    pdf_bytes = slides_to_pdf(slides_data)
    
    # Create the slides_json artifact
    # Requires turning the content into bytes, encoding as a Part object, then saving via tool_context
    json_bytes = json.dumps(slides_data, indent=2, ensure_ascii=False).encode("utf-8")
    json_part = make_part("application/json", json_bytes)
    artifact_key_json = f"slides_{presentation_id}_data.json"
    version_json = await tool_context.save_artifact(filename=artifact_key_json, artifact=json_part)
    
    # Create the PDF artifact, using same pdf_bytes from above
    pdf_part = make_part("application/pdf", pdf_bytes)
    artifact_key_pdf = f"slides_{presentation_id}.pdf"
    version_pdf = await tool_context.save_artifact(filename=artifact_key_pdf, artifact=pdf_part)

    # Both artifacts are saved - now to update state data
    # Create a new "slide_reference" entry in state to hold the slide JSON data (needed for the base64 pngs later)

    slide_reference_data = {
        "presentation_id": presentation_id,
        "artifact_key_pdf": artifact_key_pdf,
        "artifact_version_pdf": version_pdf,
        "artifact_key_json": artifact_key_json,
        "artifact_version_json": version_json,
    }
    tool_context.state["slide_artifact_reference"] = slide_reference_data

    # And add the pdf references to the grounding_artifacts list
    # Because of ADK event management, the proper way to do this is retrieve the existing list, append, then re-save
    pdf_ref = {
        "type": "pdf",
        "key": artifact_key_pdf,
        "version": version_pdf,
        "mime_type": "application/pdf",
    }
    add_to_grounding_artifacts(pdf_ref, tool_context)

    # Return a descriptive message to the agent
    return {"status": "success", **slide_reference_data}

async def create_markdown_artifact(name: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Create a markdown artifact from a Code.org curriculum level.
    
    Fetches markdown content for a specified Code.org curriculum level and saves it as
    an ADK artifact. The artifact is added to the 'grounding_artifacts' list in state
    for use in tutorial video generation.
    
    **IMPORTANT:** Only use this tool when the user explicitly specifies a markdown level
    from the Code.org curriculum. Do not use for generic markdown files.

    Args:
        name: The name/identifier of the Code.org curriculum level (e.g., "Unit3-Lesson5")
        tool_context: ADK ToolContext automatically injected at runtime for state/artifact management
    
    Returns:
        Dict containing a status (str): "success" or "error", and additional information about the created artifacts
    """

    # Get the markdown content from level using a helper function
    markdown_content = await fetch_markdown_level(name)
    if not markdown_content:
        return {"status": "error", "message": f"Could not fetch markdown content for level: {name}"}

    # Save the markdown as an artifact
    markdown_bytes = markdown_content.encode("utf-8")
    markdown_part = make_part("text/markdown", markdown_bytes)
    artifact_key_md = f"{name}_level.md"
    version_md = await tool_context.save_artifact(filename=artifact_key_md, artifact=markdown_part)
    
    # And add the markdown references to the grounding_artifacts list
    markdown_ref = {
        "type": "markdown",
        "key": artifact_key_md,
        "version": version_md,
        "mime_type": "text/markdown",
    }
    add_to_grounding_artifacts(markdown_ref, tool_context)

    return {"status": "success", "markdown_ref": markdown_ref}

async def save_google_doc_as_pdf_artifact(doc_id: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Fetch a Google Doc as PDF and save it as an ADK artifact.
    
    Given a Google Doc ID, this tool exports the document as a PDF using the Google Docs
    export API, saves it as an ADK artifact, and adds the reference to 'grounding_artifacts'
    in the agent state.
    
    Args:
        doc_id: The Google Doc ID (the string after /d/ in a Google Docs URL)
                Example: For "https://docs.google.com/document/d/ABC123/edit",
                         use "ABC123"
        tool_context: ADK ToolContext automatically injected at runtime for state/artifact management
    
    Returns:
        Dict containing a status (str): "success" or "error", and additional information about the created artifacts
    """
    # Get the PDF of the google doc
    doc_id = (doc_id or "").strip()
    if not doc_id:
        return {"status": "error", "message": "No valid Google Doc ID provided."}

    # Check if a URL was provided instead of an ID
    if "docs.google.com/document" in doc_id:
        doc_id = extract_doc_id(doc_id)
    if not doc_id:
        return {"status": "error", "message": "No valid Google Doc ID provided."}

    export_url = f"https://docs.google.com/document/d/{doc_id}/export?format=pdf"
    result = await fetch_doc_as_pdf(export_url)
    # Check that it was successful
    if isinstance(result, dict) and result.get("status") == "error":
        return {
            "status": "error",
            "message": pdf_bytes.get("message", "Unknown error fetching Google Doc PDF.")
        }
    # Save the artifact
    pdf_bytes = result.get("pdf_bytes")
    pdf_part = make_part("application/pdf", pdf_bytes)
    out_name = f"google_doc_{doc_id}.pdf"
    version = await tool_context.save_artifact(filename=out_name, artifact=pdf_part)
    # Append the artifact to grounding_artifacts in state
    
    pdf_ref = {
        "type": "pdf",
        "key": out_name,
        "version": version,
        "mime_type": "application/pdf",
    }
    add_to_grounding_artifacts(pdf_ref, tool_context)

    return {"status": "success", "artifact_key": out_name, "artifact_version": version}

def add_to_grounding_artifacts(ref: Dict[str, Any], tool_context: ToolContext) -> None:
    """Add an artifact reference to the grounding_artifacts list in state.
    
    Helper function to append a new artifact reference to the grounding_artifacts
    list. Uses the copy-modify-write pattern required for ADK state updates.
    
    Args:
        ref: Artifact reference dictionary containing type, key, version, and mime_type
        tool_context: ADK ToolContext for accessing and modifying state
        
    Returns:
        None - modifies state in place
    """
    grounding_artifacts = tool_context.state.get("grounding_artifacts", [])
    grounding_artifacts.append(ref)
    tool_context.state["grounding_artifacts"] = grounding_artifacts


async def capture_pdf_before_model(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
) -> Optional[LlmResponse]:
    """
    - Finds any incoming PDF Part(s)
    - Saves them as artifacts
    - Replaces them in the request with a short text stub (optional but recommended)
    """
    parts = []
    # Get last message from the user
    if llm_request.contents and llm_request.contents[-1].role == 'user':
        parts = llm_request.contents[-1].parts

    for part in parts:
        inline = getattr(part, "inline_data", None)
        if not inline:
            continue

        mime = getattr(inline, "mime_type", "") or ""
        if mime != "application/pdf":
            continue

        # Generate a stable artifact filename
        filename = f"upload_{uuid.uuid4().hex}.pdf"

        # Save as an artifact (CallbackContext supports artifact operations)
        # (Method names are ADK-language specific; in Python it's typically save_artifact.)
        version = await callback_context.save_artifact(filename, part)
        pdf_ref = {
            "type": "pdf",
            "key": filename,
            "version": version,
            "mime_type": "application/pdf",
        }
        
        grounding_artifacts = callback_context.state.get("grounding_artifacts", [])
        grounding_artifacts.append(pdf_ref)
        callback_context.state["grounding_artifacts"] = grounding_artifacts

        logging.info("Saved uploaded PDF as artifact: %s (version=%s)", filename, version)

        # return static confirmation of PDF upload
        return LlmResponse(
            content=Content(
                parts=[Part(text=f"PDF has been uploaded to artifacts")],
                role="model" # Assign model role to the overriding response
            )
        )

    return None  # allow normal model call to proceed






DESCRIPTION = 'Collects and grounds content for tutorial video creation.'

INSTRUCTION = """**Role:** Content Grounding Agent

**Primary Objective:** 
You assist users in collecting and grounding content resources that will be used to create tutorial videos with voiceover narration and HTML display. Your goal is to gather, validate, and prepare all necessary materials before handing off to subsequent video generation agents.

**Workflow Overview:**
1. **Greet and Explain**: Introduce your role and explain what resources you can accept
2. **Collect Resources**: Use available tools to process user-provided content
3. **Validate and Confirm**: Show the user what has been collected by reviewing the `grounding_artifacts` in state
5. **Handoff**: Once confirmed, indicate readiness to proceed to the next stage

**Supported Resource Types and Tools:**

1. **Google Slides Presentations**
   - Tool: `slides_id_to_artifacts(presentation_id, tool_context)`
   - Expected input: Presentation ID from URL (e.g., "1a2b3c4d5e6f7g8h9")
   - Output: Creates both JSON metadata and PDF artifacts
   - Use when: User provides a Google Slides link or presentation ID

2. **Google Docs**
   - Tool: `save_google_doc_as_pdf_artifact(doc_id, tool_context)`
   - Expected input: Document ID from URL (the part after /d/)
   - Output: Creates a PDF artifact
   - Use when: User provides a Google Docs link or document ID

3. **Code.org Curriculum Markdown Levels**
   - Tool: `create_markdown_artifact(name, tool_context)`
   - Expected input: Level name/identifier (e.g., "Unit3-Lesson5", "CSD-U3-L5")
   - Output: Creates a markdown artifact
   - Use when: User **explicitly** mentions a Code.org curriculum level or markdown level
   - **Do NOT use for regular markdown files** - only for Code.org curriculum

4. **Uploaded PDF Documents**
   - Action: Save directly as an artifact
   - Use when: User uploads a PDF file
   - Note: These should be saved with descriptive filenames

5. **Other Formats**
   - Guide users to convert to PDF or provide as Google Slides/Docs
   - Be helpful in explaining conversion options

**State Management:**

All artifacts you create are tracked in the agent state:
- `grounding_artifacts`: List of all content artifacts (PDFs, markdown)
- `slide_artifact_reference`: Special reference for Google Slides (includes JSON metadata)
- do NOT use list_saved_artifacts tool to verify the users resources since there may be additional saved artifacts from other user sessions. Only the grounding_artifacts list in state is relevant for this session.

**Error Handling:**
- If a tool fails, explain the error to the user in simple terms
- Offer alternatives (e.g., "The Google Doc URL may be private. Can you share it publicly or upload a PDF instead?")
- Don't abandon the conversation - help troubleshoot

**Example Conversation Flow:**

User: "I want to create a video using my Google Slides presentation: [URL]"
You: [Extract presentation ID] → Use `slides_id_to_artifacts` → Confirm success
     "I've successfully loaded your Google Slides presentation. The content has been saved as a PDF and JSON metadata."
     → Review grounding_artifacts in the state to see what has been uploaded so far
     "Is this all the content you'd like to use for your tutorial video?"

**Completion Criteria:**
You're done when:
1. All user-requested resources have been processed
4. User confirms this is all the content they need

Once complete, inform the user that the content is ready for the next stage of video generation and transfer the user back to the json-video-agent.

"""


content_grounding_agent = None

try:
    content_grounding_agent = Agent(
        model=GEMINI_MODEL,
        name='content_grounding_agent',
        description=DESCRIPTION,
        instruction=INSTRUCTION,
        tools=[slides_id_to_artifacts, create_markdown_artifact, save_google_doc_as_pdf_artifact, list_saved_artifacts, list_current_state],
        before_model_callback=capture_pdf_before_model
    )   
    logging.info(f"✅ Sub-agent '{content_grounding_agent.name}' created using model '{GEMINI_MODEL}'.")
except Exception as e:
    logging.error(f"❌ Failed to create sub-agent 'content_grounding_agent': {e}")

