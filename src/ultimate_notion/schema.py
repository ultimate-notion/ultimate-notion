"""Functionality around defining a database schema.

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

from typing import TYPE_CHECKING, Any, TypeVar, cast

from tabulate import tabulate

import ultimate_notion.obj_api.schema as obj_schema
from ultimate_notion.obj_api.schema import AggFunc, NumberFormat
from ultimate_notion.objects import Option, OptionGroup, OptionNS, RichText
from ultimate_notion.props import PropertyValue
from ultimate_notion.text import snake_case
from ultimate_notion.utils import SList, Wrapper, get_active_session, get_repr, is_notebook

if TYPE_CHECKING:
    from ultimate_notion.database import Database
    from ultimate_notion.page import Page

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
    ) -> type[PageSchema]:
        """Creation of a schema from a dictionary for easy support of dynamically created schemas."""
        title_cols = [k for k, v in schema_dct.items() if isinstance(v, Title)]
        if not title_cols:
            msg = 'Missing an item with property type `Title` as value'
            raise SchemaError(msg)
        elif len(title_cols) > 1:
            msg = f'More than one item with property type `Title` as value found: {", ".join(title_cols)}'
            raise SchemaError(msg)

        cls_name = f'{cls.__name__}FromDct'
        attrs: dict[str, Any] = {'db_desc': db_desc}
        for col_name, prop_type in schema_dct.items():
            attrs[snake_case(col_name)] = Column(col_name, prop_type)
        return type(cls_name, (PageSchema,), attrs, db_title=db_title)

    @classmethod
    def create(cls, **kwargs) -> Page:
        """Create a page using this schema with a bound database."""
        return cls.get_db().create_page(**kwargs)

    @classmethod
    def get_cols(cls) -> list[Column]:
        """Get all columns of this schema."""
        return [col for col in cls.__dict__.values() if isinstance(col, Column)]

    @classmethod
    def get_col(cls, col_name: str) -> Column:
        """Get a specific column from this schema assuming that column names are unique."""
        return SList([col for col in cls.get_cols() if col.name == col_name]).item()

    @classmethod
    def to_dict(cls) -> dict[str, PropertyType]:
        """Convert this schema to a dictionary."""
        return {col.name: col.type for col in cls.get_cols()}

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
        for col in cls.get_cols():
            rows.append((col.name, col.type, col.attr_name))

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
        """Called by Jupyter Lab automatically to display this schema."""
        return cls.as_table(tablefmt='html')

    @classmethod
    def get_title_col(cls) -> Column:
        """Returns the column holding the title of the pages."""
        return SList(col for col in cls.get_cols() if isinstance(col.type, Title)).item()

    @classmethod
    def is_consistent_with(cls, other_schema: type[PageSchema]) -> bool:
        """Is this schema consistent with another ignoring backward relations if not in other schema."""
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
        """Get the database that is bound to this schema."""
        if cls.is_bound() and cls._database is not None:
            return cls._database
        else:
            raise SchemaNotBoundError(cls)

    @classmethod
    def bind_db(cls, db: Database):
        """Bind the PageSchema to the corresponding database for back-reference."""
        cls._database = db
        cls._set_obj_refs()

    @classmethod
    def is_bound(cls) -> bool:
        """Determines if the schema is bound to a database."""
        return cls._database is not None

    @classmethod
    def _get_fwd_rels(cls) -> list[Column]:
        return [
            col
            for col in cls.get_cols()
            if isinstance(col.type, Relation) and not (col.type._is_two_way_target or col.type.is_self_ref)
        ]

    @classmethod
    def _init_fwd_rels(cls):
        """Initialise all non-self-referencing forward relations assuming that the target schemas exist."""
        for col in cls._get_fwd_rels():
            col_type = cast(Relation, col.type)
            col_type._make_obj_ref()

    @classmethod
    def _get_self_refs(cls) -> list[Column]:
        """Get all self-referencing relation columns."""
        return [col for col in cls.get_cols() if isinstance(col.type, Relation) and col.type.is_self_ref]

    @classmethod
    def _has_self_refs(cls) -> bool:
        """Determine if self-referencing relation columns are present."""
        return bool([col for col in cls.get_cols() if isinstance(col.type, Relation) and col.type.is_self_ref])

    @classmethod
    def _init_self_refs(cls):
        """Initialise all forward self-referencing relations."""
        if not cls._has_self_refs():
            return
        db = cls.get_db()  # raises if not bound!
        for col in cls._get_self_refs():
            col_type = cast(Relation, col.type)
            col_type._schema = cls  # replace placeholder `SelfRef` with this schema
            col_type._make_obj_ref()

        self_refs_dct = {col.name: col.type.obj_ref for col in cls._get_self_refs()} or None
        session = get_active_session()
        db.obj_ref = session.api.databases.update(db.obj_ref, schema=self_refs_dct)
        cls._set_obj_refs()

    @classmethod
    def _get_init_cols(cls) -> list[Column]:
        """Get all columns that are initialized by now."""
        return [col for col in cls.get_cols() if hasattr(col.type, 'obj_ref')]

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


class PropertyType(Wrapper[T], wraps=obj_schema.PropertyType):
    """Base class for Notion property objects.

    Property types define the value types of columns in a database, e.g. number, date, text, etc.
    """

    obj_ref: T
    #: If the Notion API allows to create a new database with a column of this type
    allowed_at_creation = True
    #: Back reference to the column having this type
    col_ref: Column | None = None

    @property
    def id(self) -> str | None:
        """Return identifier of this property type."""
        return self.obj_ref.id

    @property
    def name(self) -> str | None:
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


class Column:
    """Column with a name and a certain Property Type for defining a Notion database schema.

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
        self._type.col_ref = self  # link back to allow access to _schema, _py_name e.g. for relations

    def __repr__(self) -> str:
        return get_repr(self, name='Column', desc=self.type)

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


class Title(PropertyType[obj_schema.Title], wraps=obj_schema.Title):
    """Defines the mandatory title column in a database."""


class Text(PropertyType[obj_schema.RichText], wraps=obj_schema.RichText):
    """Defines a text column in a database."""


class Number(PropertyType[obj_schema.Number], wraps=obj_schema.Number):
    """Defines a number column in a database."""

    def __init__(self, number_format: NumberFormat):
        super().__init__(number_format)


class Select(PropertyType[obj_schema.Select], wraps=obj_schema.Select):
    """Defines a select column in a database."""

    def __init__(self, options: list[Option] | type[OptionNS]):
        if isinstance(options, type) and issubclass(options, OptionNS):
            options = options.to_list()

        option_objs = [option.obj_ref for option in options]
        super().__init__(option_objs)

    @property
    def options(self) -> dict[str, Option]:
        return {option.name: Option.wrap_obj_ref(option) for option in self.obj_ref.select.options}


class MultiSelect(PropertyType[obj_schema.MultiSelect], wraps=obj_schema.MultiSelect):
    """Defines a multi-select column in a database."""

    def __init__(self, options: list[Option] | type[OptionNS]):
        if isinstance(options, type) and issubclass(options, OptionNS):
            options = options.to_list()

        option_objs = [option.obj_ref for option in options]
        super().__init__(option_objs)

    @property
    def options(self) -> dict[str, Option]:
        return {option.name: Option.wrap_obj_ref(option) for option in self.obj_ref.multi_select.options}


class Status(PropertyType[obj_schema.Status], wraps=obj_schema.Status):
    """Defines a status column in a database.

    The Notion API doesn't allow to create a column of this type.
    Sending it to the API with options and option groups defined results in an error
    about the existence of the keys `options` and `groups` and removing them
    creates a database with the column missing... ignorance is bliss.

    Also the Status configuration is not mentioned as a
    [Property Schema Object])https://developers.notion.com/reference/property-schema-object).
    """

    allowed_at_creation = False

    @property
    def options(self) -> list[Option]:
        return [Option.wrap_obj_ref(option) for option in self.obj_ref.status.options]

    @property
    def groups(self) -> list[OptionGroup]:
        return [OptionGroup.wrap_obj_ref(group, options=self.options) for group in self.obj_ref.status.groups]


class Date(PropertyType[obj_schema.Date], wraps=obj_schema.Date):
    """Defines a date column in a database."""


class People(PropertyType[obj_schema.People], wraps=obj_schema.People):
    """Defines a people column in a database."""


class Files(PropertyType[obj_schema.Files], wraps=obj_schema.Files):
    """Defines a files column in a database."""


class Checkbox(PropertyType[obj_schema.Checkbox], wraps=obj_schema.Checkbox):
    """Defines a checkbox column in database."""


class Email(PropertyType[obj_schema.Email], wraps=obj_schema.Email):
    """Defines an e-mail column in a database."""


class URL(PropertyType[obj_schema.URL], wraps=obj_schema.URL):
    """Defines a URL column in a database."""


class PhoneNumber(PropertyType[obj_schema.PhoneNumber], wraps=obj_schema.PhoneNumber):
    """Defines a phone number column in a database."""


class Formula(PropertyType[obj_schema.Formula], wraps=obj_schema.Formula):
    """Defines a formula column in a database.

    Currently the formula expression cannot reference other formula columns, e.g. `prop("other formula")`
    This is a limitation of the API.
    """

    def __init__(self, expression: str):
        super().__init__(expression)


class RelationError(SchemaError):
    """Error if a Relation cannot be initialised."""


class SelfRef(PageSchema, db_title=None):
    """Target schema for self-referencing database relations."""


class Relation(PropertyType[obj_schema.Relation], wraps=obj_schema.Relation):
    """Relation to another database."""

    _schema: type[PageSchema] | None = None  # other schema, i.e. of the target database
    _two_way_col: Column | None = None  # other column, i.e. of the target database

    def __init__(self, schema: type[PageSchema] | None = None, *, two_way_col: Column | None = None):
        if two_way_col and not schema:
            msg = '`schema` needs to be provided if `two_way_col` is set'
            raise RuntimeError(msg)

        if isinstance(schema, Column):
            msg = 'Please provide a schema, not a column! Use `two_way_col` to specify a column.'
            raise ValueError(msg)

        self._schema = schema

        if two_way_col is not None:
            if not isinstance(two_way_col.type, Relation):
                msg = f'The two-way column {two_way_col.name} needs to be of type Relation!'
                raise ValueError(msg)

            if two_way_col.type.schema is not None:
                msg = f'The two-way column {two_way_col.name} must not reference a schema itself'
                raise ValueError(msg)

            self._two_way_col = two_way_col

    @property
    def schema(self) -> type[PageSchema] | None:
        """Schema of the relation database."""
        if self._schema:
            return self._schema if self._schema is not SelfRef else None
        elif self.col_ref is not None and self.col_ref._schema.is_bound():
            db = self.col_ref._schema._database
            session = get_active_session()
            return session.get_db(self.obj_ref.relation.database_id).schema if db is not None else None
        else:
            return None

    @property
    def _is_two_way_target(self) -> bool:
        """Determines if relation is meant as target for a two-way relation."""
        return self._schema is None

    @property
    def two_way_col(self) -> Column | None:
        """Return the target column object of a two-way relation."""
        if self._two_way_col:
            return self._two_way_col
        elif (
            hasattr(self, 'obj_ref')
            and self.schema
            and isinstance(self.obj_ref.relation, obj_schema.DualPropertyRelation)
        ):
            prop_name = self.obj_ref.relation.dual_property.synced_property_name
            return self.schema.get_col(prop_name) if prop_name else None
        else:
            return None

    @property
    def is_two_way(self) -> bool:
        """Determine if this relation is a two-way relation."""
        return self.two_way_col is not None

    @property
    def is_self_ref(self) -> bool:
        """Determines if this relation is self referencing the same schema."""
        return (self._schema is SelfRef) or (self.col_ref is not None and self._schema is self.col_ref._schema)

    def _make_obj_ref(self):
        """Initialize the low-level object references for this relation.

        This function is used only internally and called during the forward initialization.
        """
        try:
            db = self.schema.get_db()
        except SchemaNotBoundError as e:
            msg = f"A database with schema '{self.schema.__name__}' needs to be created first!"
            raise RelationError(msg) from e

        if self.two_way_col:
            self.obj_ref = obj_schema.DualPropertyRelation.build(db.id)
        else:
            self.obj_ref = obj_schema.SinglePropertyRelation.build(db.id)

    def _update_bwd_rel(self):
        """Change the default name of a two-way relation target to the defined one."""
        if self.col_ref is None:
            msg = 'Trying to inialize a backward relation for one-way relation that is not bound to a column'
            raise SchemaError(msg)

        if not (isinstance(self.obj_ref.relation, obj_schema.DualPropertyRelation)):
            msg = f'Trying to inialize backward relation for one-way relation {self.col_ref.name}'
            raise SchemaError(msg)

        obj_synced_property_name = self.obj_ref.relation.dual_property.synced_property_name
        two_way_col_name = self._two_way_col.name
        if obj_synced_property_name != two_way_col_name:
            session = get_active_session()

            # change the old default name in the target schema to what was passed during initialization
            other_db = self.schema.get_db()
            prop_id = self.obj_ref.relation.dual_property.synced_property_id
            schema_dct = {prop_id: obj_schema.RenameProp(name=two_way_col_name)}
            session.api.databases.update(db=other_db.obj_ref, schema=schema_dct)
            other_db.schema._set_obj_refs()

            our_db = self.col_ref._schema.get_db()
            session.api.databases.update(db=our_db.obj_ref, schema={})  # sync obj_ref
            our_db.schema._set_obj_refs()


class RollupError(SchemaError):
    """Error if definition of rollup is wrong."""


class Rollup(PropertyType[obj_schema.Rollup], wraps=obj_schema.Rollup):
    """Defines the rollup column in a database."""

    def __init__(self, relation: Column, property: Column, calculate: AggFunc):  # noqa: A002
        if not isinstance(relation.type, Relation):
            msg = f'Relation {relation} must be of type Relation'
            raise RollupError(msg)
        # ToDo: One could check here if property really is a property in the database where relation points to
        super().__init__(relation.name, property.name, calculate)


class CreatedTime(PropertyType[obj_schema.CreatedTime], wraps=obj_schema.CreatedTime):
    """Defines the created-time column in a database."""


class CreatedBy(PropertyType[obj_schema.CreatedBy], wraps=obj_schema.CreatedBy):
    """Defines the created-by column in a database."""


class LastEditedBy(PropertyType[obj_schema.LastEditedBy], wraps=obj_schema.LastEditedBy):
    """Defines the last-edited-by column in a database."""


class LastEditedTime(PropertyType[obj_schema.LastEditedTime], wraps=obj_schema.LastEditedTime):
    """Defines the last-edited-time column in a database."""


class ID(PropertyType[obj_schema.UniqueID], wraps=obj_schema.UniqueID):
    """Defines a unique ID column in a database."""

    allowed_at_creation = False

    @property
    def prefix(self) -> str:
        opt_prefix = self.obj_ref.unique_id.prefix
        return '' if opt_prefix is None else opt_prefix


class Verification(PropertyType[obj_schema.Verification], wraps=obj_schema.Verification):
    """Defines a unique ID column in a database."""

    allowed_at_creation = False


class DefaultSchema(PageSchema, db_title=None):
    """Default database schema of Notion.

    As inferred by just creating an empty database in the Notion UI.
    """

    name = Column('Name', Title())
    tags = Column('Tags', MultiSelect([]))


class ColType:
    """Namespace class of all columns types for easier access."""

    Title = Title
    Text = Text
    Number = Number
    Select = Select
    MultiSelect = MultiSelect
    Status = Status
    Date = Date
    People = People
    Files = Files
    Checkbox = Checkbox
    Email = Email
    URL = URL
    PhoneNumber = PhoneNumber
    Formula = Formula
    Relation = Relation
    Rollup = Rollup
    CreatedTime = CreatedTime
    CreatedBy = CreatedBy
    LastEditedTime = LastEditedTime
    LastEditedBy = LastEditedBy
    ID = ID
    Verification = Verification
