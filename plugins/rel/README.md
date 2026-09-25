# REL agent plugin

This plugin connects Codex or Claude Code to the MCP server bundled with
`/Applications/REL.app`. Both hosts load the same `rel-browser` and
`crawl-websites-with-rel` skills, MCP configuration, fourteen MCP tools, and
eight canonical page actions.

- [Install in Codex](https://docs.rel.me/codex-plugin/)
- [Install in Claude Code](https://docs.rel.me/claude-code-plugin/)
- [Read the MCP and tool reference](https://docs.rel.me/mcp/)
- [Build a restartable Python crawler](https://docs.rel.me/crawler/)

REL.app owns Chromium and browser state. The plugin starts only the bundled
`rel-mcp` adapter; it does not include another browser runtime or access REL's
private database, logs, Chromium storage, or proxy credentials. Starting the
adapter does not launch REL.app; validated operational tools start it lazily.

## Branding

`assets/rel-logo.png` is REL's canonical blue optical-lens icon, copied from
the app repository's generated `website/zed-theme/public/rel-logo.png` export.
Use that export when updating the plugin artwork; do not redraw or simplify it.
Both Codex's marketplace logo and composer icon use this PNG.
