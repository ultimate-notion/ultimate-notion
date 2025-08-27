# Command Line Interface

When Ultimate Notion is installed, a new command `uno` becomes available in your virtual environment. This command
provides quick access to configuration and integration information.

## Usage

The CLI currently supports the following operations:

- **Configuration management** - View your current configuration file location and contents
- **Integration information** - Display details about your Notion integration and environment
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

## Options

The CLI supports a `--log-level` option to control output verbosity. Available levels are `critical`, `error`,
`warning` (default), `info`, and `debug`.

```console
uno --log-level debug info
```

For detailed help on any command, use:

```console
uno <command> --help
```
