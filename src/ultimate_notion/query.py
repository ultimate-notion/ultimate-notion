"""Query the database for pages."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ultimate_notion.core import get_active_session
from ultimate_notion.page import Page
from ultimate_notion.view import View

if TYPE_CHECKING:
    from ultimate_notion.database import Database


class Query:
    def __init__(self, database: Database):
        self.database = database

    def execute(self) -> View:
        """Execute the query and return the resulting pages."""
        session = get_active_session()
        query_obj = session.api.databases.query(self.database.obj_ref)
        pages = [cast(Page, session.cache.setdefault(page.id, Page.wrap_obj_ref(page))) for page in query_obj.execute()]
        return View(database=self.database, pages=pages, query=self)
