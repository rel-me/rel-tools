# rel-cli

`rel-cli` provides the `rel` command and the standalone `rel-mcp` stdio adapter
for the local, versioned API exposed by REL.app. It contains no browser runtime,
session storage, proxy credentials, or proprietary app implementation.

REL.app must be installed. The CLI starts it when a command requires the local
agent. It uses its enclosing app bundle when bundled, otherwise checks
`/Applications/REL.app`, `~/Applications/REL.app`, and macOS application
registration. Set `REL_APP_PATH` to override discovery with a custom app bundle.

```sh
cargo install --git https://github.com/rel-me/rel-tools --package rel-cli
rel health
rel navigate https://example.com
rel capture > example.html
rel-mcp --help
```

See [`docs/CLI.md`](../../docs/CLI.md) and
[`docs/MCP.md`](../../docs/MCP.md) for the complete command and MCP contracts.
