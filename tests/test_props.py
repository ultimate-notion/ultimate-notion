from __future__ import annotations

from datetime import datetime

from hypothesis import given
from hypothesis import strategies as st

from ultimate_notion.props import Date


@given(
    st.datetimes(
        min_value=datetime(2000, 1, 1),  # noqa: DTZ001, hypothesis doesn't want tzinfo
        max_value=datetime(2099, 12, 31),  # noqa: DTZ001, hypothesis doesn't want tzinfo
    ),
    st.datetimes(
        min_value=datetime(3000, 1, 1),  # noqa: DTZ001, hypothesis doesn't want tzinfo
        max_value=datetime(3099, 12, 31),  # noqa: DTZ001, hypothesis doesn't want tzinfo
    ),
)
def test_date_with_datetime(d1, d2):
    # ToDo: Implement actual test
    Date(d1)
    Date(d1, d2)
