"""Functionality around defining a database schema


### Design Principles

A schema is a subclass of `PageShema` that holds `Property` objects with a name and an
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
from ultimate_notion.obj_api.schema import NumberFormat
from ultimate_notion.obj_api.text import Color
from ultimate_notion.utils import SList
from ultimate_notion.page import Page
from ultimate_notion.props import PropertyValue
from ultimate_notion.blocks import Record

if TYPE_CHECKING:
    from ultimate_notion.database import Database

# Todo: Move the functionality from the PyDantic types in here and elimate the __compose__


class SchemaError(Exception):
    """Raised when there are issues with the schema of a database."""

    def __init__(self, message):
        """Initialize the `SchemaError` with a supplied message."""
        super().__init__(message)


class SchemaNotBoundError(SchemaError):
    """Raised when the schema is not bound to a database."""

    def __init__(self, schema: type[PageSchema]):
        msg = f"Schema {schema.__name__} is not bound to any database"
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
    def create(cls, **kwargs) -> Page:
        """Create a page with properties according to the schema within the corresponding database"""
        schema_kwargs = {attr: prop for attr, prop in cls.__dict__.items() if isinstance(prop, Property)}
        if not set(kwargs).issubset(set(schema_kwargs)):
            add_kwargs = set(kwargs) - set(schema_kwargs)
            msg = f"kwargs {', '.join(add_kwargs)} not defined in schema"
            raise SchemaError(msg)

        schema_dct = {}
        for kwarg, value in kwargs.items():
            prop_type_cls = schema_kwargs[kwarg].type
            prop_value_cls = PropertyValue._get_value_from_type(prop_type_cls)
            if isinstance(value, Record):  # unwrap relations
                value = value.obj_ref

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
    def get_props(cls) -> list[Property]:
        """Return all properties of this schema"""
        return [prop for prop in cls.__dict__.values() if isinstance(prop, Property)]

    @classmethod
    def to_dict(cls) -> dict[str, PropertyType]:
        return {prop.name: prop.type for prop in cls.get_props()}

    @classmethod
    def get_title_prop(cls) -> Property:
        """Returns the title property"""
        return SList(prop for prop in cls.get_props() if isinstance(prop.type, Title)).item()

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

    obj_ref: obj_schema.PropertyObject
    prop_ref: Property

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


class Property:
    """Property for defining a Notion database schema

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
    """Mandatory Title property"""


class Text(PropertyType, type=obj_schema.RichText):
    """Text property"""


class Number(PropertyType, type=obj_schema.Number):
    """Mandatory Title property"""

    def __init__(self, number_format: NumberFormat):
        super().__init__(number_format)


class SelectOption(PropertyType, type=obj_schema.SelectOption):
    """Option for select & multi-select property"""

    def __init__(self, name, color=Color.DEFAULT):
        """Create a `SelectOption` object from the given name and color."""
        super().__init__(name=name, color=color)


class SingleSelect(PropertyType, type=obj_schema.Select):
    """Single selection property"""

    def __init__(self, options: list[SelectOption]):
        options = [option.obj_ref for option in options]
        super().__init__(options)


class MultiSelect(PropertyType, type=obj_schema.MultiSelect):
    """Multi selection property"""


class Status(PropertyType, type=obj_schema.Status):
    """Status property"""


class Date(PropertyType, type=obj_schema.Date):
    """Date property"""


class People(PropertyType, type=obj_schema.People):
    """People property"""


class Files(PropertyType, type=obj_schema.Files):
    """Files property"""


class Checkbox(PropertyType, type=obj_schema.Checkbox):
    """Checkbox property"""


class Email(PropertyType, type=obj_schema.Email):
    """E-Mail property"""


class URL(PropertyType, type=obj_schema.URL):
    """URL property"""


class PhoneNumber(PropertyType, type=obj_schema.PhoneNumber):
    """Phone number property"""


class Formula(PropertyType, type=obj_schema.Formula):
    """Formula Property"""


class RelationError(SchemaError):
    """Error if a Relation Property cannot be initialised"""

    pass


class Relation(PropertyType, type=obj_schema.Relation):
    obj_ref: obj_schema.Relation | None = None
    _schema: PageSchema | None = None
    _two_way_prop: Property | None = None

    def __init__(self, schema: type[PageSchema] | None = None, *, two_way_prop: Property | None = None):
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
    def two_way_prop(self) -> Property:
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


class Rollup(PropertyType, type=obj_schema.Rollup):
    """Defines the rollup configuration for a database property."""

    # ToDo: Needs a constructor?


class CreatedTime(PropertyType, type=obj_schema.CreatedTime):
    """Defines the created-time configuration for a database property."""


class CreatedBy(PropertyType, type=obj_schema.CreatedBy):
    """Defines the created-by configuration for a database property."""


class LastEditedBy(PropertyType, type=obj_schema.LastEditedBy):
    """Defines the last-edited-by configuration for a database property."""


class LastEditedTime(PropertyType, type=obj_schema.LastEditedTime):
    """Defines the last-edited-time configuration for a database property."""
