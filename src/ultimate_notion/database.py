"""Database object"""
from __future__ import annotations

from textwrap import dedent

from ultimate_notion.obj_api import blocks as obj_blocks
from ultimate_notion.obj_api import objects as objs
from ultimate_notion.text import make_safe_python_name
from ultimate_notion.page import Page
from ultimate_notion.query import QueryBuilder
from ultimate_notion.blocks import DataObject
from ultimate_notion.schema import PageSchema, Column, PropertyType, SchemaError, PropertyValue, ReadOnlyColumnError
from ultimate_notion.utils import decapitalize, dict_diff_str
from ultimate_notion.view import View
from ultimate_notion.text import plain_text


# ToDo: This could also inherit from DataObject[objs.Database], wraps=.... and DataObject is a Generic!
class Database(DataObject):
    """A Notion database object, not a linked databases

    If a custom schema is provided, i.e. specified during creating are the `schema` was set
    then the schemy is verified.

    https://developers.notion.com/docs/working-with-databases
    """

    obj_ref: obj_blocks.Database
    _schema: type[PageSchema] | None = None

    def __init__(self, obj_ref: obj_blocks.Database):
        super().__init__(obj_ref)

    def __str__(self):
        if self.title:
            return self.title
        else:
            return 'Untitled'

    def __repr__(self) -> str:
        cls_name = self.__class__.__name__
        return f"<{cls_name}: '{self!s}' at {hex(id(self))}>"

    def reload(self, *, check_consistency: bool = False):
        """Reload the metadata of the database and update the schema if necessary"""
        new_db = self.session._get_db(self.id)  # circumvent session cache
        if check_consistency and not self.schema.is_consistent_with(new_db.schema):
            msg = f"Schema of database {self.title} no longer consistent with schema after refresh!"
            raise SchemaError(msg)

        self.schema._enrich(new_db.schema)
        # self.obj_ref = new_db.obj_ref

    @property
    def title(self) -> None | str:
        """Return the title of this database as plain text."""
        title = self.obj_ref.title
        if title is None or len(title) == 0:
            return None
        else:
            return plain_text(*title)

    @property
    def description(self) -> list[objs.RichTextObject] | None:
        return self.obj_ref.description

    @property
    def icon(self) -> objs.FileObject | objs.EmojiObject | None:
        return self.obj_ref.icon

    @property
    def cover(self) -> objs.FileObject | None:
        return self.obj_ref.cover

    @property
    def is_wiki(self) -> bool:
        """Is this database a wiki database"""
        # ToDo: Implement using the verification property

    def _reflect_schema(self, obj_ref: obj_blocks.Database) -> type[PageSchema]:
        """Reflection about the database schema"""
        cls_name = f'{make_safe_python_name(self.title).capitalize()}Schema'
        attrs = {
            decapitalize(make_safe_python_name(k)): Column(k, PropertyType.wrap_obj_ref(v))
            for k, v in obj_ref.properties.items()
        }
        schema = type(cls_name, (PageSchema,), attrs, db_title=self.title)
        schema.bind_db(self)
        schema.custom_schema = False
        return schema

    @property
    def schema(self) -> type[PageSchema]:
        if not self._schema:
            self._schema = self._reflect_schema(self.obj_ref)
        return self._schema

    @schema.setter
    def schema(self, schema: type[PageSchema]):
        """Set a custom schema in order to change the Python variables names"""
        if self.schema.is_consistent_with(schema):
            schema.bind_db(self)
            self._schema = schema
        else:
            cols_added, cols_removed, cols_changed = dict_diff_str(self.schema.to_dict(), schema.to_dict())
            msg = f"""Provided schema is not consistent with the current schema of the database:
                      Columns added: {cols_added}
                      Columns removed: {cols_removed}
                      Columns changed: {cols_changed}
                   """
            raise SchemaError(dedent(msg))

    @property
    def url(self) -> str:
        return self.obj_ref.url

    @property
    def archived(self) -> bool:
        return self.obj_ref.archived

    @property
    def is_inline(self) -> bool:
        return self.obj_ref.is_inline

    def delete(self):
        """Delete this database"""
        self.session.api.blocks.delete(self.id)

    def _pages_from_query(self, *, query) -> list[Page]:
        # ToDo: Remove when self.query is implemented!
        return [Page(page_obj) for page_obj in query.execute()]

    def view(self) -> View:
        query = self.session.api.databases.query(self.id)  # ToDo: use self.query when implemented
        pages = [Page(page_obj) for page_obj in query.execute()]
        return View(database=self, pages=pages, query=query)

    def create_page(self, **kwargs) -> Page:
        """Create a page with properties according to the schema within the corresponding database"""
        schema_kwargs = {col.attr_name: col for col in self.schema.get_cols()}
        if not set(kwargs).issubset(set(schema_kwargs)):
            add_kwargs = set(kwargs) - set(schema_kwargs)
            msg = f"kwargs {', '.join(add_kwargs)} not defined in schema"
            raise SchemaError(msg)

        schema_dct = {}
        for kwarg, value in kwargs.items():
            col = schema_kwargs[kwarg]
            prop_value_cls = col.type.prop_value  # map schema to page property
            # ToDo: Check at that point in case of selectoption if the option is already defined in Schema!

            if prop_value_cls.readonly:
                raise ReadOnlyColumnError(col)

            if isinstance(value, PropertyValue):
                prop_value = value
            else:
                prop_value = prop_value_cls(value)

            schema_dct[schema_kwargs[kwarg].name] = prop_value.obj_ref

        page = Page(obj_ref=self.session.api.pages.create(parent=self.obj_ref, properties=schema_dct))
        return page

        return self.schema.create(**kwargs)

    def query(self) -> QueryBuilder:
        """Query a (large) database for pages in a more specific way"""
        return QueryBuilder(self)
