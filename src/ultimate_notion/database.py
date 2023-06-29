"""Database object"""
from __future__ import annotations

from copy import deepcopy

from notional import blocks, types
from notional.text import make_safe_python_name

from ultimate_notion.page import Page
from ultimate_notion.query import QueryBuilder
from ultimate_notion.record import Record
from ultimate_notion.schema import PageSchema, Property, PropertyType, SchemaError
from ultimate_notion.utils import decapitalize
from ultimate_notion.view import View


class Database(Record):
    obj_ref: blocks.Database
    _schema: type[PageSchema] | None = None

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

    def reflect_schema(self) -> type[PageSchema]:
        """Reflection about the database schema"""
        cls_name = f'{make_safe_python_name(self.title).capitalize()}Schema'

        def clear(prop_obj):
            """Clear PropertyObject from any residues coming from the reflection"""
            prop_obj = deepcopy(prop_obj)
            prop_obj.name = None
            prop_obj.id = None
            return prop_obj

        attrs = {
            decapitalize(make_safe_python_name(k)): Property(k, PropertyType.wrap_obj_ref(clear(v)))
            for k, v in self.obj_ref.properties.items()
        }
        return type(cls_name, (PageSchema,), attrs)

    @property
    def schema(self) -> type[PageSchema]:
        if not self._schema:
            self._schema = self.reflect_schema()
        return self._schema

    @schema.setter
    def schema(self, schema: type[PageSchema]):
        """Set a custom schema in order to change the Python variables names"""
        if schema() == self.reflect_schema()():
            self._schema = schema
        else:
            msg = 'Provided schema is not consistent with schema of the database!'
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
        self.session.delete_db(self)

    def _pages_from_query(self, *, query, live_update: bool = True) -> list[Page]:
        pages = [Page(page_obj) for page_obj in query.execute()]
        for page in pages:
            page.live_update = live_update
        return pages

    def view(self, *, live_update: bool = True) -> View:
        query = self.session.notional.databases.query(self.id)  # ToDo: use self.query when implemented
        pages = self._pages_from_query(query=query, live_update=live_update)
        return View(database=self, pages=pages, query=query, live_update=live_update)

    def create_page(self, *, live_update: bool = True):
        """Return page object"""
        # ToDo: Use Schema for this.
        raise NotImplementedError

    def query(self) -> QueryBuilder:
        """Query a (large) database for pages in a more specific way"""
        return QueryBuilder(self)
