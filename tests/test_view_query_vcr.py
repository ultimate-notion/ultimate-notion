"""Replay a full saved view query against recorded Notion responses."""

import pytest

from tests._views_vcr import normalize_test_root_response
from tests.conftest import TESTS_PAGE
from ultimate_notion import Option, PropType, Schema, Session, ViewType

pytestmark = pytest.mark.vcr(before_record_response=normalize_test_root_response, decode_compressed_response=True)


@pytest.fixture(autouse=True)
def notion_cleanups() -> None:
    """Use the test's own cleanup for its temporary page."""


def test_view_query_round_trip() -> None:
    class Tasks(Schema):
        task = PropType.Title('Task')
        queue = PropType.Select('Queue', options=[Option('Open'), Option('Closed')])

    with Session() as notion:
        root = notion.search_page(TESTS_PAGE, exact=True).item()
        parent = notion.create_page(root, title='Saved view query test')
        try:
            source = notion.create_ds(parent, schema=Tasks, title='View query rows')
            alpha = source.create_page(task='Alpha', queue='Open')
            bravo = source.create_page(task='Bravo', queue='Open')
            source.create_page(task='Excluded', queue='Closed')
            view = notion.create_view(
                notion.get_db(source.database_id),
                name='Open tasks',
                view_type=ViewType.TABLE,
                data_source=source,
                filter={'property': 'Queue', 'select': {'equals': 'Open'}},
                sorts=[{'property': 'Task', 'direction': 'ascending'}],
            )
            query = view.query(page_size=1)
            try:
                assert query.total_count == 2
                assert [row.id for row in query.results] == [alpha.id]
                assert query.next_cursor is not None
                second = view.query_results(query.id, start_cursor=query.next_cursor, page_size=1)
                assert [row.id for row in second.results] == [bravo.id]
                assert not second.has_more
            finally:
                view.delete_query(query.id)
        finally:
            parent.delete()
