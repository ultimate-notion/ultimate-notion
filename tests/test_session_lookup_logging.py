"""Offline regression coverage for expected lookup misses."""

from __future__ import annotations

import logging

import httpx
import pytest
from notion_client import Client

from ultimate_notion import Session
from ultimate_notion.errors import UnknownDatabaseError, UnknownDataSourceError, UnknownPageError, UnknownUserError


@pytest.fixture(autouse=True)
def notion_cleanups() -> None:
    """Skip workspace cleanup for tests using a mock transport."""


@pytest.mark.parametrize(
    ('method', 'error'),
    [
        ('get_page', UnknownPageError),
        ('get_ds', UnknownDataSourceError),
        ('get_db', UnknownDatabaseError),
        ('get_user', UnknownUserError),
    ],
)
def test_lookup_miss_logs_at_debug(method: str, error: type[Exception], caplog: pytest.LogCaptureFixture) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == '/v1/users/me':
            return httpx.Response(
                200,
                json={'object': 'user', 'id': '9ac3e083-fa26-44a7-9337-2eefbf312dec', 'type': 'bot', 'bot': {}},
            )
        return httpx.Response(404, json={'object': 'error', 'code': 'object_not_found', 'message': 'Not found'})

    logger = 'ultimate_notion.session'
    client = Client(auth='test', client=httpx.Client(transport=httpx.MockTransport(handle)))
    with (
        Session(client=client) as session,
        caplog.at_level(logging.DEBUG, logger=logger),
        pytest.raises(error) as exc,
    ):
        getattr(session, method)('9350e98a-206b-4ff1-a574-2ac5df9c4036', use_cache=False)

    miss_records = [record for record in caplog.records if record.name == logger and record.message == str(exc.value)]
    assert [record.levelno for record in miss_records] == [logging.DEBUG]
