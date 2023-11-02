"""Functionality around defining a database schema

Currently only normal databases, no wiki databases, can be created [1].
Neither the `Unique ID` nor `Status` nor the `Verfication` page property can be set as a database column
in a custom Schema when creating the database.

[1] https://developers.notion.com/docs/working-with-databases#wiki-databases


### Design Principles

A schema is a subclass of `PageShema` that holds `Column` objects with a name and an
actual `PropertyType`, e.g. `Text`, `Number`.

The source of truth is always the `obj_ref` and a `PropertyType` holds only auxilliary
information if actually needed. Since the object references `obj_ref` must always point
to the actual `obj_api.blocks.Database.properties` value if the schema is bound to an database,
the method `_remap_obj_refs` rewires this when a schema is used to create a database.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

from tabulate import tabulate

import ultimate_notion.obj_api.schema as obj_schema
from ultimate_notion.obj_api.schema import Function, NumberFormat
from ultimate_notion.objects import RichText
from ultimate_notion.props import PropertyValue
from ultimate_notion.utils import SList, Wrapper, get_active_session, is_notebook

if TYPE_CHECKING:
    from ultimate_notion.database import Database
    from ultimate_notion.objects import Option
    from ultimate_notion.page import Page

# Todo: Move the functionality from the PyDantic types in here
T = TypeVar('T', bound=obj_schema.PropertyType)


class SchemaError(Exception):
    """Raised when there are issues with the schema of a database."""

    def __init__(self, message):
        """Initialize the `SchemaError` with a supplied message."""
        super().__init__(message)


class SchemaNotBoundError(SchemaError):
    """Raised when the schema is not bound to a database."""

    def __init__(self, schema: type[PageSchema]):
        self.schema = schema
        msg = f'Schema {schema.__name__} is not bound to any database'
        super().__init__(msg)


class ReadOnlyColumnError(SchemaError):
    """Raised when a read-only columns tries to be written to."""

    def __init__(self, col: Column):
        self.col = col
        msg = f"Argument {col.attr_name} refers to the read-only column '{col.name}' of type {col.type}"
        super().__init__(msg)


class PageSchema:
    """Base class for the schema of a database."""

    db_title: RichText | None
    db_desc: RichText | None
    _database: Database | None = None

    def __init_subclass__(cls, db_title: RichText | str | None, **kwargs: Any):
        if isinstance(db_title, str):
            db_title = RichText.from_plain_text(db_title)
        cls.db_title = db_title

        cls.db_desc = RichText.from_plain_text(cls.__doc__) if cls.__doc__ is not None else None
        super().__init_subclass__(**kwargs)

    @classmethod
    def from_dict(
        cls, schema_dct: dict[str, PropertyType], db_title: str | None = None, db_desc: str | None = None
    ) -> PageSchema:
        """Creation of a schema from a dictionary for easy support of dynamically created schemas"""
        # ToDo: Implement
        raise NotImplementedError

    @classmethod
    def create(cls, **kwargs) -> Page:
        """Create a page using this schema with a bound database"""
        return cls.get_db().create_page(**kwargs)

    @classmethod
    def get_cols(cls) -> list[Column]:
        """Return all columns of this schema"""
        return [col for col in cls.__dict__.values() if isinstance(col, Column)]

    @classmethod
    def get_col(cls, col_name: str) -> Column:
        return SList([col for col in cls.get_cols() if col.name == col_name]).item()

    @classmethod
    def to_dict(cls) -> dict[str, PropertyType]:
        return {col.name: col.type for col in cls.get_cols()}

    @classmethod
    def show(cls, tablefmt: str | None) -> str:
        """Display the schema in a given table format

        Some table formats:
        - plain: no pseudographics
        - simple: Pandoc's simple table, i.e. only dashes to separate header from content
        - github: GitHub flavored Markdown
        - simple_grid: uses dashes & pipes to separate cells
        - html: standard html markup

        Find more tables formats under: https://github.com/astanin/python-tabulate#table-format
        """
        if tablefmt is None:
            tablefmt = 'html' if is_notebook() else 'simple'

        headers = ['Name', 'Property', 'Attribute']
        rows = []
        for col in cls.get_cols():
            rows.append((col.name, col.type, col.attr_name))

        return tabulate(rows, headers=headers, tablefmt=tablefmt)

    @classmethod
    def _repr_html_(cls) -> str:  # noqa: PLW3201
        """Called by Jupyter Lab automatically to display this schema"""
        return cls.show(tablefmt='html')

    @classmethod
    def get_title_prop(cls) -> Column:
        """Returns the title property"""
        return SList(col for col in cls.get_cols() if isinstance(col.type, Title)).item()

    @classmethod
    def is_consistent_with(cls, other_schema: type[PageSchema]) -> bool:
        """Is this schema consistent with another ignoring backward relations if not in other schema"""
        own_schema_dct = cls.to_dict()
        other_schema_dct = other_schema.to_dict()

        if own_schema_dct == other_schema_dct:
            # backward relation was initialized in the other schema
            return True

        other_schema_no_backrels_dct = {
            name: prop_type
            for name, prop_type in other_schema_dct.items()
            if not (isinstance(prop_type, Relation) and not prop_type.schema)
        }

        if other_schema_no_backrels_dct == own_schema_dct:
            # backward relation was not yet initialised in the other schema (during the creation of the data model)
            return True

        return False

    @classmethod
    def get_db(cls) -> Database:
        if cls.is_bound() and cls._database:
            return cls._database
        else:
            raise SchemaNotBoundError(cls)

    @classmethod
    def bind_db(cls, db: Database):
        """Bind the PageSchema to the corresponding database for back-reference"""
        cls._database = db
        cls._set_obj_refs()

    @classmethod
    def is_bound(cls) -> bool:
        """Returns if the schema is bound to a database"""
        return cls._database is not None

    @classmethod
    def _init_fwd_rels(cls):
        """Initialise all forward relations assuming that the databases of related schemas were created"""
        for relation in (prop_type for prop_type in cls.to_dict().values() if isinstance(prop_type, Relation)):
            if relation.schema:
                relation.make_obj_ref()

    @classmethod
    def _init_bwd_rels(cls):
        """Update the default property name in case of a two-way relation in the target schema.

        By default the property in the target schema is named "Related to <this_database> (<this_field>)"
        which is then set to the name specified as backward relation.
        """
        for prop_type in cls.to_dict().values():
            if isinstance(prop_type, Relation) and prop_type.is_two_way:
                prop_type._init_backward_relation()

    @classmethod
    def _set_obj_refs(cls):
        """Map obj_refs from the properties of the schema to obj_ref.properties of the bound database"""
        db_props_dct = cls.get_db().obj_ref.properties
        for prop_name, prop_type in cls.to_dict().items():
            obj_ref = db_props_dct.get(prop_name)
            if obj_ref:
                prop_type.obj_ref = obj_ref


class PropertyType(Wrapper[T], wraps=obj_schema.PropertyType):
    """Base class for Notion property objects.

    Used to map high-level objects to low-level Notion-API objects
    """

    allowed_at_creation = True  # wether the Notion API allows new database with a column of that type
    prop_ref: Column

    @property
    def prop_value(self) -> type[PropertyValue]:
        """Return the corresponding PropertyValue"""
        return PropertyValue._type_value_map[self.obj_ref.type]

    @property
    def readonly(self) -> bool:
        """Return if this property type is read-only"""
        return self.prop_value.readonly

    def __init__(self, *args, **kwargs):
        obj_api_type = self._obj_api_map_inv[self.__class__]
        self.obj_ref = obj_api_type.build(*args, **kwargs)

    def __eq__(self, other: object):
        if not isinstance(other, PropertyType):
            return NotImplemented
        return self.obj_ref.type == other.obj_ref.type and self.obj_ref.value == self.obj_ref.value

    def __hash__(self) -> int:
        return hash(self.obj_ref.type) + hash(self.obj_ref.value)

    def __repr__(self) -> str:
        cls_name = self.__class__.__name__
        return f"<PropertyType: '{cls_name}' at {hex(id(self))}>"

    def __str__(self) -> str:
        return self.__class__.__name__


class Column:
    """Column with a name and a certain Property Type for defining a Notion database schema

    This is implemented as a descriptor.
    """

    _name: str
    _type: PropertyType
    # properties below are set by __set_name__
    _schema: type[PageSchema]
    _attr_name: str  # Python attribute name of the property in the schema

    def __init__(self, name: str, type: PropertyType) -> None:  # noqa: A002
        self._name = name
        self._type = type

    def __set_name__(self, owner: type[PageSchema], name: str):
        self._schema = owner
        self._attr_name = name
        self._type.prop_ref = self  # link back to allow access to _schema, _py_name e.g. for relations

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, new_name: str):
        raise NotImplementedError

    @property
    def type(self) -> PropertyType:  # noqa: A003
        return self._type

    @type.setter
    def type(self, new_type: PropertyType):  # noqa: A003
        raise NotImplementedError

    @property
    def attr_name(self) -> str:
        return self._attr_name


class Title(PropertyType[obj_schema.Title], wraps=obj_schema.Title):
    """Defines the mandatory title column in a database"""


class Text(PropertyType[obj_schema.RichText], wraps=obj_schema.RichText):
    """Defines a text column in a database"""


class Number(PropertyType[obj_schema.Number], wraps=obj_schema.Number):
    """Defines a number column in a database"""

    def __init__(self, number_format: NumberFormat):
        super().__init__(number_format)


class Select(PropertyType[obj_schema.Select], wraps=obj_schema.Select):
    """Defines a select column in a database"""

    def __init__(self, options: list[Option]):
        options = [option.obj_ref for option in options]
        super().__init__(options)


class MultiSelect(PropertyType[obj_schema.MultiSelect], wraps=obj_schema.MultiSelect):
    """Defines a multi-select column in a database"""

    def __init__(self, options: list[Option]):
        options = [option.obj_ref for option in options]
        super().__init__(options)


class Status(PropertyType[obj_schema.Status], wraps=obj_schema.Status):
    """Defines a status column in a database"""

    allowed_at_creation = False  # ToDo: Recheck if this holds really true when the default options are passed!


class Date(PropertyType[obj_schema.Date], wraps=obj_schema.Date):
    """Defines a date column in a database"""


class People(PropertyType[obj_schema.People], wraps=obj_schema.People):
    """Defines a people column in a database"""


class Files(PropertyType[obj_schema.Files], wraps=obj_schema.Files):
    """Defines a files column in a database"""


class Checkbox(PropertyType[obj_schema.Checkbox], wraps=obj_schema.Checkbox):
    """Defines a checkbox column in database"""


class Email(PropertyType[obj_schema.Email], wraps=obj_schema.Email):
    """Defines an e-mail column in a database"""


class URL(PropertyType[obj_schema.URL], wraps=obj_schema.URL):
    """Defines a URL column in a database"""


class PhoneNumber(PropertyType[obj_schema.PhoneNumber], wraps=obj_schema.PhoneNumber):
    """Defines a phone number column in a database"""


class Formula(PropertyType[obj_schema.Formula], wraps=obj_schema.Formula):
    """Defines a formula column in a database"""

    def __init__(self, expression: str):
        # ToDo: Replace with call to `build` later
        super().__init__(expression)


class RelationError(SchemaError):
    """Error if a Relation cannot be initialised"""


class Relation(PropertyType[obj_schema.Relation], wraps=obj_schema.Relation):
    """Relation to another database"""

    _schema: type[PageSchema] | None = None
    _two_way_prop: Column | None = None

    def __init__(self, schema: type[PageSchema] | None = None, *, two_way_prop: Column | None = None):
        if two_way_prop and not schema:
            msg = '`schema` needs to be provided if `two_way_prop` is set'
            raise RuntimeError(msg)
        self._schema = schema
        self._two_way_prop = two_way_prop

    @property
    def schema(self) -> type[PageSchema] | None:
        """Schema of the relation database"""
        if self._schema:
            return self._schema
        elif self.prop_ref._schema.is_bound():
            db = self.prop_ref._schema._database
            session = get_active_session()
            return session.get_db(self.obj_ref.relation.database_id).schema if db else None
        else:
            return None

    @property
    def is_two_way(self) -> bool:
        return self.two_way_prop is not None

    @property
    def two_way_prop(self) -> Column | None:
        if self._two_way_prop:
            return self._two_way_prop
        elif (
            hasattr(self, 'obj_ref')
            and self.schema
            and isinstance(self.obj_ref.relation, obj_schema.DualPropertyRelation)
        ):
            prop_name = self.obj_ref.relation.dual_property.synced_property_name
            return self.schema.get_col(prop_name) if prop_name else None
        else:
            return None

    def make_obj_ref(self):
        try:
            db = self.schema.get_db()
        except SchemaNotBoundError as e:
            msg = f"A database with schema '{self.schema.__name__}' needs to be created first!"
            raise RelationError(msg) from e

        if self.two_way_prop:
            self.obj_ref = obj_schema.DualPropertyRelation.build(db.id)
        else:
            self.obj_ref = obj_schema.SinglePropertyRelation.build(db.id)

    def _init_backward_relation(self):
        if not isinstance(self.obj_ref.relation, obj_schema.DualPropertyRelation):
            msg = f'Trying to inialize backward relation for forward relation {self.prop_ref.name}'
            raise SchemaError(msg)

        obj_synced_property_name = self.obj_ref.relation.dual_property.synced_property_name
        two_wap_prop_name = self._two_way_prop.name
        if obj_synced_property_name != two_wap_prop_name:
            session = get_active_session()

            # change the old default name in the target schema to what was passed during initialization
            other_db = self.schema.get_db()
            prop_id = self.obj_ref.relation.dual_property.synced_property_id
            schema_dct = {prop_id: obj_schema.RenameProp(name=two_wap_prop_name)}
            session.api.databases.update(db=other_db.obj_ref, schema=schema_dct)
            other_db.schema._set_obj_refs()

            our_db = self.prop_ref._schema.get_db()
            session.api.databases.update(db=our_db.obj_ref, schema={})  # sync obj_ref
            our_db.schema._set_obj_refs()


class RollupError(SchemaError):
    """Error if definition of rollup is wrong"""


class Rollup(PropertyType[obj_schema.Rollup], wraps=obj_schema.Rollup):
    """Defines the rollup column in a database"""

    def __init__(self, relation: Column, property: Column, calculate: Function):  # noqa: A002
        if not isinstance(relation.type, Relation):
            msg = f'Relation {relation} must be of type Relation'
            raise RollupError(msg)
        # ToDo: One could check here if property really is a property in the database where relation points to
        super().__init__(relation.name, property.name, calculate)


class CreatedTime(PropertyType[obj_schema.CreatedTime], wraps=obj_schema.CreatedTime):
    """Defines the created-time column in a database"""


class CreatedBy(PropertyType[obj_schema.CreatedBy], wraps=obj_schema.CreatedBy):
    """Defines the created-by column in a database"""


class LastEditedBy(PropertyType[obj_schema.LastEditedBy], wraps=obj_schema.LastEditedBy):
    """Defines the last-edited-by column in a database"""


class LastEditedTime(PropertyType[obj_schema.LastEditedTime], wraps=obj_schema.LastEditedTime):
    """Defines the last-edited-time column in a database"""


class ID(PropertyType[obj_schema.UniqueID], wraps=obj_schema.UniqueID):
    """Defines a unique ID column in a database"""

    allowed_at_creation = False


class Verification(PropertyType[obj_schema.Verification], wraps=obj_schema.Verification):
    """Defines a unique ID column in a database"""

    allowed_at_creation = False
