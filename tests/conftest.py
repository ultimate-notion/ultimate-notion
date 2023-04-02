"""Fixtures for Ultimate-Notion unit tests.

Some fixtures are considered "connected" since they interact directly with the
Notion API.  In general, tests using these fixtures should be marked with `vcr`
to improve performance and ensure reproducibility.

Required environment variables for "connected" fixtures:
  - `NOTION_AUTH_TOKEN`: the integration token used for testing.
  - `NOTION_TEST_AREA`: a page ID that can be used for testing
"""

import os

import pytest

import ultimate_notion
from ultimate_notion.session import ENV_NOTION_AUTH_TOKEN


@pytest.fixture(scope="module")
def vcr_config():
    """Configure pytest-vcr."""

    def remove_headers(response):
        response["headers"] = {}
        return response

    return {
        "filter_headers": [
            ("authorization", "secret..."),
            ("user-agent", None),
        ],
        "before_record_response": remove_headers,
    }


@pytest.fixture
def notion():
    """Return the `PageRef` used for live testing.

    This fixture depends on the `NOTION_AUTH_TOKEN` environment variable.  If it is not
    present, this fixture will skip the current test.
    """
    if os.getenv(ENV_NOTION_AUTH_TOKEN) is None:
        raise RuntimeError(f"{ENV_NOTION_AUTH_TOKEN} not defined! Use `export {ENV_NOTION_AUTH_TOKEN}=secret_...`")

    with ultimate_notion.Session() as notion:
        yield notion


@pytest.fixture
def database(notion):
    """Return a test database"""
    return notion.search_db("Contacts").item()


@pytest.fixture
def view(database):
    """Return a test view"""
    return database.view()