"""Unit tests for the Notional iterators."""

from ultimate_notion.core.iterator import EndpointIterator

from ..mocks import mock_endpoint


def test_basic_usage():
    """Simple test for basic functionality."""

    mock = mock_endpoint(1042, 100)
    iter = EndpointIterator(endpoint=mock, user_data="testing")

    n_items = 0

    for item in iter:
        assert item["index"] == n_items
        assert item["pagenum"] == iter.page_number
        assert item["content"] == "testing"

        n_items += 1
        assert iter.total_items == n_items

    assert n_items == 1042


def test_exactly_one_page():
    """Test the iterator for exactly one page of results."""

    mock = mock_endpoint(100, 100)
    iter = EndpointIterator(endpoint=mock, user_data="one_page")

    n_items = 0

    for item in iter:
        assert item["content"] == "one_page"
        assert iter.last_page
        assert iter.page_number == 1

        n_items += 1

    assert n_items == 100


def test_one_result():
    """Make sure the iterator works for exactly one result."""

    mock = mock_endpoint(1, 100)
    iter = EndpointIterator(endpoint=mock)

    n_items = 0

    for item in iter:
        assert item["content"] is None
        assert iter.last_page
        assert iter.page_number == 1

        n_items += 1

    assert n_items == 1


def test_empty_result():
    """Make sure the iterator works with empty results."""

    mock = mock_endpoint(0, 100)
    iter = EndpointIterator(endpoint=mock)

    n_items = 0

    for _ in iter:
        n_items += 1

    assert n_items == 0, f"found {n_items} unexpected item(s) in result set"
