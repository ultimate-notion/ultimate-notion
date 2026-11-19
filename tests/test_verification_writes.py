"""Tests for creating and updating wiki page verification values."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import pytest
from notion_client import Client
from notion_client.helpers import iterate_paginated_api

import ultimate_notion as uno
from tests.conftest import TESTS_PAGE, WIKI_DB
from ultimate_notion.obj_api.blocks import DataSource as DataSourceObject
from ultimate_notion.obj_api.objects import PageRef
from ultimate_notion.obj_api.props import Verification as VerificationObject

SOURCE_ID = '9ac3e083-fa26-44a7-9337-2eefbf312dec'
PAGE_ID = '9350e98a-206b-4ff1-a574-2ac5df9c4036'
START = datetime(2026, 11, 19, 9, tzinfo=UTC)
END = datetime(2026, 12, 19, 9, tzinfo=UTC)


@pytest.fixture(autouse=True)
def notion_cleanups() -> None:
    """Use simulated wiki pages."""


def test_verification_create_and_update() -> None:
    requests: list[tuple[str, dict[str, object]]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append((request.method, body))
        return httpx.Response(
            200,
            json={
                'id': PAGE_ID,
                'parent': {'type': 'data_source_id', 'data_source_id': SOURCE_ID},
                'properties': {'Verification': body['properties']['Verification']},
            },
        )

    client = Client(auth='test', client=httpx.Client(transport=httpx.MockTransport(handle)))
    with uno.Session(client=client) as notion:
        source = uno.DataSource.wrap_obj_ref(
            DataSourceObject.model_validate(
                {
                    'id': SOURCE_ID,
                    'title': uno.text('Wiki').obj_ref,
                    'properties': {
                        'Title': {'type': 'title', 'name': 'Title', 'id': 'title'},
                        'Verification': {'type': 'verification', 'name': 'Verification', 'id': 'verification'},
                    },
                }
            )
        )
        notion._cache_add(source)
        page = source.create_page(
            title='Temporary page', verification=uno.Verification('verified', start=START, end=END)
        )
        assert page.props['Verification'].state is uno.VState.VERIFIED
        assert page.props['Verification'].date == START
        assert page.props['Verification'].expires_at == END
        page.props['Verification'] = 'unverified'
        assert page.props['Verification'].state is uno.VState.UNVERIFIED

    assert [method for method, _ in requests] == ['POST', 'PATCH']
    assert [body['properties'] for _, body in requests][1] == {
        'Verification': {'type': 'verification', 'verification': {'state': 'unverified'}}
    }
    assert requests[0][1]['properties'] == {
        'Title': uno.props.Title('Temporary page').obj_ref.serialize_for_api(),
        'Verification': {
            'type': 'verification',
            'verification': {
                'state': 'verified',
                'date': {'start': '2026-11-19T09:00:00Z', 'end': '2026-12-19T09:00:00Z'},
            },
        },
    }


def test_read_verification_states_and_omit_verifier() -> None:
    legacy = uno.Verification.wrap_obj_ref(
        VerificationObject.model_validate({'verification': {'state': 'verified', 'date': '2026-11-19T09:00:00Z'}})
    )
    assert legacy.date == START
    assert legacy.expires_at is None

    absent = uno.Verification.wrap_obj_ref(VerificationObject.model_validate({'verification': None}))
    assert absent.state is uno.VState.UNVERIFIED
    assert absent.date is None

    response = VerificationObject.model_validate(
        {'verification': {'state': 'verified', 'verified_by': {'object': 'user', 'id': PAGE_ID}}}
    )
    assert response.serialize_for_api() == {'type': 'verification', 'verification': {'state': 'verified'}}

    expired = uno.Verification.wrap_obj_ref(VerificationObject.model_validate({'verification': {'state': 'expired'}}))
    assert expired.state is uno.VState.EXPIRED
    with pytest.raises(ValueError, match='assigns the expired'):
        expired.obj_ref.serialize_for_api()


@pytest.mark.vcr(decode_compressed_response=True)
def test_wiki_verification_round_trip() -> None:
    with uno.Session() as notion:
        root = notion.search_page(TESTS_PAGE, exact=True).item()
        # Select the wiki before parsing schemas from unrelated search results.
        sources = iterate_paginated_api(
            notion.client.search, query=WIKI_DB, filter={'property': 'object', 'value': 'data_source'}
        )
        wiki_obj = DataSourceObject.model_validate(
            next(source for source in sources if ''.join(part['plain_text'] for part in source['title']) == WIKI_DB)
        )
        wiki = notion._cache_add(uno.DataSource.wrap_obj_ref(wiki_obj))
        parent = wiki.obj_ref.database_parent
        assert isinstance(parent, PageRef) and parent.page_id == root.id
        title_attr = wiki.schema.get_title_prop().attr_name
        page = wiki.create_page(**{title_attr: 'Verification round trip'}, verification=uno.Verification('verified'))
        try:
            assert page.reload().props['Verification'].state is uno.VState.VERIFIED
            page.props['Verification'] = 'unverified'
            assert page.reload().props['Verification'].state is uno.VState.UNVERIFIED
        finally:
            page.delete()
