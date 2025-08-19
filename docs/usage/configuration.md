# Ultimate Notion configuration

Ultimate Notion looks up the environment variable `ULTIMATE_NOTION_CONFIG` for a configuration [TOML] file.
If this variable is not set, it defaults to `~/.ultimate-notion/config.toml` under macOS/Linux and
`$HOME/.ultimate-notion/config.toml` under Windows systems.

If no configuration file is found, a default one is created automatically. This default file will set the
Notion token to be looked up using the environment variable `NOTION_TOKEN`.
Alternatively, you can set your token directly in the configuration file.

The default configuration file looks like:

```toml
[ultimate_notion]
sync_state_dir = "sync_states"
debug = "${env:ULTIMATE_NOTION_DEBUG|false}"
token = "${env:NOTION_TOKEN}"

[google]
client_secret_json = "client_secret.json"
token_json = "token.json"
```

The most important key is `token` within the `ultimate_notion` section. You need to either enter the
*Internal Integration Token* directly or set it in the referenced environment variable `NOTION_TOKEN`
to avoid storing your token in a file.

Setting `debug` to `true` will generate extensive debug information, which is helpful if you want to report an [issue].

The key `sync_state_dir` as well as the whole `google` section is only important if you want to sync an
Ultimate Notion database with Google Tasks. All provided non-absolute paths are always relative to the
directory of configuration file, e.g. `token.json` will reside in the same directory as `config.toml`.

Note that the value `${env:ENV_VARIABLE|default}` allows you to specify that Ultimate Notion should first
try to look up the environment variable `ENV_VARIABLE` and if not found use the `default` value. The default
part can be omitted so that reading the configuration fails if an expected environment variable is not
properly set.
