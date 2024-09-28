"""Functionality for working with Notion databases."""

from __future__ import annotations

from textwrap import dedent
from typing import cast

from pydantic import BaseModel
from typing_extensions import Self

from ultimate_notion.blocks import ChildrenMixin, DataObject
from ultimate_notion.core import get_active_session, get_repr
from ultimate_notion.file import Emoji, FileInfo
from ultimate_notion.obj_api import blocks as obj_blocks
from ultimate_notion.obj_api import objects as objs
from ultimate_notion.obj_api.query import DBQueryBuilder
from ultimate_notion.page import Page
from ultimate_notion.rich_text import Text, camel_case, snake_case
from ultimate_notion.schema import Property, PropertyType, PropertyValue, ReadOnlyPropertyError, Schema, SchemaError
from ultimate_notion.utils import dict_diff_str
from ultimate_notion.view import View


class Database(DataObject[obj_blocks.Database], wraps=obj_blocks.Database):
    """A Notion database.

    This object always represents an original database, not a linked database.

    API reference: https://developers.notion.com/docs/working-with-databases
    """

    _schema: type[Schema] | None = None

    def __str__(self):
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
        """Return the URL of this database."""
        return self.obj_ref.url

    @property
    def title(self) -> str | Text:
        """Return the title of this database as rich text."""
        title = self.obj_ref.title
        # `str` added as return value but always RichText returned, which inherits from str.
        return Text.wrap_obj_ref(title)

    @title.setter
    def title(self, text: str | Text):
        """Set the title of this database"""
        if not isinstance(text, Text):
            text = Text.from_plain_text(text)
        session = get_active_session()
        session.api.databases.update(self.obj_ref, title=text.obj_ref)

    @property
    def description(self) -> Text:
        """Return the description of this database as rich text."""
        desc = self.obj_ref.description
        return Text.wrap_obj_ref(desc)

    @description.setter
    def description(self, text: str | Text):
        """Set the description of this database."""
        if not isinstance(text, Text):
            text = Text.from_plain_text(text)
        session = get_active_session()
        session.api.databases.update(self.obj_ref, description=text.obj_ref)

    @property
    def icon(self) -> FileInfo | Emoji | None:
        """Return the icon of this database as file or emoji."""
        icon = self.obj_ref.icon
        if isinstance(icon, objs.FileObject):
            return FileInfo.wrap_obj_ref(icon)
        elif isinstance(icon, objs.EmojiObject):
            return Emoji.wrap_obj_ref(icon)
        elif icon is None:
            return None
        else:
            msg = f'unknown icon object of {type(icon)}'
            raise RuntimeError(msg)

    @property
    def cover(self) -> FileInfo | None:
        """Return the cover of this database as file."""
        cover = self.obj_ref.cover
        return FileInfo.wrap_obj_ref(cover) if cover is not None else None

    @property
    def is_wiki(self) -> bool:
        """Return whether the database is a wiki."""
        # ToDo: Implement using the verification property
        raise NotImplementedError

    @property
    def is_db(self) -> bool:
        """Return whether the object is a database."""
        return True

    def _reflect_schema(self, obj_ref: obj_blocks.Database) -> type[Schema]:
        """Reflection about the database schema."""
        title = str(self)
        cls_name = f'{camel_case(title)}Schema'
        attrs = {
            snake_case(k): Property(k, cast(PropertyType, PropertyType.wrap_obj_ref(v)))
            for k, v in obj_ref.properties.items()
        }
        schema: type[Schema] = type(cls_name, (Schema,), attrs, db_title=title)
        schema.bind_db(self)
        return schema

    @property
    def schema(self) -> type[Schema]:
        """Schema of the database."""
        if not self._schema:
            self._schema = self._reflect_schema(self.obj_ref)
        return self._schema

    @schema.setter
    def schema(self, schema: type[Schema]):
        """Set a custom schema in order to change the Python variables names."""
        if self.schema.is_consistent_with(schema):
            schema.bind_db(self)
            self._schema = schema
        else:
            props_added, props_removed, props_changed = dict_diff_str(self.schema.to_dict(), schema.to_dict())
            msg = f"""Provided schema is not consistent with the current schema of the database:
                      Properties added: {props_added}
                      Properties removed: {props_removed}
                      Properties changed: {props_changed}
                   """
            raise SchemaError(dedent(msg))

    @property
    def is_inline(self) -> bool:
        """Return whether the database is inline."""
        return self.obj_ref.is_inline

    def delete(self) -> Self:
        """Delete this database."""
        if not self.is_deleted:
            session = get_active_session()
            session.api.databases.delete(self.obj_ref)
            self._delete_me_from_parent()
        return self

    def restore(self) -> Self:
        """Restore this database."""
        if self.is_deleted:
            session = get_active_session()
            session.api.databases.restore(self.obj_ref)
            if isinstance(self.parent, ChildrenMixin):
                self.parent._children = None  # this forces a new retrieval of children next time
        return self

    def reload(self) -> Self:
        """Reload this database."""
        session = get_active_session()
        self.obj_ref = session.api.databases.retrieve(self.obj_ref.id)
        self.schema._set_obj_refs()
        return self

    @staticmethod
    def _pages_from_query(query: DBQueryBuilder) -> list[Page]:
        # ToDo: Remove when self.query is implemented!
        cache = get_active_session().cache
        pages = []
        for page_obj in query.execute():
            if page_obj.id in cache:
                page = cast(Page, cache[page_obj.id])
                page.obj_ref = page_obj  # updates the page content
            else:
                page = Page.wrap_obj_ref(page_obj)
            pages.append(page)
        return pages

    def fetch_all(self) -> View:
        """Fetch all pages and return a view."""
        session = get_active_session()
        query = session.api.databases.query(self.obj_ref)  # ToDo: use self.query when implemented
        return View(database=self, pages=self._pages_from_query(query), query=query)

    def __len__(self) -> int:
        """Return the number of pages in this database."""
        return len(self.fetch_all())

    @property
    def is_empty(self) -> bool:
        """Return whether the database is empty."""
        return len(self) == 0

    def __bool__(self) -> bool:
        """Overwrite default behaviour."""
        msg = 'Use .is_empty instead of bool(db) to check if a database is empty.'
        raise RuntimeError(msg)

    def pydantic_model(self) -> BaseModel:
        """Return a Pydantic model for this database."""
        # Check https://github.com/ultimate-notion/ultimate-notion/issues/32 for details
        raise NotImplementedError

    def create_page(self, **kwargs) -> Page:
        """Create a page with properties according to the schema within the corresponding database."""

        # ToDo: let pydantic_model check the kwargs and raise an error if something is wrong
        schema_kwargs = {prop.attr_name: prop for prop in self.schema.get_props()}
        if not set(kwargs).issubset(set(schema_kwargs)):
            add_kwargs = set(kwargs) - set(schema_kwargs)
            msg = f"kwargs {', '.join(add_kwargs)} not defined in schema"
            raise SchemaError(msg)

        schema_dct = {}
        for kwarg, value in kwargs.items():
            prop = schema_kwargs[kwarg]
            prop_value_cls = prop.type.prop_value  # map schema to page property
            # ToDo: Check at that point in case of selectoption if the option is already defined in Schema!

            if prop_value_cls.readonly:
                raise ReadOnlyPropertyError(prop)

            prop_value = value if isinstance(value, PropertyValue) else prop_value_cls(value)

            schema_dct[schema_kwargs[kwarg].name] = prop_value.obj_ref

        session = get_active_session()
        page = Page.wrap_obj_ref(session.api.pages.create(parent=self.obj_ref, properties=schema_dct))
        return page

    def query(self):
        """Query a (large) database for pages in a more specific way."""
        raise NotImplementedError

    def to_markdown(self) -> str:
        """Return the content of this database as Markdown."""
        raise NotImplementedError

    def _to_markdown(self) -> str:
        """Return the reference to this database as Markdown."""
        return f'[**🗄️ {self.title}**]({self.block_url})\n'
