# JSON Video Agent - Technical Architecture

This document provides a detailed technical walkthrough of the multi-agent system architecture, state management patterns, and implementation details.

## Table of Contents

- [System Overview](#system-overview)
- [Multi-Agent Architecture](#multi-agent-architecture)
- [State Management](#state-management)
- [Data Flow](#data-flow)
- [Agent Communication Patterns](#agent-communication-patterns)
- [Tool Function Patterns](#tool-function-patterns)
- [Sequential Pipeline Pattern](#sequential-pipeline-pattern)
- [Error Handling Conventions](#error-handling-conventions)
- [Artifact Management](#artifact-management)

## System Overview

The JSON Video Agent is built on Google's Agent Development Kit (ADK), which provides:
- Agent-to-agent communication
- Persistent state management
- Artifact storage and retrieval
- Tool function execution
- Structured output schemas (Pydantic)

### Design Philosophy

1. **Separation of Concerns** - Each agent has a single, well-defined responsibility
2. **User Approval** - Each stage requires user confirmation before proceeding
3. **State-Driven** - All data flows through a unified state object
4. **Artifact-Backed** - Large binary data (PDFs, audio, images) stored as artifacts, not in state
5. **Sequential Updates** - Updates are applied deterministically to avoid race conditions

## Multi-Agent Architecture

### Agent Hierarchy

```
root_agent (Orchestrator)
├── content_grounding_agent
│   └── Tools: slides_id_to_artifacts, create_markdown_artifact, etc.
├── voiceover_scene_agent
│   ├── Sub-agents: concept_video_agent, summary_video_agent
│   └── Pipeline: voiceover_pipeline_agent
├── audio_tags_agent
│   └── Pipeline: audio_tags_pipeline_agent
├── audio_generation_agent
│   ├── Tools: audio_generation_tool, fake_audio_generation
│   └── Pipeline: duration_pipeline_agent
└── html_generation_agent
    ├── Tools: generate_html_from_slide_pngs, generate_html_with_image_generation
    └── Pipeline: html_pipeline_agent
```

### Agent Responsibilities

#### Root Agent ([`json_video_agent/agent.py`](json_video_agent/agent.py))
- **Purpose**: Orchestrates the overall workflow and manages user interaction
- **Key Functions**:
  - `setup_state()`: Initializes state with required data structures
  - Routes user requests to appropriate sub-agents
  - Maintains conversational context
- **State Initialization**: Creates `scenes[]` and `grounding_artifacts[]` arrays

#### Content Grounding Agent ([`json_video_agent/content_grounding_agent/`](json_video_agent/content_grounding_agent/))
- **Purpose**: Imports and processes educational resources
- **Supported Inputs**:
  - Google Slides (via Slides API)
  - Google Docs (via export API)
  - Code.org curriculum markdown (via GitHub)
- **Output**: Artifacts (PDFs, markdown) + references in `state.grounding_artifacts`
- **Key Pattern**: Separates metadata (in state) from binary data (in artifacts)

#### Voiceover Scene Agent ([`json_video_agent/voiceover_scene_agent/`](json_video_agent/voiceover_scene_agent/))
- **Purpose**: Generates voiceover narration scripts
- **Modes**:
  1. **Preset - Concept Video**: Slide-by-slide detailed narration
  2. **Preset - Summary Video**: Condensed review of key concepts
  3. **Co-create**: Interactive scene generation with user
- **Output**: Updates `state.scenes` with `comment` and `speech` properties
- **Key Pattern**: Uses both full scene generation (presets) and update-based generation (co-create)

#### Audio Tags Agent ([`json_video_agent/audio_tags_agent/`](json_video_agent/audio_tags_agent/))
- **Purpose**: Enhances voiceover with ElevenLabs audio tags
- **Input**: Reads `state.scenes[].speech`
- **Output**: Adds `state.scenes[].elevenlabs` property
- **Key Feature**: Uses sequential pipeline for deterministic state updates

#### Audio Generation Agent ([`json_video_agent/audio_generation_agent/`](json_video_agent/audio_generation_agent/))
- **Purpose**: Synthesizes speech and calculates scene timings
- **Input**: Reads `state.scenes[].elevenlabs`
- **Output**: 
  - MP3 artifact (stored separately)
  - Artifact reference in `state.voiceover_audio_artifact`
  - Duration updates in `state.scenes[].duration`
- **Key Pattern**: Separates audio bytes (artifact) from timing metadata (state)

#### HTML Generation Agent ([`json_video_agent/html_generation_agent/`](json_video_agent/html_generation_agent/))
- **Purpose**: Creates visual slides for each scene
- **Modes**:
  1. **From Slides**: Reuses original slide PNGs
  2. **AI Generation**: Creates images via Gemini
  3. **Co-create**: Custom HTML generation
- **Output**: 
  - Adds `state.scenes[].html` property
  - Final export JSON artifact (includes audio as data URI)

## State Management

### Unified State Structure

The ADK maintains a persistent state object that all agents can read/write:

```python
state = {
    # Primary data structure (progressively enriched by each agent)
    "scenes": [
        {
            "comment": str,        # Added by: voiceover_scene_agent
            "speech": str,         # Added by: voiceover_scene_agent
            "elevenlabs": str,     # Added by: audio_tags_agent
            "duration": str,       # Added by: audio_generation_agent
            "html": str            # Added by: html_generation_agent
        }
    ],
    
    # Content references (from content_grounding_agent)
    "grounding_artifacts": [
        {
            "type": "pdf",
            "key": "artifact_filename.pdf",
            "version": "v1",
            "mime_type": "application/pdf"
        }
    ],
    
    # Special references
    "slide_artifact_reference": {  # From content_grounding_agent
        "presentation_id": str,
        "artifact_key_json": str,
        "artifact_version_json": str,
        "artifact_key_pdf": str,
        "artifact_version_pdf": str
    },
    
    "voiceover_audio_artifact": {  # From audio_generation_agent
        "type": "mp3",
        "artifact_key": str,
        "artifact_version": str,
        "voice_name": str,
        "mime_type": "audio/mpeg"
    },
    
    "final_json_reference": {      # From html_generation_agent
        "artifact_key": str,
        "artifact_version": str
    },
    
    # Intermediate update structures (used by sequential pipelines)
    "voiceover_updates": {"updates": [...]},  # Temporary
    "audio_tag_updates": {"updates": [...]},  # Temporary
    "html_updates": {"updates": [...]},       # Temporary
    "duration_updates": {"updates": [...]}    # Temporary
}
```

### State Access Patterns

**Reading State:**
```python
def my_tool(tool_context: ToolContext) -> Dict[str, Any]:
    scenes = tool_context.state.get("scenes", [])
    # ... use scenes
```

**Writing State:**
```python
# Direct assignment (for simple values)
tool_context.state["key"] = value

# Copy-modify-write (for complex objects)
scenes = copy.deepcopy(tool_context.state.get("scenes", []))
scenes[0]["new_field"] = "value"
tool_context.state["scenes"] = scenes
```

**Important**: Always use `copy.deepcopy()` when modifying nested structures to avoid mutation issues.

## Data Flow

### End-to-End Pipeline

```
1. Content Grounding
   Input:  User provides Google Slides URL
   Tool:   slides_id_to_artifacts()
   Output: state.grounding_artifacts += [pdf_ref]
           state.slide_artifact_reference = {...}

2. Voiceover Generation
   Input:  state.grounding_artifacts
   Agent:  concept_video_agent_from_slides
   Output: state.scenes = [{comment, speech}, ...]

3. Audio Tag Enhancement
   Input:  state.scenes[].speech
   Agent:  audio_tags_pipeline_agent
   Output: state.scenes[].elevenlabs (added)

4. Audio Synthesis
   Input:  state.scenes[].elevenlabs
   Tool:   audio_generation_tool()
   Output: MP3 artifact + state.voiceover_audio_artifact
           state.scenes[].duration (added)

5. HTML Generation
   Input:  state.scenes, state.slide_artifact_reference
   Tool:   generate_html_from_slide_pngs()
   Output: state.scenes[].html (added)
           Final JSON artifact

6. Export
   Output: JSON file with all scene data + audio data URI
```

### Data Dependencies

```
grounding_artifacts
    ↓
scenes (created by voiceover_scene_agent)
    ↓
scenes.elevenlabs (added by audio_tags_agent)
    ↓
scenes.duration + audio artifact (added by audio_generation_agent)
    ↓
scenes.html (added by html_generation_agent)
    ↓
final_json_reference (complete export)
```

## Agent Communication Patterns

### Pattern 1: Parent-to-Child Delegation

The root agent delegates to sub-agents using ADK's built-in transfer mechanism:

```python
# In root_agent configuration
sub_agents=[content_grounding_agent, voiceover_scene_agent, ...]

# ADK handles transfer automatically when agent decides to delegate
# User message determines which sub-agent to activate
```

### Pattern 2: Sequential Pipeline

Multi-step operations use `SequentialAgent` for deterministic execution:

```python
# Define individual agents
agent1 = Agent(name="generate", output_key="updates", ...)
agent2 = Agent(name="apply", tools=[apply_updates], ...)

# Chain them sequentially
pipeline = SequentialAgent(
    name="pipeline",
    sub_agents=[agent1, agent2]
)
```

**Execution Flow:**
1. Agent1 generates updates → writes to `state.updates`
2. Agent2 reads `state.updates` → applies to `state.scenes`
3. Both complete before returning to parent

### Pattern 3: Tool-as-Agent

For preset workflows, agents can be wrapped as tools:

```python
from google.adk.tools.agent_tool import AgentTool

preset_agent = Agent(...)
tool = AgentTool(agent=preset_agent)

# Now can be used in tools list
parent_agent = Agent(tools=[tool])
```

## Tool Function Patterns

### Pattern 1: ADK Tool (with ToolContext)

All tools that interact with state/artifacts follow this pattern:

```python
async def tool_name(param: str, tool_context: ToolContext) -> Dict[str, Any]:
    """Tool description.
    
    Args:
        param: Parameter description
        tool_context: ADK ToolContext for state/artifact management
        
    Returns:
        Dictionary containing:
            - status (str): "success" or "error"
            - message (str): Descriptive message
            - [additional fields on success]
    """
    # Validation
    if not param:
        return {"status": "error", "message": "Parameter required"}
    
    try:
        # Read from state
        data = tool_context.state.get("key", default)
        
        # Process data
        result = process(param, data)
        
        # Update state
        tool_context.state["output_key"] = result
        
        # Success response
        return {
            "status": "success",
            "message": "Operation completed",
            "result_key": result
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
```

### Pattern 2: Helper Function

Helper functions that don't need state access raise exceptions:

```python
def helper_function(param: str) -> List[str]:
    """Helper description.
    
    Args:
        param: Parameter description
        
    Returns:
        Processed results
        
    Raises:
        ValueError: When param is invalid
    """
    if not param:
        raise ValueError("Parameter required")
    
    return process(param)
```

### Pattern 3: Artifact Management

**Saving Artifacts:**
```python
# Create Part from bytes
part = make_part("application/json", json_bytes)

# Save to artifact store
version = await tool_context.save_artifact(
    filename="data.json",
    artifact=part
)

# Store reference in state (not the bytes!)
tool_context.state["data_ref"] = {
    "key": "data.json",
    "version": version
}
```

**Loading Artifacts:**
```python
# Get reference from state
ref = tool_context.state["data_ref"]

# Load artifact
part = await tool_context.load_artifact(
    filename=ref["key"],
    version=ref["version"]
)

# Extract bytes
bytes_data = part.inline_data.data
```

## Sequential Pipeline Pattern

### Why Sequential Pipelines?

The update-based pattern solves a key problem: **concurrent state modifications**.

**Problem Without Pipeline:**
```python
# Agent A and Agent B might both try to modify state.scenes
# Results are unpredictable and can cause data loss
```

**Solution With Pipeline:**
```python
# Step 1: Generate updates (no state mutation)
generate_agent → output_key="updates"

# Step 2: Apply updates (single writer)
apply_agent → reads "updates", modifies "scenes"
```

### Implementation Example

**Step 1: Define Update Schema**
```python
from pydantic import BaseModel

class SceneUpdate(BaseModel):
    index: int  # Which scene to update
    field: str  # The new value
```

**Step 2: Create Generate Agent**
```python
generate_agent = Agent(
    name="generate_updates",
    instruction="Generate updates for scenes...",
    output_schema=UpdateList,  # Pydantic model
    output_key="updates"       # Where to write in state
)
```

**Step 3: Create Apply Agent**
```python
def apply_updates(tool_context: ToolContext) -> Dict[str, Any]:
    scenes = copy.deepcopy(tool_context.state["scenes"])
    updates = tool_context.state["updates"]["updates"]
    
    for update in updates:
        scenes[update["index"]][field] = update["value"]
    
    tool_context.state["scenes"] = scenes
    return {"status": "success"}

apply_agent = Agent(
    name="apply_updates",
    tools=[apply_updates],
    instruction="Apply updates to scenes"
)
```

**Step 4: Chain with SequentialAgent**
```python
pipeline = SequentialAgent(
    name="update_pipeline",
    sub_agents=[generate_agent, apply_agent]
)
```

### Current Pipelines

1. **Voiceover Pipeline** - Generates and applies `comment` and `speech`
2. **Audio Tags Pipeline** - Generates and applies `elevenlabs`
3. **HTML Pipeline** - Generates and applies `html`
4. **Duration Pipeline** - Applies `duration` from audio generation

## Error Handling Conventions

### Tool Functions (Return Dict)

```python
async def tool(param: str, tool_context: ToolContext) -> Dict[str, Any]:
    # Always return dict with status
    if error_condition:
        return {
            "status": "error",
            "message": "Clear error description"
        }
    
    return {
        "status": "success",
        "message": "Success description",
        "data": result
    }
```

### Helper Functions (Raise Exceptions)

```python
def helper(param: str) -> str:
    # Raise specific exceptions
    if not param:
        raise ValueError("Parameter cannot be empty")
    
    try:
        result = external_api_call(param)
    except RequestException as e:
        raise RequestError(f"API failed: {e}")
    
    return result
```

### Convention Summary

| Function Type | Error Pattern | Rationale |
|---------------|---------------|-----------|
| Tool (with ToolContext) | Return `{"status": "error"}` | ADK can display to user |
| Helper/Utility | Raise exceptions | Clear error propagation |
| Validation | Raise exceptions | Fail fast |

## Artifact Management

### What Goes in Artifacts vs. State

**Artifacts (Large Binary Data):**
- PDFs (slide exports, docs)
- Audio files (MP3 voiceovers)
- Images (PNG slide thumbnails - embedded in JSON)
- Final export JSON

**State (Metadata & References):**
- Artifact filenames and versions
- Scene data (text, HTML strings)
- Configuration values
- Intermediate update structures

### Artifact Lifecycle

```python
# 1. Create
bytes_data = generate_content()
part = make_part(mime_type, bytes_data)

# 2. Save
version = await tool_context.save_artifact(
    filename="output.pdf",
    artifact=part
)

# 3. Reference in State
tool_context.state["reference"] = {
    "key": "output.pdf",
    "version": version,
    "mime_type": mime_type
}

# 4. Load (later)
ref = tool_context.state["reference"]
part = await tool_context.load_artifact(
    filename=ref["key"],
    version=ref["version"]
)

# 5. Use
raw_bytes = part.inline_data.data
```

### Artifact Naming Conventions

- **Content PDFs**: `slides_{presentation_id}.pdf`, `google_doc_{doc_id}.pdf`
- **Content JSON**: `slides_{presentation_id}_data.json`
- **Audio**: `voiceover_{voice_name}.mp3`
- **Final Export**: `final_video_export.json`

## Integration Points

### Google Slides API
- **Authentication**: Service account credentials (base64-encoded env var)
- **Scopes**: `presentations.readonly`, `drive.readonly`
- **Data Retrieved**: Slide notes, thumbnails (PNG)
- **Tool**: [`get_slides_data()`](json_video_agent/content_grounding_agent/content_grounding_tools.py:77)

### Google Docs API
- **Authentication**: Public export URL (no auth needed if doc is public)
- **Export Format**: PDF via `/export?format=pdf`
- **Tool**: [`fetch_doc_as_pdf()`](json_video_agent/content_grounding_agent/content_grounding_tools.py:336)

### ElevenLabs API
- **Authentication**: API key in header
- **Model**: `eleven_v3` (supports audio tags and alignment)
- **Features Used**:
  - `convert_with_timestamps()` - Character-level alignment
  - Audio tags - `[thoughtful]`, `[excited]`, etc.
- **Tool**: [`elevenlabs_generation()`](json_video_agent/audio_generation_agent/elevenlabs_tools.py:170)

### Gemini (Google AI)
- **Models Used**:
  - `gemini-2.5-flash` - Agent LLM (all agents)
  - `gemini-2.5-flash-image` - Image generation
- **Authentication**: API key
- **Tool**: [`generate_image_for_scene()`](json_video_agent/html_generation_agent/image_gen.py:38)

## Performance Considerations

### Caching
- ElevenLabs client cached with `@lru_cache`
- Google API services built once per request

### Rate Limiting
- ElevenLabs: Respect API rate limits
- Google Slides: Batch requests where possible

### Memory Management
- Large artifacts NOT stored in state
- Use streaming for large file downloads
- `copy.deepcopy()` only when necessary

## Testing Strategies

### Unit Testing Tools
```python
# Mock ToolContext for testing
from unittest.mock import MagicMock

tool_context = MagicMock()
tool_context.state = {"scenes": [...]}

result = await my_tool("param", tool_context)
assert result["status"] == "success"
```

### Integration Testing
- Use `fake_audio_generation` tool to avoid API costs
- Test with small slide decks
- Validate state transitions

### End-to-End Testing
```python
# 1. Ground content
# 2. Generate voiceover
# 3. Add audio tags
# 4. Generate audio (fake)
# 5. Generate HTML
# 6. Validate final JSON structure
```

## Debugging Tips

### State Inspection
Use `list_current_state` tool to view entire state at any point.

### Artifact Inspection
Use `list_saved_artifacts` tool to see all artifacts created in session.

### Logging
All agents use Python `logging` module:
```python
import logging
logging.info("✅ Operation successful")
logging.error("❌ Operation failed")
```

### Common Issues

**Issue**: Scenes have wrong number of elements
- **Cause**: Mismatch between slides and voiceover count
- **Fix**: Ensure one scene per slide in concept video mode

**Issue**: Audio duration shows "error"
- **Cause**: Alignment data mismatch
- **Fix**: Check `EXPECT_CONTROL_ALIGNMENT_DATA` setting

**Issue**: HTML doesn't display
- **Cause**: Invalid HTML string in scenes
- **Fix**: Validate HTML structure before saving

## Future Enhancements

Potential areas for expansion:

1. **Additional Content Sources**: YouTube transcripts, web pages
2. **More Voice Options**: Additional ElevenLabs voices, voice cloning
3. **Advanced HTML**: Interactive elements, animations
4. **Video Export**: Direct MP4 rendering (not just JSON)
5. **Batch Processing**: Multiple videos in one session
6. **Template Library**: Reusable scene templates
