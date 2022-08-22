"""Objects representing a database schema."""

from enum import Enum
from typing import Any, List, Optional
from uuid import UUID

from .core import DataObject, NestedObject, TypedObject
from .text import Color


class Function(str, Enum):
    """Standard aggregation functions."""

    COUNT_ALL = "count_all"
    COUNT_VALUES = "count_values"
    COUNT_UNIQUE_VALUES = "count_unique_values"
    COUNT_EMPTY = "count_empty"
    COUNT_NOT_EMPTY = "count_not_empty"

    PERCENT_EMPTY = "percent_empty"
    PERCENT_NOT_EMPTY = "percent_not_empty"

    AVERAGE = "average"
    MIN = "min"
    MAX = "max"
    MEDIAN = "median"
    RANGE = "range"
    SUM = "sum"

    EARLIEST_DATE = "earliest_date"
    LATEST_DATE = "latest_date"

    SHOW_ORIGINAL = "show_original"


class NumberFormat(str, Enum):
    """Available number formats in Notion."""

    NUMBER = "number"
    NUMBER_WITH_COMMAS = "number_with_commas"
    PERCENT = "percent"
    DOLLAR = "dollar"
    CANADIAN_DOLLAR = "canadian_dollar"
    EURO = "euro"
    POUND = "pound"
    YEN = "yen"
    RUBLE = "ruble"
    RUPEE = "rupee"
    WON = "won"
    YUAN = "yuan"
    REAL = "real"
    LIRA = "lira"
    RUPIAH = "rupiah"
    FRANC = "franc"
    HONG_KONG_DOLLAR = "hong_kong_dollar"
    NEW_ZEALAND_DOLLAR = "new_zealand_dollar"
    KRONA = "krona"
    NORWEGIAN_KRONE = "norwegian_krone"
    MEXICAN_PESO = "mexican_peso"
    RAND = "rand"
    NEW_TAIWAN_DOLLAR = "new_taiwan_dollar"
    DANISH_KRONE = "danish_krone"
    ZLOTY = "zloty"
    BAHT = "baht"
    FORINT = "forint"
    KORUNA = "koruna"
    SHEKEL = "shekel"
    CHILEAN_PESO = "chilean_peso"
    PHILIPPINE_PESO = "philippine_peso"
    DIRHAM = "dirham"
    COLOMBIAN_PESO = "colombian_peso"
    RIYAL = "riyal"
    RINGGIT = "ringgit"
    LEU = "leu"
    ARGENTINE_PESO = "argentine_peso"
    URUGUAYAN_PESO = "uruguayan_peso"


class PropertyObject(TypedObject):
    """Base class for Notion property objects."""

    id: Optional[str] = None
    name: Optional[str] = None


class Title(PropertyObject, type="title"):
    """Defines the title configuration for a database property."""

    title: Any = {}


class RichText(PropertyObject, type="rich_text"):
    """Defines the rich text configuration for a database property."""

    rich_text: Any = {}


class Number(PropertyObject, type="number"):
    """Defines the number configuration for a database property."""

    class _NestedData(NestedObject):
        format: NumberFormat = NumberFormat.NUMBER

    number: _NestedData = _NestedData()

    @classmethod
    def __compose__(cls, format):
        """Create a `Number` object with the expected format."""
        return cls(number=cls._NestedData(format=format))


class SelectOption(DataObject):
    """Options for select & multi-select objects."""

    name: str
    id: str = None
    color: str = Color.DEFAULT

    @classmethod
    def __compose__(cls, name, color=Color.DEFAULT):
        """Create a `SelectOption` object from the given name and color."""
        return cls(name=name, color=color)


class Select(PropertyObject, type="select"):
    """Defines the select configuration for a database property."""

    class _NestedData(NestedObject):
        options: List[SelectOption] = []

    select: _NestedData = _NestedData()

    @classmethod
    def __compose__(cls, options):
        """Create a `Select` object from the list of `SelectOption`'s."""
        return cls(select=cls._NestedData(options=options))


class MultiSelect(PropertyObject, type="multi_select"):
    """Defines the multi-select configuration for a database property."""

    class _NestedData(NestedObject):
        options: List[SelectOption] = []

    multi_select: _NestedData = _NestedData()


class Status(PropertyObject, type="status"):
    """Defines the status configuration for a database property."""

    status: Any = {}


class Date(PropertyObject, type="date"):
    """Defines the date configuration for a database property."""

    date: Any = {}


class People(PropertyObject, type="people"):
    """Defines the people configuration for a database property."""

    people: Any = {}


class Files(PropertyObject, type="files"):
    """Defines the files configuration for a database property."""

    files: Any = {}


class Checkbox(PropertyObject, type="checkbox"):
    """Defines the checkbox configuration for a database property."""

    checkbox: Any = {}


class Email(PropertyObject, type="email"):
    """Defines the email configuration for a database property."""

    email: Any = {}


class URL(PropertyObject, type="url"):
    """Defines the URL configuration for a database property."""

    url: Any = {}


class PhoneNumber(PropertyObject, type="phone_number"):
    """Defines the phone number configuration for a database property."""

    phone_number: Any = {}


class Formula(PropertyObject, type="formula"):
    """Defines the formula configuration for a database property."""

    class _NestedData(NestedObject):
        expression: str = None

    formula: _NestedData = _NestedData()


class Relation(PropertyObject, type="relation"):
    """Defines the relation configuration for a database property."""

    class _NestedData(NestedObject):
        database_id: UUID = None
        synced_property_name: Optional[str] = None
        synced_property_id: Optional[str] = None

    relation: _NestedData = _NestedData()

    @classmethod
    def __compose__(cls, database_id):
        """Create a `Relation` property using the target database ID."""
        return cls(relation=cls._NestedData(database_id=database_id))


class Rollup(PropertyObject, type="rollup"):
    """Defines the rollup configuration for a database property."""

    class _NestedData(NestedObject):
        function: Function = Function.COUNT_ALL

        relation_property_name: Optional[str] = None
        relation_property_id: Optional[str] = None

        rollup_property_name: Optional[str] = None
        rollup_property_id: Optional[str] = None

    rollup: _NestedData = _NestedData()


class CreatedTime(PropertyObject, type="created_time"):
    """Defines the created-time configuration for a database property."""

    created_time: Any = {}


class CreatedBy(PropertyObject, type="created_by"):
    """Defines the created-by configuration for a database property."""

    created_by: Any = {}


class LastEditedBy(PropertyObject, type="last_edited_by"):
    """Defines the last-edited-by configuration for a database property."""

    last_edited_by: Any = {}


class LastEditedTime(PropertyObject, type="last_edited_time"):
    """Defines the last-edited-time configuration for a database property."""

    last_edited_time: Any = {}
