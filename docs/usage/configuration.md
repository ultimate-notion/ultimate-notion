# Ultimate Notion configuration

Ultimate Notion uses a [TOML] configuration file to manage settings and authentication. There are two ways to
provide your configuration:

1. **Environment variable**: Set `ULTIMATE_NOTION_CONFIG` to point to your config file
2. **Default location**:
    * macOS/Linux: `~/.ultimate-notion/config.toml`
    * Windows: `$HOME/.ultimate-notion/config.toml`

## Creating a configuration file

To create a default configuration file, run:

```console
uno config
```

See the [CLI documentation](cli.md) for more configuration commands.

## Configuration options

The configuration file manages your Notion token and other settings. You can either:

* Set your token directly in the config file
* Use environment variables (recommended for security)

### Default configuration

The default configuration file contains:

```toml
[ultimate_notion]
sync_state_dir = "sync_states"
debug = "${env:ULTIMATE_NOTION_DEBUG|false}"
token = "${env:NOTION_TOKEN}"

[google]
client_secret_json = "client_secret.json"
token_json = "token.json"
```

Let's examine each setting:

**Token (required)**: The `token` setting specifies your Notion integration token. You have two options:

* **Environment variable (recommended)**: Set `export NOTION_TOKEN="ntn_your_token_here"`
* **Direct in file**: Replace `"${env:NOTION_TOKEN}"` with `"ntn_your_token_here"`

Using environment variables is more secure as it avoids storing sensitive tokens in files.

**Debug mode**: The `debug` setting controls logging verbosity. Set to `true` for extensive debug information
when reporting [issues]. You can either:

* Set environment variable: `export ULTIMATE_NOTION_DEBUG=true`
* Edit config directly: `debug = true`

!!! info "Environment variable syntax"
    The `${env:VARIABLE_NAME|default}` format looks up environment variables.
    If the variable exists, its value is used; otherwise, the default after `|` is applied.
    If no default is provided and the variable is missing, configuration loading fails.

**Google Tasks integration**: The `sync_state_dir` and `[google]` section are only needed for syncing
Ultimate Notion databases with Google Tasks:

* `sync_state_dir`: Directory for storing sync state files
* `client_secret_json`: Google OAuth client secret file
* `token_json`: Google OAuth token storage

All non-absolute paths are relative to the config file directory (e.g., `token.json` will be in the same
directory as `config.toml`).

[TOML]: https://toml.io/
[issues]: https://github.com/ultimate-notion/ultimate-notion/issues
