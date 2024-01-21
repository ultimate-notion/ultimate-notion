from datetime import date, datetime, timezone

from ultimate_notion.obj_api import objects as objs


def test_date_range():
    date_obj = date(2023, 1, 1)
    datetime_obj = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    obj = objs.DateRange.build(start=date_obj, end=datetime_obj)
    assert obj.start == date_obj
    assert obj.end == datetime_obj
    assert isinstance(obj.start, date)
    assert isinstance(obj.end, datetime)

    obj = objs.DateRange.build(start=datetime_obj)
    assert obj.start == datetime_obj
