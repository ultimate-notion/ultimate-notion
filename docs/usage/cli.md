# Command Line Interface

When Ultimate Notion is installed, a new command `uno` becomes available in your virtual environment. This command
provides quick access to configuration and integration information.

## Usage

The CLI currently supports the following operations:

- **Configuration management** - View your current configuration file location and contents
- **Integration information** - Display details about your Notion integration and environment
- **File uploads** - Upload files to Notion pages with automatic block type detection
- **System diagnostics** - Check version information and workspace details

To see all available commands and options:

```console
uno --help
```

!!! info "Shell Auto-completion"
    The CLI supports shell auto-completion for faster command entry. Install it with:
    ```console
    uno --install-completion
    ```

## Available Commands

### `config`

Display the current configuration file path and contents:

```console
uno config
```

### `info`

Display information about your Notion integration, including version details and workspace information:

```console
uno info
```

### `upload`

Upload a file to a Notion page and automatically append it as the appropriate block type:

```console
uno upload <file_path> <page_name_or_uuid>
```

The command automatically detects the file type and creates the appropriate block:

- **Images** (`.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, etc.) → Image block
- **Videos** (`.mp4`, `.avi`, `.mov`, `.wmv`, etc.) → Video block
- **PDFs** (`.pdf`) → PDF block
- **All other files** → File block

#### Examples

Upload an image to a page by name:

```console
uno upload screenshot.png "My Project Notes"
```

Upload a PDF to a page by UUID:

```console
uno upload document.pdf 12345678-1234-1234-1234-123456789abc
```

Upload a video file:

```console
uno upload demo.mp4 "Product Demo Page"
```

## Options

The CLI supports a `--log-level` option to control output verbosity. Available levels are `critical`, `error`,
`warning` (default), `info`, and `debug`.

```console
uno --log-level debug info
```

!!! tip "Upload Command Logging"
    The `upload` command shows detailed progress information when using `--log-level info` or `--log-level debug`.
    This includes file upload progress, page lookup details, and file URLs. By default, only success messages
    and errors are shown.

    ```console
    uno --log-level info upload document.pdf "My Page"
    ```

For detailed help on any command, use:

```console
uno <command> --help
```
