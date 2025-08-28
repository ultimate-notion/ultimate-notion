from __future__ import annotations

from typing_extensions import assert_type

import ultimate_notion as uno


def test_workspace_sentinel() -> None:
    assert uno.Workspace != 'workspace_root'
    assert_type(uno.Workspace, uno.WorkspaceType)

    def func() -> str | uno.WorkspaceType:
        return 'dummy'

    my_var = func()
    if my_var is uno.Workspace:
        assert_type(my_var, uno.WorkspaceType)  # type narrowing check
