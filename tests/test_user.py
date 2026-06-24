"""Unit tests for users in Notion."""

from __future__ import annotations

from uuid import UUID

import pytest

from ultimate_notion.errors import UnsetError
from ultimate_notion.obj_api import objects as objs
from ultimate_notion.user import Bot

WORKSPACE_ID = UUID('12345678-1234-1234-1234-1234567890ab')
BOT_ID = UUID('abcdabcd-1234-1234-1234-1234567890ab')


def test_workspace_info_for_own_bot() -> None:
    bot_data = objs.BotTypeData(
        workspace_id=WORKSPACE_ID,
        workspace_name='Test Bot Workspace',
        workspace_limits=objs.WorkSpaceLimits(max_file_upload_size_in_bytes=42),
    )
    bot = Bot.wrap_obj_ref(objs.Bot(id=BOT_ID, bot=bot_data))

    info = bot.workspace_info
    assert info.name == 'Test Bot Workspace'
    assert info.workspace_id == WORKSPACE_ID
    assert info.max_file_upload_size_in_bytes == 42


@pytest.mark.parametrize(
    'bot_data',
    [
        objs.BotTypeData(workspace_id=None, workspace_name=None),
        objs.BotTypeData(workspace_id=WORKSPACE_ID, workspace_name=None),
        objs.BotTypeData(workspace_id=None, workspace_name='Test Bot Workspace'),
    ],
)
def test_workspace_info_unavailable_raises_unset_error(bot_data: objs.BotTypeData) -> None:
    bot = Bot.wrap_obj_ref(objs.Bot(id=BOT_ID, bot=bot_data))
    with pytest.raises(UnsetError):
        _ = bot.workspace_info
