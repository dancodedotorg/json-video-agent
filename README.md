# JSON Video Agent

A multi-agent system for creating tutorial videos with AI-generated voiceovers and visual displays, built using Google's Agent Development Kit (ADK).

## Overview

The JSON Video Agent orchestrates a team of specialized AI agents to transform educational content (Google Slides, Docs, or markdown) into complete tutorial videos with synchronized voiceover narration and HTML-based visual displays. The final output is a JSON file containing scene-by-scene HTML slides and an audio track, ready for rendering in a video player.

### Key Features

- 🎙️ **AI-Generated Voiceovers** - Natural-sounding narration with ElevenLabs TTS
- 🎨 **Flexible Visual Options** - Reuse existing slides, generate AI images, or co-create custom HTML
- 📝 **Content Grounding** - Import from Google Slides, Docs, or Code.org curriculum
- 🔊 **Audio Enhancement** - Intelligent audio tags for expressive delivery
- ⚙️ **Sequential Processing** - Step-by-step workflow with user approval at each stage

## Architecture

The system uses a hierarchical multi-agent architecture:

```
┌─────────────────┐
│   Root Agent    │  Orchestrator
└────────┬────────┘
         │
    ┌────┴────────────────────────────┐
    │                                 │
    ├─► Content Grounding Agent      │  Imports resources
    │                                 │
    ├─► Voiceover Scene Agent        │  Generates scripts
    │                                 │
    ├─► Audio Tags Agent              │  Adds expression
    │                                 │
    ├─► Audio Generation Agent        │  Synthesizes speech
    │                                 │
    └─► HTML Generation Agent         │  Creates visuals
```

Each agent specializes in a specific task and maintains shared state for seamless data flow.

For detailed technical documentation, see [`ARCHITECTURE.md`](ARCHITECTURE.md).

## Quick Start

### Prerequisites

- Python 3.11+
- Google API Key (for Gemini models)
- ElevenLabs API Key (for audio generation)
- Google Service Account (for Slides/Docs access)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/json-video-agent.git
cd json-video-agent
```

2. Install dependencies:
```bash
cd json_video_agent
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
# Copy the example .env file
cp ".env example" .env

# Edit .env and add your API keys:
# - GOOGLE_API_KEY (for Gemini)
# - ELEVENLABS_API_KEY (for voice synthesis)
# - GOOGLE_SERVICE_ACCOUNT_JSON (base64-encoded JSON)
```

### Running the Agent
```bash
# From the root folder json-video-agent directory, NOT the agent subfolder
adk web
```

This will load the ADK web interface. Select "json_video_agent" from the dropdown and start chatting.

The agent will start in conversational mode. Follow the prompts to:
1. Ground your content (upload slides, docs, or markdown)
2. Generate voiceover scenes
3. Add audio tags for expression
4. Generate audio
5. Create HTML slides
6. Export final JSON

## Agent Responsibilities

### Content Grounding Agent
Collects and processes educational resources for the tutorial video.

**Supported inputs:**
- Google Slides presentations
- Google Docs
- Code.org curriculum markdown levels

**Output:** PDF and metadata artifacts stored in session state

### Voiceover Scene Agent
Generates voiceover narration scripts from grounded content.

**Options:**
- Preset concept video (slide-by-slide narration)
- Preset summary video (condensed review)
- Co-create (interactive scene generation)

**Output:** Scenes with `comment` and `speech` properties

### Audio Tags Agent
Enhances voiceover with ElevenLabs audio tags for expressive delivery.

**Enhancement examples:**
- `[thoughtful]` - Reflective tone
- `[excited]` - Enthusiastic delivery
- `[short pause]` - Timing control

**Output:** Scenes with `elevenlabs` property (tagged speech)

### Audio Generation Agent
Synthesizes speech using ElevenLabs API and calculates scene durations.

**Features:**
- Multiple voice options (Sam, Dan, Adam, Hope)
- Character-level timestamp alignment
- Automatic duration calculation

**Output:** MP3 audio artifact + `duration` property per scene

### HTML Generation Agent
Creates visual slides to accompany voiceover narration.

**Options:**
- Reuse original slide images
- Generate AI images (Gemini)
- Co-create custom HTML

**Output:** Final JSON export with `html` and `audio` data

## State Management

All agents share a unified state object that persists throughout the session:

```python
{
    "scenes": [               # Main data structure (updated by each agent)
        {
            "comment": str,    # Scene description
            "speech": str,     # Original voiceover text
            "elevenlabs": str, # Enhanced voiceover with audio tags
            "duration": str,   # Scene timing (e.g., "5.23s")
            "html": str        # Visual slide content
        }
    ],
    "grounding_artifacts": [], # List of content references
    "voiceover_audio_artifact": {}, # MP3 audio reference
    # ... other state data
}
```

## Output Format

The final exported JSON file contains:

```json
{
    "scenes": [
        {
            "comment": "Introduction to functions",
            "speech": "Welcome to this tutorial...",
            "elevenlabs": "[warmly] Welcome to this tutorial...",
            "duration": "4.52s",
            "html": "<html><body>...</body></html>"
        }
    ],
    "audio": "data:audio/mpeg;base64,..."
}
```

This can be consumed by a video player that synchronizes HTML slides with the audio timeline.

## Environment Variables

Required environment variables (see `.env example`):

- `GOOGLE_API_KEY` - Google AI API key for Gemini models
- `ELEVENLABS_API_KEY` - ElevenLabs API key for TTS
- `GOOGLE_SERVICE_ACCOUNT_JSON` - Base64-encoded service account credentials

## Project Structure

```
json-video-agent/
├── json_video_agent/
│   ├── agent.py                      # Root orchestrator agent
│   ├── shared/                       # Shared utilities
│   │   ├── constants.py              # Configuration
│   │   └── tools.py                  # Common tools
│   ├── content_grounding_agent/      # Content import
│   ├── voiceover_scene_agent/        # Script generation
│   ├── audio_tags_agent/             # Audio enhancement
│   ├── audio_generation_agent/       # Speech synthesis
│   └── html_generation_agent/        # Visual creation
├── plans/                            # Documentation plans
└── README.md                         # This file
```

## Development

### Adding New Agents

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for detailed guidance on:
- Agent communication patterns
- State management conventions
- Tool function patterns
- Error handling standards

## Acknowledgments

Built with:
- [Google Agent Development Kit (ADK)](https://github.com/google/adk-python)
- [Google Gemini](https://ai.google.dev/)
- [ElevenLabs](https://elevenlabs.io/)
