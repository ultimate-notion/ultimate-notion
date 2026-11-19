"""Replay Status schema creation and updates against recorded Notion responses."""

import pytest

from tests._views_vcr import normalize_test_root_response
from tests.conftest import TESTS_PAGE
from ultimate_notion import Option, PropType, Schema, Session

pytestmark = pytest.mark.vcr(before_record_response=normalize_test_root_response, decode_compressed_response=True)


@pytest.fixture(autouse=True)
def notion_cleanups() -> None:
    """Use the test's own cleanup for its temporary page."""


def test_status_schema_round_trip() -> None:
    class Tasks(Schema):
        task = PropType.Title('Task')
        default_status = PropType.Status('Default status')
        progress = PropType.Status(
            'Progress',
            to_do=[Option('Backlog', color='gray')],
            in_progress=[Option('Review', color='blue')],
            complete=[Option('Done', color='green')],
        )

    with Session() as notion:
        root = notion.search_page(TESTS_PAGE, exact=True).item()
        parent = notion.create_page(root, title='Status schema test')
        try:
            source = notion.create_ds(parent, schema=Tasks, title='Status schema rows')
            default_status = source.schema['Default status']
            progress = source.schema['Progress']
            assert isinstance(default_status, PropType.Status)
            assert isinstance(progress, PropType.Status)
            assert default_status.options
            groups = {group.name: group.options for group in progress.groups}
            assert [option.name for option in groups['In progress']] == ['Review']
            progress.set_options(
                to_do=groups['To-do'], in_progress=[], complete=[*groups['In progress'], *groups['Complete']]
            )
            source.reload()
            updated = source.schema['Progress']
            assert isinstance(updated, PropType.Status)
            by_name = {group.name: {option.name for option in group.options} for group in updated.groups}
            assert by_name['Complete'] == {'Review', 'Done'}
        finally:
            parent.delete()
