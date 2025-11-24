# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Ultimate Notion is a high-level Python client for the Notion API providing a Pythonic, object-oriented interface built on top of `notion-sdk-py`.

## Commands

### Running Python Commands

Always use hatch for Python commands:
```bash
hatch run <command>              # Use default environment
hatch run vscode:<command>       # Use vscode environment (for IDE integration)
```

### Testing
```bash
hatch run test                   # Run tests with VCR recording (records once)
hatch run vcr-only               # Offline tests using existing cassettes
hatch run vcr-rewrite            # Regenerate all VCR cassettes
hatch run debug                  # Debug tests with IPython pdb
hatch run test -k "test_name"    # Run single test
```

### Linting and Type Checking
```bash
hatch run lint:all               # Run mypy + ruff checks (run before submitting)
hatch run lint:fix               # Auto-fix ruff issues
hatch run lint:typing            # Run mypy only
hatch run lint:style             # Run ruff only
```

### Documentation
```bash
hatch run docs:serve             # Local docs server at localhost:8000
hatch run docs:build             # Build docs
```

## Architecture

### Two-Layer API Design

1. **Low-level obj_api** (`src/ultimate_notion/obj_api/`): Pydantic models directly mapping Notion API JSON structures
2. **High-level API** (`src/ultimate_notion/`): User-friendly wrapper classes

The `Wrapper[GT]` class in `core.py` bridges both layers via the `obj_ref` attribute.

### Polymorphic Object System

All obj_api classes inherit from base types with automatic type resolution:
- `TypedObject[T]` - polymorphic base with `type` field (blocks, properties)
- `NotionObject` - top-level resources with `object` field (pages, databases, users)
- `GenericObject` - basic Pydantic model for nested data

Example pattern:
```python
class PropertyValue(TypedObject[Any], polymorphic_base=True):
    # Base class automatically resolves to correct subtype

class Title(PropertyValue, type='title'):
    # Automatically registered in _typemap for 'title' type
```

### Object Wrapping Pattern

```python
class HighLevelObject(Wrapper[LowLevelObject], wraps=LowLevelObject):
    def __init__(self, ...):
        super().__init__(...)  # Calls LowLevelObject.build()
```

### UnsetType Pattern

Use `Unset` sentinel for optional API fields where `None` has semantic meaning (e.g., "delete"):
```python
from ultimate_notion.obj_api.core import Unset, UnsetType

class SomeObject(GenericObject):
    optional_field: str | UnsetType = Unset
```

### Session Management

- Single active session via `get_active_session()`
- Object caching in `Session.cache` by UUID
- Use context manager: `with uno.Session() as notion:`

## Key File Locations

### Core Infrastructure
- `session.py` - API client and object caching
- `core.py` - Base wrapper classes and session management
- `config.py` - Configuration handling with TOML files

### Object Model (obj_api/)
- `core.py` - Base Pydantic models with polymorphism
- `objects.py` - Shared object types (users, references)
- `blocks.py` - Block types
- `props.py` - Property value types
- `schema.py` - Database schema/property definitions

### High-Level API
- `page.py`, `database.py`, `blocks.py` - Main user-facing objects
- `schema.py` - Database schema with property classes
- `query.py` - Database querying with conditions
- `rich_text.py` - Text formatting and mentions

## Code Style

- Ruff for linting/formatting: single quotes, 120 char line length
- MyPy for type checking with strict settings
- Uses `pendulum` for date/time (not `datetime`)

## Testing Notes

- VCR.py records API responses as cassettes in `tests/cassettes/`
- Never use `datetime.now()` in tests - breaks VCR replay
- Module-scoped fixtures record only on first test execution
- Delete cassettes to regenerate them
- Requires `NOTION_TOKEN` environment variable for live API tests

## Environment Variables

- `NOTION_TOKEN` - Required for API access
- `ULTIMATE_NOTION_CONFIG` - Path to config.toml file
- `ULTIMATE_NOTION_DEBUG` - Enable debug logging
