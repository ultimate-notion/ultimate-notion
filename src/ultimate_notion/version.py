"""Consistent version information for notional."""

import logging
import os

log = logging.getLogger(__name__)

__version__ = "0.4.1"

# if we are running in a local copy, append the repo information
# XXX do we want to do something more advanced when using `make publish` ?

log.debug("attempting to parse git version information")

try:

    import git

    basedir = os.path.dirname(os.path.abspath(__file__)) + "/.."
    log.debug("version basedir: %s", basedir)

    try:
        repo = git.Repo(basedir, search_parent_directories=True)
        head = repo.head.commit

        assert not repo.bare

        # TODO add branch name
        __version__ = f"{__version__}-{head.hexsha[:7]}"

        if repo.is_dirty():
            __version__ = f"{__version__}+"

    except git.InvalidGitRepositoryError:
        pass

except ModuleNotFoundError:
    pass

log.info("notional-%s", __version__)
