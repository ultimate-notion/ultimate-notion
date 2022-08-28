import logging
from importlib.metadata import PackageNotFoundError, version

try:
    dist_name = "ultimate-notion"
    __version__ = version(dist_name)
except PackageNotFoundError:  # pragma: no cover
    __version__ = "unknown"
finally:
    del version, PackageNotFoundError

from .session import Session

__all__ = ["__version__", "connect"]
_logger = logging.getLogger(__name__)


def connect(**kwargs):
    """Connect to Notion using the provided integration token."""

    _logger.debug("connecting to Notion...")

    return Session(**kwargs)
