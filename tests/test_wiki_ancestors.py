from __future__ import annotations

from uuid import uuid4

import httpx
import notion_client
import pytest

from ultimate_notion.blocks import ChildPage
from ultimate_notion.session import Session


@pytest.fixture(autouse=True)
def notion_cleanups() -> None:
    """Disable workspace cleanup for the mock API test."""


def test_wiki_child_block_parent_and_ancestors() -> None:
    wiki_id, child_id = str(uuid4()), str(uuid4())
    responses = {
        f'/v1/databases/{wiki_id}': {
            'object': 'database',
            'id': wiki_id,
            'parent': {'type': 'workspace', 'workspace': True},
            'title': [],
            'database_type': 'wiki',
            'show_data_source_title': True,
        },
        f'/v1/blocks/{child_id}': {
            'object': 'block',
            'id': child_id,
            'parent': {'type': 'database_id', 'database_id': wiki_id},
            'type': 'child_page',
            'child_page': {'title': 'Wiki child'},
        },
    }

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.method == 'GET'
        return httpx.Response(200, json=responses[request.url.path])

    client = notion_client.Client(auth='test', client=httpx.Client(transport=httpx.MockTransport(handle)))
    with Session(client=client) as session:
        child = session.get_block(child_id)
        assert isinstance(child, ChildPage)
        wiki = child.parent
        assert wiki is session.get_db(wiki_id)
        assert child.ancestors == (wiki,)
