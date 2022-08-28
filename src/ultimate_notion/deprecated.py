from functools import cache
from typing import Optional
from uuid import UUID

import pandas as pd
from notional import types
from notional.orm import connected_page
from notional.query import QueryBuilder
from notional.records import Database
from notional.session import Session


class NotionSession(Session):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def get_dbs_by_name(self, db_name: str) -> [Database]:
        return list(
            self.search(db_name).filter(property="object", value="database").execute()
        )

    def get_db_id(self, db_name: str) -> UUID:
        dbs = self.get_dbs_by_name(db_name)
        if not dbs:
            raise RuntimeError(f"No database `{db_name}` found.")
        if len(dbs) > 1:
            raise RuntimeError(f"{len(dbs)} databases of name `{db_name}` found.")
        return dbs[0].id

    def get_db(
        self, *, db_id: Optional[str] = None, db_name: Optional[str] = None
    ) -> Database:
        if (db_id is not None) == (db_name is not None):
            raise RuntimeError("Either `db_id` or `db_name` must be given.")
        if db_name is not None:
            db_id = self.get_db_id(db_name)
        return self.databases.retrieve(db_id)

    # Todo: Change the CustomBase type to type named like the Database
    # Todo: have a function that connects a page. This should work by creating a
    #  ConnectedPage object and setting `.__notion__page`.
    def query_db(
        self,
        *,
        db_id: Optional[str] = None,
        db_name: Optional[str] = None,
        live_updates=True,
    ) -> QueryBuilder:
        db_obj = self.get_db(db_id=db_id, db_name=db_name)

        if live_updates:
            cpage = connected_page(session=self, source_db=db_obj)
            return cpage.query()
        else:
            return self.databases.query(db_id)

    def get_db_as_df(self, db: Database) -> pd.DataFrame:
        rows = (
            self._page_to_row(page) for page in self.databases.query(db.id).execute()
        )
        return pd.DataFrame(rows)

    @cache
    def get_page(self, page_id):
        return self.pages.retrieve(page_id)

    def _resolve_relation(self, relation):
        for ref in relation:
            yield self.get_page(ref.id)

    def _page_to_row(self, page):
        row = dict(
            page_title=page.Title,
            page_id=page.id,
            page_created_time=page.created_time,
            page_last_edited_time=page.last_edited_time,
        )
        for k, v in page.properties.items():
            if isinstance(v, (types.Date, types.MultiSelect)):
                v = str(v)
            elif isinstance(v, types.Relation):
                v = ", ".join((p.Title for p in self._resolve_relation(v)))
            elif isinstance(v, types.DateFormula):
                v = str(v.Result)
            elif isinstance(v, types.Formula):
                v = v.Result
            else:
                v = v.Value
            row[k] = v
        return row
