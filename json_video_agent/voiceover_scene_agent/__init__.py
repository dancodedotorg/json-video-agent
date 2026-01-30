"""Voiceover Scene Agent - Generates voiceover narration scripts for tutorial videos.

This package contains the agent responsible for creating voiceover scripts based on
grounded educational content. It supports multiple generation modes including preset
workflows and collaborative scene creation.

Main Components:
    - agent.py: Agent definition with preset sub-agents and sequential pipeline

Generation Modes:
    - Concept Video: Slide-by-slide detailed narration for each slide
    - Summary Video: Condensed review of key concepts across slides
    - Co-create: Interactive scene generation with user guidance

The agent uses both full scene generation (for presets) and update-based generation
(for co-creation) patterns, writing scene data with 'comment' and 'speech' properties
to the unified state.scenes array.
"""

from . import agent
