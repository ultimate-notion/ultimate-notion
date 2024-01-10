"""Utilities to sync other services with Notion."""

from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, TypeAlias, TypeVar

from ultimate_notion.config import get_cfg_file

State: TypeAlias = dict[str, Any]

_logger = logging.getLogger(__name__)

all_tasks: set[SyncTask] = set()
"""All tasks that have been created so far."""

Self = TypeVar('Self', bound='SyncTask')


class ConflictMode(str, Enum):
    """Conflict resolution modes."""

    NEWER = 'newer'
    NOTION = 'notion'
    OTHER = 'other'  # any other service than Notion
    ERROR = 'error'


class SyncTask(ABC):
    """A task to be performed during a sync.

    This is an abstract base class to allow for different kinds of sync tasks.
    """

    _run_every_secs: float | None = None
    _in_total_times: int | None = None

    def __init__(
        self, name: str, attr_map: dict[str, str], resolve_conflict: ConflictMode | str = ConflictMode.NEWER
    ) -> None:
        if isinstance(resolve_conflict, str):
            resolve_conflict = ConflictMode(resolve_conflict)

        self.name = name
        self.attr_map = attr_map
        self.resolve_conflict = resolve_conflict
        self.state_path = get_cfg_file().parent / 'sync_states' / f'{name}.json'
        super().__init__()

    def schedule(self: Self) -> Self:
        """Apply the task."""
        all_tasks.add(self)
        return self

    def run_every(self: Self, hours: int = 0, minutes: int = 0, seconds: int = 0) -> Self:
        """Schedule the task to run every so many seconds."""
        self._run_every_secs = timedelta(hours=hours, minutes=minutes, seconds=seconds).total_seconds()
        return self

    def run_once(self: Self) -> Self:
        self._run_every_secs = None
        return self

    def in_total(self: Self, times: int) -> Self:
        """Schedule the task to run a total of so many times."""
        if times <= 0:
            msg = 'times must be positive'
            raise ValueError(msg)
        self._in_total_times = times
        return self

    @abstractmethod
    def get_notion_objects(self: Self) -> list[Any]:
        """Get all Notion objects to sync."""
        raise NotImplementedError()

    @abstractmethod
    def get_other_objects(self: Self) -> list[Any]:
        """Get all other objects to sync."""
        raise NotImplementedError()

    @abstractmethod
    def notion_timestamp(self: Self, obj: Any) -> datetime:
        """Get the timestamp of the Notion object."""
        raise NotImplementedError()

    @abstractmethod
    def other_timestamp(self: Self, obj: Any) -> datetime:
        """Get the timestamp of the other object."""
        raise NotImplementedError()

    @abstractmethod
    def notion_hash(self: Self, obj: Any) -> str:
        """Get the hash of the Notion object for object mapping/linking."""
        raise NotImplementedError()

    @abstractmethod
    def other_hash(self: Self, obj: Any) -> str:
        """Get the hash of the other object for object mapping/linking."""
        raise NotImplementedError()

    @abstractmethod
    def notion_to_dict(self, obj: Any) -> dict[str, Any]:
        """Convert a Notion object to a dictionary."""
        raise NotImplementedError()

    @abstractmethod
    def other_to_dict(self, obj: Any) -> dict[str, Any]:
        """Convert another object to a dictionary."""
        raise NotImplementedError()

    @abstractmethod
    def notion_update_obj(self, obj: Any, attr: str, value: Any) -> None:
        """Set an attribute of the Notion object, e.g. page."""
        raise NotImplementedError()

    @abstractmethod
    def other_update_obj(self, obj: Any, attr: str, value: Any) -> None:
        """Set an attribute of the other object."""
        raise NotImplementedError()

    @abstractmethod
    def notion_delete_obj(self, obj: Any) -> None:
        """Delete the page."""
        raise NotImplementedError()

    @abstractmethod
    def other_delete_obj(self, obj: Any) -> None:
        """Delete the other object."""
        raise NotImplementedError()

    @abstractmethod
    def notion_create_obj(self, **kwargs: Any) -> None:
        """Create a new page."""
        raise NotImplementedError()

    @abstractmethod
    def other_create_obj(self, **kwargs: Any) -> None:
        """Create a new other object."""
        raise NotImplementedError()

    def sync_notion_deleted(self: Self, state: State, notion_objs: dict[str, Any], other_objs: dict[str, Any]) -> State:
        """Sync an object in the state that was deleted in Notion."""
        for obj_hash in state:
            if obj_hash not in notion_objs:
                self.other_delete_obj(other_objs[obj_hash])
                del state[obj_hash]
        return state

    def sync_other_deleted(self: Self, state: State, notion_objs: dict[str, Any], other_objs: dict[str, Any]) -> State:
        """Sync an object in the state that was deleted in the other service."""
        for obj_hash in state:
            if obj_hash not in other_objs:
                self.notion_delete_obj(notion_objs[obj_hash])
                del state[obj_hash]
        return state

    def sync_notion_created(self: Self, state: State, notion_objs: dict[str, Any]) -> State:
        """Sync an object not in the state and created in Notion."""
        for obj_hash, obj in notion_objs.items():
            if obj_hash not in state:
                notion_obj_dct = self.notion_to_dict(obj)
                self.other_create_obj(**notion_obj_dct)
                state[obj_hash] = notion_obj_dct
        return state

    def sync_other_created(self: Self, state: State, other_objs: dict[str, Any]) -> State:
        """Sync an object not in the state and created in other service."""
        for obj_hash, obj in other_objs.items():
            if obj_hash not in state:
                other_obj_dct = self.other_to_dict(obj)
                self.notion_create_obj(**other_obj_dct)
                state[obj_hash] = other_obj_dct
        return state

    def resolve_conflict(self: Self, notion_obj: Any, other_obj: Any, notion_attr: str, other_attr: str) -> Any:
        """Resolve a conflict between two objects on an attribute."""
        notion_obj_dct, other_obj_dct = self.notion_to_dict(notion_obj), self.other_to_dict(other_obj)

        if self.resolve_conflict == ConflictMode.NOTION:
            self.other_update_obj(other_obj, other_attr, notion_obj_dct[notion_attr])
            return notion_obj_dct[notion_attr]
        elif self.resolve_conflict == ConflictMode.OTHER:
            self.notion_update_obj(notion_obj, notion_attr, other_obj_dct[other_attr])
            return other_obj_dct[other_attr]
        elif self.resolve_conflict == ConflictMode.NEWER:
            if self.notion_timestamp(notion_obj) > self.other_timestamp(other_obj):
                self.other_update_obj(other_obj, other_attr, notion_obj_dct[notion_attr])
                return notion_obj_dct[notion_attr]
            else:
                self.notion_update_obj(notion_obj, notion_attr, other_obj_dct[other_attr])
                return other_obj_dct[other_attr]
        else:
            msg = f'Conflict between {notion_obj} and {other_obj} on attribute {other_attr}'
            raise RuntimeError(msg)

    def initial_sync(self: Self, notion_objs: dict[str, Any], other_objs: dict[str, Any]) -> State:
        """Make the initial state.

        This is a two-way sync, i.e. the objects are compared and the differences are resolved.
        """
        state = {}
        common_hashes = set(notion_objs) & set(other_objs)

        for obj_hash in common_hashes:
            state_obj = state[obj_hash] = {}
            notion_obj, other_obj = notion_objs[obj_hash], other_objs[obj_hash]
            notion_obj_dct, other_obj_dct = self.notion_to_dict(notion_obj), self.other_to_dict(other_obj)

            for notion_attr, other_attr in self.attr_map.items():
                if notion_obj_dct[notion_attr] == other_obj_dct[other_attr]:
                    state_obj[notion_attr] = notion_obj_dct[notion_attr]
                else:
                    state_obj[notion_attr] = self.resolve_conflict(notion_obj, other_obj, notion_attr, other_attr)

        return state

    def sync_state_changes(self: Self, state: State, notion_objs: dict[str, Any], other_objs: dict[str, Any]) -> State:
        """Sync changes with respect to the state and update the state.

        This is a three-way sync, i.e. the objects are compared and the differences are resolved.
        """
        for obj_hash, state_obj_dct in state.items():
            notion_obj, other_obj = notion_objs[obj_hash], other_objs[obj_hash]
            notion_obj_dct, other_obj_dct = self.notion_to_dict(notion_obj), self.other_to_dict(other_obj)
            # notion_is_newer = self.notion_timestamp(notion_obj) > self.other_timestamp(other_obj)

            for notion_attr, other_attr in self.attr_map.items():
                if notion_obj_dct[notion_attr] != state_obj_dct[notion_attr] == other_obj_dct[other_attr]:
                    self.other_update_obj(other_obj, other_attr, notion_obj_dct[notion_attr])
                    state_obj_dct[notion_attr] = notion_obj_dct[notion_attr]
                elif notion_obj_dct[notion_attr] == state_obj_dct[notion_attr] != other_obj_dct[other_attr]:
                    self.other_update_obj(other_obj, other_attr, notion_obj_dct[notion_attr])
                    state_obj_dct[notion_attr] = notion_obj_dct[notion_attr]
                elif notion_obj_dct[notion_attr] != state_obj_dct[notion_attr] != other_obj_dct[other_attr]:
                    state_obj_dct[notion_attr] = self.resolve_conflict(notion_obj, other_obj, notion_attr, other_attr)

        return state

    def sync(self: Self, state: State | None = None) -> State:
        """The actual sync operation.

        The state holds the synched objects and their attributes as a dictionary of Notion attributes.
        """
        notion_objs = {self.notion_hash(obj): obj for obj in self.get_notion_objects()}
        other_objs = {self.other_hash(obj): obj for obj in self.get_other_objects()}

        if state is None:
            state = self.initial_sync(notion_objs, other_objs)
        else:
            state = self.sync_notion_deleted(state, notion_objs, other_objs)
            state = self.sync_other_deleted(state, notion_objs, other_objs)
            state = self.sync_state_changes(state, notion_objs, other_objs)

        state = self.sync_notion_created(state, notion_objs)
        state = self.sync_other_created(state, other_objs)

        return state

    def __await__(self):
        # Delegate the await to the __call__ method
        return self().__await__()

    async def __call__(self: Self):
        """Run the task."""
        while True:
            with open(str(self.state_path), 'w', encoding='utf8') as state_file:
                state = json.load(state_file) if state_file else None

                new_state = self.sync(state)
                json.dump(new_state, state_file)

            if self._in_total_times is not None:
                self._in_total_times -= 1
                if self._in_total_times <= 0:
                    break

            if self._run_every_secs is not None:
                await asyncio.sleep(self._run_every_secs)

            if self._run_every_secs is None and self._in_total_times is None:
                break


def run_all_tasks(*, debug: bool | None = None):
    """Run all scheduled tasks."""

    async def gather_all_tasks():
        return await asyncio.gather(*all_tasks)

    _logger.info('Running all scheduled tasks...')
    asyncio.run(gather_all_tasks(), debug=debug)
