"""Handling the configuration for all adapters"""

import os
from pathlib import Path

import tomli
from pydantic import BaseModel, FilePath, field_validator
from pydantic_core.core_schema import ValidationInfo

ULTIMATE_NOTION_ENV: str = 'ULTIMATE_NOTION_CONFIG'
"""Name of the environment variable to look up the path for the config"""
ULTIMATE_NOTION_CFG_PATH: str = '.ultimate-notion/config.toml'
"""Path within $HOME to the configuration file of Ultimate Notion"""


class GoogleCfg(BaseModel):
    """Configuration related to the Google API"""

    client_secret_json: Path | None = None
    token_json: Path | None = None


class Config(BaseModel):
    """Main configuration object"""

    cfg_path: FilePath
    Google: GoogleCfg | None = None

    @field_validator('Google')
    @classmethod
    def convert_json_path(cls, v: GoogleCfg, info: ValidationInfo) -> GoogleCfg:
        def make_rel_path_abs(entry: FilePath):
            if entry is not None and not entry.is_absolute():
                cfg_path: Path = info.data['cfg_path']
                entry = cfg_path.parent / entry
            return entry

        v.client_secret_json = make_rel_path_abs(v.client_secret_json)
        v.token_json = make_rel_path_abs(v.token_json)

        return v


def get_cfg_file() -> Path:
    """Determines the path of the config file"""
    path_str = os.environ.get(ULTIMATE_NOTION_ENV, None)
    path = Path.home() / Path(ULTIMATE_NOTION_CFG_PATH) if path_str is None else Path(path_str)
    return path


def get_cfg() -> Config:
    """Returns the configuration as an object"""
    cfg_path = get_cfg_file()
    with open(cfg_path, 'rb') as fh:
        cfg_dict = tomli.load(fh)
    # add config path to later resolve relative paths of config values
    cfg_dict['cfg_path'] = cfg_path
    return Config.model_validate(cfg_dict)
