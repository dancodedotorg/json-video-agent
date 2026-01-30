"""Shared configuration constants and API clients for the JSON Video Agent system.

This module provides centralized configuration values and initialized API clients
that are used across all agents in the multi-agent system.

Constants:
    GEMINI_MODEL: The Gemini model identifier used for all agent LLM calls
    GOOGLE_API_KEY: Google AI API key loaded from environment variables
    GEMINI_CLIENT: Initialized Gemini client instance (shared across agents)
"""

from google import genai
import os
from dotenv import load_dotenv

load_dotenv()

# Model configuration for all agents (Flash variant for speed/cost balance)
GEMINI_MODEL = "gemini-2.5-flash"

# Google API key from environment (required for Gemini and image generation)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Shared Gemini client instance (reused across agent tools)
GEMINI_CLIENT = genai.Client(
    api_key=GOOGLE_API_KEY,
)