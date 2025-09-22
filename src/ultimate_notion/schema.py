"""Functionality around defining a database schema.

Currently only normal databases, no wiki databases, can be created [1].
Neither the `Unique ID` nor `Status` nor the `Verfication` page property can be set as a database property
in a custom Schema when creating the database.

[1] https://developers.notion.com/docs/working-with-databases#wiki-databases


### Design Principles

A schema is a subclass of `Schema` that holds `Property` objects, which define the name and the type of the
property, e.g. `Text`, `Number`.

The source of truth is always the `obj_ref` and a `Property` holds only auxilliary
information if actually needed. Since the object references `obj_ref` must always point
to the actual `obj_api.blocks.Database.properties` value if the schema is bound to a database,
the method `_set_obj_refs` rewires this when a schema is used to create a database.
"""

from __future__ import annotations

from abc import ABC, ABCMeta
from collections import Counter
from collections.abc import Iterator
from copy import deepcopy
from functools import partial
from typing import TYPE_CHECKING, Annotated, Any, TypeAlias, cast, overload

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, create_model, field_validator
from tabulate import tabulate
from typing_extensions import Self, TypeVar

import ultimate_notion.obj_api.core as obj_core
import ultimate_notion.obj_api.schema as obj_schema
from ultimate_notion import rich_text
from ultimate_notion.core import Wrapper, get_active_session, get_repr
from ultimate_notion.errors import (
    EmptyListError,
    InvalidAPIUsageError,
    MultipleItemsError,
    PropertyError,
    RelationError,
    RollupError,
    SchemaError,
    SchemaNotBoundError,
    UnsetError,
)
from ultimate_notion.obj_api.core import Unset, UnsetType, is_unset, raise_unset
from ultimate_notion.obj_api.enums import OptionGroupType
from ultimate_notion.obj_api.schema import AggFunc, NumberFormat
from ultimate_notion.option import Option, OptionGroup, OptionNS, check_for_updates
from ultimate_notion.props import PropertyValue
from ultimate_notion.utils import SList, dict_diff_str, is_notebook

if TYPE_CHECKING:
    from ultimate_notion.database import Database
    from ultimate_notion.obj_api.core import UnsetType
    from ultimate_notion.page import Page

T = TypeVar('T')
PropertyGO: TypeAlias = obj_schema.Property[obj_core.GenericObject]
GO_co = TypeVar('GO_co', bound=PropertyGO, default=PropertyGO, covariant=True)


class Property(Wrapper[GO_co], ABC, wraps=PropertyGO):
    """Base class for Notion property objects.

    A property defines the name and type of a property in a database, e.g. number, date, text, etc.
    """

    """Reference to the low-level object representation of this property"""
    allowed_at_creation = True
    """If the Notion API allows to create a new database with a property of this type"""
    _name: str | None = None  # name given by the user, not the Notion API, will match when set
    _owner: type[Schema] | None = None  # back reference to the schema
    _attr_name: str | None = None  # name of the attribute within the schema holding the Property

    def __new__(cls, *args: Any, **kwargs: Any) -> Property:
        if cls is Property:
            msg = f'{cls.__name__} is abstract and cannot be instantiated directly'
            raise TypeError(msg)
        return super().__new__(cls)

    def __init__(self, name: str | None = None, **kwargs: Any) -> None:
        if name is not None and not isinstance(name, str):
            msg = f'The name of the property must be a string, not {type(name).__name__}'
            raise PropertyError(msg)
        self._name = name
        obj_api_type = self._obj_api_map_inv[self.__class__]
        self.obj_ref = obj_api_type.build(**kwargs)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Property):
            return NotImplemented
        other_obj_ref = cast(GO_co, other.obj_ref)
        return (self.obj_ref.type == other_obj_ref.type) and (self.obj_ref.value == other_obj_ref.value)

    def __hash__(self) -> int:
        return hash((self.obj_ref.type, self.obj_ref.value))

    def __repr__(self) -> str:
        return get_repr(self, name=f'{self.__class__.__name__} Property', desc=self.name)

    def __str__(self) -> str:
        return self.__class__.__name__

    @property
    def _is_init(self) -> bool:
        """Determines if the property is already initialized"""
        return hasattr(self, '_obj_ref')

    @property
    def _is_init_ready(self) -> bool:
        """Determines if the property is ready to be initialized"""
        return True

    def _get_owner(self) -> type[Schema]:
        """Get the owner schema of this property."""
        if self._owner is None:
            msg = f'The property {self.name} is not bound to a Schema!'
            raise PropertyError(msg)
        return self._owner

    def _update_prop(self, prop_obj: GO_co) -> GO_co:  # type: ignore[misc] # breaking covariance
        """Update the attributes of this property from a schema."""
        db = self._get_owner().get_db()
        session = get_active_session()
        session.api.databases.update(db=db.obj_ref, schema={self.name: prop_obj})
        return cast(GO_co, db.obj_ref.properties[self.name])

    def _rename_prop(self, new_name: str | None) -> None:
        """Update the name of this property in the schema or delete it.

        !!! warning

            The name of the Python attribute, i.e. `attr_name`, in the schema is not the changed!
            Use `prop.attr_name = "..."` to change the attribute name of a property `prop` within a schema.
        """
        schema = self._get_owner()
        db = schema.get_db()
        session = get_active_session()
        schema_obj: dict[str, obj_schema.RenameProp | None] = (
            {self.name: None} if new_name is None else {self.name: obj_schema.RenameProp(name=new_name)}
        )
        session.api.databases.update(db=db.obj_ref, schema=schema_obj)

        if new_name is None:
            schema._props = [prop for prop in schema.get_props() if prop.name != self.name]
        else:
            self.obj_ref.name = new_name
            self._name = new_name

        schema._set_obj_refs()

    @classmethod
    def wrap_obj_ref(cls, obj_ref: GO_co) -> Self:  # type: ignore[misc] # breaking covariance
        """Wrap the object reference for this property."""
        obj = super().wrap_obj_ref(obj_ref)
        obj._attr_name = rich_text.snake_case(obj.name)
        return obj

    def delete(self) -> None:
        """Delete this property from the schema."""
        self._rename_prop(None)

    @property
    def id(self) -> str | None:
        """Return identifier of this property."""
        return raise_unset(self.obj_ref.id)

    @property
    def name(self) -> str:
        """Return name of this property."""
        if self._is_init and not is_unset(self.obj_ref.name):
            return self.obj_ref.name
        elif self._name is not None:
            return self._name
        else:
            msg = f'A name needs to be provided for `{self.__class__.__name__}`.'
            raise PropertyError(msg)

    @name.setter
    def name(self, new_name: str) -> None:
        """Set the name of this property."""
        self._rename_prop(new_name)

    @property
    def description(self) -> str | None:
        """Return the description of this property."""
        return self.obj_ref.description

    @property
    def attr_name(self) -> str:
        """Return the Python attribute name of the property in the schema."""
        if self._attr_name is None:
            msg = f'Property `{self.name}` has no assigned attribute name yet.'
            raise PropertyError(msg)
        return self._attr_name

    @attr_name.setter
    def attr_name(self, name: str) -> None:
        """Define the attribute name of the property within the schema."""
        self._attr_name = name

    @property
    def prop_value(self) -> type[PropertyValue]:
        """Return the corresponding property value of this property."""
        return PropertyValue._type_value_map[self.obj_ref.type]

    @property
    def readonly(self) -> bool:
        """Return if this property is read-only."""
        return self.prop_value.readonly


class SchemaType(ABCMeta):
    """Metaclass for the schema of a database.

    This makes the schema class itself more user-friendly by providing a `__magic__` methods, e.g.
    letting it behave like a dictionary for the properties although it is a class, not an instance.
    """

    # ToDo: When mypy is smart enough to understand metaclasses, we can remove the `type: ignore` comments
    def __new__(metacls, name: str, bases: tuple[type, ...], namespace: dict[str, object], **kwargs: Any) -> SchemaType:
        # This collects all schema properties under `_props`. Using __prepare__ doesn't work as referencing
        # the class itself would not be possible at that stage any more as __getattr__ is not used at that point.
        # Thus, we create the class normally and change it only afterwards when __prepare__ is already done.
        props = cast(list[Property], namespace.setdefault('_props', []))

        for b in bases:
            for prop in getattr(b, '_props', []):
                prop = cast(Property, deepcopy(prop))
                props.append(prop)

        for attr, val in list(namespace.items()):
            if isinstance(val, Property):
                del namespace[attr]
                val._attr_name = attr
                props.append(val)

        cls = super().__new__(metacls, name, bases, dict(namespace), **kwargs)
        for prop in props:
            prop._owner = cast(type[Schema], cls)

        return cls

    def __str__(cls: type[Schema]) -> str:  # type: ignore[misc]
        # We can only overwrite __str__ for a class in a metaclass
        return cls.as_table(tablefmt='simple')

    def __getitem__(cls: type[Schema], prop_name: str) -> Property:  # type: ignore[misc]
        return cls.get_prop(prop_name)

    def __delitem__(cls: type[Schema], prop_name: str) -> None:  # type: ignore[misc]
        cls.get_prop(prop_name).delete()

    def __setitem__(cls: type[Schema], prop_name: str, prop_type: Property) -> None:  # type: ignore[misc]
        if prop_type._name is not None:
            msg = (
                f'Property `{prop_name}` already has a name and thus the `name` parameter of `{prop_type}` must '
                'not be set or use `prop.name = "..."` to change the name of a property.'
            )
            raise PropertyError(msg)

        # handle updating existing properties
        if (curr_prop := cls.get_prop(prop_name, default=None)) is not None:
            if prop_type._attr_name is None:
                prop_type._attr_name = curr_prop._attr_name
            curr_prop.delete()

        prop_type._name = prop_name
        prop_type._owner = cls
        if prop_type._attr_name is None:
            prop_type._attr_name = rich_text.snake_case(prop_name)

        session = get_active_session()
        session.api.databases.update(db=cls.get_db().obj_ref, schema={prop_name: prop_type.obj_ref})

        cls._props.append(prop_type)
        cls._set_obj_refs()

        if isinstance(prop_type, Relation) and (prop_type._two_way_prop is not None):
            prop_type._rename_two_way_prop(prop if isinstance(prop := prop_type._two_way_prop, str) else prop.name)

    def __getattr__(cls: type[Schema], name: str) -> Property:  # type: ignore[misc]
        attr_name_props = SList([prop for prop in cls.get_props() if prop._attr_name == name])
        try:
            return attr_name_props.item()
        except MultipleItemsError as e:
            non_unique_attrs = ', '.join(str(attr) for attr in attr_name_props)
            msg = (
                f'Attribute {name} is not unique for properties {non_unique_attrs}! '
                'Use indexing, i.e. [...], to access the property.'
            )
            raise AttributeError(msg) from e
        except EmptyListError as e:
            msg = f'Schema has no property with attribute name {name}.'
            raise AttributeError(msg) from e

    def __setattr__(cls: type[Schema], name: str, value: Any) -> None:  # type: ignore[misc]
        # Overwrite runtime setting of class attributes
        if isinstance(value, Property):
            curr_attr = getattr(cls, name, None)
            if curr_attr is None:  # adding a new property
                prop_name = value.name
                if prop_name is None:
                    msg = f'Property `{name}` must have a name.'
                    raise PropertyError(msg)
                else:
                    value._name = None  # __setitem__ needs _name to be unset
                    value._attr_name = name
                    cls[prop_name] = value
            elif isinstance(curr_attr, Property):  # updating an existing property
                cls[curr_attr.name] = value
            else:
                msg = f'Cannot override non-property `{name}` of type `{type(curr_attr)}`.'
                raise PropertyError(msg)
        else:
            super().__setattr__(name, value)  # type: ignore[misc]  # no clue why this results in a type problem

    def __len__(cls: type[Schema]) -> int:  # type: ignore[misc]
        return len(cls.get_props())

    def __iter__(cls: type[Schema]) -> Iterator[Property]:  # type: ignore[misc]
        return (prop for prop in cls.get_props())


class SchemaModel(BaseModel):
    """Base Pydantic model for schemas to validate pages within a database."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra='forbid')
    _db_title: str | None = PrivateAttr(default=None)
    _db_id: str | None = PrivateAttr(default=None)

    def to_dict(self) -> dict[str, Any]:
        """Convert the Pydantic model to a dictionary."""
        result = {}
        for name, field in self.__class__.model_fields.items():
            value = getattr(self, name)
            name = field.alias or name
            if isinstance(value, PropertyValue):
                result[name] = value.obj_ref
        return result

    def __repr__(self) -> str:
        base = super().__repr__()
        attrs = base[len(self.__class__.__name__) :]
        title = 'Untitled' if self._db_title is None else f' ({self._db_title})'
        return f'{self.__class__.__name__}[{title}]{attrs}'


class Schema(metaclass=SchemaType):
    """Base class for the schema of a database."""

    _db_title: rich_text.Text | None
    _db_id: str | None
    _db_desc: rich_text.Text | None
    _database: Database | None = None
    _props: list[Property]

    def __init_subclass__(cls, db_title: str | None = None, db_id: str | None = None, **kwargs: Any):
        if db_title is not None:
            db_title = rich_text.Text(db_title)
        cls._db_title = db_title
        cls._db_id = db_id
        cls._db_desc = rich_text.Text(cls.__doc__) if cls.__doc__ is not None else None
        cls._validate()
        super().__init_subclass__(**kwargs)

    @classmethod
    def _validate(cls) -> None:
        """Validate the schema before creating a database."""
        try:
            cls.get_title_prop()
        except EmptyListError as e:
            msg = 'A property of type `Title` is mandatory'
            raise SchemaError(msg) from e
        except MultipleItemsError as e:
            msg = 'Only one property of type `Title` is allowed'
            raise SchemaError(msg) from e

        counter = Counter(prop.name for prop in cls.get_props())
        if duplicates := [prop for prop, count in counter.items() if count > 1]:
            msg = f'Properties {", ".join(duplicates)} are defined more than once'
            raise SchemaError(msg)

    @classmethod
    def create(cls, **kwargs: Any) -> Page:
        """Create a page using this schema with a bound database."""
        return cls.get_db().create_page(**kwargs)

    @classmethod
    def get_props(cls) -> list[Property]:
        """Get all properties of this schema."""
        return cls._props

    @overload
    @classmethod
    def get_prop(cls, prop_name: str, *, default: UnsetType = ...) -> Property: ...
    @overload
    @classmethod
    def get_prop(cls, prop_name: str, *, default: T) -> Property | T: ...

    @classmethod
    def get_prop(cls, prop_name: str, *, default: object = Unset) -> Property | T:
        """Get a specific property from this schema assuming that property names are unique."""
        try:
            return SList([prop for prop in cls.get_props() if prop.name == prop_name]).item()
        except EmptyListError as e:
            if default is Unset:
                if cls.is_bound():
                    msg = f'Property `{prop_name}` not found in schema of `{cls._database}`.'
                else:
                    msg = f'Property `{prop_name}` not found in unbound schema.'
                raise SchemaError(msg) from e
            return cast(T, default)

    @classmethod
    def has_prop(cls, prop_name: str) -> bool:
        """Check if a property exists in this schema."""
        return cls.get_prop(prop_name, default=None) is not None

    @classmethod
    def get_ro_props(cls) -> list[Property]:
        """Get all read-only properties of this schema."""
        return [prop for prop in cls.get_props() if prop.readonly]

    @classmethod
    def get_rw_props(cls) -> list[Property]:
        """Get all writeable properties of this schema."""
        return [prop for prop in cls.get_props() if not prop.readonly]

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
            prop.attr_name: Annotated[prop.prop_value, Field(default=None, alias=prop.name)]
            for prop in cls.get_rw_props()
        }
        validators: dict[str, Any] = {
            f'{prop.attr_name}_validator': field_validator(prop.attr_name, mode='before')(
                partial(pytype_to_prop_value, prop_value=prop.prop_value)
            )
            for prop in cls.get_rw_props()
        }

        if with_ro_props:
            kwargs |= {
                prop.attr_name: Annotated[prop.prop_value, Field(alias=prop.name)] for prop in cls.get_ro_props()
            }
            validators |= {
                f'{prop.attr_name}_validator': field_validator(prop.attr_name, mode='before')(
                    partial(pytype_to_prop_value, prop_value=prop.prop_value)
                )
                for prop in cls.get_ro_props()
            }

        model = create_model(
            SchemaModel.__name__,
            __validators__=validators,
            __base__=SchemaModel,
            **kwargs,
        )
        model._db_title = cls._db_title
        model._db_id = cls._db_id
        return model

    @classmethod
    def to_dict(cls) -> dict[str, Property]:
        """Convert this schema to a dictionary of property names and corresponding types."""
        return {prop.name: prop for prop in cls.get_props()}

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
            rows.append((prop.name, prop, prop.attr_name))

        return tabulate(rows, headers=headers, tablefmt=tablefmt)

    @classmethod
    def show(cls, *, simple: bool | None = None) -> None:
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
        return SList(prop for prop in cls.get_props() if isinstance(prop, Title)).item()

    @classmethod
    def assert_consistency_with(cls, other_schema: type[Schema], *, during_init: bool = False) -> None:
        """Assert that this schema is consistent with another schema."""
        own_schema_dct = cls.to_dict()
        other_schema_dct = other_schema.to_dict()

        if during_init:
            # backward relation was not yet initialised in the other schema (during the creation of the data model)
            # or self-referencing relation was not yet initialised
            own_schema_dct = {
                name: prop_type
                for name, prop_type in own_schema_dct.items()
                if not (
                    isinstance(prop_type, Relation) and (prop_type.is_two_way)  # synced_prop_name default name
                )
            }

            other_schema_dct = {
                name: prop_type
                for name, prop_type in other_schema_dct.items()
                if not (
                    (isinstance(prop_type, Relation) and (prop_type.is_two_way))
                    or (isinstance(prop_type, Relation) and (prop_type._is_two_way_target or prop_type.is_self_ref))
                    or (isinstance(prop_type, Rollup) and prop_type.is_self_ref)
                )
            }

        if other_schema_dct != own_schema_dct:
            props_added, props_removed, props_changed = dict_diff_str(own_schema_dct, other_schema_dct)
            msg = 'Provided schema is not consistent with the current schema of the database:\n'
            if props_added:
                msg += f'- added: {", ".join(props_added)}\n'
            if props_removed:
                msg += f'- removed: {", ".join(props_removed)}\n'
            if props_changed:
                msg += f'- changed: {", ".join(props_changed)}\n'
            raise SchemaError(msg)

    @classmethod
    def get_db(cls) -> Database:
        """Get the database that is bound to this schema."""
        if cls._database is not None:  # is_bound() cannot be used here due to type checker
            return cls._database
        else:
            raise SchemaNotBoundError(cls)

    @classmethod
    def _bind_db(cls, db: Database) -> None:
        """Bind this schema to the corresponding database for back-reference without setting it in `db`."""
        # Needed to break the recursion when setting a schema in Database
        cls._database = db
        cls._set_obj_refs()

    @classmethod
    def bind_db(cls, db: Database | None = None) -> None:
        """Bind this schema to the corresponding database for back-reference and vice versa.

        If `None` (default) is passed, search for the database using `db_id` or `db_title`
        and bind it to this schema.
        """
        if db is None:
            sess = get_active_session()
            if cls._db_id is not None:
                db = sess.get_db(cls._db_id)
            elif cls._db_title is not None:
                db = sess.search_db(cls._db_title).item()
            else:
                msg = 'Neither a database ID nor a title is set to bind the schema automatically.'
                raise InvalidAPIUsageError(msg)

        db.schema = cls
        cls._bind_db(db)

    @classmethod
    def is_bound(cls) -> bool:
        """Determines if the schema is bound to a database."""
        return cls._database is not None

    @classmethod
    def _get_fwd_rels(cls) -> list[Relation]:
        return [
            prop
            for prop in cls.get_props()
            if isinstance(prop, Relation) and not (prop._is_two_way_target or prop.is_self_ref)
        ]

    @classmethod
    def _get_self_refs(cls) -> list[Relation]:
        """Get all self-referencing relation properties."""
        return [prop for prop in cls.get_props() if isinstance(prop, Relation) and prop.is_self_ref]

    @classmethod
    def _has_self_refs(cls) -> bool:
        """Determine if self-referencing relation properties are present."""
        return bool([prop for prop in cls.get_props() if isinstance(prop, Relation) and prop.is_self_ref])

    @classmethod
    def _init_self_refs(cls) -> None:
        """Initialise all forward self-referencing relations."""
        if not cls._has_self_refs():
            return
        db = cls.get_db()  # raises if not bound!
        for prop_type in cls._get_self_refs():
            prop_type._rel_schema = cls  # replace placeholder `SelfRef` with this schema

        new_props_schema = {prop.name: prop.obj_ref for prop in cls._get_self_refs()} or None
        session = get_active_session()
        session.api.databases.update(db.obj_ref, schema=new_props_schema)
        cls._set_obj_refs()

    @classmethod
    def _init_self_ref_rollups(cls) -> None:
        """Initialise all rollup properties that reference the same schema."""
        if not cls._has_self_refs():
            return
        db = cls.get_db()  # raises if not bound!

        self_ref_rollups = [prop for prop in cls.get_props() if isinstance(prop, Rollup) and prop.is_self_ref]
        new_props_schema = {prop.name: prop.obj_ref for prop in self_ref_rollups} or None
        session = get_active_session()
        session.api.databases.update(db.obj_ref, schema=new_props_schema)
        cls._set_obj_refs()

    @classmethod
    def _update_bwd_rels(cls) -> None:
        """Update the default property name in case of a two-way relation in the external target schema.

        By default the property in the target schema is named "Related to <this_database> (<this_field>)"
        which is then set to the name specified as backward relation.
        """
        for prop_type in cls.to_dict().values():
            if isinstance(prop_type, Relation) and prop_type.is_two_way:
                prop_type._update_bwd_rel()

    @classmethod
    def _set_obj_refs(cls) -> None:
        """Map obj_refs from the properties of the schema to obj_ref.properties of the bound database."""
        db_props_dct = cls.get_db().obj_ref.properties
        for prop_name, prop_type in cls.to_dict().items():
            obj_ref = db_props_dct.get(prop_name)
            if obj_ref:
                prop_type.obj_ref = obj_ref


class Title(Property[obj_schema.Title], wraps=obj_schema.Title):
    """Defines the mandatory title property in a database."""


class Text(Property[obj_schema.RichText], wraps=obj_schema.RichText):
    """Defines a text property in a database."""


class Number(Property[obj_schema.Number], wraps=obj_schema.Number):
    """Defines a number property in a database."""

    def __init__(self, name: str | None = None, *, format: NumberFormat | str = NumberFormat.NUMBER):  # noqa: A002
        super().__init__(name, format=NumberFormat(format))

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
        self._update_prop(self.obj_ref)


class Select(Property[obj_schema.Select], wraps=obj_schema.Select):
    """Defines a select property in a database."""

    def __init__(self, name: str | None = None, *, options: list[Option] | type[OptionNS]):
        if isinstance(options, type) and issubclass(options, OptionNS):
            options = options.to_list()

        option_objs = [option.obj_ref for option in options]
        super().__init__(name, options=option_objs)

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

        updates = check_for_updates(self.options, new_options)
        if updates:
            msg = f'Cannot update options of {self.name} property: {updates}'
            raise InvalidAPIUsageError(msg)

        self.obj_ref.select.options = [option.obj_ref for option in new_options]
        self._update_prop(self.obj_ref)


class MultiSelect(Property[obj_schema.MultiSelect], wraps=obj_schema.MultiSelect):
    """Defines a multi-select property in a database."""

    def __init__(self, name: str | None = None, *, options: list[Option] | type[OptionNS]):
        if isinstance(options, type) and issubclass(options, OptionNS):
            options = options.to_list()

        option_objs = [option.obj_ref for option in options]
        super().__init__(name, options=option_objs)

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
        diffs = check_for_updates(self.options, new_options)
        if diffs:
            msg = f'Cannot update options of {self.name} property: {diffs}'
            raise InvalidAPIUsageError(msg)

        self.obj_ref.multi_select.options = [option.obj_ref for option in new_options]
        self._update_prop(self.obj_ref)


class Status(Property[obj_schema.Status], wraps=obj_schema.Status):
    """Defines a status property in a database.

    The Notion API doesn't allow to create a property of this type.
    Sending it to the API with options and option groups defined results in an error
    about the existence of the keys `options` and `groups` and removing them
    creates a database with the property missing... ignorance is bliss.

    Also the Status configuration is not mentioned as a
    [Property Schema Object])https://developers.notion.com/reference/property-schema-object).

    It can still be used to check a schema.
    """

    allowed_at_creation = False

    def __init__(
        self,
        name: str | None = None,
        *,
        to_do: list[Option] | type[OptionNS] | None = None,
        in_progress: list[Option] | type[OptionNS] | None = None,
        complete: list[Option] | type[OptionNS] | None = None,
    ) -> None:
        def _normalize(group: list[Option] | type[OptionNS] | None) -> list[Option]:
            if group is None:
                return []
            elif isinstance(group, type) and issubclass(group, OptionNS):
                return group.to_list()
            else:
                return group

        to_do = _normalize(to_do)
        in_progress = _normalize(in_progress)
        complete = _normalize(complete)

        to_do_group = OptionGroup(OptionGroupType.TO_DO, options=to_do)
        in_progress_group = OptionGroup(OptionGroupType.IN_PROGRESS, options=in_progress)
        complete_group = OptionGroup(OptionGroupType.COMPLETE, options=complete)

        option_objs = [option.obj_ref for option in (*to_do, *in_progress, *complete)]
        group_objs = [group.obj_ref for group in (to_do_group, in_progress_group, complete_group)]
        super().__init__(name, options=option_objs, groups=group_objs)

    @property
    def options(self) -> list[Option]:
        """Return the options of this status property."""
        return [Option.wrap_obj_ref(option) for option in self.obj_ref.status.options]

    def _extract_groups(self) -> list[tuple[obj_schema.SelectGroup, list[Option]]]:
        """Extract options from a group."""

        def get_id(option: Option) -> str:
            try:
                return option.id
            except UnsetError:
                return option.name

        option_ids = {get_id(option): option for option in self.options}

        groups = []
        for group_obj in self.obj_ref.status.groups:
            # note that opt_id might be a name here, as explained in `OptionGroup``
            group_options = [option_ids[opt_id] for opt_id in set(group_obj.option_ids) & set(option_ids.keys())]
            groups.append((group_obj, group_options))

        return groups

    @property
    def groups(self) -> list[OptionGroup]:
        """Return the option groups of this status property."""
        return [OptionGroup.wrap_obj_ref(group, options=options) for group, options in self._extract_groups()]


class Date(Property[obj_schema.Date], wraps=obj_schema.Date):
    """Defines a date property in a database."""


class Person(Property[obj_schema.People], wraps=obj_schema.People):
    """Defines a person/people property in a database."""


class Files(Property[obj_schema.Files], wraps=obj_schema.Files):
    """Defines a files property in a database."""


class Checkbox(Property[obj_schema.Checkbox], wraps=obj_schema.Checkbox):
    """Defines a checkbox property in database."""


class Email(Property[obj_schema.Email], wraps=obj_schema.Email):
    """Defines an e-mail property in a database."""


class URL(Property[obj_schema.URL], wraps=obj_schema.URL):
    """Defines a URL property in a database."""


class Phone(Property[obj_schema.PhoneNumber], wraps=obj_schema.PhoneNumber):
    """Defines a phone number property in a database."""


class Formula(Property[obj_schema.Formula], wraps=obj_schema.Formula):
    """Defines a formula property in a database.

    Currently the formula expression cannot reference other formula properties, e.g. `prop("other formula")`
    This is a limitation of the Notion API.
    """

    @property
    def formula(self) -> str:
        """Return the formula of this property."""
        return self.obj_ref.formula.expression

    @formula.setter
    def formula(self, formula: str) -> None:
        """Set the formula of this property."""
        self.obj_ref.formula.expression = formula
        self._update_prop(self.obj_ref)


class SelfRef(Schema):
    """Target schema for self-referencing database relations."""

    _ = Title('title')  # mandatory title property, used for nothing.


class Relation(Property[obj_schema.Relation], wraps=obj_schema.Relation):
    """Relation to another database."""

    _rel_schema: type[Schema] | None = None  # other schema, i.e. of the target database
    _two_way_prop: Property | str | None = None  # other property, i.e. of the target database

    def __init__(
        self, name: str | None = None, *, schema: type[Schema] | None = None, two_way_prop: Relation | str | None = None
    ):
        self._name = name
        self._owner = None
        # Note that we don't call super().__init__ here since we only know how to build the obj_ref later.
        if two_way_prop and not schema:
            msg = '`schema` needs to be provided if `two_way_prop` is set!'
            raise RuntimeError(msg)

        if isinstance(schema, Property):
            msg = 'Please provide a schema, not a property! Use `two_way_prop` to specify a property.'
            raise ValueError(msg)

        self._rel_schema = schema

        if two_way_prop is not None:
            if not isinstance(two_way_prop, Relation | str):
                msg = 'The two-way property parameter needs to be of type Relation or str!'
                raise ValueError(msg)

            if isinstance(two_way_prop, Relation) and two_way_prop._rel_schema is not None:
                msg = f'The two-way property {two_way_prop.name} must not reference a schema itself!'
                raise ValueError(msg)

            self._two_way_prop = two_way_prop

    @property
    def _is_init_ready(self) -> bool:
        """Determines if the Relation can be initialized"""
        return not (self._rel_schema is SelfRef or self._is_two_way_target)

    def _make_obj_ref(self) -> obj_schema.Relation:
        """Create the low-level object reference for this relation."""
        try:
            db = self.schema.get_db()
        except SchemaNotBoundError as e:
            msg = f"A database with schema '{self.schema.__name__}' needs to be created first!"
            raise RelationError(msg) from e

        if self._two_way_prop:
            obj_ref = obj_schema.DualPropertyRelation.build_relation(db.id)
        else:
            obj_ref = obj_schema.SinglePropertyRelation.build_relation(db.id)
        return obj_ref

    @property
    def obj_ref(self) -> obj_schema.Relation:
        """Initialize the low-level object references for this relation."""
        if not self._is_init:
            # Delayed construction of obj_ref to assure that a self-reference is resolved.
            self._obj_ref = self._make_obj_ref()
        return self._obj_ref

    @obj_ref.setter
    def obj_ref(self, new_obj_ref: obj_schema.Relation) -> None:
        self._obj_ref = new_obj_ref

    @property
    def schema(self) -> type[Schema]:
        """Schema of the relation database."""
        if self._rel_schema is None and self._get_owner().is_bound():
            session = get_active_session()
            self._rel_schema = session.get_db(self.obj_ref.relation.database_id).schema
        elif self._rel_schema is not None and self._rel_schema is not SelfRef:
            return self._rel_schema
        else:
            msg = 'The relation is not yet related to another schema!'
            raise RelationError(msg)
        return self._rel_schema

    @schema.setter
    def schema(self, new_schema: type[Schema]) -> None:
        """Set the schema of the relation database."""
        if self.is_two_way:
            new_rel = obj_schema.DualPropertyRelation.build_relation(new_schema.get_db().id)
        else:
            new_rel = obj_schema.SinglePropertyRelation.build_relation(new_schema.get_db().id)
        self.obj_ref.relation = new_rel.relation
        self._update_prop(self.obj_ref)
        self._rel_schema = new_schema

    def _rename_two_way_prop(self, new_prop_name: str) -> None:
        """Rename the two-way property in the target schema.

        This is necessary as a two-way relation is created with a default name,
        which is rather a bug in the Notion API itself.
        """
        two_way_prop_rel = cast(obj_schema.DualPropertyRelation, self.obj_ref.relation)
        tmp_prop_name = raise_unset(two_way_prop_rel.dual_property.synced_property_name)
        db = self.schema.get_db()
        db.reload()
        if (back_ref_prop_type := db.schema[tmp_prop_name]) is not None:
            back_ref_prop_type.name = new_prop_name
            back_ref_prop_type._attr_name = rich_text.snake_case(new_prop_name)

    @property
    def two_way_prop(self) -> Property | None:
        """Return the target property object of a two-way relation."""
        if self._two_way_prop:
            if isinstance(self._two_way_prop, str):
                self._two_way_prop = self._get_owner().get_prop(self._two_way_prop)
            return self._two_way_prop
        elif self._is_init and isinstance(self.obj_ref.relation, obj_schema.DualPropertyRelation):
            prop_name = raise_unset(self.obj_ref.relation.dual_property.synced_property_name)
            return self.schema.get_prop(prop_name) if prop_name else None
        else:
            return None

    @two_way_prop.setter
    def two_way_prop(self, prop_name: str | None) -> None:
        """Set the target property as string of a two-way relation.

        The `new_prop_name` is the name of the property in the target schema.
        """

        if (db := self.schema.get_db()) is None:
            msg = 'The target schema of the relation is not bound to a database'
            raise RelationError(msg)

        if prop_name is None:  # delete the two-way property
            if self.two_way_prop is None:
                return
            target_schema = self.schema
            target_two_way_prop = self.two_way_prop.name
            new_rel = obj_schema.SinglePropertyRelation.build_relation(db.id)
            self.obj_ref.relation = new_rel.relation
            self.obj_ref = self._update_prop(self.obj_ref)
            # Strangely enough, the two-way property is not removed from the target schema
            # also it is no longer a two-way relation.
            del target_schema[target_two_way_prop]
        else:
            new_rel = obj_schema.DualPropertyRelation.build_relation(db.id)
            self.obj_ref.relation = cast(obj_schema.DualPropertyRelation, new_rel.relation)
            self.obj_ref = self._update_prop(self.obj_ref)
            self._rename_two_way_prop(prop_name)

        self._rel_schema = None  # Don't rely on the initialization of the schema

    @property
    def is_two_way(self) -> bool:
        """Determine if this relation is a two-way relation."""
        return self._two_way_prop is not None or (
            self._is_init and isinstance(self.obj_ref.relation, obj_schema.DualPropertyRelation)
        )

    @property
    def is_self_ref(self) -> bool:
        """Determines if this relation is self referencing the same schema."""
        return (self._rel_schema is SelfRef) or (self._rel_schema is self._get_owner())

    @property
    def _is_two_way_target(self) -> bool:
        """Determines if this relation is a target of a two-way relation."""
        return self._rel_schema is None

    def _update_bwd_rel(self) -> None:
        """Change the default name of a two-way relation target to the defined one."""
        if not isinstance(self.obj_ref.relation, obj_schema.DualPropertyRelation):
            msg = f'Trying to inialize backward relation for one-way relation {self.name}'
            raise SchemaError(msg)

        obj_synced_property_name = self.obj_ref.relation.dual_property.synced_property_name
        two_way_prop_name = self.two_way_prop.name if self.two_way_prop else None

        if obj_synced_property_name != two_way_prop_name:
            session = get_active_session()

            # change the old default name in the target schema to what was passed during initialization
            other_db = self.schema.get_db()

            if is_unset(prop_id := self.obj_ref.relation.dual_property.synced_property_id):
                msg = 'No synced property ID found in the relation object'
                raise SchemaError(msg)

            schema_dct = {prop_id: obj_schema.RenameProp(name=two_way_prop_name)}
            session.api.databases.update(db=other_db.obj_ref, schema=schema_dct)
            other_db.schema._set_obj_refs()

            our_db = self._get_owner().get_db()
            session.api.databases.update(db=our_db.obj_ref, schema={})  # sync obj_ref
            our_db.schema._set_obj_refs()


class Rollup(Property[obj_schema.Rollup], wraps=obj_schema.Rollup):
    """Defines the rollup property in a database.

    If the relation propery is a self-referencing relation, i.e. `uno.PropType.Relation(uno.SelfRef)` in the schema,
    then the `property` must be a `str` of the corresponding property name.
    """

    def __init__(
        self,
        name: str | None = None,
        *,
        relation: Relation,
        rollup: Property,
        calculate: AggFunc | str = AggFunc.SHOW_ORIGINAL,
    ):
        calculate = AggFunc.from_alias(calculate) if not isinstance(calculate, AggFunc) else calculate

        # ToDo: One could check here if property really is a property in the database where relation points to
        super().__init__(name, relation=relation.name, property=rollup.name, function=calculate)

    @property
    def _is_init_ready(self) -> bool:
        """Determines if the relation of the rollup is ready to be initialized."""
        try:
            return self.relation_prop._is_init_ready
        except SchemaError:  # DB is not bound yet
            return False

    @property
    def is_self_ref(self) -> bool:
        """Determines if this rollup is self-referencing the same schema."""
        return self.relation_prop.is_self_ref

    @property
    def relation_prop(self) -> Relation:
        """Return the relation property object of the rollup."""
        rel_prop = self._get_owner().get_prop(self.obj_ref.rollup.relation_property_name)
        if isinstance(rel_prop, Relation):
            return rel_prop
        else:
            msg = f'Rollup property {self.name} is not bound to a Relation property'
            raise RollupError(msg)

    @property
    def rollup_prop(self) -> Property:
        """Return the rollup property object of the rollup."""
        return self._get_owner().get_prop(self.obj_ref.rollup.rollup_property_name)

    @property
    def calculate(self) -> AggFunc:
        """Return the aggregation function of the rollup."""
        return self.obj_ref.rollup.function


class CreatedTime(Property[obj_schema.CreatedTime], wraps=obj_schema.CreatedTime):
    """Defines the created-time property in a database."""


class CreatedBy(Property[obj_schema.CreatedBy], wraps=obj_schema.CreatedBy):
    """Defines the created-by property in a database."""


class LastEditedBy(Property[obj_schema.LastEditedBy], wraps=obj_schema.LastEditedBy):
    """Defines the last-edited-by property in a database."""


class LastEditedTime(Property[obj_schema.LastEditedTime], wraps=obj_schema.LastEditedTime):
    """Defines the last-edited-time property in a database."""


class ID(Property[obj_schema.UniqueID], wraps=obj_schema.UniqueID):
    """Defines a unique ID property in a database."""

    allowed_at_creation = False

    @property
    def prefix(self) -> str:
        opt_prefix = self.obj_ref.unique_id.prefix
        return '' if opt_prefix is None else opt_prefix


class Verification(Property[obj_schema.Verification], wraps=obj_schema.Verification):
    """Defines a unique ID property in a database."""

    allowed_at_creation = False


class Button(Property[obj_schema.Button], wraps=obj_schema.Button):
    """Defines a button property in a database."""

    allowed_at_creation = False


class DefaultSchema(Schema):
    # Default database schema of Notion.
    #
    # As inferred by just creating an empty database in the Notion UI.
    # NOTE: Use no docstring here, otherwise it will be used as the database description.

    name = Title('Name')


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
