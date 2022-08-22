"""Unit tests for the Notional session."""

import pytest

from ultimate_notion import records


@pytest.mark.vcr()
def test_active_session(notion):
    """Verify the session reports as active."""
    assert notion.IsActive

    notion.close()
    assert not notion.IsActive


@pytest.mark.vcr()
def test_ping_session(notion):
    """Verify the active session responds to a ping."""
    assert notion.ping()


@pytest.mark.vcr()
def test_simple_search(notion):
    """Make sure search returns some results."""

    search = notion.search()

    num_results = 0

    for result in search.execute():
        assert isinstance(result, records.Record)
        num_results += 1

    # sanity check to make sure some results came back
    assert num_results > 0
