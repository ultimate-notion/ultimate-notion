"""Base classes for working with the Notion API.


!!! warning

   To have proper type checking and inference, covariant type parameters are sometimes used even though
   they may violate the LSP (Liskov Substitution Principle) in some cases. This was done to improve the usability
   and flexibility of the API, allowing for more intuitive code while still maintaining type safety.
   Especially in this complex class hierarchy, Pydantic, which is heavily used in the API, relies on these
   covariant type parameters to function correctly. As an alternative approach, Protocol classes were tried,
   but they introduced their own complexities and limitations.
"""

from __future__ import annotations

import builtins
import logging
import re
from abc import ABC
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar, Generic, NoReturn, cast, overload
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
from typing_extensions import Self, TypeIs, TypeVar

from ultimate_notion.errors import UnsetError
from ultimate_notion.obj_api.enums import Color
from ultimate_notion.utils import is_stable_release, pydantic_apply

if TYPE_CHECKING:
    from ultimate_notion.obj_api.objects import User


_logger = logging.getLogger(__name__)


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


# ToDo: Replace with MISSING when stable: https://docs.pydantic.dev/latest/concepts/experimental/#missing-sentinel
# Or use typing_extensions.Sentinel instead.
class UnsetType(BaseModel):
    """Sentinel type for missing default values.

    A sentinel type for indicating that a value is unset or missing for cases when `None` has another meaning.
    In the Notion API, `None` is also used to delete properties, so a way to represent "no value" explicitly is needed.
    """

    __slots__ = ()

    def __new__(cls, *args: Any, **kwargs: Any) -> UnsetType:
        # Ensure only one instance is created, allowing `is` to work correctly
        if not hasattr(cls, '_instance'):
            cls._instance = super().__new__(cls)
        return cls._instance

    # Marker field that survives serialization to identify unset values
    unset_marker: bool = Field(default=True, exclude=False)

    def __repr__(self) -> str:
        return 'Unset'

    def __hash__(self) -> int:
        return hash(UnsetType)


Unset: UnsetType = UnsetType()


def is_unset(v: Any) -> TypeIs[UnsetType]:
    """Check if the given value is unset."""
    if isinstance(v, UnsetType):
        return True
    elif v == Unset.model_dump(mode='python'):  # v was serialized
        return True
    return False


@overload
def raise_unset(obj: UnsetType) -> NoReturn: ...
@overload
def raise_unset(obj: T) -> T: ...
def raise_unset(obj: T | UnsetType) -> T:
    """Raise an error if the object is unset."""
    if is_unset(obj):
        msg = 'Parameter is unset and was not yet initialized by the Notion API.'
        raise UnsetError(msg)
    return obj


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

    __hash__: ClassVar[None] = None  # type: ignore[assignment]
    _frozen: bool = False  # for computing hash and equality
    model_config = ConfigDict(extra='ignore' if is_stable_release() else 'forbid')

    def __eq__(self, other: Any) -> bool:
        """Compare two objects for equality by comparing all their fields."""
        # Require exact same runtime type (not just isinstance) to avoid comparing different subclasses
        # This also means that delegation takes place, e.g. for UserRef vs User
        if type(self) is not type(other):
            return NotImplemented

        # _freeze is used to guarantee the consistency with __hash__.
        return BaseModel.__eq__(_normalize_model(self), _normalize_model(other))

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
    def update(self, **data: Any) -> None:
        """Update the internal attributes with new data in place."""

        new_obj_dct = self.model_dump()
        new_obj_dct.update(data)
        new_obj = self.model_validate(new_obj_dct)

        for k, v in new_obj.model_dump(exclude_unset=True).items():
            # exclude_unset avoids overwriting for instance known children that need to be retrieved separately
            _logger.debug('updating object data: %s => %s', k, v)
            setattr(self, k, getattr(new_obj, k))

    def serialize_for_api(self) -> dict[str, Any]:
        """Serialize the object for sending it to the Notion API."""

        def remove_unset(key: str, value: Any) -> Any:
            if is_unset(value):
                return None
            return value

        filtered_obj = pydantic_apply(self, remove_unset)
        # Notion API doesn't like "null" values
        return filtered_obj.model_dump(mode='json', exclude_none=True, by_alias=True)

    @classmethod
    def build(cls, *args: Any, **kwargs: Any) -> Self:
        """Use the standard constructur to build the instance. Will be overwritten for more complex types."""
        return cls(*args, **kwargs)


T = TypeVar('T', default=Any)  # ToDo: use new syntax in Python 3.12 and consider using default = in Python 3.13+


def _normalize_color(val: Color | UnsetType) -> Color:
    """Normalize unset colors to Color.DEFAULT.

    This is useful for ensuring consistent behavior when comparing objects. Notion API sometimes
    demands a color field to be `Unset` but then returns the default color, which can lead to
    unexpected behavior in equality checks and hashing.
    """
    if is_unset(val):
        return Color.DEFAULT
    return val


def _normalize_model(obj: T) -> T:
    """Normalize the model for comparison and hashing.

    !!! note

        We normalize the `color` field in some objects, since if it is `Unset`
        and has a default value of `Color.DEFAULT` in equality comparisons.
        We also ignore `id` fields here, e.g. in `Option` objects, since they
        are not relevant for equality and hashing.
    """

    def _recurse(obj: Any) -> Any:
        if isinstance(obj, GenericObject):
            # Create a copy to avoid modifying the original
            obj_copy = obj.model_copy()
            for field_name in type(obj_copy).model_fields:
                field_value = getattr(obj_copy, field_name)
                if field_name in {'id', 'option_ids'}:
                    setattr(obj_copy, field_name, Unset)
                elif field_name == 'color' and is_unset(field_value):
                    setattr(obj_copy, field_name, _normalize_color(field_value))
                elif isinstance(obj, TypedObject) and obj.type == 'mention' and field_name == 'plain_text':
                    setattr(
                        obj_copy, field_name, Unset
                    )  # allows comparing offline-built mentions with UserRef to online ones
                else:
                    setattr(obj_copy, field_name, _recurse(field_value))
            return obj_copy
        if isinstance(obj, dict):
            return {k: _recurse(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple, set)):
            return type(obj)(_recurse(x) for x in obj)
        return obj

    return cast(T, _recurse(obj))


class UniqueObject(GenericObject):
    """A Notion object that has a unique ID.

    This is the base class for all Notion objects that have a unique identifier, i.e. `id`.

    !!! warning

        The `id` field is only set when the object is sent or retrieved from the API, not when created locally.
    """

    id: UUID | str | UnsetType = Field(union_mode='left_to_right', default=Unset)
    """`id` is an `UUID` if possible or a string (possibly not unique) depending on the object"""


class NotionObject(UniqueObject):
    """A top-level Notion API resource.

    Many objects in the Notion API follow a standard pattern with a `object` property, which
    defines the general object type, e.g. `page`, `database`, `user`, `block`, ...
    """

    object: str = Field(default=None)  # type: ignore # avoids mypy plugin errors as this is set in __init_subclass__
    """`object` is a string that identifies the general object type, e.g. `page`, `database`, `user`, `block`, ..."""

    request_id: UUID | None = None
    """`request_id` is a UUID that is used to track requests in the Notion API"""

    def __init_subclass__(cls, *, object: str | None = None, **kwargs: Any) -> None:  # noqa: A002
        super().__init_subclass__(**kwargs)

    @classmethod
    def __pydantic_init_subclass__(cls, *, object: str | None = None, **kwargs: Any) -> None:  # noqa: A002, PLW3201
        """Update `GenericObject` defaults for the named object.

        Needed since `model_fields` are not available during __init_subclass__
        See: https://github.com/pydantic/pydantic/issues/5369
        """
        super().__pydantic_init_subclass__(object=object, **kwargs)

        if object is not None:  # if None we inherit 'object' from the base class
            cls._set_field_default('object', default=object)

    @field_validator('object', mode='after')
    @classmethod
    def _verify_object_matches_expected(cls, val: str) -> str:
        """Make sure that the deserialized object matches the name in this class."""
        if (obj_field := cls.model_fields.get('object')) is not None:
            obj_attr = obj_field.default
        else:
            msg = 'Field `object` of Notion object is missing'
            raise ValueError(msg)

        if val != obj_attr:
            msg = f'Invalid object for {obj_attr} - {val}'
            raise ValueError(msg)

        return val


class ObjectRef(GenericObject):
    """A general-purpose object reference in the Notion API."""

    id: UUID

    @classmethod
    def build(cls, ref: ParentRef | GenericObject | UUID | str) -> ObjectRef:
        """Compose a reference to an object from the given reference.

        Strings may be either UUID's or URL's to Notion content.
        """

        match ref:
            case ObjectRef():
                return ref.model_copy(deep=True)
            case ParentRef() if isinstance(ref.value, UUID):
                # ParentRefs are typed objects with a nested UUID
                return cls.model_construct(id=ref.value)
            case GenericObject() if hasattr(ref, 'id'):
                # Re-compose the ObjectReference from the internal ID
                return cls.build(ref.id)
            case UUID():
                return cls.model_construct(id=ref)
            case str() if (id_str := extract_id(ref)) is not None:
                return cls.model_construct(id=UUID(id_str))
            case _:
                msg = f'Cannot interpret {ref} of type {type(ref)} as a reference to an object.'
                raise ValueError(msg)


class UserRef(NotionObject, object='user'):
    """Reference to a user, e.g. in `created_by`, `last_edited_by`, mentioning, unknown user, etc."""

    id: UUID

    @classmethod
    def build(cls, user_ref: User | str | UUID) -> UserRef:
        """Compose a PageRef from the given reference object."""
        ref = ObjectRef.build(user_ref)
        return UserRef.model_construct(id=ref.id)


class NotionEntity(NotionObject):
    """A materialized entity, which was created by a user."""

    id: UUID | UnsetType = Unset
    parent: SerializeAsAny[ParentRef] | UnsetType = Unset

    created_time: datetime | UnsetType = Unset
    created_by: UserRef | UnsetType = Unset

    last_edited_time: datetime | UnsetType = Unset


TO_co = TypeVar('TO_co', covariant=True, default=Any)  # ToDo: use new syntax in Python 3.12


class TypedObject(GenericObject, Generic[TO_co]):
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

    type: str = Field(default=None)  # type: ignore  # avoids mypy errors as this is set in __pydantic_init_subclass__
    """`type` is a string that identifies the specific object type, e.g. `heading_1`, `paragraph`, `equation`, ..."""
    _polymorphic_base: ClassVar[bool] = False
    _typemap: ClassVar[dict[str, builtins.type[TypedObject]]]

    def __init_subclass__(cls, *, type: str | None = None, polymorphic_base: bool = False, **kwargs: Any) -> None:  # noqa: A002
        super().__init_subclass__(**kwargs)
        cls._polymorphic_base = polymorphic_base

    @classmethod
    def __pydantic_init_subclass__(cls, *, type: str | None = None, **kwargs: Any) -> None:  # noqa: A002, PLW3201
        """Register the subtypes of the TypedObject subclass.

        This is needed since `model_fields` is not available during __init_subclass__.
        See: https://github.com/pydantic/pydantic/issues/5369
        """
        super().__pydantic_init_subclass__(type=type, **kwargs)
        type_name = cls.__name__ if type is None else type
        cls._register_type(type_name)

    @classmethod
    def _register_type(cls, name: str) -> None:
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

        _logger.debug('Registered new subtype: %s => %s', name, cls)
        cls._typemap[name] = cls

    @model_validator(mode='wrap')
    @classmethod
    def _resolve_type(cls, value: Any, handler: ValidatorFunctionWrapHandler) -> Any:
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
            if value.get('object') == 'user':
                return UserRef.model_construct(**value)
            else:
                msg = f"Missing 'type' in data {value}"
                raise ValueError(msg)

        sub_cls = cls._typemap.get(type_name)

        if sub_cls is None:
            msg = f'Unsupported sub-type: {type_name}'
            raise ValueError(msg)

        return sub_cls(**value)

    @classmethod
    def build(cls, *args: Any, **kwargs: Any) -> Self:
        """Build non-polymorphic instances of TypedObject by adding the proper `type` parameter."""
        if cls._polymorphic_base:
            msg = 'Cannot build instance of polymorphic base class directly.'
            raise ValueError(msg)

        kwargs['type'] = cls.model_fields['type'].default
        return cls(*args, **kwargs)

    @property
    def value(self) -> TO_co:
        """Return the nested object."""
        return cast(TO_co, getattr(self, self.type))

    @value.setter
    def value(self, val: TO_co) -> None:  # type: ignore[misc]  # breaking covariance
        """Set the nested object."""
        # we are breaking covariance here but going down the Protocol way didn't work out
        # either due to many limititations, e.g. @runtime_checkable not working with inheritance, etc.
        # This is still the most programmatic way it seems without adding too much complexity.
        setattr(self, self.type, val)


class ParentRef(TypedObject[T], ABC, polymorphic_base=True):
    """Reference another block as a parent.

    Notion API: [Parent Object](https://developers.notion.com/reference/parent-object)

    Note: This class is simply a placeholder for the typed concrete *Ref classes.
          Callers should always instantiate the intended concrete versions.
    """
