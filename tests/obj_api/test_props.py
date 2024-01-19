from ultimate_notion.obj_api import props as obj_props


def test_number():
    obj = obj_props.Number.build(42)
    assert obj.number == 42
    assert isinstance(obj.number, int)

    obj = obj_props.Number.build(42.0)
    assert obj.number == 42.0
    assert isinstance(obj.number, float)
