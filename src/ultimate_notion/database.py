"""Functionality for working with Notion databases"""

from __future__ import annotations

from textwrap import dedent
from typing import cast

from ultimate_notion.blocks import DataObject
from ultimate_notion.obj_api import blocks as obj_blocks
from ultimate_notion.obj_api import objects as objs
from ultimate_notion.objects import File, RichText
from ultimate_notion.page import Page
from ultimate_notion.query import QueryBuilder
from ultimate_notion.schema import Column, PageSchema, PropertyType, PropertyValue, ReadOnlyColumnError, SchemaError
from ultimate_notion.text import camel_case, snake_case
from ultimate_notion.utils import dict_diff_str, get_active_session, get_repr
from ultimate_notion.view import View


class Database(DataObject[obj_blocks.Database], wraps=obj_blocks.Database):
    """A Notion database

    This object always represents an original database, not a linked database.
    API reference: https://developers.notion.com/docs/working-with-databases
    """

    _schema: type[PageSchema] | None = None

    def __str__(self):
        if self.title:
            return str(self.title)
        else:
            return 'Untitled'

    def _repr_html_(self) -> str:  # noqa: PLW3201
        """Called by Jupyter Lab automatically"""
        return str(self)

    def __repr__(self) -> str:
        return get_repr(self)

    @property
    def title(self) -> RichText:
        """Return the title of this database as rich text."""
        title = self.obj_ref.title
        return RichText.wrap_obj_ref(title)

    @title.setter
    def title(self, text: str | RichText):
        """Set the title of this database"""
        if not isinstance(text, RichText):
            text = RichText.from_plain_text(text)
        session = get_active_session()
        session.api.databases.update(self.obj_ref, title=text.obj_ref)

    @property
    def description(self) -> RichText:
        """Return the description of this database as rich text."""
        desc = self.obj_ref.description
        return RichText.wrap_obj_ref(desc)

    @description.setter
    def description(self, text: str | RichText):
        """Set the description of this database"""
        if not isinstance(text, RichText):
            text = RichText.from_plain_text(text)
        session = get_active_session()
        session.api.databases.update(self.obj_ref, description=text.obj_ref)

    @property
    def icon(self) -> File | str | None:
        icon = self.obj_ref.icon
        if isinstance(icon, objs.FileObject):
            return File.wrap_obj_ref(icon)
        elif isinstance(icon, objs.EmojiObject):
            return icon.emoji
        else:
            return None

    @property
    def cover(self) -> File | None:
        cover = self.obj_ref.cover
        return File.wrap_obj_ref(cover) if cover is not None else None

    @property
    def is_wiki(self) -> bool:
        """Is this database a wiki database"""
        # ToDo: Implement using the verification property
        raise NotImplementedError

    def _reflect_schema(self, obj_ref: obj_blocks.Database) -> type[PageSchema]:
        """Reflection about the database schema"""
        title = str(self)
        cls_name = f'{camel_case(title)}Schema'
        attrs = {
            snake_case(k): Column(k, cast(PropertyType, PropertyType.wrap_obj_ref(v)))
            for k, v in obj_ref.properties.items()
        }
        schema: type[PageSchema] = type(cls_name, (PageSchema,), attrs, db_title=title)
        schema.bind_db(self)
        return schema

    @property
    def schema(self) -> type[PageSchema]:
        """Schema of the database"""
        if not self._schema:
            self._schema = self._reflect_schema(self.obj_ref)
        return self._schema

    @schema.setter
    def schema(self, schema: type[PageSchema]):
        """Set a custom schema in order to change the Python variables names"""
        if self.schema.is_consistent_with(schema):
            schema.bind_db(self)
            self._schema = schema
        else:
            cols_added, cols_removed, cols_changed = dict_diff_str(self.schema.to_dict(), schema.to_dict())
            msg = f"""Provided schema is not consistent with the current schema of the database:
                      Columns added: {cols_added}
                      Columns removed: {cols_removed}
                      Columns changed: {cols_changed}
                   """
            raise SchemaError(dedent(msg))

    @property
    def url(self) -> str:
        return self.obj_ref.url

    @property
    def is_inline(self) -> bool:
        return self.obj_ref.is_inline

    def delete(self) -> Database:
        """Delete/archive this database"""
        if not self.is_archived:
            session = get_active_session()
            session.api.databases.delete(self.obj_ref)
        return self

    def restore(self) -> Database:
        """Restore/unarchive this database"""
        if self.is_archived:
            session = get_active_session()
            session.api.databases.restore(self.obj_ref)
        return self

    def reload(self) -> Database:
        """Reload this database"""
        session = get_active_session()
        self.obj_ref = session.api.databases.retrieve(self.obj_ref.id)
        return self

    @staticmethod
    def _pages_from_query(query) -> list[Page]:
        # ToDo: Remove when self.query is implemented!
        return [Page.wrap_obj_ref(page_obj) for page_obj in query.execute()]

    def fetch_all(self) -> View:
        """Fetch all pages and return a view"""
        # ToDo: Decide on also caching the view? or at least the pages within the view?
        session = get_active_session()
        query = session.api.databases.query(self.id)  # ToDo: use self.query when implemented
        pages = [Page.wrap_obj_ref(page_obj) for page_obj in query.execute()]
        return View(database=self, pages=pages, query=query)

    def create_page(self, **kwargs) -> Page:
        """Create a page with properties according to the schema within the corresponding database"""
        schema_kwargs = {col.attr_name: col for col in self.schema.get_cols()}
        if not set(kwargs).issubset(set(schema_kwargs)):
            add_kwargs = set(kwargs) - set(schema_kwargs)
            msg = f"kwargs {', '.join(add_kwargs)} not defined in schema"
            raise SchemaError(msg)

        schema_dct = {}
        for kwarg, value in kwargs.items():
            col = schema_kwargs[kwarg]
            prop_value_cls = col.type.prop_value  # map schema to page property
            # ToDo: Check at that point in case of selectoption if the option is already defined in Schema!

            if prop_value_cls.readonly:
                raise ReadOnlyColumnError(col)

            prop_value = value if isinstance(value, PropertyValue) else prop_value_cls(value)

            schema_dct[schema_kwargs[kwarg].name] = prop_value.obj_ref

        session = get_active_session()
        page = Page.wrap_obj_ref(session.api.pages.create(parent=self.obj_ref, properties=schema_dct))
        return page

    def query(self) -> QueryBuilder:
        """Query a (large) database for pages in a more specific way"""
        return QueryBuilder(self)
