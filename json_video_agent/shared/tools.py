"""Shared tool functions for ADK state and artifact management.

This module provides common utility functions used across all agents for:
    - State inspection and listing
    - Artifact creation and management
    - JSON extraction from agent responses
    - Content part parsing for structured output

These tools are available to all agents and provide standardized patterns for
working with the ADK framework's state and artifact systems.
"""

import logging
from google.adk.tools import ToolContext
import re
from google.genai.types import Part, Blob
from typing import Dict, Any, Tuple, Optional

async def list_saved_artifacts(tool_context: ToolContext) -> Dict[str, Any]:
    """List all artifacts saved in the current ADK session.
    
    Retrieves filenames of all artifacts that have been saved during the current
    session using tool_context.save_artifact(). Useful for debugging and verifying
    what content has been stored.
    
    Args:
        tool_context: ADK ToolContext for accessing the artifact store
        
    Returns:
        Dictionary containing:
            - count (int): Number of artifacts in the store
            - files (list): List of artifact filenames
    """
    filenames = await tool_context.list_artifacts()
    return {
        "count": len(filenames),
        "files": filenames
    }

def list_current_state(tool_context: ToolContext) -> Dict[str, Any]:
    """List the entire current session state.
    
    Returns all key-value pairs stored in the ADK state object. Useful for
    debugging state flow between agents and understanding what data is available.
    
    Args:
        tool_context: ADK ToolContext for accessing the session state
        
    Returns:
        Dictionary containing:
            - status (str): Always "success"
            - [all state keys]: All state data as key-value pairs
    """
    current_state = tool_context.state.to_dict()
    # logging.info(f"Current state: {current_state}")
    return {
        "status": "success",
        **current_state
    }

def list_grounding_artifacts(tool_context: ToolContext) -> Dict[str, Any]:
    """List content grounding artifacts from the current session.
    
    Retrieves references to educational content (PDFs, markdown) that have been
    imported by the content_grounding_agent. These artifacts are used as source
    material for generating voiceover scripts.
    
    Args:
        tool_context: ADK ToolContext for accessing the session state
        
    Returns:
        Dictionary containing:
            - count (int): Number of grounding artifacts
            - grounding_artifacts (list): List of artifact reference dictionaries
    """
    grounding_artifacts = tool_context.state.get("grounding_artifacts", [])
    return {
        "count": len(grounding_artifacts),
        "grounding_artifacts": grounding_artifacts
    }


def make_part(type: str, content: bytes) -> Part:
    """Create an ADK Part object for artifact storage.
    
    Wraps binary content in the ADK Part structure required for saving artifacts.
    The Part contains inline_data with mime_type and binary content.
    
    Args:
        type: MIME type of the content (e.g., "application/json", "audio/mpeg")
        content: Binary data to store in the artifact
        
    Returns:
        Part object ready for use with tool_context.save_artifact()
    """
    return Part(
        inline_data=Blob(
            mime_type=type,
            data=content,
        )
    )

# Regex pattern for extracting JSON from markdown code fences
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)

def _maybe_extract_json(text: str) -> str:
    """Extract JSON object from text, handling markdown code fences.
    
    Attempts to extract a JSON object string from text that may or may not be
    wrapped in markdown code fences (```json...```). This is useful for parsing
    LLM responses that sometimes include formatting.
    
    Processing logic:
        1) If text is already pure JSON -> return as-is
        2) If wrapped in ```json ... ``` -> extract the fenced block
        3) Otherwise, return original text (caller can attempt JSON parsing)
    
    Args:
        text: Input text that may contain JSON (possibly fenced)
        
    Returns:
        JSON string extracted from the input, or original text if no fence found
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

def _part_to_candidate_json(part: Part) -> Tuple[Optional[str], Optional[str]]:
    """Extract JSON candidate from an ADK Part object.
    
    Attempts to extract a JSON string from a Part object, checking both
    inline_data (for direct JSON attachments) and text content (for JSON
    embedded in text responses). Useful for parsing structured output from agents.
    
    Args:
        part: ADK Part object from an agent response
        
    Returns:
        Tuple of (candidate_json_str, raw_text_for_debug):
            - candidate_json_str: Extracted JSON string or None if no JSON found
            - raw_text_for_debug: Original text for debugging or None
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