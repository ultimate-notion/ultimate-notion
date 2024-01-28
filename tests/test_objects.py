from __future__ import annotations

from typing import cast

import pytest

from ultimate_notion.blocks import TextBlock
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
    """These markdowns were tested with https://stackedit.io/app#"""
    correct_mds = [
        'here is something **very** *simpel* and <u>underlined</u> as well as `code`',
        '**here is a sentence that was bolded *then* typed.**',
        'here is a test sentence with ~~many **different *styles*.**~~',
        'here is another test with ~~many *different **styles**.*~~',
        'here is one more with a *strange **style*** **combination**',
        'here is one with an inline **~~equa-*tion*~~ *$E=mc^2$ and*** no block equation',
        (
            'and here is one with ~~***person** mention [@Florian Wilhelm]()*~~ and **page mention '
            '↗[Markdown Test](https://www.notion.so/0c8ea7f1c7ca4abb8890085c0fac383b)** '
        ),
        'here is one **stretching over *many\n~~many~~*\n~~lines~~**',
        # ToDo: This is not 100% right as code blocks with line breaks are not supported in Markdown.
        # Thus '\n' in the last code block will be ignored and the code will be in one line.
        # To Fix this we would have to break rich_texts into multiple code blocks.
        'This is code, e.g. **`python` code\nnow stretching `over\nmany lines`**',
    ]
    for idx, block in enumerate(md_page.content):
        assert isinstance(block, TextBlock)
        our_md = block.rich_text.to_markdown()
        assert our_md == correct_mds[idx]
