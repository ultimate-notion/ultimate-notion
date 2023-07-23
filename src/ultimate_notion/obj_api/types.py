"""Wrapper for various Notion API data types like parents, mentions, emojis & users

Similar to other records, these object provide access to the primitive data structure
used in the Notion API as well as higher-level methods.
"""
from datetime import date, datetime
from uuid import UUID
from enum import Enum

from notion_client import helpers

from ultimate_notion.obj_api import util
from ultimate_notion.obj_api.core import GenericObject, TypedObject, NotionObject
from ultimate_notion.obj_api.text import RichTextObject


class ObjectReference(GenericObject):
    """A general-purpose object reference in the Notion API."""

    id: UUID

    @classmethod
    def __compose__(cls, ref):
        """Compose an ObjectReference from the given reference.

        `ref` may be a `UUID`, `str`, `ParentRef` or `GenericObject` with an `id`.

        Strings may be either UUID's or URL's to Notion content.
        """

        if isinstance(ref, cls):
            return ref.copy(deep=True)

        if isinstance(ref, ParentRef):
            # ParentRef's are typed-objects with a nested UUID
            return ObjectReference(id=ref())

        if isinstance(ref, GenericObject) and hasattr(ref, "id"):
            # re-compose the ObjectReference from the internal ID
            return ObjectReference[ref.id]

        if isinstance(ref, UUID):
            return ObjectReference(id=ref)

        if isinstance(ref, str):
            ref = util.extract_id_from_string(ref)

            if ref is not None:
                return ObjectReference(id=UUID(ref))

        raise ValueError("Unrecognized 'ref' attribute")

    @property
    def URL(self):
        """Return the Notion URL for this object reference.

        Note: this is a convenience property only.  It does not guarantee that the
        URL exists or that it is accessible by the integration.
        """
        return helpers.get_url(self.id)


# https://developers.notion.com/reference/parent-object
class ParentRef(TypedObject):
    """Reference another block as a parent."""

    # note that this class is simply a placeholder for the typed concrete *Ref classes
    # callers should always instantiate the intended concrete versions


class DatabaseRef(ParentRef, type="database_id"):
    """Reference a database."""

    database_id: UUID

    @classmethod
    def __compose__(cls, db_ref):
        """Compose a DatabaseRef from the given reference object.

        `db_ref` can be either a string, UUID, or database.
        """
        ref = ObjectReference[db_ref]
        return DatabaseRef(database_id=ref.id)


class PageRef(ParentRef, type="page_id"):
    """Reference a page."""

    page_id: UUID

    @classmethod
    def __compose__(cls, page_ref):
        """Compose a PageRef from the given reference object.

        `page_ref` can be either a string, UUID, or page.
        """
        ref = ObjectReference[page_ref]
        return PageRef(page_id=ref.id)


class BlockRef(ParentRef, type="block_id"):
    """Reference a block."""

    block_id: UUID

    @classmethod
    def __compose__(cls, block_ref):
        """Compose a BlockRef from the given reference object.

        `block_ref` can be either a string, UUID, or block.
        """
        ref = ObjectReference[block_ref]
        return BlockRef(block_id=ref.id)


class WorkspaceRef(ParentRef, type="workspace"):
    """Reference the workspace."""

    workspace: bool = True


class UserRef(NotionObject, object="user"):
    """Reference to a user, e.g. in `created_by`, `last_edited_by`, mentioning, etc."""


class UserType(str, Enum):
    """Available user types."""

    PERSON = "person"
    BOT = "bot"


class User(UserRef, TypedObject):
    """Represents a User in Notion."""

    name: str | None = None
    avatar_url: str | None = None


class Person(User, type="person"):
    """Represents a Person in Notion."""

    class _NestedData(GenericObject):
        email: str

    person: _NestedData = None

    def __str__(self):
        """Return a string representation of this `Person`."""
        return f"[@{self.name}]"


class Bot(User, type="bot"):
    """Represents a Bot in Notion."""

    class _NestedData(GenericObject):
        pass

    bot: _NestedData = None

    def __str__(self):
        """Return a string representation of this `Bot`."""
        return f"[%{self.name}]"


class EmojiObject(TypedObject, type="emoji"):
    """A Notion emoji object."""

    emoji: str

    def __str__(self):
        """Return this EmojiObject as a simple string."""
        return self.emoji

    @classmethod
    def __compose__(cls, emoji):
        """Compose an EmojiObject from the given emoji string."""
        return EmojiObject(emoji=emoji)


class FileObject(TypedObject):
    """A Notion file object.

    Depending on the context, a FileObject may require a name (such as in the `Files`
    property).  This makes the object hierarchy difficult, so here we simply allow
    `name` to be optional. It is the responsibility of the caller to set `name` if
    required by the API.
    """

    name: str | None = None

    def __str__(self):
        """Return a string representation of this object."""
        return self.name or "__unknown__"

    @property
    def URL(self):
        """Return the URL to this FileObject."""
        return self("url")


class HostedFile(FileObject, type="file"):
    """A Notion file object."""

    class _NestedData(GenericObject):
        url: str
        expiry_time: datetime | None = None

    file: _NestedData


class ExternalFile(FileObject, type="external"):
    """An external file object."""

    class _NestedData(GenericObject):
        url: str

    external: _NestedData

    def __str__(self):
        """Return a string representation of this object."""
        name = super().__str__()

        if self.external and self.external.url:
            return f"![{name}]({self.external.url})"

        return name

    @classmethod
    def __compose__(cls, url, name=None):
        """Create a new `ExternalFile` from the given URL."""
        return cls(name=name, external=cls._NestedData(url=url))


class DateRange(GenericObject):
    """A Notion date range, with an optional end date."""

    start: date | datetime
    end: date | datetime | None = None

    def __str__(self):
        """Return a string representation of this object."""

        if self.end is None:
            return f"{self.start}"

        return f"{self.start} :: {self.end}"


class MentionData(TypedObject):
    """Base class for typed `Mention` data objects."""


class MentionUser(MentionData, type="user"):
    """Nested user data for `Mention` properties."""

    user: UserRef

    @classmethod
    def __compose__(cls, user: User):
        """Build a `Mention` object for the specified user.

        The `id` field must be set for the given User.  Other fields may cause errors
        if they do not match the specific type returned from the API.
        """

        return MentionObject(plain_text=str(user), mention=MentionUser(user=user))


class MentionPage(MentionData, type="page"):
    """Nested page data for `Mention` properties."""

    page: ObjectReference

    @classmethod
    def __compose__(cls, page_ref):
        """Build a `Mention` object for the specified page reference."""

        ref = ObjectReference[page_ref]

        return MentionObject(plain_text=str(ref), mention=MentionPage(page=ref))


class MentionDatabase(MentionData, type="database"):
    """Nested database information for `Mention` properties."""

    database: ObjectReference

    @classmethod
    def __compose__(cls, page):
        """Build a `Mention` object for the specified database reference."""

        ref = ObjectReference[page]

        return MentionObject(plain_text=str(ref), mention=MentionDatabase(database=ref))


class MentionDate(MentionData, type="date"):
    """Nested date data for `Mention` properties."""

    date: DateRange

    @classmethod
    def __compose__(cls, start, end=None):
        """Build a `Mention` object for the specified URL."""

        date_obj = DateRange(start=start, end=end)

        return MentionObject(plain_text=str(date_obj), mention=MentionDate(date=date_obj))


class MentionLinkPreview(MentionData, type="link_preview"):
    """Nested url data for `Mention` properties.

    These objects cannot be created via the API.
    """

    class _NestedData(GenericObject):
        url: str

    link_preview: _NestedData


class MentionTemplateData(TypedObject):
    """Nested template data for `Mention` properties."""


class MentionTemplateDate(MentionTemplateData, type="template_mention_date"):
    """Nested date template data for `Mention` properties."""

    template_mention_date: str


class MentionTemplateUser(MentionTemplateData, type="template_mention_user"):
    """Nested user template data for `Mention` properties."""

    template_mention_user: str


class MentionTemplate(MentionData, type="template_mention"):
    """Nested template data for `Mention` properties."""

    template_mention: MentionTemplateData


class MentionObject(RichTextObject, type="mention"):
    """Notion mention element."""

    mention: MentionData


class EquationObject(RichTextObject, type="equation"):
    """Notion equation element."""

    class _NestedData(GenericObject):
        expression: str

    equation: _NestedData

    def __str__(self):
        """Return a string representation of this object."""

        if self.equation is None:
            return None

        return self.equation.expression
