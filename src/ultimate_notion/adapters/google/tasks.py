"""Client for Google Tasks API.

Follow this quickstart guide to enalbe the API and create the necessary credentials:
https://developers.google.com/tasks/quickstart/python

Official API documentation: https://googleapis.github.io/google-api-python-client/docs/dyn/tasks_v1.html
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from ultimate_notion.config import Config, get_or_create_cfg


class Scope(str, Enum):
    # Allows read-only access to Google Tasks
    TASKS_RO = 'https://www.googleapis.com/auth/tasks.readonly'
    # Allows read/write access to Google Tasks
    TASKS_RW = 'https://www.googleapis.com/auth/tasks'


class Link(BaseModel):
    """Representation of a link in a Google Task."""

    model_config = ConfigDict(extra='forbid')
    description: str
    Link: HttpUrl
    type: str  # noqa: A003


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

    model_config = ConfigDict(extra='forbid')

    id: str  # noqa: A003
    title_: str = Field(..., alias='title')
    kind: Kind
    etag: str
    updated: datetime
    self_link: HttpUrl = Field(..., alias='selfLink')
    _resource: Resource

    def __init__(self, resource: Resource, **data: str):
        super().__init__(**data)
        self._resource = resource

    def __eq__(self, other: object) -> bool:
        if isinstance(other, GObject):
            return self.kind == self.kind and self.id == other.id
        else:
            return NotImplemented

    def __hash__(self) -> int:
        return hash(self.id)

    def _update(self, resp: dict[str, str]):
        """Updates this object with the given response from the API."""
        new_obj_dct = dict(resp, resource=self._resource)
        new_obj = self.model_validate(new_obj_dct)

        for k in new_obj.model_dump(by_alias=False):
            setattr(self, k, getattr(new_obj, k))


class GTask(GObject):
    """Representation of a Google Task."""

    model_config = ConfigDict(extra='forbid')

    kind: Literal[Kind.TASK]
    completed_at: datetime | None = Field(alias='completed', default=None)
    is_deleted: bool = Field(alias='deleted', default=False)
    due: datetime | None = None
    notes_: str | None = Field(alias='notes', default=None)
    parent_id: str | None = Field(alias='parent', default=None)
    position_: str = Field(alias='position')
    status: Status = Status.NEEDS_ACTION
    links: list[Link] | None = None

    @property
    def tasklist_id(self) -> str:
        """Returns the task list this task belongs to."""
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
    def notes(self) -> str | None:
        """Returns the notes of this task."""
        return self.notes_

    @notes.setter
    def notes(self, new_notes: str | None):
        """Sets the notes of this task."""
        resource = self._resource.tasks()
        resp = resource.patch(tasklist=self.tasklist_id, task=self.id, body={'notes': new_notes}).execute()
        self._update(resp)

    @property
    def title(self) -> str:
        """Returns the title of this task."""
        return self.title_

    @title.setter
    def title(self, new_title: str):
        """Sets the title of this task."""
        resource = self._resource.tasks()
        resp = resource.patch(tasklist=self.tasklist_id, task=self.id, body={'title': new_title}).execute()
        self._update(resp)

    @property
    def completed(self) -> bool:
        """Returns whether this task is completed."""
        return self.status == Status.COMPLETED

    @completed.setter
    def completed(self, completed: bool):
        """Sets the completed status of this task."""
        resource = self._resource.tasks()
        resp = resource.patch(
            tasklist=self.tasklist_id,
            task=self.id,
            body={'status': Status.COMPLETED if completed else Status.NEEDS_ACTION},
        ).execute()
        self._update(resp)
        return self

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
    def parent(self, parent: GTask | None):
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

    def all_tasks(self, max_results: int | None = None) -> list[GTask]:
        """Returns a list of all tasks in this task list."""
        resource = self._resource.tasks()
        page_token = None
        tasks = []

        while True:
            results = resource.list(tasklist=self.id, maxResults=max_results, pageToken=page_token).execute()
            items = results.get('items', [])
            tasks.extend([GTask(resource=self._resource, **item) for item in items])

            page_token = results.get('nextPageToken')
            if not page_token:
                break

        return tasks

    def get_task(self, task_id: str) -> GTask:
        """Returns the task with the given ID."""
        resource = self._resource.tasks()
        task = resource.get(tasklist=self.id, task=task_id).execute()
        return GTask(resource=self._resource, **task)

    def create_task(self, title: str) -> GTask:
        """Creates a new task."""
        resource = self._resource.tasks()
        task = resource.insert(tasklist=self.id, body={'title': title}).execute()
        return GTask(resource=self._resource, **task)

    def delete(self):
        """Deletes this task list."""
        resource = self._resource.tasklists()
        resource.delete(tasklist=self.id).execute()
        # We return None as the object is deleted

    @property
    def title(self) -> str:
        """Returns the title of this task list."""
        return self.title_

    @title.setter
    def title(self, new_title: str):
        """Sets the title of this task list."""
        resource = self._resource.tasklists()
        resp = resource.patch(tasklist=self.id, body={'title': new_title}).execute()
        self._update(resp)

    def clear(self) -> GTaskList:
        """Clears all completed tasks in this task list."""
        resource = self._resource.tasks()
        resource.clear(tasklist=self.id).execute()
        return self

    def reload(self) -> GTaskList:
        """Reloads this task list from the API."""
        resource = self._resource.tasklists()
        resp = resource.get(tasklist=self.id).execute()
        self._update(resp)
        return self


class GTasksClient:
    """Google API to easily handle Google Tasks.

    By default, only the least permissive scope `TASKS_RO` in case of `read_only = True` is used.
    """

    def __init__(self, config: Config | None = None, *, read_only: bool = True):
        self.read_only = read_only
        self._scopes = [Scope.TASKS_RO.value] if read_only else [Scope.TASKS_RW.value]
        if config is None:
            config = get_or_create_cfg()
        self._config = config
        self.resource = self._build_resource()

    def _build_resource(self) -> Resource:
        if self._config.gtasks is None:
            msg = 'Configurtion has no `gtasks` section!'
            raise RuntimeError(msg)
        if (secret_path := self._config.gtasks.client_secret_json) is None:
            msg = 'You have to set gtasks.client_secret_json in your config.toml!'
            raise RuntimeError(msg)
        if (token_path := self._config.gtasks.token_json) is None:
            msg = 'You have to set gtasks.token_json in your config.toml!'
            raise RuntimeError(msg)
        if not secret_path.exists():
            msg = f'File {secret_path} does not exist!'
            raise RuntimeError(msg)

        creds = Credentials.from_authorized_user_file(token_path, self._scopes) if token_path.exists() else None
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(secret_path, self._scopes)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open(token_path, 'w', encoding='utf8') as token:
                token.write(creds.to_json())

        return build('tasks', 'v1', credentials=creds)

    def recreate_token(self):
        """Recreate the current token using the scopes given at initialization."""
        self._config.gtasks.token_json.unlink(missing_ok=True)
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

    def get_tasklist(self, tasklist_id: str) -> GTaskList:
        """Returns the task list with the given ID."""
        tasklist = self.resource.tasklists().get(tasklist=tasklist_id).execute()
        return GTaskList(resource=self.resource, **tasklist)

    def create_tasklist(self, title: str) -> GTaskList:
        """Creates a new task list."""
        tasklist = self.resource.tasklists().insert(body={'title': title}).execute()
        return GTaskList(resource=self.resource, **tasklist)
