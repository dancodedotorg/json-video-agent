# Google ADK Imports
from google.adk.agents.llm_agent import Agent
from google.adk.agents.sequential_agent import SequentialAgent
from google.adk.tools import ToolContext

# Shared Imports
from ..shared.constants import GEMINI_MODEL
from ..shared.tools import list_saved_artifacts, list_current_state, make_part
from .elevenlabs_tools import elevenlabs_generation, ALL_VOICE_IDS

# Utilities
import base64
from typing import List, Dict, Any
import logging
import requests
from pydantic import BaseModel, Field
import copy

# ----------------------------
# Update schemas (for duration updates)
# ----------------------------
class DurationUpdate(BaseModel):
    """Patch for adding duration to a scene."""
    index: int = Field(description="Index into the top-level state['scenes'] array")
    duration: str = Field(description="Duration of scene audio (e.g., '5.23s' or 'auto')")

class DurationUpdateList(BaseModel):
    """List of duration updates for multiple scenes."""
    updates: List[DurationUpdate]

# ----------------------------
# Apply Updates Function
# ----------------------------

def apply_duration_updates(tool_context: ToolContext) -> Dict[str, Any]:
    """
    Merge state['duration_updates'] into state['scenes'] by index.
    
    This function reads duration updates and applies them to the scenes array.

    Expects:
      - tool_context.state['scenes']: List[dict] (must already exist)
      - tool_context.state['duration_updates']: {"updates":[{"index":int,"duration":str}, ...]}
      
    Updates:
      - tool_context.state['scenes']: List[dict] with duration property added
    """

    if "scenes" not in tool_context.state:
        return {"status": "error", "message": "Missing 'scenes' array in state"}
    if "duration_updates" not in tool_context.state:
        return {"status": "error", "message": "Missing 'duration_updates' in state"}

    scenes = copy.deepcopy(tool_context.state["scenes"])
    payload = copy.deepcopy(tool_context.state["duration_updates"])
    updates = payload.get("updates") or []

    updated = 0
    skipped: List[Dict[str, Any]] = []

    for u in updates:
        # u may be a dict (from state) or a pydantic model
        idx = u.get("index") if isinstance(u, dict) else getattr(u, "index", None)
        duration = u.get("duration") if isinstance(u, dict) else getattr(u, "duration", None)

        if not isinstance(idx, int) or not isinstance(duration, str):
            skipped.append({"update": u, "reason": "invalid update shape"})
            continue

        if 0 <= idx < len(scenes):
            scenes[idx]["duration"] = duration
            updated += 1
        else:
            skipped.append({"update": u, "reason": "index out of range"})

    tool_context.state["scenes"] = scenes
    tool_context.state["duration_updates__applied"] = {"updated": updated, "skipped": skipped}

    return {"status": "success", "updated": updated, "skipped": skipped}

AUDIO_GENERATION_PROMPT = """**Role:** Audio Generation Agent

**Primary Objective:** Generate an audio artifact from scenes and add duration information to each scene in state.

**Core Tasks and Conversational Workflow:**

1. Check that state['scenes'] exists with 'elevenlabs' properties and confirm with the user that this is the script they want to use for audio
2. Use the get_available_voices tool to ask the user which voice they want to generate the audio in
3. Get explicit permission from the user to generate this audio. Warn the user that this uses ElevenLabs credits
   - Also ask the user if they want to generate "fake audio". If they say yes: use the fake_audio_generation tool.
4. Once the user approves, use the audio_generation_tool to generate audio (saved to artifacts) and duration updates (saved to state)
5. Transfer to the duration_pipeline_agent sub-agent to apply duration updates to state['scenes']
6. Use list_saved_artifacts and list_current_state to verify audio artifact was created and durations were added to scenes

**Important Notes:**
- Audio bytes are stored in artifacts, NOT in state
- Only duration information is added to state['scenes']
- The audio artifact reference is stored in state['voiceover_audio_artifact']

"""



def get_available_voices() -> List[str]:
    """Return a list of available voice names"""
    return list(ALL_VOICE_IDS)

async def fake_audio_generation(tool_context: ToolContext) -> Dict[str, Any]:
    """Use this tool when testing. It will use a pre-generated audio file rather than spending elevenlabs credits"""
    logging.info("FAKE Audio Generation Tool invoked.")

    # Get data from state
    scenes = tool_context.state.get("scenes", [])
    if not scenes:
        logging.error("❌ 'scenes' not found in tool context state.")
        return {"status": "error", "message": "'scenes' not found in state. Return to audio_tags agent to generate scenes first."}

    # Create duration updates
    updates = []
    for idx in range(len(scenes)):
        updates.append({"index": idx, "duration": "auto"})
    
    # Download fake audio
    url = "https://raw.githubusercontent.com/dancodedotorg/sam_dan_silly/refs/heads/main/sam_dan.b64"
    b64_data = requests.get(url, timeout=10).text.strip()
    audio_bytes = base64.b64decode(b64_data)

    # Save artifact (UNCHANGED - audio bytes go to artifact, NOT state)
    audio_part = make_part("audio/mpeg", audio_bytes)
    artifact_key = f"voiceover_silly.mp3"
    version = await tool_context.save_artifact(filename=artifact_key, artifact=audio_part)

    artifact_ref = {
        "type": "mp3",
        "artifact_key": artifact_key,
        "artifact_version": version,
        "voice_name": "Dan and Sam",
        "mime_type": "audio/mpeg",
    }
    
    # Store artifact reference and duration updates in state
    tool_context.state["voiceover_audio_artifact"] = artifact_ref
    tool_context.state["duration_updates"] = {"updates": updates}

    return {"status": "success", "message": "Audio generation completed.", "audio_artifact": artifact_ref, "duration_updates_count": len(updates)}



async def audio_generation_tool(voice_name: str, tool_context: ToolContext) -> Dict[str, Any]:
    """Audio Generation Tool using ElevenLabs API.
    
    Generates audio from scenes with elevenlabs property and extracts duration for each scene.
    Audio bytes are saved to artifacts (NOT state). Duration updates are stored in state.
    """

    logging.info("🤖 Audio Generation Tool invoked.")

    # Get data from state - now using unified scenes array
    scenes = tool_context.state.get("scenes", [])
    if not scenes:
        logging.error("❌ 'scenes' not found in tool context state.")
        return {"status": "error", "message": "'scenes' not found in state. Return to audio_tags agent to generate scenes first."}

    # Build script object for elevenlabs_generation (expects old format)
    script_obj = {"scenes": copy.deepcopy(scenes)}

    # Audio generation via helper functions (UNCHANGED)
    result = elevenlabs_generation(script_obj=script_obj, voice_name=voice_name)

    # Validate audio before continuing (UNCHANGED)
    data_uri = result["audio"]
    if data_uri.startswith("data:"):
        try:
            header, b64_payload = data_uri.split(",", 1)
        except ValueError as e:
            return {"status": "error", "message": "Invalid data URI (missing comma)."}

        if ";base64" not in header:
            return {"status": "error", "message": "Data URI is not base64-encoded."}
    else:
        b64_payload = data_uri

    try:
        audio_bytes = base64.b64decode(b64_payload, validate=False)
    except Exception as e:
        logging.exception("❌ Failed to decode ElevenLabs audio data URI.")
        return {"status": "error", "message": f"Failed to decode audio: {e}"}
    
    # Save artifact (UNCHANGED - audio bytes to artifact, NOT state)
    audio_part = make_part("audio/mpeg", audio_bytes)
    artifact_key = f"voiceover_{voice_name}.mp3"
    version = await tool_context.save_artifact(filename=artifact_key, artifact=audio_part)

    # Avoid returning huge payloads (UNCHANGED)
    result.pop("audio", None)

    # Extract duration updates from result
    updates = []
    for idx, scene in enumerate(result.get("scenes", [])):
        if "duration" in scene:
            updates.append({"index": idx, "duration": scene["duration"]})

    artifact_ref = {
        "type": "mp3",
        "artifact_key": artifact_key,
        "artifact_version": version,
        "voice_name": voice_name,
        "mime_type": "audio/mpeg",
    }
    
    # Store artifact reference and duration updates in state
    tool_context.state["voiceover_audio_artifact"] = artifact_ref
    tool_context.state["duration_updates"] = {"updates": updates}

    return {"status": "success", "message": "Audio generation completed.", "audio_artifact": artifact_ref, "duration_updates_count": len(updates)}


# ----------------------------
# Sequential Agent Pattern: Apply Agent
# ----------------------------

duration_apply_agent = Agent(
    model=GEMINI_MODEL,
    name="duration_apply_agent",
    description="Applies duration updates to state['scenes'] deterministically.",
    instruction="Call apply_duration_updates to merge state['duration_updates'] into state['scenes']. When finished, let the user know the durations have been applied.",
    tools=[apply_duration_updates],
)

# ----------------------------
# Sequential Pipeline
# ----------------------------

duration_pipeline_agent = SequentialAgent(
    name="duration_pipeline_agent",
    description="Applies duration updates to scenes after audio generation.",
    sub_agents=[duration_apply_agent],
)

# ----------------------------
# Main Agent
# ----------------------------

audio_generation_agent = None

try:
    audio_generation_agent = Agent(
        model=GEMINI_MODEL,
        name='audio_generation_agent',
        description='Generates audio file and adds duration to scenes in state',
        instruction=AUDIO_GENERATION_PROMPT,
        tools=[get_available_voices, list_current_state, list_saved_artifacts, audio_generation_tool, fake_audio_generation],
        sub_agents=[duration_pipeline_agent],
    )
    logging.info(f"✅ Sub-agent '{audio_generation_agent.name}' created using model '{GEMINI_MODEL}'.")
except Exception as e:
    logging.error(f"❌ Failed to create sub-agent 'audio_generation_agent': {e}")