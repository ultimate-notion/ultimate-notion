from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from tests.conftest import delete_all_taskslists, vcr_fixture
from ultimate_notion.adapters.google.tasks import GTasksClient


@pytest.fixture
def gtasks(custom_config: Path) -> GTasksClient:
    """Returns a GTasksClient instance with read_only=False."""
    return GTasksClient(read_only=False)


@vcr_fixture(scope='module', autouse=True)
def gtasks_cleanups(custom_config: Path) -> None:
    """Clean all Tasklists except of the default one before the tests."""
    delete_all_taskslists()


@pytest.mark.vcr()
def test_gtask_client(gtasks: GTasksClient) -> None:
    new_list = gtasks.create_tasklist('My new tasklist')
    assert new_list.title == 'My new tasklist'

    same_list = gtasks.get_tasklist(new_list.id)
    assert same_list == new_list

    all_lists = gtasks.all_tasklists()
    assert new_list in all_lists

    new_list.delete()


@pytest.mark.vcr()
def test_gtask_tasklist(gtasks: GTasksClient) -> None:
    new_list = gtasks.create_tasklist('My new tasklist')
    assert not new_list.is_default
    new_task = new_list.create_task('My new task')
    assert new_task.title == 'My new task'

    assert new_task in new_list.all_tasks()
    new_task.is_completed = True
    new_task.delete()
    assert new_task not in new_list.all_tasks()

    same_list = gtasks.get_tasklist(new_list.id)
    same_list.title = 'My renamed tasklist'
    assert new_list == same_list
    assert new_list.title != same_list.title
    new_list.reload()
    assert new_list.title == same_list.title

    new_list.delete()

    default_tasklist = gtasks.get_tasklist()
    assert default_tasklist.is_default

    with pytest.raises(RuntimeError):
        default_tasklist.delete()


@pytest.mark.vcr()
def test_gtask_task(gtasks: GTasksClient) -> None:
    new_list = gtasks.create_tasklist('My new tasklist')
    today = datetime(2024, 1, 1, tzinfo=timezone.utc)
    tomorrow = today + timedelta(days=1)
    new_task = new_list.create_task('My new task', due=today)
    assert new_task.title == 'My new task'
    assert new_task.tasklist == new_list
    assert new_task.due is not None
    assert new_task.due.date() == today.date()  # time is not stored in Google Tasks
    new_task.due = tomorrow
    assert new_task.due is not None
    assert new_task.due.date() == tomorrow.date()

    same_task = new_list.get_task(new_task.id)
    same_task.title = 'My renamed task'
    assert new_task == same_task
    assert same_task.title != new_task.title
    new_task.reload()
    assert new_task.title == same_task.title

    new_task.notes = 'My notes'
    assert new_task.notes == 'My notes'

    new_task.is_completed = True
    assert new_task.is_completed

    new_task.position_after(None)
    assert new_task.position == 0
    assert new_task.parent is None
    second_task = new_list.create_task('Second task')
    second_task.position_after(new_task)
    assert second_task.position == 1

    parent_task = new_list.create_task('Parent task')
    assert parent_task.children == []
    new_task.parent = parent_task
    assert new_task.parent == parent_task
    assert parent_task.children == [new_task]
    new_task.parent = None
    assert new_task.parent is None
    assert parent_task.children == []

    new_task.delete()
    assert new_task.is_deleted
    new_list.delete()
