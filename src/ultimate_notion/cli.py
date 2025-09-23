import enum
import logging
import sys
from pathlib import Path
from typing import Annotated
from uuid import UUID

import filetype
import typer

from ultimate_notion import Session, __version__
from ultimate_notion.blocks import PDF, Audio, File, Image, Video
from ultimate_notion.config import get_cfg, get_cfg_file
from ultimate_notion.errors import UnknownPageError
from ultimate_notion.page import Page
from ultimate_notion.utils import pydantic_to_toml

_logger = logging.getLogger(__name__)


class LogLevel(str, enum.Enum):
    CRITICAL = 'critical'
    ERROR = 'error'
    WARNING = 'warning'
    INFO = 'info'
    DEBUG = 'debug'


def setup_logging(log_level: LogLevel) -> None:
    """Setup basic logging"""
    log_format = '[%(asctime)s] %(levelname)s:%(name)s:%(message)s'
    numeric_level = getattr(logging, log_level.upper(), None)
    logging.basicConfig(level=numeric_level, stream=sys.stdout, format=log_format, datefmt='%Y-%m-%d %H:%M:%S')


app = typer.Typer(
    name=f'Ultimate Notion {__version__}',
    help='🚀 The ultimate Python client for Notion!',
)


@app.callback()
def main(log_level: Annotated[LogLevel, typer.Option(help='Log level')] = LogLevel.WARNING) -> None:
    """Shared options for all commands"""
    setup_logging(log_level)


@app.command()
def config() -> None:
    """Display the current configuration file path and contents"""
    cfg_file = get_cfg_file()
    cfg = get_cfg()

    typer.echo(f'Config file: {cfg_file}')
    typer.echo('Configuration:')
    typer.echo('-' * 40)
    toml_string = pydantic_to_toml(cfg)
    typer.echo(toml_string)


@app.command()
def info() -> None:
    """Display information about the Notion integration"""
    typer.echo(f'Python version: {sys.version}')
    typer.echo(f'Ultimate Notion version: {__version__}')
    with Session() as session:
        this_integration = session.whoami()

    typer.echo('Notion integration:')
    typer.echo(f'- name: {this_integration.name}')
    typer.echo(f'- id: {this_integration.id}')

    typer.echo('Workspace info:')
    if workspace_info := this_integration.workspace_info:
        for key, value in workspace_info.model_dump().items():
            typer.echo(f'- {key}: {value}')


def _is_uuid(value: str) -> bool:
    """Check if a string is a valid UUID."""
    try:
        UUID(value)
        return True
    except ValueError:
        return False


def _get_block_class_for_file(file_path: Path) -> type[File | Image | Video | PDF | Audio]:
    """Determine the appropriate block class based on file content and extension.

    Uses the filetype library to detect file type by examining magic bytes,
    falling back to extension-based detection if needed.
    """
    # First try to detect by examining file content
    kind = filetype.guess(str(file_path))
    if kind is not None:
        mime_type = kind.mime
        if mime_type.startswith('image/'):
            return Image
        elif mime_type.startswith('video/'):
            return Video
        elif mime_type.startswith('audio/'):
            return Audio
        elif mime_type == 'application/pdf':
            return PDF

    return File


def _find_page_by_name(session: Session, page_name: str) -> Page:
    """Find a page by name, ensuring it's unique."""
    pages = session.search_page(page_name, exact=True)

    if not pages:
        typer.echo(f"Error: No page found with name '{page_name}'", err=True)
        raise typer.Exit(1)

    if len(pages) > 1:
        typer.echo(f"Error: Multiple pages found with name '{page_name}'. Please use the UUID instead.", err=True)
        typer.echo('Found pages:')
        for page in pages:
            typer.echo(f'  - {page.title} (ID: {page.id})')
        raise typer.Exit(1)

    return pages.item()


@app.command()
def upload(
    file_name: Annotated[str, typer.Argument(help='Path to the file to upload')],
    notion_page: Annotated[str, typer.Argument(help='Page name or UUID to upload the file to')],
) -> None:
    """Upload a file to a Notion page and append it as a block.

    The file will be uploaded to Notion and appended to the specified page.
    The block type is automatically determined based on the file extension:
    - Images (.png, .jpg, .jpeg, .gif, .webp, etc.) → Image block
    - Videos (.mp4, .avi, .mov, .wmv, etc.) → Video block
    - PDFs (.pdf) → PDF block
    - All other files → File block

    The page can be specified either by name or by UUID. If specified by name,
    the name must be unique (exact match).
    """
    file_path = Path(file_name)

    # Check if file exists
    if not file_path.exists():
        typer.echo(f"Error: File '{file_name}' does not exist", err=True)
        raise typer.Exit(1)

    if not file_path.is_file():
        typer.echo(f"Error: '{file_name}' is not a file", err=True)
        raise typer.Exit(1)

    with Session() as session:
        # Determine if notion_page is a UUID or name
        if _is_uuid(notion_page):
            try:
                page = session.get_page(notion_page)
                _logger.info(f"Found page by UUID: '{page.title}' (ID: {page.id})")
            except UnknownPageError as err:
                typer.echo(f"Error: Page with UUID '{notion_page}' not found", err=True)
                raise typer.Exit(1) from err
        else:
            _logger.info(f"Searching for page with name: '{notion_page}'")
            page = _find_page_by_name(session, notion_page)
            _logger.info(f"Found page: '{page.title}' (ID: {page.id})")

        _logger.info(f'Uploading file: {file_path.name}')
        with open(file_path, 'rb') as f:
            uploaded_file = session.upload(f, file_name=file_path.name)

        block_class = _get_block_class_for_file(file_path)
        block = block_class(uploaded_file)
        page.append(block)
        _logger.info(f"Successfully appended {block_class.__name__} block to page '{page.title}'")
