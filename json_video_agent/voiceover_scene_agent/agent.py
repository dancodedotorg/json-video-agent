"""Voiceover scene agent implementation with preset workflows and sequential pipeline.

This module defines the voiceover scene agent which generates narration scripts from
grounded educational content. It supports multiple generation modes:
    - Preset concept video (slide-by-slide detailed narration)
    - Preset summary video (condensed review of key concepts)
    - Co-create pipeline (interactive scene generation with user)

Key Components:
    - Pydantic schemas for scene data and update structures
    - Preset sub-agents (concept_video_agent, summary_video_agent)
    - Sequential pipeline agent (voiceover_pipeline_agent)
    - Update conversion utilities for compatibility between patterns

The agent reads grounded artifacts and writes scene data with 'comment' and 'speech'
properties to the unified state.scenes array.
"""

# Google ADK Imports
from google.adk.agents.llm_agent import Agent
from google.adk.agents.sequential_agent import SequentialAgent
from google.adk.tools import load_artifacts
from google.adk.models import LlmResponse
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.agent_tool import AgentTool
from google.genai.types import Content, Part
from google.adk.tools import ToolContext

# Shared imports
from ..shared.constants import GEMINI_MODEL
from ..shared.tools import list_grounding_artifacts, _part_to_candidate_json

# Utilities
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ValidationError, ConfigDict
import copy

# ----------------------------
# Update schemas (for sequential agent pattern)
# ----------------------------
class VoiceoverUpdate(BaseModel):
    """Patch for adding voiceover properties to a scene."""
    index: int = Field(description="Index into the top-level state['scenes'] array")
    comment: str = Field(description="A 1-sentence metadata comment for the scene")
    speech: str = Field(description="The voiceover speech for this particular scene")

class VoiceoverUpdateList(BaseModel):
    """List of voiceover updates for multiple scenes."""
    updates: List[VoiceoverUpdate]

# ----------------------------
# Legacy schemas (for preset sub-agents that return full scene lists)
# ----------------------------
class Scene(BaseModel):
    """A single scene containing a comment and speech"""
    model_config = ConfigDict(extra="allow")
    comment: str = Field(description="A 1-sentence metadata comment for the generated scene")
    speech: str = Field(description="The voiceover speech for this particular scene")

class SceneList(BaseModel):
    """A list of one or more scenes."""
    model_config = ConfigDict(extra="allow")
    scenes: List[Scene]


VOICEOVER_SYSTEM_INSTRUCTION = """**Role:** Voiceover Scene Agent

**Primary Objective:**
Assist the user in generating a voiceover script for a tutorial video based on previously grounded content. You will analyze the provided resources, break them down into manageable scenes, and create clear, concise voiceover narrations for each scene. You also have several preset voiceover tools that users can use for specific types of videos.

**Workflow Overview:**
1. **Greet and Explain**: Introduce your role and how you will generate scenes
2. **Provide Options**: List your available preset voiceover generation tools for different resource types
3. **Work with the User**: Either use an existing tool to generate a voiceover scene, or ask the user for guidance as you generate voiceover scenes based on the grounded content
4. **Validate and Confirm**: Show the user the generated scenes and ask for approval
5. **Handoff**: Once confirmed, transfer the agent back to the parent agent for next steps.

**Supported Resource Types and Tools:**

1. **Concept Video From Slides**
   - Tool: `concept_video_agent_from_slides`
   - Expected input: A PDF file derived from Google Slides
   - Output: Adds voiceover comment and speech to state['scenes'] for each slide
   - How to use:
     - Use the `list_grounding_artifacts` tool to list all available grounding artifacts
     - Have the user select which PDF artifact they want to use
     - Call the `concept_video_agent_from_slides` sub-agent to generate scenes

2. **Summary Video From Slides**
    - Tool: `summary_video_agent_from_slides`
    - Expected input: A PDF file derived from Google Slides
    - Output: Adds voiceover scenes that summarize the key concepts to state['scenes']
    - How to use:
      - Use the `list_grounding_artifacts` tool to list all available grounding artifacts
      - Have the user select which PDF artifact they want to use
      - Call the `summary_video_agent_from_slides` sub-agent to generate scenes

3. **Co-Create Together**
    - Sub-agent: `voiceover_pipeline_agent`
    - Expected input: Any combination of grounded content artifacts
    - Output: Adds voiceover comment and speech to state['scenes']
    - How to use:
      - Use the `list_grounding_artifacts` tool to list all available grounding artifacts
      - Work with the user to decide how to break down the content into scenes
      - Transfer to the `voiceover_pipeline_agent` to collaboratively generate voiceover narrations
      

**State Management:**

All data is tracked in the unified agent state:
- `grounding_artifacts`: List of all content artifacts
- `scenes`: Unified array where each scene will have 'comment' and 'speech' properties added by this agent



**Error Handling:**
- If a tool fails, explain the error to the user in simple terms
- Don't abandon the conversation - help troubleshoot

**Example Conversation Flow:**

User: "I want to use an existing Google Slides presentation for my tutorial video."
You: [use list_grounding_artifacts tool] "Great - here are the artifacts I have available: {...list of grounding_artifacts...}"
You: "Which one would you like to use for the voiceover script?"
User: "The one titled 'Intro to Python'."
You: [transfer to `concept_video_agent_from_slides` sub-agent with the selected PDF artifact reference]

**Completion Criteria:**
You're done when:
1. All user-requested resources have been processed
2. User confirms this is all the content they need
3. Scenes have been added to state['scenes'] with voiceover content
4. Once this is done, transfer back to the json_video_agent

**Don't Forget:** Start by greeting the user and explaining the pre-made tools you have available, then ask if they want to use one of those or co-create these scenes with you.
"""

# ----------------------------
# Sequential Agent Pattern: Apply Updates Function
# ----------------------------

def apply_voiceover_updates(tool_context: ToolContext) -> Dict[str, Any]:
    """
    Merge state['voiceover_updates'] into state['scenes'] by index.
    
    This function reads voiceover updates (comment, speech) and applies them
    to the scenes array, creating new scene objects as needed.

    Expects:
      - tool_context.state['voiceover_updates']: {"updates":[{"index":int,"comment":str,"speech":str}, ...]}
      
    Updates:
      - tool_context.state['scenes']: List[dict] with comment and speech added
    """

    if "voiceover_updates" not in tool_context.state:
        return {"status": "error", "message": "Missing 'voiceover_updates' in state; generate updates first"}

    scenes = copy.deepcopy(tool_context.state.get("scenes", []))
    payload = copy.deepcopy(tool_context.state["voiceover_updates"])
    updates = payload.get("updates") or []

    updated = 0
    created = 0
    skipped: List[Dict[str, Any]] = []

    for u in updates:
        # u may be a dict (from state) or a pydantic model
        idx = u.get("index") if isinstance(u, dict) else getattr(u, "index", None)
        comment = u.get("comment") if isinstance(u, dict) else getattr(u, "comment", None)
        speech = u.get("speech") if isinstance(u, dict) else getattr(u, "speech", None)

        if not isinstance(idx, int) or not isinstance(comment, str) or not isinstance(speech, str):
            skipped.append({"update": u, "reason": "invalid update shape"})
            continue

        # Extend scenes array if needed
        while len(scenes) <= idx:
            scenes.append({})
            created += 1

        scenes[idx]["comment"] = comment
        scenes[idx]["speech"] = speech
        updated += 1

    tool_context.state["scenes"] = scenes
    tool_context.state["voiceover_updates__applied"] = {"updated": updated, "created": created, "skipped": skipped}

    return {"status": "success", "updated": updated, "created": created, "skipped": skipped}

# ----------------------------
# Helper: Convert SceneList to VoiceoverUpdateList
# ----------------------------

def _convert_scenes_to_updates(callback_context: CallbackContext):
    """
    After a preset agent returns a full SceneList, convert it to VoiceoverUpdateList
    and apply the updates directly to state['scenes'].
    
    This allows preset agents to return full scenes while maintaining compatibility
    with the sequential update pattern.
    """
    # Check if we have a full scene list (from preset agents)
    if "preset_scene_output" in callback_context.state:
        scene_list = callback_context.state["preset_scene_output"]
        scenes_output = scene_list.get("scenes", [])
        
        # Get existing scenes array or create new one
        scenes = copy.deepcopy(callback_context.state.get("scenes", []))
        
        # Apply each scene directly to the scenes array
        for idx, scene in enumerate(scenes_output):
            # Extend scenes array if needed
            while len(scenes) <= idx:
                scenes.append({})
            
            # Apply comment and speech
            scenes[idx]["comment"] = scene.get("comment", "")
            scenes[idx]["speech"] = scene.get("speech", "")
        
        # Update state
        callback_context.state["scenes"] = scenes
        logging.info(f"Applied {len(scenes_output)} preset scenes to state['scenes']")
        
        # Also store in updates format for consistency
        updates = []
        for idx, scene in enumerate(scenes_output):
            updates.append({
                "index": idx,
                "comment": scene.get("comment", ""),
                "speech": scene.get("speech", "")
            })
        callback_context.state["voiceover_updates"] = {"updates": updates}

# ----------------------------
# Concept Video Sub Agent as Tool
# ----------------------------

CONCEPT_VIDEO_INSTRUCTIONS = """You are generating voiceover scripts for a high school introductory Python course. You will be provided a set of slides - for each slide: generate a voiceover narration explaining the content of the slide.

Start by using the `load_artifacts` tool to load the slide PDF artifact provided to you. Then, for each slide in the PDF, generate a concise voiceover narration that explains the content of that slide in a way that is engaging and easy to understand for high school students.

** Guidelines: **
- DO act as a patient, clear, concise, warm tutor who is helping to explain concepts and key steps to students.
- DO generate a voiceover for each uniqe slide and do not combine slides.
- Do NOT use academic vocabulary other than what is included in the slides. Instead, use language appropriate for a teenager.
- Do NOT include markdown text such as ** or `` in your voiceover
- Do NOT vary significantly from the content on the slides, and keep explanations short and concise for each slide.
- Do NOT mention the Unit Guide - focus only on the concept and skill being introduced in the slides.
- DO format your response as a JSON object with the property "scenes", then an array of objects with properties "comment" and "speech".

** Examples: **
- 'Welcome! This is a quick byte about functions.
- "So, what exactly is a function? A function is a named block of code that performs a specific task. They are incredibly useful because they allow us to reuse code and organize our programs more efficiently. Let's see how functions work in code."
- 'Here's a simple Python program that uses a function to print the greeting "hello world" to the screen. We'll go through this program step by step to understand how it works.'
- 'The first step is to define your function, which is where you give it a name and specify the commands you want it to run. We use the keyword "def" to indicate that we are defining a new function.
- 'Next, we give our function a descriptive name. In this example, our function is called "greet".'
- "When we define a function, we always include parenthesis and a colon. The colon tells the program we're about to enter the specific steps of our function."
- 'speech': 'After the definition, each line of our function needs to be indented - otherwise we'll get a syntax error. This function just has one line: it'll print "Hello World".'
- 'Once we've defined our function, the next step is to call it. You do that by typing the name of the function with its parenthesis. In our case, we'd type "greet" with an open and close parenthesis.'
- "When the program runs and gets to this function, it will look up it's definition from earlier in the program..."
- 'And then run the code inside the definition. In this case, it would print Hello World.'

**Output Format:**
    Return a JSON object that conforms to the SceneList schema, containing an array of scenes:
    {
      "scenes": [
        {
          "comment": "A brief comment about the scene",
          "speech": "The voiceover speech for this scene."
        },
        ...
      ]
    }
    
    do NOT include any preamble, such as ```json ``` or explanations - ONLY return the JSON object.

Final Reminder: You MUST base your scenes on the provided PDF documents using load_artifacts, and your resulting scenes MUST have the same number of scenes as slides in the PDF.
"""

concept_video_agent_from_slides = Agent(
    model=GEMINI_MODEL,
    name="concept_video_agent_from_slides",
    description="Generates voiceover scenes for a tutorial video from a specific slide artifact in the session state",
    instruction=CONCEPT_VIDEO_INSTRUCTIONS,
    tools=[load_artifacts],
    output_schema=SceneList,
    output_key="preset_scene_output",  # Changed to temp key
    after_agent_callback=_convert_scenes_to_updates,  # Convert to updates
)

# ----------------------------
# Summary From Slides Sub Agent as Tool
# ----------------------------

SUMMARY_VIDEO_INSTRUCTIONS = """You are generating a condensed review voiceover for a high school introductory Python course. The purpose of this voiceover is to help students who may have been absent understand the key concepts from the lesson.

You will be provided a slide deck as a PDF. Start by using the `load_artifacts` tool to load the slide PDF artifact provided to you. Review the entire slide deck before generating any output.

Instead of creating narration for each slide, you will synthesize the content of the full slide deck and decide how to summarize the most important ideas, concepts, and skills introduced in the lesson. Your goal is to produce a succinct, concept-focused review that explains what students should understand after this lesson.

Focus on:
- Core concepts and ideas introduced in the slides
- Important vocabulary or syntax that students need to recognize or understand
- How ideas connect or build on one another across the lesson

Ignore or minimize:
- Specific activities, exercises, or step-by-step tasks students were asked to do
- Instructions like “try this,” “pause here,” or “work with a partner,” unless they help clarify a concept
- Redundant examples unless they are necessary to explain an idea clearly

You should make decisions about:
- Which concepts are essential to include
- How to explain them clearly and simply
- How to combine related ideas into a shorter, cohesive explanation

**Guidelines:**
- DO act as a patient, clear, concise, warm tutor helping a student catch up.
- DO use language appropriate for a high school student.
- DO summarize across slides rather than repeating slide-by-slide content.
- DO keep the final voiceover succinct and focused on understanding, not procedure.
- DO base all explanations directly on the content of the provided slides.
- Do NOT introduce concepts that are not present in the slide deck.
- Do NOT use academic vocabulary beyond what appears in the slides.
- Do NOT include markdown text such as ** or ``.
- Do NOT mention slide numbers, activities, or the Unit Guide.

**Output Format:**
Format your response as a JSON object with the property "scenes", containing an array of objects with properties "comment" and "speech".

Each scene should represent a major concept or idea from the lesson, not an individual slide.

Example structure:
{
  "scenes": [
    {
      "comment": "Overview of the main idea",
      "speech": "This lesson introduces the idea of functions in Python..."
    },
    {
      "comment": "Key syntax and purpose",
      "speech": "A function is a named block of code that performs a specific task..."
    }
  ]
}

Final Reminder:
- You MUST base your review on the provided PDF using load_artifacts.
- You MUST review the entire slide deck before generating scenes.
- The number of scenes does NOT need to match the number of slides.
- The final voiceover should feel like a short lesson recap that helps an absent student understand the key takeaways.
"""

summary_video_agent_from_slides = Agent(
    model=GEMINI_MODEL,
    name="summary_video_agent_from_slides",
    description="Generates voiceover scenes that summarize the conent of a slide deck used in a lesson. Use this tool when you want to summarize a deck rather than create a narration for each specific slide.",
    instruction=SUMMARY_VIDEO_INSTRUCTIONS,
    tools=[load_artifacts],
    output_schema=SceneList,
    output_key="preset_scene_output",  # Changed to temp key
    after_agent_callback=_convert_scenes_to_updates,  # Convert to updates
)

# ----------------------------
# Sequential Agent Pattern: Generate and Apply Agents
# ----------------------------

VOICEOVER_GENERATE_INSTRUCTION = """
You generate voiceover scripts for tutorial video scenes.

You will be given access to state['scenes'] (may be empty or contain partial scene data).
For each scene you want to create, produce a 'comment' and 'speech' and return as updates.

Rules:
- Return ONLY: {"updates":[{"index":0,"comment":"...","speech":"..."}, ...]}
- One update per scene you want to create or modify
- Do NOT return the full scenes array
- Do NOT wrap output in ``` fences

The 'comment' is a brief 1-sentence description of what the scene is about.
The 'speech' is the actual voiceover narration text for that scene.
"""

voiceover_generate_updates_agent = Agent(
    model=GEMINI_MODEL,
    name="voiceover_generate_updates_agent",
    description="Generates voiceover comment and speech as index-based updates.",
    instruction=VOICEOVER_GENERATE_INSTRUCTION,
    output_schema=VoiceoverUpdateList,
    output_key="voiceover_updates",
)

voiceover_apply_updates_agent = Agent(
    model=GEMINI_MODEL,
    name="voiceover_apply_updates_agent",
    description="Applies voiceover_updates to state['scenes'] deterministically.",
    instruction="Call apply_voiceover_updates to merge state['voiceover_updates'] into state['scenes']. When you are finished, let the user know your task is complete",
    tools=[apply_voiceover_updates],
)

# ----------------------------
# Sequential Pipeline
# ----------------------------

voiceover_pipeline_agent = SequentialAgent(
    name="voiceover_pipeline_agent",
    description="Generates voiceover updates and applies them to scenes.",
    sub_agents=[voiceover_generate_updates_agent, voiceover_apply_updates_agent],
)

# ----------------------------
# Main Agent
# ----------------------------

voiceover_scene_agent = None

try:
    voiceover_scene_agent = Agent(
        model=GEMINI_MODEL,
        name="voiceover_scene_agent",
        description="Generates voiceover scenes for a tutorial video from artifacts in the session state",
        instruction=VOICEOVER_SYSTEM_INSTRUCTION,
        tools=[list_grounding_artifacts, load_artifacts, AgentTool(agent=concept_video_agent_from_slides), AgentTool(agent=summary_video_agent_from_slides)],
        sub_agents=[voiceover_pipeline_agent],
    )
    logging.info(f"✅ Sub-agent '{voiceover_scene_agent.name}' created using model '{GEMINI_MODEL}'.")
except Exception as e:
    logging.error(f"❌ Failed to create sub-agent 'voiceover_scene_agent': {e}")




