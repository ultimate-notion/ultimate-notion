from __future__ import annotations

import pytest
from pydantic import ValidationError
from typing_extensions import assert_type

import ultimate_notion as uno
from ultimate_notion.obj_api.objects import RichTextBaseObject, User


def test_resolve_type_validates_user_ref() -> None:
    """A user ref without a `type` is now validated, not constructed unchecked."""
    # A valid user ref resolves fine.
    user = User.model_validate({'object': 'user', 'id': '11111111-1111-1111-1111-111111111111'})
    assert user.object == 'user'

    # An invalid field now raises a `ValidationError` instead of silently passing through.
    with pytest.raises(ValidationError):
        User.model_validate({'object': 'user', 'request_id': 'not-a-uuid'})


def test_resolve_type_wraps_validation_error() -> None:
    """A polymorphic sub-type's `ValidationError` is wrapped with context as a `RuntimeError`."""
    with pytest.raises(RuntimeError, match=r'Error constructing .* for type text') as exc_info:
        # `text` resolves to `TextObject`, which requires `plain_text`.
        RichTextBaseObject.model_validate({'type': 'text', 'text': {'content': 'hi'}})

    assert isinstance(exc_info.value.__cause__, ValidationError)


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
