"""Generate and sets the ULTIMATE_NOTION_VERSION environment variable

Copyright (c) 2017, Ofek Lev, MIT License

Taken from: https://github.com/pypa/hatch/blob/master/scripts/set_release_version.py
"""

import os

from hatch.project.core import Project
from hatch.utils.fs import Path
from packaging.version import Version


def main():
    project = Project(Path(__file__).resolve().parent.parent)
    version = Version(project.metadata.version)
    with open(os.environ['GITHUB_ENV'], 'a', encoding='utf-8') as f:
        f.write(f'ULTIMATE_NOTION_VERSION={version.major}.{version.minor}\n')


if __name__ == '__main__':
    main()
