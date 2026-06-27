"""One test for each example in the examples folder"""

import contextlib
import shutil
import sys
from pathlib import Path

import pytest

import ultimate_notion as uno
from tests.conftest import delete_all_taskslists, exec_pyfile
from ultimate_notion.config import get_cfg


@pytest.fixture(scope='module', autouse=True)
def notion_cleanups() -> None:
    """Overwrites fixture from conftest.py to avoid an open session."""


@pytest.mark.vcr()
@pytest.mark.skipif(sys.platform == 'win32', reason='Does not run on Windows')
def test_getting_started() -> None:
    exec_pyfile('examples/getting_started.py')


@pytest.mark.vcr()
@pytest.mark.skipif(sys.platform == 'win32', reason='Does not run on Windows')
def test_simple_taskdb() -> None:
    exec_pyfile('examples/simple_taskdb.py')


@pytest.mark.vcr()
@pytest.mark.skipif(sys.platform == 'win32', reason='Does not run on Windows')
def test_sync_google_tasks(custom_config: Path) -> None:
    # assures deterministic tests by removing possible states
    shutil.rmtree(get_cfg().ultimate_notion.sync_state_dir)
    delete_all_taskslists()

    exec_pyfile('examples/sync_google_tasks.py')

    delete_all_taskslists()
    # Manual cleanup as `notion_cleanups` fixture does not work here
    with uno.Session() as notion, contextlib.suppress(ValueError):
        notion.search_ds('My synced task db').item().delete()


@pytest.mark.file_upload()
def test_file_upload() -> None:
    exec_pyfile('examples/file_upload.py')
