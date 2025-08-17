# Ultimate Notion Copilot Instructions

## Project Overview

Ultimate Notion is a high-level Python client for the Notion API that provides a Pythonic, object-oriented interface built on top of `notion-sdk-py`. The architecture consists of two main layers:

1. **Low-level obj_api**: Direct Pydantic models mapping Notion API responses (`src/ultimate_notion/obj_api/`)
2. **High-level API**: User-friendly wrapper classes (`src/ultimate_notion/`)

## CRITICAL: Python Command Execution

🚨 **ALWAYS USE HATCH FOR PYTHON COMMANDS IN VSCODE** 🚨

- **NEVER** use `python` directly in terminal commands
- **NEVER** use `/path/to/python` directly
- **ALWAYS** use `hatch run vscode:PYTHON_COMMAND` format

Examples of CORRECT usage:
- `hatch run vscode:python script.py` (not `python script.py`)
- `hatch run vscode:mypy src/file.py` (not `mypy src/file.py`)
- `hatch run vscode:pytest tests/` (not `pytest tests/`)
- `hatch run vscode:pip install package` (not `pip install package`)

This ensures the correct virtual environment and dependencies are used.

## Core Architecture Patterns

### Two-Layer API Design
- **obj_api layer**: Pydantic models in `src/ultimate_notion/obj_api/` directly mirror Notion API JSON structures
- **High-level layer**: Wrapper classes in `src/ultimate_notion/` provide Pythonic interfaces
- Bridge pattern: `Wrapper[GT]` class in `core.py` connects both layers via `obj_ref` attribute

### Polymorphic Object System
All obj_api classes inherit from base types with automatic type resolution:
- `TypedObject[T]` - polymorphic base with `type` field (blocks, properties, etc.)
- `NotionObject` - top-level resources with `object` field (pages, databases, users)
- `GenericObject` - basic Pydantic model for nested data

Example pattern:
```python
class PropertyValue(TypedObject[Any], polymorphic_base=True):
    # Base class automatically resolves to correct subtype

class Title(PropertyValue, type='title'):
    # Automatically registered in _typemap for 'title' type
```

### UnsetType Pattern
Use `Unset` sentinel value for optional API fields where `None` has semantic meaning:
```python
from ultimate_notion.obj_api.core import Unset, UnsetType

class SomeObject(GenericObject):
    optional_field: str | UnsetType = Unset  # vs None which means "delete"
```

## Key Development Workflows

### Running Python Commands (MANDATORY FORMAT)
- `hatch run vscode:python script.py` - Run Python scripts
- `hatch run vscode:mypy file.py` - Type checking
- `hatch run vscode:pytest tests/` - Run tests
- `hatch run vscode:pip install package` - Install packages

### Testing with VCR.py
- `hatch run test` - Run tests with VCR recording
- `hatch run vcr-only` - Offline tests using existing cassettes
- `hatch run vcr-rewrite` - Regenerate all VCR cassettes
- `hatch run debug` - Debug tests with pdb

### Linting and Formatting (MANDATORY FOR ALL CHANGES)
- `hatch run lint:all` - Run mypy + ruff checks (ALWAYS RUN BEFORE SUBMITTING)
- `hatch run lint:fix` - Auto-fix ruff issues
- Uses ruff for formatting (single quotes, 120 char line length)

### Environment Management
- `hatch run upgrade-all` - Upgrade all dependencies
- `hatch run upgrade-pkg <package>` - Upgrade specific package
- Environment files in `locks/` directory

## REMEMBER: NEVER USE BARE PYTHON COMMANDS

❌ **WRONG:**
- `python script.py`
- `mypy file.py`
- `pytest tests/`
- `pip install package`

✅ **CORRECT:**
- `hatch run vscode:python script.py`
- `hatch run vscode:mypy file.py`
- `hatch run vscode:pytest tests/`
- `hatch run vscode:pip install package`

## Critical Implementation Patterns

### Session Management
- Single active session via `get_active_session()`
- Object caching in `Session.cache` by UUID to avoid duplicate API calls
- Always use context manager: `with uno.Session() as notion:`

### Object Wrapping
When creating wrapper classes, follow the pattern:
```python
class HighLevelObject(Wrapper[LowLevelObject], wraps=LowLevelObject):
    def __init__(self, ...):
        # High-level construction logic
        super().__init__(...)  # Calls LowLevelObject.build()
```

### Property Value Handling
- Property values use `PropertyValue.build()` for construction
- Type mapping via `_type_value_map` class variable
- Always serialize via `serialize_for_api()` to remove Unset values

### Error Handling
- Custom exceptions in `errors.py` inherit from base classes
- Session errors, API usage errors, and object-specific errors
- Use proper error messages with context

## File Organization

### Core Infrastructure
- `session.py` - API client and object caching
- `core.py` - Base wrapper classes and session management
- `config.py` - Configuration handling with TOML files

### Object Model
- `obj_api/core.py` - Base Pydantic models with polymorphism
- `obj_api/objects.py` - Shared object types (users, references, etc.)
- `obj_api/blocks.py` - Block types (pages, databases, content blocks)
- `obj_api/props.py` - Property value types
- `obj_api/schema.py` - Database schema/property definitions

### High-Level API
- `page.py`, `database.py`, `blocks.py` - Main user-facing objects
- `schema.py` - Database schema with property classes
- `query.py` - Database querying with conditions
- `rich_text.py` - Text formatting and mentions

## Dependencies and Constraints

### Required Dependencies
- `pydantic ~=2.0` - Core data modeling
- `notion-client ~=2.4` - Low-level Notion API client
- `pendulum ~=3.0` - Date/time handling (not datetime)

### Optional Features
- `[google]` - Google Tasks sync adapter
- `[pandas]` - DataFrame export
- `[polars]` - Polars DataFrame export

### Environment Variables
- `NOTION_TOKEN` - Required for API access
- `ULTIMATE_NOTION_CONFIG` - Path to config.toml file
- `ULTIMATE_NOTION_DEBUG` - Enable debug logging

## Common Gotchas

### VCR Testing
- Never use `datetime.now()` in tests - breaks VCR replay
- Module-scoped fixtures only record on first test execution
- Delete cassettes in `tests/cassettes/` to regenerate

### Pydantic Model Updates
- Use `model_rebuild(force=True)` after changing field defaults
- Call `_set_field_default()` to modify inherited field values

### Type Resolution
- Polymorphic classes need `polymorphic_base=True` parameter
- Missing 'type' field causes resolution errors in TypedObject subclasses
- obj_api models auto-register in `_typemap` during class creation

## Testing Patterns

- Fixtures in `conftest.py` use module scope for API efficiency
- Mock external services, use VCR for Notion API
- Test both obj_api and high-level API layers
- Use `pytest-recording` for VCR cassette management
- **MANDATORY**: Always run `hatch run lint:all` before submitting changes to ensure code quality
- **REMEMBER**: Use `hatch run vscode:pytest` not bare `pytest`
