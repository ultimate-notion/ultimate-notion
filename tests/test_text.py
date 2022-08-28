"""Unit tests for text types in Notional."""

import re

from ultimate_notion.core import blocks
from ultimate_notion.core.text import (
    Annotations,
    CodingLanguage,
    TextObject,
    is_emoji,
    markdown,
    plain_text,
)


def confirm_rtf_markdown(plain, md, rtf):
    """Confirm the expected text for the given list of RichTextObject's."""

    if plain is not None:
        assert plain_text(*rtf) == plain

    if md is not None:
        assert markdown(*rtf) == md


def confirm_block_markdown(cls, plain, md):
    """Make sure the block type returns expected markdown for the given text."""
    block = cls[plain]

    if plain is not None:
        assert block.PlainText == plain

    if md is not None:
        assert block.Markdown == md


def test_empty_blocks():
    """Ensure that empty blocks behave."""
    confirm_block_markdown(blocks.Paragraph, "", "")

    confirm_block_markdown(blocks.Heading1, "", "")
    confirm_block_markdown(blocks.Heading2, "", "")
    confirm_block_markdown(blocks.Heading3, "", "")

    confirm_block_markdown(blocks.Quote, "", "")


def test_empty_text():
    """Verify text formatting for empty text."""

    assert TextObject[None] is None


def test_zero_length_text():
    """Verify text formatting for zero-length text."""
    text = TextObject[""]

    assert plain_text(text) == ""
    assert markdown(text) == ""


def test_plain_text():
    """Verify text formatting for plain text."""
    text = TextObject["hello world"]

    assert plain_text(text) == "hello world"
    assert markdown(text) == "hello world"


def test_basic_links():
    """Verify text formatting for basic links."""
    text = TextObject["Search Me", "https://www.google.com/"]

    assert plain_text(text) == "Search Me"
    assert markdown(text) == "[Search Me](https://www.google.com/)"


def test_bold_text():
    """Verify text formatting for bold words."""
    bold = Annotations(bold=True)
    text = TextObject["be BOLD", None, bold]

    assert plain_text(text) == "be BOLD"
    assert markdown(text) == "*be BOLD*"


def test_emphasis_text():
    """Verify text formatting for italic words."""
    style = Annotations(italic=True)
    text = TextObject["suggestive", None, style]

    assert plain_text(text) == "suggestive"
    assert markdown(text) == "**suggestive**"


def test_bold_italic_text():
    """Verify text formatting for bold & italic words."""
    style = Annotations(bold=True, italic=True)
    text = TextObject["really important", None, style]

    assert plain_text(text) == "really important"
    assert markdown(text) == "***really important***"


def test_underline_text():
    """Verify text formatting for underline words."""
    underline = Annotations(underline=True)
    text = TextObject["non-standard", None, underline]

    assert plain_text(text) == "non-standard"
    assert markdown(text) == "_non-standard_"


def test_strikethrough():
    """Verify text formatting for strikethrough text."""
    strike = Annotations(strikethrough=True)
    text = TextObject["canceled", None, strike]

    assert plain_text(text) == "canceled"
    assert markdown(text) == "~canceled~"


def test_code_word():
    """Verify text formatting for code words."""
    code = Annotations(code=True)
    text = TextObject["keyword", None, code]

    assert plain_text(text) == "keyword"
    assert markdown(text) == "`keyword`"


def test_paragraph_block():
    """Create a Paragraph block from text."""
    block = blocks.Paragraph["Lorem ipsum dolor sit amet"]

    assert block.PlainText == "Lorem ipsum dolor sit amet"
    assert block.Markdown == "Lorem ipsum dolor sit amet"


def test_heading_1():
    """Verify text formatting for Heading1 blocks."""
    block = blocks.Heading1["Introduction"]

    assert block.PlainText == "Introduction"
    assert block.Markdown == "# Introduction #"


def test_heading_2():
    """Verify text formatting for Heading2 blocks."""
    block = blocks.Heading2["More Context"]

    assert block.PlainText == "More Context"
    assert block.Markdown == "## More Context ##"


def test_heading_3():
    """Verify text formatting for Heading3 blocks."""
    block = blocks.Heading3["Minor Point"]

    assert block.PlainText == "Minor Point"
    assert block.Markdown == "### Minor Point ###"


def test_bulleted_list_item():
    """Verify text formatting for BulletedListItem blocks."""
    block = blocks.BulletedListItem["point number one"]

    assert block.PlainText == "point number one"
    assert block.Markdown == "- point number one"


def test_numbered_list_item():
    """Verify text formatting for NumberedListItem blocks."""
    block = blocks.NumberedListItem["first priority"]

    assert block.PlainText == "first priority"
    assert block.Markdown == "1. first priority"


def test_quote_block():
    """Verify text formatting for Quote blocks."""
    block = blocks.Quote["Now is the time for all good men..."]

    assert block.PlainText == "Now is the time for all good men..."
    assert block.Markdown == "> Now is the time for all good men..."


def test_divider_block():
    """Create a Divider and check its behavior."""
    div = blocks.Divider()

    assert re.match(r"^([*_-])\1{2,}$", div.Markdown)


def test_todo_block():
    """Verify text formatting for ToDo blocks."""
    block = blocks.ToDo["COMPLETED", True]

    assert block.PlainText == "COMPLETED"
    assert block.Markdown == "- [x] COMPLETED"

    block = blocks.ToDo["INCOMPLETE", False]

    assert block.PlainText == "INCOMPLETE"
    assert block.Markdown == "- [ ] INCOMPLETE"


def test_code_block():
    """Verify text formatting for Code blocks."""
    code = "import sys\nprint('hello world')\nsys.exit(0)"
    block = blocks.Code[code, CodingLanguage.PYTHON]

    assert block.Markdown == f"```python\n{code}\n```"


def test_is_emoji():
    """Test if is_emoji detects single emoji."""
    assert is_emoji("🍟")
    assert not is_emoji("no emoji")
    assert not is_emoji("I love 🍟")
    assert not is_emoji("🍟🍟")
    assert not is_emoji("🍟 is my favourite")
    assert not is_emoji("🍟🍔")
