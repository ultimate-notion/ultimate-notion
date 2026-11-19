"""Tests for creating and updating Status properties."""

import json

import httpx
import pytest
from notion_client import Client

import ultimate_notion as uno
from tests._views_vcr import normalize_test_root_response
from tests.conftest import TESTS_PAGE
from ultimate_notion.obj_api.blocks import Page as PageObject
from ultimate_notion.obj_api.props import Title
from ultimate_notion.rich_text import Text

PAGE_ID = '21e91325-4fb6-4d6b-8cdb-e556333affd8'
DATABASE_ID = 'df2dfbb0-f527-4136-b31a-c0d50bef1179'
SOURCE_ID = '991b892a-dd14-48a6-b93e-722bc5659a22'


@pytest.fixture(autouse=True)
def notion_cleanups() -> None:
    """Let the live test clean up its own temporary page."""


def test_create_and_update_status_schema() -> None:
    class Tasks(uno.Schema):
        title = uno.PropType.Title('Task')
        default_status = uno.PropType.Status('Default status')
        progress = uno.PropType.Status('Progress', in_progress=[uno.Option('Review')])

    default_options = [{'id': 'default', 'name': 'Not started', 'color': 'default'}]
    test_options = [{'id': 'review', 'name': 'Review', 'color': 'default'}]
    status_groups = [
        {'id': 'todo', 'name': 'To-do', 'color': 'gray', 'option_ids': []},
        {'id': 'active', 'name': 'In progress', 'color': 'blue', 'option_ids': ['review']},
        {'id': 'done', 'name': 'Complete', 'color': 'green', 'option_ids': []},
    ]
    properties = {
        'Task': {'id': 'title', 'type': 'title', 'name': 'Task', 'title': {}},
        'Default status': {
            'id': 'default-status',
            'type': 'status',
            'name': 'Default status',
            'status': {'options': default_options, 'groups': [], 'default_option': 'Not started'},
        },
        'Progress': {
            'id': 'progress',
            'type': 'status',
            'name': 'Progress',
            'status': {'options': test_options, 'groups': status_groups, 'default_option': 'Review'},
        },
    }
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == 'POST':
            return httpx.Response(
                200,
                json={'object': 'database', 'id': DATABASE_ID, 'data_sources': [{'id': SOURCE_ID, 'name': 'Tasks'}]},
            )
        if request.method == 'PATCH':
            test_options.append({'id': 'shipped', 'name': 'Shipped', 'color': 'green'})
            status_groups[2]['option_ids'] = ['review', 'shipped']
            status_groups[1]['option_ids'] = []
        return httpx.Response(
            200,
            json={
                'object': 'data_source',
                'id': SOURCE_ID,
                'title': [],
                'parent': {'type': 'database_id', 'database_id': DATABASE_ID},
                'properties': properties,
            },
        )

    client = Client(auth='test', client=httpx.Client(transport=httpx.MockTransport(handle)))
    with uno.Session(client=client) as notion:
        parent = uno.Page.wrap_obj_ref(
            PageObject.model_validate(
                {
                    'object': 'page',
                    'id': PAGE_ID,
                    'parent': {'type': 'workspace', 'workspace': True},
                    'properties': {'title': Title(id='title', title=Text('Tests').obj_ref)},
                }
            )
        )
        notion.create_ds(parent, schema=Tasks, title='Tasks')
        default_status = Tasks.default_status
        progress = Tasks.progress
        assert isinstance(default_status, uno.PropType.Status)
        assert isinstance(progress, uno.PropType.Status)
        assert [option.name for option in default_status.options] == ['Not started']
        assert [option.name for option in progress.groups[1].options] == ['Review']
        progress.set_options(
            to_do=[], in_progress=[], complete=[progress.options[0], uno.Option('Shipped', color='green')]
        )
        assert [option.name for option in progress.groups[2].options] == ['Review', 'Shipped']

    assert [(req.method, req.url.path) for req in requests] == [
        ('POST', '/v1/databases'),
        ('GET', f'/v1/data_sources/{SOURCE_ID}'),
        ('PATCH', f'/v1/data_sources/{SOURCE_ID}'),
    ]
    create = json.loads(requests[0].content)['initial_data_source']['properties']
    assert create['Default status']['status'] == {}
    assert create['Progress']['status'] == {'options': [{'name': 'Review', 'group': 'In progress'}]}
    update = json.loads(requests[2].content)['properties']
    assert update['Progress']['status'] == {
        'options': [
            {'id': 'review', 'name': 'Review', 'color': 'default', 'group': 'Complete'},
            {'name': 'Shipped', 'color': 'green', 'group': 'Complete'},
        ]
    }


@pytest.mark.vcr(before_record_response=normalize_test_root_response, decode_compressed_response=True)
def test_status_schema_round_trip() -> None:
    class Tasks(uno.Schema):
        task = uno.PropType.Title('Task')
        default_status = uno.PropType.Status('Default status')
        progress = uno.PropType.Status(
            'Progress',
            to_do=[uno.Option('Backlog', color='gray')],
            in_progress=[uno.Option('Review', color='blue')],
            complete=[uno.Option('Done', color='green')],
        )

    with uno.Session() as notion:
        root = notion.search_page(TESTS_PAGE, exact=True).item()
        parent = notion.create_page(root, title='Status schema test')
        try:
            source = notion.create_ds(parent, schema=Tasks, title='Status schema rows')
            default_status = source.schema['Default status']
            progress = source.schema['Progress']
            assert isinstance(default_status, uno.PropType.Status)
            assert isinstance(progress, uno.PropType.Status)
            assert default_status.options
            groups = {group.name: group.options for group in progress.groups}
            assert [option.name for option in groups['In progress']] == ['Review']
            progress.set_options(
                to_do=groups['To-do'], in_progress=[], complete=[*groups['In progress'], *groups['Complete']]
            )
            source.reload()
            updated = source.schema['Progress']
            assert isinstance(updated, uno.PropType.Status)
            by_name = {group.name: {option.name for option in group.options} for group in updated.groups}
            assert by_name['Complete'] == {'Review', 'Done'}
        finally:
            parent.delete()
