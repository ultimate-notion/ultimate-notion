"""Functionality around Notion pages."""

from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING, Any, cast

from emoji import is_emoji

from ultimate_notion.blocks import Block, ChildDatabase, ChildPage, DataObject
from ultimate_notion.obj_api import blocks as obj_blocks
from ultimate_notion.obj_api import objects as objs
from ultimate_notion.obj_api import props as obj_props
from ultimate_notion.objects import Emoji, File, RichText, wrap_icon
from ultimate_notion.props import PropertyValue, Title
from ultimate_notion.text import md_renderer
from ultimate_notion.utils import get_active_session, get_repr, get_url, get_uuid, is_notebook

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
    _render_md = md_renderer()
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
        return self.to_html()

    @property
    def url(self) -> str:
        """Return the URL of this database."""
        return get_url(self.id)

    @property
    def content(self) -> list[Block]:
        """Return the content of this page, i.e. all blocks belonging to this page"""
        if self._content is None:  # generate cache
            session = get_active_session()
            child_blocks = session.api.blocks.children.list(parent=get_uuid(self.obj_ref))
            self._content = [Block.wrap_obj_ref(block) for block in child_blocks]
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
        return wrap_icon(icon)

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
        md = '\n'.join(block.to_markdown() for block in self.content)
        return md

    def to_html(self, *, raw: bool = False) -> str:
        """Return the content of the page as HTML."""
        # prepend MathJax configuration
        if raw:
            return self._render_md(self.to_markdown())

        html_before = dedent(
            """
            <!DOCTYPE html>
            <html>
            <head>
              <style>
                table {
                    width: 100%;
                    border-collapse: collapse;
                    margin: 15px 0;
                }

                th, td {
                    border: 1px solid #999;
                    padding: 0.5rem;
                    text-align: left;
                }

                th {
                    background-color: #f3f3f3;
                    color: #333;
                }

                tr:nth-child(even) {
                    background-color: #f2f2f2;
                }
                a {
                    color: #007BFF;
                    text-decoration: none;
                }
                a:hover {
                    color: #0056b3;
                    text-decoration: none;
                }
                kbd {
                    padding: 0.2em 0.4em;
                    font-size: 0.87em;
                    color: #24292e;
                    background-color: #f6f8fa;
                    border: 1px solid #d1d5da;
                    border-radius: 3px;
                    box-shadow: inset 0 -1px 0 #d1d5da;
                    font-family: Consolas, "Liberation Mono", Menlo, Courier, monospace;
                }
              </style>
              <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/default.min.css">
              <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
              <script type="text/x-mathjax-config">
                MathJax.Hub.Config({tex2jax: {inlineMath: [['$','$']]}});
              </script>
              <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
            </head>
            <body>
            """
        )
        html_after = dedent(
            """
            <script>hljs.highlightAll();</script>
            </body>
            </html>
            """
        )
        return html_before + self._render_md(self.to_markdown()) + html_after

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
        self._content = None  # this forces a new retrieval of children next time
        return self
