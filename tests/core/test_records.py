"""Unit tests for Notional records."""

import pytest

from ultimate_notion.core import blocks, schema, types
from ultimate_notion.core.text import plain_text

from ..utils import mktitle


def iterate_blocks(notion, parent, include_children=False):
    """Iterate over all blocks on a page, including children if specified."""
    for block in notion.blocks.children.list(parent=parent):
        yield block

        if block.has_children and include_children:
            for child in iterate_blocks(notion, block, include_children=True):
                yield child


def find_block_on_page(notion, parent, block_id):
    """Find a block on the given page using its ID."""

    for child in iterate_blocks(notion, parent):
        if child.id == block_id:
            return child

    return None


def confirm_blocks(notion, parent, *blocks):
    """Confirm the expected blocks in a given page."""

    num_blocks = 0

    for block in iterate_blocks(notion, parent):
        expected = blocks[num_blocks]
        assert type(block) == type(expected)
        num_blocks += 1

    assert num_blocks == len(blocks)


@pytest.mark.vcr()
def test_iterate_page_blocks(notion, test_area):
    """Iterate over all blocks on the test page and its descendants.

    This is mostly to ensure we do not encounter errors when mapping blocks.  To
    make this effective, the test page should include many different block types.
    """

    for _ in iterate_blocks(notion, test_area):
        pass


@pytest.mark.vcr()
def test_create_empty_page(notion, blank_page):
    """Create an empty page and confirm its contents."""

    new_page = notion.pages.retrieve(blank_page.id)
    assert blank_page == new_page

    num_children = 0

    for _ in notion.blocks.children.list(new_page):
        num_children += 1

    assert num_children == 0, f"found {num_children} unexpected item(s) in result set"


@pytest.mark.vcr()
def test_create_simple_page(notion, test_area):
    """Make sure we can create a page with children."""

    children = [
        blocks.Heading1["Welcome to the Matrix"],
        blocks.Divider(),
        blocks.Paragraph["There is no spoon..."],
    ]

    page = notion.pages.create(
        parent=test_area,
        title=mktitle(),
        children=children,
    )

    confirm_blocks(notion, page, *children)

    notion.pages.delete(page)


@pytest.mark.vcr()
def test_restore_page(notion, blank_page):
    """Create / delete / restore a page.

    This method will pull a fresh copy of the page each time to ensure that the
    metadata is updated properly.
    """

    assert not blank_page.archived

    notion.pages.delete(blank_page)
    deleted = notion.pages.retrieve(blank_page.id)
    assert deleted.archived

    notion.pages.restore(deleted)
    restored = notion.pages.retrieve(blank_page.id)
    assert not restored.archived


@pytest.mark.vcr()
def test_page_icon(notion, blank_page):
    """Set a page icon and confirm."""
    assert blank_page.icon is None

    snowman = types.EmojiObject["☃️"]
    notion.pages.set(blank_page, icon=snowman)

    winter = notion.pages.retrieve(blank_page.id)
    assert winter.icon == snowman


@pytest.mark.vcr()
def test_page_cover(notion, blank_page):
    """Set a page cover and confirm."""
    assert blank_page.cover is None

    loved = types.ExternalFile["https://raw.githubusercontent.com/jheddings/notional/main/tests/data/loved.png"]
    notion.pages.set(blank_page, cover=loved)

    covered = notion.pages.retrieve(blank_page.id)
    assert covered.cover == loved


@pytest.mark.vcr()
def test_create_database(notion, blank_db):
    """Create a database and confirm its contents."""

    # make sure the schema has exactly 1 entry
    assert len(blank_db.properties) == 1

    new_db = notion.databases.retrieve(blank_db.id)
    assert blank_db == new_db

    num_children = 0

    for _ in notion.blocks.children.list(new_db):
        num_children += 1

    assert num_children == 0, f"found {num_children} unexpected item(s) in result set"


@pytest.mark.vcr()
def test_restore_database(notion, blank_db):
    """Delete a database, then restore it."""
    notion.databases.delete(blank_db)
    deleted = notion.databases.retrieve(blank_db.id)
    assert deleted.archived

    notion.databases.restore(deleted)
    restored = notion.databases.retrieve(blank_db.id)
    assert not restored.archived


@pytest.mark.vcr()
def test_update_schema(notion, blank_db):
    """Create a simple database and update the schema."""

    props = {
        "Name": schema.Title(),
        "Index": schema.Number(),
        "Notes": schema.RichText(),
        "Complete": schema.Checkbox(),
        "Due Date": schema.Date(),
        "Tags": schema.MultiSelect(),
    }

    notion.databases.update(
        blank_db,
        title="Improved Database",
        schema=props,
    )

    improved_db = notion.databases.retrieve(blank_db.id)

    assert plain_text(*improved_db.title) == "Improved Database"
    assert len(improved_db.properties) == len(props)
