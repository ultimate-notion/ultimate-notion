"""One test for each example in the examples folder"""

import os
import re
import subprocess


def test_getting_started():
    with open('examples/getting_started.py', encoding='utf8') as file:
        py_file = file.read()

    py_file = py_file.replace('\n', os.linesep)  # for windows
    py_file = re.sub(r'auth=TOKEN', '', py_file, flags=re.MULTILINE)
    # avoid the fact that we open up another ultimate-notion client
    result = subprocess.run(['python', '-c', py_file], capture_output=True, text=True, check=True)  # noqa: S603, S607
    assert result.returncode == 0
