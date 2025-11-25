# Migration of Ultimate-Notion to the Notion API-Version 2025-09-03

This issue is tracked under: https://github.com/ultimate-notion/ultimate-notion/issues/118
The library notion-sdk-py supports the Notion API-Version 2025-09-03 from version 2.6.0 on (use 2.7.0).
The Upgrading howto is under: https://developers.notion.com/docs/upgrade-guide-2025-09-03

> **Status**: The API version 2025-09-03 was released on September 3rd, 2025. The old API version
> is now deprecated. Migration should proceed promptly.

## Conceptual Changes

In API-Version 2025-09-03:
- What was previously called a **"database"** is now called a **"data source"** (or "datasource")
- A new **"database"** concept is introduced that can encompass multiple data sources
- Data sources are now first-class API objects with their own endpoints and properties
- The old single-data-source database model maps 1:1 to a data source in the new model

This is essentially a terminology shift where the granular data container (with schema, properties, pages)
is now the "data source", while "database" becomes a higher-level grouping concept.

## Naming Convention

We adopt a **`ds` abbreviation** for data sources throughout the codebase:

| Old Name | New Name | Concept |
|----------|----------|---------|
| `*_db` | `*_ds` | Data source (formerly database) |
| n/a | `*_database` | New database container concept (collection of data sources) |
| `DBQueryBuilder` | `DataSourceQueryBuilder` | Query builder for data sources (kept full name in obj_api) |
| `db_only` | `ds_only` | Filter parameter |
| `_bind_db` | `_bind_ds` | Internal binding method |

**Rationale:**
- Using `ds` for data sources keeps the API concise and reduces verbosity
- `db` is reserved for the NEW Database concept (collection of data sources)
- This creates a clear distinction: `ds` = single data source, `db` = database collection
- Example: `session.create_ds()` for data sources, `session.create_db()` for databases (future)
- The pattern: `ds` is more specific (data source), `db` is the container (database)

**Important Distinction:**
- `DataSource` (abbreviated as `ds`) = What Notion previously called a "database" - a single data source with schema, properties, and pages
- `Database` (abbreviated as `db`) = NEW concept in API 2025-09-03 - a collection/container that can hold multiple data sources
- **No backward compatibility alias needed**: The old `Database` class is now `DataSource`, and `Database` is a completely new class for the new concept

## Impact Analysis

### Files Requiring Changes

**Low-level obj_api layer:**
- `src/ultimate_notion/obj_api/endpoints.py` - Add `DataSourcesEndpoint`, modify `DatabasesEndpoint`
- `src/ultimate_notion/obj_api/blocks.py` - Add `DataSource` NotionObject, keep `Database` for new concept
- `src/ultimate_notion/obj_api/objects.py` - Add `DataSourceRef`, potentially modify `DatabaseRef`
- `src/ultimate_notion/obj_api/schema.py` - Relations now may need `data_source_id` alongside `database_id`
- `src/ultimate_notion/obj_api/query.py` - Rename `DBQueryBuilder` to `DataSourceQueryBuilder`

**High-level API layer:**
- `src/ultimate_notion/database.py` - Rename `Database` to `DataSource` (keep file as `database.py`, can hold both classes)
- `src/ultimate_notion/database.py` - Add new `Database` class for the NEW container concept
- `src/ultimate_notion/session.py` - Rename all `*_db` methods to `*_ds`, add new `*_database` methods for collections
- `src/ultimate_notion/blocks.py` - Update `DataObject` hierarchy, add `ChildDataSource` block type
- `src/ultimate_notion/page.py` - Pages belong to data sources (parent_ds, in_ds properties)
- `src/ultimate_notion/schema.py` - Schema binds to data sources (_bind_ds method)
- `src/ultimate_notion/query.py` - Queries target data sources (Query.ds attribute)
- `src/ultimate_notion/view.py` - Views are of data sources (View.ds attribute)

**Other files with "database" references (316 occurrences across 24 files):**
- `src/ultimate_notion/core.py`
- `src/ultimate_notion/props.py`
- `src/ultimate_notion/rich_text.py`
- `src/ultimate_notion/errors.py`
- `src/ultimate_notion/comment.py`
- `src/ultimate_notion/__init__.py`
- `src/ultimate_notion/adapters/google/tasks/sync.py`

## Detailed Migration Steps

### Phase 1: Preparation & Analysis

1. **Create a feature branch** for the migration work
2. **Document current API behavior** by running full test suite with VCR recording
   ```bash
   hatch run vcr-rewrite
   ```
3. **Review notion-sdk-py 2.6.0 source** to understand new endpoint signatures:
   - Check `notion_client/api_endpoints.py` for new `DataSourcesEndpoint`
   - Identify parameter changes in `DatabasesEndpoint`

### Phase 2: Low-Level obj_api Layer Changes

#### Step 2.1: Update `pyproject.toml`
```toml
# Change from:
"notion-client~=2.5.0",
# To:
"notion-client~=2.7.0",
```
Run `hatch run upgrade-pkg notion-client` to update locks.

#### Step 2.2: Add DataSource to `obj_api/blocks.py`
```python
class DataSource(DataObject, MentionMixin, object='data_source'):
    """A data source record type (formerly 'database' in pre-2025-09-03 API)."""

    title: list[SerializeAsAny[RichTextBaseObject]] | UnsetType = Unset
    url: str | UnsetType = Unset
    public_url: str | None = None
    icon: SerializeAsAny[FileObject] | EmojiObject | CustomEmojiObject | None = None
    cover: SerializeAsAny[FileObject] | None = None
    properties: dict[str, SerializeAsAny[Property]]
    description: list[SerializeAsAny[RichTextBaseObject]] | UnsetType = Unset
    is_inline: bool = False
    database_id: UUID | UnsetType = Unset  # NEW: reference to parent database

    def build_mention(self, style: Annotations | None = None) -> MentionObject:
        return MentionDataSource.build_mention_from(self, style=style)
```

Keep existing `Database` class but repurpose it for the new database concept:
```python
class Database(DataObject, object='database'):
    """A database that can contain multiple data sources (new 2025-09-03 concept)."""

    title: list[SerializeAsAny[RichTextBaseObject]] | UnsetType = Unset
    data_sources: list[DataSourceRef] = Field(default_factory=list)
    # ... other new database fields
```

#### Step 2.3: Add references to `obj_api/objects.py`
```python
class DataSourceRef(ParentRef, type='data_source_id'):
    """Reference to a DataSource, primarily used as parent reference."""

    data_source_id: UUID

    @classmethod
    def build(cls, ref: DataSource | str | UUID) -> DataSourceRef:
        # ... implementation
```

#### Step 2.4: Update `obj_api/schema.py` for Relations
The `Relation` property needs to support both `database_id` (for the new database) and `data_source_id`:
```python
class PropertyRelation(TypedObject[GO_co], polymorphic_base=True):
    """Defines common configuration for a property relation."""

    database_id: UUID | UnsetType = Unset  # Keep for backwards compat or new DB concept
    data_source_id: UUID | UnsetType = Unset  # NEW: actual target for queries
```

#### Step 2.5: Create `DataSourcesEndpoint` in `obj_api/endpoints.py`
```python
class DataSourcesEndpoint(Endpoint):
    """Interface to the 'data_sources' endpoint of the Notion API."""

    @property
    def raw_api(self) -> NCDataSourcesEndpoint:
        """Return the underlying endpoint in the Notion SDK."""
        return self.api.client.data_sources  # or whatever notion-sdk-py calls it

    def create(self, parent: Page, schema: Mapping[str, Property], ...) -> DataSource:
        """Add a data source to the given Page parent."""
        # Implementation similar to current DatabasesEndpoint.create

    def retrieve(self, dsref: DataSource | str | UUID) -> DataSource:
        """Return the DataSource with the given ID."""

    def update(self, ds: DataSource, ...) -> None:
        """Update the DataSource object on the server."""

    def delete(self, ds: DataSource) -> DataSource:
        """Delete (archive) the specified DataSource."""

    def query(self, ds: DataSource | UUID | str) -> DataSourceQueryBuilder:
        """Initialize a new Query object for the data source."""
```

Update `NotionAPI.__init__`:
```python
def __init__(self, client: NCClient):
    self.client = client
    self.blocks = BlocksEndpoint(self)
    self.data_sources = DataSourcesEndpoint(self)  # NEW
    self.databases = DatabasesEndpoint(self)  # MODIFIED for new database concept
    self.pages = PagesEndpoint(self)
    # ...
```

#### Step 2.6: Update `obj_api/query.py`
- Rename `DBQueryBuilder` to `DataSourceQueryBuilder`
- Update `SearchQueryBuilder` filter to use `data_source` instead of `database`:
  ```python
  def filter(self, *, page_only: bool = False, datasource_only: bool = False) -> Self:
      # Change filter["value"] from "database" to "data_source"
  ```

### Phase 3: High-Level API Layer Changes

#### Step 3.1: Update `database.py`

**Keep the file as `database.py`** - it will contain both classes:

```python
# Rename the existing Database class to DataSource
class DataSource(DataObject[obj_blocks.DataSource], wraps=obj_blocks.DataSource):
    """A Notion data source (formerly 'database' in pre-2025-09-03 API).

    This object always represents an original data source, not a linked one.
    A data source has a schema, properties, and contains pages.
    """
    # ... keep most implementation, update docstrings and references
    # Update properties: is_database -> is_ds, etc.
```

**Create NEW Database class** for the container concept:
```python
class Database(DataObject[obj_blocks.Database], wraps=obj_blocks.Database):
    """A Notion database - a collection that can contain multiple data sources.

    This is a NEW concept introduced in API version 2025-09-03.
    Think of it as a container or grouping mechanism for related data sources.
    """

    @property
    def data_sources(self) -> list[DataSource]:
        """Return all data sources in this database."""
        # ...
```

**Important**: Both classes live in `database.py` - no file rename needed.

#### Step 3.2: Update `session.py` Methods
Rename and update methods using `ds` abbreviation for data sources:
```python
# Old API -> New API naming

# Data source methods (what was previously called "database")
create_db      -> create_ds         # Create a data source
search_db      -> search_ds         # Search for data sources
get_db         -> get_ds            # Get a data source by ID
get_or_create_db -> get_or_create_ds # Get or create a data source

# Database methods (NEW concept - collection of data sources)
# Note: create_db() will be used for the NEW Database class once implemented
# For now, we only have data sources (ds), so only *_ds methods exist
```

This naming convention:
- Uses `ds` abbreviation for data sources (concise, reduces verbosity)
- Keeps `db` for the future Database collection concept (when implemented)
- Creates clear distinction: `ds` = single data source, `db` = database collection
- Example: `session.create_ds()` for data sources, `session.create_db()` for databases (future)

#### Step 3.3: Update `schema.py`
- Schema binds to `DataSource`, not `Database`
- Update `_bind_db` to `_bind_ds`
- Update `_datasource` to `_ds` (internal attribute)
- Update `get_datasource()` to `get_ds()`
- Update relation property classes

#### Step 3.4: Update `query.py`
- `Query` class works with `DataSource`
- Update type hints and docstrings

#### Step 3.5: Update `blocks.py`
- Add `ChildDataSource` block type (analogous to `ChildDatabase`)
- Update `DataObject` hierarchy if needed

#### Step 3.6: Update `page.py`
- Pages can be children of data sources
- Update parent resolution logic

### Phase 4: Update Examples and Tests

**No backwards compatibility alias needed!**

The old `Database` class is now `DataSource`, and `Database` is a completely NEW class for the new database collection concept. These are two distinct objects:

- `DataSource` = what was previously called "database" (single data source with schema)
- `Database` = NEW container concept (collection of data sources)

Update all examples and tests:
```python
# Old code
db = notion.create_db(parent, schema=MySchema)

# New code
ds = notion.create_ds(parent, schema=MySchema)  # Create a data source
db = notion.create_db(...)  # NEW: Create a database collection (when implemented)
```

Note: For now, only `*_ds` methods exist since Database collections are not yet implemented.

### Phase 5: Testing

#### Step 5.1: Update Test Files
All test files in `tests/` need updating:
- `tests/test_database.py` -> rename to `tests/test_datasource.py` or update in place
- Update all fixtures and test functions
- Add new tests for the new `Database` concept

#### Step 5.2: Rewrite VCR Cassettes
```bash
hatch run vcr-drop-cassettes
hatch run vcr-rewrite
```

#### Step 5.3: Run Full Test Suite
```bash
hatch run test
hatch run lint:all
```

### Phase 6: Documentation Updates

1. **Update all docstrings** with new terminology
2. **Update `docs/`** markdown files:
   - `features.md` - list DataSource as the new primary object
   - `getting_started.md` - update examples
   - All API reference docs
3. **Update `CHANGELOG.md`** with breaking changes
4. **Update `README.md`** examples if needed

### Phase 7: Release Preparation

1. **Bump version** (major version bump due to breaking changes)
2. **Update migration guide** in documentation
3. **Test against production** with a staging Notion workspace
4. **Create release notes** highlighting:
   - Breaking changes
   - Migration path
   - New features (multi-datasource databases)

## Additional Items (Often Overlooked)

### Error Classes (`errors.py`)
```python
# Rename
UnknownDatabaseError -> UnknownDataSourceError
EmptyDBError -> EmptyDataSourceError

# Update docstrings
SchemaNotBoundError  # "not bound to a database" -> "not bound to a data source"
SchemaError          # "issues with the schema of a database" -> "...of a data source"
```

### Mentions (`obj_api/objects.py`)
```python
# Rename
MentionDatabase -> MentionDataSource

# Keep MentionDatabase as alias for backwards compatibility during transition
```

### Public Exports (`__init__.py`)
```python
# Current export
from ultimate_notion.database import Database

# New exports
from ultimate_notion.datasource import DataSource
from ultimate_notion.database import Database  # new container concept

# __all__ updates
'Database',     # new container concept
'DataSource',   # formerly Database
```

### Schema Internal Methods (`schema.py`)
```python
# Rename internal methods
_bind_db -> _bind_datasource
is_bound -> is_bound  # keep, but update docstring "bound to a data source"

# Update TYPE_CHECKING imports
from ultimate_notion.datasource import DataSource  # was: database import Database
```

### Block Types
- `ChildDatabase` in `obj_api/blocks.py` -> keep for new concept
- Add `ChildDataSource` block type
- Update `blocks.py` high-level wrappers accordingly

### File Renames
Consider renaming files for clarity:
- `database.py` -> `datasource.py` (move new Database class elsewhere or keep both in same file)
- `test_database.py` -> `test_datasource.py`

### Cache Considerations
- `Session.cache` uses UUIDs as keys
- Data sources and databases will have different UUIDs, so no collision
- But cache type hints need updating: `dict[UUID, DataObject | User]`

### Type Hints Throughout
Many files have type hints like:
```python
def some_func(db: Database) -> ...:
```
These need systematic updates to use `DataSource` where appropriate.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Notion API behavior differs from docs | Medium | High | Test thoroughly with real API, not just VCR |
| notion-sdk-py 2.7.0 has bugs | Low | Medium | Pin exact version, monitor issues |
| User code breaks silently | Medium | High | Provide clear deprecation warnings |
| VCR cassettes incompatible | High | Low | Plan for full rewrite |
| Relations break due to new IDs | Medium | High | Test relation scenarios extensively |

## Open Questions

1. Does the new `Database` concept require workspace-level permissions we don't have?
2. How do existing linked databases behave in the new model?
3. Are there any endpoints that still use `database_id` vs `data_source_id` inconsistently?
4. What happens to webhooks - do we need to handle new event types?

## Estimated Effort

- Phase 1 (Preparation): 0.5 days
- Phase 2 (Low-level): 2-3 days
- Phase 3 (High-level): 2-3 days
- Phase 4 (Backwards compat): 0.5 days
- Phase 5 (Testing): 2-3 days
- Phase 6 (Documentation): 1-2 days
- Phase 7 (Release): 0.5 days

**Total: ~10-13 days of focused work**

---

## Progress Log

### 2025-11-24: Phase 1 & 2 Completed

#### Commits Made

1. **`a2fbdb5c` - docs: Add detailed migration plan for Notion API 2025-09-03**
   - Created this comprehensive migration plan document
   - Documented conceptual changes, naming conventions, and 7-phase approach
   - Added risk assessment and effort estimates

2. **`f73c8d2d` - build: Upgrade notion-client to ~=2.7.0**
   - Updated `pyproject.toml` dependency from `~=2.5.0` to `~=2.7.0`
   - notion-sdk-py 2.7.0 provides `DataSourcesEndpoint` with retrieve, query, create, update methods
   - `DatabasesEndpoint.query` moved to `DataSourcesEndpoint.query`

3. **`1efa7ba9` - feat(obj_api): Add DataSource class and DataSourcesEndpoint for API 2025-09-03**

   **Changes to `obj_api/blocks.py`:**
   - Added `DataSource` class (formerly Database functionality) with `object='data_source'`
   - Added `database_id` field to DataSource for parent reference
   - Updated `Database` class to container concept with `data_sources` list
   - Added `ChildDataSource` and `ChildDataSourceTypeData` block types
   - Updated imports for `DataSourceRef` and `MentionDataSource`

   **Changes to `obj_api/objects.py`:**
   - Added `DataSourceRef` class with `data_source_id` field and `build()` method
   - Added `MentionDataSource` class with `build_mention_from()` method
   - Updated TYPE_CHECKING import to include `DataSource`
   - Updated docstrings for `DatabaseRef` and `MentionDatabase`

   **Changes to `obj_api/schema.py`:**
   - Updated `PropertyRelation` to use `data_source_id` as primary key (was `database_id`)
   - Made `database_id` optional with `UnsetType`
   - Updated `SinglePropertyRelation.build_relation()` to use `dsref` parameter
   - Updated `DualPropertyRelation.build_relation()` to use `dsref` parameter
   - Updated docstrings to reference "data source" instead of "database"

   **Changes to `obj_api/endpoints.py`:**
   - Added `DataSourcesEndpoint` class with full CRUD operations:
     - `create()`, `retrieve()`, `update()`, `delete()`, `restore()`, `query()`
   - Updated `DatabasesEndpoint`:
     - Removed `schema` parameter from `create()` and `update()` (moved to DataSource)
     - Removed `query()` method (moved to DataSourcesEndpoint)
     - Removed `delete()` and `restore()` methods
     - Updated docstrings to reflect container concept
   - Updated `PagesEndpoint.create()` to accept `DataSource` instead of `Database`
   - Added `NCDataSourcesEndpoint` TYPE_CHECKING import
   - Updated `NotionAPI.__init__` to include `data_sources` endpoint

   **Changes to `obj_api/query.py`:**
   - Renamed `DBQueryBuilder` → `DataSourceQueryBuilder`
   - Renamed `DBQuery` → `DataSourceQuery`
   - Renamed `DBSort` → `DataSourceSort`
   - Updated `SearchQueryBuilder.filter()` parameter from `db_only` to `datasource_only`
   - Updated search filter value from `'database'` to `'data_source'`
   - Updated `DataSourceQueryBuilder` to use `data_source_id` parameter
   - Updated TypeVar bound from `Page | Database` to `Page | DataSource`

#### Current State

- **Low-level obj_api layer**: Complete
- **High-level API layer**: Not started (25 mypy errors expected)
- **Tests**: Not updated
- **Documentation**: Not updated

#### Mypy Errors (Expected)

All 25 errors are in the high-level API layer, which still references the old Database concept:
- `session.py`: 4 errors (uses old `DatabasesEndpoint` methods)
- `schema.py`: 8 errors (references `Database.properties`, old endpoint methods)
- `query.py`: 4 errors (references `DBSort`, `databases.query`)
- `database.py`: 4 errors (references old endpoint methods)
- `tests/obj_api/test_endpoints.py`: 2 errors (passes `Database` to `pages.create`)
- `utils.py`: 1 error (unrelated pendulum issue)

#### Next Steps

Phase 3 (High-level API) should:
1. Rename `database.py` to `datasource.py`
2. Update `Database` class to `DataSource` in high-level API
3. Update `session.py` methods (`get_db` → `get_datasource`, etc.)
4. Update `schema.py` bindings to use DataSource
5. Update `query.py` high-level Query class
