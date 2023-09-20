"""Base classes for working with the Notion API."""

import inspect
import logging
from datetime import date, datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, validator
from pydantic.main import validate_model

logger = logging.getLogger(__name__)


def serialize_to_api(data):
    """Recursively convert the given data to an API-safe form.

    This is mostly to handle data types that will not directly serialize to JSON.
    """

    # https://github.com/samuelcolvin/pydantic/issues/1409
    # ToDo: Seems to be fixed in pydantic v2, remove this workaround

    if isinstance(data, date | datetime):
        return data.isoformat()

    if isinstance(data, UUID):
        return str(data)

    if isinstance(data, Enum):
        return data.value

    if isinstance(data, list | tuple):
        return [serialize_to_api(value) for value in data]

    if isinstance(data, dict):
        return {name: serialize_to_api(value) for name, value in data.items()}

    return data


class GenericObject(BaseModel, extra='forbid'):
    """The base for all API objects.

    As a general convention, data fields in lower case are defined by the
    Notion API.  Properties in Title Case are provided for convenience.
    """

    def __setattr__(self, name, value):
        """Set the attribute of this object to a given value.

        The implementation of `BaseModel.__setattr__` does not support property setters.

        See https://github.com/samuelcolvin/pydantic/issues/1577
        """
        try:
            super().__setattr__(name, value)
        except ValueError as err:
            setters = inspect.getmembers(
                object=self.__class__,
                predicate=lambda x: isinstance(x, property) and x.fset is not None,
            )
            for setter_name, _ in setters:
                if setter_name == name:
                    object.__setattr__(self, name, value)
                    break
            else:
                raise err

    @classmethod
    def _set_field_default(cls, name, default=None):
        """Modify the `BaseModel` field information for a specific class instance.

        This is necessary in particular for subclasses that change the default values
        of a model when defined.  Notable examples are `TypedObject` and `NotionObject`.

        :param name: the named attribute in the class
        :param default: the new default for the named field
        """

        # set the attribute on the class to the given default
        setattr(cls, name, default)

        # update the model field definition
        field = cls.__fields__.get(name)

        field.default = default
        field.required = default is None

    # https://github.com/samuelcolvin/pydantic/discussions/3139
    def refresh(self, **data):
        """Refresh the internal attributes with new data."""

        values, fields, error = validate_model(self.__class__, data)

        if error:
            raise error

        for name in fields:
            value = values[name]
            logger.debug('set object data -- %s => %s', name, value)
            setattr(self, name, value)

        return self

    def dict(self, **kwargs):  # noqa: A003, rename to model_dump when using pydantic v2
        """Convert to a suitable representation for the Notion API."""

        # the API doesn't like "undefined" values...
        kwargs['exclude_none'] = True
        kwargs['by_alias'] = True

        obj = super().dict(**kwargs)  # model_dump in pydantic v2

        # TODO read-only fields should not be sent to the API
        # https://github.com/jheddings/notional/issues/9

        return serialize_to_api(obj)

    @classmethod
    def build(cls, *args, **kwargs):
        """Use the standard constructur to build the instance. Will be overridden for more complex types"""
        return cls(*args, **kwargs)


class NotionObject(GenericObject):
    """A top-level Notion API resource."""

    object: str  # noqa: A003
    id: UUID | None = None  # noqa: A003

    def __init_subclass__(cls, object=None, **kwargs):  # noqa: A002
        """Update `GenericObject` defaults for the named object."""
        super().__init_subclass__(**kwargs)

        if object is not None:
            cls._set_field_default('object', default=object)

    @validator('object', always=True, pre=False)
    @classmethod
    def _verify_object_matches_expected(cls, val):
        """Make sure that the deserialzied object matches the name in this class."""

        if val != cls.object:
            msg = f'Invalid object for {cls.object} - {val}'
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

    type: str  # noqa: A003

    # modified from the methods described in this discussion:
    # - https://github.com/samuelcolvin/pydantic/discussions/3091

    def __init_subclass__(cls, type=None, **kwargs):  # noqa: A002
        """Register the subtypes of the TypedObject subclass."""
        super().__init_subclass__(**kwargs)

        type_name = cls.__name__ if type is None else type

        cls._register_type(type_name)

    @property
    def value(self):
        """Return the nested object"""

        cls = self.__class__
        return getattr(self, cls.type)

    @classmethod
    def __get_validators__(cls):
        """Provide `BaseModel` with the means to convert `TypedObject`'s."""
        yield cls._resolve_type

    @classmethod
    def parse_obj(cls, obj):
        """Parse the structured object data into an instance of `TypedObject`.

        This method overrides `BaseModel.parse_obj()`.
        """
        return cls._resolve_type(obj)

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

    @classmethod
    def _resolve_type(cls, data):
        """Instantiate the correct object based on the 'type' field."""

        if isinstance(data, cls):
            return data

        if not isinstance(data, dict):
            msg = "Invalid 'data' object"
            raise ValueError(msg)

        if not hasattr(cls, '_typemap'):
            msg = f"Missing '_typemap' in {cls}"
            raise TypeError(msg)

        type_name = data.get('type')

        if type_name is None:
            msg = "Missing 'type' in data"
            raise ValueError(msg)

        sub = cls._typemap.get(type_name)

        if sub is None:
            msg = f'Unsupported sub-type: {type_name}'
            raise TypeError(msg)

        logger.debug('initializing typed object %s :: %s => %s -- %s', cls, type_name, sub, data)

        return sub(**data)
