"""Unit tests for the Notional parsers."""

import os

import pytest

from ultimate_notion.core import blocks
from ultimate_notion.core.text import plain_text
from ultimate_notion.parser import HtmlParser

BASEDIR = os.path.dirname(os.path.abspath(__file__))


def check_single_block(html, expected_type, expected_text):
    """Verify the given HTML is parsed into expected block."""

    parser = HtmlParser()
    parser.parse(html)

    assert len(parser.content) >= 1

    block = parser.content[0]

    assert isinstance(block, expected_type)

    if expected_text is not None:
        assert block.PlainText == expected_text

    return block


def check_table_data(html, expected):
    """Verify the given HTML is parsed into expected table data.

    The `expected` data must conform to the following strucure:
        [
            [row_1_cell_1, row_1_cell_2, row_1_cell_3, ...],
            [row_1_cell_2, row_2_cell_2, row_2_cell_3, ...],
            ...
        ]

    Each cell will be compared to the parsed HTML results and confirmed.
    """

    parser = HtmlParser()
    parser.parse(html)

    assert len(parser.content) == 1

    table = parser.content[0]

    assert isinstance(table, blocks.Table)

    rows = table("children")
    assert len(rows) == len(expected)

    for idx in range(len(rows)):
        parser_row = rows[idx]
        expected_row = expected[idx]

        assert isinstance(parser_row, blocks.TableRow)

        cells = parser_row("cells")
        assert len(cells) == len(expected_row)

        for jdx in range(len(cells)):
            parser_cell = cells[jdx]
            expected_cell = expected_row[jdx]

            parser_text = plain_text(*parser_cell)
            expected_text = str(expected_cell)

            assert parser_text == expected_text


def check_style(text, **expected_style):
    """Check the given text block for the specified annotations.

    Example: `check_style(text, bold=True)` will ensure that the bold flag is
    set to `True` in the `text` object annotations.

    Similarly, `check_style(text, underline=False)` will ensure that the underline
    flag is set to `False`.

    Multiple flags may be specified.  For example:
        `check_style(text, bold=True, italic=True)`
    will verify the status of both the `bold` and `italic` flags.
    """

    current_style = text.annotations

    for attrib in expected_style:
        current_value = getattr(current_style, attrib)
        expected_value = expected_style[attrib]
        assert current_value == expected_value


@pytest.fixture
def dormouse():
    """Parse the `dormouse.html` test data as a test fixture."""
    parser = HtmlParser()

    filename = os.path.join(BASEDIR, "dormouse.html")
    with open(filename, "r") as fp:
        html = fp.read()

    parser.parse(html)

    return parser


def test_dormouse(dormouse):
    """Confirm parsing of the `dormouse.html` test file."""

    assert dormouse.title == "The Dormouse's Story"
    assert dormouse.content is not None
    assert len(dormouse.content) > 0


def test_basic_title():
    """Confirm proper handling of `<title>` tags."""

    html = "<html><head><title>Hello World</title></head></html>"

    parser = HtmlParser()
    parser.parse(html)

    assert parser.title == "Hello World"
    assert len(parser.content) == 0


def test_basic_comment():
    """Confirm proper handling of comment tags."""

    html = "<!-- Hide this text -->"

    parser = HtmlParser()
    parser.parse(html)

    assert len(parser.content) == 0


def test_divider():
    """Confirm support for `<br>` tags."""

    check_single_block(
        html="<body><hr></body>",
        expected_type=blocks.Divider,
        expected_text=None,
    )


def test_heading_1():
    """Confirm support for `<h1>` tags."""

    check_single_block(
        html="<h1>Heading One</h1>",
        expected_type=blocks.Heading1,
        expected_text="Heading One",
    )


def test_heading_2():
    """Confirm support for `<h2>` tags."""

    check_single_block(
        html="<h2>Heading Two</h2>",
        expected_type=blocks.Heading2,
        expected_text="Heading Two",
    )


def test_heading_3():
    """Confirm support for `<h3>` tags."""

    check_single_block(
        html="<h3>Heading Three</h3>",
        expected_type=blocks.Heading3,
        expected_text="Heading Three",
    )


def test_basic_paragraph():
    """Confirm support for `<p>` tags."""

    check_single_block(
        html="<p>Lorem ipsum dolor sit amet, ...</p>",
        expected_type=blocks.Paragraph,
        expected_text="Lorem ipsum dolor sit amet, ...",
    )


def test_extra_whitespace():
    """Confirm handling of "ignorable" whitespace within an element."""

    check_single_block(
        html="<p> ...\tconsectetur   adipiscing\nelit.  </p>",
        expected_type=blocks.Paragraph,
        expected_text="... consectetur adipiscing elit.",
    )


def test_naked_text():
    """Confirm support for plain text elements."""

    check_single_block(
        html="Look ma, no tags!",
        expected_type=blocks.Paragraph,
        expected_text="Look ma, no tags!",
    )


def test_basic_quote():
    """Confirm support for `<blockquote>` elements."""

    check_single_block(
        html="<blockquote>To be, or not to be...</blockquote>",
        expected_type=blocks.Quote,
        expected_text="To be, or not to be...",
    )


def test_basic_pre():
    """Confirm support for `<pre>` elements."""

    check_single_block(
        html="<pre>    ...that is the question</pre>",
        expected_type=blocks.Code,
        expected_text="    ...that is the question",
    )


def test_bulleted_list():
    """Confirm support for bulleted lists."""

    html = "<ul><li>Eenie</li><li>Meenie</li></ul"

    parser = HtmlParser()
    parser.parse(html)

    assert len(parser.content) == 2

    li = parser.content[0]
    assert isinstance(li, blocks.BulletedListItem)
    assert li.PlainText == "Eenie"

    li = parser.content[1]
    assert isinstance(li, blocks.BulletedListItem)
    assert li.PlainText == "Meenie"


def test_incorrect_nested_list():
    """Confirm support for improperly nested lists."""

    html = """<ul>
        <li>Outer A</li>
        <li>Outer B</li>
        <ul>
            <li>Inner A</li>
        </ul>
        <li>Outer C</li>
    </ul>"""

    parser = HtmlParser()
    parser.parse(html)

    assert len(parser.content) == 3

    for block in parser.content:
        assert isinstance(block, blocks.BulletedListItem)

    li = parser.content[1]
    assert li.has_children

    for block in parser.content[1].__children__:
        assert isinstance(block, blocks.BulletedListItem)


def test_implicit_text():
    """Confirm support for text outside of phrasing elements."""

    html = "<body><div>Open Text</div></body>"

    parser = HtmlParser()
    parser.parse(html)

    found_text = False

    for block in parser.content:
        assert isinstance(block, blocks.TextBlock)
        assert block.PlainText == "Open Text"
        found_text = True

    assert found_text


def test_strong_text():
    """Confirm support for strong/bold text."""

    block = check_single_block(
        html="<b>Strong Text</b>",
        expected_type=blocks.Paragraph,
        expected_text="Strong Text",
    )

    text = block("rich_text")

    assert len(text) == 1
    check_style(text[0], bold=True)


def test_emphasis_text():
    """Confirm support for emphasized/italic text."""

    block = check_single_block(
        html="<i>Emphasis Text</i>",
        expected_type=blocks.Paragraph,
        expected_text="Emphasis Text",
    )

    text = block("rich_text")

    assert len(text) == 1
    check_style(text[0], italic=True)


def test_table_data():
    """Confirm support for basic table data."""

    check_table_data(
        html="<table><tr><td>Datum</td></tr></table>",
        expected=[["Datum"]],
    )


def test_empty_table_cells():
    """Confirm support for empty table cells."""

    check_table_data(
        html="<table><tr><td></td></tr></table>",
        expected=[[""]],
    )


def test_table_cell_with_div():
    """Confirm support for table cells with `<div>` elements."""

    check_table_data(
        html="<table><tr><td><div>hidden DATA</div></td></tr></table>",
        expected=[["hidden DATA"]],
    )
