"""HTML Generation Agent - Creates visual slides for tutorial videos.

This package contains the agent responsible for generating HTML-based visual slides
that accompany voiceover narration in tutorial videos. It supports multiple generation
modes including reusing existing slides, AI image generation, and custom HTML creation.

Main Components:
    - agent.py: Agent definition with generation tools and HTML pipeline
    - image_gen.py: Gemini image generation integration for AI-created visuals

Generation Modes:
    - From Slides: Reuses PNG images from original Google Slides presentation
    - AI Images: Generates educational illustrations using Gemini image generation
    - Co-create: Interactive custom HTML slide creation with user

The agent reads scene metadata and writes scene.html properties containing complete
HTML slide markup. It also generates the final JSON export artifact that combines
all scene data with the audio file as a base64 data URI.
"""

from . import agent
