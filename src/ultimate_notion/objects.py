from __future__ import annotations

from typing import cast

from ultimate_notion.obj_api import objects as objs
from ultimate_notion.utils import Wrapper


class Option(Wrapper[objs.SelectOption], wraps=objs.SelectOption):
    """Option for select & multi-select property"""

    @property
    def name(self) -> str:
        """Name of the option"""
        return self.obj_ref.name


class File(Wrapper[objs.FileObject], wraps=objs.FileObject):
    """A web resource e.g. for the files property"""

    obj_ref: objs.FileObject

    def __init__(self, url: str) -> None:
        self.obj_ref = objs.ExternalFile.build(url=url, name=url)


class RichTextElem(Wrapper[objs.RichTextObject], wraps=objs.RichTextObject):
    """Super class for text, equation, mentions of various kinds"""


class Text(RichTextElem, wraps=objs.TextObject):
    """A Text object"""


class Equation(RichTextElem, wraps=objs.EquationObject):
    """An Equation object"""


class Mention(RichTextElem, wraps=objs.MentionObject):
    """A Mention object"""


class RichText(list[RichTextElem]):
    """User-facing class holding several RichText's"""

    @property
    def obj_ref(self) -> list[objs.RichTextObject]:
        return [elem.obj_ref for elem in self]

    @classmethod
    def from_markdown(cls, text: str) -> RichText:
        """Create RichTextList by parsing the markdown"""
        # ToDo: Fix this cyclic import.
        # Rather have the rich_text logic here and provide convenience Func in `functions.py`
        from ultimate_notion.text import rich_text

        return rich_text(text)

    def to_markdown(self) -> str:
        """Convert the list of RichText objects to markdown"""
        # ToDo: Implement
        raise NotImplementedError()

    def __str__(self) -> str:
        return self.to_markdown()


class User(Wrapper[objs.User], wraps=objs.User):
    @classmethod
    def wrap_obj_ref(cls, obj_ref: objs.User) -> User:
        self = cast(User, cls.__new__(cls))
        self.obj_ref = obj_ref
        return self

    def __str__(self):
        return self.name

    def __repr__(self) -> str:
        cls_name = self.__class__.__name__
        return f"<{cls_name}: '{self!s}' at {hex(id(self))}>"

    def __eq__(self, other):
        return self.id == other.id

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
