"""Page object"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

from notional import blocks, types

from .record import Record
from .utils import deepcopy_with_sharing

if TYPE_CHECKING:
    from .session import Session


class Page(Record):
    def __init__(self, obj_ref: blocks.Page, session: Optional[Session]):
        self.obj_ref: blocks.Page = obj_ref
        self.session = session

    @property
    def is_live(self) -> bool:
        if self.session is None:
            return False
        else:
            return True

    @property
    def title(self) -> str:
        return self.obj_ref.Title

    @property
    def icon(self) -> str:
        icon = self.obj_ref.icon
        if isinstance(icon, types.FileObject):
            return icon.URL
        elif isinstance(icon, types.EmojiObject):
            return icon.emoji
        else:
            raise RuntimeError(f"unknown icon object of {type(icon)}")

    @property
    def properties(self) -> Dict[str, types.PropertyValue]:
        return self.obj_ref.properties

    def clone(self) -> Page:
        return deepcopy_with_sharing(self, shared_attributes=['session'])

    def _resolve_relation(self, relation):
        for ref in relation:
            yield self.session.get_page(ref.id)

    def to_dict(self) -> Dict[str, Any]:
        dct = super().to_dict()
        dct['title'] = self.title
        for k, v in self.properties.items():
            if isinstance(v, types.MultiSelect):
                v = str(v)
            elif isinstance(v, types.Date):
                v = v.date
            elif isinstance(v, types.Relation):
                v = [p.title for p in self._resolve_relation(v)]
            elif isinstance(v, types.Formula):
                v = v.Result
            elif isinstance(v, (types.LastEditedBy, types.CreatedBy)):
                assert isinstance(self.session, Session)
                v = self.session.get_user(v.last_edited_by.id).name
            elif isinstance(v, types.DatabaseRef):
                assert isinstance(self.session, Session)
                v = self.session.get_db(v.database_id).title
            else:
                assert isinstance(v, types.NativeTypeMixin)
                v = v.Value
            dct[k] = v
        return dct
