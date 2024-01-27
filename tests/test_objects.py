from __future__ import annotations

from typing import cast

import pytest

from ultimate_notion.database import Database, Page
from ultimate_notion.schema import MultiSelect, Select, Status


@pytest.mark.vcr()
def test_status_options_groups(all_cols_db: Database):
    status_prop_type = cast(Status, all_cols_db.schema.get_col('Status').type)
    all_options = ['Not started', 'In progress', 'Done']
    assert [option.name for option in status_prop_type.options] == all_options

    all_groups = ['To-do', 'In progress', 'Complete']
    assert [group.name for group in status_prop_type.groups] == all_groups

    completed_options = status_prop_type.groups[2].options
    assert [option.name for option in completed_options] == ['Done']


@pytest.mark.vcr()
def test_select_options(all_cols_db: Database):
    select_prop_type = cast(Select, all_cols_db.schema.get_col('Select').type)
    all_options = ['Option1', 'Option2']
    assert [option.name for _, option in select_prop_type.options.items()] == all_options


@pytest.mark.vcr()
def test_multi_select_options(all_cols_db: Database):
    multi_select_prop_type = cast(MultiSelect, all_cols_db.schema.get_col('Multi-Select').type)
    all_options = ['MultiOption1', 'MultiOption2']
    assert [option.name for _, option in multi_select_prop_type.options.items()] == all_options


@pytest.mark.vcr()
def test_rich_text_md(md_page: Page):
    pass
    # from IPython import embed

    # embed()
