from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("ultimate-notion")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "unknown"
finally:
    del version, PackageNotFoundError

from .session import Session

__all__ = ["__version__", "Session"]
