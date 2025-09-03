"""Unit tests for the CLI module."""

import logging
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from ultimate_notion import Session, __version__
from ultimate_notion.cli import LogLevel, app, setup_logging


@patch('logging.basicConfig')
def test_setup_logging_configures_correctly(mock_basic_config: Mock) -> None:
    """Test that setup_logging configures logging with the correct parameters."""
    # Test with INFO level
    setup_logging(LogLevel.INFO)

    mock_basic_config.assert_called_with(
        level=logging.INFO,
        stream=sys.stdout,
        format='[%(asctime)s] %(levelname)s:%(name)s:%(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    # Reset the mock and test with DEBUG level
    mock_basic_config.reset_mock()
    setup_logging(LogLevel.DEBUG)

    mock_basic_config.assert_called_with(
        level=logging.DEBUG,
        stream=sys.stdout,
        format='[%(asctime)s] %(levelname)s:%(name)s:%(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )


def test_config_command_displays_configuration(custom_config: Path) -> None:
    """Test that config command displays the configuration file and its contents."""
    runner = CliRunner()
    result = runner.invoke(app, ['config'])

    assert result.exit_code == 0

    # Check that config file path is displayed
    assert 'Config file:' in result.stdout
    assert str(custom_config) in result.stdout

    # Check that configuration section is displayed
    assert 'Configuration:' in result.stdout
    assert '-' * 40 in result.stdout

    # Should contain some TOML-formatted configuration
    assert '[ultimate_notion]' in result.stdout or 'ultimate_notion' in result.stdout


@pytest.mark.vcr()
def test_info_command_displays_system_and_notion_info(notion: Session) -> None:
    """Test that info command displays system information and Notion integration details."""
    runner = CliRunner()

    # Mock the Session creation in the CLI to use our fixture
    with patch('ultimate_notion.cli.Session') as mock_session_class:
        mock_session_class.return_value.__enter__.return_value = notion
        mock_session_class.return_value.__exit__.return_value = None

        result = runner.invoke(app, ['info'])

    assert result.exit_code == 0

    # Check system information
    assert f'Python version: {sys.version}' in result.stdout
    assert f'Ultimate Notion version: {__version__}' in result.stdout

    # Check Notion integration information
    assert 'Notion integration:' in result.stdout
    assert '- name:' in result.stdout
    assert '- id:' in result.stdout

    # Check workspace information section
    assert 'Workspace info:' in result.stdout


def test_log_level_option_affects_logging() -> None:
    """Test that the --log-level option correctly sets the logging level."""
    runner = CliRunner()

    # Test with debug level
    with patch('ultimate_notion.cli.setup_logging') as mock_setup:
        result = runner.invoke(app, ['--log-level', 'debug', 'config'])
        assert result.exit_code == 0
        mock_setup.assert_called_with(LogLevel.DEBUG)

    # Test with error level
    with patch('ultimate_notion.cli.setup_logging') as mock_setup:
        result = runner.invoke(app, ['--log-level', 'error', 'config'])
        assert result.exit_code == 0
        mock_setup.assert_called_with(LogLevel.ERROR)
