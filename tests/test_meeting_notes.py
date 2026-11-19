"""Tests for reading and querying AI meeting note blocks."""

from __future__ import annotations

import json
from uuid import UUID

import httpx
import pytest
from notion_client import Client

from ultimate_notion import MeetingNotes, Session

NOTE_ID = '9ac3e083-fa26-44a7-9337-2eefbf312dec'
TRANSCRIPT_ID = '9350e98a-206b-4ff1-a574-2ac5df9c4036'


@pytest.fixture(autouse=True)
def notion_cleanups() -> None:
    """Skip workspace cleanup for simulated meeting notes."""


def test_query_and_retrieve_meeting_notes() -> None:
    # The test workspace returns HTTP 400 for this endpoint because its plan
    # does not include AI Meeting Notes. Recording a successful VCR cassette
    # requires a Business or Enterprise workspace with AI Meeting Notes enabled
    # and a meeting note shared with the test integration. Mock the HTTP
    # responses here so the test can exercise the SDK request and parsing offline.
    requests: list[httpx.Request] = []
    note = {
        'object': 'block',
        'id': NOTE_ID,
        'type': 'meeting_notes',
        'meeting_notes': {
            'is_full_page': False,
            'status': 'notes_ready',
            'title': [{'type': 'text', 'text': {'content': 'Weekly sync'}, 'plain_text': 'Weekly sync'}],
            'children': {'transcript_block_id': TRANSCRIPT_ID},
            'recording': {'start_time': '2026-03-11T10:00:00Z'},
        },
    }

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == 'POST':
            return httpx.Response(200, json={'results': [note], 'has_more': True})
        return httpx.Response(200, json=note)

    filter_by = {
        'operator': 'and',
        'filters': [
            {
                'property': 'title',
                'filter': {'operator': 'string_contains', 'value': {'type': 'exact', 'value': 'Weekly'}},
            }
        ],
    }
    sort = [{'property': 'created_time', 'direction': 'descending'}]
    client = Client(auth='test', client=httpx.Client(transport=httpx.MockTransport(handle)))
    with Session(client=client) as notion:
        result = notion.query_meeting_notes(filter_by=filter_by, sort=sort, limit=1)
        (selected,) = result.results
        assert result.has_more
        assert selected.id == UUID(NOTE_ID)
        assert selected.to_markdown() == 'Weekly sync\n'
        assert selected.metadata.children is not None
        assert selected.metadata.children.transcript_block_id == UUID(TRANSCRIPT_ID)
        assert selected.metadata.recording is not None and selected.metadata.recording.start_time is not None
        assert selected.metadata.recording.start_time.hour == 10

        fetched = notion.get_block(NOTE_ID)
        assert isinstance(fetched, MeetingNotes)
        assert fetched.metadata == selected.metadata

    assert [(request.method, request.url.path) for request in requests] == [
        ('POST', '/v1/blocks/meeting_notes/query'),
        ('GET', f'/v1/blocks/{NOTE_ID}'),
    ]
    assert json.loads(requests[0].content) == {'filter': filter_by, 'sort': sort, 'limit': 1}
