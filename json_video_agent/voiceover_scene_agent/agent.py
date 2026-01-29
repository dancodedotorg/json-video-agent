# Google ADK Imports
from google.adk.agents.llm_agent import Agent
from google.adk.tools import load_artifacts
from google.adk.models import LlmResponse
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.agent_tool import AgentTool
from google.genai.types import Content, Part
from google.adk.tools import ToolContext

# Shared imports
from ..shared.constants import GEMINI_MODEL
from ..shared.tools import list_grounding_artifacts, _part_to_candidate_json, _maybe_extract_json

# Utilities
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ValidationError, ConfigDict
import copy

# ----------------------------
# Output schema
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


VOICEOVER_SYSTEM_INSTRUCTION = """ Role:** Voiceover Scene Agent

**Primary Objective:** 
Assist the user in generating a voiceover script for a tutorial video based on previously grounded content. You will analyze the provided resources, break them down into manageable scenes, and create clear, concise voiceover narrations for each scene. You also have several preset voiceover tools that users can use for specific types of videos.

**Workflow Overview:**
1. **Greet and Explain**: Introduce your role and how you will generate scenes
2. **Provide Options**: List your available preset voiceover generation tools for different resource types
3. **Work with the User**: Either use an existing tool to generate a voiceover scene, or ask the user for guidance as you generate voiceover scenes based on the grounded content
4. **Validate and Confirm**: Show the user the generated scenes and ask for approval
5. **Handoff**: Once confirmed, indicate readiness to proceed to the next stage

**Supported Resource Types and Tools:**

1. **Concept Video From Slides**
   - Tool: `concept_video_agent_from_slides`
   - Expected input: A PDF file derived from Google Slides
   - Output: A JSON object containing an array of scenes with voiceover narrations for each slide
   - How to use: 
     - Use the `list_grounding_artifacts` tool to list all available grounding artifacts
     - Have the user select which PDF artifact they want to use
     - Provide the actual PDF content to the `concept_video_agent_from_slides` tool to generate scenes

2. **Summary Video From Slides**
    - Tool: `summary_video_agent_from_slides`
    - Expected input: A PDF file derived from Google Slides
    - Output: A JSON object containing an array of scenes that summarize the key concepts from the slide deck
    - How to use: 
      - Use the `list_grounding_artifacts` tool to list all available grounding artifacts
      - Have the user select which PDF artifact they want to use
      - Provide the actual PDF content to the `summary_video_agent_from_slides` tool to generate scenes

3. **Co-Create Together**
    - No specific tool; you will generate scenes directly in conversation with the user
    - Expected input: Any combination of grounded content artifacts
    - Output: A JSON object containing an array of scenes with voiceover narrations
    - How to use:
      - Use the `list_grounding_artifacts` tool to list all available grounding artifacts
      - Work with the user to decide how to break down the content into scenes
      - Generate voiceover narrations for each scene based on the grounded content
      - Use the `commit_initial_voiceover_scenes` tool frequently to save the generated scenes to state
      

**State Management:**

All artifacts you create are tracked in the agent state:
- `grounding_artifacts`: List of all content artifacts
- `initial_voiceover_scenes`: Will contain the final generated scenes for the voiceover video. This is populated by your tools, or when you are done working with your user



**Error Handling:**
- If a tool fails, explain the error to the user in simple terms
- Don't abandon the conversation - help troubleshoot

**Example Conversation Flow:**

User: "I want to use an existing Google Slides presentation for my tutorial video."
You: [use list_grounding_artifacts tool] "Great - here are the artifacts I have available: {...list of grounding_artifacts...}"
You: "Which one would you like to use for the voiceover script?"
User: "The one titled 'Intro to Python'."
You: [call `concept_video_agent_from_slides` tool with the selected PDF artifact reference]

**Completion Criteria:**
You're done when:
1. All user-requested resources have been processed
2. User confirms this is all the content they need
3. Used the `commit_initial_voiceover_scenes` tool to save the final scenes to state
4. Once this is done, transfer back to the json_video_agent

**Don't Forget:** Start by greeting the user and explaining the pre-made tools you have available, then ask if they want to use one of those or co-create these scenes with you.
"""

def commit_initial_voiceover_scenes(json_str: str, tool_context: ToolContext) -> Dict[str, Any]:
    """Updates the session state with the in-progress scenes being generated between the agent and the user.
    
    This tool commits the in-progress voiceover scenes being generated by the agent to the session state under 'initial_voiceover_scenes'.
    **Input Format:** The json_str input must conform to the SceneList schema, containing an array of scenes:
    {
      "scenes": [
        {
          "comment": "A brief comment about the scene",
          "speech": "The voiceover speech for this scene."
        },
        ...
      ]
    }
    do NOT include any preamble, such as ```json ``` or explanations - ONLY provide the JSON object.

    Args:
        json_str: The voiceover scenes as a str, conforming to the SceneList schema above.
        tool_context: ADK ToolContext automatically injected at runtime for state/artifact management
    
    Returns:
        Dict containing a status (str): "success" or "error", and additional information about the session state"""
    candidate_json = _maybe_extract_json(json_str)
    # Validate the JSON against the SceneList schema
    try:
        scenes = SceneList.model_validate_json(candidate_json)
    except ValidationError as e:
        return {
            "status": "error",
            "message": f"Provided JSON does not conform to SceneList schema: {e}"
        }

    # If we made it here: it worked!
    json_obj = scenes.model_dump()
    tool_context.state["initial_voiceover_scenes"] = json_obj
    return {
        "status": "success",
        "message": "Initial voiceover scenes committed to state.",
        "initial_voiceover_scenes": json_obj
    }


# Not currently used - wasn't working correctly. May need to debug if I continue to have issues with model output validation
def validate_scenes_after_model(
    callback_context: CallbackContext,
    llm_response: LlmResponse,
) -> Optional[LlmResponse]:
    """
    After-model callback:
      - If a valid SceneList is present already => return None (do nothing)
      - If we can clean/fix the model output into a valid SceneList => update the llm_response and return it
      - If we can't produce valid SceneList => replace response with an error SceneList JSON and return it
    """
    # If the model returned a tool call or no text, don't touch it.
    if not (llm_response.content and llm_response.content.parts):
        return None

    parts = llm_response.content.parts

    for i, part in enumerate(parts):
        # check if current part is already valid JSON that matches this agent's output schema
        try:
            # =================================================
            # TODO: THIS PART IS WRONG! Need to do part to json first, and then try to extract from the text.
            # I got my functions confused
            # =================================================
            scenes = SceneList.model_validate_json(part.text or "")
            # If I'm still here: already valid JSON, so just return None to keep the flow going
            logging.info(f"Response from agent-tool is already valid SceneList JSON.")
            return None
        except ValidationError:
            pass
        # if I made it here, the initial response wasn't valid JSON right away
        # so now I can try to parse it as valid json
        logging.warning(f"Response from agent-tool is not valid JSON - attempting recovery")
        try:
            candidate_json, raw = _part_to_candidate_json(part)
        except Exception:
            candidate_json, raw = None, getattr(part, "text", "")
        
        if not candidate_json:
            # something didn't work, so get out of this loop and try the next part
            # if this was the final part: then this goes to the fallback error logic
            continue

        try:
            scenes = SceneList.model_validate_json(candidate_json)
            # If I'm still here: candidate_json was valid logic, so need to update the LLM response with this.
            # This snippet adapted from https://google.github.io/adk-docs/callbacks/types-of-callbacks/#after-model-callback
            # Deep copy parts to avoid modifying original if other callbacks exist
            logging.info(f"Successfully recovered valid SceneList JSON from model response.")
            modified_parts = [copy.deepcopy(part) for part in llm_response.content.parts]
            modified_parts[i].text = candidate_json # Update the text

            new_response = LlmResponse(
                content=Content(role="model", parts=modified_parts))
            logging.info(f"[Callback] Returning modified response.")
            return new_response # Return the modified response
        except Exception as e:
            # If I made it here, the candidate json still didn't confirm to the schema (or something else was wrong), so continue in the loop
            continue

    # No valid JSON found in any part
    logging.error(f"Failed to recover valid SceneList JSON from model response - returning error message.")
    error_message = """{
        "scenes": [
            {
                "comment": "Error",
                "speech": "There was a parsing error generating voiceover scenes. Try asking the model to generate again and it may work"
            }
        ]
    }"""
    new_response = LlmResponse(
        content=Content(
            role="model", 
            parts=[Part(text=error_message)]
        )
    )
    return new_response

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
    output_key="initial_voiceover_scenes",
    #after_model_callback=validate_scenes_after_model,
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
    output_key="initial_voiceover_scenes",
    #after_model_callback=validate_scenes_after_model,
)



# ----------------------------
# Agent
# ----------------------------

def before_agent_preload_state(callback_context: CallbackContext):
    # when entering agent: take existing top-level scenes and populate locally for this agent
    callback_context.state["initial_voiceover_scenes"] = {
        "scenes": callback_context.state.get("scenes", [])
    }

def after_agent_adjust_state(callback_context: CallbackContext):
    # when entering agent: take existing top-level scenes and populate locally for this agent
    callback_context.state["scenes"] = callback_context.state.get("initial_voiceover_scenes", {}).get("scenes", [])

voiceoever_scene_agent = None

try:
    voiceover_scene_agent = Agent(
        model=GEMINI_MODEL,
        name="voiceover_scene_agent",
        description="Generates voiceover scenes for a tutorial video from artifacts in the session state",
        instruction=VOICEOVER_SYSTEM_INSTRUCTION,
        tools=[list_grounding_artifacts, commit_initial_voiceover_scenes, load_artifacts, AgentTool(agent=concept_video_agent_from_slides), AgentTool(agent=summary_video_agent_from_slides)],
        before_agent_callback=before_agent_preload_state,
        after_agent_callback=after_agent_adjust_state,
        # after_model_callback=validate_store_scenes_after_model,
        # output_key="scenes",
        # output_schema=SceneList,
    )
    logging.info(f"✅ Sub-agent '{voiceoever_scene_agent.name}' created using model '{GEMINI_MODEL}'.")
except Exception as e:
    logging.error(f"❌ Failed to create sub-agent 'content_grounding_agent': {e}")