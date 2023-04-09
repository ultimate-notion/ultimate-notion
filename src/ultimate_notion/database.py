"""Database object"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from notional import blocks, types
from notional.schema import PropertyObject

from ultimate_notion.page import Page
from ultimate_notion.query import QueryBuilder
from ultimate_notion.record import Record
from ultimate_notion.view import View

if TYPE_CHECKING:
    from ultimate_notion.session import Session


class Database(Record):
    def __init__(self, db_ref: blocks.Database, session: Session):
        self.obj_ref: blocks.Database = db_ref
        self.session: Session = session

    def __str__(self):
        return self.title

    def __repr__(self) -> str:
        cls_name = self.__class__.__name__
        return f"<{cls_name}: '{str(self)}' at {hex(id(self))}>"

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
    def meta_properties(self) -> dict[str, Any]:
        return super().to_dict()

    @property
    def schema(self) -> dict[str, PropertyObject]:
        # ToDo: Wrap these properties in our schema props from `.schema` to avoid confusion
        return self.obj_ref.properties

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

    def view(self, *, live_update: bool = True) -> View:
        query = self.session.notional.databases.query(self.id)
        pages = [Page(page_obj, self.session, live_update=live_update) for page_obj in query.execute()]
        return View(database=self, pages=pages, query=query, live_update=live_update)

    def create_page(self):
        raise NotImplementedError

    def query(self) -> QueryBuilder:
        """Query a (large) database for pages in a more specific way"""
        return QueryBuilder(self)
