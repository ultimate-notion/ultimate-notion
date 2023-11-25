"""Wrapper for various Notion API objects like parents, mentions, emojis & users

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
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import Field

from ultimate_notion.obj_api.core import GenericObject, NotionObject, TypedObject
from ultimate_notion.obj_api.enums import BGColor, Color
from ultimate_notion.text import extract_id

if TYPE_CHECKING:
    from ultimate_notion.obj_api.blocks import Database, Page


class SelectOption(GenericObject):
    """Options for select & multi-select objects."""

    name: str
    id: str = None  # type: ignore  # noqa: A003  # According to docs: "These are sometimes, but not always, UUIDs."
    color: Color = Color.DEFAULT

    @classmethod
    def build(cls, name, color=Color.DEFAULT):
        """Create a `SelectOption` object from the given name and color."""
        return cls.model_construct(name=name, color=color)


class SelectGroup(GenericObject):
    """Group of options for status objects."""

    name: str
    id: str = None  # type: ignore  # noqa: A003  # According to docs: "These are sometimes, but not always, UUIDs."
    color: Color = Color.DEFAULT
    option_ids: list[str] = Field(default_factory=list)


class ObjectReference(GenericObject):
    """A general-purpose object reference in the Notion API."""

    id: UUID  # noqa: A003

    @classmethod
    def build(cls, ref):
        """Compose an ObjectReference from the given reference.

        `ref` may be a `UUID`, `str`, `ParentRef` or `GenericObject` with an `id`.

        Strings may be either UUID's or URL's to Notion content.
        """

        if isinstance(ref, cls):
            return ref.model_copy(deep=True)

        if isinstance(ref, ParentRef):
            # ParentRef's are typed-objects with a nested UUID
            return ObjectReference.model_construct(id=ref())

        if isinstance(ref, GenericObject) and hasattr(ref, 'id'):
            # re-compose the ObjectReference from the internal ID
            return ObjectReference.build(ref.id)

        if isinstance(ref, UUID):
            return ObjectReference.model_construct(id=ref)

        if isinstance(ref, str):
            ref = extract_id(ref)

            if ref is not None:
                return ObjectReference.model_construct(id=UUID(ref))

        msg = "Unrecognized 'ref' attribute"
        raise ValueError(msg)


# https://developers.notion.com/reference/parent-object
class ParentRef(TypedObject, ABC, polymorphic_base=True):
    """Reference another block as a parent.

    Note: This class is simply a placeholder for the typed concrete *Ref classes.
          Callers should always instantiate the intended concrete versions.
    """


class DatabaseRef(ParentRef, type='database_id'):
    """Reference a database."""

    database_id: UUID

    @classmethod
    def build(cls, db_ref: Database | str | UUID):
        """Compose a DatabaseRef from the given reference object."""
        ref = ObjectReference.build(db_ref)
        return DatabaseRef.model_construct(database_id=ref.id)


class PageRef(ParentRef, type='page_id'):
    """Reference a page."""

    page_id: UUID

    @classmethod
    def build(cls, page_ref: Page | str | UUID):
        """Compose a PageRef from the given reference object."""
        ref = ObjectReference.build(page_ref)
        return PageRef.model_construct(page_id=ref.id)


class BlockRef(ParentRef, type='block_id'):
    """Reference a block."""

    block_id: UUID

    @classmethod
    def build(cls, block_ref):
        """Compose a BlockRef from the given reference object.

        `block_ref` can be either a string, UUID, or block.
        """
        ref = ObjectReference[block_ref]
        return BlockRef.model_construct(block_id=ref.id)


class WorkspaceRef(ParentRef, type='workspace'):
    """Reference the workspace."""

    workspace: bool = True


class UserRef(NotionObject, object='user'):
    """Reference to a user, e.g. in `created_by`, `last_edited_by`, mentioning, etc."""


class UserType(str, Enum):
    """Available user types."""

    PERSON = 'person'
    BOT = 'bot'


class User(UserRef, TypedObject, polymorphic_base=True):
    """Represents a User in Notion."""

    name: str | None = None
    avatar_url: str | None = None


class Person(User, type='person'):
    """Represents a Person in Notion."""

    class _NestedData(GenericObject):
        email: str = None  # type: ignore

    person: _NestedData = _NestedData()


class Bot(User, type='bot'):
    """Represents a Bot in Notion."""

    class _NestedData(GenericObject):
        owner: WorkspaceRef = None  # type: ignore
        workspace_name: str = None  # type: ignore

    bot: _NestedData = _NestedData()


class EmojiObject(TypedObject, type='emoji'):
    """A Notion emoji object."""

    emoji: str

    @classmethod
    def build(cls, emoji):
        """Compose an EmojiObject from the given emoji string."""
        # Todo: convert string-based emoji to unicode here!
        return EmojiObject.model_construct(emoji=emoji)


class FileObject(TypedObject, polymorphic_base=True):
    """A Notion file object.

    Depending on the context, a FileObject may require a name (such as in the `Files`
    property).  This makes the object hierarchy difficult, so here we simply allow
    `name` to be optional. It is the responsibility of the caller to set `name` if
    required by the API.
    """

    name: str | None = None


class HostedFile(FileObject, type='file'):
    """A Notion file object."""

    class _NestedData(GenericObject):
        url: str
        expiry_time: datetime | None = None

    file: _NestedData


class ExternalFile(FileObject, type='external'):
    """An external file object."""

    class _NestedData(GenericObject):
        url: str

    external: _NestedData

    def __str__(self):
        """Return a string representation of this object."""
        name = super().__str__()

        if self.external and self.external.url:
            return f'![{name}]({self.external.url})'

        return name

    @classmethod
    def build(cls, url, name=None):
        """Create a new `ExternalFile` from the given URL."""
        return cls.model_construct(name=name, external=cls._NestedData(url=url))


class DateRange(GenericObject):
    """A Notion date range, with an optional end date."""

    start: date | datetime
    end: date | datetime | None = None
    time_zone: str | None = None


class Annotations(GenericObject):
    """Style information for RichTextObject's."""

    bold: bool = False
    italic: bool = False
    strikethrough: bool = False
    underline: bool = False
    code: bool = False
    color: BGColor = None  # type: ignore

    @property
    def is_plain(self):
        """Determine if any flags are set in this `Annotations` object.

        If all flags match their defaults, this is considered a "plain" style.
        """

        # XXX a better approach here would be to just compare all fields to defaults

        if self.bold:
            return False
        if self.italic:
            return False
        if self.strikethrough:
            return False
        if self.underline:
            return False
        if self.code:
            return False
        if self.color is not None:
            return False
        return True


class RichTextObject(TypedObject, polymorphic_base=True):
    """Base class for Notion rich text elements."""

    plain_text: str
    href: str | None = None
    annotations: Annotations | None = None

    # def __str__(self):
    #     """Return a string representation of this object."""

    #     if self.href is None:
    #         text = self.plain_text or ""
    #     elif self.plain_text is None or len(self.plain_text) == 0:
    #         text = f"({self.href})"
    #     else:
    #         text = f"[{self.plain_text}]({self.href})"

    #     if self.annotations:
    #         if self.annotations.bold:
    #             text = f"*{text}*"
    #         if self.annotations.italic:
    #             text = f"**{text}**"
    #         if self.annotations.underline:
    #             text = f"_{text}_"
    #         if self.annotations.strikethrough:
    #             text = f"~{text}~"
    #         if self.annotations.code:
    #             text = f"`{text}`"

    #     return text

    @classmethod
    def build(cls, text, href=None, style=None):
        """Compose a TextObject from the given properties.

        :param text: the plain text of this object
        :param href: an optional link for this object
        :param style: an optional Annotations object for this text
        """

        if text is None:
            return None

        # TODO convert markdown in text:str to RichText?

        style = deepcopy(style)

        return cls.model_construct(plain_text=text, href=href, annotations=style)


class LinkObject(GenericObject):
    """Reference a URL."""

    type: str = 'url'  # noqa: A003
    url: str = None  # type: ignore


class TextObject(RichTextObject, type='text'):
    """Notion text element."""

    class _NestedData(GenericObject):
        content: str = None  # type: ignore
        link: LinkObject | None = None

    text: _NestedData = _NestedData()

    @classmethod
    def build(cls, text: str, href: str | None = None, style: Annotations | None = None):
        """Compose a TextObject from the given properties.

        Args:
            text: the plain text of this object
            href: optional link for this object
            style: optional annotations for styling this text
        """

        if text is None:
            return None

        link = LinkObject(url=href) if href else None
        nested = TextObject._NestedData(content=text, link=link)
        style = deepcopy(style)

        return cls.model_construct(
            plain_text=text,
            text=nested,
            href=href,
            annotations=style,
        )


class EquationObject(RichTextObject, type='equation'):
    """Notion equation element."""

    class _NestedData(GenericObject):
        expression: str

    equation: _NestedData


class MentionData(TypedObject, polymorphic_base=True):
    """Base class for typed `Mention` data objects."""


class MentionObject(RichTextObject, type='mention'):
    """Notion mention element."""

    mention: MentionData


class MentionUser(MentionData, type='user'):
    """Nested user data for `Mention` properties."""

    user: UserRef

    @classmethod
    def build(cls, user: User):
        """Build a `Mention` object for the specified user.

        The `id` field must be set for the given User.  Other fields may cause errors
        if they do not match the specific type returned from the API.
        """

        return MentionObject.model_construct(plain_text=str(user), mention=MentionUser(user=user))


class MentionPage(MentionData, type='page'):
    """Nested page data for `Mention` properties."""

    page: ObjectReference

    @classmethod
    def build(cls, page_ref):
        """Build a `Mention` object for the specified page reference."""

        ref = ObjectReference[page_ref]

        return MentionObject.model_construct(plain_text=str(ref), mention=MentionPage(page=ref))


class MentionDatabase(MentionData, type='database'):
    """Nested database information for `Mention` properties."""

    database: ObjectReference

    @classmethod
    def build(cls, page):
        """Build a `Mention` object for the specified database reference."""

        ref = ObjectReference[page]

        return MentionObject.model_construct(plain_text=str(ref), mention=MentionDatabase(database=ref))


class MentionDate(MentionData, type='date'):
    """Nested date data for `Mention` properties."""

    date: DateRange

    @classmethod
    def build(cls, start, end=None):
        """Build a `Mention` object for the specified URL."""

        date_obj = DateRange(start=start, end=end)

        return MentionObject.model_construct(plain_text=str(date_obj), mention=MentionDate(date=date_obj))


class MentionLinkPreview(MentionData, type='link_preview'):
    """Nested url data for `Mention` properties.

    These objects cannot be created via the API.
    """

    class _NestedData(GenericObject):
        url: str

    link_preview: _NestedData


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