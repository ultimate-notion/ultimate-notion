import datetime as dt

import pendulum as pnd

from ultimate_notion.obj_api import objects as objs


def test_date_range(tz_berlin):
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

    date_interval = pnd.interval(start=pnd.parse('2024-01-01', exact=True), end=pnd.parse('2024-01-03', exact=True))
    obj = objs.DateRange.build(date_interval)
    assert isinstance(obj.start, dt.date)
    assert obj.start == date_interval.start
    assert isinstance(obj.end, dt.date)
    assert obj.end == date_interval.end
    assert obj.time_zone is None
    assert obj.to_pendulum() == date_interval

    datetime_interval = pnd.interval(start=pnd.parse('2024-01-01 10:00'), end=pnd.parse('2024-01-03 12:00'))
    obj = objs.DateRange.build(datetime_interval)
    assert isinstance(obj.start, dt.datetime)
    assert obj.start == datetime_interval.start
    assert isinstance(obj.end, dt.datetime)
    assert obj.end == datetime_interval.end
    assert obj.time_zone == 'UTC'
    assert obj.to_pendulum() == datetime_interval
