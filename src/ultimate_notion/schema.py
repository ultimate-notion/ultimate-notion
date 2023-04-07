"""Functionality around defining a database schema"""
from __future__ import annotations

from enum import Enum

from notional import schema


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


class PropertyObject:
    """Base class for Notion property objects."""

    obj_ref: schema.PropertyObject

    @property
    def id(self):  # noqa: A003
        return self.obj_ref.id

    @property
    def name(self):
        return self.obj_ref.name


class Title(PropertyObject):
    """Mandatory Title property"""

    def __init__(self):
        self.obj_ref = schema.Title()


class Text(PropertyObject):
    """Text property"""

    def __init__(self):
        self.obj_ref = schema.RichText()


class Number(PropertyObject):
    """Mandatory Title property"""

    def __init__(self, number_format: NumberFormat):
        self.obj_ref = schema.Number[number_format]


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
