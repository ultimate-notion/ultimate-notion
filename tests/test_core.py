from __future__ import annotations

from typing_extensions import assert_type

import ultimate_notion as uno


def test_workspace_sentinel() -> None:
    # The sentinel must be a distinct object, not its underlying string value. Compare against an
    # ``object``-typed value so the (intentional) cross-type check is not rejected by strict equality.
    not_workspace: object = 'workspace_root'
    assert uno.Workspace != not_workspace
    assert_type(uno.Workspace, uno.WorkspaceType)

    def func() -> str | uno.WorkspaceType:
        return 'dummy'

    my_var = func()
    if my_var is uno.Workspace:
        assert_type(my_var, uno.WorkspaceType)  # type narrowing check
