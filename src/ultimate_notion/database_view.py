"""High-level access to a view saved in Notion."""

from __future__ import annotations

from typing import Self, Unpack
from uuid import UUID

from ultimate_notion.core import NotionObject, get_active_session
from ultimate_notion.obj_api.iterator import ViewQuery, ViewQueryResultList
from ultimate_notion.obj_api.views import View, ViewSettings, ViewType


class DatabaseView(NotionObject[View], wraps=View):
    """A saved presentation of a Notion data source or a dashboard view."""

    @property
    def id(self) -> UUID:
        """Return the view's ID."""
        return self.obj_ref.id

    @property
    def name(self) -> str | None:
        """Return the view's display name, if present in the response."""
        return self.obj_ref.name

    @property
    def type(self) -> ViewType:
        """Return the view's presentation type."""
        return self.obj_ref.type

    @property
    def database_id(self) -> UUID:
        """Return the ID of the database container holding the view."""
        return self.obj_ref.parent.database_id

    @property
    def data_source_id(self) -> UUID | None:
        """Return the ID of the data source presented in the view, if any."""
        return self.obj_ref.data_source_id

    def update(self, *, name: str | None = None, **settings: Unpack[ViewSettings]) -> Self:
        """Update the view in Notion. Pass None for a nullable setting to clear it."""
        self.obj_ref = get_active_session().api.views.update(self.obj_ref, name=name, **settings)
        return self

    def delete(self) -> None:
        """Delete the saved view from Notion."""
        get_active_session().api.views.delete(self.obj_ref)

    def query(self, *, page_size: int | None = None) -> ViewQuery:
        """Run the saved view and return its first page of page references."""
        return get_active_session().api.views.create_query(self.obj_ref, page_size=page_size)

    def query_results(
        self, query_id: UUID | str, *, start_cursor: str | None = None, page_size: int | None = None
    ) -> ViewQueryResultList:
        """Return the next page of references using the cursor from a cached query."""
        return get_active_session().api.views.query_results(
            self.obj_ref, query_id, start_cursor=start_cursor, page_size=page_size
        )

    def delete_query(self, query_id: UUID | str) -> None:
        """Release cached results without deleting the saved view."""
        get_active_session().api.views.delete_query(self.obj_ref, query_id)
