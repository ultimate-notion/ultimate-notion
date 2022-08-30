from importlib.metadata import PackageNotFoundError, version

try:
    dist_name = "ultimate-notion"
    __version__ = version(dist_name)
except PackageNotFoundError:  # pragma: no cover
    __version__ = "unknown"
finally:
    del version, PackageNotFoundError

from .session import Session

__all__ = ["__version__", "Session"]
