from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from pydantic import HttpUrl

from ultimate_notion.adapters.google.tasks import GTask, GTaskList, GTasksClient


@pytest.fixture
def mock_resource():
    resource = Mock()  # spec=Resource makes no sense since it's a dynamically generated class
    return resource


@pytest.fixture
def mock_gtasklist(mock_resource: Mock):
    return GTaskList(
        mock_resource,
        id='tasklist_id',
        title='Task List',
        etag='etag_value',
        kind='tasks#taskList',
        updated='2023-12-31T23:24:45.139Z',
        selfLink='https://example.com/tasklist',
    )


def test_gtask_init(mock_resource: Mock):
    data = {
        'id': 'task_id',
        'title': 'Task Title',
        'etag': 'etag_value',
        'kind': 'tasks#task',
        'updated': '2023-12-31T23:24:45.139Z',
        'selfLink': 'https://example.com/task',
    }
    task = GTask(mock_resource, **data)
    assert task.id == data['id']
    assert task.title == data['title']
    assert task.etag == data['etag']
    assert task.kind == data['kind']
    assert task.updated == datetime.strptime(data['updated'], '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc)
    assert task.self_link == HttpUrl(data['selfLink'])


def test_gtasklist_init(mock_resource: Mock):
    data = {
        'id': 'tasklist_id',
        'title': 'Task List Title',
        'etag': 'etag_value',
        'kind': 'tasks#taskList',
        'updated': '2023-12-31T23:24:45.139Z',
        'selfLink': 'https://example.com/tasklist',
    }
    tasklist = GTaskList(mock_resource, **data)
    assert tasklist.id == data['id']
    assert tasklist.title == data['title']
    assert tasklist.etag == data['etag']
    assert tasklist.kind == data['kind']
    assert tasklist.updated == datetime.strptime(data['updated'], '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc)
    assert tasklist.self_link == HttpUrl(data['selfLink'])


def test_gtasklist_delete(mock_resource: Mock, mock_gtasklist: GTaskList):
    mock_gtasklist.delete()
    mock_resource.tasklists.return_value.delete.assert_called_once_with(tasklist='tasklist_id')


def test_gtasklist_get_tasks(mock_resource: Mock):
    mock_resource.tasks.return_value.list.return_value.execute.return_value = {
        'items': [
            {
                'id': 'task_id',
                'title': 'Task 1',
                'etag': 'etag_value',
                'kind': 'tasks#task',
                'updated': '2023-12-31T23:24:45.139Z',
                'selfLink': 'https://example.com/task1',
            },
            {
                'id': 'task_id_2',
                'title': 'Task 2',
                'etag': 'etag_value_2',
                'kind': 'tasks#task',
                'updated': '2023-12-31T23:24:45.139Z',
                'selfLink': 'https://example.com/task2',
            },
        ]
    }
    tasklist = GTaskList(
        mock_resource,
        id='tasklist_id',
        title='Task List',
        etag='etag_value',
        kind='tasks#taskList',
        updated='2023-12-31T23:24:45.139Z',
        selfLink='https://example.com/tasklist',
    )
    tasks = tasklist.all_tasks()
    assert len(tasks) == 2
    assert isinstance(tasks[0], GTask)
    assert isinstance(tasks[1], GTask)


def test_gtasksclient_all_tasklists(mock_resource: Mock):
    mock_resource.tasklists.return_value.list.return_value.execute.return_value = {
        'items': [
            {
                'id': 'tasklist_id',
                'title': 'Task List 1',
                'etag': 'etag_value',
                'kind': 'tasks#taskList',
                'updated': '2023-12-31T23:24:45.139Z',
                'selfLink': 'https://example.com/tasklist1',
            },
            {
                'id': 'tasklist_id_2',
                'title': 'Task List 2',
                'etag': 'etag_value_2',
                'kind': 'tasks#taskList',
                'updated': '2023-12-31T23:24:45.139Z',
                'selfLink': 'https://example.com/tasklist2',
            },
        ]
    }
    client = GTasksClient()
    client.resource = mock_resource
    tasklists = client.all_tasklists()
    assert len(tasklists) == 2
    assert isinstance(tasklists[0], GTaskList)
    assert isinstance(tasklists[1], GTaskList)
