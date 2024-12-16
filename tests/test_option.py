from __future__ import annotations

from typing import cast

import pytest

import ultimate_notion as uno
from ultimate_notion.schema import MultiSelect, Select, Status


@pytest.mark.vcr()
def test_status_options_groups(all_props_db: uno.Database) -> None:
    status_prop_type = cast(Status, all_props_db.schema.get_prop('Status').type)
    all_options = ['Not started', 'In progress', 'Done']
    assert [option.name for option in status_prop_type.options] == all_options

    all_groups = ['To-do', 'In progress', 'Complete']
    assert [group.name for group in status_prop_type.groups] == all_groups

    completed_options = status_prop_type.groups[2].options
    assert [option.name for option in completed_options] == ['Done']


@pytest.mark.vcr()
def test_select_options(all_props_db: uno.Database) -> None:
    select_prop_type = cast(Select, all_props_db.schema.get_prop('Select').type)
    all_options = ['Option1', 'Option2']
    assert [option.name for _, option in select_prop_type.options.items()] == all_options


@pytest.mark.vcr()
def test_multi_select_options(all_props_db: uno.Database) -> None:
    multi_select_prop_type = cast(MultiSelect, all_props_db.schema.get_prop('Multi-Select').type)
    all_options = ['MultiOption1', 'MultiOption2']
    assert [option.name for _, option in multi_select_prop_type.options.items()] == all_options
