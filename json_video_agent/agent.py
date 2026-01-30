# Google ADK Imports
from google.adk.agents.llm_agent import Agent
from google.adk.apps import App
from google.adk.agents.callback_context import CallbackContext

# Shared Imports
from .shared.constants import GEMINI_MODEL
from .shared.tools import list_saved_artifacts, list_current_state

# Subagents
from .content_grounding_agent.agent import content_grounding_agent
from .voiceover_scene_agent.agent import voiceover_scene_agent
from .audio_tags_agent.agent import audio_tags_agent
from .audio_generation_agent.agent import audio_generation_agent
from .html_generation_agent.agent import html_generation_agent

# Setup logging across agents
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logging.info("Logging works ✅")

# Load env variables
from dotenv import load_dotenv
load_dotenv()

# Agent config
DESCRIPTION = """Orchestrates the creation of a voiceover tutorial video encoded in a JSON file, utilizing specialized sub-agents for content grounding, voiceover script generation, audio synthesis, visual display, and export formatting"""
INSTRUCTION = """

**Role:** Video Orchestrator Agent

**Primary Objective:** To guide the user step-by-step through the creation of a tutorial video featuring voiceover narration and display HTML. You will orchestrate a team of specialized sub-agents for content grounding, voiceover script generation, audio synthesis, visual display, and export formatting, seeking user approval at each stage.

Your primary task is to orchestrate the creation of a tutorial video. Your role is to manage the flow between these agents, data and artifacts created by each sub-agent is stored in the session state to be used by other agents. You are the curator and delegator and data-owner of this overall process while the sub-agents perform specific tasks.

**Available Sub-Agents:**
*   `content_grounding_agent`: Gathers and processes user-provided resources for the tutorial video.
*   `voiceover_scene_agent`: Generates voiceover scripts based on the grounded content.
*   `audio_tags_agent`: Augments the voiceover with audio tags for AI voice generation
*   `audio_generation_agent`: Generates the actual audio from the voiceovers and updates the duration of each scene
*   `html_generation_agent`: Generates slides as HTML to be displayed with the voiceovers in each scene

**Core Tasks and Conversational Workflow:**

1.  **Step 1: Introduction:**
    *   Welcome the user and list the available sub-agents that can help them accomplish their task
    *   Ask them which task they would like to complete and route to that particular sub-agent

**Important Considerations:**

*   **Be a Guide:** Your primary role is to be a helpful guide for the user. Keep your responses clear, concise, and friendly.
*   **One Step at a Time:** Do not move to the next step until the user has approved the current one.
*   **Manage State:** Keep track of the approved assets to use them as input for subsequent steps.
*   **Be Patient:** The user may want to make many changes. Be patient and accommodating. """

def setup_state(callback_context: CallbackContext):
    if "scenes" not in callback_context.state:
        callback_context.state["scenes"] = []
    if "grounding_artifacts" not in callback_context.state:
        callback_context.state["grounding_artifacts"] = []

# Create agent
root_agent = Agent(
    model=GEMINI_MODEL,
    name='root_agent',
    description=DESCRIPTION,
    instruction=INSTRUCTION,
    tools=[list_saved_artifacts, list_current_state],
    sub_agents=[content_grounding_agent, voiceover_scene_agent, audio_tags_agent, audio_generation_agent, html_generation_agent],
    before_agent_callback=setup_state,
)
logging.info(f"✅ Agent '{root_agent.name}' creating used model '{GEMINI_MODEL}'.")

# Setup app with root_agent (required for deployment)
app = App(
    name="json_video_agent",   # should match the folder name for best results
    root_agent=root_agent,
)