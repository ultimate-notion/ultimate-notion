"""Unit tests for Notional query objects."""

import pytest

from ultimate_notion.core import query

from ..mocks import MockDataObject, mock_endpoint

# NOTE these tests help to debug issues in the query builder, however they do not
# perform an actual query.  the intent of these objects is to represent the API
# definition of the query, as opposed to run actual filter, sort, etc operations


def test_empty_query():
    """Create an empty query."""
    qb = query.QueryBuilder(None)

    with pytest.raises(ValueError):
        qb.first()


def test_basic_number_constraint():
    """Filter a query based on a number value."""
    mock = mock_endpoint(1000, 100)

    qb = (
        query.QueryBuilder(mock, cls=MockDataObject)
        .filter(property="index", number=query.NumberCondition(equals=42))
        .limit(1)
    )

    qb.first()


def test_number_range_constraint():
    """Filter a query based on a number range."""
    mock = mock_endpoint(1000, 23)

    qb = (
        query.QueryBuilder(mock, cls=MockDataObject)
        .filter(
            property="index",
            number=query.NumberCondition(greater_than=25),
        )
        .filter(
            property="index",
            number=query.NumberCondition(less_than_or_equal_to=75),
        )
    )

    qb.first()


def test_invalid_filter():
    """Make sure that bad filters give an error."""
    with pytest.raises(ValueError):
        query.QueryBuilder(None).filter(bad_filter_name="INVALID")


def test_invalid_sort():
    """Make sure that bad sort give an error."""
    with pytest.raises(ValueError):
        query.QueryBuilder(None).sort(sort=False)
