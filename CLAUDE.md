# Project Configuration

## 1. Project Overview

Ultimate Notion is a high-level Python client for the Notion API. A `Database` contains one
or more data sources. A `DataSource` owns the property schema and holds the pages that
queries return.

## 2. Key Technologies & Conventions

### Core Technologies

- **Python**: 3.11+ with full type hints
- **Pydantic**: For data validation and object modeling
- **notion-client**: Official Notion SDK (currently 3.1 for API 2026-03-11)
- **VCR.py**: For recording and replaying HTTP interactions in tests

### Code Conventions

- **Type Safety**: Full static type checking required (mypy and ty, via `hatch run lint:typing`)
- **Code Style**: Ruff for linting and formatting
- **Naming Conventions**:
  - Use `ds` for a data source and `db` for its database container.
  - Use snake_case for functions, variables, and methods
  - Use PascalCase for classes
  - Use UPPER_CASE for constants

### Git Workflow

- **NEVER use `git add -A` or `git add .`** - always specify exact file paths
- Always use conventional commit messages
- Include co-authorship footer for AI-assisted commits
- Use feature branches for major work

## 3. Architectural Principles

### Two-Layer Design

**Low-Level Layer (`obj_api/`):**

- Direct mapping to Notion API objects
- Pydantic models for all API types
- Minimal business logic
- Used by high-level layer

**High-Level Layer:**

- Pythonic, user-friendly API
- Wraps low-level objects with `DataObject` pattern
- Provides schema definitions, queries, views
- Session-based interaction model

### Key Patterns

**DataObject Wrapper Pattern:**

```python
class DataSource(DataContainer[obj_blocks.DataSource], wraps=obj_blocks.DataSource):
    """High-level wrapper for data source objects"""
```

**Schema Binding:**

- Schemas bind to data sources using `bind_ds()`
- Properties are defined using `PropType` descriptors
- Automatic property mapping and validation

**Type Guards:**

- Use `TypeIs` for proper type narrowing
- Prefer `isinstance()` checks for simple cases
- Type guards: `is_ds()`, `is_page()`, etc.

## 4. Navigation Architecture

### Source Code Structure

```shell
src/ultimate_notion/
├── obj_api/              # Low-level API layer
│   ├── blocks.py         # Block type definitions (DataSource, Database, Page, etc.)
│   ├── endpoints.py      # API endpoint wrappers (DataSourcesEndpoint, etc.)
│   ├── objects.py        # Reference objects (DataSourceRef, PageRef, etc.)
│   ├── schema.py         # Property type definitions
│   └── query.py          # Query builders
├── session.py            # Session management (create_ds, search_ds, etc.)
├── database.py           # DataSource and Database classes
├── page.py               # Page class and operations
├── blocks.py             # High-level block wrappers
├── schema.py             # Schema definition and binding
├── query.py              # High-level query interface
├── view.py               # View/result set handling
├── props.py              # Property value types
└── adapters/             # Third-party integrations
    └── google/tasks/     # Google Tasks sync
```

### Key Files

- `session.py`: Main entry point for API operations
- `database.py`: Data source and database classes
- `schema.py`: Schema definition and property system
- `page.py`: Page operations and management
- `blocks.py`: Block type wrappers
- `query.py`: Query building and filtering

## 5. Testing

### Test Structure

```shell
tests/
├── cassettes/           # VCR cassettes for recorded API calls
├── conftest.py          # Test fixtures and configuration
├── test_*.py            # Test modules
└── obj_api/             # Low-level API tests
```

### Key Testing Commands

```bash
# Run all tests (using VCR cassettes)
hatch run test

# Run tests without VCR (live API calls)
hatch run vcr-off

# Rewrite VCR cassettes (use with CAUTION)
hatch run vcr-rewrite

# Drop all cassettes
hatch run vcr-drop-cassettes

# Run only VCR cassettes (no live API)
hatch run vcr-only
```

### Testing Best Practices

1. **VCR Usage**: Most tests use VCR to replay recorded API interactions
2. **Fixtures**: Use fixtures from `conftest.py` for common objects
3. **Never use dynamic values**: `datetime.now()` will be recorded and replayed
4. **Fixture scope**: Be careful with module/session scoped fixtures

### Common Test Fixtures

- `notion`: Fresh session without state (function scope)
- `notion_cached`: Cached session (module scope)
- `root_page`: Test parent page
- `contacts_db`, `task_db`, `wiki_db`: Pre-configured data sources
- `person`: Test user object

## 6. Important Files & Directories

### Configuration Files

- `pyproject.toml`: Project dependencies, scripts, and tool configuration
- `.gitignore`: Git ignore patterns (includes `issues/` for test files)
- `CLAUDE.md`: This file - project documentation for Claude

### Source Directories

- `src/ultimate_notion/`: Main source code
- `tests/`: Test suite
- `examples/`: Usage examples
- `docs/`: Documentation (Markdown-based)

### Ignored Directories

- `issues/`: Test files and debugging scripts (in .gitignore)
- `.ultimate-notion/`: Local configuration
- `.venv*/`: Virtual environments

## 7. Common Commands

### Development

```bash
# Install dependencies
hatch env create

# Run linting
hatch run lint:all        # Run all linters (style + typing)
hatch run lint:style      # Ruff check + format check
hatch run lint:typing     # Type check (mypy + ty)

# Format code
hatch run lint:fix        # Auto-format (ruff format) and apply ruff fixes

# Run tests
hatch run test            # All tests with VCR
hatch run vcr-only        # Only VCR replay
hatch run vcr-off         # Live API calls
```

### Package Management

```bash
# Upgrade a specific package
hatch run upgrade-pkg <package-name>

# Update all dependencies
hatch run upgrade-all
```

### VCR Cassettes

```bash
# Drop cassettes (careful!)
hatch run vcr-drop-cassettes

# Rewrite cassettes (very careful! live API calls)
hatch run vcr-rewrite

# Run specific test with VCR rewrite
hatch run vcr-rewrite -k test_name
```

## 8. Commit Conventions

### Conventional Commits Format

```text
<type>(<scope>): <description>

🤖 [optional body]
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `refactor`: Code refactoring
- `docs`: Documentation changes
- `test`: Test changes
- `chore`: Maintenance tasks
- `build`: Build system changes

### Scopes

- `obj_api`: Low-level API layer
- `session`: Session management
- `schema`: Schema system
- `query`: Query system
- `blocks`: Block handling

### Examples

```text
feat(obj_api): add a data source endpoint

refactor(query): simplify filter construction

docs: explain schema binding
```

## 9. Important Notes for AI Assistants

### Critical Git Rules

- **NEVER use `git add -A` or `git add .`**
- Always stage specific files: `git add src/file.py tests/file.py`
- The `issues/` directory is in `.gitignore` - use `git add -f` if needed

### Code Review Checklist

1. Type hints present and correct
2. Docstrings for public methods
3. Tests updated for changes
4. Linting passes (`hatch run lint:all`)
5. No VCR cassette changes unless intentional

### Common Pitfalls

1. **VCR cassettes**: Never commit cassette changes accidentally
2. **Dynamic values in tests**: Avoid `datetime.now()`, use fixed dates
3. **Type narrowing**: Use `isinstance()` or proper type guards, not just boolean checks
4. **Schema binding**: Remember to bind schemas to data sources before use

### When in Doubt

- Read [CONTRIBUTING.md](CONTRIBUTING.md) for development and test workspace setup.
- Review existing code patterns in similar modules
- Run `hatch run lint:all` before committing
- Use specific file paths for git operations
