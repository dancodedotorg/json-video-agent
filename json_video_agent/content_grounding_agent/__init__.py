"""Content Grounding Agent - Imports and processes educational resources.

This package contains the agent responsible for collecting and grounding content
resources that will be used to create tutorial videos with voiceover narration
and HTML displays.

Main Components:
    - agent.py: Agent definition and tool functions for content import
    - content_grounding_tools.py: Helper utilities for Google APIs and content processing

Supported Resource Types:
    - Google Slides presentations (via Slides API)
    - Google Docs (via export API)
    - Code.org curriculum markdown levels (via GitHub)

The agent saves content as artifacts (PDFs, markdown) and stores references in
the session state for use by downstream agents.
"""

from . import agent
