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

import datetime as dt
from abc import ABC, abstractmethod
from copy import deepcopy
from typing import TYPE_CHECKING, Literal
from uuid import UUID

import pendulum as pnd
from pydantic import Field, SerializeAsAny
from typing_extensions import Self

from ultimate_notion.obj_api.core import GenericObject, NotionObject, TypedObject, extract_id
from ultimate_notion.obj_api.enums import BGColor, Color

if TYPE_CHECKING:
    from ultimate_notion.obj_api.blocks import Block, Database, Page


class SelectOption(GenericObject):
    """Options for select & multi-select objects."""

    name: str
    id: str = None  # type: ignore  # According to docs: "These are sometimes, but not always, UUIDs."
    color: Color = Color.DEFAULT
    description: list[RichTextBaseObject] | None = None  # ToDo: Undocumented in the Notion API

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


class MentionMixin(ABC):
    """Mixin for objects that can be mentioned in Notion.

    This mixin adds a `mention` property to the object, which can be used to
    reference the object in a mention.
    """

    @abstractmethod
    def build_mention(self, style: Annotations | None = None) -> MentionObject:
        """Return a mention object for this object."""
        ...


class DateRange(GenericObject, MentionMixin):
    """A Notion date range, with an optional end date."""

    start: dt.date | dt.datetime
    end: dt.date | dt.datetime | None = None
    time_zone: str | None = None

    @classmethod
    def build(cls, dt_spec: dt.datetime | dt.date | pnd.Interval) -> Self:
        """Compose a DateRange object from the given properties."""

        if isinstance(dt_spec, pnd.Interval):
            time_zone = dt_spec.start.timezone_name if isinstance(dt_spec.start, pnd.DateTime) else None
            start = dt_spec.start
            end = dt_spec.end
        elif isinstance(dt_spec, pnd.DateTime):
            time_zone = dt_spec.timezone_name
            start = dt_spec.naive()
            end = None
        elif isinstance(dt_spec, pnd.Date):
            time_zone = None
            start = dt_spec
            end = None
        elif isinstance(dt_spec, dt.datetime):
            # we just don't trust the timezone of the naive datetime and convert to utc
            time_zone = 'UTC'
            start = dt_spec.astimezone(dt.timezone.utc)
            end = None
        elif isinstance(dt_spec, dt.date):
            time_zone = None
            start = dt_spec
            end = None
        else:
            msg = f"Unsupported type for 'dt_spec': {type(dt_spec)}"
            raise TypeError(msg)
        return cls.model_construct(start=start, end=end, time_zone=time_zone)

    def build_mention(self, style: Annotations | None = None) -> MentionObject:
        return MentionDate.build(self, style=style)

    def to_pendulum(self) -> pnd.DateTime | pnd.Date | pnd.Interval:
        """Convert the DateRange to a pendulum object."""
        if self.time_zone is None:
            if self.end is None:
                return pnd.instance(self.start)
            else:
                return pnd.Interval(start=pnd.instance(self.start), end=pnd.instance(self.end))
        else:
            pnd_start = pnd.instance(self.start)
            pnd_start = pnd_start.in_tz(self.time_zone) if isinstance(pnd_start, pnd.DateTime) else pnd_start
            if self.end is None:
                return pnd_start
            else:
                pnd_end = pnd.instance(self.end)
                pnd_end = pnd_end.in_tz(self.time_zone) if isinstance(pnd_end, pnd.DateTime) else pnd_end
                return pnd.Interval(start=pnd_start, end=pnd_end)

    def __str__(self) -> str:
        # ToDo: Implement the possibility to configure date format globally, maybe in the config?
        date_str = str(self.start) if self.end is None else f'{self.start} → {self.end}'
        return f'@{date_str}'  # we add the @ as Notion does it too


class LinkObject(GenericObject):
    """Reference a URL."""

    type: str = 'url'
    url: str = None  # type: ignore


class ObjectReference(GenericObject):
    """A general-purpose object reference in the Notion API."""

    id: UUID

    @classmethod
    def build(cls, ref: ParentRef | GenericObject | UUID | str) -> Self:
        """Compose an ObjectReference from the given reference.

        `ref` may be a `UUID`, `str`, `ParentRef` or `GenericObject` with an `id`.

        Strings may be either UUID's or URL's to Notion content.
        """

        if isinstance(ref, cls):
            return ref.model_copy(deep=True)

        if isinstance(ref, ParentRef):
            # ParentRef's are typed-objects with a nested UUID
            return cls.model_construct(id=ref.value)

        if isinstance(ref, GenericObject) and hasattr(ref, 'id'):
            # re-compose the ObjectReference from the internal ID
            return cls.build(ref.id)

        if isinstance(ref, UUID):
            return cls.model_construct(id=ref)

        if isinstance(ref, str) and (id_str := extract_id(ref)) is not None:
            return cls.model_construct(id=UUID(id_str))

        msg = f'Cannot interpret {ref} of type {type(ref)} as reference to an object.'
        raise ValueError(msg)


def get_uuid(obj: str | UUID | ParentRef | NotionObject | BlockRef) -> UUID:
    """Retrieves a UUID from an object reference.

    Only meant for internal use.
    """
    return ObjectReference.build(obj).id


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
    def build(cls, block_ref: Block | str | UUID) -> BlockRef:
        """Compose a BlockRef from the given reference object."""
        ref = ObjectReference.build(block_ref)
        return BlockRef.model_construct(block_id=ref.id)


class WorkspaceRef(ParentRef, type='workspace'):
    """Reference the workspace."""

    workspace: bool = True


class UserRef(NotionObject, object='user'):
    """Reference to a user, e.g. in `created_by`, `last_edited_by`, mentioning, etc."""


class User(UserRef, TypedObject, MentionMixin, polymorphic_base=True):
    """Represents a User in Notion."""

    id: UUID = None  # type: ignore
    name: str | None = None
    avatar_url: str | None = None

    def build_mention(self, style: Annotations | None = None) -> MentionObject:
        return MentionUser.build(self, style=style)


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

    This is a unofficial placeholder for a user that is not recognized by the API.
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
    color: Color | BGColor = Color.DEFAULT


class RichTextBaseObject(TypedObject, polymorphic_base=True):
    """Base class for Notion rich text elements."""

    plain_text: str
    href: str | None = None
    annotations: Annotations | None = None


def rich_text_to_str(rich_texts: list[RichTextBaseObject]) -> str:
    """Convert a list of rich texts to plain text."""
    return ''.join(rich_text.plain_text for rich_text in rich_texts)


class TextObject(RichTextBaseObject, type='text'):
    """Notion text element."""

    class TypeData(GenericObject):
        content: str = None  # type: ignore
        link: LinkObject | None = None

    text: TypeData = TypeData()

    @classmethod
    def build(cls, text: str, *, href: str | None = None, style: Annotations | None = None) -> Self:
        """Compose a TextObject from the given properties.

        Args:
            text: the plain text of this object
            href: optional link for this object
            style: optional annotations for styling this text
        """
        link = LinkObject(url=href) if href else None
        nested = cls.TypeData(content=text, link=link)
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

    @classmethod
    def build(cls, expression: str, *, href: str | None = None, style: Annotations | None = None) -> Self:
        """Compose a TextObject from the given properties.

        Args:
            expression: expression
            href: optional link for this object
            style: optional annotations for styling this text
        """
        style = deepcopy(style)
        return cls.model_construct(
            plain_text=expression, equation=cls.TypeData(expression=expression), href=href, annotations=style
        )


class MentionBase(TypedObject, polymorphic_base=True):
    """Base class for typed `Mention` objects."""


class MentionObject(RichTextBaseObject, type='mention'):
    """Notion mention element."""

    mention: SerializeAsAny[MentionBase]


class MentionUser(MentionBase, type='user'):
    """Nested user data for `Mention` properties."""

    user: SerializeAsAny[User]

    @classmethod
    def build(cls, user: User, *, style: Annotations | None = None) -> MentionObject:
        style = deepcopy(style)
        mention = cls.model_construct(user=user)
        # note that `href` is always `None` for user mentions
        return MentionObject.model_construct(plain_text=user.name, href=None, annotations=style, mention=mention)


class MentionPage(MentionBase, type='page'):
    """Nested page data for `Mention` properties."""

    page: SerializeAsAny[ObjectReference]

    @classmethod
    def build(cls, page: Page, *, style: Annotations | None = None) -> MentionObject:
        style = deepcopy(style)
        page_ref = ObjectReference.build(page)
        mention = cls.model_construct(page=page_ref)
        # note that `href` is always `None` for page mentions
        return MentionObject.model_construct(
            plain_text=rich_text_to_str(page.title), href=None, annotations=style, mention=mention
        )


class MentionDatabase(MentionBase, type='database'):
    """Nested database information for `Mention` properties."""

    database: SerializeAsAny[ObjectReference]

    @classmethod
    def build(cls, db: Database, *, style: Annotations | None = None) -> MentionObject:
        style = deepcopy(style)
        db_ref = ObjectReference.build(db)
        mention = cls.model_construct(database=db_ref)
        # note that `href` is always `None` for database mentions
        return MentionObject.model_construct(
            plain_text=rich_text_to_str(db.title), ref=None, annotations=style, mention=mention
        )


class MentionDate(MentionBase, type='date'):
    """Nested date data for `Mention` properties."""

    date: DateRange

    @classmethod
    def build(cls, date_range: DateRange, *, style: Annotations | None = None) -> MentionObject:
        style = deepcopy(style)
        mention = cls.model_construct(date=date_range)
        # note that `href` is always `None` for date mentions
        return MentionObject.model_construct(plain_text=str(date_range), ref=None, annotations=style, mention=mention)


class MentionLinkPreview(MentionBase, type='link_preview'):
    """Nested url data for `Mention` properties.

    !!! warning

        Link previews cannot be created via the API.
    """

    class TypeData(GenericObject):
        url: str

    link_preview: TypeData


class MentionTemplateData(TypedObject):
    """Nested template data for `Mention` properties."""


class MentionTemplate(MentionBase, type='template_mention'):
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
        expiry_time: dt.datetime | None = None

    file: TypeData

    @classmethod
    def build(
        cls,
        url: str,
        *,
        name: str | None = None,
        caption: list[RichTextBaseObject] | None = None,
        expiry_time: dt.datetime | None = None,
    ) -> Self:
        """Create a new `HostedFile` from the given URL."""
        return cls.model_construct(name=name, caption=caption, external=cls.TypeData(url=url, expiry_time=expiry_time))


class ExternalFile(FileObject, type='external'):
    """An external file object."""

    class TypeData(GenericObject):
        url: str

    external: TypeData

    @classmethod
    def build(cls, url: str, *, name: str | None = None, caption: list[RichTextBaseObject] | None = None) -> Self:
        """Create a new `ExternalFile` from the given URL."""
        return cls.model_construct(name=name, caption=caption, external=cls.TypeData(url=url))
