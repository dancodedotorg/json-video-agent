"""JSON Video Agent - Multi-agent system for creating tutorial videos.

This package contains the root orchestrator agent and all specialized sub-agents
for creating tutorial videos with AI-generated voiceovers and visual displays.

The system transforms educational content (Google Slides, Docs, or markdown) into
complete tutorial videos with synchronized narration and HTML-based visuals.

Main Components:
    - agent.py: Root orchestrator agent that manages the workflow
    - shared/: Common utilities and tools used across all agents
    - content_grounding_agent/: Imports and processes educational resources
    - voiceover_scene_agent/: Generates voiceover narration scripts
    - audio_tags_agent/: Enhances voiceover with expressive audio tags
    - audio_generation_agent/: Synthesizes speech using ElevenLabs
    - html_generation_agent/: Creates visual slides for each scene

Usage:
    from json_video_agent import root_agent
    # The root_agent is configured with all sub-agents and ready to use
"""

from . import agent
from .agent import root_agent

__all__ = ["root_agent"]