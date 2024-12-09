from __future__ import annotations

import sys

import pytest
from mktestdocs import check_md_file

WIN_SKIP_REASON = "Avoiding UnicodeDecodeError: 'charmap' codec can't decode"


@pytest.mark.vcr()
@pytest.mark.skipif(sys.platform == 'win32', reason=WIN_SKIP_REASON)
def test_db_introduction():
    check_md_file(fpath='docs/usage/db_introduction.md', memory=True)


@pytest.mark.vcr()
@pytest.mark.skipif(sys.platform == 'win32', reason=WIN_SKIP_REASON)
def test_db_advanced():
    check_md_file(fpath='docs/usage/db_advanced.md', memory=True)


@pytest.mark.vcr()
@pytest.mark.skipif(sys.platform == 'win32', reason=WIN_SKIP_REASON)
def test_db_querying():
    check_md_file(fpath='docs/usage/db_querying.md', memory=True)


@pytest.mark.vcr()
@pytest.mark.skipif(sys.platform == 'win32', reason=WIN_SKIP_REASON)
def test_page_introduction():
    check_md_file(fpath='docs/usage/page_introduction.md', memory=True)


@pytest.mark.vcr()
@pytest.mark.skipif(sys.platform == 'win32', reason=WIN_SKIP_REASON)
def test_page_advanced():
    check_md_file(fpath='docs/usage/page_advanced.md', memory=True)
