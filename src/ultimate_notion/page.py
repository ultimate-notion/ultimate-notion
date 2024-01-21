"""Functionality around Notion pages."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import mistune
from emoji import is_emoji

from ultimate_notion.blocks import Block, ChildDatabase, ChildPage, DataObject
from ultimate_notion.obj_api import blocks as obj_blocks
from ultimate_notion.obj_api import objects as objs
from ultimate_notion.obj_api import props as obj_props
from ultimate_notion.objects import Emoji, File, RichText
from ultimate_notion.props import PropertyValue, Title
from ultimate_notion.utils import get_active_session, get_repr, is_notebook

if TYPE_CHECKING:
    from ultimate_notion.database import Database


class PageProperty:
    """Property of a page implementing the descriptor protocol."""

    def __init__(self, prop_name: str):
        self._prop_name = prop_name

    def __get__(self, obj: PageProperties, type=None) -> PropertyValue:  # noqa: A002
        return obj[self._prop_name]

    def __set__(self, obj: PageProperties, value):
        obj[self._prop_name] = value


class PageProperties:
    """Properties of a page as defined in the schema of the database.

    This defines the `.props` namespace of a page `page` and updates the content
    on the Notion server side in case of an assignment.
    Access the properties with `page.props.property_name` or `page.props["Property Name"]`.
    """

    def __init__(self, page: Page):
        self._page = page

    @property
    def _properties(self) -> dict[str, obj_props.PropertyValue]:
        """Return the low-level page properties"""
        return self._page.obj_ref.properties

    def __getitem__(self, prop_name: str) -> PropertyValue:
        prop = self._properties.get(prop_name)
        if prop is None:
            msg = f'No such property: {prop_name}'
            raise AttributeError(msg)

        return cast(PropertyValue, PropertyValue.wrap_obj_ref(prop))

    def __setitem__(self, prop_name: str, value: Any):
        # Todo: use the schema of the database to see which properties are writeable at all.
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
        """Iterator of property names."""
        yield from self._properties.keys()

    def to_dict(self) -> dict[str, PropertyValue]:
        """All page properties as dictionary."""
        return {prop_name: self[prop_name] for prop_name in self}


class Page(DataObject[obj_blocks.Page], wraps=obj_blocks.Page):
    """A Notion page.

    Attributes:
        props: accessor for all page properties
    """

    props: PageProperties
    _render_md = mistune.create_markdown(plugins=['strikethrough', 'url', 'task_lists', 'math'], escape=False)
    _content: list[Block] | None = None

    @classmethod
    def wrap_obj_ref(cls, obj_ref: obj_blocks.Page, /) -> Page:
        obj = super().wrap_obj_ref(obj_ref)
        obj.props = obj._create_prop_attrs()
        return obj

    def _create_prop_attrs(self) -> PageProperties:
        """Create the attributes for the database properties of this page."""
        # We have to subclass in order to populate it with the descriptor `PageProperty``
        # as this only works on the class level and we want a unique class for each property.
        page_props_cls = type('_PageProperties', (PageProperties,), {})
        if self.database is not None:
            for col in self.database.schema.get_cols():
                setattr(page_props_cls, col.attr_name, PageProperty(prop_name=col.name))
        return page_props_cls(page=self)

    def __str__(self) -> str:
        return str(self.title)

    def __repr__(self) -> str:
        return get_repr(self, desc=self.title)

    def _repr_html_(self) -> str:  # noqa: PLW3201
        """Called by Jupyter Lab automatically to display this page."""
        return self._render_md(self.to_markdown())  # Github flavored markdown

    @property
    def content(self) -> list[Block]:
        """Return the content of this page, i.e. all blocks belonging to this page"""
        if self._content is None:  # generate cache
            session = get_active_session()
            self._content = session._get_blocks(self.id)

        return self._content

    @property
    def children(self) -> list[Page | Database]:
        """Return all contained databases and pages within this page"""
        session = get_active_session()
        children: list[Page | Database] = []
        for block in self.content:
            if isinstance(block, ChildPage):
                children.append(session.get_page(block.id))
            elif isinstance(block, ChildDatabase):
                children.append(session.get_db(block.id))
        return children

    @property
    def database(self) -> Database | None:
        """If this page is located in a database return the database or None otherwise."""
        from ultimate_notion.database import Database  # noqa: PLC0415

        if isinstance(self.parent, Database):
            return self.parent
        else:
            return None

    def _get_title_col_name(self) -> str:
        """Get the name of the title property."""
        # As the 'title' property might be renamed in case of pages in databases, we look for the `id`.
        for name, prop in self.obj_ref.properties.items():
            if prop.id == 'title':
                return name
        msg = 'Encountered a page without title property'
        raise RuntimeError(msg)

    @property
    def title(self) -> RichText:
        """Title of the page."""
        title_prop_name = self._get_title_col_name()
        title_prop = self.obj_ref.properties[title_prop_name]
        title = cast(Title, PropertyValue.wrap_obj_ref(title_prop))
        return title.value

    @title.setter
    def title(self, text: RichText | str | None):
        """Set the title of the page."""
        if text is None:
            text = ''
        title = Title(text)
        title_prop_name = self._get_title_col_name()
        session = get_active_session()
        session.api.pages.update(self.obj_ref, **{title_prop_name: title.obj_ref})

    @property
    def icon(self) -> File | Emoji | None:
        """Icon of the page, i.e. emojis, Notion's icons, or custom images."""
        icon = self.obj_ref.icon
        if isinstance(icon, objs.ExternalFile):
            return File.wrap_obj_ref(icon)
        elif isinstance(icon, objs.EmojiObject):
            return Emoji.wrap_obj_ref(icon)
        elif icon is None:
            return None
        else:
            msg = f'unknown icon object of {type(icon)}'
            raise RuntimeError(msg)

    @icon.setter
    def icon(self, icon: File | Emoji | str | None):
        """Set the icon of this page."""
        if isinstance(icon, str) and not isinstance(icon, Emoji):
            icon = Emoji(icon) if is_emoji(icon) else File(url=icon, name=None)
        icon_obj = None if icon is None else icon.obj_ref
        session = get_active_session()
        session.api.pages.set_attr(self.obj_ref, icon=icon_obj)

    @property
    def cover(self) -> File | None:
        """Cover of the page."""
        cover = self.obj_ref.cover
        if isinstance(cover, objs.ExternalFile):
            return File.wrap_obj_ref(cover)
        elif cover is None:
            return None
        else:
            msg = f'unknown cover object of {type(cover)}'
            raise RuntimeError(msg)

    @cover.setter
    def cover(self, cover: File | str | None):
        """Set the cover fo this page."""
        if isinstance(cover, str):
            cover = File(url=cover, name=None)
        cover_obj = None if cover is None else cover.obj_ref
        session = get_active_session()
        session.api.pages.set_attr(self.obj_ref, cover=cover_obj)

    def to_markdown(self) -> str:
        """Return the content of the page as Markdown."""
        # ToDo: Since notion2md is also quite buggy, use an own implementation here using Mistune!
        import os  # noqa: PLC0415

        from notion2md.exporter.block import StringExporter  # noqa: PLC0415

        from ultimate_notion.session import ENV_NOTION_TOKEN, Session  # noqa: PLC0415

        auth_token = Session.get_or_create().client.options.auth
        if auth_token is None:
            msg = 'Impossible to pass the auth token to notion_client via an environment variable'
            raise RuntimeError(msg)
        os.environ[ENV_NOTION_TOKEN] = auth_token  # used internally by notion_client used by notion2md

        md = f'# {self.title}\n'
        md += StringExporter(block_id=self.id).export()
        return md

    def show(self, *, simple: bool | None = None):
        """Show the content of the page, rendered in Jupyter Lab"""
        simple = simple if simple is not None else is_notebook()
        md = self.to_markdown()

        if simple:
            print(md)  # noqa: T201
        else:
            from IPython.core.display import display_markdown  # noqa: PLC0415

            display_markdown(md, raw=True)

    def delete(self) -> Page:
        """Delete/archive this page."""
        if not self.is_deleted:
            session = get_active_session()
            session.api.pages.delete(self.obj_ref)
        return self

    def restore(self) -> Page:
        """Restore/unarchive this page."""
        if self.is_deleted:
            session = get_active_session()
            session.api.pages.restore(self.obj_ref)
        return self

    def reload(self) -> Page:
        """Reload this page."""
        session = get_active_session()
        self.obj_ref = session.api.pages.retrieve(self.obj_ref.id)
        self._content = None  # this forces a new retrieval next time
        return self
