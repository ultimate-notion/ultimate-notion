"""Wrapper for various Notion API objects like parents, mentions, emojis & users.

Similar to other records, these object provide access to the primitive data structure
used in the Notion API.

For validation the Pydantic model fields specify if a field is optional or not.
Some fields are always set, e.g. `id`, when retrieving an object but must not be set
when sending the object to the Notion API in order to create the object.
To model this behavior, the default sentinel value `Unset` is used for those objects, e.g.
```
class SelectOption(GenericObject)
    id: str | UnsetType = Unset
```
Be aware that this is important when updating to differentiate between the actual set
values from default/unset values.
"""

from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod
from copy import deepcopy
from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID

import pendulum as pnd
from pydantic import Field, SerializeAsAny
from typing_extensions import TypeVar

from ultimate_notion.obj_api.core import (
    GenericObject,
    NotionEntity,
    NotionObject,
    TypedObject,
    Unset,
    UnsetType,
    _normalize_color,
    extract_id,
    raise_unset,
)
from ultimate_notion.obj_api.enums import BGColor, Color, FileUploadStatus
from ultimate_notion.utils import DateTimeOrRange, parse_dt_str

if TYPE_CHECKING:
    from ultimate_notion.obj_api.blocks import Block, Database, Page


class SelectOption(GenericObject):
    """Options for select & multi-select objects.

    Specifying no color will result in the default color being used, i.e. `Color.DEFAULT`, which is a light grey.
    Note that colors can't be changed after they are set.
    """

    name: str
    id: str | UnsetType = Unset  # According to docs: "These are sometimes, but not always, UUIDs."
    color: Color | UnsetType = Unset  # Leave this as Unset when overwriting an option as colors can't be changed
    description: list[RichTextBaseObject] | None = None  # ToDo: Undocumented in the Notion API

    @classmethod
    def build(cls, name: str, color: Color = Color.DEFAULT) -> SelectOption:
        """Create a `SelectOption` object from the given name and color."""
        return cls.model_construct(name=name, color=color)

    def __eq__(self, other: object) -> bool:
        """Compare SelectOption objects by all attributes except id."""
        if not isinstance(other, SelectOption):
            return False

        my_color, other_color = _normalize_color(self.color), _normalize_color(other.color)
        return self.name == other.name and my_color == other_color and self.description == other.description

    def __hash__(self) -> int:
        """Return a hash of the SelectOption based on name, color, and description."""
        # Convert description list to tuple for hashing if it exists
        desc_tuple = tuple(self.description) if self.description else None
        return hash((self.name, self.color, desc_tuple))


class SelectGroup(GenericObject):
    """Group of options for status objects."""

    name: str
    id: str | UnsetType = Unset  # According to docs: "These are sometimes, but not always, UUIDs."
    color: Color | UnsetType = Unset
    option_ids: list[str] = Field(default_factory=list)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SelectGroup):
            return False
        # we don't compare option_ids since we might not always have them (Status property can't be created)
        my_color, other_color = _normalize_color(self.color), _normalize_color(other.color)
        return self.name == other.name and my_color == other_color

    def __hash__(self) -> int:
        return hash((self.name, self.color))


class MentionMixin(ABC):
    """Mixin for objects that can be mentioned in Notion.

    This mixin adds a `build_mention` property to the object, which can be used to
    reference the object in a mention.
    """

    @abstractmethod
    def build_mention(self, style: Annotations | None = None) -> MentionObject:
        """Return a mention object for this object."""


class DateRange(GenericObject, MentionMixin):
    """A Notion date range, with an optional end date."""

    start: dt.date | dt.datetime
    end: dt.date | dt.datetime | None = None
    time_zone: str | None = None

    @classmethod
    def build(cls, dt_spec: str | DateTimeOrRange) -> DateRange:
        """Compose a DateRange object from the given properties."""

        if isinstance(dt_spec, str):
            dt_spec = parse_dt_str(dt_spec)

        match dt_spec:
            case pnd.Interval():
                return cls.model_construct(
                    time_zone=dt_spec.start.timezone_name if isinstance(dt_spec.start, pnd.DateTime) else None,
                    start=dt_spec.start,
                    end=dt_spec.end,
                )

            case pnd.DateTime():
                return cls.model_construct(time_zone=dt_spec.timezone_name, start=dt_spec.naive(), end=None)

            case dt.datetime():
                # We don't trust the timezone of naive datetime and convert to UTC
                return cls.model_construct(time_zone='UTC', start=dt_spec.astimezone(dt.timezone.utc), end=None)

            case pnd.Date() | dt.date():
                return cls.model_construct(time_zone=None, start=dt_spec, end=None)

            case _:
                msg = f"Unsupported type for 'dt_spec': {type(dt_spec)}"
                raise TypeError(msg)

    def build_mention(self, style: Annotations | None = None) -> MentionObject:
        return MentionDate.build_mention_from(self, style=style)

    def to_pendulum(self) -> DateTimeOrRange:
        """Convert the DateRange to a pendulum object."""
        # self.time_zone is None for pure dates.
        start = str(self.start) if self.time_zone is None else f'{self.start} {self.time_zone}'
        if self.end is None:
            return parse_dt_str(start)
        else:
            end = str(self.end) if self.time_zone is None else f'{self.end} {self.time_zone}'
            start_dt, end_dt = parse_dt_str(start), parse_dt_str(end)

            if isinstance(start_dt, pnd.Date) and isinstance(end_dt, pnd.Date):
                return pnd.Interval(start=start_dt, end=end_dt)
            elif isinstance(start_dt, pnd.DateTime) and isinstance(end_dt, pnd.DateTime):
                return pnd.Interval(start=start_dt, end=end_dt)
            else:
                msg = f"Unsupported type for 'start' or 'end': {type(start)}, {type(end)}"
                raise TypeError(msg)

    def __str__(self) -> str:
        # ToDo: Implement the possibility to configure date format globally, maybe in the config?
        date_str = str(self.start) if self.end is None else f'{self.start} → {self.end}'
        return f'@{date_str}'  # we add the @ as Notion does it too


class LinkObject(GenericObject):
    """Reference a URL."""

    type: str = 'url'
    url: str


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


def get_uuid(obj: str | UUID | ParentRef | NotionObject | BlockRef) -> UUID:
    """Retrieves a UUID from an object reference.

    Only meant for internal use.
    """
    return ObjectRef.build(obj).id


T = TypeVar('T', default=Any)


class ParentRef(TypedObject[T], ABC, polymorphic_base=True):
    """Reference another block as a parent.

    Notion API: [Parent Object](https://developers.notion.com/reference/parent-object)

    Note: This class is simply a placeholder for the typed concrete *Ref classes.
          Callers should always instantiate the intended concrete versions.
    """


class DatabaseRef(ParentRef[UUID], type='database_id'):
    """Reference a database."""

    database_id: UUID

    @classmethod
    def build(cls, db_ref: Database | str | UUID) -> DatabaseRef:
        """Compose a DatabaseRef from the given reference object."""
        ref = ObjectRef.build(db_ref)
        return DatabaseRef.model_construct(database_id=ref.id)


class PageRef(ParentRef[UUID], type='page_id'):
    """Reference a page."""

    page_id: UUID

    @classmethod
    def build(cls, page_ref: Page | str | UUID) -> PageRef:
        """Compose a PageRef from the given reference object."""
        ref = ObjectRef.build(page_ref)
        return PageRef.model_construct(page_id=ref.id)


class BlockRef(ParentRef[UUID], type='block_id'):
    """Reference a block."""

    block_id: UUID

    @classmethod
    def build(cls, block_ref: Block | str | UUID) -> BlockRef:
        """Compose a BlockRef from the given reference object."""
        ref = ObjectRef.build(block_ref)
        return BlockRef.model_construct(block_id=ref.id)


class WorkspaceRef(ParentRef[bool], type='workspace'):
    """Reference the workspace."""

    workspace: bool = True


class CommentRef(ParentRef[UUID], type='comment_id'):
    """Reference a comment."""

    comment_id: UUID

    @classmethod
    def build(cls, comment_ref: Comment | str | UUID) -> CommentRef:
        """Compose a CommentRef from the given reference object."""
        ref = ObjectRef.build(comment_ref)
        return CommentRef.model_construct(comment_id=ref.id)


class UserRef(NotionObject, object='user'):
    """Reference to a user, e.g. in `created_by`, `last_edited_by`, mentioning, etc."""

    id: UUID

    @classmethod
    def build(cls, user_ref: User | str | UUID) -> UserRef:
        """Compose a PageRef from the given reference object."""
        ref = ObjectRef.build(user_ref)
        return UserRef.model_construct(id=ref.id)


# ToDo: Use new syntax when requires-python >= 3.12
GO_co = TypeVar('GO_co', bound=GenericObject, default=GenericObject, covariant=True)


class User(TypedObject[GO_co], UserRef, MentionMixin, polymorphic_base=True):
    """Represents a User in Notion."""

    name: str | None = None
    avatar_url: str | None = None

    def build_mention(self, style: Annotations | None = None) -> MentionObject:
        return MentionUser.build_mention_from(self, style=style)


class PersonTypeData(GenericObject):
    """Type data for a `Person`."""

    email: str | None = None


class Person(User[PersonTypeData], type='person'):
    """Represents a Person in Notion."""

    person: PersonTypeData = Field(default_factory=PersonTypeData)


class WorkSpaceLimits(GenericObject):
    """Limits for a Notion workspace."""

    max_file_upload_size_in_bytes: int | None = None


class UnknownUserTypeData(GenericObject):
    """Type data for an `UnknownUser`."""


class UnknownUser(User[UnknownUserTypeData], type='unknown'):
    """Represents an unknown user in Notion.

    This is a unofficial placeholder for a user that is not recognized by the API.
    """

    name: Literal['Unknown User'] = 'Unknown User'
    unknown: UnknownUserTypeData = Field(default_factory=UnknownUserTypeData)


class Annotations(GenericObject):
    """Style information for RichTextObject's."""

    bold: bool = False
    italic: bool = False
    strikethrough: bool = False
    underline: bool = False
    code: bool = False
    # `Unset` for instance for code blocks to have flexible coloring. Will be replaced by Color.DEFAULT.
    color: Color | BGColor | UnsetType = Unset


MAX_TEXT_OBJECT_SIZE = 2_000
"""The max text size according to the Notion API is 2000 characters."""


class RichTextBaseObject(TypedObject[GenericObject], polymorphic_base=True):
    """Base class for Notion rich text elements."""

    plain_text: str
    href: str | None = None
    annotations: Annotations | UnsetType = Unset


def rich_text_to_str(rich_texts: list[RichTextBaseObject]) -> str:
    """Convert a list of rich texts to plain text."""
    return ''.join(rich_text.plain_text for rich_text in rich_texts)


class TextObject(RichTextBaseObject, type='text'):
    """Notion text element."""

    class TypeData(GenericObject):
        content: str
        link: LinkObject | None = None

    text: TypeData

    @classmethod
    def build(cls, text: str, *, href: str | None = None, style: Annotations | None = None) -> TextObject:
        """Compose a TextObject from the given properties.

        Args:
            text: the plain text of this object
            href: optional link for this object
            style: optional annotations for styling this text
        """
        link = LinkObject(url=href) if href else None
        nested = cls.TypeData(content=text, link=link)

        return cls.model_construct(
            plain_text=text,
            text=nested,
            href=href,
            annotations=Unset if style is None else deepcopy(style),
        )


class EquationObject(RichTextBaseObject, type='equation'):
    """Notion equation element."""

    class TypeData(GenericObject):
        expression: str

    equation: TypeData

    @classmethod
    def build(cls, expression: str, *, href: str | None = None, style: Annotations | None = None) -> EquationObject:
        """Compose a TextObject from the given properties.

        Args:
            expression: expression
            href: optional link for this object
            style: optional annotations for styling this text
        """
        return cls.model_construct(
            plain_text=expression,
            equation=cls.TypeData(expression=expression),
            href=href,
            annotations=Unset if style is None else deepcopy(style),
        )


class MentionBase(TypedObject[GO_co], ABC, polymorphic_base=True):
    """Base class for typed `Mention` objects.

    Note that this class is different to `MentionMixin`, which is used to
    provide a `build_mention` method for objects that can be mentioned in Notion.
    Here, we have a *class method* to build a mention object *from* the target object.
    """

    @classmethod
    @abstractmethod
    def build_mention_from(cls, *args: Any, **kwargs: Any) -> MentionObject:
        """Build a mention object for this type of mention from the actual target object."""


class MentionObject(RichTextBaseObject, type='mention'):
    """Notion mention element."""

    mention: SerializeAsAny[MentionBase]


class MentionUser(MentionBase[User | UserRef], type='user'):
    """Nested user data for `Mention` properties."""

    user: SerializeAsAny[User | UserRef]

    @classmethod
    def build_mention_from(cls, user: User, *, style: Annotations | None = None) -> MentionObject:
        # When creating a user mention, we need to send only the id, not the full object.
        user_ref = UserRef.build(user)
        mention = cls.model_construct(user=user_ref)
        # note that `href` is always `None` for user mentions, also we prepend the '@' to mimic server side
        return MentionObject.model_construct(
            plain_text=f'@{user.name}',
            href=None,
            annotations=Unset if style is None else deepcopy(style),
            mention=mention,
        )


class MentionLinkTypeData(GenericObject):
    """Type data for a `MentionLink`."""

    href: str
    title: str


class MentionLink(MentionBase, type='link_mention'):
    """Nested url data for `Mention` properties."""

    link_mention: MentionLinkTypeData

    @classmethod
    def build_mention_from(cls, href: str, title: str, *, style: Annotations | None = None) -> MentionObject:
        """Build a mention object for this type of mention from the actual target object."""
        mention = cls.model_construct(link_mention=MentionLinkTypeData(href=href, title=title))
        return MentionObject.model_construct(
            plain_text=title,
            href=None,
            annotations=Unset if style is None else deepcopy(style),
            mention=mention,
        )


class BotTypeData(GenericObject):
    """Type data for a `Bot`."""

    owner: WorkspaceRef | MentionUser | None = None
    workspace_name: str | None = None
    workspace_limits: WorkSpaceLimits = Field(default_factory=WorkSpaceLimits)


class Bot(User[BotTypeData], type='bot'):
    """Represents a Bot in Notion."""

    # Even if stated otherwise in the docs, `bot` type data is optional and for instance
    # not present when a new page is created by a bot within a database with a `CreatedBy` Property.
    # For ease of use, we include a default instance of the bot type data.
    bot: BotTypeData = Field(default_factory=BotTypeData)


class MentionPage(MentionBase[ObjectRef], type='page'):
    """Nested page data for `Mention` properties."""

    page: SerializeAsAny[ObjectRef]

    @classmethod
    def build_mention_from(cls, page: Page, *, style: Annotations | None = None) -> MentionObject:
        page_ref = ObjectRef.build(page)
        mention = cls.model_construct(page=page_ref)
        # note that `href` is always `None` for page mentions
        return MentionObject.model_construct(
            plain_text=rich_text_to_str(page.title),
            href=None,
            annotations=Unset if style is None else deepcopy(style),
            mention=mention,
        )


class MentionDatabase(MentionBase[ObjectRef], type='database'):
    """Nested database information for `Mention` properties."""

    database: SerializeAsAny[ObjectRef]

    @classmethod
    def build_mention_from(cls, db: Database, *, style: Annotations | None = None) -> MentionObject:
        db_ref = ObjectRef.build(db)
        mention = cls.model_construct(database=db_ref)
        # note that `href` is always `None` for database mentions
        db_title = raise_unset(db.title)
        return MentionObject.model_construct(
            plain_text=rich_text_to_str(db_title),
            ref=None,
            annotations=Unset if style is None else deepcopy(style),
            mention=mention,
        )


class MentionDate(MentionBase[DateRange], type='date'):
    """Nested date data for `Mention` properties."""

    date: DateRange

    @classmethod
    def build_mention_from(cls, date_range: DateRange, *, style: Annotations | None = None) -> MentionObject:
        mention = cls.model_construct(date=date_range)
        # note that `href` is always `None` for date mentions
        return MentionObject.model_construct(
            plain_text=str(date_range),
            ref=None,
            annotations=Unset if style is None else deepcopy(style),
            mention=mention,
        )


class MentionLinkPreviewTypeData(GenericObject):
    """Type data for a `MentionLinkPreview`."""

    url: str


class MentionLinkPreview(MentionBase, type='link_preview'):
    """Nested url data for `Mention` properties.

    !!! warning

        Link previews cannot be created via the API.
    """

    link_preview: MentionLinkPreviewTypeData

    @classmethod
    def build_mention_from(cls, url: str, *, style: Annotations | None = None) -> MentionObject:
        """Build a mention object for this type of mention from the actual target object."""
        mention = cls.model_construct(link_preview=MentionLinkPreviewTypeData.model_construct(url=url))
        return MentionObject.model_construct(
            plain_text=url,
            href=None,
            annotations=Unset if style is None else deepcopy(style),
            mention=mention,
        )


class MentionTemplateData(TypedObject[GenericObject]):
    """Nested template data for `Mention` properties."""


class MentionTemplate(MentionBase[MentionTemplateData], type='template_mention'):
    """Nested template data for `Mention` properties."""

    template_mention: SerializeAsAny[MentionTemplateData]


class MentionTemplateDate(MentionTemplateData, type='template_mention_date'):
    """Nested date template data for `Mention` properties."""

    template_mention_date: str


class MentionTemplateUser(MentionTemplateData, type='template_mention_user'):
    """Nested user template data for `Mention` properties."""

    template_mention_user: str


class EmojiObject(TypedObject[GenericObject], type='emoji'):
    """A Notion emoji object.

    Within text an emoji is represented as unicode string.
    """

    emoji: str

    @classmethod
    def build(cls, emoji: str) -> EmojiObject:
        """Compose an EmojiObject from the given emoji string."""
        return EmojiObject.model_construct(emoji=emoji)


class CustomEmojiObjectTypeData(GenericObject):
    """Type data for a `CustomEmojiObject`."""

    id: UUID
    name: str
    url: str


class CustomEmojiObject(MentionBase[CustomEmojiObjectTypeData], MentionMixin, type='custom_emoji'):
    """A Notion custom emoji object.

    Within text a custom emoji is represented as a mention. For this
    reason there is no `MentionCustomEmoji` class, but the `CustomEmojiObject`
    itself can be used to build a mention object.
    """

    custom_emoji: CustomEmojiObjectTypeData

    @classmethod
    def build_mention_from(cls, custom_emoji: CustomEmojiObject, *, style: Annotations | None = None) -> MentionObject:
        mention = cls.model_construct(custom_emoji=custom_emoji.custom_emoji)
        # note that `href` is always `None` for custom emoji mentions
        return MentionObject.model_construct(
            plain_text=f':{custom_emoji.custom_emoji.name}:',
            href=None,
            annotations=Unset if style is None else deepcopy(style),
            mention=mention,
        )

    def build_mention(self, style: Annotations | None = None) -> MentionObject:
        """Build a mention object for this custom emoji."""
        return self.__class__.build_mention_from(self, style=style)


class FileObject(TypedObject[GO_co], polymorphic_base=True):
    """A Notion file object.

    Depending on the context, a FileObject may require a name (such as in the `Files` property) or may have a caption,
    for instance when used within a File block, which makes the object hierarchy complex. Thus, we simply allow `name`
    and `caption` to be optional. It is the responsibility of the caller to set `name` if required by the API.
    """

    name: str | None = None
    caption: list[SerializeAsAny[RichTextBaseObject]] | None = None


class HostedTypedata(GenericObject):
    """Type data for `HostedFile`."""

    url: str
    expiry_time: dt.datetime | None = None


class HostedFile(FileObject[HostedTypedata], type='file'):
    """A Notion file object."""

    file: HostedTypedata

    @classmethod
    def build(
        cls,
        url: str,
        *,
        name: str | None = None,
        caption: list[RichTextBaseObject] | None = None,
        expiry_time: dt.datetime | None = None,
    ) -> HostedFile:
        """Create a new `HostedFile` from the given URL."""
        return cls.model_construct(name=name, caption=caption, file=HostedTypedata(url=url, expiry_time=expiry_time))


class ExternalFileTypeData(GenericObject):
    """Type data for `ExternalFile`."""

    url: str


class ExternalFile(FileObject[ExternalFileTypeData], type='external'):
    """A Notion external file object."""

    external: ExternalFileTypeData

    @classmethod
    def build(
        cls, url: str, *, name: str | None = None, caption: list[RichTextBaseObject] | None = None
    ) -> ExternalFile:
        """Create a new `ExternalFile` from the given URL."""
        return cls.model_construct(name=name, caption=caption, external=ExternalFileTypeData(url=url))


class UploadedFileTypeData(GenericObject):
    """Type data for `UploadedFile`."""

    id: UUID


class UploadedFile(FileObject[UploadedFileTypeData], type='file_upload'):
    """A Notion uploaded file object. The result of completed FileUpload"""

    file_upload: UploadedFileTypeData

    @classmethod
    def build(cls, id: UUID) -> UploadedFile:  # noqa: A002
        """Create a new `UploadedFile` from the given ID."""
        return cls.model_construct(file_upload=UploadedFileTypeData(id=id))


class FileImportTypeData(GenericObject):
    """Type data for `FileImportSuccess` and `FileImportError`.

    For ease of use, the parameters of success and error are combined into a single class.
    """

    type: str | None = None
    code: str | None = None
    message: str | None = None
    parameter: str | None = None
    status_code: int | None = None


class FileImportSuccess(TypedObject[GenericObject], type='success'):
    """Result of a successful file import operation."""

    imported_time: dt.datetime | None = None
    success: FileImportTypeData


class FileImportError(TypedObject[GenericObject], type='error'):
    """Result of a failed file import operation."""

    imported_time: dt.datetime | None = None
    error: FileImportTypeData


class FileUpload(NotionObject, object='file_upload'):
    """A Notion file upload object.

    This object is used to handle the process of uploading a file to Notion.
    """

    class NumberOfParts(GenericObject):
        """Number of parts for the file upload."""

        total: int
        sent: int

    id: UUID
    created_time: dt.datetime
    last_edited_time: dt.datetime
    expiry_time: dt.datetime | None = None
    status: FileUploadStatus
    filename: str | None = None
    content_type: str | None = None
    content_length: int | None = None
    number_of_parts: NumberOfParts | None = None
    upload_url: str | None = None
    complete_url: str | None = None
    file_import_result: FileImportSuccess | FileImportError | None = None
    archived: bool  # undocumented but sent by the API
    created_by: User  # undocumented but sent by the API


class Comment(NotionEntity, object='comment'):
    """A Notion comment object."""

    class TypeData(GenericObject):
        type: str  # This is strangely always `integration`, even if set by a user
        resolved_name: str  # This always the workspace name

    discussion_id: UUID
    rich_text: list[RichTextBaseObject]
    display_name: TypeData
