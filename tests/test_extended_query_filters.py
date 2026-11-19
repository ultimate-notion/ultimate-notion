"""Payload tests for multi-value and relative query filters."""

from __future__ import annotations

from datetime import date
from typing import Any, cast

import pytest

import ultimate_notion as uno
from tests.conftest import TESTS_PAGE
from ultimate_notion.obj_api.blocks import DataSource as DataSourceObject
from ultimate_notion.query import Condition


@pytest.fixture(autouse=True)
def notion_cleanups() -> None:
    """Use the live test's own cleanup for its temporary data source."""


@pytest.fixture
def source() -> uno.DataSource:
    property_types = {
        'Title': 'title',
        'Priority': 'select',
        'Status': 'status',
        'Tags': 'multi_select',
        'Due': 'date',
        'Created': 'created_time',
        'Assignee': 'people',
        'Editor': 'last_edited_by',
    }
    return uno.DataSource.wrap_obj_ref(
        DataSourceObject.model_validate(
            {
                'id': '9ac3e083-fa26-44a7-9337-2eefbf312dec',
                'title': uno.text('Query test source').obj_ref,
                'properties': {
                    name: {'type': kind, 'name': name, 'id': name, kind: {}} for name, kind in property_types.items()
                },
            }
        )
    )


@pytest.mark.parametrize(
    ('condition', 'payload'),
    [
        (
            uno.prop('Priority') == ['Low', uno.Option('High')],
            {'property': 'Priority', 'select': {'equals': ['Low', 'High']}},
        ),
        (
            uno.prop('Status') != ('Done', 'Closed'),
            {'property': 'Status', 'status': {'does_not_equal': ['Done', 'Closed']}},
        ),
        (
            uno.prop('Tags').contains(['First', uno.Option('Second')]),
            {'property': 'Tags', 'multi_select': {'contains': ['First', 'Second']}},
        ),
        (
            uno.prop('Tags').does_not_contain(('First', 'Second')),
            {'property': 'Tags', 'multi_select': {'does_not_contain': ['First', 'Second']}},
        ),
        (uno.prop('Due') == 'today', {'property': 'Due', 'date': {'equals': 'today'}}),
        (uno.prop('Due') >= 'one_month_ago', {'property': 'Due', 'date': {'on_or_after': 'one_month_ago'}}),
        (uno.prop('Created') < 'tomorrow', {'timestamp': 'created_time', 'created_time': {'before': 'tomorrow'}}),
        (uno.prop('Assignee').contains('me'), {'property': 'Assignee', 'people': {'contains': 'me'}}),
        (uno.prop('Editor').does_not_contain('me'), {'property': 'Editor', 'people': {'does_not_contain': 'me'}}),
    ],
)
def test_extended_query_filter_payload(
    source: uno.DataSource, condition: Condition, payload: dict[str, object]
) -> None:
    assert condition.create_obj_ref(source).serialize_for_api() == payload


@pytest.mark.vcr(decode_compressed_response=True)
def test_query_with_multi_value_and_relative_filters() -> None:
    low = uno.Option('Low')
    high = uno.Option('High')

    class FilterTest(uno.Schema, db_title='Extended filters test'):
        title = uno.PropType.Title('Title')
        priority = uno.PropType.Select('Priority', options=[low, high])
        tags = uno.PropType.MultiSelect('Tags', options=[low, high, uno.Option('Unused')])
        due = uno.PropType.Date('Due')
        assignee = uno.PropType.Person('Assignee')

    with uno.Session() as notion:
        root = notion.search_page(TESTS_PAGE, exact=True).item()
        properties = {name: prop.obj_ref.serialize_for_api() for name, prop in FilterTest.to_dict().items()}
        title = [part.serialize_for_api() for part in uno.text('Extended filters test').obj_ref]
        # Keep fixture setup independent of validation of the database container response.
        database = cast(
            'dict[str, Any]',
            notion.client.databases.create(
                parent={'type': 'page_id', 'page_id': str(root.id)},
                title=title,
                initial_data_source={'properties': properties},
            ),
        )
        try:
            source_obj = notion.api.data_sources.retrieve(database['data_sources'][0]['id'])
            source = notion._bind_new_ds(source_obj, FilterTest)
            early = source.create_page(title='Early', priority=low, tags=[low], due=date(2000, 1, 1))
            late = source.create_page(title='Late', priority=high, tags=[high], due=date(2099, 1, 1))
            assert set(source.query.filter(uno.prop('Priority') == [low, high]).execute()) == {early, late}
            assert set(source.query.filter(uno.prop('Tags').contains(['High', 'Unused'])).execute()) == {late}
            assert set(source.query.filter(uno.prop('Due') <= 'today').execute()) == {early}
            assert source.query.filter(uno.prop('Assignee').contains('me')).execute().is_empty
        finally:
            notion.client.databases.update(database['id'], in_trash=True)
