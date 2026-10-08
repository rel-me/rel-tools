# REL agent plugin

This plugin connects Codex or Claude Code to the MCP server bundled with
the installed REL app. Both hosts load the same `rel-browser` and
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

## App discovery

The plugin checks `/Applications/REL.app`, then `~/Applications/REL.app`, then
asks macOS to locate the registered app with bundle ID `me.rel.Rel`. This also
supports renamed app bundles and custom locations. Discovery does not open REL.
Set `REL_APP_PATH` in the MCP host's environment to choose an explicit app bundle,
for example `/Volumes/Apps/REL.app`. An invalid override reports an error rather
than selecting another installation. The launcher executes the selected app's
`Contents/Resources/rel-mcp` directly and preserves its stdio and exit status.

## Branding

`assets/rel-logo.png` is REL's canonical blue optical-lens icon, copied from
the app repository's generated `website/zed-theme/public/rel-logo.png` export.
Use that export when updating the plugin artwork; do not redraw or simplify it.
Both Codex's marketplace logo and composer icon use this PNG.
