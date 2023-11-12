from __future__ import annotations

from typing import cast

from ultimate_notion.obj_api import objects as objs
from ultimate_notion.text import chunky, html_img
from ultimate_notion.utils import Wrapper, get_repr


class Option(Wrapper[objs.SelectOption], wraps=objs.SelectOption):
    """Option for select & multi-select property"""

    @property
    def name(self) -> str:
        """Name of the option"""
        return self.obj_ref.name

    def __repr__(self) -> str:
        return get_repr(self)

    def __str__(self) -> str:
        return self.name


class File(Wrapper[objs.FileObject], wraps=objs.FileObject):
    """A web resource e.g. for the files property"""

    obj_ref: objs.FileObject

    @classmethod
    def wrap_obj_ref(cls, obj_ref: objs.FileObject) -> File:
        self = cast(File, cls.__new__(cls))
        self.obj_ref = obj_ref
        return self

    def __init__(self, url: str) -> None:
        self.obj_ref = objs.ExternalFile.build(url=url, name=url)

    def __repr__(self) -> str:
        return get_repr(self)

    def __str__(self) -> str:
        return self.url

    def _repr_html_(self) -> str:  # noqa: PLW3201
        """Called by Jupyter Lab automatically to display this file"""
        return html_img(self.url, size=2)

    @property
    def name(self) -> str | None:
        return self.obj_ref.name

    @property
    def url(self) -> str:
        if isinstance(self.obj_ref, objs.HostedFile):
            return self.obj_ref.file.url
        elif isinstance(self.obj_ref, objs.ExternalFile):
            return self.obj_ref.external.url
        else:
            msg = f'Unknown file type {type(self.obj_ref)}'
            raise RuntimeError(msg)


class RichTextBase(Wrapper[objs.RichTextObject], wraps=objs.RichTextObject):
    """Super class for text, equation and mentions of various kinds"""


class Text(RichTextBase, wraps=objs.TextObject):
    """A Text object"""


class Equation(RichTextBase, wraps=objs.EquationObject):
    """An Equation object"""


class Mention(RichTextBase, wraps=objs.MentionObject):
    """A Mention object"""


class RichText(list[RichTextBase]):
    """User-facing class holding several RichTexts"""

    def __new__(cls, plain_text: str, *, _factory_method: bool = False) -> RichText:
        """Default constructor creates RichText object from a single plain text string argument"""
        if _factory_method:
            return super().__new__(cls)
        else:
            return cls.from_plain_text(plain_text)

    def __init__(self, *args, _factory_method: bool = False):
        if _factory_method:  # avoids the automatic call after the implicit __new__ when calling default constructor
            super().__init__(*args)

    @classmethod
    def wrap_obj_ref(cls, obj_refs: list[objs.RichTextObject]) -> RichText:
        rich_texts = [cast(RichTextBase, RichTextBase.wrap_obj_ref(obj_ref)) for obj_ref in obj_refs]
        return cls(rich_texts, _factory_method=True)

    @property
    def obj_ref(self) -> list[objs.RichTextObject]:
        return [elem.obj_ref for elem in self]

    @classmethod
    def from_markdown(cls, text: str) -> RichText:
        """Create RichTextList by parsing the markdown"""
        # ToDo: Implement
        # ToDo: Handle Equations and Mentions here accordingly
        raise NotImplementedError

    def to_markdown(self) -> str | None:
        """Convert the list of RichText objects to markdown"""
        # ToDo: Implement
        raise NotImplementedError

    @classmethod
    def from_plain_text(cls, text: str) -> RichText:
        """Create RichTextList from plain text"""
        rich_texts: list[RichTextBase] = []
        for part in chunky(text):
            rich_texts.append(Text(part))

        return cls(rich_texts, _factory_method=True)

    def to_plain_text(self) -> str:
        """Return rich text as plaintext"""
        return ''.join(text.plain_text for text in self.obj_ref if text)

    def _repr_html_(self) -> str:  # noqa: PLW3201
        """Called by Jupyter Lab automatically to display this text"""
        # ToDo: Later use Markdown output.
        return self.to_plain_text()

    def __str__(self) -> str:
        plain_text = self.to_plain_text()
        return plain_text if plain_text is not None else ''

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return str(self) == other
        elif isinstance(other, RichText):
            return str(self) == str(other)
        else:
            return NotImplemented

    def __hash__(self):
        return hash(str(self))


class User(Wrapper[objs.User], wraps=objs.User):
    @classmethod
    def wrap_obj_ref(cls, obj_ref: objs.User) -> User:
        self = cast(User, cls.__new__(cls))
        self.obj_ref = obj_ref
        return self

    def __str__(self):
        return self.name

    def __repr__(self) -> str:
        return get_repr(self)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, User):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    @property
    def id(self):  # noqa: A003
        return self.obj_ref.id

    @property
    def name(self):
        return self.obj_ref.name

    @property
    def is_person(self) -> bool:
        return isinstance(self.obj_ref, objs.Person)

    @property
    def is_bot(self) -> bool:
        return isinstance(self.obj_ref, objs.Bot)

    @property
    def avatar_url(self):
        return self.obj_ref.avatar_url

    @property
    def email(self) -> str | None:
        if isinstance(self.obj_ref, objs.Person):
            return self.obj_ref.person.email
        else:  # it's a bot without an e-mail
            return None
