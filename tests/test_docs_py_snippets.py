from __future__ import annotations

from mktestdocs import check_md_file


def test_db_introduction():
    check_md_file(fpath='docs/usage/db_introduction.md', memory=True)
