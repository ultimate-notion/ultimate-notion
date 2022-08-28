"""Unit tests for the Notional ORM classes."""

from uuid import uuid4

import pytest

from ultimate_notion.core import blocks, schema, types
from ultimate_notion.core.orm import ConnectedPage, Property, connected_page


def test_property_type():
    """Confirm that `Property()` returns a `property`."""

    prop = Property("Special", schema.Title())
    assert isinstance(prop, property)


def test_invalid_property_types():
    """Fail when using incorrect Property definitions."""

    with pytest.raises(TypeError):
        Property("BAD_TYPE", schema.Title)

    with pytest.raises(TypeError):
        Property("BAD_TYPE", types.Title())

    with pytest.raises(TypeError):
        Property("BAD_TYPE", "ImaType")


def test_invalid_base_class():
    """Verify that we cannot create connected pages from invalid classes."""

    class _MySpecialPage:
        __database__ = "mock_db"

    with pytest.raises(ValueError):
        connected_page(cls=_MySpecialPage)


def test_session_is_none(local_model):
    """Verify we raise expected errors when the session is None."""

    with pytest.raises(ValueError):
        local_model.create()


def test_empty_page(local_model):
    """Verify expected behavior with an empty page."""
    empty = local_model()

    assert isinstance(empty, ConnectedPage)
    assert empty.id is None

    num_children = 0

    for _ in empty.children:
        num_children += 1

    assert num_children == 0, f"found {num_children} unexpected child(ren) on page"

    with pytest.raises(ValueError):
        empty += blocks.Divider()


def test_custom_model_page_id(local_model):
    """Make sure the page ID comes through."""
    page_id = uuid4()

    data = {"id": page_id.hex}

    page = local_model.parse_obj(data)
    assert page.id == page_id


@pytest.mark.vcr()
def test_simple_model(notion, simple_model):
    """Create a simple object and verify connectivity."""

    only = simple_model.create(Name="One&Only")
    assert only.Name == "One&Only"

    obj = notion.pages.retrieve(only.id)
    assert only.Name == obj.Title


@pytest.mark.vcr()
def test_change_model_title(notion, simple_model):
    """Create a simple custom object and change its data."""
    first = simple_model.create(Name="First")

    first.Name = "Second"
    assert first.Name == "Second"

    # in our model, `Name` is the title property...
    obj = notion.pages.retrieve(first.id)
    assert first.Name == obj.Title


@pytest.mark.vcr()
def test_simple_model_with_children(simple_model):
    """Verify appending child blocks to custom types."""
    first = simple_model.create(Name="First")
    first += blocks.Heading1["New Business"]

    num_children = 0

    for child in first.children:
        assert child.PlainText == "New Business"
        num_children += 1

    assert num_children == 1


def test_missing_database():
    """Raise an error if a custom model fails to specify a database."""

    CustomPage = connected_page()

    class _MissingDatabase(CustomPage):
        pass

    with pytest.raises(ValueError):
        _MissingDatabase.create()


@pytest.mark.vcr()
def test_missing_property(notion, simple_db):
    """Make sure we raise an error on missing properties."""

    CustomPage = connected_page(session=notion)

    class _ConnectedModel(CustomPage):
        __database__ = simple_db.id

        Name = Property("Name", schema.Title())
        NewProperty = Property("NoSuchProperty")

    incorrect = _ConnectedModel.create(Name="MissingProp")

    assert incorrect.Name == "MissingProp"

    with pytest.raises(AttributeError):
        assert incorrect.NewProperty != ...


@pytest.mark.vcr()
def test_orm_icon(notion, simple_model):
    """Set the icon for a connected page."""

    burger = simple_model.create()
    burger.icon = "🍔"

    fries = simple_model.create()
    fries.icon = "🍟"

    shake = simple_model.create()
    shake.icon = "🥤"

    obj = notion.pages.retrieve(burger.id)

    assert obj.icon is not None
    assert obj.icon.emoji == "🍔"


@pytest.mark.vcr()
def test_orm_query(simple_model):
    """Make sure we can query for custom types."""

    needle = simple_model.create(Name="Needle")

    obj = simple_model.query().first()

    assert obj.id == needle.id
    assert obj.Name == "Needle"
