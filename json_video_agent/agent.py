# Google ADK Imports
from google.adk.agents.llm_agent import Agent
from google.adk.apps import App
from google.adk.agents.callback_context import CallbackContext

# Shared Imports
from .shared.constants import GEMINI_MODEL

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
DESCRIPTION = """agent description"""
INSTRUCTION = """agent instruction"""

def setup_state(callback_context: CallbackContext):
    callback_context.state["scenes"] = []

# Create agent
root_agent = Agent(
    model=GEMINI_MODEL,
    name='root_agent',
    description=DESCRIPTION,
    instruction=INSTRUCTION,
    before_agent_callback=setup_state,
)
logging.info(f"✅ Agent '{root_agent.name}' creating used model '{GEMINI_MODEL}'.")

# Setup app with root_agent (required for deployment)
app = App(
    name="json_video_agent",   # should match the folder name for best results
    root_agent=root_agent,
)