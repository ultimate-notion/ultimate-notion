"""Database object"""
from __future__ import annotations

from notional import blocks, types
from notional.schema import PropertyObject

from ultimate_notion.page import Page
from ultimate_notion.query import QueryBuilder
from ultimate_notion.record import Record
from ultimate_notion.view import View


class Database(Record):
    obj_ref: blocks.Database

    def __init__(self, obj_ref: blocks.Database):
        super().__init__(obj_ref)

    def __str__(self):
        return self.title

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

    @property
    def schema(self) -> dict[str, PropertyObject]:
        # ToDo: Wrap these properties in our schema props from `.schema` to avoid confusion
        return self.obj_ref.properties

    # ToDo: Have a setter method for schema too?

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
        query = self.session.notional.databases.query(self.id)
        pages = self._pages_from_query(query=query, live_update=live_update)
        return View(database=self, pages=pages, query=query, live_update=live_update)

    def create_page(self, *, live_update: bool = True):
        """Return page object"""
        # ToDo: Use Schema for this.
        raise NotImplementedError

    def query(self) -> QueryBuilder:
        """Query a (large) database for pages in a more specific way"""
        return QueryBuilder(self)
