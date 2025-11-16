from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, cast

import pendulum as pnd
import pytest

from ultimate_notion.obj_api import blocks as obj_blocks
from ultimate_notion.obj_api import objects as objs

if TYPE_CHECKING:
    import ultimate_notion as uno


def test_date_range(tz_berlin: str) -> None:
    date = pnd.date(2024, 1, 1)
    obj = objs.DateRange.build(date)
    assert isinstance(obj.start, dt.date)
    assert obj.start == date
    assert obj.end is None
    assert obj.time_zone is None
    assert obj.to_pendulum() == date

    datetime = pnd.datetime(2024, 1, 1, 12, 0, 0, tz=tz_berlin)
    obj = objs.DateRange.build(datetime)
    assert isinstance(obj.start, dt.datetime)
    assert obj.start == datetime.naive()
    assert obj.end is None
    assert obj.time_zone == tz_berlin
    assert obj.to_pendulum() == datetime

    start = cast(pnd.DateTime, pnd.parse('2024-01-01', exact=True))
    end = cast(pnd.DateTime, pnd.parse('2024-01-03', exact=True))
    date_interval = pnd.interval(start=start, end=end)
    obj = objs.DateRange.build(date_interval)
    assert isinstance(obj.start, dt.date)
    assert obj.start == date_interval.start
    assert isinstance(obj.end, dt.date)
    assert obj.end == date_interval.end
    assert obj.time_zone is None
    assert obj.to_pendulum() == date_interval

    start = cast(pnd.DateTime, pnd.parse('2024-01-01 10:00', exact=True))
    end = cast(pnd.DateTime, pnd.parse('2024-01-03 12:00', exact=True))
    datetime_interval = pnd.interval(start=start, end=end)
    obj = objs.DateRange.build(datetime_interval)
    assert isinstance(obj.start, dt.datetime)
    assert obj.start == datetime_interval.start
    assert isinstance(obj.end, dt.datetime)
    assert obj.end == datetime_interval.end
    assert obj.time_zone == 'UTC'
    assert obj.to_pendulum() == datetime_interval


@pytest.mark.vcr()
def test_pageref(intro_page: uno.Page) -> None:
    page_ref = objs.PageRef(page_id=intro_page.id)
    obj_link_to_page = obj_blocks.LinkToPage(link_to_page=page_ref, type='link_to_page')
    assert cast(objs.PageRef, obj_link_to_page.link_to_page).page_id == intro_page.id
