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

from ultimate_notion.adapters.config import Config, get_cfg


class Scope(str, Enum):
    # Allows read-only access to Google Tasks
    TASKS_RO = 'https://www.googleapis.com/auth/tasks.readonly'
    # Allows read/write access to Google Tasks
    TASKS_RW = 'https://www.googleapis.com/auth/tasks'


class Link(BaseModel):
    """Representation of a link in a Google Task"""

    model_config = ConfigDict(extra='forbid')
    description: str
    Link: HttpUrl
    type: str  # noqa: A003


class GTask(BaseModel):
    """Representation of a Google Task"""

    model_config = ConfigDict(extra='forbid')

    id: str  # noqa: A003
    title: str
    etag: str
    kind: Literal['tasks#task']
    updated: datetime
    self_link: HttpUrl = Field(..., alias='selfLink')
    completed: datetime | None = None
    deleted: bool = False
    due: datetime | None = None
    notes: str | None = None
    parent: str | None = None
    position: str
    status: Literal['needsAction', 'completed'] = 'needsAction'
    links: list[Link] | None = None

    def __init__(self, resource: Resource, **data: str):
        super().__init__(**data)
        self._resource = resource

    def __eq__(self, other: object) -> bool:
        if isinstance(other, GTask):
            return self.id == other.id
        else:
            return NotImplemented

    def __hash__(self) -> int:
        return hash(self.id)

    def _update(self, resp: dict[str, str]):
        """Updates this object with the given response from the API"""
        new_obj_dct = self.model_dump(by_alias=True)
        new_obj_dct.update(resp, resource=self._resource)
        new_obj = self.model_validate(new_obj_dct)

        for k in new_obj.model_dump(by_alias=False):
            setattr(self, k, getattr(new_obj, k))

    @property
    def tasklist_id(self) -> str:
        """Returns the task list this task belongs to"""
        url_paths = self.self_link.path.split('/')
        if url_paths[3] != 'lists':
            msg = f'Unexpected URL path: {self.self_link.path}'
            raise RuntimeError(msg)
        return url_paths[4]

    @property
    def tasklist(self) -> GTaskList:
        """Returns the task list this task belongs to"""
        tasklist = self._resource.tasklists().get(tasklist=self.tasklist_id).execute()
        return GTaskList(resource=self._resource, **tasklist)

    def delete(self) -> GTask:
        """Deletes this task"""
        tasks_resource = self._resource.tasks()
        tasks_resource.delete(tasklist=self.tasklist_id, task=self.id).execute()
        resp = tasks_resource.get(tasklist=self.tasklist_id, task=self.id).execute()
        self._update(resp)
        return self


class GTaskList(BaseModel):
    """Representation of a Google Task List"""

    model_config = ConfigDict(extra='forbid')

    id: str  # noqa: A003
    title: str
    etag: str
    kind: Literal['tasks#taskList']
    updated: datetime
    self_link: HttpUrl = Field(..., alias='selfLink')

    def __init__(self, resource: Resource, **fields: str):
        super().__init__(**fields)
        self._resource = resource

    def __eq__(self, other: object) -> bool:
        if isinstance(other, GTaskList):
            return self.id == other.id
        else:
            return NotImplemented

    def __hash__(self) -> int:
        return hash(self.id)

    def _update(self, resp: dict[str, str]):
        """Updates this object with the given response from the API"""
        new_obj_dct = self.model_dump(by_alias=True)
        new_obj_dct.update(resp, resource=self._resource)
        new_obj = self.model_validate(new_obj_dct)

        for k in new_obj.model_dump(by_alias=False):
            setattr(self, k, getattr(new_obj, k))

    def all_tasks(self, max_results: int | None = None) -> list[GTask]:
        """Returns a list of all tasks in this task list"""
        tasks_resource = self._resource.tasks()
        page_token = None
        tasks = []

        while True:
            results = tasks_resource.list(tasklist=self.id, maxResults=max_results, pageToken=page_token).execute()
            items = results.get('items', [])
            tasks.extend([GTask(resource=self._resource, **item) for item in items])

            page_token = results.get('nextPageToken')
            if not page_token:
                break

        return tasks

    def get_task(self, task_id: str) -> GTask:
        """Returns the task with the given ID"""
        tasks_resource = self._resource.tasks()
        task = tasks_resource.get(tasklist=self.id, task=task_id).execute()
        return GTask(resource=self._resource, **task)

    def create_task(self, title: str) -> GTask:
        """Creates a new task"""
        tasks_resource = self._resource.tasks()
        task = tasks_resource.insert(tasklist=self.id, body={'title': title}).execute()
        return GTask(resource=self._resource, **task)

    def delete(self):
        """Deletes this task list"""
        tasks_resource = self._resource.tasklists()
        tasks_resource.delete(tasklist=self.id).execute()
        # We return None as the object is deleted

    def rename(self, new_title: str) -> GTaskList:
        """Renames this task list"""
        tasks_resource = self._resource.tasklists()
        resp = tasks_resource.patch(tasklist=self.id, body={'title': new_title}).execute()
        self._update(resp)
        return self


class GTasksClient:
    """Google API to easily handle Google Tasks

    By default, only the least permissive scope `TASKS_RO` in case of `read_only = True` is used.
    """

    def __init__(self, config: Config | None = None, *, read_only: bool = True):
        self.read_only = read_only
        self._scopes = [Scope.TASKS_RO.value] if read_only else [Scope.TASKS_RW.value]
        if config is None:
            config = get_cfg()
        self._config = config
        self.resource = self._build_resource()

    def _build_resource(self) -> Resource:
        if self._config.Google is None:
            msg = 'Configurtion has no `Google` section!'
            raise RuntimeError(msg)
        if (secret_path := self._config.Google.client_secret_json) is None:
            msg = 'You have to set Google.client_secret_json in your config.toml!'
            raise RuntimeError(msg)
        if (token_path := self._config.Google.token_json) is None:
            msg = 'You have to set Google.token_json in your config.toml!'
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
        """Recreate the current token using the scopes given at initialization"""
        self._config.Google.token_json.unlink(missing_ok=True)
        self.resource = self._build_resource()

    def all_tasklists(self, max_results: int | None = None) -> list[GTaskList]:
        """Returns a list of all task lists"""
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
        """Returns the task list with the given ID"""
        tasklist = self.resource.tasklists().get(tasklist=tasklist_id).execute()
        return GTaskList(resource=self.resource, **tasklist)

    def create_tasklist(self, title: str) -> GTaskList:
        """Creates a new task list"""
        tasklist = self.resource.tasklists().insert(body={'title': title}).execute()
        return GTaskList(resource=self.resource, **tasklist)
