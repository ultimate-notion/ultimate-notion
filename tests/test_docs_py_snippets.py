from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sybil import Sybil
from sybil.parsers.markdown import PythonCodeBlockParser

WIN_SKIP_REASON = "Avoiding UnicodeDecodeError: 'charmap' codec can't decode"

_sybil = Sybil(parsers=[PythonCodeBlockParser()])


def check_md_file(*, fpath: str) -> None:
    """Execute every Python code block in a Markdown file in a shared namespace."""
    document = _sybil.parse(Path(fpath))
    for example in document:
        example.evaluate()


@pytest.mark.vcr()
@pytest.mark.skipif(sys.platform == 'win32', reason=WIN_SKIP_REASON)
def test_db_introduction() -> None:
    check_md_file(fpath='docs/usage/db_introduction.md')


@pytest.mark.vcr()
@pytest.mark.skipif(sys.platform == 'win32', reason=WIN_SKIP_REASON)
def test_db_advanced() -> None:
    check_md_file(fpath='docs/usage/db_advanced.md')


@pytest.mark.vcr()
@pytest.mark.skipif(sys.platform == 'win32', reason=WIN_SKIP_REASON)
def test_db_querying() -> None:
    check_md_file(fpath='docs/usage/db_querying.md')


@pytest.mark.vcr()
@pytest.mark.skipif(sys.platform == 'win32', reason=WIN_SKIP_REASON)
def test_page_introduction() -> None:
    check_md_file(fpath='docs/usage/page_introduction.md')


@pytest.mark.vcr()
@pytest.mark.skipif(sys.platform == 'win32', reason=WIN_SKIP_REASON)
def test_page_advanced() -> None:
    check_md_file(fpath='docs/usage/page_advanced.md')


@pytest.mark.file_upload()
def test_file_upload() -> None:
    check_md_file(fpath='docs/usage/file_upload.md')
