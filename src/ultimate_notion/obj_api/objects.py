"""Wrapper for various Notion API objects like parents, mentions, emojis & users.

Similar to other records, these object provide access to the primitive data structure
used in the Notion API as well as higher-level methods.

For validation the Pydantic model fields specify if a field is optional or not.
Some fields are always set, e.g. `id`, when retrieving an object but must not be set
when sending the object to the Notion API in order to create the object.
To model this behavior, the default value `None` is used for those objects, e.g.
```
class SelectOption(GenericObject)
    id: str = None  # type: ignore  # to make sure mypy doesn't complain
```
Also be aware that this is import when updating to differentiate actual set values
from default/unset values.
"""

from __future__ import annotations

from abc import ABC
from copy import deepcopy
from datetime import date, datetime
from typing import TYPE_CHECKING, Literal
from uuid import UUID

import pendulum as pnd
from pydantic import Field, SerializeAsAny
from typing_extensions import Self

from ultimate_notion.obj_api.core import GenericObject, NotionObject, TypedObject
from ultimate_notion.obj_api.enums import BGColor, Color
from ultimate_notion.text import extract_id

if TYPE_CHECKING:
    from ultimate_notion.obj_api.blocks import Database, Page


class SelectOption(GenericObject):
    """Options for select & multi-select objects."""

    name: str
    id: str = None  # type: ignore  # According to docs: "These are sometimes, but not always, UUIDs."
    color: Color = Color.DEFAULT
    description: str | None = None  # ToDo: Undocumented, could also be [RichTextObject]

    @classmethod
    def build(cls, name, color=Color.DEFAULT) -> Self:
        """Create a `SelectOption` object from the given name and color."""
        return cls.model_construct(name=name, color=color)


class SelectGroup(GenericObject):
    """Group of options for status objects."""

    name: str
    id: str = None  # type: ignore  # According to docs: "These are sometimes, but not always, UUIDs."
    color: Color = Color.DEFAULT
    option_ids: list[str] = Field(default_factory=list)


class DateRange(GenericObject):
    """A Notion date range, with an optional end date."""

    start: date | datetime
    end: date | datetime | None = None
    time_zone: str | None = None

    @classmethod
    def build(cls, dt: pnd.DateTime | pnd.Date | pnd.Interval) -> Self:
        """Compose a DateRange object from the given properties."""

        def to_naive_dt(dt: pnd.DateTime | pnd.Date | datetime | date) -> datetime | date:
            if type(dt) is datetime or type(dt) is date:
                return dt
            elif isinstance(dt, pnd.DateTime):
                dt = dt.naive()
                return datetime(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, dt.microsecond)  # noqa: DTZ001
            else:  # pnd.Date
                return date(dt.year, dt.month, dt.day)

        if isinstance(dt, pnd.Interval):
            time_zone = dt.start.timezone_name if isinstance(dt.start, pnd.DateTime) else None
            start = to_naive_dt(dt.start)
            end = to_naive_dt(dt.end)
        elif isinstance(dt, pnd.DateTime):
            time_zone = dt.timezone_name
            start = to_naive_dt(dt)
            end = None
        elif isinstance(dt, pnd.Date):
            time_zone = None
            start = to_naive_dt(dt)
            end = None
        else:
            msg = f"Unsupported type for 'dt': {type(dt)}"
            raise TypeError(msg)
        return cls.model_construct(start=start, end=end, time_zone=time_zone)

    def to_pendulum(self) -> pnd.DateTime | pnd.Date | pnd.Interval:
        """Convert the DateRange to a pendulum object."""
        if self.time_zone is None:
            if self.end is None:
                return pnd.instance(self.start)
            else:
                return pnd.Interval(start=pnd.instance(self.start), end=pnd.instance(self.end))
        else:  # noqa: PLR5501
            if self.end is None:
                return pnd.instance(self.start, tz=self.time_zone)
            else:
                return pnd.Interval(
                    start=pnd.instance(self.start, tz=self.time_zone),
                    end=pnd.instance(self.end, tz=self.time_zone),
                )


class LinkObject(GenericObject):
    """Reference a URL."""

    type: str = 'url'
    url: str = None  # type: ignore


class ObjectReference(GenericObject):
    """A general-purpose object reference in the Notion API."""

    id: UUID

    @classmethod
    def build(cls, ref: ParentRef | GenericObject | UUID | str) -> ObjectReference:
        """Compose an ObjectReference from the given reference.

        `ref` may be a `UUID`, `str`, `ParentRef` or `GenericObject` with an `id`.

        Strings may be either UUID's or URL's to Notion content.
        """

        if isinstance(ref, cls):
            return ref.model_copy(deep=True)

        if isinstance(ref, ParentRef):
            # ParentRef's are typed-objects with a nested UUID
            return ObjectReference.model_construct(id=ref.value)

        if isinstance(ref, GenericObject) and hasattr(ref, 'id'):
            # re-compose the ObjectReference from the internal ID
            return ObjectReference.build(ref.id)

        if isinstance(ref, UUID):
            return ObjectReference.model_construct(id=ref)

        if isinstance(ref, str) and (id_str := extract_id(ref)) is not None:
            return ObjectReference.model_construct(id=UUID(id_str))

        msg = f'Cannot interpret {ref} of type {type(ref)} as reference to an object.'
        raise ValueError(msg)


class ParentRef(TypedObject, ABC, polymorphic_base=True):
    """Reference another block as a parent.

    Notion API: [Parent Object](https://developers.notion.com/reference/parent-object)

    Note: This class is simply a placeholder for the typed concrete *Ref classes.
          Callers should always instantiate the intended concrete versions.
    """


class DatabaseRef(ParentRef, type='database_id'):
    """Reference a database."""

    database_id: UUID

    @classmethod
    def build(cls, db_ref: Database | str | UUID) -> DatabaseRef:
        """Compose a DatabaseRef from the given reference object."""
        ref = ObjectReference.build(db_ref)
        return DatabaseRef.model_construct(database_id=ref.id)


class PageRef(ParentRef, type='page_id'):
    """Reference a page."""

    page_id: UUID

    @classmethod
    def build(cls, page_ref: Page | str | UUID) -> PageRef:
        """Compose a PageRef from the given reference object."""
        ref = ObjectReference.build(page_ref)
        return PageRef.model_construct(page_id=ref.id)


class BlockRef(ParentRef, type='block_id'):
    """Reference a block."""

    block_id: UUID

    @classmethod
    def build(cls, block_ref: Page | str | UUID) -> BlockRef:
        """Compose a BlockRef from the given reference object."""
        ref = ObjectReference.build(block_ref)
        return BlockRef.model_construct(block_id=ref.id)


class WorkspaceRef(ParentRef, type='workspace'):
    """Reference the workspace."""

    workspace: bool = True


class UserRef(NotionObject, object='user'):
    """Reference to a user, e.g. in `created_by`, `last_edited_by`, mentioning, etc."""


class User(UserRef, TypedObject, polymorphic_base=True):
    """Represents a User in Notion."""

    id: UUID = None  # type: ignore
    name: str | None = None
    avatar_url: str | None = None


class Person(User, type='person'):
    """Represents a Person in Notion."""

    class TypeData(GenericObject):
        email: str = None  # type: ignore

    person: TypeData = TypeData()


class Bot(User, type='bot'):
    """Represents a Bot in Notion."""

    class TypeData(GenericObject):
        owner: WorkspaceRef = None  # type: ignore
        workspace_name: str = None  # type: ignore

    bot: TypeData = TypeData()


class UnknownUser(User, type='unknown'):
    """Represents an unknown user in Notion.

    This is a unoffical placeholder for a user that is not recognized by the API.
    """

    name: Literal['Unknown User'] = 'Unknown User'

    class TypeData(GenericObject): ...

    unknown: TypeData = TypeData()


class EmojiObject(TypedObject, type='emoji'):
    """A Notion emoji object."""

    emoji: str

    @classmethod
    def build(cls, emoji: str) -> EmojiObject:
        """Compose an EmojiObject from the given emoji string."""
        return EmojiObject.model_construct(emoji=emoji)


class Annotations(GenericObject):
    """Style information for RichTextObject's."""

    bold: bool = False
    italic: bool = False
    strikethrough: bool = False
    underline: bool = False
    code: bool = False
    color: BGColor = None  # type: ignore


class RichTextBaseObject(TypedObject, polymorphic_base=True):
    """Base class for Notion rich text elements."""

    plain_text: str
    href: str | None = None
    annotations: Annotations | None = None

    @classmethod
    def build(cls, text: str, href: str | None = None, style: Annotations | None = None) -> Self:
        """Compose a TextObject from the given properties.

        Args:
            text: the plain text of this object
            href: an optional link for this object
            style: an optional Annotations object for this text
        """
        style = deepcopy(style)
        return cls.model_construct(plain_text=text, href=href, annotations=style)


class TextObject(RichTextBaseObject, type='text'):
    """Notion text element."""

    class TypeData(GenericObject):
        content: str = None  # type: ignore
        link: LinkObject | None = None

    text: TypeData = TypeData()

    @classmethod
    def build(cls, text: str, href: str | None = None, style: Annotations | None = None) -> Self:
        """Compose a TextObject from the given properties.

        Args:
            text: the plain text of this object
            href: optional link for this object
            style: optional annotations for styling this text
        """

        if text is None:
            return None

        link = LinkObject(url=href) if href else None
        nested = TextObject.TypeData(content=text, link=link)
        style = deepcopy(style)

        return cls.model_construct(
            plain_text=text,
            text=nested,
            href=href,
            annotations=style,
        )


class EquationObject(RichTextBaseObject, type='equation'):
    """Notion equation element."""

    class TypeData(GenericObject):
        expression: str

    equation: TypeData


class MentionData(TypedObject, polymorphic_base=True):
    """Base class for typed `Mention` data objects."""


class MentionObject(RichTextBaseObject, type='mention'):
    """Notion mention element."""

    mention: MentionData


class MentionUser(MentionData, type='user'):
    """Nested user data for `Mention` properties."""

    user: User

    # ToDo: Check if this is needed!
    @classmethod
    def build(cls, user: User) -> MentionObject:
        """Build a `Mention` object for the specified user.

        The `id` field must be set for the given User.  Other fields may cause errors
        if they do not match the specific type returned from the API.
        """
        mention = MentionUser.model_construct(user=user)
        return MentionObject.model_construct(plain_text=str(user), mention=mention)


class MentionPage(MentionData, type='page'):
    """Nested page data for `Mention` properties."""

    page: ObjectReference

    # ToDo: Check if this is needed!
    @classmethod
    def build(cls, page_ref: PageRef) -> MentionObject:
        """Build a `Mention` object for the specified page reference."""

        ref = ObjectReference.build(page_ref)
        mention = MentionPage.model_construct(page=ref)
        return MentionObject.model_construct(plain_text=str(ref), mention=mention)


class MentionDatabase(MentionData, type='database'):
    """Nested database information for `Mention` properties."""

    database: ObjectReference

    # ToDo: Check if this is needed!
    @classmethod
    def build(cls, db_ref: DatabaseRef) -> MentionObject:
        """Build a `Mention` object for the specified database reference."""

        ref = ObjectReference.build(db_ref)
        mention = MentionDatabase.model_construct(database=ref)
        return MentionObject.model_construct(plain_text=str(ref), mention=mention)


class MentionDate(MentionData, type='date'):
    """Nested date data for `Mention` properties."""

    date: DateRange

    # ToDo: Check if this is needed!
    @classmethod
    def build(cls, start, end=None) -> MentionObject:
        """Build a `Mention` object for the specified URL."""

        date_obj = DateRange(start=start, end=end)
        mention = MentionDate.model_construct(date=date_obj)
        return MentionObject.model_construct(plain_text=str(date_obj), mention=mention)


class MentionLinkPreview(MentionData, type='link_preview'):
    """Nested url data for `Mention` properties.

    These objects cannot be created via the API.
    """

    class TypeData(GenericObject):
        url: str

    link_preview: TypeData


class MentionTemplateData(TypedObject):
    """Nested template data for `Mention` properties."""


class MentionTemplate(MentionData, type='template_mention'):
    """Nested template data for `Mention` properties."""

    template_mention: MentionTemplateData


class MentionTemplateDate(MentionTemplateData, type='template_mention_date'):
    """Nested date template data for `Mention` properties."""

    template_mention_date: str


class MentionTemplateUser(MentionTemplateData, type='template_mention_user'):
    """Nested user template data for `Mention` properties."""

    template_mention_user: str


class FileObject(TypedObject, polymorphic_base=True):
    """A Notion file object.

    Depending on the context, a FileObject may require a name (such as in the `Files`
    property). This makes the object hierarchy difficult, so here we simply allow
    `name` to be optional. It is the responsibility of the caller to set `name` if
    required by the API.
    """

    name: str | None = None
    caption: list[SerializeAsAny[RichTextBaseObject]] | None = None


class HostedFile(FileObject, type='file'):
    """A Notion file object."""

    class TypeData(GenericObject):
        url: str
        expiry_time: datetime | None = None

    file: TypeData


class ExternalFile(FileObject, type='external'):
    """An external file object."""

    class TypeData(GenericObject):
        url: str

    external: TypeData

    @classmethod
    def build(cls, url: str, name: str | None = None, caption: list[RichTextBaseObject] | None = None) -> Self:
        """Create a new `ExternalFile` from the given URL."""
        return cls.model_construct(name=name, caption=caption, external=cls.TypeData(url=url))
