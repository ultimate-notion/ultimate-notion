"""Functionality around defining a database schema

Currently only normal databases, no wiki databases, can be created [1].
Neither the `Unique ID` nor `Status` nor the `Verfication` page property can be set as a database column
in a custom Schema when creating the database.

[1] https://developers.notion.com/docs/working-with-databases#wiki-databases


### Design Principles

A schema is a subclass of `PageShema` that holds `Column` objects with a name and an
actual `PropertyType`, e.g. `Text`, `Number`. A `PropertyType` is a thin wrapper for the
actual `PropertyObject` of the Notion API, which is referenced by `obj_ref`, to allow
more user-friendly definition of a data model, especially if it has relations.

The source of truth is always the `obj_ref` and a `PropertyType` holds only auxilliary
information if actually needed. Since the object references `obj_ref` must always point
to the actual `obj_api.blocks.Database.properties` value if the schema is bound to an database,
the method `_remap_obj_refs` rewires this when a schema is used to create a database.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

import ultimate_notion.obj_api.schema as obj_schema
from ultimate_notion.obj_api.schema import NumberFormat, Function
from ultimate_notion.utils import SList
from ultimate_notion.props import PropertyValue
from ultimate_notion.blocks import DataObject


if TYPE_CHECKING:
    from ultimate_notion.database import Database
    from ultimate_notion.objects import Option
    from ultimate_notion.page import Page

# Todo: Move the functionality from the PyDantic types in here and elimate the __compose__


class SchemaError(Exception):
    """Raised when there are issues with the schema of a database."""

    def __init__(self, message):
        """Initialize the `SchemaError` with a supplied message."""
        super().__init__(message)


class SchemaNotBoundError(SchemaError):
    """Raised when the schema is not bound to a database."""

    def __init__(self, schema: type[PageSchema]):
        self.schema = schema
        msg = f"Schema {schema.__name__} is not bound to any database"
        super().__init__(msg)


class ReadOnlyColumnError(SchemaError):
    """Raised when a read-only columns tries to be written to."""

    def __init__(self, col: Column):
        self.col = col
        msg = f"Argument {col.attr_name} refers to the read-only column '{col.name}' of type {col.type}"
        super().__init__(msg)


class PageSchema:
    """Base class for the schema of a database."""

    db_title: str
    # ToDo: if custom_schema is True don't allow changing the schema otherwise it's fine
    custom_schema: bool = True
    _database: Database | None = None

    def __init_subclass__(cls, db_title: str, **kwargs: Any):  # noqa: A002
        cls.db_title = db_title
        super().__init_subclass__(**kwargs)

    @classmethod
    def from_dict(cls, schema_dct: dict[str, PropertyType], db_title: str | None = None) -> PageSchema:
        """Creation of a schema from a dictionary for easy support of dynamically created schemas"""
        # ToDo: Implement

    @classmethod
    def create(cls, **kwargs) -> Page:
        # ToDo: Avoid this here by moving the method into database create_page where it makes more sense
        from ultimate_notion.page import Page

        """Create a page with properties according to the schema within the corresponding database"""
        schema_kwargs = {col.attr_name: col for col in cls.get_cols()}
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

        db = cls.get_db()
        page = Page(obj_ref=db.session.api.pages.create(parent=db.obj_ref, properties=schema_dct))
        return page

    @classmethod
    def reload(cls, *, check_consistency: bool = False):
        db = cls.get_db()
        db.reload(check_consistency=check_consistency)

    @classmethod
    def get_cols(cls) -> list[Column]:
        """Return all columns of this schema"""
        return [col for col in cls.__dict__.values() if isinstance(col, Column)]

    @classmethod
    def to_dict(cls) -> dict[str, PropertyType]:
        return {col.name: col.type for col in cls.get_cols()}

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
        if cls.is_bound():
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


class PropertyType:
    """Base class for Notion property objects.

    Used to map high-level objects to low-level Notion-API objects
    """

    allowed_at_creation = True  # wether the Notion API allows new database with a column of that type
    obj_ref: obj_schema.PropertyObject
    prop_ref: Column

    _obj_api_map: ClassVar[dict[type[obj_schema.PropertyObject], type[PropertyType]]] = {}
    _has_compose: ClassVar[dict[type[obj_schema.PropertyObject], bool]] = {}

    def __new__(cls, *args, **kwargs) -> PropertyType:
        # Needed for wrap_obj_ref and its call to __new__ to work!
        return super().__new__(cls)

    def __init_subclass__(cls, type: type[obj_schema.PropertyObject], **kwargs: Any):  # noqa: A002
        super().__init_subclass__(**kwargs)
        cls._obj_api_map[type] = cls
        cls._has_compose[type] = hasattr(type, '__compose__')

    @classmethod
    def wrap_obj_ref(cls, obj_ref: obj_schema.PropertyObject) -> PropertyType:
        prop_type_cls = cls._obj_api_map[type(obj_ref)]
        prop_type = prop_type_cls.__new__(prop_type_cls)
        prop_type.obj_ref = obj_ref
        return prop_type

    @property
    def prop_value(self) -> type[PropertyValue]:
        """Return the corresponding PropertyValue"""
        return PropertyValue._type_value_map[self.obj_ref.type]

    @property
    def readonly(self) -> bool:
        """Return if this property type is read-only"""
        return self.prop_value.readonly

    @property
    def _obj_api_map_inv(self) -> dict[type[PropertyType], type[obj_schema.PropertyObject]]:
        return {v: k for k, v in self._obj_api_map.items()}

    def __init__(self, *args, **kwargs):
        obj_api_type = self._obj_api_map_inv[self.__class__]
        if hasattr(obj_api_type, "__compose__"):
            self.obj_ref = obj_api_type.__compose__(*args, **kwargs)
        else:
            self.obj_ref = obj_api_type(*args, **kwargs)

    def __eq__(self, other: PropertyType):
        return self.obj_ref.type == other.obj_ref.type and self.obj_ref() == self.obj_ref()


class Column:
    """Column with a name and a certain Property Type for defining a Notion database schema

    This is implemented as a descriptor.
    """

    _name: str
    _type: PropertyType  # noqa: A003
    # properties below are set by __set_name__
    _schema: type[PageSchema]
    _attr_name: str  # Python attribute name of the property in the schema

    def __init__(self, name: str, type: PropertyType) -> None:
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
    def type(self) -> PropertyType:
        return self._type

    @type.setter
    def type(self, new_type: PropertyType):
        raise NotImplementedError

    @property
    def attr_name(self) -> str:
        return self._attr_name


class Title(PropertyType, type=obj_schema.Title):
    """Defines the mandatory title column in a database"""


class Text(PropertyType, type=obj_schema.RichText):
    """Defines a text column in a database"""


class Number(PropertyType, type=obj_schema.Number):
    """Defines a number column in a database"""

    def __init__(self, number_format: NumberFormat):
        super().__init__(number_format)


class Select(PropertyType, type=obj_schema.Select):
    """Defines a select column in a database"""

    def __init__(self, options: list[Option]):
        options = [option.obj_ref for option in options]
        super().__init__(options)


class MultiSelect(PropertyType, type=obj_schema.MultiSelect):
    """Defines a multi-select column in a database"""

    def __init__(self, options: list[Option]):
        options = [option.obj_ref for option in options]
        super().__init__(options)


class Status(PropertyType, type=obj_schema.Status):
    """Defines a status column in a database"""

    allowed_at_creation = False


class Date(PropertyType, type=obj_schema.Date):
    """Defines a date column in a database"""


class People(PropertyType, type=obj_schema.People):
    """Defines a people column in a database"""


class Files(PropertyType, type=obj_schema.Files):
    """Defines a files column in a database"""


class Checkbox(PropertyType, type=obj_schema.Checkbox):
    """Defines a checkbox column in database"""


class Email(PropertyType, type=obj_schema.Email):
    """Defines an e-mail column in a database"""


class URL(PropertyType, type=obj_schema.URL):
    """Defines a URL column in a database"""


class PhoneNumber(PropertyType, type=obj_schema.PhoneNumber):
    """Defines a phone number column in a database"""


class Formula(PropertyType, type=obj_schema.Formula):
    """Defines a formula column in a database"""

    def __init__(self, expression: str):
        # ToDo: Replace with call to `build` later
        super().__init__(expression)


class RelationError(SchemaError):
    """Error if a Relation cannot be initialised"""


class Relation(PropertyType, type=obj_schema.Relation):
    """Relation to another database"""

    obj_ref: obj_schema.Relation | None = None
    _schema: PageSchema | None = None
    _two_way_prop: Column | None = None

    def __init__(self, schema: type[PageSchema] | None = None, *, two_way_prop: Column | None = None):
        if two_way_prop and not schema:
            raise RuntimeError("`schema` needs to be provided if `two_way_prop` is set")
        if isinstance(schema, type):
            schema = schema()
        self._schema = schema
        self._two_way_prop = two_way_prop

    @property
    def schema(self) -> type[PageSchema] | None:
        if self._schema:
            return self._schema
        elif self.prop_ref._schema.is_bound():
            db = self.prop_ref._schema._database
            return db.session.get_db(self.obj_ref.relation.database_id).schema
        else:
            return self._schema

    @property
    def is_two_way(self) -> bool:
        return self.two_way_prop is not None

    @property
    def two_way_prop(self) -> Column:
        if self.obj_ref and isinstance(self.obj_ref.relation, obj_schema.DualPropertyRelation):
            # ToDo: This should actually return a property! We might have to resolve things here.
            return self.obj_ref.relation.dual_property.synced_property_name
        else:
            return self._two_way_prop

    def make_obj_ref(self):
        try:
            db = self.schema.get_db()
        except SchemaNotBoundError as e:
            msg = f"A database with schema '{self.schema.__name__}' needs to be created first!"
            raise RelationError(msg) from e

        if self.schema:
            if self.two_way_prop:
                self.obj_ref = obj_schema.DualPropertyRelation[db.id]
            else:
                self.obj_ref = obj_schema.SinglePropertyRelation[db.id]

    def _init_backward_relation(self):
        if not isinstance(self.obj_ref.relation, obj_schema.DualPropertyRelation):
            msg = f"Trying to inialize backward relation for forward relation {self.prop_ref.name}"
            raise SchemaError(msg)

        obj_synced_property_name = self.obj_ref.relation.dual_property.synced_property_name
        two_wap_prop_name = self._two_way_prop.name
        if obj_synced_property_name != two_wap_prop_name:
            # change the old default name in the target schema what was passed during initialization
            other_db = self.schema.get_db()
            prop_id = self.obj_ref.relation.dual_property.synced_property_id
            schema_dct = {prop_id: obj_schema.RenameProp(name=two_wap_prop_name)}
            other_db.session.api.databases.update(dbref=other_db.obj_ref, schema=schema_dct)
            other_db.schema._set_obj_refs()

            our_db = self.prop_ref._schema.get_db()
            our_db.session.api.databases.update(dbref=our_db.obj_ref, schema={})  # sync obj_ref
            our_db.schema._set_obj_refs()


class RollupError(SchemaError):
    """Error if definition of rollup is wrong"""


class Rollup(PropertyType, type=obj_schema.Rollup):
    """Defines the rollup column in a database"""

    def __init__(self, relation: Column, property: Column, calculate: Function):
        if not isinstance(relation.type, Relation):
            msg = f"Relation {relation} must be of type Relation"
            raise RollupError(msg)
        # ToDo: One could check here if property really is a property in the database where relation points to
        super().__init__(relation.name, property.name, calculate)


class CreatedTime(PropertyType, type=obj_schema.CreatedTime):
    """Defines the created-time column in a database"""


class CreatedBy(PropertyType, type=obj_schema.CreatedBy):
    """Defines the created-by column in a database"""


class LastEditedBy(PropertyType, type=obj_schema.LastEditedBy):
    """Defines the last-edited-by column in a database"""


class LastEditedTime(PropertyType, type=obj_schema.LastEditedTime):
    """Defines the last-edited-time column in a database"""


class ID(PropertyType, type=obj_schema.UniqueID):
    """Defines a unique ID column in a database"""

    allowed_at_creation = False


class Verification(PropertyType, type=obj_schema.Verification):
    """Defines a unique ID column in a database"""

    allowed_at_creation = False
