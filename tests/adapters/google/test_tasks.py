from __future__ import annotations

import pytest

from ultimate_notion.adapters.google import GTasksClient


@pytest.fixture
def client():
    return GTasksClient(read_only=False)


@pytest.mark.vcr()
def test_gtask_client(client: GTasksClient, custom_config: str):
    new_list = client.create_tasklist('My new tasklist')
    assert new_list.title == 'My new tasklist'

    same_list = client.get_tasklist(new_list.id)
    assert same_list == new_list

    all_lists = client.all_tasklists()
    assert new_list in all_lists

    new_list.delete()


@pytest.mark.vcr()
def test_gtask_tasklist(client: GTasksClient, custom_config: str):
    new_list = client.create_tasklist('My new tasklist')
    new_task = new_list.create_task('My new task')
    assert new_task.title == 'My new task'

    assert new_task in new_list.all_tasks()
    new_task.completed = True
    new_list.clear()
    assert new_task not in new_list.all_tasks()

    same_list = client.get_tasklist(new_list.id)
    same_list.title = 'My renamed tasklist'
    assert new_list == same_list
    assert new_list.title != same_list.title
    new_list.reload()
    assert new_list.title == same_list.title

    new_list.delete()


@pytest.mark.vcr()
def test_gtask_task(client: GTasksClient, custom_config: str):
    new_list = client.create_tasklist('My new tasklist')
    new_task = new_list.create_task('My new task')
    assert new_task.title == 'My new task'
    assert new_task.tasklist == new_list

    same_task = new_list.get_task(new_task.id)
    same_task.title = 'My renamed task'
    assert new_task == same_task
    assert same_task.title != new_task.title
    new_task.reload()
    assert new_task.title == same_task.title

    new_task.notes = 'My notes'
    assert new_task.notes == 'My notes'

    new_task.completed = True
    assert new_task.completed

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
