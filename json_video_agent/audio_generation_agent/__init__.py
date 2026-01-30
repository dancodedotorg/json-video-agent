"""Audio Generation Agent - Synthesizes speech and calculates scene timings.

This package contains the agent responsible for generating audio narration from
voiceover scripts using the ElevenLabs text-to-speech API, and calculating precise
scene durations from character-level timestamp alignment data.

Main Components:
    - agent.py: Agent definition with audio generation tools and duration pipeline
    - elevenlabs_tools.py: ElevenLabs API integration and duration calculation logic

Key Features:
    - Speech synthesis with multiple voice options
    - Character-level timestamp alignment
    - Automatic scene duration calculation
    - Support for audio tags (via ElevenLabs V3 model)
    - Fake audio generation for testing without API costs

The agent reads scene.elevenlabs properties, generates MP3 audio (stored as artifact),
and writes scene.duration properties with calculated timing for each scene.
"""

from . import agent
