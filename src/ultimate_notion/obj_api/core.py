"""Base classes for working with the Notion API."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializeAsAny,
    ValidatorFunctionWrapHandler,
    field_validator,
    model_validator,
)
from typing_extensions import Self

from ultimate_notion.utils import is_stable_release

if TYPE_CHECKING:
    from ultimate_notion.obj_api.objects import ParentRef, UserRef


logger = logging.getLogger(__name__)

BASE_URL_PATTERN = r'https://(www.)?notion.so/'
UUID_PATTERN = r'[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}'

UUID_RE = re.compile(rf'^(?P<id>{UUID_PATTERN})$')

PAGE_URL_SHORT_RE = re.compile(
    rf"""^
      {BASE_URL_PATTERN}
      (?P<page_id>{UUID_PATTERN})
    $""",
    flags=re.IGNORECASE | re.VERBOSE,
)

PAGE_URL_LONG_RE = re.compile(
    rf"""^
      {BASE_URL_PATTERN}
      (?P<title>.*)-
      (?P<page_id>{UUID_PATTERN})
    $""",
    flags=re.IGNORECASE | re.VERBOSE,
)

BLOCK_URL_LONG_RE = re.compile(
    rf"""^
      {BASE_URL_PATTERN}
      (?P<username>.*)/
      (?P<title>.*)-
      (?P<page_id>{UUID_PATTERN})
      \#(?P<block_id>{UUID_PATTERN})
    $""",
    flags=re.IGNORECASE | re.VERBOSE,
)


def extract_id(text: str) -> str | None:
    """Examine the given text to find a valid Notion object ID."""

    m = UUID_RE.match(text)
    if m is not None:
        return m.group('id')

    m = PAGE_URL_LONG_RE.match(text)
    if m is not None:
        return m.group('page_id')

    m = PAGE_URL_SHORT_RE.match(text)
    if m is not None:
        return m.group('page_id')

    m = BLOCK_URL_LONG_RE.match(text)
    if m is not None:
        return m.group('block_id')

    return None


class GenericObject(BaseModel):
    """The base for all API objects."""

    model_config = ConfigDict(extra='ignore' if is_stable_release() else 'forbid')

    @classmethod
    def _set_field_default(cls, name: str, default: str) -> None:
        """Modify the `BaseModel` field information for a specific class instance.

        This is necessary in particular for subclasses that change the default values
        of a model when defined. Notable examples are `TypedObject` and `NotionObject`.

        Args:
            name: the named attribute in the class
            default: the new default value for the named field
        """
        # Rebuild model to avoid UserWarning about shadowing an attribute in parent.
        # More details here: https://github.com/pydantic/pydantic/issues/6966
        field = cls.model_fields.get(name)
        if field is None:
            msg = f'No field of name {name} in {cls.__name__} found!'
            raise ValueError(msg)
        field.default = default
        field.validate_default = False
        cls.model_rebuild(force=True)

    # https://github.com/pydantic/pydantic/discussions/3139
    def update(self, **data: Any) -> Self:
        """Update the internal attributes with new data."""

        new_obj_dct = self.model_dump()
        new_obj_dct.update(data)
        new_obj = self.model_validate(new_obj_dct)

        for k, v in new_obj.model_dump(exclude_unset=True).items():
            # exclude_unset avoids overwriting for instance known children that need to be retrieved separately
            logger.debug('updating object data -- %s => %s', k, v)
            setattr(self, k, getattr(new_obj, k))

        return self

    def serialize_for_api(self) -> dict[str, Any]:
        """Serialize the object for sending it to the Notion API."""
        # Notion API doesn't like "null" values
        return self.model_dump(mode='json', exclude_none=True, by_alias=True)

    @classmethod
    def build(cls, *args, **kwargs):
        """Use the standard constructur to build the instance. Will be overwritten for more complex types."""
        return cls(*args, **kwargs)


class NotionObject(GenericObject):
    """A top-level Notion API resource.

    Many objects in the Notion API follow a standard pattern with a `object` property, which
    defines the general object type, e.g. `page`, `database`, `user`, `block`, ...
    """

    object: str = Field(default=None)  # type: ignore # avoids mypy plugin errors as this is set in __init_subclass__
    """`object` is a string that identifies the general object type, e.g. `page`, `database`, `user`, `block`, ..."""
    id: UUID | str = Field(union_mode='left_to_right', default=None)  # type: ignore
    """`id` is an `UUID` if possible or a string (possibly not unique) depending on the object"""
    request_id: UUID | None = None
    """`request_id` is a UUID that is used to track requests in the Notion API"""

    def __init_subclass__(cls, *, object=None, **kwargs):  # noqa: A002
        super().__init_subclass__(**kwargs)

    @classmethod
    def __pydantic_init_subclass__(cls, *, object=None, **kwargs):  # noqa: A002, PLW3201
        """Update `GenericObject` defaults for the named object.

        Needed since `model_fields` are not available during __init_subclass__
        See: https://github.com/pydantic/pydantic/issues/5369
        """
        super().__pydantic_init_subclass__(object=object, **kwargs)

        if object is not None:  # if None we inherit 'object' from the base class
            cls._set_field_default('object', default=object)

    @field_validator('object', mode='after')
    @classmethod
    def _verify_object_matches_expected(cls, val):
        """Make sure that the deserialized object matches the name in this class."""

        obj_attr = cls.model_fields.get('object').default
        if val != obj_attr:
            msg = f'Invalid object for {obj_attr} - {val}'
            raise ValueError(msg)

        return val


class NotionEntity(NotionObject):
    """A materialized entity, which was created by a user."""

    id: UUID = None  # type: ignore
    parent: SerializeAsAny[ParentRef] = None  # type: ignore

    created_time: datetime = None  # type: ignore
    created_by: UserRef = None  # type: ignore

    last_edited_time: datetime = None  # type: ignore


class TypedObject(GenericObject):
    """A type-referenced object.

    Many objects in the Notion API follow a standard pattern with a `type` property
    followed by additional data. These objects must specify a `type` attribute to
    ensure that the correct object is created.

    For example, this contains a nested 'detail' object:

        data = {
            type: "detail",
            ...
            detail: {
                ...
            }
        }
    """

    type: str = Field(default=None)  # type: ignore  # avoids mypy plugin errors as this is set in __init_subclass__
    """`type` is a string that identifies the specific object type, e.g. `heading_1`, `paragraph`, `equation`, ..."""
    _polymorphic_base: ClassVar[bool] = False

    def __init_subclass__(cls, *, type: str | None = None, polymorphic_base: bool = False, **kwargs):  # noqa: A002
        super().__init_subclass__(**kwargs)
        cls._polymorphic_base = polymorphic_base

    @classmethod
    def __pydantic_init_subclass__(cls, *, type: str | None = None, **kwargs):  # noqa: A002, PLW3201
        """Register the subtypes of the TypedObject subclass.

        This is needed since `model_fields` is not available during __init_subclass__.
        See: https://github.com/pydantic/pydantic/issues/5369
        """
        super().__pydantic_init_subclass__(type=type, **kwargs)
        type_name = cls.__name__ if type is None else type
        cls._register_type(type_name)

    @classmethod
    def _register_type(cls, name):
        """Register a specific class for the given 'type' name."""

        cls._set_field_default('type', default=name)

        # initialize a _typemap map for each direct child of TypedObject

        # this allows different class trees to have the same 'type' name
        # but point to a different object (e.g. the 'date' type may have
        # different implementations depending where it is used in the API)

        if not hasattr(cls, '_typemap'):
            cls._typemap = {}

        if name in cls._typemap:
            msg = f'Duplicate subtype for class - {name} :: {cls}'
            raise ValueError(msg)

        logger.debug('registered new subtype: %s => %s', name, cls)
        cls._typemap[name] = cls

    @model_validator(mode='wrap')
    @classmethod
    def _resolve_type(cls, value: Any, handler: ValidatorFunctionWrapHandler):
        """Instantiate the correct object based on the `type` field.

        Following this approach: https://github.com/pydantic/pydantic/discussions/7008
        Also the reason for `polymorphic_base` is explained there.
        """

        if isinstance(value, cls):
            return handler(value)

        if not cls._polymorphic_base:  # breaks the recursion
            return handler(value)

        if not isinstance(value, dict):
            msg = "Invalid 'data' object"
            raise ValueError(msg)

        if not hasattr(cls, '_typemap'):
            msg = f"Missing '_typemap' in {cls}"
            raise ValueError(msg)

        type_name = value.get('type')

        if type_name is None:
            logger.warning(f'Missing type in data {value}. Most likely a User object without type')
            msg = f"Missing 'type' in data {value}"
            if value['object'] == 'user':
                type_name = 'unknown'  # for the unofficial type objects.UnknownUser
            else:
                raise ValueError(msg)

        sub_cls = cls._typemap.get(type_name)

        if sub_cls is None:
            msg = f'Unsupported sub-type: {type_name}'
            raise ValueError(msg)

        return sub_cls(**value)

    @property
    def value(self) -> Any:
        """Return the nested object."""
        return getattr(self, self.type)

    @value.setter
    def value(self, val: Any) -> None:
        """Set the nested object."""
        setattr(self, self.type, val)
