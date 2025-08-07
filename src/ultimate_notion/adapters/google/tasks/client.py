"""Client for Google Tasks API.

Follow this quickstart guide to enable the API and create the necessary credentials:
https://developers.google.com/tasks/quickstart/python

Official Python API documentation: https://googleapis.github.io/google-api-python-client/docs/dyn/tasks_v1.html
Official REST documentation: https://developers.google.com/tasks/reference/rest

!!! danger
    The Google Task API does not support setting time information for due dates.
    Thus, the time information of a datetime object is truncated and a pure date is obtained.
    https://issuetracker.google.com/issues/128979662
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime, time, timezone
from enum import Enum
from types import TracebackType
from typing import Any, Literal

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from ultimate_notion.config import Config, get_or_create_cfg
from ultimate_notion.utils import SList, is_stable_release

DEFAULT_LIST_ID_LEN = 32
"""Length of the ID of the Google default tasklist."""
MAX_RESULTS_PER_PAGE = 100
"""Maximum number of results per page when fetching all tasks."""


class Scope(str, Enum):
    TASKS_RO = 'https://www.googleapis.com/auth/tasks.readonly'
    """Allows read-only access to Google Tasks"""
    TASKS_RW = 'https://www.googleapis.com/auth/tasks'
    """Allows read/write access to Google Tasks"""


class Link(BaseModel):
    """Representation of a link in a Google Task."""

    model_config = ConfigDict(extra='ignore' if is_stable_release() else 'forbid')
    description: str
    Link: HttpUrl
    type: str


class Status(str, Enum):
    """Representation of the different statuses of a Google Task."""

    NEEDS_ACTION = 'needsAction'
    COMPLETED = 'completed'


class Kind(str, Enum):
    """Representation of the different kinds of Google Objects."""

    TASK = 'tasks#task'
    TASK_LIST = 'tasks#taskList'


class GObject(BaseModel):
    """Representation of a general Google Object from the Tasks API."""

    model_config = ConfigDict(extra='ignore' if is_stable_release() else 'forbid')

    id: str  # A003
    title_: str = Field(..., alias='title')
    kind: Kind
    etag: str
    updated: datetime
    self_link: HttpUrl = Field(..., alias='selfLink')
    _resource: Resource

    def __init__(self, resource: Resource, **data: Any) -> None:
        super().__init__(**data)
        self._resource = resource

    def __eq__(self, other: object) -> bool:
        if isinstance(other, GObject):
            return self.kind == self.kind and self.id == other.id
        else:
            return NotImplemented

    def __hash__(self) -> int:
        return hash(self.id)

    def _update(self, resp: dict[str, str]) -> None:
        """Updates this object with the given response from the API."""
        new_obj_dct = dict(resp, resource=self._resource)
        new_obj = self.model_validate(new_obj_dct)

        for k in new_obj.model_dump(by_alias=False):
            setattr(self, k, getattr(new_obj, k))


class GTask(GObject):
    """Representation of a Google Task."""

    kind: Literal[Kind.TASK]  # ToDo: This is nonsense, replace with proper generic
    completed_at: datetime | None = Field(alias='completed', default=None)
    is_deleted: bool = Field(alias='deleted', default=False)
    hidden: bool = False
    due_: datetime | None = Field(alias='due', default=None)
    notes_: str | None = Field(alias='notes', default=None)
    parent_id: str | None = Field(alias='parent', default=None)
    position_: str = Field(alias='position')
    status: Status = Status.NEEDS_ACTION
    links: list[Link] | None = None
    web_view_link: HttpUrl = Field(alias='webViewLink')

    @property
    def tasklist_id(self) -> str:
        """Returns the task list this task belongs to."""
        if self.self_link.path is None:
            msg = 'selfLink has no path to determine the id of the tasklist!'
            raise RuntimeError(msg)

        url_paths = self.self_link.path.split('/')
        if url_paths[3] != 'lists':
            msg = f'Unexpected URL path: {self.self_link.path}'
            raise RuntimeError(msg)
        return url_paths[4]

    @property
    def tasklist(self) -> GTaskList:
        """Returns the task list this task belongs to."""
        tasklist = self._resource.tasklists().get(tasklist=self.tasklist_id).execute()
        return GTaskList(resource=self._resource, **tasklist)

    def delete(self) -> GTask:
        """Deletes this task."""
        resource = self._resource.tasks()
        resource.delete(tasklist=self.tasklist_id, task=self.id).execute()
        resp = resource.get(tasklist=self.tasklist_id, task=self.id).execute()
        self._update(resp)
        return self

    @property
    def due(self) -> datetime | None:
        """Returns the due date of this task."""
        return self.due_

    @due.setter
    def due(self, due_date: datetime | date | None) -> None:
        """Sets the due date of this task."""
        due_date = assert_datetime(due_date)
        due_date_str = due_date if due_date is None else due_date.isoformat()
        resource = self._resource.tasks()
        resp = resource.patch(tasklist=self.tasklist_id, task=self.id, body={'due': due_date_str}).execute()
        self._update(resp)

    @property
    def notes(self) -> str | None:
        """Returns the notes of this task."""
        return self.notes_

    @notes.setter
    def notes(self, new_notes: str | None) -> None:
        """Sets the notes of this task."""
        resource = self._resource.tasks()
        resp = resource.patch(tasklist=self.tasklist_id, task=self.id, body={'notes': new_notes}).execute()
        self._update(resp)

    @property
    def title(self) -> str:
        """Returns the title of this task."""
        return self.title_

    @title.setter
    def title(self, new_title: str) -> None:
        """Sets the title of this task."""
        resource = self._resource.tasks()
        resp = resource.patch(tasklist=self.tasklist_id, task=self.id, body={'title': new_title}).execute()
        self._update(resp)

    @property
    def is_completed(self) -> bool:
        """Returns whether this task is completed."""
        return self.status == Status.COMPLETED

    @is_completed.setter
    def is_completed(self, completed: bool) -> None:
        """Sets the completed status of this task."""
        resource = self._resource.tasks()
        resp = resource.patch(
            tasklist=self.tasklist_id,
            task=self.id,
            body={'status': Status.COMPLETED if completed else Status.NEEDS_ACTION},
        ).execute()
        self._update(resp)

    @property
    def position(self) -> int:
        """Returns the position of this task."""
        return int(self.position_)

    def position_after(self, previous: GTask | None = None) -> GTask:
        """Moves this task to the behind the given task."""
        previous_id = None if previous is None else previous.id
        resource = self._resource.tasks()
        resp = resource.move(tasklist=self.tasklist_id, task=self.id, previous=previous_id).execute()
        self._update(resp)
        return self

    @property
    def parent(self) -> GTask | None:
        """Returns the parent task of this task."""
        if self.parent_id is None:
            return None
        resource = self._resource.tasks()
        resp = resource.get(tasklist=self.tasklist_id, task=self.parent_id).execute()
        return GTask(resource=self._resource, **resp)

    @parent.setter
    def parent(self, parent: GTask | None) -> None:
        """Sets the parent of this task."""
        parent_id = None if parent is None else parent.id

        resource = self._resource.tasks()
        resp = resource.move(tasklist=self.tasklist_id, task=self.id, parent=parent_id).execute()
        self._update(resp)

    @property
    def children(self) -> list[GTask]:
        """Returns the children of this task."""
        return [task for task in self.tasklist.all_tasks() if task.parent_id == self.id]

    def reload(self) -> GTask:
        """Reloads this task from the API."""
        resource = self._resource.tasks()
        resp = resource.get(tasklist=self.tasklist_id, task=self.id).execute()
        self._update(resp)
        return self


class GTaskList(GObject):
    """Representation of a Google Task List."""

    kind: Literal[Kind.TASK_LIST]

    def all_tasks(self, *, show_deleted: bool = False) -> list[GTask]:
        """Returns a list of all tasks, completed or not, in this task list."""
        resource = self._resource.tasks()
        page_token = None
        tasks = []

        while True:
            results = resource.list(
                tasklist=self.id,
                maxResults=MAX_RESULTS_PER_PAGE,
                pageToken=page_token,
                showCompleted=True,
                showHidden=True,
                showDeleted=show_deleted,
            ).execute()
            items = results.get('items', [])
            tasks.extend([GTask(resource=self._resource, **item) for item in items])

            page_token = results.get('nextPageToken')
            if page_token is None:
                break

        return tasks

    def __iter__(self) -> Iterator[GTask]:  # type: ignore[override]
        """Returns an iterator over all tasks in this task list."""
        yield from self.all_tasks()

    def __len__(self) -> int:
        """Return the number of tasks in this task list."""
        return len(self.all_tasks())

    @property
    def is_empty(self) -> bool:
        """Is this task list empty?"""
        return len(self) == 0

    def __bool__(self) -> bool:
        """Overwrite default behaviour."""
        msg = 'Use .is_empty instead of bool(task_list) to check if a task list is empty.'
        raise RuntimeError(msg)

    def get_task(self, task_id: str) -> GTask:
        """Returns the task with the given ID."""
        resource = self._resource.tasks()
        task = resource.get(tasklist=self.id, task=task_id).execute()
        return GTask(resource=self._resource, **task)

    def create_task(self, title: str, due: date | datetime | None = None) -> GTask:
        """Creates a new task."""
        due = assert_datetime(due)
        resource = self._resource.tasks()
        body = {'title': title}
        if due is not None:
            body['due'] = due.isoformat()
        task = resource.insert(tasklist=self.id, body=body).execute()
        return GTask(resource=self._resource, **task)

    @property
    def is_default(self) -> bool:
        """Is this the default task list?"""
        return len(self.id) == DEFAULT_LIST_ID_LEN

    def delete(self) -> None:
        """Deletes this task list."""
        if len(self.id) == DEFAULT_LIST_ID_LEN:
            msg = 'This is the default tasklist and thus cannot be deleted!'
            raise RuntimeError(msg)
        resource = self._resource.tasklists()
        resource.delete(tasklist=self.id).execute()
        # We return None as the object is deleted

    @property
    def title(self) -> str:
        """Returns the title of this task list."""
        return self.title_

    @title.setter
    def title(self, new_title: str) -> None:
        """Sets the title of this task list."""
        resource = self._resource.tasklists()
        resp = resource.patch(tasklist=self.id, body={'title': new_title}).execute()
        self._update(resp)

    def reload(self) -> GTaskList:
        """Reloads this task list from the API."""
        resource = self._resource.tasklists()
        resp = resource.get(tasklist=self.id).execute()
        self._update(resp)
        return self


class GTasksClient:
    """Google API to easily handle Google Tasks."""

    read_only: bool
    _scopes: list[str]
    _config: Config
    resource: Resource

    def __init__(self, config: Config | None = None, *, read_only: bool = False) -> None:
        self.read_only = read_only
        self._scopes = [Scope.TASKS_RO.value] if read_only else [Scope.TASKS_RW.value]
        if config is None:
            config = get_or_create_cfg()
        self._config = config
        self.resource = self._build_resource()

    def _build_resource(self) -> Resource:
        if self._config.google is None:
            msg = 'Configurtion has no `google` section!'
            raise RuntimeError(msg)
        if (secret_path := self._config.google.client_secret_json) is None:
            msg = 'You have to set google.client_secret_json in your config.toml!'
            raise RuntimeError(msg)
        if (token_path := self._config.google.token_json) is None:
            msg = 'You have to set google.token_json in your config.toml!'
            raise RuntimeError(msg)
        if not secret_path.exists():
            msg = f'File {secret_path} does not exist!'
            raise RuntimeError(msg)

        creds = Credentials.from_authorized_user_file(token_path, self._scopes) if token_path.exists() else None
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except RefreshError as e:
                    msg = f'Error refreshing token. Please delete {token_path} and try again!'
                    raise RuntimeError(msg) from e
            else:
                flow = InstalledAppFlow.from_client_secrets_file(secret_path, self._scopes)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open(token_path, 'w', encoding='utf8') as token:
                token.write(creds.to_json())

        return build('tasks', 'v1', credentials=creds)

    def recreate_token(self) -> None:
        """Recreate the current token using the scopes given at initialization."""
        if (gconfig := self._config.google) and (token_json := gconfig.token_json):
            token_json.unlink(missing_ok=True)
        self.resource = self._build_resource()

    def all_tasklists(self, max_results: int | None = None) -> list[GTaskList]:
        """Returns a list of all task lists."""
        page_token = None
        tasklists = []

        while True:
            results = self.resource.tasklists().list(maxResults=max_results, pageToken=page_token).execute()
            items = results.get('items', [])
            tasklists.extend([GTaskList(resource=self.resource, **item) for item in items])

            page_token = results.get('nextPageToken')
            if not page_token:
                break

        return tasklists

    def get_tasklist(self, tasklist_id: str = '@default') -> GTaskList:
        """Returns the task list with the given ID.

        If no ID is given, the default task list is returned.
        """
        tasklist = self.resource.tasklists().get(tasklist=tasklist_id).execute()
        return GTaskList(resource=self.resource, **tasklist)

    def search_tasklist(self, title: str) -> SList[GTaskList]:
        """Returns the task list with the given title."""
        tasklists = self.all_tasklists()
        return SList(tasklist for tasklist in tasklists if tasklist.title == title)

    def create_tasklist(self, title: str) -> GTaskList:
        """Creates a new task list."""
        tasklist = self.resource.tasklists().insert(body={'title': title}).execute()
        return GTaskList(resource=self.resource, **tasklist)

    def get_or_create_tasklist(self, title: str) -> GTaskList:
        """Returns the task list with the given title or creates it if it doesn't exist yet."""
        tasklists = self.search_tasklist(title)
        if len(tasklists) == 0:
            return self.create_tasklist(title)
        else:
            return tasklists.item()

    def close(self) -> None:
        """Closes the client."""
        self.resource.close()

    def __enter__(self) -> GTasksClient:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None
    ) -> None:
        self.close()


def assert_datetime(dt: date | datetime | None) -> datetime | None:
    """Asserts that the given object is a datetime object or None."""
    match dt:
        case None:
            return None
        case datetime():
            return dt
        case date():
            return datetime.combine(dt, time(tzinfo=timezone.utc))
        case _:
            msg = f'Expected a datetime object or None, but got {type(dt)}!'
            raise TypeError(msg)
