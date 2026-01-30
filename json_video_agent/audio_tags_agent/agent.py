"""Audio tags agent implementation with sequential pipeline for tag generation.

This module defines the audio tags agent which enhances voiceover scripts with
ElevenLabs audio tags that control tone, pacing, emotion, and emphasis in
text-to-speech synthesis.

Key Components:
    - Pydantic schemas for audio tag update structures
    - Sequential pipeline agent (audio_tags_pipeline_agent)
    - Update generation and application functions

The agent reads scene.speech properties and writes enhanced scene.elevenlabs properties
with strategically placed audio tags like [thoughtful], [excited], [short pause], etc.
Uses a sequential pipeline pattern to ensure deterministic state updates.
"""

# Google ADK Imports
from google.adk.agents.llm_agent import Agent
from google.adk.agents.sequential_agent import SequentialAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools import ToolContext

# Shared imports
from ..shared.constants import GEMINI_MODEL
from ..shared.tools import list_grounding_artifacts, list_current_state
from .audio_tag_prompt import AUDIO_TAGS_PROMPT, AUDIO_TAGS_DESCRIPTION, AUDIO_TAG_GENERATION_INSTRUCTIONS

# Utilities
from typing import Any, Dict, List
from pydantic import BaseModel, Field, ConfigDict
import logging
import copy

# ----------------------------
# Update schemas (for sequential agent pattern)
# ----------------------------
class AudioTagUpdate(BaseModel):
    """Patch for adding ElevenLabs audio tags to a scene."""
    index: int = Field(description="Index into the top-level state['scenes'] array")
    elevenlabs: str = Field(description="The augmented ElevenLabs voiceover with SSML tags")

class AudioTagUpdateList(BaseModel):
    """List of audio tag updates for multiple scenes."""
    updates: List[AudioTagUpdate]

# ----------------------------
# Sequential Agent Pattern: Apply Updates Function
# ----------------------------

def apply_audio_tag_updates(tool_context: ToolContext) -> Dict[str, Any]:
    """
    Merge state['audio_tag_updates'] into state['scenes'] by index.
    
    This function reads audio tag updates (elevenlabs) and applies them
    to the scenes array.

    Expects:
      - tool_context.state['scenes']: List[dict] (must already exist with comment/speech)
      - tool_context.state['audio_tag_updates']: {"updates":[{"index":int,"elevenlabs":str}, ...]}
      
    Updates:
      - tool_context.state['scenes']: List[dict] with elevenlabs property added
    """

    if "scenes" not in tool_context.state:
        return {"status": "error", "message": "Missing 'scenes' array in state"}
    if "audio_tag_updates" not in tool_context.state:
        return {"status": "error", "message": "Missing 'audio_tag_updates' in state; generate updates first"}

    scenes = copy.deepcopy(tool_context.state["scenes"])
    payload = copy.deepcopy(tool_context.state["audio_tag_updates"])
    updates = payload.get("updates") or []

    updated = 0
    skipped: List[Dict[str, Any]] = []

    for u in updates:
        # u may be a dict (from state) or a pydantic model
        idx = u.get("index") if isinstance(u, dict) else getattr(u, "index", None)
        elevenlabs = u.get("elevenlabs") if isinstance(u, dict) else getattr(u, "elevenlabs", None)

        if not isinstance(idx, int) or not isinstance(elevenlabs, str):
            skipped.append({"update": u, "reason": "invalid update shape"})
            continue

        if 0 <= idx < len(scenes):
            scenes[idx]["elevenlabs"] = elevenlabs
            updated += 1
        else:
            skipped.append({"update": u, "reason": "index out of range"})

    tool_context.state["scenes"] = scenes
    tool_context.state["audio_tag_updates__applied"] = {"updated": updated, "skipped": skipped}

    return {"status": "success", "updated": updated, "skipped": skipped}

# ----------------------------
# Sequential Agent Pattern: Generate and Apply Agents
# ----------------------------

audio_tags_generate_updates_agent = Agent(
    model=GEMINI_MODEL,
    name="audio_tags_generate_updates_agent",
    description="Generates ElevenLabs audio tag updates for voiceover scripts.",
    instruction=AUDIO_TAG_GENERATION_INSTRUCTIONS,
    output_schema=AudioTagUpdateList,
    output_key="audio_tag_updates",
)

audio_tags_apply_updates_agent = Agent(
    model=GEMINI_MODEL,
    name="audio_tags_apply_updates_agent",
    description="Applies audio_tag_updates to state['scenes'] deterministically.",
    instruction="Call apply_audio_tag_updates to merge state['audio_tag_updates'] into state['scenes']. When you are finished, let the user know the task is complete.",
    tools=[apply_audio_tag_updates],
)

# ----------------------------
# Sequential Pipeline
# ----------------------------

audio_tags_pipeline_agent = SequentialAgent(
    name="audio_tags_pipeline_agent",
    description="Generates audio tag updates and applies them to scenes.",
    sub_agents=[audio_tags_generate_updates_agent, audio_tags_apply_updates_agent],
)

# ----------------------------
# Main Agent
# ----------------------------

audio_tags_agent = None

try:
    audio_tags_agent = Agent(
        model=GEMINI_MODEL,
        name='audio_tags_agent',
        description=AUDIO_TAGS_DESCRIPTION,
        instruction=AUDIO_TAGS_PROMPT,
        tools=[list_grounding_artifacts, list_current_state],
        sub_agents=[audio_tags_pipeline_agent],
    )
    logging.info(f"✅ Sub-agent '{audio_tags_agent.name}' created using model '{GEMINI_MODEL}'.")
except Exception as e:
    logging.error(f"❌ Failed to create sub-agent 'audio_tags_agent': {e}")