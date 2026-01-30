"""
html_generation_agent

This module defines the HTML generation sub-agent and its tools for producing
HTML-backed "slides" for each voiceover scene and exporting a final JSON artifact
that includes both:
- `scenes`: one HTML slide per scene (plus any other scene metadata), and
- `audio`: a base64 data URI for the generated voiceover audio.

Expected state inputs (written by upstream agents/tools):
- scenes_with_duration: dict with {"scenes": [...]} (required by generation tools)
- slide_artifact_reference: dict with JSON artifact refs containing slide PNG base64 (required for slide-based tool)
- voiceover_audio_artifact: dict with audio artifact refs (required for final export)

State outputs written by this module:
- html_voiceover_scenes: dict with {"scenes": [...]} including "html" fields
- final_json_reference: dict with {"status": ..., "final_json_reference_data": {...}} (or error)
"""

# Google ADK Imports
from google.adk.agents.llm_agent import Agent
from google.adk.agents.sequential_agent import SequentialAgent
from google.adk.tools import ToolContext
from google import genai
from google.adk.agents.callback_context import CallbackContext

# Shared Imports
from ..shared.constants import GEMINI_MODEL
from ..shared.tools import list_saved_artifacts, list_current_state, make_part, _maybe_extract_json
from .image_gen import generate_image_for_scene

# Utilities
import copy
import base64
import logging
import json
from typing import Any, Dict, List
from pydantic import BaseModel, Field

# Load secrets
from dotenv import load_dotenv
import os
load_dotenv()


HTML_GENERATION_PROMPT = """**Role:** HTML Slide Generation Agent

**Primary Objective:**  
You generate HTML slide layouts that will be used as visual backgrounds for tutorial videos with voiceover narration. Your goal is to transform each voiceover scene into a corresponding HTML slide, ensuring consistency with timing, content, and available visual assets.

**Workflow Overview:**
1. **Greet and Explain**: Introduce your role and how you will generate html
2. **Provide Options**: List your available preset HTML generation generation tools
3. **Work with the User**: Either use an existing tool to generate HTML slides, or ask the user for guidance as you generate HTML based on the guidelines below
4. **Validate and Confirm**: Show the user the generated HTML and ask for approval
5. **Handoff**: Once confirmed, transfer the agent back to the parent agent for next steps.

**Supported Resource Types and Tools:**

1. **Generate Images from Slides**
   - Tool: `generate_html_from_slide_pngs`
   - Description: uses the original slides uploaded with the content_grounding agent to create images of each slide
   - How to use: 
     - Check the agent state for a `slide_artifact_reference`
     - If present, ask the user whether they want to reuse the existing slide images
     - If confirmed, call `generate_html_from_slide_pngs`
     - If declined, continue to the next step
   - This tool generates a final_output json artifact that the user can use for their video
   
2. **AI-Generated Images**
   - Tool: `generate_html_with_image_generation`
   - Description: Will use AI to generate a single image for each scene
   - How to use: 
     - Ask the user whether they would like to use AI-generated images for their slides
     - If confirmed, call `generate_html_with_image_generation`
     - If declined, proceed with text-based HTML generation
   - This tool generates a final_output json artifact that the user can use for their video

3. **Co-Create Together**
    - No specific tool, but this uses the `html_pipeline_agent` instead
    - How to use:
      - Ask the user if they want to co-create the HTML together
      - If confirmed, transfer control to the `html_pipeline_agent`
      - After the pipeline completes, ask the user if they want to save the final output.
      - If they confirm, use the `generate_final_export_obj` tool to create the final export object using this JSON

"""


# Helper function to generate final export object within this agent
async def generate_final_export_obj(scenes_parent_obj: Dict[List, Any], tool_context: ToolContext) -> Dict[str, Any]:
    """Generate and save the final export JSON artifact.

    This is a tool wrapper that reads the scenes from state and produces a final
    JSON artifact that includes `audio` as a base64 data URI.

    Scene source precedence:
        1) `html_voiceover_scenes` (co-created scenes with HTML)
        2) from context of converation so far

    Preconditions:
        - tool_context.state contains `voiceover_audio_artifact`
        - One of the scene sources above exists and contains "html" for each scene

    Side effects:
        - Saves `final_video_export.json` artifact (application/json)
        - Writes tool_context.state["final_json_reference"]

    Returns:
        A dict with status/message and final_json_reference_data on success.
    """
    

    if "html" not in scenes_parent_obj["scenes"][0]:
        return {
            "status": "error",
            "message": "Missing html field in scenes - return to html_generation_agent to generate it"
        }

    # Add audio back to scenes_parent_obj
    audio_artifact_ref = tool_context.state["voiceover_audio_artifact"]
    audio_filename = audio_artifact_ref["artifact_key"]
    audio_version = audio_artifact_ref["artifact_version"]
    audio_artifact = await tool_context.load_artifact(filename=audio_filename, version=audio_version)

    # 2) Extract bytes
    if not audio_artifact.inline_data or audio_artifact.inline_data.data is None:
        return {"status": "error", "message": "Artifact Part has no inline_data bytes."}

    raw: bytes = audio_artifact.inline_data.data

    # (Optional) sanity check
    mime = getattr(audio_artifact.inline_data, "mime_type", None)
    if mime and mime != "audio/mpeg":
        return {"status": "error", "message": f"Unexpected mime_type: {mime}"}

    # 3) Decode bytes -> audio string
    b64_payload: str = base64.b64encode(raw).decode("utf-8")
    audio_data_uri = f"data:audio/mpeg;base64,{b64_payload}"

    # put into dict
    scenes_parent_obj["audio"] = audio_data_uri

    # Save this as an artifact for export
    # 1) Prepare data for saving
    json_bytes = json.dumps(scenes_parent_obj, indent=2, ensure_ascii=False).encode("utf-8")
    json_part = make_part("application/json", json_bytes)
    artifact_key_json = f"final_video_export.json"
    # 2) Use tool call to save the artifact
    version_json = await tool_context.save_artifact(filename=artifact_key_json, artifact=json_part)

    final_json_reference_data = {
        "artifact_key": artifact_key_json,
        "artifact_version": version_json,
    }
    tool_context.state["final_json_reference"] = final_json_reference_data

    return {
        "status": "success",
        "message": "Successfully added HTML to scenes and saved final export artifact",
        "final_json_reference_data": final_json_reference_data
    }

async def generate_html_with_image_generation(tool_context: ToolContext) -> Dict[str, Any]:
    """Generate HTML slides by AI-generating one image per scene.

    Preconditions:
        - tool_context.state["scenes"] exists with duration properties

    Side effects:
        - Adds `html` field to each scene (image-only HTML slide)
        - Saves `final_video_export.json` artifact (via final export helper)
        - Writes tool_context.state["final_json_reference"]

    Returns:
        On success, includes final_json_reference_data.
    """

    logging.info("Generating HTML slides with image generation for each scene.")

    if "scenes" not in tool_context.state or not tool_context.state["scenes"]:
        return {
            "status": "error",
            "message": "Missing scenes - return to audio_generation_agent to generate scenes and durations"
        }
    
    # Initialize the client with your API key.
    # Re-use same client for all image generations in this call
    client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
    logging.info("Standalone Gemini Client initialized for image generation.")

    scenes_parent_obj = {"scenes": copy.deepcopy(tool_context.state["scenes"])}
    for i in range(len(scenes_parent_obj["scenes"])):
        logging.info(f"Generating image for scene {i}: {scenes_parent_obj['scenes'][i]['comment']}")
        comment = scenes_parent_obj["scenes"][i]["comment"]
        speech = scenes_parent_obj["scenes"][i]["speech"]
        img_base64 = generate_image_for_scene(client, comment, speech)
        logging.info(f"Image generated for scene {i}.")
        scenes_parent_obj["scenes"][i]["html"] = f"""<html><body><img style="width: 100%" src="{img_base64}" /></body></html>"""
    
    logging.info("All images generated and HTML slides created. Starting final export object generation.")
    final_json_reference_data = await generate_final_export_obj(scenes_parent_obj, tool_context)

    tool_context.state["final_json_reference"] = final_json_reference_data

    return {
        "status": "success",
        "message": "Successfully added HTML to scenes and saved final export artifact",
        **final_json_reference_data
    }

async def generate_html_from_slide_pngs(tool_context: ToolContext) -> Dict[str, Any]:
    """Generate HTML slides using existing slide PNGs stored in state.

    This reads slide metadata JSON (containing `png_base64` per slide) from the artifact
    referenced by tool_context.state["slide_artifact_reference"], then maps each slide image to
    the corresponding scene in tool_context.state["scenes"].

    Preconditions:
        - tool_context.state["slide_artifact_reference"] exists and contains artifact_key_json/artifact_version_json
        - tool_context.state["scenes"] exists with duration properties

    Side effects:
        - Adds `html` field to each scene (image-only HTML slide)
        - Saves `final_video_export.json` artifact (via final export helper)
        - Writes tool_context.state["final_json_reference"]

    Returns:
        On success, includes final_json_reference_data.
    """
    if "slide_artifact_reference" not in tool_context.state:
        return {
            "status": "error",
            "message": "Missing slide artifact in state - return to content_grounding_agent to generate it"
        }
    if "scenes" not in tool_context.state or not tool_context.state["scenes"]:
        return {
            "status": "error",
            "message": "Missing scenes - return to audio_generation_agent to generate scenes and durations"
        }
    # 1) get the json ref from the state
    slide_json_ref = tool_context.state["slide_artifact_reference"]
    artifact = await tool_context.load_artifact(
        filename=slide_json_ref["artifact_key_json"],
        version=slide_json_ref["artifact_version_json"],
    )

    # 2) Extract bytes
    if not artifact.inline_data or artifact.inline_data.data is None:
        return {"status": "error", "message": "Artifact Part has no inline_data bytes."}

    raw: bytes = artifact.inline_data.data

    # (Optional) sanity check
    mime = getattr(artifact.inline_data, "mime_type", None)
    if mime and mime != "application/json":
        return {"status": "error", "message": f"Unexpected mime_type: {mime}"}

    # 3) Decode bytes -> text
    text = raw.decode("utf-8")

    # 4) Parse JSON text -> python object
    slide_data = json.loads(text)
    scenes_parent_obj = {"scenes": copy.deepcopy(tool_context.state["scenes"])}
    

    # Create the "html" field with the base64 image in each slide
    if len(slide_data) != len(scenes_parent_obj["scenes"]):
        return {
            "status": "error",
            "message": "Length of slides data is not the same as number of scenes - a mismatch occurred somewhere. Make sure there is exactly one scene per slide."
        }

    for i in range(len(slide_data)):
        img_base64 = slide_data[i]['png_base64']
        scenes_parent_obj["scenes"][i]["html"] = f"""<html><body><img style="width: 100%" src="{img_base64}" /></body></html>"""

    # Call generate_final_export_obj to save the final json artifact by adding back the audio and doing artifact management
    final_json_reference_data = await generate_final_export_obj(scenes_parent_obj, tool_context)

    tool_context.state["final_json_reference"] = final_json_reference_data

    return {
        "status": "success",
        "message": "Successfully added HTML to scenes and saved final export artifact",
        **final_json_reference_data
    }

# Co-Creating HTML

# ----------------------------
# 1) Structured output: "updates" (NOT full scenes)
# ----------------------------

class HtmlUpdate(BaseModel):
    """Patch for a single scene's HTML."""
    index: int = Field(description="Index into the top-level state['scenes'] array")
    html: str = Field(description="Full HTML slide string to store on scenes[index]['html']")

class HtmlUpdateList(BaseModel):
    """List of patches for multiple scenes."""
    updates: List[HtmlUpdate]

# ----------------------------
# 3) Agent 1: generate HTML updates (structured output -> output_key)
# ----------------------------

HTML_GENERATION_INSTRUCTION = """
You generate HTML slide layouts for tutorial video scenes.

You will be given access to state['scenes'] (a list of scene objects).
For each scene, produce an HTML slide string and return ONLY an updates list.

Rules:
- Return ONLY: {"updates":[{"index":0,"html":"<div ...>...</div>"}, ...]}
- One update per scene index that you can generate.
- Do NOT return the full scenes array.
- Do NOT wrap output in ``` fences.
"""

html_generate_updates_agent = Agent(
    model=GEMINI_MODEL,
    name="html_generate_updates_agent",
    description="Generates HTML slide strings as index-based updates.",
    instruction=HTML_GENERATION_INSTRUCTION,
    # Optional tools to help with debugging / context
    # tools=[list_current_state],
    output_schema=HtmlUpdateList,
    output_key="html_updates",
)
# ----------------------------
# 4) Agent 2: apply updates deterministically (single writer to scenes)
# ----------------------------


def apply_html_updates(tool_context: ToolContext) -> Dict[str, Any]:
    """
    Merge state['html_updates'] into state['scenes'] by index.

    Expects:
      - tool_context.state['scenes']: List[dict]
      - tool_context.state['html_updates']: {"updates":[{"index":int,"html":str}, ...]}
    """

    if "scenes" not in tool_context.state:
        return {"status": "error", "message": "Missing 'scenes' array in state"}
    if "html_updates" not in tool_context.state:
        return {"status": "error", "message": "Missing 'html_updates' in array state; try re-running html_pipeline_agent"}

    scenes = copy.deepcopy(tool_context.state["scenes"])
    payload = copy.deepcopy(tool_context.state["html_updates"])
    updates = payload.get("updates") or []

    updated = 0
    skipped: List[Dict[str, Any]] = []

    for u in updates:
        # u may be a dict (from state) or a pydantic model, depending on how you store it
        idx = u.get("index") if isinstance(u, dict) else getattr(u, "index", None)
        html = u.get("html") if isinstance(u, dict) else getattr(u, "html", None)

        if not isinstance(idx, int) or not isinstance(html, str):
            skipped.append({"update": u, "reason": "invalid update shape"})
            continue

        if 0 <= idx < len(scenes):
            scenes[idx]["html"] = html
            updated += 1
        else:
            skipped.append({"update": u, "reason": "index out of range"})

    tool_context.state["scenes"] = scenes
    tool_context.state["html_updates__applied"] = {"updated": updated, "skipped": skipped}

    return {"status": "success", "updated": updated, "skipped": skipped}

html_apply_updates_agent = Agent(
    model=GEMINI_MODEL,
    name="html_apply_updates_agent",
    description="Applies html_updates to state['scenes'] deterministically.",
    instruction="Call apply_html_updates to merge state['html_updates'] into state['scenes']. Do not output anything else.",
    tools=[apply_html_updates],
)

# ----------------------------
# 5) Sequential pipeline agent
# ----------------------------

html_pipeline_agent = SequentialAgent(
    name="html_pipeline_agent",
    description="Generates HTML updates and applies them to scenes.",
    sub_agents=[html_generate_updates_agent, html_apply_updates_agent],
)


html_generation_agent = None

try:
    html_generation_agent = Agent(
        model=GEMINI_MODEL,
        name='html_generation_agent',
        description='Generates HTML for a tutorial video.',
        instruction=HTML_GENERATION_PROMPT,
        tools=[list_saved_artifacts, list_current_state, generate_html_from_slide_pngs, generate_html_with_image_generation, generate_final_export_obj],
        sub_agents=[html_pipeline_agent],
    )   
    logging.info(f"✅ Sub-agent '{html_generation_agent.name}' created using model '{GEMINI_MODEL}'.")
except Exception as e:
    logging.error(f"❌ Failed to create sub-agent 'html_generation_agent': {e}")