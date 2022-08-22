"""Utilities for working text, markdown & Rich Text in Notion."""

import re
from copy import deepcopy
from enum import Enum
from typing import Optional

from emoji import EMOJI_DATA

from .core import DataObject, NestedObject, TypedObject

# this might be a place to capture other utilities for working with markdown, text
# rich text, etc...  the challenge is not importing types due to a circular ref.


# the max text size according to the Notion API is 2000 characters...
MAX_TEXT_OBJECT_SIZE = 2000


def plain_text(*rtf):
    """Return the combined plain text from the list of RichText objects."""
    return "".join(text.plain_text for text in rtf if text)


def markdown(*rtf):
    """Return text as markdown from the list of RichText objects."""
    return "".join(str(text) for text in rtf if text)


def is_emoji(text):
    """Check if text is a single emoji."""
    return text in EMOJI_DATA


def chunky(text, length=MAX_TEXT_OBJECT_SIZE):
    """Break the given `text` into chunks of at most `length` size."""
    return (text[idx : idx + length] for idx in range(0, len(text), length))


def truncate(text, length=-1, trail="..."):
    """Truncate the given text, using a supplied tail as a placeholder."""

    if text is None:
        return None

    # repr() includes open and close quotes...
    literal = repr(text)[1:-1]

    if 0 < length < len(literal):
        literal = literal[:length]

        if trail is not None:
            literal += trail

    return literal


def lstrip(*rtf):
    """Remove leading whitespace from each `TextObject` in the list."""

    if rtf is None or len(rtf) < 1:
        return

    for obj in rtf:
        if not isinstance(obj, TextObject):
            raise AttributeError("invalid object in rtf")

        if obj.text and obj.text.content:
            strip_text = obj.text.content.lstrip()
            obj.text.content = strip_text
            obj.plain_text = strip_text


def rstrip(*rtf):
    """Remove trailing whitespace from each `TextObject` in the list."""

    if rtf is None or len(rtf) < 1:
        return

    for obj in rtf:
        if not isinstance(obj, TextObject):
            raise AttributeError("invalid object in rtf")

        if obj.text and obj.text.content:
            strip_text = obj.text.content.rstrip()
            obj.text.content = strip_text
            obj.plain_text = strip_text


def strip(*rtf):
    """Remove leading and trailing whitespace from each `TextObject` in the list.

    This is functionally equivalent to:
        ```python
        lstrip(*rtf)
        rstrip(*rtf)
        ```

    :param rtf: a list of `TextObject`'s
    """
    lstrip(*rtf)
    rstrip(*rtf)


def make_safe_python_name(name):
    """Make the given string safe for use as a Python identifier.

    This will remove any leading characters that are not valid and change all
    invalid interior sequences to underscore.
    """

    s = re.sub(r"[^0-9a-zA-Z_]+", "_", name)
    s = re.sub(r"^[^a-zA-Z]+", "", s)

    # remove trailing underscores
    return s.rstrip("_")


class Color(str, Enum):
    """Basic color values."""

    DEFAULT = "default"
    GRAY = "gray"
    BROWN = "brown"
    ORANGE = "orange"
    YELLOW = "yellow"
    GREEN = "green"
    BLUE = "blue"
    PURPLE = "purple"
    PINK = "pink"
    RED = "red"


class FullColor(str, Enum):
    """Extended color values, including backgrounds."""

    DEFAULT = "default"
    GRAY = "gray"
    BROWN = "brown"
    ORANGE = "orange"
    YELLOW = "yellow"
    GREEN = "green"
    BLUE = "blue"
    PURPLE = "purple"
    PINK = "pink"
    RED = "red"

    GRAY_BACKGROUND = "gray_background"
    BROWN_BACKGROUND = "brown_background"
    ORANGE_BACKGROUND = "orange_background"
    YELLOW_BACKGROUND = "yellow_background"
    GREEN_BACKGROUND = "green_background"
    BLUE_BACKGROUND = "blue_background"
    PURPLE_BACKGROUND = "purple_background"
    PINK_BACKGROUND = "pink_background"
    RED_BACKGROUND = "red_background"


class LinkObject(DataObject):
    """Reference a URL."""

    type: str = "url"
    url: str = None


class Annotations(DataObject):
    """Style information for RichTextObject's."""

    bold: bool = False
    italic: bool = False
    strikethrough: bool = False
    underline: bool = False
    code: bool = False
    color: FullColor = None

    @property
    def is_plain(self):
        """Determine if any flags are set in this `Annotations` object.

        If all flags match their defaults, this is considered a "plain" style.
        """

        # XXX a better approach here would be to just compate all fields to defaults

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


class RichTextObject(TypedObject):
    """Base class for Notion rich text elements."""

    plain_text: str
    href: Optional[str] = None
    annotations: Optional[Annotations] = None

    def __str__(self):
        """Return a string representation of this object."""

        if self.href is None:
            text = self.plain_text or ""
        elif self.plain_text is None or len(self.plain_text) == 0:
            text = f"({self.href})"
        else:
            text = f"[{self.plain_text}]({self.href})"

        if self.annotations:
            if self.annotations.bold:
                text = f"*{text}*"
            if self.annotations.italic:
                text = f"**{text}**"
            if self.annotations.underline:
                text = f"_{text}_"
            if self.annotations.strikethrough:
                text = f"~{text}~"
            if self.annotations.code:
                text = f"`{text}`"

        return text


class TextObject(RichTextObject, type="text"):
    """Notion text element."""

    class _NestedData(NestedObject):
        content: str = None
        link: Optional[LinkObject] = None

    text: _NestedData = _NestedData()

    @classmethod
    def __compose__(cls, text, href=None, style=None):
        """Compose a TextObject from the given properties.

        :param text: the plain text of this object
        :param href: an optional link for this object
        :param style: an optional Annotations object for this text
        """

        if text is None:
            return None

        # TODO convert markdown in text:str to RichText?

        link = LinkObject(url=href) if href else None
        nested = TextObject._NestedData(content=text, link=link)
        style = deepcopy(style)

        return TextObject(
            plain_text=text,
            text=nested,
            href=href,
            annotations=style,
        )


class CodingLanguage(str, Enum):
    """Available coding languages."""

    ABAP = "abap"
    ARDUINO = "arduino"
    BASH = "bash"
    BASIC = "basic"
    C = "c"
    CLOJURE = "clojure"
    COFFEESCRIPT = "coffeescript"
    CPP = "c++"
    CSHARP = "c#"
    CSS = "css"
    DART = "dart"
    DIFF = "diff"
    DOCKER = "docker"
    ELIXIR = "elixir"
    ELM = "elm"
    ERLANG = "erlang"
    FLOW = "flow"
    FORTRAN = "fortran"
    FSHARP = "f#"
    GHERKIN = "gherkin"
    GLSL = "glsl"
    GO = "go"
    GRAPHQL = "graphql"
    GROOVY = "groovy"
    HASKELL = "haskell"
    HTML = "html"
    JAVA = "java"
    JAVASCRIPT = "javascript"
    JSON = "json"
    JULIA = "julia"
    KOTLIN = "kotlin"
    LATEX = "latex"
    LESS = "less"
    LISP = "lisp"
    LIVESCRIPT = "livescript"
    LUA = "lua"
    MAKEFILE = "makefile"
    MARKDOWN = "markdown"
    MARKUP = "markup"
    MATLAB = "matlab"
    MERMAID = "mermaid"
    NIX = "nix"
    OBJECTIVE_C = "objective-c"
    OCAML = "ocaml"
    PASCAL = "pascal"
    PERL = "perl"
    PHP = "php"
    PLAIN_TEXT = "plain text"
    POWERSHELL = "powershell"
    PROLOG = "prolog"
    PROTOBUF = "protobuf"
    PYTHON = "python"
    R = "r"
    REASON = "reason"
    RUBY = "ruby"
    RUST = "rust"
    SASS = "sass"
    SCALA = "scala"
    SCHEME = "scheme"
    SCSS = "scss"
    SHELL = "shell"
    SQL = "sql"
    SWIFT = "swift"
    TYPESCRIPT = "typescript"
    VB_NET = "vb.net"
    VERILOG = "verilog"
    VHDL = "vhdl"
    VISUAL_BASIC = "visual basic"
    WEBASSEMBLY = "webassembly"
    XML = "xml"
    YAML = "yaml"
    MISC = "java/c/c++/c#"
