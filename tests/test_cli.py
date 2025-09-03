"""Unit tests for the CLI module."""

import logging
import sys
import tempfile
import textwrap
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

import ultimate_notion as uno
from ultimate_notion import Session, __version__
from ultimate_notion.cli import LogLevel, _get_block_class_for_file, app, setup_logging  # noqa: PLC2701


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


@pytest.mark.file_upload
def test_upload_image_by_page_name(notion: Session, root_page: uno.Page) -> None:
    """Test uploading an image file by page name."""
    runner = CliRunner()
    test_page = notion.get_or_create_page(parent=root_page, title='CLI Upload Image Test')
    image_path = 'docs/assets/images/favicon.png'

    with patch('ultimate_notion.cli.Session') as mock_session_class:
        mock_session_class.return_value.__enter__.return_value = notion
        mock_session_class.return_value.__exit__.return_value = None

        result = runner.invoke(app, ['upload', image_path, str(test_page.title)])

    assert result.exit_code == 0
    # Verify the block was actually added
    test_page.reload()
    assert len(test_page.children) > 0
    assert isinstance(test_page.children[-1], uno.Image)


@pytest.mark.file_upload
def test_upload_pdf_by_uuid(notion: Session, root_page: uno.Page, tmp_path: Path) -> None:
    """Test uploading a PDF file by page UUID."""
    runner = CliRunner()
    test_page = notion.get_or_create_page(parent=root_page, title='CLI Upload PDF Test')
    pdf_content = textwrap.dedent("""\
        %PDF-1.4
        1 0 obj
        <<
        /Type /Catalog
        /Pages 2 0 R
        >>
        endobj
        2 0 obj
        <<
        /Type /Pages
        /Kids [3 0 R]
        /Count 1
        >>
        endobj
        3 0 obj
        <<
        /Type /Page
        /Parent 2 0 R
        /MediaBox [0 0 612 792]
        >>
        endobj
        xref
        0 4
        0000000000 65535 f
        0000000010 00000 n
        0000000053 00000 n
        0000000125 00000 n
        trailer
        <<
        /Size 4
        /Root 1 0 R
        >>
        startxref
        230
        %%EOF""").encode('utf-8')

    pdf_file = tmp_path / 'test.pdf'
    pdf_file.write_bytes(pdf_content)

    with patch('ultimate_notion.cli.Session') as mock_session_class:
        mock_session_class.return_value.__enter__.return_value = notion
        mock_session_class.return_value.__exit__.return_value = None

        result = runner.invoke(app, ['upload', str(pdf_file), str(test_page.id)])

    assert result.exit_code == 0

    # Verify the block was actually added
    test_page.reload()
    assert len(test_page.children) > 0
    assert isinstance(test_page.children[-1], uno.PDF)


def test_upload_nonexistent_file() -> None:
    """Test uploading a file that doesn't exist."""
    runner = CliRunner()

    result = runner.invoke(app, ['upload', 'nonexistent_file.txt', 'some-page'])

    assert result.exit_code == 1
    assert "Error: File 'nonexistent_file.txt' does not exist" in result.stderr


def test_upload_directory_instead_of_file(tmp_path: Path) -> None:
    """Test trying to upload a directory instead of a file."""
    runner = CliRunner()
    test_dir = tmp_path / 'test_directory'
    test_dir.mkdir()

    result = runner.invoke(app, ['upload', str(test_dir), 'some-page'])

    assert result.exit_code == 1
    assert f"Error: '{test_dir}' is not a file" in result.stderr


def test_upload_invalid_page_uuid(notion: Session) -> None:
    """Test uploading to a page with invalid UUID."""
    runner = CliRunner()

    # Create a temporary test file
    with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tmp_file:
        tmp_file.write(b'test content')
        tmp_file_path = tmp_file.name

        invalid_uuid = '12345678-1234-1234-1234-123456789abc'

        with patch('ultimate_notion.cli.Session') as mock_session_class:
            mock_session_class.return_value.__enter__.return_value = notion
            mock_session_class.return_value.__exit__.return_value = None

            result = runner.invoke(app, ['upload', tmp_file_path, invalid_uuid])

        assert result.exit_code == 1
        assert f"Error: Page with UUID '{invalid_uuid}' not found" in result.stderr


@pytest.mark.vcr()
def test_upload_nonexistent_page_name(notion: Session) -> None:
    """Test uploading to a page that doesn't exist by name."""
    runner = CliRunner()

    with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tmp_file:
        tmp_file.write(b'test content')
        tmp_file_path = tmp_file.name

        nonexistent_page = 'This Page Does Not Exist At All'

        with patch('ultimate_notion.cli.Session') as mock_session_class:
            mock_session_class.return_value.__enter__.return_value = notion
            mock_session_class.return_value.__exit__.return_value = None

            result = runner.invoke(app, ['upload', tmp_file_path, nonexistent_page])

        assert result.exit_code == 1
        assert f"Error: No page found with name '{nonexistent_page}'" in result.stderr


@pytest.mark.file_upload
def test_upload_generic_file(notion: Session, root_page: uno.Page, tmp_path: Path) -> None:
    """Test uploading a generic file that falls back to File block."""
    runner = CliRunner()

    test_page = notion.get_or_create_page(parent=root_page, title='CLI Upload Generic File Test')
    text_file = tmp_path / 'test.txt'
    text_file.write_text('This is a test file content.')

    with patch('ultimate_notion.cli.Session') as mock_session_class:
        mock_session_class.return_value.__enter__.return_value = notion
        mock_session_class.return_value.__exit__.return_value = None

        result = runner.invoke(app, ['upload', str(text_file), 'CLI Upload Generic File Test'])

    assert result.exit_code == 0

    # Verify the block was actually added
    test_page.reload()
    assert len(test_page.children) > 0
    assert isinstance(test_page.children[-1], uno.File)


def test_upload_file_type_detection_with_filetype(tmp_path: Path) -> None:
    """Test that file type detection works with filetype library for files without proper extensions."""
    png_content = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13'
        b'\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc```'
        b'\x00\x00\x00\x04\x00\x01]\xcc\xdb\x8d\x00\x00\x00\x00IEND\xaeB`\x82'
    )

    fake_txt_file = tmp_path / 'image.txt'  # Wrong extension
    fake_txt_file.write_bytes(png_content)

    # Should detect as Image despite .txt extension
    block_class = _get_block_class_for_file(fake_txt_file)
    assert block_class == uno.Image
