"""Page object"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, cast, overload

from markdown2 import markdown as md2html

from ultimate_notion.blocks import DataObject
from ultimate_notion.obj_api import blocks as obj_blocks
from ultimate_notion.obj_api import objects as objs
from ultimate_notion.objects import File
from ultimate_notion.props import PropertyValue, Title
from ultimate_notion.utils import get_active_session, get_repr, is_notebook

if TYPE_CHECKING:
    from ultimate_notion.database import Database

# ToDo:
#   * use the schema of the database to see which properties are writeable at all.


class PageProperty:
    """Property of a page implementing the descriptor protocol"""

    def __init__(self, prop_name: str):
        self._prop_name = prop_name

    def __get__(self, obj: PageProperties, type=None) -> PropertyValue:  # noqa: A002
        return obj[self._prop_name]

    def __set__(self, obj: PageProperties, value):
        obj[self._prop_name] = value


class PageProperties:
    """Properties of a page as defined in the schema of the database

    Access the properties with `.property_name` or `["Property Name"]`.
    """

    def __init__(self, page: Page):
        self._page = page
        self._properties = page.obj_ref.properties

    def __getitem__(self, prop_name: str) -> PropertyValue:
        prop = self._properties.get(prop_name)
        if prop is None:
            msg = f'No such property: {prop_name}'
            raise AttributeError(msg)

        return cast(PropertyValue, PropertyValue.wrap_obj_ref(obj_ref=prop))

    def __setitem__(self, prop_name: str, value: Any):
        db = self._page.database
        if db is None:
            msg = f'Trying to set a property but page {self._page} is not bound to any database'
            raise RuntimeError(msg)

        if not isinstance(value, PropertyValue):
            # construct concrete PropertyValue using the schema
            prop_type = db.schema.to_dict()[prop_name]
            value = prop_type.prop_value(value)

        # update the property on the server (which will update the local data)
        session = get_active_session()
        session.api.pages.update(self._page.obj_ref, **{prop_name: value.obj_ref})

    def __iter__(self):
        """Iterator of property names"""
        yield from self._properties.keys()

    def to_dict(self) -> dict[str, PropertyValue]:
        """All page properties as dictionary"""
        return {prop_name: self[prop_name] for prop_name in self}


class Page(DataObject[obj_blocks.Page], wraps=obj_blocks.Page):
    props: PageProperties

    @classmethod
    def wrap_obj_ref(cls, obj_ref: obj_blocks.Page, /) -> Page:
        obj = super().wrap_obj_ref(obj_ref)
        obj.props = obj._create_prop_attrs()
        return obj

    def _create_prop_attrs(self) -> PageProperties:
        """Create the attributes for the database properties of this page"""
        # We have to subclass in order to populate it with the descriptor `PageProperty``
        # as this only works on the class level and we want a unique class for each property.
        page_props_cls = type('_PageProperties', (PageProperties,), {})
        if self.database:
            for col in self.database.schema.get_cols():
                setattr(page_props_cls, col.attr_name, PageProperty(col.name))
        return page_props_cls(page=self)

    def __str__(self) -> str:
        return str(self.title)

    def __repr__(self) -> str:
        return get_repr(self, desc=self.title.value)

    def _repr_html_(self) -> str:  # noqa: PLW3201
        """Called by Jupyter Lab automatically to display this page"""
        return md2html(self.markdown(), extras=['strike', 'task_list'])

    # ToDo: Build a real hierarchy of Pages and Blocks here
    # @property
    # def children(self) -> List[blocks.Block]:
    #     """Return all blocks belonging to this page"""
    #     return list(self.session.api.blocks.children.list(parent=self.obj_ref))

    @property
    def database(self) -> Database | None:
        """If this page is located in a database return the database or None otherwise"""
        from ultimate_notion.database import Database  # noqa: PLC0415

        if isinstance(self.parent, Database):
            return self.parent
        else:
            return None

    @property
    def title(self) -> Title:  # Todo: Rather return Text here!
        """Title of the page"""
        # As the 'title' property might be renamed in case of pages in databases, we look for the `id`.
        for prop in self.obj_ref.properties.values():
            if prop.id == 'title':
                return cast(Title, PropertyValue.wrap_obj_ref(prop))
        msg = 'Encountered a page without title property'
        raise RuntimeError(msg)

    @property
    def icon(self) -> File | str:
        """Icon of page, i.e. emojis, Notion's icons, or custom images"""
        icon = self.obj_ref.icon
        if isinstance(icon, objs.ExternalFile):
            return File.wrap_obj_ref(icon)
        elif isinstance(icon, objs.EmojiObject):
            return icon.emoji
        else:
            msg = f'unknown icon object of {type(icon)}'
            raise RuntimeError(msg)

    def markdown(self) -> str:
        """Return the content of the page as Markdown"""
        # ToDo: Since notion2md is also quite buggy, use an own implementation here using Mistune!
        import os  # noqa: PLC0415

        from notion2md.exporter.block import StringExporter  # noqa: PLC0415

        from ultimate_notion.session import ENV_NOTION_TOKEN, Session  # noqa: PLC0415

        auth_token = Session.get_or_create().client.options.auth
        os.environ[ENV_NOTION_TOKEN] = auth_token  # used internally by notion_client used by notion2md
        return StringExporter(block_id=self.id).export()

    @overload
    def show(self, *, display: Literal[False]) -> str: ...

    @overload
    def show(self, *, display: Literal[True]) -> None: ...

    @overload
    def show(self) -> str | None: ...

    def show(self, *, display=None):
        """Show the content of the page as markdown, rendered in Jupyter Lab"""
        if display is None:
            display = is_notebook()

        md = self.markdown()
        if display:
            from IPython.core.display import display_markdown  # noqa: PLC0415

            display_markdown(md, raw=True)
        else:
            return md

    def delete(self) -> Page:
        """Delete/archive this page"""
        if not self.is_archived:
            session = get_active_session()
            session.api.pages.delete(self.obj_ref)
        return self

    def restore(self) -> Page:
        """Restore/unarchive this page"""
        if self.is_archived:
            session = get_active_session()
            session.api.pages.restore(self.obj_ref)
        return self

    def reload(self) -> Page:
        """Reload this page"""
        session = get_active_session()
        self.obj_ref = session.api.pages.retrieve(self.obj_ref.id)
        return self
