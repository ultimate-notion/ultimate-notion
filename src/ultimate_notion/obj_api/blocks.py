"""Wrapper for Notion API blocks.

Blocks are the base for all Notion content.
"""

from __future__ import annotations

from abc import ABC
from typing import Any, cast
from uuid import UUID

from pydantic import Field, SerializeAsAny

from ultimate_notion.obj_api.core import GenericObject, NotionEntity, TypedObject
from ultimate_notion.obj_api.enums import BGColor, CodeLang, Color
from ultimate_notion.obj_api.objects import (
    Annotations,
    BlockRef,
    EmojiObject,
    FileObject,
    MentionDatabase,
    MentionMixin,
    MentionObject,
    MentionPage,
    ParentRef,
    RichTextBaseObject,
    UserRef,
)
from ultimate_notion.obj_api.props import PropertyValue, Title
from ultimate_notion.obj_api.schema import PropertyType


class DataObject(NotionEntity, ABC):
    """The base type for all Notion objects that hold actual data."""

    has_children: bool = False

    in_trash: bool = False  # used to be `archived`
    archived: bool = False  # ToDo: Deprecated but still partially used in Notion. Check to remove in v1.0!

    last_edited_by: UserRef = None  # type: ignore


class Database(DataObject, MentionMixin, object='database'):
    """A database record type."""

    title: list[SerializeAsAny[RichTextBaseObject]] = None  # type: ignore
    url: str = None  # type: ignore
    public_url: str | None = None
    icon: SerializeAsAny[FileObject] | EmojiObject | None = None
    cover: SerializeAsAny[FileObject] | None = None
    properties: dict[str, PropertyType] = None  # type: ignore
    description: list[SerializeAsAny[RichTextBaseObject]] = None  # type: ignore
    is_inline: bool = False

    def build_mention(self, style: Annotations | None = None) -> MentionObject:
        return MentionDatabase.build(self, style=style)


class Page(DataObject, MentionMixin, object='page'):
    """A standard Notion page object."""

    url: str = None  # type: ignore
    public_url: str | None = None
    icon: SerializeAsAny[FileObject] | EmojiObject | None = None
    cover: SerializeAsAny[FileObject] | None = None
    properties: dict[str, PropertyValue] = None  # type: ignore

    def _get_title_prop_name(self) -> str:
        """Get the name of the title property."""
        # As the 'title' property might be renamed in case of pages in databases, we look for the `id`.
        for name, prop in self.properties.items():
            if prop.id == 'title':
                return name
        msg = 'Encountered a page without title property'
        raise RuntimeError(msg)

    @property
    def title(self) -> list[RichTextBaseObject]:
        """Retrieve the title of the page from page properties."""
        title_prop_name = self._get_title_prop_name()
        title_prop = cast(Title, self.properties[title_prop_name])
        return title_prop.title

    def build_mention(self, style: Annotations | None = None) -> MentionObject:
        return MentionPage.build(self, style=style)


class Block(DataObject, TypedObject, object='block', polymorphic_base=True):
    """A standard block object in Notion.

    Calling the block will expose the nested data in the object.
    """

    id: UUID = None  # type: ignore


class UnsupportedBlock(Block, type='unsupported'):
    """A placeholder for unsupported blocks in the API."""

    class TypeData(GenericObject): ...

    unsupported: TypeData | None = None


class TextBlock(Block, ABC):
    """A standard abstract text block object in Notion."""


class Paragraph(TextBlock, type='paragraph'):
    """A paragraph block in Notion."""

    class TypeData(GenericObject):
        rich_text: list[SerializeAsAny[RichTextBaseObject]] = None  # type: ignore
        children: list[SerializeAsAny[Block]] = Field(default_factory=list)
        color: Color | BGColor = Color.DEFAULT

    paragraph: TypeData = TypeData()


class Heading(TextBlock, ABC):
    """Abstract Heading block."""

    class TypeData(GenericObject):
        rich_text: list[SerializeAsAny[RichTextBaseObject]] = None  # type: ignore
        color: Color | BGColor = Color.DEFAULT
        is_toggleable: bool = False


class Heading1(Heading, type='heading_1'):
    """A heading_1 block in Notion."""

    heading_1: Heading.TypeData = Heading.TypeData()


class Heading2(Heading, type='heading_2'):
    """A heading_2 block in Notion."""

    heading_2: Heading.TypeData = Heading.TypeData()


class Heading3(Heading, type='heading_3'):
    """A heading_3 block in Notion."""

    heading_3: Heading.TypeData = Heading.TypeData()


class Quote(TextBlock, type='quote'):
    """A quote block in Notion."""

    class TypeData(GenericObject):
        rich_text: list[SerializeAsAny[RichTextBaseObject]] = None  # type: ignore
        children: list[SerializeAsAny[Block]] = Field(default_factory=list)
        color: Color | Color = Color.DEFAULT

    quote: TypeData = TypeData()


class Code(TextBlock, type='code'):
    """A code block in Notion."""

    class TypeData(GenericObject):
        rich_text: list[SerializeAsAny[RichTextBaseObject]] = None  # type: ignore
        caption: list[SerializeAsAny[RichTextBaseObject]] = None  # type: ignore
        language: CodeLang = CodeLang.PLAIN_TEXT

    code: TypeData = TypeData()


class Callout(TextBlock, type='callout'):
    """A callout block in Notion."""

    class TypeData(GenericObject):
        rich_text: list[SerializeAsAny[RichTextBaseObject]] = None  # type: ignore
        children: list[SerializeAsAny[Block]] = Field(default_factory=list)
        icon: SerializeAsAny[FileObject] | EmojiObject = None  # type: ignore
        color: Color | BGColor = BGColor.GRAY

    callout: TypeData = TypeData()


class BulletedListItem(TextBlock, type='bulleted_list_item'):
    """A bulleted list item in Notion."""

    class TypeData(GenericObject):
        rich_text: list[SerializeAsAny[RichTextBaseObject]] = None  # type: ignore
        children: list[SerializeAsAny[Block]] = Field(default_factory=list)
        color: Color | BGColor = Color.DEFAULT

    bulleted_list_item: TypeData = TypeData()


class NumberedListItem(TextBlock, type='numbered_list_item'):
    """A numbered list item in Notion."""

    class TypeData(GenericObject):
        rich_text: list[SerializeAsAny[RichTextBaseObject]] = None  # type: ignore
        children: list[SerializeAsAny[Block]] = Field(default_factory=list)
        color: Color | BGColor = Color.DEFAULT

    numbered_list_item: TypeData = TypeData()


class ToDo(TextBlock, type='to_do'):
    """A todo list item in Notion."""

    class TypeData(GenericObject):
        rich_text: list[SerializeAsAny[RichTextBaseObject]] = None  # type: ignore
        checked: bool = False
        children: list[SerializeAsAny[Block]] = Field(default_factory=list)
        color: Color | BGColor = Color.DEFAULT

    to_do: TypeData = TypeData()


class Toggle(TextBlock, type='toggle'):
    """A toggle list item in Notion."""

    class TypeData(GenericObject):
        rich_text: list[SerializeAsAny[RichTextBaseObject]] = None  # type: ignore
        children: list[SerializeAsAny[Block]] = Field(default_factory=list)
        color: Color | BGColor = Color.DEFAULT

    toggle: TypeData = TypeData()


class Divider(Block, type='divider'):
    """A divider block in Notion."""

    class TypeData(GenericObject): ...

    divider: TypeData = TypeData()


class TableOfContents(Block, type='table_of_contents'):
    """A table_of_contents block in Notion."""

    class TypeData(GenericObject):
        color: Color | BGColor = Color.DEFAULT

    table_of_contents: TypeData = TypeData()


class Breadcrumb(Block, type='breadcrumb'):
    """A breadcrumb block in Notion."""

    class TypeData(GenericObject): ...

    breadcrumb: TypeData = TypeData()


class Embed(Block, type='embed'):
    """An embed block in Notion."""

    class TypeData(GenericObject):
        url: str = None  # type: ignore
        caption: list[SerializeAsAny[RichTextBaseObject]] | None = None

    embed: TypeData = TypeData()


class Bookmark(Block, type='bookmark'):
    """A bookmark block in Notion."""

    class TypeData(GenericObject):
        url: str = None  # type: ignore
        caption: list[SerializeAsAny[RichTextBaseObject]] | None = None

    bookmark: TypeData = TypeData()


class LinkPreview(Block, type='link_preview'):
    """A link_preview block in Notion."""

    class TypeData(GenericObject):
        url: str = None  # type: ignore

    link_preview: TypeData = TypeData()


class Equation(Block, type='equation'):
    """An equation block in Notion."""

    class TypeData(GenericObject):
        expression: str | None = None

    equation: TypeData = TypeData()


class FileBase(Block, ABC):
    """A abstract block referencing a FileObject."""


class File(FileBase, type='file'):
    """A file block in Notion."""

    file: SerializeAsAny[FileObject] = None  # type: ignore


class Image(FileBase, type='image'):
    """An image block in Notion."""

    image: SerializeAsAny[FileObject] = None  # type: ignore


class Video(FileBase, type='video'):
    """A video block in Notion."""

    video: SerializeAsAny[FileObject] = None  # type: ignore


class PDF(FileBase, type='pdf'):
    """A pdf block in Notion."""

    pdf: SerializeAsAny[FileObject] = None  # type: ignore


class ChildPage(Block, type='child_page'):
    """A child page block in Notion."""

    class TypeData(GenericObject):
        title: str = None  # type: ignore

    child_page: TypeData = TypeData()


class ChildDatabase(Block, type='child_database'):
    """A child database block in Notion."""

    class TypeData(GenericObject):
        title: str = None  # type: ignore

    child_database: TypeData = TypeData()


class Column(Block, type='column'):
    """A column block in Notion."""

    class TypeData(GenericObject):
        # note that children will not be populated when getting this block
        # https://developers.notion.com/changelog/column-list-and-column-support
        children: list[SerializeAsAny[Block]] = Field(default_factory=list)

    column: TypeData = TypeData()

    @classmethod
    def build(cls) -> Column:
        return Column.model_construct(column=cls.TypeData.model_construct(children=[]))


class ColumnList(Block, type='column_list'):
    """A column list block in Notion."""

    class TypeData(GenericObject):
        # note that children will not be populated when getting this block
        # https://developers.notion.com/changelog/column-list-and-column-support
        children: list[Column] = Field(default_factory=list)

    column_list: TypeData = TypeData()


class TableRow(Block, type='table_row'):
    """A table_row block in Notion."""

    class TypeData(GenericObject):
        cells: list[list[SerializeAsAny[RichTextBaseObject]]] = Field(default_factory=list)

    table_row: TypeData = TypeData()

    @classmethod
    def build(cls, n_cells: int) -> TableRow:
        return TableRow.model_construct(table_row=cls.TypeData.model_construct(cells=[[] for _ in range(n_cells)]))


class Table(Block, type='table'):
    """A table block in Notion."""

    class TypeData(GenericObject):
        table_width: int = 0
        has_column_header: bool = False
        has_row_header: bool = False

        # note that children will not be populated when getting this block
        # https://developers.notion.com/reference/block#table-blocks
        children: list[TableRow] = Field(default_factory=list)

    table: TypeData = TypeData()


class LinkToPage(Block, type='link_to_page'):
    """A link_to_page block in Notion."""

    link_to_page: SerializeAsAny[ParentRef] = None  # type: ignore


class SyncedBlock(Block, type='synced_block'):
    """A synced_block block in Notion - either original or synced."""

    class TypeData(GenericObject):
        synced_from: BlockRef | None = None
        children: list[SerializeAsAny[Block]] = Field(default_factory=list)

    synced_block: TypeData = TypeData()

    def serialize_for_api(self) -> dict[str, Any]:
        """Serialize the object for sending it to the Notion API."""
        model_data = super().serialize_for_api()
        # Everywhere else we have to remove "null" values but `synced_from` is an exception
        if self.synced_block.synced_from is None:
            model_data['synced_block']['synced_from'] = None
        return model_data


class Template(Block, type='template'):
    """A template block in Notion."""

    class TypeData(GenericObject):
        rich_text: list[SerializeAsAny[RichTextBaseObject]] | None = None
        children: list[SerializeAsAny[Block]] = Field(default_factory=list)

    template: TypeData = TypeData()
