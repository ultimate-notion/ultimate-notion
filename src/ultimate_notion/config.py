"""Handling the configuration for all adapters"""

import os
import re
from pathlib import Path

import tomli
from pydantic import BaseModel, FilePath, field_validator
from pydantic_core.core_schema import ValidationInfo

ENV_ULTIMATE_NOTION_CFG: str = 'ULTIMATE_NOTION_CONFIG'
"""Name of the environment variable to look up the path for the config"""
DEFAULT_ULTIMATE_NOTION_CFG_PATH: str = '.ultimate-notion/config.toml'
"""Default path within $HOME to the configuration file of Ultimate Notion"""
ENV_NOTION_TOKEN = 'NOTION_TOKEN'  # same as in `notion-sdk-py` package
"""Name of the environment variable to look up the Notion token"""

DEFAULT_CFG = f"""\
# Configuration for Ultimate Notion
#
# * Non-absolute paths are always relative to the directory of this file.
# * You can use environment variables in the format ${{env:VAR_NAME}} or ${{env:VAR_NAME|DEFAULT_VALUE}}.

[ultimate_notion]
token = "${{env:{ENV_NOTION_TOKEN}}}"

[google]
client_secret_json = "client_secret.json"
token_json = "token.json"
"""


class UNOCfg(BaseModel):
    """Configuration related to Ultimate Notion itself."""

    token: str | None = None
    cfg_path: FilePath  # will be set automatically


class GoogleCfg(BaseModel):
    """Configuration related to the Google API."""

    client_secret_json: Path | None = None
    token_json: Path | None = None


class Config(BaseModel):
    """Main configuration object."""

    ultimate_notion: UNOCfg
    google: GoogleCfg | None = None

    @field_validator('google')
    @classmethod
    def convert_json_path(cls, v: GoogleCfg | None, info: ValidationInfo) -> GoogleCfg | None:
        def make_rel_path_abs(entry: FilePath):
            if entry is not None and not entry.is_absolute():
                cfg_path: Path = info.data['ultimate_notion'].cfg_path
                entry = cfg_path.parent / entry
            return entry

        if v is not None:
            v.client_secret_json = make_rel_path_abs(v.client_secret_json)
            v.token_json = make_rel_path_abs(v.token_json)

        return v


def get_cfg_file() -> Path:
    """Determines the path of the config file."""
    path_str = os.environ.get(ENV_ULTIMATE_NOTION_CFG, None)
    path = Path.home() / Path(DEFAULT_ULTIMATE_NOTION_CFG_PATH) if path_str is None else Path(path_str)
    return path


def resolve_env_value(value: str) -> str:
    """Resolves environment variable values in the format ${env:VAR_NAME|DEFAULT_VALUE}."""
    match = re.match(r'\${env:(\w+)(?:\|(.*))?}$', value)
    if match:
        var_name = match.group(1)
        default_value = match.group(2)
        return os.environ.get(var_name, default_value)
    return value


def get_cfg() -> Config:
    """Returns the configuration as an object."""
    cfg_path = get_cfg_file()
    with open(cfg_path, 'rb') as fh:
        cfg_dict = tomli.load(fh)

    # Resolve environment variable values in the configuration
    def resolve_values(data):
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, dict):
                    resolve_values(value)
                elif isinstance(value, str):
                    data[key] = resolve_env_value(value)

    resolve_values(cfg_dict)

    # add config path to later resolve relative paths of config values
    if 'ultimate_notion' not in cfg_dict:
        msg = f'The configuration file {cfg_path} does not contain a section [ultimate-notion].'
        raise RuntimeError(msg)

    cfg_dict['ultimate_notion']['cfg_path'] = cfg_path
    return Config.model_validate(cfg_dict)


def get_or_create_cfg() -> Config:
    """Returns the configuration as an object or creates it if it doesn't exist yet."""
    cfg_path = get_cfg_file()
    if not cfg_path.exists():
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(DEFAULT_CFG)
    return get_cfg()
