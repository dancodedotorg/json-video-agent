"""Audio Tags Agent - Enhances voiceover scripts with ElevenLabs audio tags.

This package contains the agent responsible for augmenting voiceover scripts with
expressive audio tags that control tone, pacing, and emotion in text-to-speech synthesis.

Main Components:
    - agent.py: Agent definition with sequential pipeline for tag generation
    - audio_tag_prompt.py: Detailed instructions and examples for audio tag usage

Audio Tag Capabilities:
    - Emotional expression (e.g., [thoughtful], [excited], [patient])
    - Pacing control (e.g., [short pause], [slows down], [rushed])
    - Tone setting (e.g., [dramatic tone], [lighthearted], [serious tone])
    - Emphasis (e.g., [emphasized], [understated])

The agent reads scene.speech properties and writes enhanced scene.elevenlabs properties
with strategically placed audio tags for natural, engaging narration.
"""

from . import agent
