"""Database object"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .core import records
from .core.text import plain_text

if TYPE_CHECKING:
    from .session import NotionSession


class Database:
    def __init__(self, db_obj: records.Database, session: NotionSession):
        self.db_obj = db_obj
        self.session = session

    @property
    def Title(self):
        """Return the title of this database as plain text."""
        if self.db_obj.title is None or len(self.db_obj.title) == 0:
            return None

        return plain_text(*self.db_obj.title)
