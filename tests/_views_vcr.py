"""Redaction for live view tests that discover their own test root."""

from __future__ import annotations

import json
from typing import Any

from tests.conftest import TESTS_PAGE, _normalize_ids_in_body, _object_title, normalize_response


def normalize_test_root_response(response: dict[str, Any]) -> dict[str, Any]:
    """Keep only the test root in a cassette's page search and normalize shared IDs."""
    response = normalize_response(response)
    storage, key = (response, 'content') if 'content' in response else (response['body'], 'string')
    raw = storage[key]
    text = raw.decode('utf-8') if isinstance(raw, bytes) else raw
    if not text:
        return response

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return response
    if payload.get('type') in {'page_or_data_source', 'page_or_database'}:
        payload['results'] = [result for result in payload['results'] if _object_title(result) in {TESTS_PAGE, 'Tests'}]
        text = json.dumps(payload)
    normalized = _normalize_ids_in_body(text)
    storage[key] = normalized.encode('utf-8') if isinstance(raw, bytes) else normalized
    response['headers'] = {
        name: value for name, value in response['headers'].items() if name.lower() != 'content-length'
    }
    return response
