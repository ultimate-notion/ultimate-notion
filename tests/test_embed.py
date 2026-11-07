from __future__ import annotations

import pytest
from pydantic import ValidationError

from ultimate_notion.blocks import Embed
from ultimate_notion.obj_api.blocks import Embed as ObjEmbed
from ultimate_notion.obj_api.blocks import EmbedTypeData


@pytest.fixture(autouse=True)
def notion_cleanups() -> None:
    """Disable live cleanup for isolated unit tests."""


def test_read_embed_signed_url() -> None:
    embed = Embed.wrap_obj_ref(ObjEmbed.model_validate({'embed': {'url': 'https://example.com/signed?token=abc'}}))
    assert embed.url == 'https://example.com/signed?token=abc'


@pytest.mark.parametrize('url', [None, 'https://example.com/chart'])
def test_invalid_embed_sources(url: str | None) -> None:
    data: dict[str, object] = {'url': url}
    if url is not None:
        data['file_upload'] = {'id': '59833787-2cf9-4fdf-8782-e53db20768a5'}
    with pytest.raises(ValidationError):
        EmbedTypeData.model_validate(data)
