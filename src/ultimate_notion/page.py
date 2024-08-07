"""Functionality around Notion pages."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeGuard, cast

from emoji import is_emoji
from typing_extensions import Self

from ultimate_notion.blocks import ChildDatabase, ChildPage, ChildrenMixin, DataObject
from ultimate_notion.core import get_active_session, get_repr, get_url
from ultimate_notion.file import Emoji, FileInfo, wrap_icon
from ultimate_notion.obj_api import blocks as obj_blocks
from ultimate_notion.obj_api import objects as objs
from ultimate_notion.obj_api import props as obj_props
from ultimate_notion.props import PropertyValue, Title
from ultimate_notion.templates import page_html
from ultimate_notion.text import RichText, render_md
from ultimate_notion.utils import is_notebook

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
        db = self._page.parent_db
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


class Page(ChildrenMixin, DataObject[obj_blocks.Page], wraps=obj_blocks.Page):
    """A Notion page.

    Attributes:
        props: accessor for all page properties
    """

    props: PageProperties

    @classmethod
    def wrap_obj_ref(cls, obj_ref: obj_blocks.Page, /) -> Self:
        obj = super().wrap_obj_ref(obj_ref)
        obj.props = obj._create_prop_attrs()
        return obj

    def _create_prop_attrs(self) -> PageProperties:
        """Create the attributes for the database properties of this page."""
        # We have to subclass in order to populate it with the descriptor `PageProperty``
        # as this only works on the class level and we want a unique class for each property.
        page_props_cls = type('_PageProperties', (PageProperties,), {})
        if self.parent_db is not None:
            for prop in self.parent_db.schema.get_props():
                setattr(page_props_cls, prop.attr_name, PageProperty(prop_name=prop.name))
        return page_props_cls(page=self)

    def __str__(self) -> str:
        return str(self.title)

    def __repr__(self) -> str:
        return get_repr(self, desc=self.title)

    def _repr_html_(self) -> str:  # noqa: PLW3201
        """Called by Jupyter Lab automatically to display this page."""
        return self.to_html()

    @property
    def is_page(self) -> bool:
        """Return whether the object is a page."""
        return True

    @property
    def url(self) -> str:
        """Return the URL of this database."""
        return get_url(self.id)

    @property
    def subpages(self) -> list[Page]:
        """Return all contained pages within this page"""
        session = get_active_session()
        return [session.get_page(block.id) for block in self.children if isinstance(block, ChildPage)]

    @property
    def subdbs(self) -> list[Database]:
        """Return all contained databases within this page"""
        session = get_active_session()
        return [session.get_db(block.id) for block in self.children if isinstance(block, ChildDatabase)]

    @property
    def parent_db(self) -> Database | None:
        """If this page is located in a database return the database or None otherwise.

        This is a convenience method to avoid the need to check and cast the type of the parent.
        """

        def is_db(obj: DataObject | None) -> TypeGuard[Database]:
            return obj is not None and obj.is_db

        if is_db(self.parent):
            return self.parent
        else:
            return None

    @property
    def in_db(self) -> bool:
        """Return True if this page is located in a database."""
        return self.parent_db is not None

    @property
    def title(self) -> RichText:
        """Title of the page."""
        return RichText.wrap_obj_ref(self.obj_ref.title)

    @title.setter
    def title(self, text: RichText | str | None):
        """Set the title of the page."""
        if text is None:
            text = ''
        title = Title(text)
        title_prop_name = self.obj_ref._get_title_prop_name()
        session = get_active_session()
        session.api.pages.update(self.obj_ref, **{title_prop_name: title.obj_ref})

    @property
    def icon(self) -> FileInfo | Emoji | None:
        """Icon of the page, i.e. emojis, Notion's icons, or custom images."""
        icon = self.obj_ref.icon
        return wrap_icon(icon)

    @icon.setter
    def icon(self, icon: FileInfo | Emoji | str | None):
        """Set the icon of this page."""
        if isinstance(icon, str) and not isinstance(icon, Emoji):
            icon = Emoji(icon) if is_emoji(icon) else FileInfo(url=icon, name=None)
        icon_obj = None if icon is None else icon.obj_ref
        session = get_active_session()
        session.api.pages.set_attr(self.obj_ref, icon=icon_obj)

    @property
    def cover(self) -> FileInfo | None:
        """Cover of the page."""
        cover = self.obj_ref.cover
        if isinstance(cover, objs.ExternalFile):
            return FileInfo.wrap_obj_ref(cover)
        elif cover is None:
            return None
        else:
            msg = f'unknown cover object of {type(cover)}'
            raise RuntimeError(msg)

    @cover.setter
    def cover(self, cover: FileInfo | str | None):
        """Set the cover fo this page."""
        if isinstance(cover, str):
            cover = FileInfo(url=cover, name=None)
        cover_obj = None if cover is None else cover.obj_ref
        session = get_active_session()
        session.api.pages.set_attr(self.obj_ref, cover=cover_obj)

    def to_markdown(self) -> str:
        """Return the content of the page as Markdown.

        !!! note

            This will not include nested blocks, i.e. children.
        """
        md = f'# {self.title}\n\n'
        md += '\n'.join(block.to_markdown() for block in self.children)
        return md

    def to_html(self, *, raw: bool = False) -> str:
        """Return the content of the page as HTML."""
        html = render_md(self.to_markdown())
        if not raw:
            html = page_html(html, title=self.title)
        return html

    def show(self, *, simple: bool | None = None):
        """Show the content of the page, rendered in Jupyter Lab"""
        simple = simple if simple is not None else not is_notebook()
        md = self.to_markdown()

        if simple:
            print(md)  # noqa: T201
        else:
            from IPython.core.display import display_markdown  # noqa: PLC0415

            display_markdown(md, raw=True)

    def delete(self) -> Self:
        """Delete this page.

        !!! Warning

            Deleting a page will also delete all child pages and child databases recursively.
            If these objects are already cached in the session, they will not be updated.
            Use `session.cache.clear()` to clear the cache or call `reload()` on them.
        """
        if not self.is_deleted:
            session = get_active_session()
            session.api.pages.delete(self.obj_ref)
            self._delete_me_from_parent()
        return self

    def restore(self) -> Self:
        """Restore this page."""
        if self.is_deleted:
            session = get_active_session()
            session.api.pages.restore(self.obj_ref)
            if isinstance(self.parent, ChildrenMixin):
                self.parent._children = None  # this forces a new retrieval of children next time
        return self

    def reload(self) -> Self:
        """Reload this page."""
        session = get_active_session()
        self.obj_ref = session.api.pages.retrieve(self.obj_ref.id)
        self._children = None  # this forces a new retrieval of children next time
        return self
