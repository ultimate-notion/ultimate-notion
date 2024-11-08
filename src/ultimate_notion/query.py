"""Query the database for pages."""

from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, cast

from pydantic import BaseModel, Field
from typing_extensions import Self

from ultimate_notion import schema
from ultimate_notion.core import get_active_session
from ultimate_notion.obj_api import query as obj_query
from ultimate_notion.obj_api.enums import FormulaType, SortDirection
from ultimate_notion.page import Page
from ultimate_notion.user import User
from ultimate_notion.utils import is_dt_str
from ultimate_notion.view import View

if TYPE_CHECKING:
    from ultimate_notion.database import Database


class Property(BaseModel):
    """Represents a property of a page.

    !!! note

        We override some magic methods to allow for more natural query building in an unorthodox way.
        This is done to avoid the need for a custom query builder class and to keep the API simple.
        Be aware that for instance the comparison operator == will not return boolean values but
        instances of the corresponding condition classes.
    """

    name: str
    sort: SortDirection = Field(default=SortDirection.ASCENDING)

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: Any) -> Equals:  # type: ignore[override]
        return Equals(prop=self, value=other)

    def __ne__(self, other: Any) -> EqualsNot:  # type: ignore[override]
        return EqualsNot(prop=self, value=other)

    def __gt__(self, value: Any) -> GreaterThan:
        return GreaterThan(prop=self, value=value)

    def __lt__(self, value: Any) -> LessThan:
        return LessThan(prop=self, value=value)

    def __ge__(self, value: Any) -> GreaterThanOrEqualTo:
        return GreaterThanOrEqualTo(prop=self, value=value)

    def __le__(self, value: Any) -> LessThanOrEqualTo:
        return LessThanOrEqualTo(prop=self, value=value)

    def contains(self, value: str) -> Contains:
        return Contains(prop=self, value=value)

    def does_not_contain(self, value: str) -> ContainsNot:
        return ContainsNot(prop=self, value=value)

    def starts_with(self, value: str) -> StartsWith:
        return StartsWith(prop=self, value=value)

    def ends_with(self, value: str) -> EndsWith:
        return EndsWith(prop=self, value=value)

    def is_empty(self, value: FormulaType | None = None) -> IsEmpty:
        return IsEmpty(prop=self, value=value)

    def is_not_empty(self, value: FormulaType | None = None) -> IsNotEmpty:
        return IsNotEmpty(prop=self, value=value)

    def this_week(self) -> ThisWeek:
        return ThisWeek(prop=self, value=obj_query.DateCondition.EmptyObject())

    def past_week(self) -> PastWeek:
        return PastWeek(prop=self, value=obj_query.DateCondition.EmptyObject())

    def past_month(self) -> PastMonth:
        return PastMonth(prop=self, value=obj_query.DateCondition.EmptyObject())

    def past_year(self) -> PastYear:
        return PastYear(prop=self, value=obj_query.DateCondition.EmptyObject())

    def next_week(self) -> NextWeek:
        return NextWeek(prop=self, value=obj_query.DateCondition.EmptyObject())

    def next_month(self) -> NextMonth:
        return NextMonth(prop=self, value=obj_query.DateCondition.EmptyObject())

    def next_year(self) -> NextYear:
        return NextYear(prop=self, value=obj_query.DateCondition.EmptyObject())

    def asc(self) -> Self:
        self.sort = SortDirection.ASCENDING
        return self

    def desc(self) -> Self:
        self.sort = SortDirection.DESCENDING
        return self

    def __repr__(self) -> str:
        return f"prop('{self.name}')"

    def __str__(self) -> str:
        return repr(self)


def prop(prop_name: str, /) -> Property:
    """Create a column object."""
    return Property(name=prop_name)


class Condition(BaseModel, ABC):
    """Base class for filter query conditions."""

    def __and__(self, other: Condition) -> Condition:
        match other:
            case And(terms=terms) if isinstance(self, And):
                return And(terms=[self.terms, *terms])
            case And(terms=terms):
                return And(terms=[self, *terms])
            case _ if isinstance(self, And):
                return And(terms=[self.terms, other])
            case _:
                return And(terms=[self, other])

    def __iand__(self, other: Condition) -> Condition:
        return self & other

    def __or__(self, other: Condition) -> Condition:
        match other:
            case Or(terms=terms) if isinstance(self, Or):
                return Or(terms=[self.terms, *terms])
            case Or(terms=terms):
                return Or(terms=[self, *terms])
            case _ if isinstance(self, Or):
                return Or(terms=[self.terms, other])
            case _:
                return Or(terms=[self, other])

    def __ior__(self, other: Condition) -> Condition:
        return self | other

    @abstractmethod
    def __repr__(self) -> str: ...

    def __str__(self) -> str:
        return repr(self)

    @abstractmethod
    def create_obj_ref(self, db: Database) -> obj_query.QueryFilter: ...


class PropertyCondition(Condition, ABC):
    prop: Property
    value: Any

    def _prop_type(self, db: Database) -> schema.PropertyType:
        return db.schema[self.prop.name]


class Equals(PropertyCondition):
    _condition_kw = 'equals'

    def create_obj_ref(self, db: Database) -> obj_query.QueryFilter:
        kwargs: dict[str, Any] = {'property': self.prop.name}
        prop_type = self._prop_type(db)

        match prop_type:
            case schema.Text() | schema.Title() | schema.PhoneNumber():
                kwargs['rich_text'] = obj_query.TextCondition(**{self._condition_kw: self.value})
            case schema.Number():
                kwargs['number'] = obj_query.NumberCondition(**{self._condition_kw: self.value})
            case schema.Checkbox():
                kwargs['checkbox'] = obj_query.CheckboxCondition(**{self._condition_kw: bool(self.value)})
            case schema.Select():
                kwargs['select'] = obj_query.SelectCondition(**{self._condition_kw: str(self.value)})
            case schema.Date():
                kwargs['date'] = obj_query.DateCondition(**{self._condition_kw: self.value})
            case schema.CreatedTime():
                date_condition = obj_query.DateCondition(**{self._condition_kw: self.value})
                return obj_query.CreatedTimeFilter(created_time=date_condition)
            case schema.LastEditedTime():
                date_condition = obj_query.DateCondition(**{self._condition_kw: self.value})
                return obj_query.LastEditedTimeFilter(last_edited_time=date_condition)
            case schema.Formula():
                match self.value:
                    case str():
                        condition: type[obj_query.Condition]
                        if is_dt_str(self.value):
                            condition = obj_query.DateCondition
                            formula_type = 'date'
                        else:
                            condition = obj_query.TextCondition
                            formula_type = 'string'
                    case dt.datetime():
                        condition = obj_query.DateCondition
                        formula_type = 'date'
                    case bool():
                        condition = obj_query.CheckboxCondition
                        formula_type = 'checkbox'
                    case int() | float():
                        condition = obj_query.NumberCondition
                        formula_type = 'number'
                    case _:
                        msg = f'Invalid value type `{type(self.value)}` for {self} condition.'
                        raise ValueError(msg)

                formula_condition = condition(**{self._condition_kw: self.value})
                kwargs['formula'] = obj_query.FormulaCondition(**{formula_type: formula_condition})
            case _:
                msg = f'Invalid property type `{prop_type}` for {self} condition.'
                raise ValueError(msg)

        return obj_query.PropertyFilter(**kwargs)

    def __repr__(self) -> str:
        return f'({self.prop} == {self.value})'


class EqualsNot(Equals):
    _condition_kw = 'does_not_equal'

    def __repr__(self) -> str:
        return f'({self.prop} != {self.value})'


class Contains(PropertyCondition):
    _condition_kw = 'contains'

    def create_obj_ref(self, db: Database) -> obj_query.QueryFilter:
        kwargs: dict[str, Any] = {'property': self.prop.name}
        prop_type = self._prop_type(db)

        match prop_type:
            case schema.Text() | schema.Title() | schema.PhoneNumber():
                kwargs['rich_text'] = obj_query.TextCondition(**{self._condition_kw: self.value})
            case schema.MultiSelect():
                kwargs['multi_select'] = obj_query.MultiSelectCondition(**{self._condition_kw: str(self.value)})
            case schema.People() if isinstance(self.value, User):
                kwargs['people'] = obj_query.PeopleCondition(**{self._condition_kw: self.value.id})
            case schema.Relation() if isinstance(self.value, Page):
                kwargs['relation'] = obj_query.RelationCondition(**{self._condition_kw: self.value.id})
            case schema.Formula():
                if isinstance(self.value, str):
                    formula_condition = obj_query.TextCondition(**{self._condition_kw: self.value})
                    kwargs['formula'] = obj_query.FormulaCondition(string=formula_condition)
                else:
                    msg = f'Invalid value type `{type(self.value)}` for {self} condition.'
                    raise ValueError(msg)

            case _:
                msg = f'Invalid property type `{prop_type}` for {self} condition.'
                raise ValueError(msg)

        return obj_query.PropertyFilter(**kwargs)

    def __repr__(self) -> str:
        return f'{self.prop}.{self._condition_kw}({self.value})'


class ContainsNot(Contains):
    _condition_kw = 'does_not_contain'


class StartsWith(PropertyCondition):
    _condition_kw = 'starts_with'

    def create_obj_ref(self, db: Database) -> obj_query.QueryFilter:
        kwargs: dict[str, Any] = {'property': self.prop.name}
        prop_type = self._prop_type(db)

        match prop_type:
            case schema.Text() | schema.Title() | schema.PhoneNumber():
                kwargs['rich_text'] = obj_query.TextCondition(**{self._condition_kw: self.value})
            case schema.MultiSelect():
                kwargs['multi_select'] = obj_query.MultiSelectCondition(**{self._condition_kw: str(self.value)})
            case schema.People() if isinstance(self.value, User):
                kwargs['people'] = obj_query.PeopleCondition(**{self._condition_kw: self.value.id})
            case schema.Relation() if isinstance(self.value, Page):
                kwargs['relation'] = obj_query.RelationCondition(**{self._condition_kw: self.value.id})
            case schema.Formula():
                if isinstance(self.value, str):
                    formula_condition = obj_query.TextCondition(**{self._condition_kw: self.value})
                    kwargs['formula'] = obj_query.FormulaCondition(string=formula_condition)
                else:
                    msg = f'Invalid value type `{type(self.value)}` for {self} condition.'
                    raise ValueError(msg)

            case _:
                msg = f'Invalid property type `{prop_type}` for {self} condition.'
                raise ValueError(msg)

        return obj_query.PropertyFilter(**kwargs)

    def __repr__(self) -> str:
        return f'{self.prop}.{self._condition_kw}({self.value})'


class EndsWith(StartsWith):
    _condition_kw = 'ends_with'


class IsEmpty(PropertyCondition):
    _condition_kw = 'is_empty'

    def create_obj_ref(self, db: Database) -> obj_query.QueryFilter:
        kwargs: dict[str, Any] = {'property': self.prop.name}
        prop_type = self._prop_type(db)

        match prop_type:
            case schema.Text() | schema.Title() | schema.PhoneNumber():
                kwargs['rich_text'] = obj_query.TextCondition(**{self._condition_kw: self.value})
            case schema.Number():
                kwargs['number'] = obj_query.NumberCondition(**{self._condition_kw: self.value})
            case schema.Select():
                kwargs['select'] = obj_query.SelectCondition(**{self._condition_kw: str(self.value)})
            case schema.MultiSelect():
                kwargs['multi_select'] = obj_query.MultiSelectCondition(**{self._condition_kw: str(self.value)})
            case schema.Date():
                kwargs['date'] = obj_query.DateCondition(**{self._condition_kw: self.value})
            case schema.People():
                kwargs['people'] = obj_query.PeopleCondition(**{self._condition_kw: self.value})
            case schema.Files():
                kwargs['files'] = obj_query.FilesCondition(**{self._condition_kw: self.value})
            case schema.Relation():
                kwargs['relation'] = obj_query.RelationCondition(**{self._condition_kw: self.value})
            case schema.CreatedTime():
                date_condition = obj_query.DateCondition(**{self._condition_kw: self.value})
                return obj_query.CreatedTimeFilter(created_time=date_condition)
            case schema.LastEditedTime():
                date_condition = obj_query.DateCondition(**{self._condition_kw: self.value})
                return obj_query.LastEditedTimeFilter(last_edited_time=date_condition)
            case schema.Formula():
                value = FormulaType(self.value)
                condition: type[obj_query.Condition]

                match value:
                    case None:
                        msg = (
                            f'The property {self.prop.name} is a formula and we need its type, i.e. `number`, ',
                            '`string` or `date`, for `.is_empty()` and `.is_not_empty()` conditions to infer ',
                            'the proper API call.',
                        )
                        raise ValueError(msg)

                    case FormulaType.DATE:
                        condition = obj_query.DateCondition
                        formula_type = 'date'
                    case FormulaType.NUMBER:
                        condition = obj_query.NumberCondition
                        formula_type = 'number'
                    case FormulaType.STRING:
                        condition = obj_query.TextCondition
                        formula_type = 'string'
                    case _:
                        msg = f'Invalid value type `{type(self.value)}` for {self} condition.'
                        raise ValueError(msg)

                formula_condition = condition(**{self._condition_kw: self.value})
                kwargs['formula'] = obj_query.FormulaCondition(**{formula_type: formula_condition})
            case _:
                msg = f'Invalid property type `{prop_type}` for {self} condition.'
                raise ValueError(msg)

        return obj_query.PropertyFilter(**kwargs)

    def __repr__(self) -> str:
        return f'{self.prop}.{self._condition_kw}()'


class IsNotEmpty(IsEmpty):
    _condition_kw = 'is_not_empty'


class InEquality(PropertyCondition, ABC):
    _num_condition_kw: str
    _date_condition_kw: str

    def create_obj_ref(self, db: Database) -> obj_query.QueryFilter:
        kwargs: dict[str, Any] = {'property': self.prop.name}
        prop_type = self._prop_type(db)

        match prop_type:
            case schema.Number():
                kwargs['number'] = obj_query.NumberCondition(**{self._num_condition_kw: self.value})
            case schema.Date():
                kwargs['date'] = obj_query.DateCondition(**{self._date_condition_kw: self.value})
            case schema.Formula():
                condition: type[obj_query.Condition]
                formula_condition: obj_query.Condition

                match self.value:
                    case str() | dt.datetime():
                        condition = obj_query.DateCondition
                        formula_type = 'date'
                        formula_condition = condition(**{self._date_condition_kw: self.value})
                    case int() | float():
                        condition = obj_query.NumberCondition
                        formula_type = 'number'
                        formula_condition = condition(**{self._num_condition_kw: self.value})
                    case _:
                        msg = f'Invalid value type `{type(self.value)}` for {self} condition.'
                        raise ValueError(msg)

                kwargs['formula'] = obj_query.FormulaCondition(**{formula_type: formula_condition})
            case _:
                msg = f'Invalid property type `{prop_type}` for {self} condition.'
                raise ValueError(msg)

        return obj_query.PropertyFilter(**kwargs)

    @abstractmethod
    def __repr__(self) -> str: ...


class GreaterThan(InEquality):
    _num_condition_kw = 'greater_than'
    _date_condition_kw = 'after'

    def __repr__(self) -> str:
        return f'({self.prop} > {self.value})'


class LessThan(InEquality):
    _num_condition_kw = 'less_than'
    _date_condition_kw = 'before'

    def __repr__(self) -> str:
        return f'({self.prop} < {self.value})'


class GreaterThanOrEqualTo(InEquality):
    _num_condition_kw = 'greater_than_or_equal_to'
    _date_condition_kw = 'on_or_after'

    def __repr__(self) -> str:
        return f'({self.prop} >= {self.value})'


class LessThanOrEqualTo(InEquality):
    _num_condition_kw = 'less_than_or_equal_to'
    _date_condition_kw = 'on_or_before'

    def __repr__(self) -> str:
        return f'({self.prop} <= {self.value})'


class DateCondition(PropertyCondition, ABC):
    _condition_kw: str

    def create_obj_ref(self, db: Database) -> obj_query.QueryFilter:
        kwargs: dict[str, Any] = {'property': self.prop.name}
        prop_type = self._prop_type(db)
        match prop_type:
            case schema.Date():
                kwargs['date'] = obj_query.DateCondition(**{self._condition_kw: self.value})
            case schema.Formula():
                condition = obj_query.DateCondition(**{self._condition_kw: self.value})
                kwargs['formula'] = obj_query.FormulaCondition(date=condition)
            case _:
                msg = f'Invalid property type `{prop_type}` for {self} condition.'
                raise ValueError(msg)
        return obj_query.PropertyFilter(**kwargs)

    def __repr__(self) -> str:
        return f'{self.prop}.{self._condition_kw}()'


class PastWeek(DateCondition):
    _condition_kw = 'past_week'


class PastMonth(DateCondition):
    _condition_kw = 'past_month'


class PastYear(DateCondition):
    _condition_kw = 'past_year'


class ThisWeek(DateCondition):
    _condition_kw = 'this_week'


class NextWeek(DateCondition):
    _condition_kw = 'next_week'


class NextMonth(DateCondition):
    _condition_kw = 'next_month'


class NextYear(DateCondition):
    _condition_kw = 'next_year'


class And(Condition):
    terms: list[Condition]

    def create_obj_ref(self, db: Database) -> obj_query.QueryFilter:
        return obj_query.CompoundFilter(and_=[term.create_obj_ref(db) for term in self.terms])

    def __repr__(self) -> str:
        return f"({' & '.join(str(term) for term in self.terms)})"


class Or(Condition):
    terms: list[Condition]

    def create_obj_ref(self, db: Database) -> obj_query.QueryFilter:
        return obj_query.CompoundFilter(or_=[term.create_obj_ref(db) for term in self.terms])

    def __repr__(self) -> str:
        return f"({' | '.join(str(term) for term in self.terms)})"


class Query:
    """A query object to filter and sort pages in a database."""

    _filter: Condition | None = None
    _sorts: list[Property] | None = None

    def __init__(self, database: Database):
        self.database = database

    def execute(self) -> View:
        """Execute the query and return the resulting pages as a view."""
        session = get_active_session()
        query_obj = session.api.databases.query(self.database.obj_ref)
        if self._filter:
            query_obj.filter(self._filter.create_obj_ref(self.database))
        if self._sorts:
            query_obj.sort([obj_query.DBSort(property=prop.name, direction=prop.sort) for prop in self._sorts])
        pages = [cast(Page, session.cache.setdefault(page.id, Page.wrap_obj_ref(page))) for page in query_obj.execute()]
        return View(database=self.database, pages=pages, query=self)

    def filter(self, expr: Condition) -> Query:
        """Filter the query by the given properties.

        !!! note
            The filter is applied as an AND operation with the existing filter.
        """
        if self._filter is None:
            self._filter = expr
        else:
            self._filter &= expr
        return self

    def sort(self, *props: Property | str) -> Query:
        """Sort the query by the given properties and directions.

        !!! note
            The order of the properties is important. The first property is the primary sort,
            the second is the secondary sort, and so on. Calling this method multiple times
            will overwrite the previous sorts.
        """
        self._sorts = [prop if isinstance(prop, Property) else Property(name=prop) for prop in props]
        return self
