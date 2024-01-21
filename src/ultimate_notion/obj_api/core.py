"""Base classes for working with the Notion API."""

from __future__ import annotations

import logging
from typing import Any, ClassVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, ValidatorFunctionWrapHandler, field_validator, model_validator

logger = logging.getLogger(__name__)


class GenericObject(BaseModel):
    """The base for all API objects.

    As a general convention, data fields in lower case are defined by the
    Notion API.  Properties in Title Case are provided for convenience.
    """

    model_config = ConfigDict(extra='forbid')

    @classmethod
    def _set_field_default(cls, name: str, default: str):
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
    def update(self, **data):
        """Update the internal attributes with new data."""

        new_obj_dct = self.model_dump()
        new_obj_dct.update(data)
        new_obj = self.model_validate(new_obj_dct)

        for k, v in new_obj.model_dump().items():
            # model_dump(exclude_defaults=True) was used before, but that prevented restoring pages
            logger.debug('updating object data -- %s => %s', k, v)
            setattr(self, k, getattr(new_obj, k))

        return self

    def serialize_for_api(self):
        """Serialize the object for sending it to the Notion API."""
        # Notion API doesn't like "null" values
        return self.model_dump(mode='json', exclude_none=True, by_alias=True)

    @classmethod
    def build(cls, *args, **kwargs):
        """Use the standard constructur to build the instance. Will be overridden for more complex types."""
        return cls(*args, **kwargs)


class NotionObject(GenericObject):
    """A top-level Notion API resource."""

    object: str
    request_id: UUID = None  # type: ignore
    id: UUID | str = None  # type: ignore

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

        obj_attr = cls.build().object
        if val != obj_attr:
            msg = f'Invalid object for {obj_attr} - {val}'
            raise ValueError(msg)

        return val


class TypedObject(GenericObject):
    """A type-referenced object.

    Many objects in the Notion API follow a standard pattern with a 'type' property
    followed by additional data.  These objects must specify a `type` attribute to
    ensure that the correct object is created.

    For example, this contains a nested 'detail' object:

        data = {
            type: "detail",
            ...
            detail: {
                ...
            }
        }

    Calling the object provides direct access to the data stored in `{type}`.
    """

    type: str
    _polymorphic_base: ClassVar[bool] = False

    def __init_subclass__(cls, *, type: str | None = None, polymorphic_base: bool = False, **kwargs):  # noqa: A002
        cls._polymorphic_base = polymorphic_base
        super().__init_subclass__(**kwargs)

    @classmethod
    def __pydantic_init_subclass__(cls, *, type: str | None = None, **kwargs):  # noqa: A002, PLW3201
        """Register the subtypes of the TypedObject subclass.

        Needed since `model_fields` are not available during __init_subclass__.
        See: https://github.com/pydantic/pydantic/issues/5369
        """
        type_name = cls.__name__ if type is None else type
        cls._register_type(type_name)
        super().__pydantic_init_subclass__(**kwargs)

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
        """Instantiate the correct object based on the 'type' field.

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
            msg = "Missing 'type' in data"
            raise ValueError(msg)

        sub_cls = cls._typemap.get(type_name)

        if sub_cls is None:
            msg = f'Unsupported sub-type: {type_name}'
            raise ValueError(msg)

        logger.debug('initializing typed object %s :: %s => %s -- %s', cls, type_name, sub_cls, value)

        return sub_cls(**value)

    # ToDo: Check if we shouldn't make this rather abstract
    @property
    def value(self) -> Any:
        """Return the nested object."""
        return getattr(self, self.type)
