"""Page object

ToDo:
    * make use of ObjectReference and wrap it own function

"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

from notional import blocks, types

from .record import Record
from .utils import deepcopy_with_sharing, schema2prop_type

if TYPE_CHECKING:
    from .database import Database
    from .session import Session

# ToDo:
#   * use the schema of the database to see which properties are writeable at all.


class Page(Record):
    def __init__(self, obj_ref: blocks.Page, session: Session, live_update: bool = True):
        self.obj_ref: blocks.Page = obj_ref
        self.session = session
        self.live_update = live_update

    @property
    def database(self) -> Optional[Database]:
        """Retrieve database from parent or None"""
        if not isinstance(self.parent, types.DatabaseRef):
            return None
        else:
            return self.session.get_db(self.parent)

    @property
    def title(self) -> str:
        return self.obj_ref.Title

    def __str__(self):
        return self.title

    def __repr__(self) -> str:
        cls_name = self.__class__.__name__
        return f"<{cls_name}: '{str(self)}' at {hex(id(self))}>"

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

    def __getitem__(self, property_name) -> types.PropertyValue:
        val = self.obj_ref[property_name]
        if isinstance(val, types.Date):
            val = val.date
        elif isinstance(val, types.Relation):
            val = [p.title for p in self._resolve_relation(val)]
        elif isinstance(val, types.Formula):
            val = val.Result
        elif isinstance(val, (types.LastEditedBy, types.CreatedBy)):
            assert isinstance(self.session, Session)
            val = str(self.session.get_user(val.last_edited_by.id))
        elif isinstance(val, types.MultiSelect):
            val = val.Values
        else:
            assert isinstance(val, types.NativeTypeMixin)
            val = val.Value
        return val

    def _get_prop_type(self, property_name: str) -> type[types.PropertyValue]:
        db = self.database
        assert db is not None, "this page is not within a database"
        return schema2prop_type(db.schema[property_name].type)

    def __setitem__(self, property_name: str, value: Any):
        value_type = self._get_prop_type(property_name)
        if isinstance(value, value_type):
            prop = value
        elif hasattr(value_type, "__compose__"):
            prop = value_type[value]
        else:
            raise TypeError(f"Unsupported value type for {value_type.type}")

        # update the property on the server (which will refresh the local data)
        self.session.notional.pages.update(self.obj_ref, **{property_name: prop})

    def __delitem__(self, key):
        # ToDo: Implement me!
        pass

    def to_dict(self) -> Dict[str, Any]:
        dct = super().to_dict()  # meta properties
        for k in self.properties.keys():
            dct[k] = self[k]
        return dct
