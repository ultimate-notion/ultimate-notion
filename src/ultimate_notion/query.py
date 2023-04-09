from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ultimate_notion.database import Database


class QueryBuilder:
    """ "Querybuilder to query a database in a more specific way"""

    def __init__(self, db: Database):
        self.db = db
        # ToDo: Implement this using Notion's QueryBuilder
        raise NotImplementedError
