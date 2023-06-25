"""Functionality around defining a database schema"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

from notional import schema

if TYPE_CHECKING:
    pass


class PageSchema:
    @classmethod
    def to_dict(cls) -> dict[str, PropertyType]:
        return {prop.name: prop.type for prop in cls.__dict__.values() if isinstance(prop, Property)}

    @classmethod
    def create(cls, **kwargs):
        """Create a page using this schema"""
        # ToDo: Next Step
        # """Create a new instance of the ConnectedPage type.

        # Any properties that support object composition may be defined in `kwargs`.

        # This operation takes place on the Notion server, creating the page immediately.

        # :param kwargs: the properties to initialize for this object as parameters, i.e.
        #   `name=value`, where `name` is the attribute in the custom type and `value` is
        #   a supported type for composing.
        # """

        # if cls._notional__session is None:
        #     raise ValueError("Cannot create Page; invalid session")

        # if cls._notional__database is None:
        #     raise ValueError("Cannot create Page; invalid database")

        # logger.debug("creating new %s :: %s", cls, cls._notional__database)
        # parent = DatabaseRef(database_id=cls._notional__database)

        # page = cls._notional__session.pages.create(parent=parent)
        # logger.debug("=> connected page :: %s", page.id)

        # connected = cls(page)

        # # FIXME it would be better to convert properties to a dict and pass to the API,
        # # rather than setting them individually here...
        # for name, value in kwargs.items():
        #     setattr(connected, name, value)

        # return connected


class Function(str, Enum):
    """Enum of standard aggregation functions."""

    COUNT = 'count'
    COUNT_VALUES = 'count_values'
    COUNT_PER_GROUP = 'count_per_group'

    EMPTY = 'empty'
    NOT_EMPTY = 'not_empty'

    CHECKED = 'checked'
    UNCHECKED = 'unchecked'

    PERCENT_EMPTY = 'percent_empty'
    PERCENT_NOT_EMPTY = 'percent_not_empty'
    PERCENT_CHECKED = 'percent_checked'
    PERCENT_PER_GROUP = 'percent_per_group'

    AVERAGE = 'average'
    MIN = 'min'
    MAX = 'max'
    MEDIAN = 'median'
    RANGE = 'range'
    SUM = 'sum'

    DATE_RANGE = 'date_range'
    EARLIEST_DATE = 'earliest_date'
    LATEST_DATE = 'latest_date'

    SHOW_ORIGINAL = 'show_original'
    SHOW_UNIQUE = 'show_unique'
    UNIQUE = 'unique'


class NumberFormat(str, Enum):
    """Enum of available number formats in Notion."""

    NUMBER = 'number'
    NUMBER_WITH_COMMAS = 'number_with_commas'
    PERCENT = 'percent'
    DOLLAR = 'dollar'
    CANADIAN_DOLLAR = 'canadian_dollar'
    EURO = 'euro'
    POUND = 'pound'
    YEN = 'yen'
    RUBLE = 'ruble'
    RUPEE = 'rupee'
    WON = 'won'
    YUAN = 'yuan'
    REAL = 'real'
    LIRA = 'lira'
    RUPIAH = 'rupiah'
    FRANC = 'franc'
    HONG_KONG_DOLLAR = 'hong_kong_dollar'
    NEW_ZEALAND_DOLLAR = 'new_zealand_dollar'
    KRONA = 'krona'
    NORWEGIAN_KRONE = 'norwegian_krone'
    MEXICAN_PESO = 'mexican_peso'
    RAND = 'rand'
    NEW_TAIWAN_DOLLAR = 'new_taiwan_dollar'
    DANISH_KRONE = 'danish_krone'
    ZLOTY = 'zloty'
    BAHT = 'baht'
    FORINT = 'forint'
    KORUNA = 'koruna'
    SHEKEL = 'shekel'
    CHILEAN_PESO = 'chilean_peso'
    PHILIPPINE_PESO = 'philippine_peso'
    DIRHAM = 'dirham'
    COLOMBIAN_PESO = 'colombian_peso'
    RIYAL = 'riyal'
    RINGGIT = 'ringgit'
    LEU = 'leu'
    ARGENTINE_PESO = 'argentine_peso'
    URUGUAYAN_PESO = 'uruguayan_peso'


class PropertyType:
    """Base class for Notion property objects.

    Used to map our objects to Notional objects.
    """

    obj_ref: schema.PropertyObject

    _notional_type_map: dict[type[schema.PropertyObject], type[PropertyType]] = {}
    _has_compose: dict[type[schema.PropertyObject], bool] = {}

    @property
    def id(self):  # noqa: A003
        return self.obj_ref.id

    @property
    def name(self):
        return self.obj_ref.name

    @property
    def _notional_type_map_inv(self) -> dict[type[PropertyType], type[schema.PropertyObject]]:
        return {v: k for k, v in self._notional_type_map.items()}

    def __init_subclass__(cls, type: type[schema.PropertyObject], **kwargs: Any):  # noqa: A002
        super().__init_subclass__(**kwargs)
        cls._notional_type_map[type] = cls
        cls._has_compose[type] = hasattr(type, '__compose__')

    def __init__(self, *args, **kwargs):
        notional_type = self._notional_type_map_inv[self.__class__]
        if self._has_compose[notional_type]:
            assert not kwargs  # noqa: S101
            self.obj_ref = notional_type[args]
        else:
            assert not args  # noqa: S101
            self.obj_ref = notional_type(**kwargs)


@dataclass
class Property:
    """Property for defining a Notion database schema"""

    name: str
    type: PropertyType  # noqa: A003


class Title(PropertyType, type=schema.Title):
    """Mandatory Title property"""


class Text(PropertyType, type=schema.RichText):
    """Text property"""


class Number(PropertyType, type=schema.Number):
    """Mandatory Title property"""

    def __init__(self, number_format: NumberFormat):
        super().__init__(number_format)


#
# class SelectOption(schema.SelectOption):
#     """Option for select & multi-select property"""
#
#
# class SingleSelect(schema.Select):
#     """Single selection property"""
#
#
# class MultiSelect(schema.MultiSelect):
#     """Multi selection property"""
#
#
# class Status(schema.Status):
#     """Status property"""
#
#
# class Date(schema.Date):
#     """Date property"""
#
#
# class People(schema.People):
#     """People property"""
#
#
# class Files(schema.Files):
#     """Files property"""
#
#
# class Checkbox(schema.Checkbox):
#     """Checkbox property"""
#
#
# class Email(schema.Email):
#     """E-Mail property"""
#
#
# class URL(schema.URL):
#     """URL property"""
#
#
# class Formula(schema.Formula):
#     """Formula Property"""
#
#
