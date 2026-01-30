# Documentation Improvement Plan for json-video-agent

## Executive Summary

This plan outlines comprehensive documentation improvements for the multi-agent system. The focus is exclusively on documentation updates—no code refactoring or optimization.

## Current State Analysis

### Strengths
- Some functions have good docstrings (e.g., [`slides_id_to_artifacts`](json_video_agent/content_grounding_agent/agent.py:17))
- Consistent use of dict returns with status indicators in tool functions
- Clear agent instruction prompts provide good context

### Gaps Identified

1. **No root README.md** - New users have no entry point to understand the system
2. **No package docstrings** - All `__init__.py` files lack module-level documentation
3. **Inconsistent function docstrings** - Many functions lack proper documentation
4. **Missing type annotations** - Approximately 60% of functions lack complete type hints
5. **Mixed error handling** - Some functions return error dicts, others raise exceptions, creating inconsistency
6. **Undocumented constants** - Configuration values lack explanatory comments
7. **Module docstrings** - Only 1 of 12 modules has a module-level docstring

## Documentation Standards to Adopt

### Google-Style Docstrings

All functions should follow this format:

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
            
    Raises:
        ValueError: When param1 is empty
        RequestError: When external API fails
        
    Example:
        >>> result = function_name("test", 42)
        >>> print(result["status"])
        'success'
    """
```

### Type Annotations

- All function parameters must have type hints
- All return types must be annotated
- Use `typing` module for complex types: `Dict`, `List`, `Optional`, `Any`, `Union`
- For async functions, use `-> Awaitable[T]` or specific return type

### Error Handling Standardization

**Current inconsistency found:**
- Tool functions (with `ToolContext`) → Return `Dict[str, Any]` with status
- Helper functions → Mixed (some raise, some return None, some return error dicts)

**Recommended pattern:**
1. **Tool functions** (ADK tools with ToolContext): Always return `Dict[str, Any]` with `{"status": "success" | "error", ...}`
2. **Helper/utility functions**: Raise exceptions for errors, document in docstring
3. **Validation functions**: Return bool or raise exceptions

## Detailed Changes by File

### 1. Root Level

#### [`README.md`](README.md) - **CREATE NEW**

Sections to include:
- Project overview and purpose
- Architecture diagram (Mermaid)
- Quick start guide
- Agent hierarchy and responsibilities
- State management explanation
- Environment setup (.env requirements)
- Deployment notes (reference deploy_notes/)
- Contributing guidelines
- License information

### 2. Main Package: [`json_video_agent/`](json_video_agent/)

#### [`__init__.py`](json_video_agent/__init__.py:1)
- Add package-level docstring explaining the multi-agent system
- Document exported symbols

#### [`agent.py`](json_video_agent/agent.py:1)
- Add module docstring explaining root agent orchestration
- Document [`setup_state`](json_video_agent/agent.py:59) function with types
- Add type hints to callback parameter
- Document DESCRIPTION, INSTRUCTION constants

### 3. Shared Package: [`json_video_agent/shared/`](json_video_agent/shared/)

#### [`__init__.py`](json_video_agent/shared/__init__.py:1)
- Add package docstring for shared utilities

#### [`constants.py`](json_video_agent/shared/constants.py:1)
- Add module docstring
- Document each constant:
  - `GEMINI_MODEL` - explain model choice
  - `GOOGLE_API_KEY` - usage notes
  - `GEMINI_CLIENT` - explain global client pattern

#### [`tools.py`](json_video_agent/shared/tools.py:1)
- Add module docstring
- Add complete docstrings for:
  - [`list_saved_artifacts`](json_video_agent/shared/tools.py:6) - add Args, Returns sections
  - [`list_current_state`](json_video_agent/shared/tools.py:14) - add Args, Returns sections
  - [`list_grounding_artifacts`](json_video_agent/shared/tools.py:23) - add Args, Returns sections
  - [`make_part`](json_video_agent/shared/tools.py:32) - improve docstring, add type hints
  - [`_maybe_extract_json`](json_video_agent/shared/tools.py:43) - enhance docstring with examples
  - [`_part_to_candidate_json`](json_video_agent/shared/tools.py:62) - clarify return tuple meaning
- Add type annotations to all parameters and returns

### 4. Content Grounding Agent: [`json_video_agent/content_grounding_agent/`](json_video_agent/content_grounding_agent/)

#### [`__init__.py`](json_video_agent/content_grounding_agent/__init__.py:1)
- Add package docstring explaining content grounding functionality

#### [`agent.py`](json_video_agent/content_grounding_agent/agent.py:1)
- Add module docstring
- Existing docstrings are good but need type annotations:
  - [`slides_id_to_artifacts`](json_video_agent/content_grounding_agent/agent.py:17) - add return type
  - [`create_markdown_artifact`](json_video_agent/content_grounding_agent/agent.py:87) - add return type
  - [`save_google_doc_as_pdf_artifact`](json_video_agent/content_grounding_agent/agent.py:128) - add return type
  - [`add_to_grounding_artifacts`](json_video_agent/content_grounding_agent/agent.py:182) - add full docstring and return type

#### [`content_grounding_tools.py`](json_video_agent/content_grounding_agent/content_grounding_tools.py:1)
- Add module docstring explaining Google API integration
- Add/improve docstrings for:
  - [`get_service_account_creds_from_env`](json_video_agent/content_grounding_agent/content_grounding_tools.py:31) - good docstring, add type hints
  - [`_build_slides_service`](json_video_agent/content_grounding_agent/content_grounding_tools.py:55) - add docstring with type hints
  - [`_build_authed_session`](json_video_agent/content_grounding_agent/content_grounding_tools.py:64) - enhance docstring
  - [`get_slides_data`](json_video_agent/content_grounding_agent/content_grounding_tools.py:77) - add proper docstring with Args/Returns
  - [`render_pdf_bytes_from_slides`](json_video_agent/content_grounding_agent/content_grounding_tools.py:101) - add proper docstring
  - All remaining functions need docstrings
- Add type hints to all functions
- Document SLIDES_SCOPES constant

### 5. Voiceover Scene Agent: [`json_video_agent/voiceover_scene_agent/`](json_video_agent/voiceover_scene_agent/)

#### [`__init__.py`](json_video_agent/voiceover_scene_agent/__init__.py:1)
- Add package docstring

#### [`agent.py`](json_video_agent/voiceover_scene_agent/agent.py:1)
- Add module docstring explaining scene generation patterns
- Add docstrings for:
  - [`apply_voiceover_updates`](json_video_agent/voiceover_scene_agent/agent.py:125) - enhance existing docstring with types
  - [`_convert_scenes_to_updates`](json_video_agent/voiceover_scene_agent/agent.py:178) - add full docstring
- Add type hints to callback parameters
- Document Pydantic models (VoiceoverUpdate, VoiceoverUpdateList, Scene, SceneList)

### 6. Audio Tags Agent: [`json_video_agent/audio_tags_agent/`](json_video_agent/audio_tags_agent/)

#### [`__init__.py`](json_video_agent/audio_tags_agent/__init__.py:1)
- Add package docstring

#### [`agent.py`](json_video_agent/audio_tags_agent/agent.py:1)
- Add module docstring
- Add docstring for [`apply_audio_tag_updates`](json_video_agent/audio_tags_agent/agent.py:34) with type hints
- Document Pydantic models

#### [`audio_tag_prompt.py`](json_video_agent/audio_tags_agent/audio_tag_prompt.py:1)
- Add module docstring explaining prompt engineering for audio tags
- Document the three exported constants

### 7. Audio Generation Agent: [`json_video_agent/audio_generation_agent/`](json_video_agent/audio_generation_agent/)

#### [`__init__.py`](json_video_agent/audio_generation_agent/__init__.py:1)
- Add package docstring

#### [`agent.py`](json_video_agent/audio_generation_agent/agent.py:1)
- Add module docstring
- Add docstrings with types for:
  - [`apply_duration_updates`](json_video_agent/audio_generation_agent/agent.py:35)
  - [`get_available_voices`](json_video_agent/audio_generation_agent/agent.py:104) - add proper docstring
  - [`fake_audio_generation`](json_video_agent/audio_generation_agent/agent.py:108) - enhance existing docstring
  - [`audio_generation_tool`](json_video_agent/audio_generation_agent/agent.py:149) - enhance existing docstring with complete Args/Returns

#### [`elevenlabs_tools.py`](json_video_agent/audio_generation_agent/elevenlabs_tools.py:1)
- Add module docstring explaining ElevenLabs integration
- Document constants section (MODEL, OUTPUT_FORMAT, voice IDs, etc.)
- Add docstrings for:
  - [`get_elevenlabs_client`](json_video_agent/audio_generation_agent/elevenlabs_tools.py:42) - enhance docstring
  - [`get_alignment`](json_video_agent/audio_generation_agent/elevenlabs_tools.py:52) - enhance with Args/Returns
  - [`calculate_durations_by_char_count`](json_video_agent/audio_generation_agent/elevenlabs_tools.py:61) - add comprehensive docstring
  - [`generate_audio`](json_video_agent/audio_generation_agent/elevenlabs_tools.py:142) - enhance existing docstring
  - [`elevenlabs_generation`](json_video_agent/audio_generation_agent/elevenlabs_tools.py:170) - enhance existing docstring
- Add type hints throughout

### 8. HTML Generation Agent: [`json_video_agent/html_generation_agent/`](json_video_agent/html_generation_agent/)

#### [`__init__.py`](json_video_agent/html_generation_agent/__init__.py:1)
- Add package docstring

#### [`agent.py`](json_video_agent/html_generation_agent/agent.py:1)
- Module docstring exists and is excellent! ✓
- Add complete docstrings with types for:
  - [`generate_final_export_obj`](json_video_agent/html_generation_agent/agent.py:91) - enhance existing docstring
  - [`generate_html_with_image_generation`](json_video_agent/html_generation_agent/agent.py:164) - enhance existing docstring
  - [`generate_html_from_slide_pngs`](json_video_agent/html_generation_agent/agent.py:212) - enhance existing docstring
  - [`apply_html_updates`](json_video_agent/html_generation_agent/agent.py:336) - add full docstring
- Document Pydantic models

#### [`image_gen.py`](json_video_agent/html_generation_agent/image_gen.py:1)
- Add module docstring explaining Gemini image generation
- Document constants (IMAGE_GENERATION_PROMPT, IMAGE_GEN_CONFIG, GEMINI_IMG_MODEL)
- Add docstring for [`generate_image_for_scene`](json_video_agent/html_generation_agent/image_gen.py:38) with Args/Returns/Raises

## Error Handling Standardization Plan

### Current Patterns Found

| Function Type | Current Pattern | Files |
|---------------|----------------|-------|
| ADK Tool functions | Return `{"status": "error", ...}` | agent.py files |
| Helper functions | Mixed (raise/return None/return dict) | content_grounding_tools.py, elevenlabs_tools.py |
| Validation | Mixed | Various |

### Standardization Rules

1. **ADK Tool Functions** (functions with `ToolContext` parameter):
   - MUST return `Dict[str, Any]`
   - MUST include `"status": "success"` or `"status": "error"`
   - On error: `{"status": "error", "message": "descriptive message"}`
   - On success: `{"status": "success", ...additional data...}`
     - Ensure that large filetype data is never returned. Instead, return artifact references instead of raw data
   - Document return dict structure in docstring

2. **Helper/Utility Functions**:
   - SHOULD raise exceptions on errors
   - Document exceptions in "Raises:" section
   - Return meaningful values (not error dicts)

3. **Functions that need review**:
   - [`fetch_doc_as_pdf`](json_video_agent/content_grounding_agent/content_grounding_tools.py:336) - Returns dict with status (good, document it)
   - [`fetch_markdown_level`](json_video_agent/content_grounding_agent/content_grounding_tools.py:299) - Returns `None` on error (document this)
   - [`generate_image_for_scene`](json_video_agent/html_generation_agent/image_gen.py:38) - Raises exception (document in Raises section)

### Specific Changes Needed

#### Clean Error Returns (Document in Docstring):
- [`slides_id_to_artifacts`](json_video_agent/content_grounding_agent/agent.py:17)
- [`create_markdown_artifact`](json_video_agent/content_grounding_agent/agent.py:87)
- [`save_google_doc_as_pdf_artifact`](json_video_agent/content_grounding_agent/agent.py:128)
- [`audio_generation_tool`](json_video_agent/audio_generation_agent/agent.py:149)
- [`fake_audio_generation`](json_video_agent/audio_generation_agent/agent.py:108)
- All `apply_*_updates` functions

#### Functions Returning None on Error (Document Behavior):
- [`fetch_markdown_level`](json_video_agent/content_grounding_agent/content_grounding_tools.py:299) - Document `Returns: ... or None if not found`

#### Functions Raising Exceptions (Add Raises Section):
- [`get_service_account_creds_from_env`](json_video_agent/content_grounding_agent/content_grounding_tools.py:31) - Raises ValueError
- [`generate_image_for_scene`](json_video_agent/html_generation_agent/image_gen.py:38) - Re-raises exceptions

## Type Annotation Priorities

### High Priority (Public API Functions)

All tool functions exposed to agents:
- [`slides_id_to_artifacts`](json_video_agent/content_grounding_agent/agent.py:17)
- [`create_markdown_artifact`](json_video_agent/content_grounding_agent/agent.py:87)
- [`save_google_doc_as_pdf_artifact`](json_video_agent/content_grounding_agent/agent.py:128)
- [`audio_generation_tool`](json_video_agent/audio_generation_agent/agent.py:149)
- [`fake_audio_generation`](json_video_agent/audio_generation_agent/agent.py:108)
- [`generate_html_from_slide_pngs`](json_video_agent/html_generation_agent/agent.py:212)
- [`generate_html_with_image_generation`](json_video_agent/html_generation_agent/agent.py:164)
- [`generate_final_export_obj`](json_video_agent/html_generation_agent/agent.py:91)

### Medium Priority (Helper Functions)

All functions in:
- [`shared/tools.py`](json_video_agent/shared/tools.py)
- [`content_grounding_tools.py`](json_video_agent/content_grounding_agent/content_grounding_tools.py)
- [`elevenlabs_tools.py`](json_video_agent/audio_generation_agent/elevenlabs_tools.py)

### Lower Priority (Internal State Management)

- Callback functions
- Apply update functions (already use Pydantic which provides typing)

## Implementation Sequence

### Phase 1: Foundation (Core Documentation)
1. Create root [`README.md`](README.md)
2. Add package docstrings to all [`__init__.py`](json_video_agent/__init__.py) files
3. Add module docstrings to all `.py` files

### Phase 2: Function Documentation
4. Add/improve docstrings for all tool functions (with ToolContext)
5. Add/improve docstrings for all helper functions
6. Document all Pydantic models

### Phase 3: Type Annotations
7. Add type hints to high-priority functions
8. Add type hints to medium-priority functions
9. Add type hints to remaining functions

### Phase 4: Constants and Configuration
10. Document all constants with inline comments
11. Document configuration variables
12. Add examples for environment setup

### Phase 5: Final Review
13. Create documentation style guide
14. Review consistency across all files
15. Test documentation with fresh eyes (colleague review)

## Metrics for Success

- [ ] 100% of `.py` files have module docstrings
- [ ] 100% of `__init__.py` files have package docstrings
- [ ] 100% of public functions have complete docstrings (with Args, Returns, Examples)
- [ ] 90%+ of functions have type annotations
- [ ] Error handling patterns documented consistently
- [ ] Root README.md provides clear onboarding path
- [ ] All constants are documented

## Example Transformations

### Before:
```python
def get_slides_data(presentation_id):
    """
    Orchestrates fetching speaker notes + thumbnails, returning a single list
    of slide dicts.
    """
    creds = get_service_account_creds_from_env()
    # ... implementation
```

### After:
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
            
    Example:
        >>> slides = get_slides_data("1a2b3c4d5e")
        >>> print(f"Found {len(slides)} slides")
        Found 10 slides
        >>> print(slides[0].keys())
        dict_keys(['index', 'slide_id', 'notes', 'png_base64'])
    """
    creds = get_service_account_creds_from_env()
    # ... implementation
```

## Questions for Review

1. **Docstring style**: Is Google-style acceptable, or would you prefer NumPy or reStructuredText?
2. **Type annotation strictness**: Should we use strict typing (`mypy --strict` compatible) or relaxed?
3. **Examples in docstrings**: Should all public functions include usage examples?
4. **README depth**: How detailed should the architecture section be? (High-level vs. detailed state flow)
5. **Deployment docs**: Should deployment notes stay in `deploy_notes/` or move to main README?

## Timeline Estimate

This is a documentation-only project, no code changes:

- **Phase 1 (Foundation)**: Focus on creating README and package/module docstrings
- **Phase 2 (Function Docs)**: Systematic documentation of all functions
- **Phase 3 (Type Hints)**: Adding type annotations throughout
- **Phase 4 (Constants)**: Documenting configuration and constants
- **Phase 5 (Review)**: Final consistency pass and style guide creation

**Note**: Estimates intentionally omitted per instruction guidelines.
