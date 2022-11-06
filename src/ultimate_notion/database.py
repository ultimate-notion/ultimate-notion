"""Database object"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Dict, List, Optional, Union
from uuid import UUID

import pandas as pd

from .core import records
from .core.records import ParentRef
from .core.schema import PropertyObject
from .core.text import plain_text
from .core.types import EmojiObject, FileObject, RichTextObject

if TYPE_CHECKING:
    from .session import NotionSession


class Database:
    def __init__(self, db_obj: records.Database, session: NotionSession):
        self.db_obj = db_obj
        self.session = session

    @property
    def id(self) -> UUID:
        return self.db_obj.id

    @property
    def created_time(self) -> datetime:
        return self.db_obj.created_time

    # ToDo: Add this
    # @property
    # def created_by(self):
    #     return self.db_obj.created_by

    @property
    def last_edited_time(self) -> datetime:
        return self.db_obj.last_edited_time

    # ToDo: Add this
    # @property
    # def last_edited_by(self):
    #     return self.db_obj.last_edited_by

    @property
    def title(self) -> str:
        """Return the title of this database as plain text."""
        if self.db_obj.title is None or len(self.db_obj.title) == 0:
            return None

        return plain_text(*self.db_obj.title)

    @property
    def description(self) -> Optional[List[RichTextObject]]:
        return self.db_obj.description

    @property
    def icon(self) -> Optional[Union[FileObject, EmojiObject]]:
        return self.db_obj.icon

    @property
    def cover(self) -> Optional[FileObject]:
        return self.db_obj.cover

    @property
    def properties(self) -> Dict[str, PropertyObject]:
        return self.db_obj.properties

    @property
    def parent(self) -> ParentRef:
        # ToDo: Resolve page when calling?
        return self.db_obj.parent

    @property
    def url(self) -> str:
        return self.db_obj.url

    @property
    def archived(self) -> bool:
        return self.db_obj.archived

    @property
    def is_inline(self) -> bool:
        return self.db_obj.is_inline

    # ToDo: implement this and add unit test
    def as_df(self) -> pd.DataFrame:
        rows = (page.to_dict() for page in self.session.databases.query(self.id).execute())
        return pd.DataFrame(rows)

    # ToDo: Implement this.
    # def query_db(
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
