import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from ultimate_notion.adapters.config import Config, GoogleCfg, get_cfg, get_cfg_file


@pytest.fixture
def config_file():
    # Create a temporary file
    with tempfile.NamedTemporaryFile() as file:
        yield file.name


def test_get_cfg_file():
    expected_path = Path.home() / '.ultimate-notion/config.toml'
    assert get_cfg_file() == expected_path


def test_get_cfg_no_google(config_file):
    cfg_path = config_file
    expected_cfg = Config(cfg_path=cfg_path, Google=None)

    with patch('ultimate_notion.adapters.config.get_cfg_file', return_value=cfg_path), patch(
        'tomli.load', return_value={}
    ):
        cfg = get_cfg()

    assert cfg == expected_cfg


def test_get_cfg_file_custom_path(config_file):
    with patch.dict(os.environ, {'ULTIMATE_NOTION_CONFIG': str(config_file)}):
        assert str(get_cfg_file()) == config_file


def test_get_cfg(config_file):
    google_cfg = GoogleCfg(
        client_secret_json=Path('/path/to/client_secret.json'), token_json=Path('/path/to/token.json')
    )
    expected_cfg = Config(cfg_path=config_file, Google=google_cfg)

    with patch('ultimate_notion.adapters.config.get_cfg_file', return_value=config_file), patch(
        'tomli.load', return_value={'Google': google_cfg.model_dump()}
    ):
        cfg = get_cfg()

    assert cfg == expected_cfg
