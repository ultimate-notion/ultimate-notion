"""Page object"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .core import records, types

if TYPE_CHECKING:
    from .session import NotionSession


class Page:
    def __init__(self, page_obj: records.Page, session: NotionSession):
        self.page_obj = page_obj
        self.session = session

    def _resolve_relation(self, relation):
        for ref in relation:
            yield self.session.get_page(ref.id)

    def to_dict(self, page):
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
                v = ", ".join((p.title for p in self._resolve_relation(v)))
            elif isinstance(v, types.DateFormula):
                v = str(v.Result)
            elif isinstance(v, types.Formula):
                v = v.Result
            else:
                v = v.Value
            row[k] = v

        return row
