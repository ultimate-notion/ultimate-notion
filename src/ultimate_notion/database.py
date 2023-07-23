"""Database object"""
from __future__ import annotations

from copy import deepcopy

from ultimate_notion.obj_api import blocks, types
from ultimate_notion.obj_api.text import make_safe_python_name
from ultimate_notion.page import Page
from ultimate_notion.query import QueryBuilder
from ultimate_notion.record import Record
from ultimate_notion.schema import PageSchema, Property, PropertyType, SchemaError
from ultimate_notion.utils import decapitalize
from ultimate_notion.view import View


class Database(Record):
    """A Notion database object, not a linked databases

    If a custom schema is provided, i.e. specified during creating are the `schema` was set
    then the schemy is verified.

    https://developers.notion.com/docs/working-with-databases
    """

    obj_ref: blocks.Database
    _schema: PageSchema | None = None

    def __init__(self, obj_ref: blocks.Database):
        super().__init__(obj_ref)

    def __str__(self):
        if self.title:
            return self.title
        else:
            return 'Untitled'

    def __repr__(self) -> str:
        cls_name = self.__class__.__name__
        return f"<{cls_name}: '{self!s}' at {hex(id(self))}>"

    def reload(self, *, check_consistency: bool = False):
        """Reload the metadata of the database and update the schema if necessary"""
        new_db = self.session._get_db(self.id)  # circumvent session cache
        if check_consistency and not self.schema.is_consistent_with(new_db.schema):
            msg = f"Schema of database {self.title} no longer consistent with schema after refresh!"
            raise SchemaError(msg)

        self.schema._enrich(new_db.schema)
        # self.obj_ref = new_db.obj_ref

    @property
    def title(self) -> str:
        """Return the title of this database as plain text."""
        return self.obj_ref.Title

    @property
    def description(self) -> list[types.RichTextObject] | None:
        return self.obj_ref.description

    @property
    def icon(self) -> types.FileObject | types.EmojiObject | None:
        return self.obj_ref.icon

    @property
    def cover(self) -> types.FileObject | None:
        return self.obj_ref.cover

    def _reflect_schema(self, obj_ref: blocks.Database) -> PageSchema:
        """Reflection about the database schema"""
        cls_name = f'{make_safe_python_name(self.title).capitalize()}Schema'
        attrs = {
            decapitalize(make_safe_python_name(k)): Property(k, PropertyType.wrap_obj_ref(v))
            for k, v in obj_ref.properties.items()
        }
        schema = type(cls_name, (PageSchema,), attrs, db_title=self.title)
        schema.bind_db(self)
        schema.custom_schema = False
        return schema()

    @property
    def schema(self) -> PageSchema:
        if not self._schema:
            self._schema = self._reflect_schema(self.obj_ref)
        return self._schema

    @schema.setter
    def schema(self, schema: PageSchema | type[PageSchema]):
        """Set a custom schema in order to change the Python variables names"""
        if isinstance(schema, type):
            schema = schema()

        if self.schema.is_consistent_with(schema):
            schema.bind_db(self)
            self._schema = schema
        else:
            msg = 'Provided schema is not consistent with the current schema of the database!'
            raise SchemaError(msg)

    @property
    def url(self) -> str:
        return self.obj_ref.url

    @property
    def archived(self) -> bool:
        return self.obj_ref.archived

    @property
    def is_inline(self) -> bool:
        return self.obj_ref.is_inline

    def delete(self):
        """Delete this database"""
        self.session.api.blocks.delete(self.id)

    def _pages_from_query(self, *, query, live_update: bool = True) -> list[Page]:
        pages = [Page(page_obj) for page_obj in query.execute()]
        for page in pages:
            page.live_update = live_update
        return pages

    def view(self, *, live_update: bool = True) -> View:
        query = self.session.api.databases.query(self.id)  # ToDo: use self.query when implemented
        pages = self._pages_from_query(query=query, live_update=live_update)
        return View(database=self, pages=pages, query=query, live_update=live_update)

    def create_page(self, *, live_update: bool = True):
        """Return page object"""
        # ToDo: Use Schema for this.
        raise NotImplementedError

    def query(self) -> QueryBuilder:
        """Query a (large) database for pages in a more specific way"""
        return QueryBuilder(self)
