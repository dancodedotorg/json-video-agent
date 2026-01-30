# Final Documentation Improvement Plan for json-video-agent

## Executive Summary

This plan outlines comprehensive documentation improvements for the multi-agent video creation system. Focus is exclusively on documentation updates—no code refactoring or optimization.

## Documentation Standards (User-Approved)

### 1. Docstring Format: Google-Style (Args/Returns Only)

```python
def function_name(param1: str, param2: int) -> Dict[str, Any]:
    """Brief one-line description.
    
    Longer description if needed, explaining the function's purpose,
    behavior, and any important implementation details.
    
    Args:
        param1: Description of first parameter
        param2: Description of second parameter
        
    Returns:
        Dictionary containing:
            - status (str): "success" or "error"
            - message (str): Descriptive message
            - data (Any): Additional data on success
    """
```

**Note**: No Examples section needed. If exceptions are raised, add a Raises section.

### 2. Type Annotations: Practical Approach

- Use `Dict[str, Any]` for ADK state/tool patterns (flexibility needed)
- Specific types where clear (str, int, bool, List[str], etc.)
- `Optional[T]` for nullable parameters
- Avoid overly complex nested type definitions
- `Any` is acceptable for truly dynamic values

### 3. README Structure

- **Root README.md**: High-level overview only
  - Project purpose
  - Quick start
  - Agent hierarchy diagram
  - Basic usage
  - Environment setup
  
- **ARCHITECTURE.md**: Detailed technical walkthrough (NEW)
  - State management details
  - Data flow between agents
  - Sequential pipeline patterns
  - Tool function patterns
  - Error handling conventions

### 4. Deployment Notes

- Ignore `deploy_notes/` directory (internal notes)

## File-by-File Documentation Plan

### Documentation Files to Create

1. **`README.md`** (root) - High-level project overview
2. **`ARCHITECTURE.md`** (root) - Detailed technical documentation
3. **`docs/STYLE_GUIDE.md`** - Documentation standards for contributors

### Core Package Files

#### `json_video_agent/__init__.py`
- [ ] Add package docstring explaining the multi-agent system architecture
- [ ] Document exported symbols (`root_agent`)

#### `json_video_agent/agent.py`
- [ ] Add module docstring explaining root agent orchestration
- [ ] Document `setup_state()` function
  - Add type hints: `(callback_context: CallbackContext) -> None`
  - Add docstring with Args section
- [ ] Add inline comments for DESCRIPTION and INSTRUCTION constants

### Shared Utilities

#### `json_video_agent/shared/__init__.py`
- [ ] Add package docstring

#### `json_video_agent/shared/constants.py`
- [ ] Add module docstring
- [ ] Document constants with inline comments:
  ```python
  # Model configuration for all agents (Flash variant for speed/cost balance)
  GEMINI_MODEL = "gemini-2.5-flash"
  
  # Google API key from environment (required for Gemini and image generation)
  GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
  
  # Shared Gemini client instance (reused across agent tools)
  GEMINI_CLIENT = genai.Client(api_key=GOOGLE_API_KEY)
  ```

#### `json_video_agent/shared/tools.py`
- [ ] Add module docstring
- [ ] `list_saved_artifacts()` - Add Args/Returns, type: `async def list_saved_artifacts(tool_context: ToolContext) -> Dict[str, Any]:`
- [ ] `list_current_state()` - Add Args/Returns, type: `def list_current_state(tool_context: ToolContext) -> Dict[str, Any]:`
- [ ] `list_grounding_artifacts()` - Add Args/Returns, type: `def list_grounding_artifacts(tool_context: ToolContext) -> Dict[str, Any]:`
- [ ] `make_part()` - Add Args/Returns, type: `def make_part(type: str, content: bytes) -> Part:`
- [ ] `_maybe_extract_json()` - Enhance docstring, type: `def _maybe_extract_json(text: str) -> str:`
- [ ] `_part_to_candidate_json()` - Add Args/Returns, type: `def _part_to_candidate_json(part: Part) -> tuple[str | None, str | None]:`

### Content Grounding Agent

#### `json_video_agent/content_grounding_agent/__init__.py`
- [ ] Add package docstring

#### `json_video_agent/content_grounding_agent/agent.py`
- [ ] Add module docstring
- [ ] `slides_id_to_artifacts()` - Add return type: `async def slides_id_to_artifacts(presentation_id: str, tool_context: ToolContext) -> Dict[str, Any]:`
- [ ] `create_markdown_artifact()` - Add return type: `async def create_markdown_artifact(name: str, tool_context: ToolContext) -> Dict[str, Any]:`
- [ ] `save_google_doc_as_pdf_artifact()` - Add return type: `async def save_google_doc_as_pdf_artifact(doc_id: str, tool_context: ToolContext) -> Dict[str, Any]:`
- [ ] `add_to_grounding_artifacts()` - Add full docstring and type: `def add_to_grounding_artifacts(ref: Dict[str, Any], tool_context: ToolContext) -> None:`

#### `json_video_agent/content_grounding_agent/content_grounding_tools.py`
- [ ] Add module docstring explaining Google API integration
- [ ] `get_service_account_creds_from_env()` - Add type hints for all parameters and return
- [ ] `_build_slides_service()` - Add docstring with Args/Returns
- [ ] `_build_authed_session()` - Add docstring with Args/Returns
- [ ] `get_slides_data()` - Add type: `def get_slides_data(presentation_id: str) -> List[Dict[str, Any]]:`
- [ ] `render_pdf_bytes_from_slides()` - Add docstring and type
- [ ] `_get_slide_list()` - Add docstring and type
- [ ] `get_all_speaker_notes()` - Add type hints
- [ ] `get_all_speaker_notes_by_slide_id()` - Add type hints
- [ ] `get_all_pngs_from_presentation()` - Add type hints
- [ ] `get_all_pngs_by_slide_id()` - Add type hints
- [ ] `slides_to_pdf()` - Add docstring and type: `def slides_to_pdf(slides: List[Dict[str, Any]]) -> str:`
- [ ] `extract_slides_id()` - Already has docstring, add type hints
- [ ] `extract_doc_id()` - Add type hints
- [ ] `fetch_markdown_level()` - Add type hints, document None return in docstring
- [ ] `fetch_doc_as_pdf()` - Add type hints
- [ ] Document SLIDES_SCOPES constant

### Voiceover Scene Agent

#### `json_video_agent/voiceover_scene_agent/__init__.py`
- [ ] Add package docstring

#### `json_video_agent/voiceover_scene_agent/agent.py`
- [ ] Add module docstring explaining scene generation and sequential patterns
- [ ] Document Pydantic models (VoiceoverUpdate, VoiceoverUpdateList, Scene, SceneList) with class docstrings
- [ ] `apply_voiceover_updates()` - Add type: `def apply_voiceover_updates(tool_context: ToolContext) -> Dict[str, Any]:`
- [ ] `_convert_scenes_to_updates()` - Add docstring and type: `def _convert_scenes_to_updates(callback_context: CallbackContext) -> None:`
- [ ] Document VOICEOVER_SYSTEM_INSTRUCTION and CONCEPT_VIDEO_INSTRUCTIONS as constants

### Audio Tags Agent

#### `json_video_agent/audio_tags_agent/__init__.py`
- [ ] Add package docstring

#### `json_video_agent/audio_tags_agent/agent.py`
- [ ] Add module docstring
- [ ] Document Pydantic models (AudioTagUpdate, AudioTagUpdateList)
- [ ] `apply_audio_tag_updates()` - Add type: `def apply_audio_tag_updates(tool_context: ToolContext) -> Dict[str, Any]:`

#### `json_video_agent/audio_tags_agent/audio_tag_prompt.py`
- [ ] Add module docstring explaining prompt engineering for audio tags
- [ ] Add comments for exported constants (AUDIO_TAGS_DESCRIPTION, AUDIO_TAG_GENERATION_INSTRUCTIONS, AUDIO_TAGS_PROMPT)

### Audio Generation Agent

#### `json_video_agent/audio_generation_agent/__init__.py`
- [ ] Add package docstring

#### `json_video_agent/audio_generation_agent/agent.py`
- [ ] Add module docstring
- [ ] Document Pydantic models (DurationUpdate, DurationUpdateList)
- [ ] `apply_duration_updates()` - Add type: `def apply_duration_updates(tool_context: ToolContext) -> Dict[str, Any]:`
- [ ] `get_available_voices()` - Add docstring and type: `def get_available_voices() -> List[str]:`
- [ ] `fake_audio_generation()` - Enhance docstring, add type: `async def fake_audio_generation(tool_context: ToolContext) -> Dict[str, Any]:`
- [ ] `audio_generation_tool()` - Enhance docstring, add type: `async def audio_generation_tool(voice_name: str, tool_context: ToolContext) -> Dict[str, Any]:`

#### `json_video_agent/audio_generation_agent/elevenlabs_tools.py`
- [ ] Add module docstring explaining ElevenLabs integration and alignment calculation
- [ ] Document constants section with inline comments:
  ```python
  # ElevenLabs model configuration
  MODEL = "eleven_v3"  # V3 model supports audio tags and alignment data
  OUTPUT_FORMAT = "mp3_44100_128"  # Standard quality MP3
  
  # Voice ID mappings (ElevenLabs voice identifiers)
  SAM_VOICE_ID = "utHJATTigr4CyfAK1MPl"
  DAN_VOICE_ID = "VtuhZ4p3OdnFWQ5O4O7Y"
  ADAM_VOICE_ID = "s3TPKV1kjDlVtZbl4Ksh"
  HOPE_VOICE_ID = "tnSpp4vdxKPjI9w0GnoV"
  
  # Scene separator for concatenated voiceover (used in alignment calculation)
  SCENE_SEPARATOR = " [pause] "
  
  # Controls alignment parsing behavior for V3 models (silence, not characters)
  EXPECT_CONTROL_ALIGNMENT_DATA = False
  ```
- [ ] `get_elevenlabs_client()` - Add type hints
- [ ] `get_alignment()` - Add docstring with type: `def get_alignment(data: Dict[str, Any]) -> Dict[str, Any]:`
- [ ] `calculate_durations_by_char_count()` - Add comprehensive docstring and type
- [ ] `generate_audio()` - Enhance docstring and add type hints
- [ ] `elevenlabs_generation()` - Enhance docstring and add type hints

### HTML Generation Agent

#### `json_video_agent/html_generation_agent/__init__.py`
- [ ] Add package docstring

#### `json_video_agent/html_generation_agent/agent.py`
- [ ] Module docstring exists and is excellent ✓
- [ ] Document Pydantic models (HtmlUpdate, HtmlUpdateList)
- [ ] `generate_final_export_obj()` - Add type: `async def generate_final_export_obj(scenes_parent_obj: Dict[str, List[Any]], tool_context: ToolContext) -> Dict[str, Any]:`
- [ ] `generate_html_with_image_generation()` - Add type: `async def generate_html_with_image_generation(tool_context: ToolContext) -> Dict[str, Any]:`
- [ ] `generate_html_from_slide_pngs()` - Add type: `async def generate_html_from_slide_pngs(tool_context: ToolContext) -> Dict[str, Any]:`
- [ ] `apply_html_updates()` - Add docstring and type: `def apply_html_updates(tool_context: ToolContext) -> Dict[str, Any]:`

#### `json_video_agent/html_generation_agent/image_gen.py`
- [ ] Add module docstring explaining Gemini image generation integration
- [ ] Document constants with comments
- [ ] `generate_image_for_scene()` - Add docstring with type: `def generate_image_for_scene(client: genai.Client, comment: str, speech: str) -> str | None:`
  - Add Raises section documenting exception handling

## Error Handling Documentation Patterns

### Pattern 1: ADK Tool Functions (with ToolContext)
Always return `Dict[str, Any]` with status indicator.

```python
async def tool_function(param: str, tool_context: ToolContext) -> Dict[str, Any]:
    """Tool description.
    
    Args:
        param: Parameter description
        tool_context: ADK ToolContext for state/artifact management
        
    Returns:
        Dictionary containing:
            - status (str): "success" or "error"
            - message (str): Descriptive message about the operation
            - [additional keys on success]
    """
```

### Pattern 2: Helper Functions
Raise exceptions on errors, document in Raises section.

```python
def helper_function(param: str) -> List[str]:
    """Helper description.
    
    Args:
        param: Parameter description
        
    Returns:
        List of results
        
    Raises:
        ValueError: When param is invalid
        RequestError: When external API fails
    """
```

### Pattern 3: Functions Returning Optional Values
Document None behavior in Returns section.

```python
async def fetch_data(identifier: str) -> str | None:
    """Fetch data description.
    
    Args:
        identifier: Data identifier
        
    Returns:
        Data string if found, None if not found or on error
    """
```

## Implementation Phases

### Phase 1: Foundation Documents
- [ ] Create `README.md` (high-level overview)
- [ ] Create `ARCHITECTURE.md` (detailed technical walkthrough)
- [ ] Add package docstrings to all `__init__.py` files (7 files)
- [ ] Add module docstrings to all `.py` files (12 files)

### Phase 2: Function Documentation - Core Tools
- [ ] Shared tools (`shared/tools.py`)
- [ ] Content grounding tools (agent.py + content_grounding_tools.py)
- [ ] Audio generation tools (agent.py + elevenlabs_tools.py)
- [ ] HTML generation tools (agent.py + image_gen.py)

### Phase 3: Function Documentation - Agents
- [ ] Root agent (`agent.py`)
- [ ] Voiceover scene agent
- [ ] Audio tags agent
- [ ] All apply/update functions

### Phase 4: Type Annotations
- [ ] High-priority: All tool functions with ToolContext
- [ ] Medium-priority: All helper/utility functions
- [ ] Lower-priority: Callback and internal functions

### Phase 5: Constants and Configuration
- [ ] Document all constants with inline comments
- [ ] Document Pydantic model classes
- [ ] Document agent instruction prompts

### Phase 6: Style Guide and Final Review
- [ ] Create `docs/STYLE_GUIDE.md`
- [ ] Consistency review across all files
- [ ] Verify all checklist items complete

## Metrics for Success

- [ ] 100% of `.py` files have module docstrings
- [ ] 100% of `__init__.py` files have package docstrings
- [ ] 100% of public tool functions have complete docstrings (Args/Returns)
- [ ] 90%+ of functions have type annotations
- [ ] Error handling patterns documented consistently
- [ ] Root README.md provides clear onboarding path
- [ ] ARCHITECTURE.md explains technical details
- [ ] All constants documented with inline comments

## Documentation Templates

### Module Docstring Template
```python
"""Module description.

This module provides [functionality description]. It includes:
- Key component 1
- Key component 2
- Integration with [external system]

The module is part of the [agent_name] agent in the json-video-agent system.
"""
```

### Package Docstring Template (\_\_init\_\_.py)
```python
"""Package description.

This package contains the [agent_name] agent which [primary responsibility].

Key components:
- agent.py: Main agent definition and tool functions
- [other_file.py]: Helper utilities for [purpose]

Usage:
    from json_video_agent.[package_name] import [agent_name]
"""
```

### Tool Function Template
```python
async def tool_name(param: str, tool_context: ToolContext) -> Dict[str, Any]:
    """Brief description of what this tool does.
    
    Longer explanation of the tool's purpose, behavior, and any important
    implementation details. Explain how it integrates with agent state.
    
    Args:
        param: Description of the parameter including expected format
        tool_context: ADK ToolContext for state/artifact management
        
    Returns:
        Dictionary containing:
            - status (str): "success" or "error"
            - message (str): Descriptive message
            - [specific_key] (type): Description of success data
    """
```

## Example Before/After

### Before
```python
def get_slides_data(presentation_id):
    """
    Orchestrates fetching speaker notes + thumbnails, returning a single list
    of slide dicts.
    """
    creds = get_service_account_creds_from_env()
    slides = _get_slide_list(presentation_id, creds)
    # ...
```

### After
```python
def get_slides_data(presentation_id: str) -> List[Dict[str, Any]]:
    """Fetch slide data including speaker notes and thumbnails from Google Slides.
    
    Orchestrates the retrieval of presentation data by combining slide metadata,
    speaker notes, and PNG thumbnails into a unified data structure.
    
    Args:
        presentation_id: Google Slides presentation ID (the ID portion from the URL,
            e.g., "1a2b3c4d5e")
            
    Returns:
        List of slide dictionaries, where each dict contains:
            - index (int): Zero-based slide index
            - slide_id (str): Google Slides object ID
            - notes (str): Speaker notes text content
            - png_base64 (str | None): Base64-encoded PNG data URI or None if unavailable
    """
    creds = get_service_account_creds_from_env()
    slides = _get_slide_list(presentation_id, creds)
    # ...
```

## Next Steps

Once this plan is approved, switch to Code mode to implement these documentation improvements systematically, following the phase order outlined above.
