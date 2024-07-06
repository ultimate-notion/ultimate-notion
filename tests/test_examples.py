"""One test for each example in the examples folder"""

import contextlib
import shutil
import sys
from pathlib import Path

import pytest

import ultimate_notion as uno
from tests.conftest import delete_all_taskslists
from ultimate_notion.config import get_cfg


@pytest.fixture(scope='module', autouse=True)
def notion_cleanups():
    """Overwrites fixture from conftest.py to avoid an open session."""


def exec_pyfile(file_path: str) -> None:
    """Executes a Python module as a script, as if it was called from the command line."""
    code = compile(Path(file_path).read_text(encoding='utf-8'), file_path, 'exec')
    exec(code, {'__MODULE__': '__main__'})  # noqa: S102


@pytest.mark.vcr()
@pytest.mark.skipif(sys.platform == 'win32', reason='Does not run on Windows')
def test_getting_started():
    exec_pyfile('examples/getting_started.py')


@pytest.mark.vcr()
@pytest.mark.skipif(sys.platform == 'win32', reason='Does not run on Windows')
def test_simple_taskdb():
    exec_pyfile('examples/simple_taskdb.py')


@pytest.mark.vcr()
@pytest.mark.skipif(sys.platform == 'win32', reason='Does not run on Windows')
def test_sync_google_tasks(custom_config: Path):
    # assures deterministic tests by removing possible states
    shutil.rmtree(get_cfg().ultimate_notion.sync_state_dir)
    delete_all_taskslists()

    exec_pyfile('examples/sync_google_tasks.py')

    delete_all_taskslists()
    # Manual cleanup as `notion_cleanups` fixture does not work here
    with uno.Session() as notion, contextlib.suppress(ValueError):
        notion.search_db('My synced task db').item().delete()
