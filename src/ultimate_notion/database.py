"""Functionality for working with Notion databases."""

from __future__ import annotations

from typing import cast

from pydantic import BaseModel
from typing_extensions import Self

from ultimate_notion.blocks import ChildrenMixin, DataObject
from ultimate_notion.core import get_active_session, get_repr
from ultimate_notion.file import Emoji, FileInfo
from ultimate_notion.obj_api import blocks as obj_blocks
from ultimate_notion.obj_api import objects as objs
from ultimate_notion.page import Page
from ultimate_notion.query import Query
from ultimate_notion.rich_text import Text, camel_case, snake_case
from ultimate_notion.schema import Property, PropertyType, PropertyValue, ReadOnlyPropertyError, Schema, SchemaError
from ultimate_notion.view import View


class Database(DataObject[obj_blocks.Database], wraps=obj_blocks.Database):
    """A Notion database.

    This object always represents an original database, not a linked database.

    API reference: https://developers.notion.com/docs/working-with-databases
    """

    _schema: type[Schema] | None = None

    def __str__(self):
        if self.title:
            return str(self.title)
        else:
            return 'Untitled'

    def _repr_html_(self) -> str:  # noqa: PLW3201
        """Called by JupyterLab automatically"""
        return str(self)

    def __repr__(self) -> str:
        return get_repr(self)

    @property
    def url(self) -> str:
        """Return the URL of this database."""
        return self.obj_ref.url

    @property
    def title(self) -> str | Text:
        """Return the title of this database as rich text."""
        title = self.obj_ref.title
        # `str` added as return value but always RichText returned, which inherits from str.
        return Text.wrap_obj_ref(title)

    @title.setter
    def title(self, text: str | Text):
        """Set the title of this database"""
        if not isinstance(text, Text):
            text = Text.from_plain_text(text)
        session = get_active_session()
        session.api.databases.update(self.obj_ref, title=text.obj_ref)

    @property
    def description(self) -> Text:
        """Return the description of this database as rich text."""
        desc = self.obj_ref.description
        return Text.wrap_obj_ref(desc)

    @description.setter
    def description(self, text: str | Text):
        """Set the description of this database."""
        if not isinstance(text, Text):
            text = Text.from_plain_text(text)
        session = get_active_session()
        session.api.databases.update(self.obj_ref, description=text.obj_ref)

    @property
    def icon(self) -> FileInfo | Emoji | None:
        """Return the icon of this database as file or emoji."""
        match self.obj_ref.icon:
            case objs.FileObject() as icon:
                return FileInfo.wrap_obj_ref(icon)
            case objs.EmojiObject() as icon:
                return Emoji.wrap_obj_ref(icon)
            case None:
                return None
            case _:
                msg = f'Unknown icon object of {type(self.obj_ref.icon)}'
                raise RuntimeError(msg)

    @property
    def cover(self) -> FileInfo | None:
        """Return the cover of this database as file."""
        cover = self.obj_ref.cover
        return FileInfo.wrap_obj_ref(cover) if cover is not None else None

    @property
    def is_wiki(self) -> bool:
        """Return whether the database is a wiki."""
        # ToDo: Implement using the verification property
        raise NotImplementedError

    @property
    def is_db(self) -> bool:
        """Return whether the object is a database."""
        return True

    def _reflect_schema(self, obj_ref: obj_blocks.Database) -> type[Schema]:
        """Reflection about the database schema."""
        title = str(self)
        cls_name = f'{camel_case(title)}Schema'
        attrs = {
            snake_case(k): Property(k, cast(PropertyType, PropertyType.wrap_obj_ref(v)))
            for k, v in obj_ref.properties.items()
        }
        schema: type[Schema] = type(cls_name, (Schema,), attrs, db_title=title)
        schema.bind_db(self)
        return schema

    def _set_schema(self, schema: type[Schema], *, during_init: bool):
        """Set a custom schema in order to change the Python variables names."""
        self.schema.assert_consistency_with(schema, during_init=during_init)
        schema.bind_db(self)
        self._schema = schema

    @property
    def schema(self) -> type[Schema]:
        """Schema of the database."""
        if not self._schema:
            self._schema = self._reflect_schema(self.obj_ref)
        return self._schema

    @schema.setter
    def schema(self, schema: type[Schema]):
        """Set a custom schema in order to change the Python variables names."""
        self._set_schema(schema, during_init=False)

    @property
    def is_inline(self) -> bool:
        """Return whether the database is inline."""
        return self.obj_ref.is_inline

    def delete(self) -> Self:
        """Delete this database."""
        if not self.is_deleted:
            session = get_active_session()
            session.api.databases.delete(self.obj_ref)
            self._delete_me_from_parent()
        return self

    def restore(self) -> Self:
        """Restore this database."""
        if self.is_deleted:
            session = get_active_session()
            session.api.databases.restore(self.obj_ref)
            if isinstance(self.parent, ChildrenMixin):
                self.parent._children = None  # this forces a new retrieval of children next time
        return self

    def reload(self) -> Self:
        """Reload this database."""
        session = get_active_session()
        self.obj_ref = session.api.databases.retrieve(self.obj_ref.id)
        self.schema._set_obj_refs()
        return self

    @property
    def query(self) -> Query:
        """Return a Query object to build and execute a database query."""
        return Query(database=self)

    def get_all_pages(self) -> View:
        """Retrieve all pages and return a view."""
        return self.query.execute()

    def __len__(self) -> int:
        """Return the number of pages in this database."""
        return len(self.get_all_pages())

    @property
    def is_empty(self) -> bool:
        """Return whether the database is empty."""
        return len(self) == 0

    def __bool__(self) -> bool:
        """Overwrite default behaviour."""
        msg = 'Use .is_empty instead of bool(db) to check if a database is empty.'
        raise RuntimeError(msg)

    def pydantic_model(self) -> BaseModel:
        """Return a Pydantic model for this database."""
        # Check https://github.com/ultimate-notion/ultimate-notion/issues/32 for details
        raise NotImplementedError

    def create_page(self, **kwargs) -> Page:
        """Create a page with properties according to the schema within the corresponding database."""

        # ToDo: let pydantic_model check the kwargs and raise an error if something is wrong
        #       this would also generate a nice error message for the user!
        schema_kwargs = {prop.attr_name: prop for prop in self.schema.get_props()}
        if not set(kwargs).issubset(set(schema_kwargs)):
            add_kwargs = set(kwargs) - set(schema_kwargs)
            msg = f"kwargs {', '.join(add_kwargs)} not defined in schema"
            raise SchemaError(msg)

        schema_dct = {}
        for kwarg, value in kwargs.items():
            prop = schema_kwargs[kwarg]
            prop_value_cls = prop.type.prop_value  # map schema to page property
            # ToDo: Check at that point in case of select option if the option is already defined in Schema!

            if prop_value_cls.readonly:
                raise ReadOnlyPropertyError(prop)

            prop_value = value if isinstance(value, PropertyValue) else prop_value_cls(value)

            schema_dct[schema_kwargs[kwarg].name] = prop_value.obj_ref

        session = get_active_session()
        page_obj = session.api.pages.create(parent=self.obj_ref, properties=schema_dct)
        page = Page.wrap_obj_ref(page_obj)
        session.cache[page.id] = page
        return page

    def to_markdown(self) -> str:
        """Return the content of this database as Markdown."""
        raise NotImplementedError

    def _to_markdown(self) -> str:
        """Return the reference to this database as Markdown."""
        return f'[**🗄️ {self.title}**]({self.block_url})\n'
