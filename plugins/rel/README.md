# REL agent plugin

This plugin connects Codex or Claude Code to the MCP server bundled with
`/Applications/REL.app`. Both hosts load the same `rel-browser` skill, MCP
configuration, ten MCP tools, and eight canonical page actions.

- [Install in Codex](https://docs.rel.me/codex-plugin/)
- [Install in Claude Code](https://docs.rel.me/claude-code-plugin/)
- [Read the MCP and tool reference](https://docs.rel.me/mcp/)

REL.app owns Chromium and browser state. The plugin starts only the bundled
`rel-mcp` adapter; it does not include another browser runtime or access REL's
private database, logs, Chromium storage, or proxy credentials. Starting the
adapter does not launch REL.app; validated operational tools start it lazily.
