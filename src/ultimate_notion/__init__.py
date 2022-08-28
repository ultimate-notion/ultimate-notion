import logging
from contextlib import contextmanager
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
_log = logging.getLogger(__name__)


@contextmanager
def connect(**kwargs):
    """Connect to Notion using the provided integration token."""

    _log.debug("Connecting to Notion...")
    sess = Session(**kwargs)
    try:
        yield sess
    finally:
        if sess.is_active:
            _log.debug("Closing connection to Notion...")
            sess.close()
