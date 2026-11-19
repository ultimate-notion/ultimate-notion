"""Tests for listing and applying Notion page templates."""

from __future__ import annotations

import json
from uuid import UUID

import httpx
import pytest
from notion_client import Client
from notion_client.helpers import iterate_paginated_api

from tests.conftest import CONTACTS_DB
from ultimate_notion import DataSource, Page, PageTemplate, Session
from ultimate_notion.obj_api.blocks import DataSource as DataSourceObject
from ultimate_notion.obj_api.blocks import Page as PageObject

DS_ID = '9ac3e083-fa26-44a7-9337-2eefbf312dec'
PAGE_ID = '9350e98a-206b-4ff1-a574-2ac5df9c4036'
TEMPLATE_ID = 'fc9baea0-d607-4db4-9a6d-3d3013db96af'


@pytest.fixture(autouse=True)
def notion_cleanups() -> None:
    """Skip workspace cleanup for mock requests and the read-only live test."""


def test_list_and_apply_templates() -> None:
    cursor = 'templates:next/+'
    requests: list[httpx.Request] = []
    parent = {'type': 'page_id', 'page_id': PAGE_ID}
    response = {'object': 'page', 'id': PAGE_ID, 'parent': {'type': 'workspace', 'workspace': True}}

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == 'GET':
            is_first = 'start_cursor' not in request.url.params
            templates = [{'id': TEMPLATE_ID, 'name': 'Example', 'is_default': True}] if not is_first else []
            return httpx.Response(
                200,
                json={'templates': templates, 'has_more': is_first, 'next_cursor': cursor if is_first else None},
            )
        return httpx.Response(200, json=response)

    client = Client(auth='test', client=httpx.Client(transport=httpx.MockTransport(handle)))
    with Session(client=client) as notion:
        source = DataSource.wrap_obj_ref(DataSourceObject.model_validate({'id': DS_ID, 'title': []}))
        (template,) = source.list_templates()
        assert template == PageTemplate(id=UUID(TEMPLATE_ID), name='Example', is_default=True)
        page = notion.create_page(source, template=template)
        assert page.apply_template('default', erase_content=True) is page
        root = Page.wrap_obj_ref(PageObject.model_validate(response))
        notion.api.pages.create(root.obj_ref)

    assert [request.url.path for request in requests[:2]] == [f'/v1/data_sources/{DS_ID}/templates'] * 2
    assert [dict(request.url.params) for request in requests[:2]] == [{}, {'start_cursor': cursor}]
    assert [(request.method, request.url.path) for request in requests[2:]] == [
        ('POST', '/v1/pages'),
        ('PATCH', f'/v1/pages/{UUID(PAGE_ID).hex}'),
        ('POST', '/v1/pages'),
    ]
    assert [json.loads(request.content) for request in requests[2:]] == [
        {
            'parent': {'type': 'data_source_id', 'data_source_id': DS_ID},
            'properties': {},
            'template': {'type': 'template_id', 'template_id': TEMPLATE_ID},
        },
        {'template': {'type': 'default'}, 'erase_content': True},
        {'parent': parent, 'properties': {}},
    ]


@pytest.mark.vcr(decode_compressed_response=True)
def test_list_workspace_data_source_templates() -> None:
    with Session() as notion:
        # Discover the ID without coupling this test to the source's property definitions.
        sources = iterate_paginated_api(
            notion.client.search, query=CONTACTS_DB, filter={'property': 'object', 'value': 'data_source'}
        )
        source_id = next(
            entry['id'] for entry in sources if ''.join(part['plain_text'] for part in entry['title']) == CONTACTS_DB
        )
        source = DataSource.wrap_obj_ref(DataSourceObject.model_validate({'id': source_id}))
        assert all(isinstance(template, PageTemplate) for template in source.list_templates())
