"""Syncs a Notion database with a Google Tasks task list."""
# ruff: noqa: PLR6301

from __future__ import annotations

from datetime import datetime
from typing import Any

from ultimate_notion import Database, Page
from ultimate_notion.adapters.google_tasks.client import GTask, GTaskList
from ultimate_notion.sync import ConflictMode, SyncTask


class SyncGTasks(SyncTask):
    """Syncs a Notion database with a Google Tasks task list."""

    def __init__(
        self,
        *,
        notion_db: Database,
        tasklist: GTaskList,
        completed_attr: str,
        completed_value: Any,
        not_completed_value: Any,
        due_attr: str,
        name: str = 'SyncGTasks',
        resolve_conflict: ConflictMode = ConflictMode.NEWER,
    ):
        self.notion_db = notion_db
        self.tasklist = tasklist
        self.completed_attr = completed_attr
        self.completed_value = completed_value
        self.not_completed_value = (not_completed_value,)
        self.due_attr = due_attr

        attr_map = {
            'title': 'title',
            completed_attr: 'completed',
            due_attr: 'due',
        }
        super().__init__(name=name, attr_map=attr_map, resolve_conflict=resolve_conflict)

    def get_notion_objects(self) -> list[Page]:
        """Get all pages from database."""
        return self.notion_db.fetch_all().to_pages()

    def get_other_objects(self) -> list[GTask]:
        """Get all Google Taks from Tasklist."""
        return self.tasklist.all_tasks()

    def notion_timestamp(self, obj: Page) -> datetime:
        """Get the timestamp of the Notion page."""
        raise obj.last_edited_time

    def other_timestamp(self, obj: GTask) -> datetime:
        """Get the timestamp of the Google Task."""
        raise obj.updated

    def notion_hash(self, obj: Page) -> str:
        """Get the hash of the Notion page for object mapping/linking."""
        raise hash(obj.title)

    def other_hash(self, obj: GTask) -> str:
        """Get the hash of the other object for object mapping/linking."""
        return hash(obj.title)

    def notion_to_dict(self, obj: Page) -> dict[str, Any]:
        """Convert a Notion object to a dictionary."""
        return {
            'title': obj.title,
            self.completed_attr: obj.props[self.completed_attr] == self.completed_value,
            self.due_attr: obj.props[self.due_attr],
        }

    def other_to_dict(self, obj: GTask) -> dict[str, Any]:
        """Convert another object to a dictionary."""
        return {
            'title': obj.title,
            self.completed_attr: obj.completed,
            self.due_attr: obj.due,
        }

    def notion_update_obj(self, obj: Page, attr: str, value: Any) -> None:
        """Set an attribute of the Notion object, e.g. page."""
        obj.props[attr] = value

    def other_update_obj(self, obj: GTask, attr: str, value: Any) -> None:
        """Set an attribute of the other object."""
        setattr(obj, attr, value)

    def notion_delete_obj(self, obj: Page) -> None:
        """Delete the page."""
        obj.delete()

    def other_delete_obj(self, obj: GTask) -> None:
        """Delete the other object."""
        obj.delete()

    def notion_create_obj(self, **kwargs: Any) -> None:
        """Create a new page."""
        self.notion_db.create_page(**kwargs)

    def other_create_obj(self, **kwargs: Any) -> None:
        """Create a new other object."""
        self.tasklist.create_task(**kwargs)
