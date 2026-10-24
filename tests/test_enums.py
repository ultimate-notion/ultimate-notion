import json
from enum import StrEnum

import pytest

from ultimate_notion.adapters.google.tasks.client import Status
from ultimate_notion.adapters.sync import ConflictMode
from ultimate_notion.cli import LogLevel
from ultimate_notion.obj_api.enums import Color, FormulaType


@pytest.mark.parametrize(
    ('member', 'expected'),
    [
        (Color.RED, 'red'),
        (FormulaType.BOOLEAN, 'boolean'),
        (ConflictMode.NEWER, 'newer'),
        (Status.NEEDS_ACTION, 'needsAction'),
        (LogLevel.WARNING, 'warning'),
    ],
)
def test_enum_string_representation(member: StrEnum, expected: str) -> None:
    assert str(member) == expected
    assert f'{member}' == expected
    assert f'{member:>20}' == expected.rjust(20)
    assert json.loads(json.dumps(member)) == expected


def test_formula_type_query_keyword() -> None:
    assert FormulaType.BOOLEAN.formula_kwarg == 'checkbox'
