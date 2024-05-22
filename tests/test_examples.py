"""One test for each example in the examples folder"""

import asyncio
import contextlib
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

import ultimate_notion as uno
from tests.conftest import delete_all_taskslists
from ultimate_notion.config import get_cfg


@pytest.fixture(scope='module', autouse=True)
def notion_cleanups():
    """Overwrites fixture from conftest.py to avoid an open session."""


def run_in_new_loop(code, file_path):
    """Function to run provided code in a new event loop in a separate thread."""

    async def async_exec(compiled_code):  # noqa: RUF029
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Execute the compiled code in the new loop
            exec(compiled_code, {'__MODULE__': '__main__', 'asyncio': asyncio})  # noqa: S102
        finally:
            # Close the loop after execution
            loop.close()

    # Compile the code for execution
    compiled_code = compile(code, file_path, 'exec')

    # Run the async_exec coroutine in the new event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(async_exec(compiled_code))
    finally:
        loop.close()


def exec_pyfile(file_path: str) -> None:
    """Executes a Python module as a script (like CLI) in a separate thread with its own event loop."""
    code = Path(file_path).read_text(encoding='utf-8')

    # Execute in a separate thread with its own event loop
    with ThreadPoolExecutor() as executor:
        executor.submit(run_in_new_loop, code, file_path)


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
        notion.search_db('My synched task db').item().delete()
