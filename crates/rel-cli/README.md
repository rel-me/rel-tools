# rel-cli

`rel-cli` provides the `rel` command and the standalone `rel-mcp` stdio adapter
for the local, versioned API exposed by Rel.app. It contains no browser runtime,
session storage, proxy credentials, or proprietary app implementation.

Rel.app must be installed in `/Applications`. The CLI starts it when a command
requires the local agent.

```sh
cargo install --git https://github.com/rel-me/rel-tools --package rel-cli
rel health
rel navigate https://example.com
rel capture > example.html
rel-mcp --help
```

See [`docs/CLI.md`](../../docs/CLI.md) and
[`docs/MCP.md`](../../docs/MCP.md) for the complete command and MCP contracts.
