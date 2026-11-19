"""Notion's saved database views and their API settings."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, TypedDict
from uuid import UUID

from pydantic import ConfigDict

from ultimate_notion.obj_api.core import NotionObject, UserRef
from ultimate_notion.obj_api.objects import DatabaseRef


class ViewType(StrEnum):
    """Presentation type of a saved Notion view."""

    TABLE = 'table'
    BOARD = 'board'
    LIST = 'list'
    CALENDAR = 'calendar'
    TIMELINE = 'timeline'
    GALLERY = 'gallery'
    FORM = 'form'
    CHART = 'chart'
    MAP = 'map'
    DASHBOARD = 'dashboard'


class ViewRef(NotionObject[UUID], object='view'):
    """A reference returned when listing saved views."""

    id: UUID


class ViewSettings(TypedDict, total=False):
    """Settings accepted by the Views API, using Notion's JSON shapes."""

    filter: dict[str, Any] | None
    sorts: list[dict[str, Any]] | None
    quick_filters: dict[str, Any] | None
    configuration: dict[str, Any]


class View(ViewRef):
    """A saved view returned by Notion."""

    # Layout-specific fields can vary by view type.
    model_config = ConfigDict(extra='allow')

    parent: DatabaseRef
    type: ViewType
    name: str | None = None
    data_source_id: UUID | None = None
    filter: dict[str, Any] | None = None
    sorts: list[dict[str, Any]] | None = None
    quick_filters: dict[str, Any] | None = None
    configuration: dict[str, Any] | None = None
    created_time: datetime | None = None
    created_by: UserRef | None = None
    last_edited_time: datetime | None = None
    last_edited_by: UserRef | None = None
    url: str | None = None
    dashboard_view_id: UUID | None = None
