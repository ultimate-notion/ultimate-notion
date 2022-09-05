"""Fixtures for Ultimate-Notion unit tests.

Some fixtures are considered "connected" since they interact directly with the
Notion API.  In general, tests using these fixtures should be marked with `vcr`
to improve performance and ensure reproducibility.

Required environment variables for "connected" fixtures:
  - `NOTION_AUTH_TOKEN`: the integration token used for testing.
  - `NOTION_TEST_AREA`: a page ID that can be used for testing
"""

import os
import time

import pytest

import ultimate_notion
from ultimate_notion.core import records, schema
from ultimate_notion.core.orm import Property, connected_page
from ultimate_notion.session import ENV_NOTION_AUTH_TOKEN

from .utils import mktitle, store_retvals

SLEEP_SECS_AFTER_DB_CREATE = 1


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
        pytest.skip(f"missing environment variable {ENV_NOTION_AUTH_TOKEN}")

    with ultimate_notion.NotionSession() as notion:
        yield notion


@pytest.fixture
def test_area():
    """Return the `PageRef` used for live testing.

    This fixture depends on the `NOTION_TEST_AREA` environment variable.  If it is not
    present, this fixture will skip the current test.
    """

    parent_id = os.getenv("NOTION_TEST_AREA", None)

    if parent_id is None:
        pytest.skip("missing NOTION_TEST_AREA")

    return records.PageRef(page_id=parent_id)


@pytest.fixture
def blank_page(notion, test_area):
    """Return a temporary (empty) page for testing.

    This page will be deleted during teardown.
    """

    page = notion.pages.create(
        parent=test_area,
        title=mktitle(),
    )

    assert page.id is not None
    assert page.parent == test_area

    yield page

    notion.pages.delete(page)


@pytest.fixture
def blank_db(notion, test_area):
    """Return a temporary (empty) database for testing.

    This database will be deleted during teardown.
    """

    db = notion.databases.create(
        parent=test_area,
        title=mktitle(),
        schema={
            "Name": schema.Title(),
        },
    )

    yield db

    notion.databases.delete(db)


@pytest.fixture
def create_blank_db(notion, test_area):
    """Return a function to temporary create an (empty) database for testing.

    This database will be deleted during teardown.
    """

    @store_retvals
    def nested_func(db_name):
        db = notion.databases.create(
            parent=test_area,
            title=db_name,
            schema={
                "Name": schema.Title(),
            },
        )
        # ToDo: Why is this needed?
        time.sleep(SLEEP_SECS_AFTER_DB_CREATE)
        return db

    yield nested_func

    # clean up by deleting the db of each prior call
    for db in nested_func.retvals:
        notion.databases.delete(db)


@pytest.fixture
def local_model():
    """Return an un-bound ORM model."""

    CustomPage = connected_page()

    class _LocalType(CustomPage):
        __database__ = None

        Name = Property("Name", schema.Title())
        Index = Property("Index", schema.Number())
        Notes = Property("Notes", schema.RichText())
        Complete = Property("Complete", schema.Checkbox())
        DueDate = Property("DueDate", schema.Date())
        Tags = Property("Tags", schema.MultiSelect())

    yield _LocalType


@pytest.fixture
def simple_db(notion, test_area):
    """Return a temporary (empty) database for testing.

    This database will be deleted during teardown.
    """

    # TODO - can we derive the schema from local_model?

    db = notion.databases.create(
        parent=test_area,
        title=mktitle(),
        schema={
            "Name": schema.Title(),
            "Index": schema.Number(),
            "Notes": schema.RichText(),
            "Complete": schema.Checkbox(),
            "Due Date": schema.Date(),
            "Tags": schema.MultiSelect(),
        },
    )

    yield db

    notion.databases.delete(db)


@pytest.fixture
def simple_model(notion, simple_db):
    """Return a Connected Page that matches the schema for `simple_db`.

    The model's database will be deleted during teardown.
    """

    yield connected_page(session=notion, source_db=simple_db)
