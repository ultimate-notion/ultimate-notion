"""Utilities to synchronize other services with Notion."""

from __future__ import annotations

import asyncio
import logging
import pickle  # noqa: S403
from abc import ABC, abstractmethod
from collections.abc import Generator
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, TypeAlias

from pydantic import BaseModel, Field
from typing_extensions import Self

from ultimate_notion.config import get_cfg

_logger = logging.getLogger(__name__)

ID: TypeAlias = str


class ConflictMode(str, Enum):
    """Conflict resolution modes."""

    NEWER = 'newer'
    NOTION = 'notion'
    OTHER = 'other'  # any other service than Notion
    ERROR = 'error'


class State(BaseModel):
    """The state of a sync task.

    The state holds the synced objects and their attributes as a dictionary of Notion attributes."""

    ids: dict[ID, ID] = Field(default_factory=dict)
    """Maps Notion object ids to other object ids."""
    objs: dict[ID, dict[str, Any]] = Field(default_factory=dict)
    """Dictionary of Notion objects synced with other service and indexed by their ids."""


class SyncTask(ABC):
    """A task to be performed during a sync.

    This is an abstract base class to allow for different kinds of sync tasks.
    """

    _run_every_secs: float | None = None
    _in_total_times: int | None = None

    def __init__(
        self, name: str, attr_map: dict[str, str], conflict_mode: ConflictMode | str = ConflictMode.NEWER
    ) -> None:
        if isinstance(conflict_mode, str):
            conflict_mode = ConflictMode(conflict_mode)

        self.name = name
        self.attr_map = attr_map
        self.conflict_mode = conflict_mode
        self.state_path = get_cfg().ultimate_notion.sync_state_dir / f'{name}.pickle'
        super().__init__()

    def schedule(self) -> Self:
        """Apply the task."""
        all_tasks.add(self)
        return self

    def run_every(self, hours: int = 0, minutes: int = 0, seconds: int = 0) -> Self:
        """Schedule the task to run every so many seconds."""
        self._run_every_secs = timedelta(hours=hours, minutes=minutes, seconds=seconds).total_seconds()
        return self

    def run_once(self) -> Self:
        self._run_every_secs = None
        return self

    def in_total(self, times: int) -> Self:
        """Schedule the task to run a total of so many times."""
        if times <= 0:
            msg = 'times must be positive'
            raise ValueError(msg)
        self._in_total_times = times
        return self

    @abstractmethod
    def get_notion_objects(self) -> list[Any]:
        """Get all Notion objects to sync."""
        raise NotImplementedError()

    @abstractmethod
    def get_other_objects(self) -> list[Any]:
        """Get all other objects to sync."""
        raise NotImplementedError()

    @abstractmethod
    def notion_timestamp(self, obj: Any) -> datetime:
        """Get the timestamp of the Notion object."""
        raise NotImplementedError()

    @abstractmethod
    def other_timestamp(self, obj: Any) -> datetime:
        """Get the timestamp of the other object."""
        raise NotImplementedError()

    @abstractmethod
    def notion_id(self, obj: Any) -> ID:
        """Get the id of the Notion object."""
        raise NotImplementedError()

    @abstractmethod
    def other_id(self, obj: Any) -> ID:
        """Get the id of the other object."""
        raise NotImplementedError()

    @abstractmethod
    def notion_hash(self, obj: Any) -> str:
        """Get the hash of the Notion object for object mapping/linking."""
        raise NotImplementedError()

    @abstractmethod
    def other_hash(self, obj: Any) -> str:
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
    def notion_create_obj(self, **kwargs: Any) -> Any:
        """Create a new page."""
        raise NotImplementedError()

    @abstractmethod
    def other_create_obj(self, **kwargs: Any) -> Any:
        """Create a new other object."""
        raise NotImplementedError()

    def sync_notion_deleted(self, state: State, notion_objs: dict[ID, Any], other_objs: dict[ID, Any]) -> State:
        """Sync an object in the state that was deleted in Notion."""
        for notion_id, other_id in state.ids.copy().items():
            if notion_id not in notion_objs:
                if other_id in other_objs:
                    _logger.debug(f'Deleting other object with id {other_id}')
                    self.other_delete_obj(other_objs[other_id])
                    del other_objs[other_id]
                del state.ids[notion_id]
                del state.objs[notion_id]
        return state

    def sync_other_deleted(self, state: State, notion_objs: dict[ID, Any], other_objs: dict[ID, Any]) -> State:
        """Sync an object in the state that was deleted in the other service."""
        for notion_id, other_id in state.ids.copy().items():
            if other_id not in other_objs:
                if notion_id in notion_objs:
                    _logger.debug(f'Deleting Notion object with id {notion_id}')
                    self.notion_delete_obj(notion_objs[notion_id])
                    del notion_objs[notion_id]
                del state.ids[notion_id]
                del state.objs[notion_id]
        return state

    def sync_notion_created(self, state: State, notion_objs: dict[ID, Any]) -> State:
        """Sync an object not in the state and created in Notion."""
        for notion_id, notion_obj in notion_objs.items():
            if notion_id not in state.objs:
                notion_obj_dct = self.notion_to_dict(notion_obj)
                other_obj_dct = {
                    other_attr: notion_obj_dct[notion_attr] for notion_attr, other_attr in self.attr_map.items()
                }
                _logger.debug(f'Creating other object with attributes: {other_obj_dct}')
                other_obj = self.other_create_obj(**other_obj_dct)

                if self.other_to_dict(other_obj) != other_obj_dct:
                    msg = 'The other object created by Notion does not match the expected object.'
                    raise RuntimeError(msg)

                other_id = self.other_id(other_obj)
                state.ids[notion_id] = other_id
                state.objs[notion_id] = notion_obj_dct
        return state

    def sync_other_created(self, state: State, other_objs: dict[ID, Any]) -> State:
        """Sync an object not in the state and created in other service."""
        for other_id, other_obj in other_objs.items():
            if other_id not in state.ids.values():
                other_obj_dct = self.other_to_dict(other_obj)
                notion_obj_dct = {
                    notion_attr: other_obj_dct[other_attr] for notion_attr, other_attr in self.attr_map.items()
                }
                _logger.debug(f'Creating Notion object with attributes: {notion_obj_dct}')
                notion_obj = self.notion_create_obj(**notion_obj_dct)

                if self.notion_to_dict(notion_obj) != notion_obj_dct:
                    msg = 'The Notion object created by other service does not match the expected object.'
                    raise RuntimeError(msg)

                notion_id = self.notion_id(notion_obj)
                state.ids[notion_id] = other_id
                state.objs[notion_id] = notion_obj_dct
        return state

    def resolve_conflict(self, notion_obj: Any, other_obj: Any, notion_attr: str, other_attr: str) -> Any:
        """Resolve a conflict between two objects on an attribute."""
        _logger.debug(
            f'Resolving conflict on attribute {notion_attr} of Notion object {self.notion_id(notion_obj)}'
            f'and attribute {other_attr} of other object {self.other_id(other_obj)}.'
        )
        notion_obj_dct, other_obj_dct = self.notion_to_dict(notion_obj), self.other_to_dict(other_obj)

        if self.conflict_mode == ConflictMode.NOTION:
            _logger.debug(f'Updating other object with attribute {other_attr} to {notion_obj_dct[notion_attr]}')
            self.other_update_obj(other_obj, other_attr, notion_obj_dct[notion_attr])
            return notion_obj_dct[notion_attr]
        elif self.conflict_mode == ConflictMode.OTHER:
            _logger.debug(f'Updating Notion object with attribute {notion_attr} to {other_obj_dct[other_attr]}')
            self.notion_update_obj(notion_obj, notion_attr, other_obj_dct[other_attr])
            return other_obj_dct[other_attr]
        elif self.conflict_mode == ConflictMode.NEWER:
            if self.notion_timestamp(notion_obj) > self.other_timestamp(other_obj):
                _logger.debug(f'Updating other object with attribute {other_attr} to {notion_obj_dct[notion_attr]}')
                self.other_update_obj(other_obj, other_attr, notion_obj_dct[notion_attr])
                return notion_obj_dct[notion_attr]
            else:
                _logger.debug(f'Updating Notion object with attribute {notion_attr} to {other_obj_dct[other_attr]}')
                self.notion_update_obj(notion_obj, notion_attr, other_obj_dct[other_attr])
                return other_obj_dct[other_attr]
        else:
            msg = f'Unknown conflict mode {self.conflict_mode}'
            raise RuntimeError(msg)

    def initial_sync(self, notion_objs: dict[ID, Any], other_objs: dict[ID, Any]) -> State:
        """Make the initial state.

        This is a two-way sync, i.e. the objects are compared and the differences are resolved.
        """
        _logger.debug('Performing initial sync...')
        state = State()
        notion_hashes = {self.notion_hash(obj): obj_id for obj_id, obj in notion_objs.items()}
        other_hashes = {self.other_hash(obj): obj_id for obj_id, obj in other_objs.items()}

        for obj_hash in notion_hashes.keys() & other_hashes.keys():
            notion_id, other_id = notion_hashes[obj_hash], other_hashes[obj_hash]

            state.ids[notion_id] = other_id
            state_obj = state.objs[notion_id] = {}

            notion_obj, other_obj = notion_objs[notion_id], other_objs[other_id]
            notion_obj_dct, other_obj_dct = self.notion_to_dict(notion_obj), self.other_to_dict(other_obj)

            for notion_attr, other_attr in self.attr_map.items():
                if notion_obj_dct[notion_attr] == other_obj_dct[other_attr]:
                    state_obj[notion_attr] = notion_obj_dct[notion_attr]
                else:
                    state_obj[notion_attr] = self.resolve_conflict(notion_obj, other_obj, notion_attr, other_attr)

        return state

    def sync_state_changes(self, state: State, notion_objs: dict[ID, Any], other_objs: dict[ID, Any]) -> State:
        """Sync changes with respect to the state and update the state.

        This is a three-way sync, i.e. the objects are compared to the state as base and the differences are resolved.
        """
        _logger.debug('Performing state sync...')
        for notion_id, state_obj_dct in state.objs.items():
            notion_obj, other_obj = notion_objs[notion_id], other_objs[state.ids[notion_id]]
            notion_obj_dct, other_obj_dct = self.notion_to_dict(notion_obj), self.other_to_dict(other_obj)

            for notion_attr, other_attr in self.attr_map.items():
                if notion_obj_dct[notion_attr] != state_obj_dct[notion_attr] == other_obj_dct[other_attr]:
                    _logger.debug(f'Updating other object with attribute {other_attr} to {notion_obj_dct[notion_attr]}')
                    self.other_update_obj(other_obj, other_attr, notion_obj_dct[notion_attr])
                    state_obj_dct[notion_attr] = notion_obj_dct[notion_attr]
                elif notion_obj_dct[notion_attr] == state_obj_dct[notion_attr] != other_obj_dct[other_attr]:
                    _logger.debug(f'Updating Notion object with attribute {notion_attr} to {other_obj_dct[other_attr]}')
                    self.notion_update_obj(notion_obj, notion_attr, other_obj_dct[other_attr])
                    state_obj_dct[notion_attr] = notion_obj_dct[notion_attr]
                elif notion_obj_dct[notion_attr] != state_obj_dct[notion_attr] != other_obj_dct[other_attr]:
                    state_obj_dct[notion_attr] = self.resolve_conflict(notion_obj, other_obj, notion_attr, other_attr)

        return state

    def sync(self, state: State | None) -> State:
        """The actual sync operation.

        The state holds the synced objects and their attributes as a dictionary of Notion attributes.
        """
        notion_objs = {self.notion_id(obj): obj for obj in self.get_notion_objects()}
        other_objs = {self.other_id(obj): obj for obj in self.get_other_objects()}

        if state is None:
            state = self.initial_sync(notion_objs, other_objs)
        else:
            state = self.sync_notion_deleted(state, notion_objs, other_objs)
            state = self.sync_other_deleted(state, notion_objs, other_objs)
            state = self.sync_state_changes(state, notion_objs, other_objs)

        state = self.sync_notion_created(state, notion_objs)
        state = self.sync_other_created(state, other_objs)

        return state

    def __await__(self) -> Generator[Any, None, None]:
        """Delegate the await to the __call__ method"""
        return self().__await__()

    async def __call__(self) -> None:
        """Run the task as scheduled."""
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        state = pickle.loads(self.state_path.read_bytes()) if self.state_path.exists() else None  # noqa: S301

        while True:
            state = self.sync(state)
            self.state_path.write_bytes(pickle.dumps(state))

            if self._in_total_times is not None:
                self._in_total_times -= 1
                if self._in_total_times <= 0:
                    break

            if self._run_every_secs is not None:
                await asyncio.sleep(self._run_every_secs)

            if self._run_every_secs is None and self._in_total_times is None:
                break


all_tasks: set[SyncTask] = set()
"""All tasks that have been created so far."""


def run_all_tasks(*, debug: bool | None = None) -> None:
    """Run all scheduled tasks."""

    async def gather_all_tasks() -> list[Any]:
        return await asyncio.gather(*all_tasks)

    _logger.info('Running all scheduled tasks...')
    asyncio.run(gather_all_tasks(), debug=debug)
