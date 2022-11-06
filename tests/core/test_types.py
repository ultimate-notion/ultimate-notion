"""Unit tests for Notional types."""

from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from ultimate_notion.core import schema, types, user

# TODO look for opportunities to parse using VCR - avoid keeping embedded data


def test_page_reference_from_uuid():
    """Compose a PageReference from a UUID."""
    id = uuid4()

    ref = types.PageReference[id]

    assert ref.id == id


def test_page_reference_from_str():
    """Compose a PageReference from an ID string."""
    id = uuid4()

    ref = types.PageReference(id=id.hex)

    assert ref.id == id


def test_page_reference_from_ref():
    """Compose a PageReference from another PageRef."""
    id = uuid4()

    orig = types.PageReference(id=id)
    new = types.PageReference[orig]

    assert new.id == id


def test_invalid_page_reference_from_ref():
    """Try to create a PageReference from invalid data."""

    with pytest.raises(ValueError):
        types.PageReference[None]

    with pytest.raises(ValueError):
        types.PageReference[False]

    with pytest.raises(ValueError):
        types.PageReference[42]


def test_parse_title_data():
    """Create a Title object from API data."""

    test_data = {
        "id": "title",
        "type": "title",
        "title": [
            {
                "type": "text",
                "text": {"content": "Buy milk", "link": None},
                "annotations": {
                    "bold": False,
                    "italic": False,
                    "strikethrough": False,
                    "underline": False,
                    "code": False,
                    "color": "default",
                },
                "plain_text": "Buy milk",
                "href": None,
            }
        ],
    }

    title = types.Title.parse_obj(test_data)

    assert title.id == "title"
    assert title.Value == "Buy milk"


def test_title_from_value():
    """Create a Title object from a literal string."""
    title = types.Title["Get more milk"]
    assert title.Value == "Get more milk"


def test_parse_number_data():
    """Create a Number object from API data."""

    test_data = {"id": "XQOP", "type": "number", "number": 42}

    num = types.Number.parse_obj(test_data)

    assert num.type == "number"
    assert num.number == 42


def test_number_from_float_value():
    """Create a Number object from a literal float."""
    num = types.Number[2.718281828]
    assert num.Value == 2.718281828


def test_number_from_string_value():
    """Create a Number object from a literal string."""
    num = types.Number["100.00"]
    assert num.Value == 100


def test_number_from_bad_string():
    """Check exceptions for strings with invalid values."""
    with pytest.raises(ValidationError):
        types.Number["twelve"]


def test_number_math():
    """Perform math on Number objects."""
    num = types.Number[10]

    num += 2
    assert num.Value == 12

    num -= 20
    assert num.Value == -8


def test_parse_checkbox_data():
    """Create a Checkbox object from API data."""

    test_data = {"id": "ax{O", "type": "checkbox", "checkbox": False}

    check = types.Checkbox.parse_obj(test_data)

    assert check.type == "checkbox"
    assert not check.checkbox


def test_checkbox_from_boolean_value():
    """Create a Checkbox object from a boolean."""
    check = types.Checkbox[True]
    assert check.Value


def test_checkbox_from_string_value():
    """Create a Checkbox object from a string."""
    check = types.Checkbox["no"]
    assert not check.Value


def test_checkbox_from_bad_string():
    """Check exceptions for strings with invalid values."""
    with pytest.raises(ValidationError):
        types.Checkbox["foo"]


def test_parse_single_date():
    """Create a simple Date object from API data."""

    test_data = {
        "id": "[wke",
        "type": "date",
        "date": {"start": "2020-08-04", "end": None},
    }

    single = types.Date.parse_obj(test_data)

    assert single.type == "date"
    assert single.Start == date(2020, 8, 4)
    assert not single.IsRange

    with pytest.raises(ValueError):
        if date(2020, 8, 4) in single:
            pass


def test_parse_date_with_time():
    """Create a Date object with time from API data."""

    test_data = {
        "id": "_mGp",
        "type": "date",
        "date": {"start": "2021-05-04T07:11:03.141Z", "end": None},
    }

    tstamp = types.Date.parse_obj(test_data)

    assert tstamp.type == "date"
    assert tstamp.Start == datetime(2021, 5, 4, 7, 11, 3, 141000, timezone.utc)
    assert not tstamp.IsRange


def test_parse_date_range():
    """Create a Date range object from API data."""

    test_data = {
        "id": "<|;g",
        "type": "date",
        "date": {"start": "1978-11-01", "end": "1978-11-30"},
    }

    span = types.Date.parse_obj(test_data)

    assert span.type == "date"
    assert span.IsRange

    assert span.Start == date(1978, 11, 1)
    assert span.End == date(1978, 11, 30)

    assert date(1978, 11, 18) in span
    assert date(1978, 11, 1) in span
    assert date(1978, 11, 30) in span


def test_compose_date():
    """Compose a Date from a single datetime."""

    today = date.today()
    single = types.Date[today]

    assert single.IsRange is False
    assert single.Start == today
    assert single.End is None


def test_compose_date_range():
    """Compose a Date from a single datetime."""

    today = date.today()
    tomorrow = today + timedelta(days=1)

    one_day = types.Date[today, tomorrow]

    assert one_day.IsRange is True
    assert one_day.Start == today
    assert one_day.End == tomorrow


def test_parse_select_one_data():
    """Create a SelectOne object from API data."""

    test_data = {
        "id": "c::a",
        "type": "select",
        "select": {
            "id": "4e76c87f-2189-4560-88a7-95a5eca140dd",
            "name": "High",
            "color": "yellow",
        },
    }

    priority = types.SelectOne.parse_obj(test_data)

    assert priority.type == "select"
    assert priority == "High"
    assert priority.Value == "High"


def test_compose_select_one():
    """Create a SelectOne object from a literal string."""
    priority = types.SelectOne["URGENT"]
    assert priority == "URGENT"


def test_compose_empty_select_one():
    """Try to compose an empty SelectOne object."""
    with pytest.raises(ValueError):
        types.SelectOne[None]


def test_parse_multi_select_data():
    """Create a MultiSelect object from API data."""

    test_data = {
        "id": "W:kr",
        "type": "multi_select",
        "multi_select": [
            {
                "id": "89696e9c-17a8-4a90-b0a6-ede587d3705d",
                "name": "Grocery",
                "color": "default",
            }
        ],
    }

    tags = types.MultiSelect.parse_obj(test_data)

    assert tags.type == "multi_select"
    assert "Grocery" in tags

    tags += "TEMPORARY"
    assert "TEMPORARY" in tags

    tags -= "TEMPORARY"
    assert "TEMPORARY" not in tags


def test_multi_select_from_string():
    """Create a MultiSelect object from a string."""
    tags = types.MultiSelect["bar"]

    assert len(tags) == 1
    assert tags.Values == ["bar"]
    assert "foo" not in tags

    # there should be exactly one item returned by the iterator...
    for item in tags:
        assert item.name == "bar"


def test_multi_select_from_list():
    """Create a MultiSelect object from a list of strings."""
    tags = types.MultiSelect[["foo", None, "bar"]]

    assert len(tags) == 2
    assert tags.Values == ["foo", "bar"]
    assert None not in tags


def test_compose_status():
    """Create a Status object from a literal string."""
    backlog = types.Status["Backlog"]
    assert backlog == "Backlog"


def test_parse_email_data():
    """Create an Email object from API data."""

    test_data = {"id": "QU|p", "type": "email", "email": "alice@example.com"}

    contact = types.Email.parse_obj(test_data)

    assert contact.type == "email"
    assert contact.email == "alice@example.com"


def test_parse_phone_data():
    """Create a PhoneNumber object from API data."""

    test_data = {
        "id": "tLo^",
        "type": "phone_number",
        "phone_number": "555-555-1234",
    }

    contact = types.PhoneNumber.parse_obj(test_data)

    assert contact.type == "phone_number"
    assert contact.phone_number == "555-555-1234"


def test_parse_url_data():
    """Create a URL object from API data."""

    test_data = {
        "id": "rNKf",
        "type": "url",
        "url": "https://en.wikipedia.org/wiki/Milk",
    }

    wiki = types.URL.parse_obj(test_data)

    assert wiki.type == "url"
    assert wiki.url == "https://en.wikipedia.org/wiki/Milk"


def test_parse_string_formula():
    """Create a Formula string object from API data."""

    test_data = {
        "id": "s|>T",
        "type": "formula",
        "formula": {"type": "string", "string": "Buy milk [Alice]"},
    }

    title = types.Formula.parse_obj(test_data)

    assert title.type == "formula"
    assert title.Result == "Buy milk [Alice]"


def test_parse_number_formula():
    """Create a Formula number object from API data."""

    test_data = {
        "id": "?Y=S",
        "type": "formula",
        "formula": {"type": "number", "number": 2020},
    }

    year = types.Formula.parse_obj(test_data)

    assert year.type == "formula"
    assert year.Result == 2020


def test_parse_date_formula():
    """Create a Formula date object from API data."""

    test_data = {
        "id": "ab@]",
        "type": "formula",
        "formula": {"type": "date", "date": {"start": "2020-09-03", "end": None}},
    }

    up = types.Formula.parse_obj(test_data)
    real = types.DateRange(start=date(2020, 9, 3))

    assert up.type == "formula"
    assert up.Result == real


def test_parse_relation():
    """Create a Relation object from API data."""

    test_data = {
        "id": ">m;y",
        "type": "relation",
        "relation": [
            {"id": "5497f1ce-4fab-4594-8cf6-112a3158d96d"},
            {"id": "a26146b5-3c73-4e3e-86dd-08cf2f7007c9"},
        ],
    }

    relation = types.Relation.parse_obj(test_data)
    assert relation.type == "relation"


def test_parse_rollup_number():
    """Create a Rollup number object from API data."""

    test_data = {
        "id": "Ob:b",
        "type": "rollup",
        "rollup": {"type": "number", "number": 41, "function": "sum"},
    }

    rollup = types.Rollup.parse_obj(test_data)
    assert rollup.type == "rollup"

    assert rollup.rollup.type == "number"
    assert rollup.rollup.number == 41
    assert rollup.rollup.function == schema.Function.SUM


def test_parse_rollup_date():
    """Create a Rollup date object from API data."""

    test_data = {
        "id": "Mu?O",
        "type": "rollup",
        "rollup": {
            "type": "date",
            "date": {"start": "2022-10-23", "end": None},
            "function": "latest_date",
        },
    }

    rollup = types.Rollup.parse_obj(test_data)
    assert rollup.type == "rollup"

    assert rollup.rollup.type == "date"
    assert rollup.rollup.date.start == date(2022, 10, 23)
    assert rollup.rollup.date.end is None
    assert rollup.rollup.function == schema.Function.LATEST_DATE


def test_parse_rollup_array():
    """Create a Rollup array object from API data."""

    test_data = {
        "id": "bXNJ",
        "type": "rollup",
        "rollup": {
            "type": "array",
            "array": [
                {"type": "number", "number": 6},
                {"type": "number", "number": 4},
            ],
            "function": "show_original",
        },
    }

    rollup = types.Rollup.parse_obj(test_data)
    assert rollup.type == "rollup"

    assert rollup.rollup.type == "array"
    assert rollup.rollup.function == schema.Function.SHOW_ORIGINAL
    assert rollup.rollup.type == "array"

    for prop in rollup.rollup.array:
        assert prop.type == "number"

    assert 6 in rollup.rollup.array
    assert 4 in rollup.rollup.array


def test_parse_people_data():
    """Create a People object from API data."""

    test_data = {
        "id": "nQ<Y",
        "type": "people",
        "people": [
            {
                "object": "user",
                "id": "62e40b6e-3f05-494f-9220-d68a1995b54f",
                "name": "Alice",
                "avatar_url": None,
                "type": "person",
                "person": {"email": "alice@example.com"},
            }
        ],
    }

    owner = types.People.parse_obj(test_data)

    assert owner.type == "people"
    assert "Alice" in owner

    for person in owner:
        assert isinstance(person, user.User)


def test_parse_files_data():
    """Create a Files object from API data."""

    test_data = {
        "id": "NNT{",
        "type": "files",
        "files": [
            {
                "name": "glass.jpg",
                "type": "external",
                "external": {
                    "url": "https://upload.wikimedia.org/wikipedia/commons/a/a5/Glass_of_Milk_%2833657535532%29.jpg"  # noqa: E501
                },
            }
        ],
    }

    files = types.Files.parse_obj(test_data)

    assert files.type == "files"
    assert "glass.jpg" in files

    glass = files["glass.jpg"]

    assert glass is not None
    assert glass.type == "external"


def test_created_time():
    """Create a CreatedTime object from API data."""

    test_data = {
        "id": "v}{N",
        "type": "created_time",
        "created_time": "1999-12-31T23:59:59.999Z",
    }

    created = types.CreatedTime.parse_obj(test_data)
    assert created.type == "created_time"

    assert created.created_time == datetime(1999, 12, 31, 23, 59, 59, 999000, timezone.utc)


def test_created_by():
    """Create a CreatedBy object from API data."""

    test_data = {
        "id": "@yUe",
        "type": "created_by",
        "created_by": {
            "object": "user",
            "id": "65970102-79f4-48ed-8065-0ff257e46558",
            "name": "Bob the Person",
            "avatar_url": "https://upload.wikimedia.org/wikipedia/en/d/d0/Dogecoin_Logo.png",  # noqa: E501
            "type": "person",
            "person": {"email": "bob@example.com"},
        },
    }

    created = types.CreatedBy.parse_obj(test_data)
    assert created.type == "created_by"

    author = created.created_by
    assert author.name == "Bob the Person"


def test_last_edited_time():
    """Verify LastEditedTime property values."""

    test_data = {
        "id": "HdA>",
        "type": "last_edited_time",
        "last_edited_time": "2000-01-01T00:00:00.000Z",
    }

    updated = types.LastEditedTime.parse_obj(test_data)
    assert updated.type == "last_edited_time"

    assert updated.last_edited_time == datetime(2000, 1, 1, 0, 0, 0, 0, timezone.utc)


def test_last_edited_by():
    """Verify LastEditedBy property values."""

    test_data = {
        "id": "dxcT",
        "type": "last_edited_by",
        "last_edited_by": {
            "object": "user",
            "id": "62e40b6e-3f05-494f-9220-d68a1995b54f",
            "name": "Alice the Person",
            "avatar_url": None,
            "type": "person",
            "person": {"email": "alice@example.com"},
        },
    }

    updated = types.LastEditedBy.parse_obj(test_data)
    assert updated.type == "last_edited_by"

    author = updated.last_edited_by
    assert author.name == "Alice the Person"


def test_parse_mention_user_objecy():
    """Create a Mention user object from API data."""

    test_data = {
        "type": "mention",
        "plain_text": "@Alice",
        "mention": {
            "type": "user",
            "user": {
                "object": "user",
                "id": "62e40b6e-3f05-494f-9220-d68a1995b54f",
                "name": "Alice",
                "avatar_url": None,
                "type": "person",
                "person": {"email": "alice@example.com"},
            },
        },
    }

    at = types.MentionObject.parse_obj(test_data)

    assert at.type == "mention"
    assert at.mention.type == "user"

    data = at.mention.user

    assert data.name == "Alice"


def test_parse_mention_date_object():
    """Create a Mention date object from API data."""

    test_data = {
        "type": "mention",
        "plain_text": "FUTURE",
        "mention": {"type": "date", "date": {"start": "2099-01-01", "end": None}},
    }

    at = types.MentionObject.parse_obj(test_data)

    assert at.type == "mention"
    assert at.mention.type == "date"

    data = at.mention.date

    assert data.start == date(2099, 1, 1)


def test_parse_mention_page_object():
    """Create a Mention page object from API data."""

    test_data = {
        "type": "mention",
        "plain_text": "Awesome Sauce",
        "mention": {
            "type": "page",
            "page": {"id": "c0703d87-e3c5-4492-9654-a7d97c1262a2"},
        },
    }

    mention = types.MentionObject.parse_obj(test_data)

    assert mention.type == "mention"

    nested = mention()

    assert isinstance(nested, types.MentionPage)
    assert nested.type == "page"

    data = mention("page")

    assert data.id == UUID("c0703d87-e3c5-4492-9654-a7d97c1262a2")


def test_parse_mention_database_object():
    """Create a Mention database object from API data."""

    test_data = {
        "type": "mention",
        "plain_text": "Superfreak",
        "mention": {
            "type": "database",
            "database": {"id": "57202d16-08c9-43db-a112-a0f25443dc48"},
        },
    }

    mention = types.MentionObject.parse_obj(test_data)

    assert mention.type == "mention"

    nested = mention()

    assert isinstance(nested, types.MentionDatabase)
    assert nested.type == "database"

    data = mention("database")

    assert data.id == UUID("57202d16-08c9-43db-a112-a0f25443dc48")


def test_parse_equation_data():
    """Create an Equation object from API data."""

    test_data = {
        "type": "equation",
        "plain_text": "1 + 1 = 3",
        "equation": {"expression": "1 + 1 = 3"},
    }

    math = types.EquationObject.parse_obj(test_data)

    assert math.type == "equation"
    assert math.equation.expression == "1 + 1 = 3"


def test_rich_text_from_value():
    """Create RichText from a literal value."""
    rtf = types.RichText["We have new milk."]
    assert rtf.Value == "We have new milk."


def test_parse_rich_text_data():
    """Create RichText from API data."""

    test_data = {
        "id": ":T<z",
        "type": "rich_text",
        "rich_text": [
            {
                "type": "text",
                "plain_text": "Our ",
                "href": None,
                "annotations": {
                    "bold": False,
                    "italic": False,
                    "strikethrough": False,
                    "underline": False,
                    "code": False,
                    "color": "default",
                },
                "text": {"content": "Our ", "link": None},
            },
            {
                "type": "text",
                "plain_text": "milk",
                "href": None,
                "annotations": {
                    "bold": False,
                    "italic": False,
                    "strikethrough": False,
                    "underline": False,
                    "code": False,
                    "color": "gray",
                },
                "text": {"content": "milk", "link": None},
            },
            {
                "type": "text",
                "plain_text": " is ",
                "href": None,
                "annotations": {
                    "bold": False,
                    "italic": False,
                    "strikethrough": False,
                    "underline": False,
                    "code": False,
                    "color": "default",
                },
                "text": {"content": " is ", "link": None},
            },
            {
                "type": "text",
                "plain_text": "very",
                "href": None,
                "annotations": {
                    "bold": True,
                    "italic": False,
                    "strikethrough": False,
                    "underline": True,
                    "code": False,
                    "color": "default",
                },
                "text": {"content": "very", "link": None},
            },
            {
                "type": "text",
                "plain_text": " old.",
                "href": None,
                "annotations": {
                    "bold": False,
                    "italic": False,
                    "strikethrough": False,
                    "underline": False,
                    "code": False,
                    "color": "default",
                },
                "text": {"content": " old.", "link": None},
            },
        ],
    }

    rtf = types.RichText.parse_obj(test_data)
    assert rtf.type == "rich_text"
    assert rtf.Value == "Our milk is very old."
