"""Query the database for pages."""

from __future__ import annotations

import datetime as dt
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, cast

from pydantic import BaseModel, Field
from typing_extensions import Self

from ultimate_notion import props, schema
from ultimate_notion.core import get_active_session
from ultimate_notion.errors import EmptyDBError, FilterQueryError
from ultimate_notion.obj_api import query as obj_query
from ultimate_notion.obj_api.core import raise_unset
from ultimate_notion.obj_api.enums import ArrayQuantifier, FormulaType, RollupType, SortDirection
from ultimate_notion.option import Option
from ultimate_notion.page import Page
from ultimate_notion.user import User
from ultimate_notion.view import View

if TYPE_CHECKING:
    from ultimate_notion.database import Database
    from ultimate_notion.schema import Property


_logger = logging.getLogger(__name__)


class PageProperty(BaseModel):
    """Represents a property of a page.

    !!! note

        We override some magic methods to allow for more natural query building in an unorthodox way.
        Be aware that for instance the comparison operator == will not return boolean values but
        instances of the corresponding condition classes.
    """

    name: str
    sort: SortDirection = Field(default=SortDirection.ASCENDING)

    def __hash__(self) -> int:
        return hash((self.name, self.sort))

    def __eq__(self, other: Any) -> Condition:  # type: ignore[override]
        return Equals(prop=self, value=other)

    def __ne__(self, other: Any) -> Condition:  # type: ignore[override]
        return EqualsNot(prop=self, value=other)

    def __gt__(self, value: Any) -> Condition:
        return GreaterThan(prop=self, value=value)

    def __lt__(self, value: Any) -> Condition:
        return LessThan(prop=self, value=value)

    def __ge__(self, value: Any) -> Condition:
        return GreaterThanOrEqualTo(prop=self, value=value)

    def __le__(self, value: Any) -> Condition:
        return LessThanOrEqualTo(prop=self, value=value)

    def __repr__(self) -> str:
        return f"prop('{self.name}')"

    def __str__(self) -> str:
        return repr(self)

    def contains(self, value: str | User | Page | Option) -> Condition:
        return Contains(prop=self, value=value)

    def does_not_contain(self, value: str | User | Page | Option) -> Condition:
        return ContainsNot(prop=self, value=value)

    def starts_with(self, value: str) -> Condition:
        return StartsWith(prop=self, value=value)

    def ends_with(self, value: str) -> Condition:
        return EndsWith(prop=self, value=value)

    def is_empty(self) -> Condition:
        return IsEmpty(prop=self, value=True)

    def is_not_empty(self) -> Condition:
        return IsNotEmpty(prop=self, value=True)

    def this_week(self) -> Condition:
        return ThisWeek(prop=self, value=obj_query.DateCondition.EmptyObject())

    def past_week(self) -> Condition:
        return PastWeek(prop=self, value=obj_query.DateCondition.EmptyObject())

    def past_month(self) -> Condition:
        return PastMonth(prop=self, value=obj_query.DateCondition.EmptyObject())

    def past_year(self) -> Condition:
        return PastYear(prop=self, value=obj_query.DateCondition.EmptyObject())

    def next_week(self) -> Condition:
        return NextWeek(prop=self, value=obj_query.DateCondition.EmptyObject())

    def next_month(self) -> Condition:
        return NextMonth(prop=self, value=obj_query.DateCondition.EmptyObject())

    def next_year(self) -> Condition:
        return NextYear(prop=self, value=obj_query.DateCondition.EmptyObject())

    def asc(self) -> Self:
        self.sort = SortDirection.ASCENDING
        return self

    def desc(self) -> Self:
        self.sort = SortDirection.DESCENDING
        return self

    @property
    def any(self) -> RollupArrayProperty:
        return RollupArrayProperty(name=self.name, sort=self.sort, quantifier=ArrayQuantifier.ANY)

    @property
    def none(self) -> RollupArrayProperty:
        return RollupArrayProperty(name=self.name, sort=self.sort, quantifier=ArrayQuantifier.NONE)

    @property
    def every(self) -> RollupArrayProperty:
        return RollupArrayProperty(name=self.name, sort=self.sort, quantifier=ArrayQuantifier.EVERY)


class RollupArrayProperty(PageProperty):
    """Represents a rollup array property of a page."""

    quantifier: ArrayQuantifier

    def __repr__(self) -> str:
        return f"prop('{self.name}').{self.quantifier.value}"


def prop(prop_name: str, /) -> PageProperty:
    """Create a property object."""
    return PageProperty(name=prop_name)


class Condition(BaseModel, ABC):
    """Base class for filter query conditions."""

    is_method: bool = False  # to distinguish between method and operator conditions for parenthesizing

    def __and__(self, other: Condition) -> Condition:
        # This logic reduces the number of parentheses by combining ANDs (associative rule)
        match other:
            case And(terms=terms) if isinstance(self, And):
                return And(terms=[*self.terms, *terms])
            case And(terms=terms):
                return And(terms=[self, *terms])
            case _ if isinstance(self, And):
                return And(terms=[*self.terms, other])
            case _:
                return And(terms=[self, other])

    def __iand__(self, other: Condition) -> Condition:
        return self & other

    def __or__(self, other: Condition) -> Condition:
        # This logic reduces the number of parentheses by combining ORs (associative rule)
        match other:
            case Or(terms=terms) if isinstance(self, Or):
                return Or(terms=[*self.terms, *terms])
            case Or(terms=terms):
                return Or(terms=[self, *terms])
            case _ if isinstance(self, Or):
                return Or(terms=[*self.terms, other])
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
    prop: PageProperty
    value: Any
    _probe_page: Page | None = None

    @abstractmethod
    def _create_obj_ref_kwargs(self, db: Database, prop_type: Property) -> dict[str, obj_query.Condition]:
        """Create the keyword arguments for the obj_query.PropertyFilter constructor.

        We need this as a rollup array condition works on top of a property condition.
        Thus we handle here everything except of the rollup array condition.
        """

    def _get_prop_type(self, db: Database) -> Property:
        return db.schema[self.prop.name]

    def _get_probe_page(self, db: Database) -> Page:
        """Return a page from the database to probe its properties as needed for certain conditions."""
        if self._probe_page is None:
            session = get_active_session()
            try:
                page_obj = next(session.api.databases.query(db.obj_ref).execute(page_size=1))
            except StopIteration as e:
                msg = f'The database {db} is empty.'
                raise EmptyDBError(msg) from e
            page_obj_id = raise_unset(page_obj.id)
            self._probe_page = cast(Page, session.cache.setdefault(page_obj_id, Page.wrap_obj_ref(page_obj)))

        return self._probe_page

    def _get_formula_type(self, db: Database) -> FormulaType:
        """Return the type of a formula property."""
        page = self._get_probe_page(db)
        prop: props.PropertyValue = props.PropertyValue.wrap_obj_ref(page.props._obj_prop_vals[self.prop.name])

        if not isinstance(prop, props.Formula):
            msg = f'The property {self.prop.name} is not a formula property.'
            raise FilterQueryError(msg)

        if not (prop_type := prop.value_type):
            msg = f'The property {self.prop.name} does not have a formula type set.'
            raise FilterQueryError(msg)

        return prop_type

    def _get_rollup_type(self, db: Database) -> RollupType:
        """Return the type of a rollup property."""
        page = self._get_probe_page(db)
        prop: props.PropertyValue = props.PropertyValue.wrap_obj_ref(page.props._obj_prop_vals[self.prop.name])

        if isinstance(prop, props.Rollup) and (prop_type := prop.value_type) is not None:
            return prop_type
        else:
            msg = f'The property {self.prop.name} is not a rollup property or is missing a type.'
            raise FilterQueryError(msg)

    @property
    def _value_str(self) -> str:
        match self.value:
            case str() | dt.datetime() | Option():
                return f"'{self.value}'"
            case _:
                return f'{self.value}'


class IsEmpty(PropertyCondition):
    _condition_kw = 'is_empty'
    is_method: bool = True

    def _create_obj_ref_kwargs(self, db: Database, prop_type: Property) -> dict[str, obj_query.Condition]:
        kwargs: dict[str, obj_query.Condition] = {}

        match prop_type:
            case schema.Text() | schema.Title() | schema.Phone() | schema.Email() | schema.URL():
                kwargs['rich_text'] = obj_query.TextCondition(**{self._condition_kw: self.value})
            case schema.Number():
                kwargs['number'] = obj_query.NumberCondition(**{self._condition_kw: self.value})
            case schema.Select():
                kwargs['select'] = obj_query.SelectCondition(**{self._condition_kw: str(self.value)})
            case schema.MultiSelect():
                kwargs['multi_select'] = obj_query.MultiSelectCondition(**{self._condition_kw: str(self.value)})
            case schema.Date():
                kwargs['date'] = obj_query.DateCondition(**{self._condition_kw: self.value})
            case schema.Person():
                kwargs['people'] = obj_query.PeopleCondition(**{self._condition_kw: self.value})
            case schema.Files():
                kwargs['files'] = obj_query.FilesCondition(**{self._condition_kw: self.value})
            case schema.Relation():
                kwargs['relation'] = obj_query.RelationCondition(**{self._condition_kw: self.value})
            case schema.Formula():
                condition: obj_query.Condition

                match formula_type := self._get_formula_type(db):
                    case FormulaType.STRING:
                        condition = obj_query.TextCondition(**{self._condition_kw: self.value})
                    case FormulaType.NUMBER:
                        condition = obj_query.NumberCondition(**{self._condition_kw: self.value})
                    case FormulaType.DATE:
                        condition = obj_query.DateCondition(**{self._condition_kw: self.value})
                    case _:
                        msg = f'Invalid formula type `{formula_type.value}` for condition {self}.'
                        raise FilterQueryError(msg)

                kwargs['formula'] = obj_query.FormulaCondition(**{formula_type.formula_kwarg: condition})
            case _:
                msg = f'Invalid property type `{prop_type}` for condition {self}.'
                raise FilterQueryError(msg)

        return kwargs

    def create_obj_ref(self, db: Database) -> obj_query.QueryFilter:
        prop_type = self._get_prop_type(db)

        match prop_type:
            case schema.CreatedTime():
                date_condition = obj_query.DateCondition(**{self._condition_kw: self.value})
                return obj_query.CreatedTimeFilter(created_time=date_condition)
            case schema.LastEditedTime():
                date_condition = obj_query.DateCondition(**{self._condition_kw: self.value})
                return obj_query.LastEditedTimeFilter(last_edited_time=date_condition)
            case schema.Rollup():
                condition: obj_query.Condition

                match rollup_type := self._get_rollup_type(db):
                    case RollupType.ARRAY:
                        if not isinstance(self.prop, RollupArrayProperty):
                            msg = (
                                f'The property {self.prop.name} must be a rollup array property, '
                                'use one of the properties `any`, `every` and `none`.'
                            )
                            raise FilterQueryError(msg)

                        kwargs = self._create_obj_ref_kwargs(db, prop_type.rollup_prop)
                        condition = obj_query.RollupArrayCondition(**kwargs)
                        rollup_kwarg = self.prop.quantifier.value
                    case RollupType.NUMBER:
                        condition = obj_query.NumberCondition(**{self._condition_kw: self.value})
                        rollup_kwarg = rollup_type.value
                    case RollupType.DATE:
                        condition = obj_query.DateCondition(**{self._condition_kw: self.value})
                        rollup_kwarg = rollup_type.value
                    case _:
                        msg = f'Invalid rollup type `{rollup_type}` for condition {self}.'
                        raise FilterQueryError(msg)

                kwargs = {'rollup': obj_query.RollupCondition(**{rollup_kwarg: condition})}
            case _:
                kwargs = self._create_obj_ref_kwargs(db, prop_type)

        return obj_query.PropertyFilter(property=self.prop.name, **kwargs)

    def __repr__(self) -> str:
        return f'{self.prop}.{self._condition_kw}()'


class IsNotEmpty(IsEmpty):
    _condition_kw = 'is_not_empty'
    is_method: bool = True


class Equals(PropertyCondition):
    _condition_kw = 'equals'

    def _create_obj_ref_kwargs(self, db: Database, prop_type: Property) -> dict[str, obj_query.Condition]:
        kwargs: dict[str, obj_query.Condition] = {}

        match prop_type:
            case schema.Text() | schema.Title() | schema.Phone() | schema.Email() | schema.URL():
                kwargs['rich_text'] = obj_query.TextCondition(**{self._condition_kw: self.value})
            case schema.ID():
                kwargs['unique_id'] = obj_query.IdCondition(**{self._condition_kw: self.value})
            case schema.Number():
                kwargs['number'] = obj_query.NumberCondition(**{self._condition_kw: self.value})
            case schema.Checkbox():
                kwargs['checkbox'] = obj_query.CheckboxCondition(**{self._condition_kw: bool(self.value)})
            case schema.Select():
                kwargs['select'] = obj_query.SelectCondition(**{self._condition_kw: str(self.value)})
            case schema.Date() if self._condition_kw == 'equals':  # date has no `does_not_equal` condition
                kwargs['date'] = obj_query.DateCondition(**{self._condition_kw: self.value})
            case schema.Formula():
                condition: obj_query.Condition

                match formula_type := self._get_formula_type(db):
                    case FormulaType.STRING:
                        condition = obj_query.TextCondition(**{self._condition_kw: self.value})
                    case FormulaType.NUMBER:
                        condition = obj_query.NumberCondition(**{self._condition_kw: self.value})
                    case FormulaType.DATE:
                        condition = obj_query.DateCondition(**{self._condition_kw: self.value})
                    case FormulaType.BOOLEAN:
                        condition = obj_query.CheckboxCondition(**{self._condition_kw: bool(self.value)})

                kwargs['formula'] = obj_query.FormulaCondition(**{formula_type.formula_kwarg: condition})

            case _:
                msg = f'Invalid property type `{prop_type}` for condition {self}.'
                raise FilterQueryError(msg)

        return kwargs

    def create_obj_ref(self, db: Database) -> obj_query.QueryFilter:
        prop_type = self._get_prop_type(db)

        match prop_type:
            case schema.CreatedTime():
                date_condition = obj_query.DateCondition(**{self._condition_kw: self.value})
                return obj_query.CreatedTimeFilter(created_time=date_condition)
            case schema.LastEditedTime():
                date_condition = obj_query.DateCondition(**{self._condition_kw: self.value})
                return obj_query.LastEditedTimeFilter(last_edited_time=date_condition)
            case schema.Rollup():
                condition: obj_query.Condition

                match rollup_type := self._get_rollup_type(db):
                    case RollupType.ARRAY:
                        if not isinstance(self.prop, RollupArrayProperty):
                            msg = (
                                f'The property {self.prop.name} must be a rollup array property, '
                                'use one of the properties `any`, `every` and `none`.'
                            )
                            raise FilterQueryError(msg)

                        kwargs = self._create_obj_ref_kwargs(db, prop_type.rollup_prop)
                        condition = obj_query.RollupArrayCondition(**kwargs)
                        rollup_kwarg = self.prop.quantifier.value
                    case RollupType.NUMBER:
                        condition = obj_query.NumberCondition(**{self._condition_kw: self.value})
                        rollup_kwarg = rollup_type.value
                    case RollupType.DATE:
                        condition = obj_query.DateCondition(**{self._condition_kw: self.value})
                        rollup_kwarg = rollup_type.value
                    case _:
                        msg = f'Invalid rollup type `{rollup_type}` for condition {self}.'
                        raise FilterQueryError(msg)

                kwargs = {'rollup': obj_query.RollupCondition(**{rollup_kwarg: condition})}
            case _:
                kwargs = self._create_obj_ref_kwargs(db, prop_type)

        return obj_query.PropertyFilter(property=self.prop.name, **kwargs)

    def __repr__(self) -> str:
        return f'{self.prop} == {self._value_str}'


class EqualsNot(Equals):
    _condition_kw = 'does_not_equal'

    def __repr__(self) -> str:
        return f'{self.prop} != {self._value_str}'


class InEquality(PropertyCondition, ABC):
    _num_condition_kw: str
    _date_condition_kw: str

    def _create_obj_ref_kwargs(self, db: Database, prop_type: Property) -> dict[str, obj_query.Condition]:
        kwargs: dict[str, obj_query.Condition] = {}

        match prop_type:
            case schema.Number():
                kwargs['number'] = obj_query.NumberCondition(**{self._num_condition_kw: self.value})
            case schema.ID():
                kwargs['unique_id'] = obj_query.IdCondition(**{self._num_condition_kw: self.value})
            case schema.Date():
                kwargs['date'] = obj_query.DateCondition(**{self._date_condition_kw: self.value})
            case schema.Formula():
                condition: obj_query.Condition

                match formula_type := self._get_formula_type(db):
                    case FormulaType.NUMBER:
                        condition = obj_query.NumberCondition(**{self._num_condition_kw: self.value})
                    case FormulaType.DATE:
                        condition = obj_query.DateCondition(**{self._date_condition_kw: self.value})
                    case _:
                        msg = f'Invalid formula type `{formula_type.value}` for condition {self}.'
                        raise FilterQueryError(msg)

                kwargs['formula'] = obj_query.FormulaCondition(**{formula_type.formula_kwarg: condition})
            case _:
                msg = f'Invalid property type `{prop_type}` for condition {self}.'
                raise FilterQueryError(msg)

        return kwargs

    def create_obj_ref(self, db: Database) -> obj_query.QueryFilter:
        prop_type = self._get_prop_type(db)

        match prop_type:
            case schema.CreatedTime():
                date_condition = obj_query.DateCondition(**{self._date_condition_kw: self.value})
                return obj_query.CreatedTimeFilter(created_time=date_condition)
            case schema.LastEditedTime():
                date_condition = obj_query.DateCondition(**{self._date_condition_kw: self.value})
                return obj_query.LastEditedTimeFilter(last_edited_time=date_condition)
            case schema.Rollup():
                condition: obj_query.Condition

                match rollup_type := self._get_rollup_type(db):
                    case RollupType.ARRAY:
                        if not isinstance(self.prop, RollupArrayProperty):
                            msg = (
                                f'The property {self.prop.name} must be a rollup array property, '
                                'use one of the properties `any`, `every` and `none`.'
                            )
                            raise FilterQueryError(msg)

                        kwargs = self._create_obj_ref_kwargs(db, prop_type.rollup_prop)
                        condition = obj_query.RollupArrayCondition(**kwargs)
                        rollup_kwarg = self.prop.quantifier.value
                    case RollupType.NUMBER:
                        condition = obj_query.NumberCondition(**{self._num_condition_kw: self.value})
                        rollup_kwarg = rollup_type.value
                    case RollupType.DATE:
                        condition = obj_query.DateCondition(**{self._date_condition_kw: self.value})
                        rollup_kwarg = rollup_type.value
                    case _:
                        msg = f'Invalid rollup type `{rollup_type}` for condition {self}.'
                        raise FilterQueryError(msg)

                kwargs = {'rollup': obj_query.RollupCondition(**{rollup_kwarg: condition})}
            case _:
                kwargs = self._create_obj_ref_kwargs(db, prop_type)

        return obj_query.PropertyFilter(property=self.prop.name, **kwargs)

    @abstractmethod
    def __repr__(self) -> str: ...


class GreaterThan(InEquality):
    _num_condition_kw = 'greater_than'
    _date_condition_kw = 'after'

    def __repr__(self) -> str:
        return f'{self.prop} > {self._value_str}'


class LessThan(InEquality):
    _num_condition_kw = 'less_than'
    _date_condition_kw = 'before'

    def __repr__(self) -> str:
        return f'{self.prop} < {self._value_str}'


class GreaterThanOrEqualTo(InEquality):
    _num_condition_kw = 'greater_than_or_equal_to'
    _date_condition_kw = 'on_or_after'

    def __repr__(self) -> str:
        return f'{self.prop} >= {self._value_str}'


class LessThanOrEqualTo(InEquality):
    _num_condition_kw = 'less_than_or_equal_to'
    _date_condition_kw = 'on_or_before'

    def __repr__(self) -> str:
        return f'{self.prop} <= {self._value_str}'


class Contains(PropertyCondition):
    _condition_kw = 'contains'
    is_method: bool = True

    def _create_obj_ref_kwargs(self, db: Database, prop_type: Property) -> dict[str, obj_query.Condition]:
        kwargs: dict[str, obj_query.Condition] = {}

        match prop_type:
            case schema.Text() | schema.Title() | schema.Phone() | schema.Email() | schema.URL():
                kwargs['rich_text'] = obj_query.TextCondition(**{self._condition_kw: self.value})
            case schema.MultiSelect():
                kwargs['multi_select'] = obj_query.MultiSelectCondition(**{self._condition_kw: str(self.value)})
            case schema.Person() if isinstance(self.value, User):
                kwargs['people'] = obj_query.PeopleCondition(**{self._condition_kw: self.value.id})
            case schema.Relation() if isinstance(self.value, Page):
                kwargs['relation'] = obj_query.RelationCondition(**{self._condition_kw: self.value.id})
            case schema.Formula():
                condition: obj_query.Condition

                match formula_type := self._get_formula_type(db):
                    case FormulaType.STRING:
                        condition = obj_query.TextCondition(**{self._condition_kw: self.value})
                    case _:
                        msg = f'Invalid formula type `{formula_type.value}` for condition {self}.'
                        raise FilterQueryError(msg)

                kwargs['formula'] = obj_query.FormulaCondition(**{formula_type.formula_kwarg: condition})
            case _:
                msg = f'Invalid property type `{prop_type}` for condition {self}.'
                raise FilterQueryError(msg)

        return kwargs

    def create_obj_ref(self, db: Database) -> obj_query.QueryFilter:
        prop_type = self._get_prop_type(db)

        match prop_type:
            case schema.Rollup():
                match rollup_type := self._get_rollup_type(db):
                    case RollupType.ARRAY:
                        if not isinstance(self.prop, RollupArrayProperty):
                            msg = (
                                f'The property {self.prop.name} must be a rollup array property, '
                                'use one of the properties `any`, `every` and `none`.'
                            )
                            raise FilterQueryError(msg)

                        kwargs = self._create_obj_ref_kwargs(db, prop_type.rollup_prop)
                        condition = obj_query.RollupArrayCondition(**kwargs)
                    case _:
                        msg = f'Invalid rollup type `{rollup_type}` for condition {self}.'
                        raise FilterQueryError(msg)

                kwargs = {'rollup': obj_query.RollupCondition(**{self.prop.quantifier.value: condition})}
            case _:
                kwargs = self._create_obj_ref_kwargs(db, prop_type)

        return obj_query.PropertyFilter(property=self.prop.name, **kwargs)

    def __repr__(self) -> str:
        return f'{self.prop}.{self._condition_kw}({self._value_str})'


class ContainsNot(Contains):
    _condition_kw = 'does_not_contain'
    is_method: bool = True


class StartsWith(PropertyCondition):
    _condition_kw = 'starts_with'
    is_method: bool = True

    def _create_obj_ref_kwargs(self, db: Database, prop_type: Property) -> dict[str, obj_query.Condition]:
        kwargs: dict[str, obj_query.Condition] = {}

        match prop_type:
            case schema.Text() | schema.Title() | schema.Phone() | schema.Email() | schema.URL():
                kwargs['rich_text'] = obj_query.TextCondition(**{self._condition_kw: self.value})
            case schema.Formula():
                match formula_type := self._get_formula_type(db):
                    case FormulaType.STRING:
                        condition = obj_query.TextCondition(**{self._condition_kw: self.value})
                    case _:
                        msg = f'Invalid formula type `{formula_type.value}` for condition {self}.'
                        raise FilterQueryError(msg)

                kwargs['formula'] = obj_query.FormulaCondition(**{formula_type.formula_kwarg: condition})
            case _:
                msg = f'Invalid property type `{prop_type}` for condition {self}.'
                raise FilterQueryError(msg)

        return kwargs

    def create_obj_ref(self, db: Database) -> obj_query.QueryFilter:
        prop_type = self._get_prop_type(db)

        match prop_type:
            case schema.Rollup():
                match rollup_type := self._get_rollup_type(db):
                    case RollupType.ARRAY:
                        if not isinstance(self.prop, RollupArrayProperty):
                            msg = (
                                f'The property {self.prop.name} must be a rollup array property, '
                                'use one of the properties `any`, `every` and `none`.'
                            )
                            raise FilterQueryError(msg)

                        kwargs = self._create_obj_ref_kwargs(db, prop_type.rollup_prop)
                        condition = obj_query.RollupArrayCondition(**kwargs)
                    case _:
                        msg = f'Invalid rollup type `{rollup_type}` for condition {self}.'
                        raise FilterQueryError(msg)

                kwargs = {'rollup': obj_query.RollupCondition(**{self.prop.quantifier.value: condition})}
            case _:
                kwargs = self._create_obj_ref_kwargs(db, prop_type)

        return obj_query.PropertyFilter(property=self.prop.name, **kwargs)

    def __repr__(self) -> str:
        return f'{self.prop}.{self._condition_kw}({self._value_str})'


class EndsWith(StartsWith):
    _condition_kw = 'ends_with'
    is_method: bool = True


class DateCondition(PropertyCondition, ABC):
    _condition_kw: str
    is_method: bool = True

    def _create_obj_ref_kwargs(self, db: Database, prop_type: Property) -> dict[str, obj_query.Condition]:
        kwargs: dict[str, obj_query.Condition] = {}

        match prop_type:
            case schema.Date():
                kwargs['date'] = obj_query.DateCondition(**{self._condition_kw: self.value})
            case schema.Formula():
                match formula_type := self._get_formula_type(db):
                    case FormulaType.DATE:
                        condition = obj_query.DateCondition(**{self._condition_kw: self.value})
                    case _:
                        msg = f'Invalid formula type `{formula_type.value}` for condition {self}.'
                        raise FilterQueryError(msg)

                kwargs['formula'] = obj_query.FormulaCondition(**{formula_type.formula_kwarg: condition})
            case _:
                msg = f'Invalid property type `{prop_type}` for condition {self}.'
                raise FilterQueryError(msg)

        return kwargs

    def create_obj_ref(self, db: Database) -> obj_query.QueryFilter:
        prop_type = self._get_prop_type(db)

        match prop_type:
            case schema.CreatedTime():
                date_condition = obj_query.DateCondition(**{self._condition_kw: self.value})
                return obj_query.CreatedTimeFilter(created_time=date_condition)
            case schema.LastEditedTime():
                date_condition = obj_query.DateCondition(**{self._condition_kw: self.value})
                return obj_query.LastEditedTimeFilter(last_edited_time=date_condition)
            case schema.Rollup():
                condition: obj_query.Condition

                match rollup_type := self._get_rollup_type(db):
                    case RollupType.ARRAY:
                        if not isinstance(self.prop, RollupArrayProperty):
                            msg = (
                                f'The property {self.prop.name} must be a rollup array property, '
                                'use one of the properties `any`, `every` and `none`.'
                            )
                            raise FilterQueryError(msg)

                        kwargs = self._create_obj_ref_kwargs(db, prop_type.rollup_prop)
                        condition = obj_query.RollupArrayCondition(**kwargs)
                        rollup_kwarg = self.prop.quantifier.value
                    case RollupType.DATE:
                        condition = obj_query.DateCondition(**{self._condition_kw: self.value})
                        rollup_kwarg = rollup_type.value
                    case _:
                        msg = f'Invalid rollup type `{rollup_type}` for condition {self}.'
                        raise FilterQueryError(msg)

                kwargs = {'rollup': obj_query.RollupCondition(**{rollup_kwarg: condition})}
            case _:
                kwargs = self._create_obj_ref_kwargs(db, prop_type)

        return obj_query.PropertyFilter(property=self.prop.name, **kwargs)

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
        terms = [f'({term})' if not term.is_method else str(term) for term in self.terms]
        return ' & '.join(str(term) for term in terms)


class Or(Condition):
    terms: list[Condition]

    def create_obj_ref(self, db: Database) -> obj_query.QueryFilter:
        return obj_query.CompoundFilter(or_=[term.create_obj_ref(db) for term in self.terms])

    def __repr__(self) -> str:
        terms = [f'({term})' if not term.is_method else str(term) for term in self.terms]
        return ' | '.join(str(term) for term in terms)


class Query:
    """A query object to filter and sort pages in a database."""

    database: Database
    _filter: Condition | None = None
    _sorts: list[PageProperty]

    def __init__(self, database: Database):
        self.database = database
        self._sorts = []

    def _filter_obj_ref(self) -> obj_query.QueryFilter | None:
        if self._filter is None:
            return None
        else:
            return self._filter.create_obj_ref(self.database)

    def _sorts_obj_ref(self) -> list[obj_query.DBSort]:
        return [obj_query.DBSort(property=prop.name, direction=prop.sort) for prop in self._sorts]

    def execute(self) -> View:
        """Execute the query and return the resulting pages as a view."""
        sorts = ', '.join(f'{prop}.{prop.sort}()' for prop in self._sorts) if self._sorts else ''
        _logger.info(f'Querying database `{self.database}` with filter `{self._filter}` and sorts `{sorts}`.')
        session = get_active_session()
        query_obj = session.api.databases.query(self.database.obj_ref)

        try:
            if filter_obj := self._filter_obj_ref():
                query_obj = query_obj.filter(filter_obj)
        except EmptyDBError:
            return View(database=self.database, pages=[], query=self)

        if sort_objs := self._sorts_obj_ref():
            query_obj = query_obj.sort(sort_objs)

        pages = [
            cast(Page, session.cache.setdefault(raise_unset(page.id), Page.wrap_obj_ref(page)))
            for page in query_obj.execute()
        ]
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

    def sort(self, *props: PageProperty | str) -> Query:
        """Sort the query by the given properties and directions.

        !!! note
            The order of the properties is important. The first property is the primary sort,
            the second is the secondary sort, and so on. Calling this method multiple times
            will overwrite the previous sorts.
        """
        self._sorts = [prop if isinstance(prop, PageProperty) else PageProperty(name=prop) for prop in props]
        return self

    def __repr__(self) -> str:
        sorts = ', '.join(f'{prop}.{prop.sort}()' for prop in self._sorts) if self._sorts else ''
        return f"Query(database='{self.database}', sort=({sorts}), filter={self._filter})"

    def __str__(self) -> str:
        return repr(self)
