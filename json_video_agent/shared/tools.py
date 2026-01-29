import logging
from google.adk.tools import ToolContext
import re

async def list_saved_artifacts(tool_context: ToolContext) -> dict:
    """List all saved artifacts."""
    filenames = await tool_context.list_artifacts()
    return {
        "count": len(filenames),
        "files": filenames
    }

def list_current_state(tool_context: ToolContext) -> dict:
    """List the current session state."""
    current_state = tool_context.state.to_dict()
    logging.info(f"Current state: {current_state}")
    return {
        "status": "success",
        **current_state
    }

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)

def _maybe_extract_json(text: str) -> str:
    """
    Try to return a JSON object string.
    1) If text is already pure JSON -> return as-is
    2) If wrapped in ```json ... ``` -> extract the fenced block
    3) Otherwise, fall back to the original text (so caller can error cleanly)
    """
    text = (text or "").strip()
    if not text:
        return text

    # Common case: fenced JSON
    m = _JSON_FENCE_RE.search(text)
    if m:
        return m.group(1).strip()

    # Otherwise just return; caller will try json parsing and fail if it's not pure JSON
    return text

def _part_to_candidate_json(part) -> tuple[str | None, str | None]:
    """
    Returns (candidate_json_str, raw_text_for_debug) if this part contains JSON,
    else (None, None).
    """
    # 1) JSON directly attached as inline_data (best case)
    inline = getattr(part, "inline_data", None)
    if inline and getattr(inline, "mime_type", None) == "application/json":
        data = getattr(inline, "data", None)
        if isinstance(data, (bytes, bytearray)):
            s = data.decode("utf-8", errors="replace")
            return s, s
        if isinstance(data, str):
            return data, data

    # 2) JSON embedded in text
    text = getattr(part, "text", None) or ""
    if text.strip():
        candidate = _maybe_extract_json(text)
        if candidate:
            return candidate, text

    return None, None