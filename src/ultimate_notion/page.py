"""Functionality around Notion pages."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import TYPE_CHECKING, Any, TypeGuard

from emoji import is_emoji
from typing_extensions import Self

from ultimate_notion.blocks import ChildrenMixin, CommentMixin, DataObject
from ultimate_notion.comment import Discussion
from ultimate_notion.core import NotionEntity, get_active_session, get_repr
from ultimate_notion.file import Emoji, FileInfo, wrap_icon
from ultimate_notion.obj_api import blocks as obj_blocks
from ultimate_notion.obj_api import objects as objs
from ultimate_notion.obj_api import props as obj_props
from ultimate_notion.obj_api.props import MAX_ITEMS_PER_PROPERTY
from ultimate_notion.props import PropertyValue, Title
from ultimate_notion.rich_text import Text, render_md
from ultimate_notion.templates import page_html
from ultimate_notion.utils import SList, is_notebook

if TYPE_CHECKING:
    from ultimate_notion.database import Database


class PageProperty:
    """Property of a page implementing the descriptor protocol."""

    def __init__(self, prop_name: str):
        self._prop_name = prop_name

    def __get__(self, obj: PagePropertiesNS, type=None) -> Any:  # noqa: A002
        return obj[self._prop_name]

    def __set__(self, obj: PagePropertiesNS, value: Any):
        obj[self._prop_name] = value


class PagePropertiesNS(Mapping[str, Any]):
    """Namespace of the properties of a page as defined in the schema of the database.

    This defines the `.props` namespace of a page `page` and updates the content
    on the Notion server side in case of an assignment.
    Access the properties with `page.props.property_name` or `page.props['Property Name']`.
    You can also convert it to a dictionary with `dict(page.props)`.
    """

    def __init__(self, page: Page):
        self._page = page

    @property
    def _obj_prop_vals(self) -> dict[str, obj_props.PropertyValue]:
        """Return the low-level page properties"""
        return self._page.obj_ref.properties

    def __getitem__(self, prop_name: str) -> Any:
        prop = self._obj_prop_vals.get(prop_name)

        if prop is None:
            msg = f'No such property: {prop_name}'
            raise AttributeError(msg)

        if isinstance(prop, obj_props.Relation) and prop.has_more:  # retrieve the full list of items
            prop.has_more = False
            return self._page.get_property(prop_name)
        elif (
            isinstance(prop, obj_props.People) and len(prop.people) == MAX_ITEMS_PER_PROPERTY and not prop._is_retrieved
        ):
            return self._page.get_property(prop_name)
        elif (
            isinstance(prop, obj_props.RichText | obj_props.Title)
            and len(Text.wrap_obj_ref(prop.value).mentions) == MAX_ITEMS_PER_PROPERTY
            and not prop._is_retrieved
        ):
            return self._page.get_property(prop_name)
        else:
            return PropertyValue.wrap_obj_ref(prop).value

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

        session = get_active_session()
        # update the property on the server (which will update the local data)
        session.api.pages.update(self._page.obj_ref, **{prop_name: value.obj_ref})

    def __iter__(self) -> Iterator[str]:
        """Iterator of property names."""
        yield from self._obj_prop_vals.keys()

    def __len__(self) -> int:
        """Return the number of properties."""
        return len(self._obj_prop_vals)

    def __repr__(self) -> str:
        return repr(dict(self))

    def __str__(self) -> str:
        return str(dict(self))


class Page(ChildrenMixin, CommentMixin, DataObject[obj_blocks.Page], wraps=obj_blocks.Page):
    """A Notion page.

    Attributes:
        props: accessor for all page properties
    """

    props: PagePropertiesNS

    @classmethod
    def wrap_obj_ref(cls, obj_ref: obj_blocks.Page, /) -> Self:
        obj = super().wrap_obj_ref(obj_ref)
        obj.props = obj._create_page_props_ns()
        return obj

    def _create_page_props_ns(self) -> PagePropertiesNS:
        """Create a namespace for the properties of this page defind by the database."""
        # We have to subclass in order to populate it with the descriptor `PageProperty`
        # as this only works on the class level and we want a unique class for each page.
        page_props_ns_cls = type('_PagePropertiesNS', (PagePropertiesNS,), {})
        if self.parent_db is not None:
            for prop in self.parent_db.schema.get_props():
                setattr(page_props_ns_cls, prop.attr_name, PageProperty(prop_name=prop.name))
        return page_props_ns_cls(page=self)

    def __str__(self) -> str:
        return str(self.title)

    def __repr__(self) -> str:
        return get_repr(self, desc=self.title)

    def _repr_html_(self) -> str:  # noqa: PLW3201
        """Called by JupyterLab automatically to display this page."""
        return self.to_html()

    @property
    def is_page(self) -> bool:
        """Return whether the object is a page."""
        return True

    @property
    def url(self) -> str:
        """Return the URL of this page."""
        return self.obj_ref.url

    @property
    def public_url(self) -> str | None:
        """Return the public URL of this database."""
        return self.obj_ref.public_url

    @property
    def subpages(self) -> list[Page]:
        """Return all contained pages within this page"""
        return [block for block in self.children if is_page_guard(block)]

    @property
    def subdbs(self) -> list[Database]:
        """Return all contained databases within this page"""
        return [block for block in self.children if is_db_guard(block)]

    @property
    def parent_db(self) -> Database | None:
        """If this page is located in a database return the database or None otherwise.

        This is a convenience method to avoid the need to check and cast the type of the parent.
        """

        if is_db_guard(self.parent):
            return self.parent
        else:
            return None

    @property
    def in_db(self) -> bool:
        """Return True if this page is located in a database."""
        return self.parent_db is not None

    @property
    def title(self) -> Text:
        """Title of the page."""
        return Text.wrap_obj_ref(self.obj_ref.title)

    @title.setter
    def title(self, text: str | None):
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
        if (icon := self.obj_ref.icon) is None:
            return None
        else:
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
            cover = FileInfo(url=str(cover), name=None)
        cover_obj = None if cover is None else cover.obj_ref
        session = get_active_session()
        session.api.pages.set_attr(self.obj_ref, cover=cover_obj)

    @property
    def comments(self) -> Discussion:
        """Return the discussion thread of this page.

        A page can only have a single discussion thread in contrast to inline comments.

        !!! note

            This functionality requires that your integration was granted *read* comment capabilities.
        """
        if not self._discussions:  # create an empty discussion thread
            self._comments = [Discussion([], parent=self)]
        return SList(self._discussions).item()

    def get_property(self, prop_name: str) -> Any:
        """Directly retrieve the property value from the API.

        Use this method only if you want to retrieve a specific property value that
        might have been updated on the server side without reloading the whole page.
        In all other cases, use the `props` namespace of the page to avoid unnecessary API calls.
        """
        session = get_active_session()
        prop_obj = self.props._obj_prop_vals[prop_name]
        prop_items = session.api.pages.properties.retrieve(self.obj_ref, prop_obj)
        prop_values = (item.value for item in prop_items)

        if isinstance(prop_obj, obj_props.PAGINATED_PROP_VALS):
            prop_obj.value = list(prop_values)
        else:  # we should have only one property-item in the iterator
            prop_obj.value = SList(prop_values).item()  # guaranteed to have only one item

        prop_obj._is_retrieved = True
        return PropertyValue.wrap_obj_ref(prop_obj).value

    def to_markdown(self) -> str:
        """Return the content of the page as Markdown.

        !!! note

            This will not include nested blocks, i.e. the children of top-level blocks.
        """
        md = f'# {self.title}\n\n'
        md += '\n'.join(block._to_markdown() for block in self.children)
        return md

    def _to_markdown(self) -> str:
        """Return the reference to this page as Markdown."""
        return f'[📄 **<u>{self.title}</u>**]({self.url})\n'

    def to_html(self, *, raw: bool = False) -> str:
        """Return the content of the page as HTML."""
        html = render_md(self.to_markdown())
        if not raw:
            html = page_html(html, title=self.title)
        return html

    def show(self, *, simple: bool | None = None):
        """Show the content of the page, rendered in JupyterLab"""
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
                self.parent._children = None  # forces a new retrieval of the parent's children next time
        return self

    def reload(self) -> Self:
        """Reload this page."""
        session = get_active_session()
        self.obj_ref = session.api.pages.retrieve(self.obj_ref.id)
        self._children = None  # forces a new retrieval of children next time
        self._comments = None  # forces a new retrieval of comments next time
        return self


def is_db_guard(obj: NotionEntity | None) -> TypeGuard[Database]:
    """Return whether the object is a database as type guard."""
    return obj is not None and obj.is_db


def is_page_guard(obj: NotionEntity | None) -> TypeGuard[Page]:
    """Return whether the object is a page as type guard."""
    return obj is not None and obj.is_page
