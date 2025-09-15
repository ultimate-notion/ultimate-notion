"""Errors/exceptions of the Ultimate Notion API."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ultimate_notion.schema import Schema


class UltimateNotionError(Exception):
    """Base class for all exceptions in this package."""


class UnsetError(UltimateNotionError):
    """Raised when an unset value is accessed before being initialized by the Notion API."""


class SessionError(UltimateNotionError):
    """Raised when there are issues with the Notion session."""


class UnknownUserError(UltimateNotionError):
    """Raised when the user is unknown."""


class UnknownPageError(UltimateNotionError):
    """Raised when the page is unknown."""


class InvalidAPIUsageError(UltimateNotionError):
    """Raised when the API is used in an invalid way."""


class EmptyDBError(UltimateNotionError):
    """A special exception that tells us that a database is empty during probing."""


class FilterQueryError(ValueError, UltimateNotionError):
    """An exception that is raised when a filter query is invalid."""


class EmptyListError(UltimateNotionError):
    """Custom exception for an empty list in SList."""


class MultipleItemsError(UltimateNotionError):
    """Custom exception for a list with multiple items in SList."""


class SchemaError(UltimateNotionError):
    """Raised when there are issues with the schema of a database."""


class SchemaNotBoundError(SchemaError):
    """Raised when the schema is not bound to a database."""

    def __init__(self, schema: type[Schema]):
        self.schema = schema
        msg = f'Schema {schema.__name__} is not bound to any database'
        super().__init__(msg)


class RollupError(SchemaError):
    """Error if definition of rollup is wrong."""


class RelationError(SchemaError):
    """Error if a Relation cannot be initialised."""


class ReadOnlyPropertyError(SchemaError):
    """Raised when an attempt is made to write to a write-protected property."""


class PropertyError(SchemaError):
    """Raised when there is an issue with a property in the schema."""
