"""Functionality for working with Notion databases and data sources.

In API version 2025-09-03+:
- DataSource: Contains schema (properties) and pages (formerly 'database')
- Database: Container that can hold multiple data sources (new concept)
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError
from typing_extensions import Self

from ultimate_notion.blocks import ChildrenMixin, DataObject, wrap_icon
from ultimate_notion.core import get_active_session, get_repr
from ultimate_notion.emoji import CustomEmoji, Emoji
from ultimate_notion.errors import ReadOnlyPropertyError, SchemaError
from ultimate_notion.file import AnyFile
from ultimate_notion.obj_api import blocks as obj_blocks
from ultimate_notion.obj_api.core import raise_unset
from ultimate_notion.page import Page
from ultimate_notion.query import Query
from ultimate_notion.rich_text import Text, camel_case
from ultimate_notion.schema import Property, Schema
from ultimate_notion.view import View


class DataSource(DataObject[obj_blocks.DataSource], wraps=obj_blocks.DataSource):
    """A Notion data source (formerly 'database' in pre-2025-09-03 API).

    A data source contains the schema (properties) and pages. This object always
    represents an original data source, not a linked one.

    API reference: https://developers.notion.com/docs/working-with-databases
    """

    _schema: type[Schema] | None = None

    def __str__(self) -> str:
        if self.title:
            return str(self.title)
        else:
            return 'Untitled'

    def _repr_html_(self) -> str:  # noqa: PLW3201
        """Called by JupyterLab automatically"""
        return str(self)

    def __repr__(self) -> str:
        return get_repr(self)

    @property
    def url(self) -> str:
        """Return the URL of this data source."""
        return raise_unset(self.obj_ref.url)

    @property
    def title(self) -> str | Text | None:
        """Return the title of this data source as rich text."""
        # `str` added as return value but always RichText returned, which inherits from str.
        if title := raise_unset(self.obj_ref.title):
            return Text.wrap_obj_ref(title)
        return None

    @title.setter
    def title(self, text: str | Text | None) -> None:
        """Set the title of this data source."""
        if text is None:
            text = ''
        if not isinstance(text, Text):
            text = Text.from_plain_text(text)
        session = get_active_session()
        session.api.data_sources.update(self.obj_ref, title=text.obj_ref)

    @property
    def description(self) -> Text | None:
        """Return the description of this data source as rich text."""
        if desc := raise_unset(self.obj_ref.description):
            return Text.wrap_obj_ref(desc)
        return None

    @description.setter
    def description(self, text: str | Text | None) -> None:
        """Set the description of this data source."""
        if text is None:
            text = ''
        if not isinstance(text, Text):
            text = Text.from_plain_text(text)
        session = get_active_session()
        session.api.data_sources.update(self.obj_ref, description=text.obj_ref)

    @property
    def icon(self) -> AnyFile | Emoji | CustomEmoji | None:
        """Return the icon of this data source as file or emoji."""
        if (icon := self.obj_ref.icon) is None:
            return None
        else:
            return wrap_icon(icon)

    @property
    def cover(self) -> AnyFile | None:
        """Return the cover of this data source as file."""
        cover = self.obj_ref.cover
        return AnyFile.wrap_obj_ref(cover) if cover is not None else None

    @property
    def is_wiki(self) -> bool:
        """Return whether the data source is a wiki."""
        # ToDo: Implement using the verification property
        raise NotImplementedError

    @property
    def is_ds(self) -> bool:
        """Return whether the object is a data source."""
        return True

    def _reflect_schema(self, obj_ref: obj_blocks.DataSource) -> type[Schema]:
        """Reflection about the data source schema."""
        title = str(self)
        cls_name = f'{camel_case(title)}Schema'
        attrs = {'_props': [Property.wrap_obj_ref(v) for v in obj_ref.properties.values()]}
        schema: type[Schema] = type(cls_name, (Schema,), attrs, db_title=title)
        schema._bind_ds(self)
        return schema

    def _set_schema(self, schema: type[Schema], *, during_init: bool) -> None:
        """Set a custom schema in order to change the Python variables names."""
        self.schema.assert_consistency_with(schema, during_init=during_init)
        schema._bind_ds(self)
        self._schema = schema

    @property
    def schema(self) -> type[Schema]:
        """Schema of the data source."""
        if not self._schema:
            self._schema = self._reflect_schema(self.obj_ref)
        return self._schema

    @schema.setter
    def schema(self, schema: type[Schema]) -> None:
        """Set a custom schema in order to change the Python variables names."""
        self._set_schema(schema, during_init=False)

    @property
    def is_inline(self) -> bool:
        """Return whether the data source is inline."""
        return self.obj_ref.is_inline

    @is_inline.setter
    def is_inline(self, inline: bool) -> None:
        """Set whether the data source is inline."""
        if self.is_inline != inline:
            session = get_active_session()
            session.api.data_sources.update(self.obj_ref, inline=inline)
            self.obj_ref.is_inline = inline

    def delete(self) -> Self:
        """Delete this data source."""
        if not self.is_deleted:
            session = get_active_session()
            session.api.data_sources.delete(self.obj_ref)
            self._delete_me_from_parent()
        return self

    def restore(self) -> Self:
        """Restore this data source."""
        if self.is_deleted:
            session = get_active_session()
            session.api.data_sources.restore(self.obj_ref)
            if isinstance(self.parent, ChildrenMixin):
                self.parent._children = None  # this forces a new retrieval of children next time
        return self

    def reload(self, *, rebind_schema: bool = True) -> Self:
        """Reload this data source.

        If `rebind_schema` is `True`, the schema will be rebound to the current data source.
        Otherwise, the schema will set to the reflected schema of the current data source.
        """
        old_schema = self.schema
        session = get_active_session()
        self.obj_ref = session.api.data_sources.retrieve(self.id)
        self._schema = None  # reset schema to reflect the current data source
        self.schema._set_obj_refs()
        if rebind_schema:
            self.schema = old_schema
        return self

    @property
    def query(self) -> Query:
        """Return a Query object to build and execute a data source query."""
        return Query(ds=self)

    def get_all_pages(self) -> View:
        """Retrieve all pages and return a view."""
        return self.query.execute()

    def __len__(self) -> int:
        """Return the number of pages in this data source."""
        return len(self.get_all_pages())

    @property
    def is_empty(self) -> bool:
        """Return whether the data source is empty."""
        return len(self) == 0

    def __bool__(self) -> bool:
        """Overwrite default behaviour."""
        msg = 'Use .is_empty instead of bool(ds) to check if a data source is empty.'
        raise RuntimeError(msg)

    def create_page(self, **kwargs: Any) -> Page:
        """Create a page with properties according to the schema within the corresponding data source."""
        attr_to_name = {prop.attr_name: prop.name for prop in self.schema.get_props()}
        if not set(kwargs).issubset(set(attr_to_name)):
            add_kwargs = set(kwargs) - set(attr_to_name)
            msg = f'Attributes {", ".join(add_kwargs)} not defined for properties in schema {self.__class__.__name__}'
            raise SchemaError(msg)
        if ro_props := set(kwargs) & {prop.attr_name for prop in self.schema.get_ro_props()}:
            msg = f'Read-only properties {", ".join(ro_props)} cannot be set'
            raise ReadOnlyPropertyError(msg)

        schema_kwargs = {attr_to_name[attr]: value for attr, value in kwargs.items()}
        validator = self.schema.to_pydantic_model(with_ro_props=False)
        try:
            schema = validator(**schema_kwargs)
        except ValidationError as e:
            msg = f'Invalid keyword arguments or read-only properties are overwritten:\n{e}'
            raise SchemaError(msg) from e

        session = get_active_session()
        page_obj = session.api.pages.create(parent=self.obj_ref, properties=schema.to_dict())
        page = Page.wrap_obj_ref(page_obj)
        session.cache[page.id] = page
        return page

    def to_markdown(self) -> str:
        """Return the reference to this data source as Markdown."""
        return self._to_markdown()

    def _to_markdown(self) -> str:
        """Return the reference to this data source as Markdown."""
        return f'[**🗄️ {self.title}**]({self.block_url})\n'


class Database(DataObject[obj_blocks.Database], wraps=obj_blocks.Database):
    """A Notion database - a collection that can contain multiple data sources.

    This is a NEW concept introduced in API version 2025-09-03. A database acts as
    a container or grouping mechanism for related data sources.

    Note: This class is currently a placeholder for future implementation.
    The Notion API 2025-09-03 introduces this concept, but full support requires
    additional implementation work.
    """

    def __str__(self) -> str:
        if self.title:
            return str(self.title)
        else:
            return 'Untitled Database'

    def __repr__(self) -> str:
        return get_repr(self)

    @property
    def title(self) -> str | Text | None:
        """Return the title of this database as rich text."""
        if title := raise_unset(self.obj_ref.title):
            return Text.wrap_obj_ref(title)
        return None

    @title.setter
    def title(self, text: str | Text | None) -> None:
        """Set the title of this database."""
        if text is None:
            text = ''
        if not isinstance(text, Text):
            text = Text.from_plain_text(text)
        session = get_active_session()
        session.api.databases.update(self.obj_ref, title=text.obj_ref)

    @property
    def is_db(self) -> bool:
        """Check if this is a database (always True for Database objects)."""
        return True

    @property
    def data_sources(self) -> list[DataSource]:
        """Return all data sources in this database.

        Note: This is a placeholder implementation. Full support requires additional work.
        """
        # TODO: Implement fetching data sources from this database
        # This would involve querying the data_sources endpoint with a filter for database_id
        msg = 'Database.data_sources is not yet implemented'
        raise NotImplementedError(msg)

    def __eq__(self, other: object) -> bool:
        """Compare Database objects."""
        if isinstance(other, Database):
            return self.id == other.id
        return False

    def __hash__(self) -> int:
        """Hash the Database object."""
        return hash(self.id)
