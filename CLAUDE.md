# Project Configuration

## 1. Project Overview

Ultimate-Notion is a pythonic, high-level API for Notion. It provides a comprehensive interface to interact with Notion's API, allowing users to manage pages, databases (data sources), blocks, and more.

**Current Major Work**: Migration to Notion API 2025-09-03
- Migrating from "database" terminology to "data source" for what Notion previously called databases
- Introducing a NEW "Database" concept that represents collections of data sources
- Adopting `ds` abbreviation for data sources, reserving `db` for the new database collections

## 2. Key Technologies & Conventions

### Core Technologies
- **Python**: 3.10+ with full type hints
- **Pydantic**: For data validation and object modeling
- **notion-client**: Official Notion SDK (currently 2.7.0 for API 2025-09-03)
- **VCR.py**: For recording and replaying HTTP interactions in tests

### Code Conventions
- **Type Safety**: Full mypy type checking required
- **Code Style**: Ruff for linting and formatting
- **Naming Conventions**:
  - `ds` = data source (what was previously called "database")
  - `db` = database collection (NEW concept in API 2025-09-03)
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
class DataSource(DataObject[obj_blocks.DataSource], wraps=obj_blocks.DataSource):
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

```
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

- `session.py` (528 lines): Main entry point for API operations
- `database.py` (308 lines): DataSource and Database classes
- `schema.py` (1376 lines): Schema definition and property system
- `page.py` (664 lines): Page operations and management
- `blocks.py` (1840 lines): Block type wrappers
- `query.py` (656 lines): Query building and filtering

## 5. Testing

### Test Structure
```
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
- `issues/issue188.md`: Migration plan for Notion API 2025-09-03

### Migration Documentation
- **`issues/issue188.md`**: Complete migration plan and progress log
  - Detailed phase-by-phase migration steps
  - Progress log with all commits
  - Known issues and next steps

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
hatch run lint:all        # Run all linters
hatch run lint:style      # Ruff style check
hatch run lint:typing     # Mypy type check

# Format code
hatch run lint:fmt        # Auto-format with ruff

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

```
<type>(<scope>): <description>

[optional body]

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
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

```
feat(obj_api): Add DataSource class and DataSourcesEndpoint for API 2025-09-03

refactor: Use 'ds' abbreviation for data source throughout codebase

docs: Add comprehensive progress log for Phase 3 & 4
```

## 9. Migration Status (API 2025-09-03)

### Completed Phases
- ✅ Phase 1: Preparation and analysis
- ✅ Phase 2: Low-level obj_api layer migration
- ✅ Phase 3: High-level API migration (Database → DataSource with `ds` abbreviation)
- ✅ Phase 4: Examples and tests updated
- ✅ NEW Database class added (placeholder)

### Current State
- All source code uses `ds` for data sources
- All tests and examples updated
- `DataSource` class: What was previously called "database"
- `Database` class: NEW concept for collections (placeholder implementation)

### Next Steps (Phase 5)
1. Rewrite VCR cassettes
2. Run full test suite
3. Fix remaining type errors
4. Verify all tests pass

### Key Terminology
- **DataSource** (`ds`): A single data source with schema and pages (formerly "database")
- **Database** (`db`): A collection of data sources (NEW in API 2025-09-03, not yet implemented)

## 10. Important Notes for AI Assistants

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
- Check `issues/issue188.md` for migration context
- Review existing code patterns in similar modules
- Run `hatch run lint:all` before committing
- Use specific file paths for git operations
