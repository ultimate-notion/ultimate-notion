"""One test for each example in the examples folder"""

import sys
from pathlib import Path

import pytest
from vcr import mode as vcr_mode

from tests.conftest import VCRManager


def exec_pyfile(file_path: str) -> None:
    code = compile(Path(file_path).read_text(), file_path, 'exec')
    exec(code, {'__MODULE__': '__main__'})  # noqa: S102


@pytest.mark.vcr()
@pytest.mark.skipif(sys.platform == 'win32', reason='Does not run on Windows')
def test_getting_started():
    if VCRManager.get_vcr().record_mode == vcr_mode.NONE:
        pytest.skip('Skipping test due to avoid network traffic that is not captured by VCR')

    exec_pyfile('examples/getting_started.py')


@pytest.mark.vcr()
@pytest.mark.skipif(sys.platform == 'win32', reason='Does not run on Windows')
def test_simple_taskdb():
    if VCRManager.get_vcr().record_mode == vcr_mode.NONE:
        pytest.skip('Skipping test due to avoid network traffic that is not captured by VCR')

    exec_pyfile('examples/simple_taskdb.py')


@pytest.mark.vcr()
@pytest.mark.skipif(sys.platform == 'win32', reason='Does not run on Windows')
def test_google_tasks():
    if VCRManager.get_vcr().record_mode == vcr_mode.NONE:
        pytest.skip('Skipping test due to avoid network traffic that is not captured by VCR')

    exec_pyfile('examples/google_tasks.py')
