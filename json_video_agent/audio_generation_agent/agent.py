# Google ADK Imports
from google.adk.agents.llm_agent import Agent
from google.adk.tools import ToolContext
from google.adk.agents.callback_context import CallbackContext

# Shared Imports
from ..shared.constants import GEMINI_MODEL
from ..shared.tools import list_saved_artifacts, list_current_state, make_part
from .elevenlabs_tools import elevenlabs_generation, ALL_VOICE_IDS

# Utilities
import base64
from typing import List, Dict, Any
import logging

AUDIO_GENERATION_PROMPT = """**Role:** Audio Generation Agent

**Primary Objective:** Your primary goal is to use the audio_generation_tool to generate an audio artifact based on the refined_scenes object in the session state.

**Core Tasks and Conversational Workflow:**

1. Check that refined_voiceover_scenes exists in the session state and confirm with the user that this is the script they want to use for audio
2. Use the get_available_voices tool to ask the user which voice they want to generate the audio in
3. Get explicit permission from the user to generate this audio. Warn the user that this uses ElevenLabs credits
4. Once the user approves, use the audio_generation_tool to generate audio and an updated scene object
5. Once the audio_generation_tool finishes, use the list_saved_artifacts tool and list_current_state tool to verify that an audio artifact was created and there is a scenes_with_duration value in the session state

"""



def get_available_voices() -> List[str]:
    """Return a list of available voice names"""
    return list(ALL_VOICE_IDS)

async def audio_generation_tool(voice_name: str, tool_context: ToolContext) -> Dict[str, Any]:
    """Audio Generation Tool using ElevenLabs API."""
    #TODO: Update docstring to be way more descriptive for LLM consumption

    logging.info("🤖 Audio Generation Tool invoked.")

    # Get data from state
    script_obj = tool_context.state.get("refined_voiceover_scenes", None)
    if not script_obj:
        logging.error("❌ 'refined_voiceover_scenes' not found in tool context state.")
        return {"status": "error", "message": "'refined_voiceover_scenes' not found in tool context state. Return to audio_tags agent to generate scenes first."}

    # Audio generation via helper functions
    result = elevenlabs_generation(script_obj=script_obj, voice_name=voice_name)

    # Validate audio before continuing
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
    
    # Save artifact
    audio_part = make_part("audio/mpeg", audio_bytes)
    artifact_key = f"voiceover_{voice_name}.mp3"
    version = await tool_context.save_artifact(filename=artifact_key, artifact=audio_part)


    # Avoid returning huge payloads
    result.pop("audio", None)

    artifact_ref = {
        "type": "mp3",
        "artifact_key": artifact_key,
        "artifact_version": version,
        "voice_name": voice_name,
        "mime_type": "audio/mpeg",
    }
    
    tool_context.state["voiceover_audio_artifact"] = artifact_ref
    tool_context.state["scenes_with_duration"] = result

    return {"status": "success", "message": "Audio generation completed.", "scenes_with_duration:": result, "audio_artifact": artifact_ref}


# ----------------------------
# Agent
# ----------------------------

def after_agent_adjust_state(callback_context: CallbackContext):
    # when entering agent: take existing top-level scenes and populate locally for this agent
    callback_context.state["scenes"] = callback_context.state.get("scenes_with_duration", {}).get("scenes", [])


audio_generation_agent = None

try:
    audio_generation_agent = Agent(
        model=GEMINI_MODEL,
        name='audio_generation_agent',
        description='You generate an audio file from the refined_voiceover_scenes stored in the session state',
        instruction=AUDIO_GENERATION_PROMPT,
        tools=[get_available_voices, list_current_state, list_saved_artifacts, audio_generation_tool],
        # after_agent_callback=after_agent_adjust_state
    )   
    logging.info(f"✅ Sub-agent '{audio_generation_agent.name}' created using model '{GEMINI_MODEL}'.")
except Exception as e:
    logging.error(f"❌ Failed to create sub-agent 'audio_generation_agent': {e}")