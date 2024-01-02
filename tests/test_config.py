import os
from pathlib import Path
from unittest.mock import patch

from ultimate_notion.config import (
    ENV_NOTION_TOKEN,
    get_cfg_file,
    get_or_create_cfg,
    resolve_env_value,
)


def test_get_cfg_file(custom_config):
    assert str(get_cfg_file()) == custom_config


def test_get_or_create_cfg(custom_config):
    with patch.dict(os.environ, {ENV_NOTION_TOKEN: 'my-token'}):
        cfg = get_or_create_cfg()

    assert cfg.ultimate_notion.token == 'my-token'
    assert cfg.ultimate_notion.cfg_path == Path(custom_config)
    assert isinstance(cfg.gtasks.client_secret_json, Path)
    assert isinstance(cfg.gtasks.token_json, Path)


def test_resolve_env_value():
    assert resolve_env_value('${env:NON_EXISTENT_ENV_VAR}') is None
    assert resolve_env_value('${env:NON_EXISTENT_ENV_VAR|default}') == 'default'
    assert resolve_env_value('${env:NON_EXISTENT_ENV_VAR|}') == ''

    assert resolve_env_value('this/is/a/path') == 'this/is/a/path'

    with patch.dict(os.environ, {'VAR': 'value'}):
        assert resolve_env_value('${env:VAR}') == 'value'
        assert resolve_env_value('${env:VAR|default}') == 'value'
