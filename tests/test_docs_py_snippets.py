from __future__ import annotations

import sys

import pytest
from mktestdocs import check_md_file


@pytest.mark.skipif(sys.platform == 'win32', reason="UnicodeDecodeError: 'charmap' codec can't decode")
def test_db_introduction():
    check_md_file(fpath='docs/usage/db_introduction.md', memory=True)


@pytest.mark.skipif(sys.platform == 'win32', reason="UnicodeDecodeError: 'charmap' codec can't decode")
def test_db_advanced():
    check_md_file(fpath='docs/usage/db_advanced.md', memory=True)


@pytest.mark.skipif(sys.platform == 'win32', reason="UnicodeDecodeError: 'charmap' codec can't decode")
def test_page_introduction():
    check_md_file(fpath='docs/usage/page_introduction.md', memory=True)
