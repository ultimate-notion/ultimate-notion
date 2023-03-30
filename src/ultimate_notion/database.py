"""Database object"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from notional import blocks, types
from notional.schema import PropertyObject

from .page import Page
from .record import Record
from .view import View

if TYPE_CHECKING:
    from .session import Session


class Database(Record):
    def __init__(self, obj_ref: blocks.Database, session: Session):
        self.obj_ref: blocks.Database = obj_ref
        self.session = session

    def __str__(self) -> str:
        cls_name = self.__class__.__name__
        return f"{cls_name}: '{self.title}'"

    def __repr__(self) -> str:
        return f"<{str(self)} at {hex(id(self))}>"

    @property
    def title(self) -> str:
        """Return the title of this database as plain text."""
        return self.obj_ref.Title

    @property
    def description(self) -> Optional[List[types.RichTextObject]]:
        return self.obj_ref.description

    @property
    def icon(self) -> Optional[Union[types.FileObject, types.EmojiObject]]:
        return self.obj_ref.icon

    @property
    def cover(self) -> Optional[types.FileObject]:
        return self.obj_ref.cover

    @property
    def meta_properties(self) -> Dict[str, Any]:
        return super().to_dict()

    @property
    def properties(self) -> Dict[str, PropertyObject]:
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

    def view(self, live=True) -> View:
        session = self.session if live else None
        pages = [Page(page_obj, session) for page_obj in self.session.notional.databases.query(self.id).execute()]
        return View(database=self, pages=pages)

    # ToDo: Implement this and return view.
    # def query(
    #     self,
    #     *,
    #     db_id: Optional[str] = None,
    #     db_name: Optional[str] = None,
    #     live_updates=True,
    # ) -> QueryBuilder:
    #     db_obj = self.get_db(db_id=db_id, db_name=db_name)
    #
    #     if live_updates:
    #         cpage = connected_page(session=self, source_db=db_obj)
    #         return cpage.query()
    #     else:
    #         return self.databases.query(db_id)
