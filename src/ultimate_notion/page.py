"""Page object"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, overload

from notion2md.exporter.block import StringExporter

from ultimate_notion.props import PropertyValue
from ultimate_notion.obj_api import props
from ultimate_notion.obj_api import types
from ultimate_notion.obj_api import blocks as obj_blocks
from ultimate_notion.blocks import Record
from ultimate_notion.utils import deepcopy_with_sharing, get_uuid, is_notebook

if TYPE_CHECKING:
    from ultimate_notion.database import Database

# ToDo:
#   * use the schema of the database to see which properties are writeable at all.


class PageProperty:
    """Property of a page implementing the descriptor protocol"""

    def __init__(self, prop_name: str):
        self._prop_name = prop_name

    def __get__(self, obj: Properties, type=None) -> PropertyValue:
        return obj[self._prop_name]

    def __set__(self, obj: Properties, value):
        obj[self._prop_name] = value


class PagePropertiesNS:
    """Properties of a page as defined in the schema of the database

    Access with the properties with `.property_name` or `["Property Name"]`.
    """

    def __init__(self, page: Page):
        self._page = page

    def __getitem__(self, prop_name: str) -> PropertyValue:
        prop = self._page.obj_ref.properties.get(prop_name)
        if prop is None:
            msg = f"No such property: {prop_name}"
            raise AttributeError(msg)

        return PropertyValue.wrap_obj_ref(obj_ref=prop)

    def __setitem__(self, prop_name: str, value: Any):
        if not isinstance(value, PropertyValue):
            # construct concrete PropertyValue using the schema
            prop_type_cls = self._page.database.schema.to_dict()[prop_name]
            prop_value_cls = PropertyValue._get_value_from_type(prop_type_cls)
            value = prop_value_cls(value)

        # update the property on the server (which will refresh the local data)
        self._page.session.api.pages.update(self._page.obj_ref, **{prop_name: value.obj_ref})

    def __iter__(self):
        """Iterator of property names"""
        yield from self._page.obj_ref.properties.keys()

    def to_dict(self) -> dict[str, Any]:
        """All page properties as dictionary"""
        return {prop_name: self[prop_name] for prop_name in self}


class Page(Record):
    obj_ref: obj_blocks.Page
    props: PagePropertiesNS | None = None

    def __init__(self, obj_ref):
        super().__init__(obj_ref)
        if self.database:
            self.props = self._create_props_ns()

    def _create_props_ns(self) -> PagePropertiesNS:
        """Create the namespace for the database properties of this page"""
        # We have to subclass in order to populate it with the descriptor PageProperty as
        # this only works on the class level.
        page_props_cls = type("PagePropertiesNS", (PagePropertiesNS,), {})
        for prop in self.database.schema.get_props():
            setattr(page_props_cls, prop.attr_name, PageProperty(prop.name))
        return page_props_cls(page=self)

    # ToDo: Build a real hierarchy of Pages and Blocks here
    #     self._children = list(self.session.api.blocks.children.list(parent=self.obj_ref))
    #
    # @property
    # def children(self) -> List[blocks.Block]:
    #     """Return all blocks belonging to this page"""
    #     return self._children

    @property
    def database(self) -> Database | None:
        """If this page is located in a database return the database or None otherwise"""
        from ultimate_notion.database import Database

        if isinstance(self.parent, Database):
            return self.parent
        else:
            return None

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
    def show(self) -> str | None:
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

    def _resolve_relation(self, relation):
        for ref in relation:
            yield self.session.get_page(ref.id)

    def __getitem__(self, property_name) -> types.PropertyValue:
        # ToDo change the logic here. Use a wrapper functionality as in `schema`
        val = self.obj_ref[property_name]
        if isinstance(val, props.Date):
            val = val.date
        elif isinstance(val, props.Relation):
            val = [p.title for p in self._resolve_relation(val)]
        elif isinstance(val, props.Formula):
            val = val.Result
        elif isinstance(val, props.LastEditedBy | props.CreatedBy):
            if not (user_id := val.last_edited_by.id):
                raise RuntimeError("Cannot determine id of user!")
            val = str(self.session.get_user(user_id))
        elif isinstance(val, props.MultiSelect):
            val = val.Values
        elif isinstance(val, props.NativeTypeMixin):
            val = val.Value
        else:
            msg = f'Unknown property type {type(val)}'
            raise RuntimeError(msg)
        return val

    def __setitem__(self, property_name: str, value: Any):
        if not self.database:
            msg = 'This page is not within a database'
            raise RuntimeError(msg)

        value_type = type(self.database.schema.to_dict()[property_name])
        prop = value_type(value)
        self.obj_ref[property_name] = prop.obj_ref

        if self.live_update:
            # update the property on the server (which will refresh the local data)
            self.session.api.pages.update(self.obj_ref, **{property_name: self.obj_ref[property_name]})

    def delete(self):
        self.session.api.pages.delete(self.obj_ref)
