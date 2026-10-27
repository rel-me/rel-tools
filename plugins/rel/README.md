# REL agent plugin

This plugin connects Codex or Claude Code to the MCP server bundled with
the installed REL app. Both hosts load the same `rel-browser` and
`crawl-websites-with-rel` skills, MCP configuration, and canonical page actions. Available tools are discovered
from the installed app's bundled adapter; the plugin has no separate tool allowlist.

- [Install in Codex](https://docs.rel.me/codex-plugin/)
- [Install in Claude Code](https://docs.rel.me/claude-code-plugin/)
- [Read the MCP and tool reference](https://docs.rel.me/mcp/)
- [Diagnose navigation failures](https://docs.rel.me/browser-diagnostics/)
- [Build a restartable Python crawler](https://docs.rel.me/crawler/)

REL.app owns Chromium and browser state. The plugin starts only the bundled
`rel-mcp` adapter; it does not include another browser runtime or access REL's
private database, logs, Chromium storage, or proxy credentials. Starting the
adapter does not launch REL.app; validated operational tools start it lazily.

## Domain skills

The plugin bundles a site-specific skills collection in `plugins/rel/skills/`:

| Skill | Domain | Guidance |
| --- | --- | --- |
| `rel-reddit` | reddit.com | Login, private cookie export, fresh-cookie Session creation, bounded 429 recovery, and configured rotating routes |
| `rel-zillow` | zillow.com | Profile settings, geographic filters, maps, and property details |
| `rel-craigslist` | craigslist.org | Regional searches, category scope, postings, and expiry |
| `rel-google` | google.com Search | Native identity, direct routing, query scope, and source verification |
| `rel-x` | x.com, twitter.com | Login snapshots, search tabs, timelines, and thread coverage |
| `rel-duckduckgo` | duckduckgo.com | Regional search, result expansion, and source links |
| `rel-loopnet` | loopnet.com | Commercial-property filters, units, and gated details |

These skills load for their own domains and are available to both plugin hosts.
Their setup guidance comes from local REL.app Profiles inspected on 2026-10-27;
the plugin does not install those Profiles or ship proxy aliases, credentials,
or cookie files. Discover current Profiles before creating a Session.
RYM, AOTY, Metacritic, and Discogs are excluded from this collection.

Reddit's fresh-cookie and rotating-route workflow is specific to Reddit. It
honors rate-limit waits and bounds replacement attempts; it cannot guarantee
access. Cookie-file selection is currently an app workflow, not a CLI/MCP
creation option, and REL has no public Session reset API. See
[cookie files](https://docs.rel.me/app/#cookie-files) and
[Session scope](https://docs.rel.me/sessions/).

## Browser diagnostics

REL 0.1.156 or later and a bundled adapter advertising
`rel-project-sessions-v1` are required. The launcher checks both before starting
MCP; an old adapter fails with an update instruction instead of exposing obsolete
tools. Operational calls also validate the connected runtime's version, so a
new adapter cannot silently use an older running service.

Use `rel_list_projects` and `rel_list_sessions` to select scope. Create with
`rel_create_session({"project_id":"ProjectDefault","profile":"Reddit"})`, then
use the returned `session_id` for browser work. Sessions are independent unless
sharing is explicitly selected with `group_id`. Close one Session with
`rel_close_session`; there is no group-wide close tool.

`rel_debug_state`, `rel_session_trace`, and `rel_debug_bundle` inspect an exact
Session. State/trace reads do not wait behind its active browser operation.
HTML and screenshots require explicit opt-in for bundle export.

## App discovery

The plugin checks `/Applications/REL.app`, then `~/Applications/REL.app`, then
asks macOS to locate the registered app with bundle ID `me.rel.Rel`. This also
supports renamed app bundles and custom locations. Discovery does not open REL.
Set `REL_APP_PATH` in the MCP host's environment to choose an explicit app bundle,
for example `/Volumes/Apps/REL.app`. An invalid override reports an error rather
than selecting another installation. The launcher executes the selected app's
`Contents/Resources/rel-mcp` after version and contract validation, sets `REL_APP_PATH` to the selected
bundle for lazy startup, and preserves its stdio and exit status.

## Branding

`assets/rel-logo.png` is REL's canonical blue optical-lens icon, copied from
the app repository's generated `website/zed-theme/public/rel-logo.png` export.
Use that export when updating the plugin artwork; do not redraw or simplify it.
Both Codex's marketplace logo and composer icon use this PNG.
