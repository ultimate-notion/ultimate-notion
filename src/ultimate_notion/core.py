"""Base classes for working with the Notion API."""

import inspect
import logging
from datetime import date, datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel
from pydantic.main import ModelMetaclass, validate_model

log = logging.getLogger(__name__)


def make_api_safe(data):
    """Recursively convert the given data to an API-safe form.

    This is mostly to handle data types that will not directly serialize to JSON.
    """

    # https://github.com/samuelcolvin/pydantic/issues/1409#issuecomment-877175194

    if isinstance(data, (date, datetime)):
        return data.isoformat()

    if isinstance(data, UUID):
        return str(data)

    if isinstance(data, Enum):
        return data.value

    if isinstance(data, dict):
        return {name: make_api_safe(value) for name, value in data.items()}

    if isinstance(data, list):
        return [make_api_safe(value) for value in data]

    if isinstance(data, tuple):
        return [make_api_safe(value) for value in data]

    return data


class ComposableObject(ModelMetaclass):
    """Presents a metaclass that composes objects using simple values.

    This is primarily to allow easy definition of data objects without disrupting the
    `BaseModel` constructor.  e.g. rather than requiring a caller to understand how
    nested data works in the data objects, they can compose objects from simple values.

    Compare the following code for declaring a Paragraph:

    ```python
    # using nested data objects:
    text = "hello world"
    nested = TextObject._NestedData(content=text)
    rtf = text.TextObject(text=nested, plain_text=text)
    content = blocks.Paragraph._NestedData(text=[rtf])
    para = blocks.Paragraph(paragraph=content)

    # using a composable object:
    para = blocks.Paragraph["hello world"]
    ```

    Classes that support composition in this way must define and implement the internal
    `__compose__` method.  This method takes an arbitrary number of parameters, based
    on the needs of the implementation.  It is up to the implementing class to ensure
    that the parameters are specified correctly.
    """

    def __getitem__(self, params):
        """Return the requested class by composing using the given param.

        Types found in `params` will be compared to expected types in the `__compose__`
        method.

        If the requested class does not expose the `__compose__` method, this will raise
        an exception.
        """

        if not hasattr(self, "__compose__"):
            raise NotImplementedError(f"{self} does not support object composition")

        # XXX if params is empty / None, consider calling the default constructor

        compose = self.__compose__

        if type(params) is tuple:
            return compose(*params)

        return compose(params)


class DataObject(BaseModel, metaclass=ComposableObject):
    """The base for all API objects."""

    def __setattr__(self, name, value):
        """Set the attribute of this object to a given value.

        The implementation of `BaseModel.__setattr__` does not allow for properties.

        See https://github.com/samuelcolvin/pydantic/issues/1577
        """
        try:
            super().__setattr__(name, value)
        except ValueError as err:
            setters = inspect.getmembers(
                self.__class__,
                predicate=lambda x: isinstance(x, property) and x.fset is not None,
            )
            for setter_name, _ in setters:
                if setter_name == name:
                    object.__setattr__(self, name, value)
                    break
            else:
                raise err

    @classmethod
    def _modify_field_(cls, name, default=None):
        """Modify the `BaseModel` field information for a specific class instance.

        This is necessary in particular for subclasses that change the default values
        of a model when defined.  Notable examples are `TypedObject` and `NamedObject`.

        :param name: the named attribute in the class
        :param default: the new default for the named field
        """
        setattr(cls, name, default)

        cls.__fields__[name].default = default
        cls.__fields__[name].required = default is None

    # https://github.com/samuelcolvin/pydantic/discussions/3139
    def refresh(__pydantic_self__, **data):
        """Refresh the internal attributes with new data."""

        values, fields, error = validate_model(__pydantic_self__.__class__, data)

        if error:
            raise error

        for name in fields:
            value = values[name]
            log.debug("set object data -- %s => %s", name, value)
            setattr(__pydantic_self__, name, value)

        return __pydantic_self__

    def to_api(self):
        """Convert to a suitable representation for the Notion API."""

        # the API doesn't like "undefined" values...

        data = self.dict(exclude_none=True, by_alias=True)

        # we need to convert "special" types to string forms to help the JSON encoder.
        # there are efforts underway in pydantic to make this easier, but for now...

        return make_api_safe(data)


class NamedObject(DataObject):
    """A Notion API object."""

    # XXX should NamedObject have the same typing ability as TypedObject?

    object: str

    def __init_subclass__(cls, object=None, **kwargs):
        """Update `DataObject` defaults for the named object."""
        super().__init_subclass__(**kwargs)

        if object is not None:
            cls._modify_field_("object", default=object)


class TypedObject(DataObject):
    """A type-referenced object.

    Many objects in the Notion API follow a generic->specific pattern with a 'type'
    parameter followed by additional data.  These objects must specify a `type`
    attribute to ensure that the correct object is created.

    Calling the object provides direct access to the data stored in `{type}`.
    """

    type: str

    # modified from the methods described in this discussion:
    # - https://github.com/samuelcolvin/pydantic/discussions/3091

    def __init_subclass__(cls, type=None, **kwargs):
        """Register the subtypes of the TypedObject subclass."""
        super().__init_subclass__(**kwargs)

        if type is not None:
            sub_type = type

        elif hasattr(cls, "__type__"):
            sub_type = cls.__type__

        else:
            sub_type = cls.__name__

        cls._modify_field_("type", default=sub_type)

        # initialize a __typemap__ map for each direct child of TypedObject

        # this allows different class trees to have the same 'type' name
        # but point to a different object (e.g. the 'date' type may have
        # different implementations depending where it is used in the API)

        # also, due to the order in which typed classes are defined, once
        # the map is defined for a subclass of TypedObject, any further
        # descendants of that class will have the new map via inheritance

        if TypedObject in cls.__bases__ and not hasattr(cls, "__typemap__"):
            cls.__typemap__ = {}

        if sub_type in cls.__typemap__:
            raise ValueError(f"Duplicate subtype for class - {sub_type} :: {cls}")

        log.debug("registered new subtype: %s => %s", sub_type, cls)

        cls.__typemap__[sub_type] = cls

    def __call__(self, field=None):
        """Return nested data from this Block.

        If a field is provided, the contents of that field in the NestedData will be
        returned.  Otherwise, the full contents of the NestedData will be returned.
        """

        type = getattr(self, "type", None)

        if type is None:
            raise AttributeError("type not specified")

        nested = getattr(self, type)

        if field is not None:
            nested = getattr(nested, field)

        return nested

    @classmethod
    def __get_validators__(cls):
        """Provide `BaseModel` with the means to convert `TypedObject`'s."""
        yield cls._convert_to_real_type_

    @classmethod
    def parse_obj(cls, obj):
        """Parse the structured object data into an instance of `TypedObject`.

        This method overrides `BaseModel.parse_obj()`.
        """
        return cls._convert_to_real_type_(obj)

    @classmethod
    def _convert_to_real_type_(cls, data):
        """Instantiate the correct object based on the 'type' field."""

        if isinstance(data, cls):
            return data

        if not isinstance(data, dict):
            raise ValueError("Invalid 'data' object")

        data_type = data.get("type")

        if data_type is None:
            raise ValueError("Missing 'type' in TypedObject")

        if not hasattr(cls, "__typemap__"):
            raise TypeError(f"Invalid TypedObject: {cls} - missing __typemap__")

        sub = cls.__typemap__.get(data_type)

        if sub is None:
            raise TypeError(f"Unsupported sub-type: {data_type}")

        log.debug(
            "initializing typed object %s :: %s => %s -- %s", cls, data_type, sub, data
        )

        return sub(**data)


class NestedObject(DataObject):
    """Represents an API object with nested data.

    These objects require a 'type' property and a matching property of the same
    name, which holds additional data.

    For example, this contains a nested 'text' object:

        data = {
            type: "text",
            ...
            text: {
                ...
            }
        }

    Currently, this is a convenience class for clarity - it does not provide additional
    functionality at this time.
    """
