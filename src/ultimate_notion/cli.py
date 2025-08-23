import enum
import logging
import sys
from typing import Annotated

import typer

from ultimate_notion import __version__
from ultimate_notion.config import get_cfg, get_cfg_file
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
