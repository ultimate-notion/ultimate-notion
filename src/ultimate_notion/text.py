"""Utilities for working text, markdown & Rich Text in Notion."""

import re
from typing import Iterator

from ultimate_notion.objects import RichText, Text, RichTextElem

# this might be a place to capture other utilities for working with markdown, text
# rich text, etc...  the challenge is not importing types due to a circular ref.

# the max text size according to the Notion API is 2000 characters.
MAX_TEXT_OBJECT_SIZE = 2000


# ToDo: Check where this is needed and reimplement in the highest-level
# def plain_text(*rtf):
#     """Return the combined plain text from the list of RichText objects."""
#     return "".join(text.plain_text for text in rtf if text)


def chunky(text: str, length: int = MAX_TEXT_OBJECT_SIZE) -> Iterator[str]:
    """Break the given `text` into chunks of at most `length` size."""
    return (text[idx : idx + length] for idx in range(0, len(text), length))


def rich_text(text: str) -> RichText:
    """Convert markdown text to rich text objects"""

    # ToDo: Actual markdown parsing and interpretation not implemented!
    # This is just a dummy that respects the MAX_TEXT_OBJECT_SIZE
    # No handling of mentions, formula, etc. yet done as well as proper styling with annotations
    # Idea: Markdown parser that creates for each token like "**bold**" or "[link](https://...)"
    # the corresponding RichText Object.

    rich_texts: list[RichTextElem] = []
    for part in chunky(text):
        rich_texts.append(Text(part))

    return RichText(rich_texts)


def make_safe_python_name(name: str) -> str:
    """Make the given string safe for use as a Python identifier.

    This will remove any leading characters that are not valid and change all
    invalid interior sequences to underscore.
    """

    s = re.sub(r"[^0-9a-zA-Z_]+", "_", name)
    s = re.sub(r"^[^a-zA-Z]+", "", s)

    # remove trailing underscores
    return s.rstrip("_")


# ToDo: Get rid of that and make this available in RichTextList.
def plain_text(*rtf):
    """Return the combined plain text from the list of RichText objects."""
    return "".join(text.plain_text for text in rtf if text)
