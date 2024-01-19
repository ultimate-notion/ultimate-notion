from datetime import date, datetime, timezone

from ultimate_notion.obj_api import objects as objs


def test_date_range():
    start_date = date(2023, 1, 1)
    end_datetime = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    obj = objs.DateRange.build(start=start_date, end=end_datetime)
    assert obj.start == start_date
    assert obj.end == end_datetime
    assert isinstance(obj.start, date)
    assert isinstance(obj.end, datetime)
