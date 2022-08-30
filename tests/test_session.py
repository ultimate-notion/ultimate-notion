"""Unit tests for the Notional session."""

import pytest

from ultimate_notion.core import records


@pytest.mark.vcr()
def test_session_raise_for_status(notion):
    """Verify the active session responds or raise."""
    assert notion.raise_for_status() is None


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
