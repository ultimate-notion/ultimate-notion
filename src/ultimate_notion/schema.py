"""Functionality around defining a database schema.

Currently only normal databases, no wiki databases, can be created [1].
Neither the `Unique ID` nor `Status` nor the `Verfication` page property can be set as a database property
in a custom Schema when creating the database.

[1] https://developers.notion.com/docs/working-with-databases#wiki-databases


### Design Principles

A schema is a subclass of `Schema` that holds `Property` objects with a name and an
actual `PropertyType`, e.g. `Text`, `Number`.

The source of truth is always the `obj_ref` and a `PropertyType` holds only auxilliary
information if actually needed. Since the object references `obj_ref` must always point
to the actual `obj_api.blocks.Database.properties` value if the schema is bound to an database,
the method `_set_obj_refs` rewires this when a schema is used to create a database.
"""

from __future__ import annotations

from abc import ABCMeta
from collections import Counter
from collections.abc import Iterator
from functools import partial
from textwrap import dedent
from typing import TYPE_CHECKING, Annotated, Any, TypeVar, cast

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, create_model, field_validator
from tabulate import tabulate

import ultimate_notion.obj_api.schema as obj_schema
from ultimate_notion import rich_text
from ultimate_notion.core import Wrapper, get_active_session, get_repr
from ultimate_notion.errors import (
    EmptyListError,
    InvalidAPIUsageError,
    MultipleItemsError,
    RelationError,
    RollupError,
    SchemaError,
    SchemaNotBoundError,
)
from ultimate_notion.obj_api.schema import AggFunc, NumberFormat
from ultimate_notion.obj_api.schema import PropertyType as obj_PropertyType
from ultimate_notion.obj_api.schema import Relation as obj_Relation
from ultimate_notion.option import Option, OptionGroup, OptionNS
from ultimate_notion.props import PropertyValue
from ultimate_notion.utils import SList, dict_diff_str, is_notebook

if TYPE_CHECKING:
    from ultimate_notion.database import Database
    from ultimate_notion.page import Page
from ultimate_notion.option import compare_options

T = TypeVar('T', bound=obj_schema.PropertyType)


class PropertyType(Wrapper[T], wraps=obj_schema.PropertyType):
    """Base class for Notion property objects.

    Property types define the value types of properties in a database, e.g. number, date, text, etc.
    """

    obj_ref: T
    """Reference to the low-level object representation of this property type"""
    allowed_at_creation = True
    """If the Notion API allows to create a new database with a property of this type"""
    prop_ref: Property | None = None
    """Back reference to the property having this type"""

    @property
    def id(self) -> str | None:
        """Return identifier of this property type."""
        return self.obj_ref.id

    @property
    def name(self) -> str:
        """Return name of this property type."""
        return self.obj_ref.name

    @property
    def prop_value(self) -> type[PropertyValue]:
        """Return the corresponding property value of this property type."""
        return PropertyValue._type_value_map[self.obj_ref.type]

    @property
    def readonly(self) -> bool:
        """Return if this property type is read-only."""
        return self.prop_value.readonly

    @property
    def _is_init(self) -> bool:
        """Determines if the property type is already initialized"""
        return hasattr(self, 'obj_ref')

    def _update_prop(self, name: str, prop_type: obj_PropertyType) -> obj_PropertyType:
        """Update the attributes of this property type from a schema."""
        if self.prop_ref is None:
            msg = 'PropertyType must be bound to a Property before updating attributes.'
            raise SchemaError(msg)
        db = self.prop_ref._schema.get_db()
        session = get_active_session()
        session.api.databases.update(db=db.obj_ref, schema={name: prop_type})
        return db.obj_ref.properties[name]

    def __init__(self, *args, **kwargs):
        obj_api_type = self._obj_api_map_inv[self.__class__]
        self.obj_ref = obj_api_type.build(*args, **kwargs)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PropertyType):
            return NotImplemented
        return self.obj_ref.type == other.obj_ref.type and self.obj_ref.value == self.obj_ref.value

    def __hash__(self) -> int:
        return hash(self.obj_ref.type) + hash(self.obj_ref.value)

    def __repr__(self) -> str:
        return get_repr(self, name='PropertyType', desc=self.__class__.__name__)

    def __str__(self) -> str:
        return self.__class__.__name__


class Property:
    """Database property/column with a name and a Notion property type.

    A schema is a collection of properties that define the structure of a database.
    This is implemented as a descriptor in Python.
    """

    # TODO: Do we really need this class? It is only used to set the name and type of a property!

    _name: str
    _type: PropertyType
    # properties below are set by __set_name__
    _schema: type[Schema]
    _attr_name: str  # Python attribute name of the property in the schema

    def __init__(self, name: str, type: PropertyType) -> None:  # noqa: A002
        self._name = name
        self._type = type

    def __set_name__(self, owner: type[Schema], name: str):
        self._schema = owner
        self._attr_name = name
        self._type.prop_ref = self  # link back to allow access to _schema, _py_name e.g. for relations

    def __repr__(self) -> str:
        return get_repr(self, name='Property', desc=self.type)

    def _update_prop(self, new_name: str | None) -> None:
        """Update the name of this property in the schema or delete it."""
        if self._schema is None:
            msg = 'Property must be bound to a Schema.'
            raise SchemaError(msg)
        db = self._schema.get_db()
        session = get_active_session()
        schema: dict[str, obj_schema.RenameProp | None] = (
            {self._name: None} if new_name is None else {self._name: obj_schema.RenameProp(name=new_name)}
        )
        session.api.databases.update(db=db.obj_ref, schema=schema)
        if new_name is None:
            delattr(self._schema, self._attr_name)
        else:
            self._name = new_name
        self._schema._set_obj_refs()

    def delete(self) -> None:
        """Delete this property from the schema."""
        self._update_prop(None)

    @property
    def name(self) -> str:
        """Return the name of this property."""
        return self._name

    @name.setter
    def name(self, new_name: str):
        """Set the name of this property."""
        self._update_prop(new_name)

    @property
    def type(self) -> PropertyType:
        """Return the property type of this property."""
        return self._type

    @type.setter
    def type(self, new_type: PropertyType):
        """Set the property type of this property."""
        raise NotImplementedError

    @property
    def attr_name(self) -> str:
        """Return the Python attribute name of the property in the schema."""
        return self._attr_name


class SchemaType(ABCMeta):
    """Metaclass for the schema of a database.

    This makes the schema class itself more user-friendly by providing a custom `__repr__` method
    and letting it behave like a dictionary for the properties although it is a class, not an instance.
    """

    # ToDo: When mypy is smart enough to understand metaclasses, we can remove the `type: ignore` comments.

    def __repr__(cls: type[Schema]) -> str:  # type: ignore[misc]
        # We can only overwrite __repr__ for a class in a metaclass
        return cls.as_table(tablefmt='simple')

    def __getitem__(cls: type[Schema], prop_name: str) -> PropertyType:  # type: ignore[misc]
        return cls.get_prop(prop_name).type

    def __delitem__(cls: type[Schema], prop_name: str) -> None:  # type: ignore[misc]
        cls.get_prop(prop_name).delete()

    def __setitem__(cls: type[Schema], prop_name: str, prop_type: PropertyType) -> None:  # type: ignore[misc]
        session = get_active_session()
        session.api.databases.update(db=cls.get_db().obj_ref, schema={prop_name: prop_type.obj_ref})
        prop = Property(prop_name, prop_type)
        super().__setattr__(rich_text.snake_case(prop_name), prop)  # type: ignore[misc]
        prop.__set_name__(cls, rich_text.snake_case(prop_name))
        cls._set_obj_refs()

    def __setattr__(cls: type[Schema], name: str, value: Any) -> None:  # type: ignore[misc]
        if isinstance(value, Property):
            cls[value.name] = value.type
            super().__setattr__(name, cls.get_prop(value.name))  # type: ignore[misc]
        else:
            super().__setattr__(name, value)  # type: ignore[misc]

    def __len__(cls: type[Schema]) -> int:  # type: ignore[misc]
        return len(cls.get_props())

    def __iter__(cls: type[Schema]) -> Iterator[PropertyType]:  # type: ignore[misc]
        return (prop.type for prop in cls.get_props())


class SchemaModel(BaseModel):
    """Base Pydantic model for schemas to validate pages within a database."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra='forbid')
    _db_title: str | None = PrivateAttr(default=None)

    def to_dict(self) -> dict[str, Any]:
        """Convert the Pydantic model to a dictionary."""
        result = {}
        for name, field in self.__class__.model_fields.items():
            value = getattr(self, name)
            name = field.alias or name
            if isinstance(value, PropertyValue):
                result[name] = value.obj_ref
        return result

    def __repr__(self):
        base = super().__repr__()
        attrs = base[len(self.__class__.__name__) :]
        return f'{self.__class__.__name__}[{self._db_title}]{attrs}'


class Schema(metaclass=SchemaType):
    """Base class for the schema of a database."""

    db_title: rich_text.Text | None
    db_desc: rich_text.Text | None
    _database: Database | None = None

    def __init_subclass__(cls, db_title: str | None, **kwargs: Any):
        if db_title is not None:
            db_title = rich_text.Text(db_title)
        cls.db_title = db_title
        cls.db_desc = rich_text.Text(cls.__doc__) if cls.__doc__ is not None else None
        cls._validate()
        super().__init_subclass__(**kwargs)

    @classmethod
    def _validate(cls) -> None:
        """Validate the schema before creating a database."""
        try:
            cls.get_title_prop()
        except EmptyListError as e:
            msg = 'A property with property type `Title` is mandatory'
            raise SchemaError(msg) from e
        except MultipleItemsError as e:
            msg = 'Only one property with property type `Title` is allowed'
            raise SchemaError(msg) from e

        counter = Counter(prop.name for prop in cls.get_props())
        if duplicates := [prop for prop, count in counter.items() if count > 1]:
            msg = f'Properties {", ".join(duplicates)} are defined more than once'
            raise SchemaError(msg)

    @classmethod
    def from_dict(
        cls, schema_dct: dict[str, PropertyType], db_title: str | None = None, db_desc: str | None = None
    ) -> type[Schema]:
        """Creation of a schema from a dictionary for easy support of dynamically created schemas."""
        title_props = [k for k, v in schema_dct.items() if isinstance(v, Title)]
        if not title_props:
            msg = 'Missing an item with property type `Title` as value'
            raise SchemaError(msg)
        elif len(title_props) > 1:
            msg = f'More than one item with property type `Title` as value found: {", ".join(title_props)}'
            raise SchemaError(msg)

        cls_name = f'{cls.__name__}FromDct'
        attrs: dict[str, Any] = {'db_desc': db_desc}
        for prop_name, prop_type in schema_dct.items():
            attrs[rich_text.snake_case(prop_name)] = Property(prop_name, prop_type)
        return type(cls_name, (Schema,), attrs, db_title=db_title)

    @classmethod
    def create(cls, **kwargs) -> Page:
        """Create a page using this schema with a bound database."""
        return cls.get_db().create_page(**kwargs)

    @classmethod
    def get_props(cls) -> list[Property]:
        """Get all properties of this schema."""
        return [prop for prop in cls.__dict__.values() if isinstance(prop, Property)]

    @classmethod
    def get_prop(cls, prop_name: str) -> Property:
        """Get a specific property from this schema assuming that property names are unique."""
        try:
            return SList([prop for prop in cls.get_props() if prop.name == prop_name]).item()
        except EmptyListError as e:
            msg = f'Property `{prop_name}` not found in database `{cls._database}`.'
            raise SchemaError(msg) from e

    @classmethod
    def get_ro_props(cls) -> list[Property]:
        """Get all read-only properties of this schema."""
        return [prop for prop in cls.get_props() if prop.type.readonly]

    @classmethod
    def get_rw_props(cls) -> list[Property]:
        """Get all writeable properties of this schema."""
        return [prop for prop in cls.get_props() if not prop.type.readonly]

    @classmethod
    def to_pydantic_model(cls, *, with_ro_props: bool = False) -> type[SchemaModel]:
        """Return a Pydantic model of this schema for validation.

        This is useful for instance when writing a web API that receives data that should be validated
        before it is passed to Ultimate Notion. The actual values are converted to `PropertyValue`
        and thus `value` needs to be called to retrieve the actual Python type.

        If `with_ro_props` is set to `True`, read-only properties are included in the model.
        """

        # ToDo: Validate the categories in Select and MultiSelect using pydantic!
        def pytype_to_prop_value(py_type: Any, *, prop_value: type[PropertyValue]) -> PropertyValue:
            """Convert a Python type to a PropertyValue."""
            return py_type if isinstance(py_type, PropertyValue) else prop_value(py_type)

        kwargs: dict[str, Any] = {
            prop.attr_name: Annotated[prop.type.prop_value, Field(default=None, alias=prop.name)]
            for prop in cls.get_rw_props()
        }
        validators: dict[str, Any] = {
            f'{prop.attr_name}_validator': field_validator(prop.attr_name, mode='before')(
                partial(pytype_to_prop_value, prop_value=prop.type.prop_value)
            )
            for prop in cls.get_rw_props()
        }

        if with_ro_props:
            kwargs |= {
                prop.attr_name: Annotated[prop.type.prop_value, Field(alias=prop.name)] for prop in cls.get_ro_props()
            }
            validators |= {
                f'{prop.attr_name}_validator': field_validator(prop.attr_name, mode='before')(
                    partial(pytype_to_prop_value, prop_value=prop.type.prop_value)
                )
                for prop in cls.get_ro_props()
            }

        model = create_model(
            SchemaModel.__name__,
            __validators__=validators,
            __base__=SchemaModel,
            **kwargs,
        )
        model._db_title = cls.db_title
        return model

    @classmethod
    def to_dict(cls) -> dict[str, PropertyType]:
        """Convert this schema to a dictionary of property names and corresponding types."""
        return {prop.name: prop.type for prop in cls.get_props()}

    @classmethod
    def as_table(cls, tablefmt: str | None = None) -> str:
        """Return the schema in a given string table format.

        Some table formats:

        - plain: no pseudographics
        - simple: Pandoc's simple table, i.e. only dashes to separate header from content
        - github: GitHub flavored Markdown
        - simple_grid: uses dashes & pipes to separate cells
        - html: standard html markup

        Find more table formats under: https://github.com/astanin/python-tabulate#table-format
        """
        if tablefmt is None:
            tablefmt = 'html' if is_notebook() else 'simple'

        headers = ['Name', 'Property', 'Attribute']
        rows = []
        for prop in cls.get_props():
            rows.append((prop.name, prop.type, prop.attr_name))

        return tabulate(rows, headers=headers, tablefmt=tablefmt)

    @classmethod
    def show(cls, *, simple: bool | None = None):
        """Show the schema as html or as simple table."""
        if simple:
            tablefmt = 'simple'
        elif simple is None:
            tablefmt = 'html' if is_notebook() else 'simple'
        else:
            tablefmt = 'html'

        table_str = cls.as_table(tablefmt)

        if is_notebook() and (tablefmt == 'html'):
            from IPython.display import display_html  # noqa: PLC0415

            display_html(table_str)
        else:
            print(table_str)  # noqa: T201

    @classmethod
    def _repr_html_(cls) -> str:  # noqa: PLW3201
        """Called by JupyterLab automatically to display this schema."""
        return cls.as_table(tablefmt='html')

    @classmethod
    def get_title_prop(cls) -> Property:
        """Returns the property holding the title of the pages."""
        return SList(prop for prop in cls.get_props() if isinstance(prop.type, Title)).item()

    @classmethod
    def assert_consistency_with(cls, other_schema: type[Schema], *, during_init: bool = False) -> None:
        """Assert that this schema is consistent with another schema."""
        own_schema_dct = cls.to_dict()
        other_schema_dct = other_schema.to_dict()

        if during_init:
            # backward relation was not yet initialised in the other schema (during the creation of the data model)
            # or self-referencing relation was not yet initialised
            other_schema_dct = {
                name: prop_type
                for name, prop_type in other_schema_dct.items()
                if not (
                    (isinstance(prop_type, Relation) and not prop_type.schema)
                    or (isinstance(prop_type, Rollup) and prop_type.is_self_ref)
                )
            }

        if other_schema_dct != own_schema_dct:
            props_added, props_removed, props_changed = dict_diff_str(own_schema_dct, other_schema_dct)
            msg = f"""Provided schema is not consistent with the current schema of the database:
                      Properties added: {props_added}
                      Properties removed: {props_removed}
                      Properties changed: {props_changed}
                   """
            raise SchemaError(dedent(msg))

    @classmethod
    def get_db(cls) -> Database:
        """Get the database that is bound to this schema."""
        if cls._database is not None:  # is_bound() cannot be used here due to type checker
            return cls._database
        else:
            raise SchemaNotBoundError(cls)

    @classmethod
    def bind_db(cls, db: Database):
        """Bind this schema to the corresponding database for back-reference."""
        cls._database = db
        cls._set_obj_refs()

    @classmethod
    def is_bound(cls) -> bool:
        """Determines if the schema is bound to a database."""
        return cls._database is not None

    @classmethod
    def _get_fwd_rels(cls) -> list[Property]:
        return [
            prop
            for prop in cls.get_props()
            if isinstance(prop.type, Relation) and not (prop.type._is_two_way_target or prop.type.is_self_ref)
        ]

    @classmethod
    def _init_fwd_rels(cls):
        """Initialise all non-self-referencing forward relations assuming that the target schemas exist."""
        for prop in cls._get_fwd_rels():
            prop_type = cast(Relation, prop.type)
            prop_type._make_obj_ref()

    @classmethod
    def _get_self_refs(cls) -> list[Property]:
        """Get all self-referencing relation properties."""
        return [prop for prop in cls.get_props() if isinstance(prop.type, Relation) and prop.type.is_self_ref]

    @classmethod
    def _has_self_refs(cls) -> bool:
        """Determine if self-referencing relation properties are present."""
        return bool([prop for prop in cls.get_props() if isinstance(prop.type, Relation) and prop.type.is_self_ref])

    @classmethod
    def _init_self_refs(cls):
        """Initialise all forward self-referencing relations."""
        if not cls._has_self_refs():
            return
        db = cls.get_db()  # raises if not bound!
        for prop in cls._get_self_refs():
            prop_type = cast(Relation, prop.type)
            prop_type._schema = cls  # replace placeholder `SelfRef` with this schema
            prop_type._make_obj_ref()

        new_props_schema = {prop.name: prop.type.obj_ref for prop in cls._get_self_refs()} or None
        session = get_active_session()
        session.api.databases.update(db.obj_ref, schema=new_props_schema)
        cls._set_obj_refs()

    @classmethod
    def _init_self_ref_rollups(cls):
        """Initialise all rollup properties that reference the same schema."""
        if not cls._has_self_refs():
            return
        db = cls.get_db()  # raises if not bound!

        self_ref_rollups = [prop for prop in cls.get_props() if isinstance(prop.type, Rollup) and prop.type.is_self_ref]
        new_props_schema = {prop.name: prop.type.obj_ref for prop in self_ref_rollups} or None
        session = get_active_session()
        session.api.databases.update(db.obj_ref, schema=new_props_schema)
        cls._set_obj_refs()

    @classmethod
    def _get_init_props(cls) -> list[Property]:
        """Get all properties that are initialized by now."""
        return [prop for prop in cls.get_props() if prop.type._is_init]

    @classmethod
    def _update_bwd_rels(cls):
        """Update the default property name in case of a two-way relation in the external target schema.

        By default the property in the target schema is named "Related to <this_database> (<this_field>)"
        which is then set to the name specified as backward relation.
        """
        for prop_type in cls.to_dict().values():
            if isinstance(prop_type, Relation) and prop_type.is_two_way:
                prop_type._update_bwd_rel()

    @classmethod
    def _set_obj_refs(cls):
        """Map obj_refs from the properties of the schema to obj_ref.properties of the bound database."""
        db_props_dct = cls.get_db().obj_ref.properties
        for prop_name, prop_type in cls.to_dict().items():
            obj_ref = db_props_dct.get(prop_name)
            if obj_ref:
                prop_type.obj_ref = obj_ref


class Title(PropertyType[obj_schema.Title], wraps=obj_schema.Title):
    """Defines the mandatory title property in a database."""


class Text(PropertyType[obj_schema.RichText], wraps=obj_schema.RichText):
    """Defines a text property in a database."""


class Number(PropertyType[obj_schema.Number], wraps=obj_schema.Number):
    """Defines a number property in a database."""

    def __init__(self, format: NumberFormat | str = NumberFormat.NUMBER):  # noqa: A002
        super().__init__(NumberFormat(format))

    @property
    def format(self) -> NumberFormat:
        """Return the number format of this number property."""
        return self.obj_ref.number.format

    @format.setter
    def format(self, new_format: NumberFormat | str) -> None:
        """Set the number format of this number property."""
        if isinstance(new_format, str):
            new_format = NumberFormat(new_format)
        self.obj_ref.number.format = new_format
        self._update_prop(self.name, self.obj_ref)


class Select(PropertyType[obj_schema.Select], wraps=obj_schema.Select):
    """Defines a select property in a database."""

    def __init__(self, options: list[Option] | type[OptionNS]):
        if isinstance(options, type) and issubclass(options, OptionNS):
            options = options.to_list()

        option_objs = [option.obj_ref for option in options]
        super().__init__(option_objs)

    @property
    def options(self) -> list[Option]:
        """Return the options of this select property."""
        return [Option.wrap_obj_ref(option) for option in self.obj_ref.select.options]

    @options.setter
    def options(self, new_options: list[Option] | type[OptionNS]) -> None:
        """Set the options of this select property.

        !!! note
            Omitted options are removed from the property and new options
            will be added. Updating the `name` and `color` of an existing option
            is not supported via the API.
        """
        if isinstance(new_options, type) and issubclass(new_options, OptionNS):
            new_options = new_options.to_list()

        # Compare current and new options, handle changed attributes if needed
        diffs = compare_options(self.options, new_options)
        if diffs:
            msg = f'Cannot update options of {self.name} property: {diffs}'
            raise InvalidAPIUsageError(msg)

        self.obj_ref.select.options = [option.obj_ref for option in new_options]
        self._update_prop(self.name, self.obj_ref)


class MultiSelect(PropertyType[obj_schema.MultiSelect], wraps=obj_schema.MultiSelect):
    """Defines a multi-select property in a database."""

    def __init__(self, options: list[Option] | type[OptionNS]):
        if isinstance(options, type) and issubclass(options, OptionNS):
            options = options.to_list()

        option_objs = [option.obj_ref for option in options]
        super().__init__(option_objs)

    @property
    def options(self) -> list[Option]:
        """Return the options of this multi-select property."""
        return [Option.wrap_obj_ref(option) for option in self.obj_ref.multi_select.options]

    @options.setter
    def options(self, new_options: list[Option] | type[OptionNS]) -> None:
        """Set the options of this multi-select property.

        !!! note
            Omitted options are removed from the property and new options
            will be added. Updating the `name` and `color` of an existing option
            is not supported via the API.
        """
        if isinstance(new_options, type) and issubclass(new_options, OptionNS):
            new_options = new_options.to_list()

        # Compare current and new options, handle changed attributes if needed
        diffs = compare_options(self.options, new_options)
        if diffs:
            msg = f'Cannot update options of {self.name} property: {diffs}'
            raise InvalidAPIUsageError(msg)

        self.obj_ref.multi_select.options = [option.obj_ref for option in new_options]
        self._update_prop(self.name, self.obj_ref)


class Status(PropertyType[obj_schema.Status], wraps=obj_schema.Status):
    """Defines a status property in a database.

    The Notion API doesn't allow to create a property of this type.
    Sending it to the API with options and option groups defined results in an error
    about the existence of the keys `options` and `groups` and removing them
    creates a database with the property missing... ignorance is bliss.

    Also the Status configuration is not mentioned as a
    [Property Schema Object])https://developers.notion.com/reference/property-schema-object).
    """

    allowed_at_creation = False

    @property
    def options(self) -> list[Option]:
        """Return the options of this status property."""
        return [Option.wrap_obj_ref(option) for option in self.obj_ref.status.options]

    @property
    def groups(self) -> list[OptionGroup]:
        """Return the option groups of this status property."""
        return [OptionGroup.wrap_obj_ref(group, options=self.options) for group in self.obj_ref.status.groups]


class Date(PropertyType[obj_schema.Date], wraps=obj_schema.Date):
    """Defines a date property in a database."""


class Person(PropertyType[obj_schema.People], wraps=obj_schema.People):
    """Defines a person/people property in a database."""


class Files(PropertyType[obj_schema.Files], wraps=obj_schema.Files):
    """Defines a files property in a database."""


class Checkbox(PropertyType[obj_schema.Checkbox], wraps=obj_schema.Checkbox):
    """Defines a checkbox property in database."""


class Email(PropertyType[obj_schema.Email], wraps=obj_schema.Email):
    """Defines an e-mail property in a database."""


class URL(PropertyType[obj_schema.URL], wraps=obj_schema.URL):
    """Defines a URL property in a database."""


class Phone(PropertyType[obj_schema.PhoneNumber], wraps=obj_schema.PhoneNumber):
    """Defines a phone number property in a database."""


class Formula(PropertyType[obj_schema.Formula], wraps=obj_schema.Formula):
    """Defines a formula property in a database.

    Currently the formula expression cannot reference other formula properties, e.g. `prop("other formula")`
    This is a limitation of the API.
    """

    def __init__(self, expression: str):
        super().__init__(expression)

    @property
    def expression(self) -> str:
        """Return the expression of this formula property."""
        return self.obj_ref.formula.expression

    @expression.setter
    def expression(self, expression: str) -> None:
        """Set the expression of this formula property."""
        self.obj_ref.formula.expression = expression
        self._update_prop(self.name, self.obj_ref)


class SelfRef(Schema, db_title=None):
    """Target schema for self-referencing database relations."""

    _ = Property('title', Title())  # mandatory title property, used for nothing.


class Relation(PropertyType[obj_schema.Relation], wraps=obj_schema.Relation):
    """Relation to another database."""

    _schema: type[Schema] | None = None  # other schema, i.e. of the target database
    _two_way_prop: Property | None = None  # other property, i.e. of the target database

    def __init__(self, schema: type[Schema] | None = None, *, two_way_prop: Property | None = None):
        # Note that we don't call super().__init__ here since we only know how to build the obj_ref later.
        if two_way_prop and not schema:
            msg = '`schema` needs to be provided if `two_way_prop` is set'
            raise RuntimeError(msg)

        if isinstance(schema, Property):
            msg = 'Please provide a schema, not a property! Use `two_way_prop` to specify a property.'
            raise ValueError(msg)

        self._schema = schema

        if two_way_prop is not None:
            if not isinstance(two_way_prop.type, Relation):
                msg = f'The two-way property {two_way_prop.name} needs to be of type Relation!'
                raise ValueError(msg)

            if two_way_prop.type.schema is not None:
                msg = f'The two-way property {two_way_prop.name} must not reference a schema itself'
                raise ValueError(msg)

            self._two_way_prop = two_way_prop

    @property
    def schema(self) -> type[Schema] | None:
        """Schema of the relation database."""
        if self._schema:
            return self._schema if self._schema is not SelfRef else None
        if self.prop_ref is not None and self.prop_ref._schema.is_bound():
            session = get_active_session()
            return session.get_db(self.obj_ref.relation.database_id).schema
        else:
            return None

    @schema.setter
    def schema(self, new_schema: type[Schema]):
        """Set the schema of the relation database."""
        if self.is_two_way:
            new_rel = obj_schema.DualPropertyRelation.build(new_schema.get_db().id)
        else:
            new_rel = obj_schema.SinglePropertyRelation.build(new_schema.get_db().id)
        self.obj_ref.relation = new_rel.relation
        self._update_prop(self.name, self.obj_ref)
        self._schema = new_schema

    @property
    def _is_two_way_target(self) -> bool:
        """Determines if relation is meant as target for a two-way relation."""
        return self._schema is None

    @property
    def two_way_prop(self) -> Property | None:
        """Return the target property object of a two-way relation."""
        if self._two_way_prop:
            return self._two_way_prop
        elif (
            hasattr(self, 'obj_ref')
            and self.schema
            and isinstance(self.obj_ref.relation, obj_schema.DualPropertyRelation)
        ):
            prop_name = self.obj_ref.relation.dual_property.synced_property_name
            return self.schema.get_prop(prop_name) if prop_name else None
        else:
            return None

    @two_way_prop.setter
    def two_way_prop(self, new_prop_name: str | None):
        """Set the target property object of a two-way relation."""

        if self.schema is None or (db := self.schema.get_db()) is None:
            msg = 'The target schema of the relation is not bound to a database'
            raise RelationError(msg)

        if new_prop_name is None:
            if self.two_way_prop is None:
                return
            target_schema = self.schema
            target_two_way_prop = self.two_way_prop.name
            new_rel = obj_schema.SinglePropertyRelation.build(db.id)
            self.obj_ref.relation = new_rel.relation
            self.obj_ref = cast(obj_Relation, self._update_prop(self.name, self.obj_ref))
            # Strangely enough, the two-way property is not removed from the target schema
            # also it is no longer a two-way relation.
            del target_schema[target_two_way_prop]
        else:
            new_rel = obj_schema.DualPropertyRelation.build(db.id)

            if not isinstance(new_rel.relation, obj_schema.DualPropertyRelation):
                msg = 'Cannot set two-way property on a one-way relation'
                raise SchemaError(msg)

            self.obj_ref.relation = new_rel.relation
            self.obj_ref = cast(obj_Relation, self._update_prop(self.name, self.obj_ref))

            if not isinstance(self.obj_ref.relation, obj_schema.DualPropertyRelation):
                msg = 'Cannot set two-way property on a one-way relation'
                raise SchemaError(msg)

            tmp_new_prop_name = self.obj_ref.relation.dual_property.synced_property_name
            db = self.schema.get_db()
            db.reload()
            if (back_ref_prop := db.schema[tmp_new_prop_name].prop_ref) is not None:
                back_ref_prop.name = new_prop_name

        self._schema = None  # Don't rely on the initialization of the schema

    @property
    def is_two_way(self) -> bool:
        """Determine if this relation is a two-way relation."""
        return self.two_way_prop is not None

    @property
    def is_self_ref(self) -> bool:
        """Determines if this relation is self referencing the same schema."""
        return (self._schema is SelfRef) or (self.prop_ref is not None and self._schema is self.prop_ref._schema)

    def _make_obj_ref(self) -> None:
        """Initialize the low-level object references for this relation.

        This function is used only internally and called during the forward initialization.
        """
        if self.schema is None:
            msg = 'The target schema of the relation is not bound to a database'
            raise RelationError(msg)

        try:
            db = self.schema.get_db()
        except SchemaNotBoundError as e:
            msg = f"A database with schema '{self.schema.__name__}' needs to be created first!"
            raise RelationError(msg) from e

        if self.two_way_prop:
            self.obj_ref = obj_schema.DualPropertyRelation.build(db.id)
        else:
            self.obj_ref = obj_schema.SinglePropertyRelation.build(db.id)

    def _update_bwd_rel(self) -> None:
        """Change the default name of a two-way relation target to the defined one."""
        if self.prop_ref is None:
            msg = 'Trying to inialize a backward relation for one-way relation that is not bound to a property'
            raise SchemaError(msg)

        if not isinstance(self.obj_ref.relation, obj_schema.DualPropertyRelation):
            msg = f'Trying to inialize backward relation for one-way relation {self.prop_ref.name}'
            raise SchemaError(msg)

        obj_synced_property_name = self.obj_ref.relation.dual_property.synced_property_name
        two_way_prop_name = self._two_way_prop.name if self._two_way_prop else None

        if obj_synced_property_name != two_way_prop_name:
            session = get_active_session()

            if self.schema is None:
                msg = 'The target schema of the relation is not bound to a database'
                raise RelationError(msg)

            # change the old default name in the target schema to what was passed during initialization
            other_db = self.schema.get_db()

            if (prop_id := self.obj_ref.relation.dual_property.synced_property_id) is None:
                msg = 'No synced property ID found in the relation object'
                raise SchemaError(msg)

            schema_dct = {prop_id: obj_schema.RenameProp(name=two_way_prop_name)}
            session.api.databases.update(db=other_db.obj_ref, schema=schema_dct)
            other_db.schema._set_obj_refs()

            our_db = self.prop_ref._schema.get_db()
            session.api.databases.update(db=our_db.obj_ref, schema={})  # sync obj_ref
            our_db.schema._set_obj_refs()


class Rollup(PropertyType[obj_schema.Rollup], wraps=obj_schema.Rollup):
    """Defines the rollup property in a database.

    If the relation propery is a self-referencing relation, i.e. `uno.PropType.Relation(uno.SelfRef)` in the schema,
    then the `property` must be a `str` of the corresponding property name.
    """

    def __init__(
        self, relation_prop: Property, rollup_prop: Property, calculate: AggFunc | str = AggFunc.SHOW_ORIGINAL
    ):
        if not isinstance(relation_prop.type, Relation):
            msg = f'Relation `{relation_prop.name}` must be of type Relation'
            raise RollupError(msg)

        calculate = AggFunc.from_alias(calculate) if not isinstance(calculate, AggFunc) else calculate

        # ToDo: One could check here if property really is a property in the database where relation points to
        super().__init__(relation_prop.name, rollup_prop.name, calculate)

    @property
    def _is_init(self) -> bool:
        """Determines if the relation of the rollup is already initialized."""
        try:
            return self.relation_prop.type._is_init
        except SchemaError:  # DB is not bound yet
            return False

    @property
    def is_self_ref(self) -> bool:
        """Determines if this rollup is self-referencing the same schema."""
        return cast(Relation, self.relation_prop.type).is_self_ref

    @property
    def relation_prop(self) -> Property:
        """Return the relation property object of the rollup."""
        if self.prop_ref is not None:
            return self.prop_ref._schema.get_prop(self.obj_ref.rollup.relation_property_name)
        else:
            msg = 'Rollup property not bound to a `Property` object'
            raise RollupError(msg)

    @property
    def rollup_prop(self) -> Property:
        """Return the rollup property object of the rollup."""
        if self.prop_ref is not None:
            return self.prop_ref._schema.get_prop(self.obj_ref.rollup.rollup_property_name)
        else:
            msg = 'Rollup property not bound to a `Property` object'
            raise RollupError(msg)

    @property
    def calculate(self) -> AggFunc:
        """Return the aggregation function of the rollup."""
        return self.obj_ref.rollup.function


class CreatedTime(PropertyType[obj_schema.CreatedTime], wraps=obj_schema.CreatedTime):
    """Defines the created-time property in a database."""


class CreatedBy(PropertyType[obj_schema.CreatedBy], wraps=obj_schema.CreatedBy):
    """Defines the created-by property in a database."""


class LastEditedBy(PropertyType[obj_schema.LastEditedBy], wraps=obj_schema.LastEditedBy):
    """Defines the last-edited-by property in a database."""


class LastEditedTime(PropertyType[obj_schema.LastEditedTime], wraps=obj_schema.LastEditedTime):
    """Defines the last-edited-time property in a database."""


class ID(PropertyType[obj_schema.UniqueID], wraps=obj_schema.UniqueID):
    """Defines a unique ID property in a database."""

    allowed_at_creation = False

    @property
    def prefix(self) -> str:
        opt_prefix = self.obj_ref.unique_id.prefix
        return '' if opt_prefix is None else opt_prefix


class Verification(PropertyType[obj_schema.Verification], wraps=obj_schema.Verification):
    """Defines a unique ID property in a database."""

    allowed_at_creation = False


class Button(PropertyType[obj_schema.Button], wraps=obj_schema.Button):
    """Defines a button property in a database."""

    allowed_at_creation = False


class DefaultSchema(Schema, db_title=None):
    # Default database schema of Notion.
    #
    # As inferred by just creating an empty database in the Notion UI.
    # NOTE: Use no docstring here, otherwise it will be used as the database description.

    name = Property('Name', Title())


class PropType:
    """Namespace class of all property types of a database for easier access."""

    Title = Title
    Text = Text
    Number = Number
    Select = Select
    MultiSelect = MultiSelect
    Status = Status
    Date = Date
    Person = Person
    Files = Files
    Checkbox = Checkbox
    Email = Email
    URL = URL
    Phone = Phone
    Formula = Formula
    Relation = Relation
    Rollup = Rollup
    CreatedTime = CreatedTime
    CreatedBy = CreatedBy
    LastEditedTime = LastEditedTime
    LastEditedBy = LastEditedBy
    ID = ID
    Verification = Verification
