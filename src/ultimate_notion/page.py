"""Page object"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, overload

from notion2md.exporter.block import StringExporter
from notional import types

from ultimate_notion.record import Record
from ultimate_notion.utils import deepcopy_with_sharing, get_uuid, is_notebook, schema2prop_type

if TYPE_CHECKING:
    from ultimate_notion.database import Database

# ToDo:
#   * use the schema of the database to see which properties are writeable at all.


class Properties:
    """Properties namespace for a page"""

    ...


class Page(Record):
    live_update: bool = True

    # ToDo: Build a real hierarchy of Pages and Blocks here
    #     self._children = list(self.session.notional.blocks.children.list(parent=self.obj_ref))
    #
    # @property
    # def children(self) -> List[blocks.Block]:
    #     """Return all blocks belonging to this page"""
    #     return self._children

    @property
    def database(self) -> Database | None:
        """Retrieve database from parent or None"""
        if not isinstance(self.parent, types.DatabaseRef):
            return None
        else:
            return self.session.get_db(get_uuid(self.parent))

    @property
    def title(self) -> str:
        return self.obj_ref.Title

    def markdown(self) -> str:
        """Return the content of the page as Markdown"""
        md = f'# {self.title}\n'
        # ToDo: This retrieves the content again, could be done internally.
        #       Also notion2md is quiet buggy in generating MD and notion2markdown is better but hard to use.
        md += StringExporter(block_id=str(self.id)).export()
        return md

    @overload
    def show(self, *, display: Literal[False]) -> str:
        ...

    @overload
    def show(self, *, display: Literal[True]) -> None:
        ...

    @overload
    def show(self, *, display: None) -> str | None:
        ...

    def show(self, *, display=None):
        """Show the content of the page as markdown, rendered in Jupyter Lab"""
        if display is None:
            display = is_notebook()

        md = self.markdown()
        if display:
            from IPython.core.display import display_markdown

            display_markdown(md, raw=True)
        else:
            return md

    def __str__(self) -> str:
        return self.show(display=False)

    def __repr__(self) -> str:
        cls_name = self.__class__.__name__
        return f"<{cls_name}: '{self.title}' at {hex(id(self))}>"

    @property
    def icon(self) -> str:
        icon = self.obj_ref.icon
        if isinstance(icon, types.FileObject):
            return icon.URL
        elif isinstance(icon, types.EmojiObject):
            return icon.emoji
        else:
            msg = f'unknown icon object of {type(icon)}'
            raise RuntimeError(msg)

    @property
    def properties(self) -> dict[str, Any]:
        """Page properties as dictionary.

        This includes properties defined by a database schema as well as meta properties like creation time, etc.
        """
        dct = super().properties  # meta properties
        for k in self.obj_ref.properties:
            dct[k] = self[k]
        return dct

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
        elif isinstance(val, types.LastEditedBy | types.CreatedBy):
            val = str(self.session.get_user(val.last_edited_by.id))
        elif isinstance(val, types.MultiSelect):
            val = val.Values
        elif isinstance(val, types.NativeTypeMixin):
            val = val.Value
        else:
            msg = f'Unknown property type {type(val)}'
            raise RuntimeError(msg)
        return val

    def _get_prop_type(self, property_name: str) -> type[types.PropertyValue]:
        db = self.database
        if db is None:
            msg = 'this page is not within a database'
            raise RuntimeError(msg)
        return schema2prop_type(db.schema[property_name].type)

    def __setitem__(self, property_name: str, value: Any):
        value_type = self._get_prop_type(property_name)
        if isinstance(value, value_type):
            prop = value
        elif hasattr(value_type, '__compose__'):
            prop = value_type[value]
        else:
            msg = f'Unsupported value type for {value_type.type}'
            raise TypeError(msg)

        if self.live_update:
            # update the property on the server (which will refresh the local data)
            self.session.notional.pages.update(self.obj_ref, **{property_name: prop})

    def __delitem__(self, key):
        # ToDo: Implement me!
        pass
