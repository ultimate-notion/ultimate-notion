"""Syncs a Notion database with a Google Tasks task list."""
# ruff: noqa: PLR6301

from __future__ import annotations

from datetime import datetime
from typing import Any

from ultimate_notion import Column, Database, Page
from ultimate_notion.adapters.google.tasks.client import GTask, GTaskList
from ultimate_notion.adapters.sync import ConflictMode, SyncTask
from ultimate_notion.utils import str_hash


class SyncGTasks(SyncTask):
    """Syncs a Notion database with a Google Tasks task list."""

    def __init__(
        self,
        *,
        notion_db: Database,
        tasklist: GTaskList,
        completed_col: Column | str,
        completed_val: Any,
        not_completed_val: Any,
        due_col: Column | str,
        name: str = 'SyncGTasks',
        conflict_mode: ConflictMode = ConflictMode.NEWER,
    ):
        if isinstance(completed_col, Column):
            completed_col = completed_col.name
        if isinstance(due_col, Column):
            due_col = due_col.name

        self.notion_db = notion_db
        self.tasklist = tasklist
        self.completed_col = completed_col
        self.completed_val = completed_val
        self.not_completed_val = not_completed_val
        self.due_col = due_col
        self.title_col = self.notion_db.schema.get_title_col().name

        attr_map = {
            self.title_col: 'title',
            self.completed_col: 'is_completed',
            self.due_col: 'due',
        }
        super().__init__(name=name, attr_map=attr_map, conflict_mode=conflict_mode)

    def get_notion_objects(self) -> list[Page]:
        """Get all pages from database."""
        return self.notion_db.fetch_all().to_pages()

    def get_other_objects(self) -> list[GTask]:
        """Get all Google Taks from Tasklist."""
        return self.tasklist.all_tasks()

    def notion_timestamp(self, obj: Page) -> datetime:
        """Get the timestamp of the Notion page."""
        return obj.last_edited_time

    def other_timestamp(self, obj: GTask) -> datetime:
        """Get the timestamp of the Google Task."""
        return obj.updated

    def notion_hash(self, obj: Page) -> str:
        """Get the hash of the Notion page for object mapping/linking."""
        return str_hash(obj.title)

    def other_hash(self, obj: GTask) -> str:
        """Get the hash of the other object for object mapping/linking."""
        return str_hash(obj.title)

    def notion_to_dict(self, obj: Page) -> dict[str, Any]:
        """Convert a Notion object to a dictionary."""
        return {
            self.title_col: obj.title,
            self.completed_col: obj.props[self.completed_col] == self.completed_val,
            self.due_col: obj.props[self.due_col],
        }

    def other_to_dict(self, obj: GTask) -> dict[str, Any]:
        """Convert another object to a dictionary."""
        return {
            'title': obj.title,
            'is_completed': obj.is_completed,
            'due': obj.due,
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
        kwargs[self.completed_col] = self.completed_val if kwargs[self.completed_col] else self.not_completed_val
        attr_kwargs = {self.notion_db.schema.get_col(key).attr_name: value for key, value in kwargs.items()}
        self.notion_db.create_page(**attr_kwargs)

    def other_create_obj(self, **kwargs: Any) -> None:
        """Create a new other object."""
        task = self.tasklist.create_task(title=kwargs['title'], due=kwargs['due'].value)
        task.is_completed = kwargs['is_completed']
