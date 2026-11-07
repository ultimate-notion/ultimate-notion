from __future__ import annotations

from unittest.mock import Mock

import pytest

from ultimate_notion.errors import FilterQueryError
from ultimate_notion.obj_api import props as obj_props
from ultimate_notion.obj_api.enums import AggFunc, FormulaType, RollupType
from ultimate_notion.props import Formula, Rollup
from ultimate_notion.query import IsEmpty, PageProperty, PropertyCondition


@pytest.fixture(autouse=True)
def notion_cleanups() -> None:
    """Disable live cleanup for property-model tests."""


def test_number() -> None:
    obj = obj_props.Number.build(42)
    assert obj.number == 42
    assert isinstance(obj.number, int)

    obj = obj_props.Number.build(42.0)
    assert obj.number == 42.0
    assert isinstance(obj.number, float)


@pytest.mark.parametrize('property_item', [False, True])
def test_unsupported_formula(*, property_item: bool) -> None:
    payload = {'id': 'formula', 'type': 'formula', 'formula': {'type': 'unsupported', 'unsupported': {}}}
    obj: obj_props.Formula
    if property_item:
        payload['object'] = 'property_item'
        obj = obj_props.FormulaPropertyItem.model_validate(payload)
    else:
        obj = obj_props.Formula.model_validate(payload)
    formula = Formula.wrap_obj_ref(obj_props.Formula.build(obj.formula))

    assert formula.value is None
    assert formula.value_type is FormulaType.UNSUPPORTED
    assert obj.serialize_for_api()['formula'] == payload['formula']


@pytest.mark.parametrize('property_item', [False, True])
def test_unsupported_rollup(*, property_item: bool) -> None:
    payload = {
        'id': 'rollup',
        'type': 'rollup',
        'rollup': {'type': 'unsupported', 'unsupported': {}, 'function': 'sum'},
    }
    obj: obj_props.Rollup
    if property_item:
        payload['object'] = 'property_item'
        obj = obj_props.RollupPropertyItem.model_validate(payload)
    else:
        obj = obj_props.Rollup.model_validate(payload)
    rollup = Rollup.wrap_obj_ref(obj_props.Rollup.build(obj.rollup))

    assert rollup.value is None
    assert rollup.value_type is RollupType.UNSUPPORTED
    assert obj.rollup is not None and obj.rollup.function is AggFunc.SUM
    assert obj.serialize_for_api()['rollup'] == payload['rollup']


def test_unsupported_formula_cannot_supply_filter_type(monkeypatch: pytest.MonkeyPatch) -> None:
    obj = obj_props.Formula.model_validate({'formula': {'type': 'unsupported', 'unsupported': {}}})
    page = Mock()
    page.props._obj_prop_vals = {'Formula': obj}
    monkeypatch.setattr(PropertyCondition, '_get_probe_page', lambda self, ds: page)
    condition = IsEmpty(prop=PageProperty(name='Formula'), value=True)

    with pytest.raises(FilterQueryError, match='filter type is unavailable'):
        condition._get_formula_type(Mock())
