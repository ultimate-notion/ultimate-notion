"""Wrapper for Notion API blocks.

Blocks are the base for all Notion content.

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

from abc import ABC
from typing import Any, cast

from pydantic import Field, SerializeAsAny
from typing_extensions import TypeVar

from ultimate_notion.obj_api.core import GenericObject, NotionEntity, TypedObject, Unset, UnsetType
from ultimate_notion.obj_api.enums import BGColor, CodeLang, Color
from ultimate_notion.obj_api.objects import (
    Annotations,
    BlockRef,
    CustomEmojiObject,
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
from ultimate_notion.obj_api.schema import Property


class DataObject(NotionEntity, ABC):
    """The base type for all Notion objects that hold actual data."""

    has_children: bool = False

    in_trash: bool = False  # used to be `archived`
    archived: bool = False  # ToDo: Deprecated but still partially used in Notion. Check to remove in v1.0!

    last_edited_by: UserRef | UnsetType = Unset


class Database(DataObject, MentionMixin, object='database'):
    """A database record type."""

    title: list[SerializeAsAny[RichTextBaseObject]] | UnsetType = Unset
    url: str | UnsetType = Unset
    public_url: str | None = None
    icon: SerializeAsAny[FileObject] | EmojiObject | CustomEmojiObject | None = None
    cover: SerializeAsAny[FileObject] | None = None
    properties: dict[str, SerializeAsAny[Property]]
    description: list[SerializeAsAny[RichTextBaseObject]] | UnsetType = Unset
    is_inline: bool = False

    def build_mention(self, style: Annotations | None = None) -> MentionObject:
        return MentionDatabase.build_mention_from(self, style=style)


class Page(DataObject, MentionMixin, object='page'):
    """A standard Notion page object."""

    url: str | UnsetType = Unset
    public_url: str | None = None
    icon: SerializeAsAny[FileObject] | EmojiObject | CustomEmojiObject | None = None
    cover: SerializeAsAny[FileObject] | None = None
    properties: dict[str, PropertyValue]

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
        return MentionPage.build_mention_from(self, style=style)


# ToDo: Use new syntax when requires-python >= 3.12
GO_co = TypeVar('GO_co', bound=GenericObject, default=GenericObject, covariant=True)


class Block(TypedObject[GO_co], DataObject, object='block', polymorphic_base=True):
    """A standard block object in Notion.

    Calling the block will expose the nested data in the object.
    """


class UnsupportedBlockTypeData(GenericObject):
    """Type data for `UnsupportedBlock`."""


class UnsupportedBlock(Block[UnsupportedBlockTypeData], type='unsupported'):
    """A placeholder for unsupported blocks in the API."""

    unsupported: UnsupportedBlockTypeData = Field(default_factory=UnsupportedBlockTypeData)


class TextBlockTypeData(GenericObject):
    """Type data for `TextBlock`."""

    rich_text: list[SerializeAsAny[RichTextBaseObject]] = Field(default_factory=list)


# ToDo: Use new syntax when requires-python >= 3.12
TB_co = TypeVar('TB_co', bound=TextBlockTypeData, default=TextBlockTypeData, covariant=True)


class TextBlock(Block[TB_co]):
    """A standard abstract text block object in Notion."""


class ColoredTextBlockTypeData(TextBlockTypeData):
    """Type data for `TextBlock` with color."""

    color: Color | BGColor = Color.DEFAULT


# ToDo: Use new syntax when requires-python >= 3.12
CTB_co = TypeVar('CTB_co', bound=ColoredTextBlockTypeData, default=ColoredTextBlockTypeData, covariant=True)


class ColoredTextBlock(TextBlock[CTB_co]):
    """A standard abstract text block object in Notion with color."""


class ParagraphTypeData(ColoredTextBlockTypeData):
    """Type data for `Paragraph` block."""

    children: list[SerializeAsAny[Block]] = Field(default_factory=list)


class Paragraph(ColoredTextBlock[ParagraphTypeData], type='paragraph'):
    """A paragraph block in Notion."""

    paragraph: ParagraphTypeData = Field(default_factory=ParagraphTypeData)


class HeadingTypeData(ColoredTextBlockTypeData):
    """Type data for `Heading` block."""

    is_toggleable: bool = False


class Heading(ColoredTextBlock[HeadingTypeData]):
    """Abstract Heading block."""


class Heading1(Heading, type='heading_1'):
    """A heading_1 block in Notion."""

    heading_1: HeadingTypeData = Field(default_factory=HeadingTypeData)


class Heading2(Heading, type='heading_2'):
    """A heading_2 block in Notion."""

    heading_2: HeadingTypeData = Field(default_factory=HeadingTypeData)


class Heading3(Heading, type='heading_3'):
    """A heading_3 block in Notion."""

    heading_3: HeadingTypeData = Field(default_factory=HeadingTypeData)


class QuoteTypeData(ColoredTextBlockTypeData):
    """Type data for `Quote` block."""

    children: list[SerializeAsAny[Block]] = Field(default_factory=list)


class Quote(ColoredTextBlock[QuoteTypeData], type='quote'):
    """A quote block in Notion."""

    quote: QuoteTypeData = Field(default_factory=QuoteTypeData)


class CaptionMixin(GenericObject, ABC):
    """Mixin for blocks having a caption."""

    caption: list[SerializeAsAny[RichTextBaseObject]] = Field(default_factory=list)


class CodeTypeData(TextBlockTypeData, CaptionMixin):
    """Type data for `Code` block."""

    language: CodeLang = CodeLang.PLAIN_TEXT


class Code(TextBlock[CodeTypeData], type='code'):
    """A code block in Notion."""

    code: CodeTypeData = Field(default_factory=CodeTypeData)


class CalloutTypeData(ColoredTextBlockTypeData):
    """Type data for `Callout` block."""

    # `children` is undocumented and behaves inconsistent. It is used during creation but not filled when retrieved.
    children: list[SerializeAsAny[Block]] = Field(default_factory=list)
    icon: SerializeAsAny[FileObject] | EmojiObject | CustomEmojiObject | UnsetType = Unset


class Callout(ColoredTextBlock[CalloutTypeData], type='callout'):
    """A callout block in Notion."""

    callout: CalloutTypeData = Field(default_factory=CalloutTypeData)


class BulletedListItemTypeData(ColoredTextBlockTypeData):
    """Type data for `BulletedListItem` block."""

    children: list[SerializeAsAny[Block]] = Field(default_factory=list)


class BulletedListItem(ColoredTextBlock[BulletedListItemTypeData], type='bulleted_list_item'):
    """A bulleted list item in Notion."""

    bulleted_list_item: BulletedListItemTypeData = Field(default_factory=BulletedListItemTypeData)


class NumberedListItemTypeData(ColoredTextBlockTypeData):
    """Type data for `NumberedListItem` block."""

    children: list[SerializeAsAny[Block]] = Field(default_factory=list)


class NumberedListItem(ColoredTextBlock[NumberedListItemTypeData], type='numbered_list_item'):
    """A numbered list item in Notion."""

    numbered_list_item: NumberedListItemTypeData = Field(default_factory=NumberedListItemTypeData)


class ToDoTypeData(ColoredTextBlockTypeData):
    """Type data for `ToDo` block."""

    checked: bool = False
    children: list[SerializeAsAny[Block]] = Field(default_factory=list)


class ToDo(ColoredTextBlock[ToDoTypeData], type='to_do'):
    """A todo list item in Notion."""

    to_do: ToDoTypeData = Field(default_factory=ToDoTypeData)


class ToggleTypeData(ColoredTextBlockTypeData):
    """Type data for `Toggle` block."""

    children: list[SerializeAsAny[Block]] = Field(default_factory=list)


class Toggle(ColoredTextBlock[ToggleTypeData], type='toggle'):
    """A toggle list item in Notion."""

    toggle: ToggleTypeData = Field(default_factory=ToggleTypeData)


class DividerTypeData(GenericObject):
    """Type data for `Divider` block."""


class Divider(Block[DividerTypeData], type='divider'):
    """A divider block in Notion."""

    divider: DividerTypeData = Field(default_factory=DividerTypeData)


class TableOfContentsTypeData(GenericObject):
    """Type data for `TableOfContents` block."""

    color: Color | BGColor = Color.DEFAULT


class TableOfContents(Block[TableOfContentsTypeData], type='table_of_contents'):
    """A table_of_contents block in Notion."""

    table_of_contents: TableOfContentsTypeData = Field(default_factory=TableOfContentsTypeData)


class BreadcrumbTypeData(GenericObject):
    """Type data for `Breadcrumb` block."""


class Breadcrumb(Block[BreadcrumbTypeData], type='breadcrumb'):
    """A breadcrumb block in Notion."""

    breadcrumb: BreadcrumbTypeData = Field(default_factory=BreadcrumbTypeData)


class EmbedTypeData(CaptionMixin):
    """Type data for `Embed` block."""

    url: str


class Embed(Block[EmbedTypeData], type='embed'):
    """An embed block in Notion."""

    embed: EmbedTypeData

    @classmethod
    def build(cls, url: str, caption: list[RichTextBaseObject]) -> Embed:
        return Embed.model_construct(embed=EmbedTypeData.model_construct(url=url, caption=caption))


class BookmarkTypeData(CaptionMixin):
    """Type data for `Bookmark` block."""

    url: str


class Bookmark(Block[BookmarkTypeData], type='bookmark'):
    """A bookmark block in Notion."""

    bookmark: BookmarkTypeData

    @classmethod
    def build(cls, url: str, caption: list[RichTextBaseObject]) -> Bookmark:
        return Bookmark.model_construct(bookmark=BookmarkTypeData.model_construct(url=url, caption=caption))


class LinkPreviewTypeData(GenericObject):
    """Type data for `LinkPreview` block."""

    url: str


class LinkPreview(Block[LinkPreviewTypeData], type='link_preview'):
    """A link_preview block in Notion."""

    link_preview: LinkPreviewTypeData


class EquationTypeData(GenericObject):
    """Type data for `Equation` block."""

    expression: str | None = None


class Equation(Block[EquationTypeData], type='equation'):
    """An equation block in Notion."""

    equation: EquationTypeData = Field(default_factory=EquationTypeData)


class FileBase(Block[FileObject], ABC):
    """A abstract block referencing a FileObject."""


class File(FileBase, type='file'):
    """A file block in Notion."""

    file: SerializeAsAny[FileObject] | None = None


class Image(FileBase, type='image'):
    """An image block in Notion."""

    image: SerializeAsAny[FileObject] | None = None


class Video(FileBase, type='video'):
    """A video block in Notion."""

    video: SerializeAsAny[FileObject] | None = None


class PDF(FileBase, type='pdf'):
    """A pdf block in Notion."""

    pdf: SerializeAsAny[FileObject] | None = None


class ChildPageTypeData(GenericObject):
    """Type data for `ChildPage` block."""

    title: str


class ChildPage(Block[ChildPageTypeData], type='child_page'):
    """A child page block in Notion."""

    child_page: ChildPageTypeData


class ChildDatabaseTypeData(GenericObject):
    """Type data for `ChildDatabase` block."""

    title: str


class ChildDatabase(Block[ChildDatabaseTypeData], type='child_database'):
    """A child database block in Notion."""

    child_database: ChildDatabaseTypeData


class ColumnTypeData(GenericObject):
    """Type data for `Column` block."""

    # note that children will not be populated when getting this block
    # https://developers.notion.com/changelog/column-list-and-column-support
    children: list[SerializeAsAny[Block]] = Field(default_factory=list)
    width_ratio: float | None = None


class Column(Block[ColumnTypeData], type='column'):
    """A column block in Notion."""

    column: ColumnTypeData = Field(default_factory=ColumnTypeData)

    @classmethod
    def build(cls, width_ratio: float | None = None) -> Column:
        return Column.model_construct(column=ColumnTypeData.model_construct(children=[], width_ratio=width_ratio))


class ColumnListTypeData(GenericObject):
    """Type data for `ColumnList` block."""

    # note that children will not be populated when getting this block
    # https://developers.notion.com/changelog/column-list-and-column-support
    children: list[Column] = Field(default_factory=list)


class ColumnList(Block[ColumnListTypeData], type='column_list'):
    """A column list block in Notion."""

    column_list: ColumnListTypeData = Field(default_factory=ColumnListTypeData)


class TableRowTypeData(GenericObject):
    """Type data for `TableRow` block."""

    cells: list[list[SerializeAsAny[RichTextBaseObject]]] = Field(default_factory=list)


class TableRow(Block[TableRowTypeData], type='table_row'):
    """A table_row block in Notion."""

    table_row: TableRowTypeData = Field(default_factory=TableRowTypeData)

    @classmethod
    def build(cls, n_cells: int) -> TableRow:
        return TableRow.model_construct(table_row=TableRowTypeData.model_construct(cells=[[] for _ in range(n_cells)]))


class TableTypeData(GenericObject):
    """Type data for `Table` block."""

    table_width: int = 0
    has_column_header: bool = False
    has_row_header: bool = False
    # note that children will not be populated when getting this block
    # https://developers.notion.com/reference/block#table-blocks
    children: list[TableRow] = Field(default_factory=list)


class Table(Block[TableTypeData], type='table'):
    """A table block in Notion."""

    table: TableTypeData = Field(default_factory=TableTypeData)


class LinkToPage(Block[ParentRef], type='link_to_page'):
    """A link_to_page block in Notion."""

    link_to_page: SerializeAsAny[ParentRef]


class SyncedBlockTypeData(GenericObject):
    """Type data for `SyncedBlock` block."""

    synced_from: BlockRef | None = None
    children: list[SerializeAsAny[Block]] = Field(default_factory=list)


class SyncedBlock(Block[SyncedBlockTypeData], type='synced_block'):
    """A synced_block block in Notion - either original or synced."""

    synced_block: SyncedBlockTypeData = Field(default_factory=SyncedBlockTypeData)

    def serialize_for_api(self) -> dict[str, Any]:
        """Serialize the object for sending it to the Notion API."""
        model_data = super().serialize_for_api()
        # Everywhere else we have to remove "null" values but `synced_from` is an exception
        if self.synced_block.synced_from is None:
            model_data['synced_block']['synced_from'] = None
        return model_data


class TemplateTypeData(TextBlockTypeData):
    """Type data for `Template` block."""

    children: list[SerializeAsAny[Block]] = Field(default_factory=list)


class Template(TextBlock[TemplateTypeData], type='template'):
    """A template block in Notion."""

    template: TemplateTypeData = Field(default_factory=TemplateTypeData)
