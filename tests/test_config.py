import logging
import os
from pathlib import Path
from unittest.mock import patch

from pytest import LogCaptureFixture, MonkeyPatch

from ultimate_notion.config import (
    ENV_NOTION_TOKEN,
    activate_debug_mode,
    get_cfg_file,
    get_or_create_cfg,
    resolve_env_value,
)


def test_get_cfg_file(custom_config: Path) -> None:
    assert get_cfg_file() == custom_config


def test_get_or_create_cfg(custom_config: Path) -> None:
    with patch.dict(os.environ, {ENV_NOTION_TOKEN: 'my-token'}):
        cfg = get_or_create_cfg()

    assert cfg.ultimate_notion.token == 'my-token'
    assert cfg.ultimate_notion.cfg_path == custom_config
    assert cfg.google is not None
    assert isinstance(cfg.google.client_secret_json, Path)
    assert isinstance(cfg.google.token_json, Path)


def test_resolve_env_value() -> None:
    assert resolve_env_value('${env:NON_EXISTENT_ENV_VAR}') is None
    assert resolve_env_value('${env:NON_EXISTENT_ENV_VAR|default}') == 'default'
    assert resolve_env_value('${env:NON_EXISTENT_ENV_VAR|}') == ''

    assert resolve_env_value('this/is/a/path') == 'this/is/a/path'

    with patch.dict(os.environ, {'VAR': 'value'}):
        assert resolve_env_value('${env:VAR}') == 'value'
        assert resolve_env_value('${env:VAR|default}') == 'value'


def test_debug_mode(caplog: LogCaptureFixture, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(logging, 'basicConfig', lambda **kwargs: None)
    test_logger = logging.getLogger('test_logger')
    monkeypatch.setattr(logging, 'getLogger', lambda *args: test_logger)
    activate_debug_mode()
    assert 'is running in debug mode.' in caplog.text
