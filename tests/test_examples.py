"""One test for each example in the examples folder"""

import sys
from pathlib import Path

import pytest


@pytest.fixture(scope='module', autouse=True)
def notion_cleanups():
    """Overwrites fixture from conftest.py to avoid an open session"""


def exec_pyfile(file_path: str) -> None:
    code = compile(Path(file_path).read_text(), file_path, 'exec')
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
def test_sync_google_tasks(custom_config: str):
    exec_pyfile('examples/sync_google_tasks.py')
