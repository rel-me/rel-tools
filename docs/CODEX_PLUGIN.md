# Codex plugin

The REL plugin connects Codex to REL's persistent embedded Chromium sessions.
It configures the MCP server bundled with the installed app and adds the
`rel-browser` skill for interactive browser work plus the
`crawl-websites-with-rel` skill for restartable, history-preserving crawls.

Related documents: [MCP server](MCP.md), [browser diagnostics](BROWSER_DIAGNOSTICS.md),
[session scope](SESSIONS.md) and [CLI](CLI.md).

For provider setup and per-Session assignment, see [Configure proxies](PROXIES.md).

## Requirements

- macOS 15 or later;
- REL installed on the Mac;
- a Codex release with plugin marketplace support.

REL.app must be installed so Codex can start its bundled
`Contents/Resources/rel-mcp` adapter. The app does not need to be running for
plugin discovery or `rel_status`; other validated tool calls start it lazily.

The plugin checks `/Applications/REL.app`, `~/Applications/REL.app`, then macOS
application registration using bundle ID `me.rel.Rel`. Set `REL_APP_PATH` in the
MCP host's environment to select a custom bundle path. Discovery does not launch
REL; an invalid override reports an error without falling back.

## Install

Add this repository as a Codex marketplace, then install the `rel` plugin:

```sh
codex plugin marketplace add https://github.com/rel-me/rel-tools.git --ref main
codex plugin add rel@rel
```

Start a new Codex task after installation so the task loads the plugin's skill
and MCP tools.

## What the plugin adds

The plugin contains:

- the bundled REL MCP server configuration, with automatic app discovery;
- the `rel-browser` skill for safe session selection and browser workflows;
- the `crawl-websites-with-rel` skill for rendered-link discovery, readiness,
  checkpoints, capture metadata, bounded retries, and session recovery;
- the app-bundled MCP tools, including bounded semantic reading, opt-in untrusted website notifications,
  observations, session traces, non-blocking debug state, optional diagnostic
  bundles, and inline or file-backed screenshots;
- all eight canonical page actions: `click`, `wait-for`, `type`, `clear`,
  `press`, `select`, `wait`, and `click-link`.

The plugin does not add another browser backend. REL.app remains the only
Chromium owner, and every tool call flows through the local versioned API. See
the [MCP tool reference](MCP.md#tools) for complete inputs and action semantics.

## Verify

Begin with a read-only check in a new task:

```text
Use the REL MCP server. Call rel_status, then rel_list_sessions. Do not navigate anywhere.
```

Codex should discover the `rel_*` tools supplied by the installed app without opening REL. If REL is already
running, `rel_status` reports the app, local agent, Browser Proxy, and embedded
Chromium bridge. Otherwise it returns the local connection error without
launching the app; `rel_list_sessions` then starts REL lazily.

## Diagnose navigation

While a selected Session is waiting or after it fails, use `rel_debug_state`
and `rel_session_trace` with its exact ID. Preserve the original error details
and snapshot age before retrying or replacing the Session. Use `rel_debug_bundle`
for a bounded shareable artifact; HTML and screenshots default to off.

These tools are discovered from the installed app's bundled `rel-mcp`. A plugin
update changes its instructions and packaging, not the app's API. If diagnostics
are missing from discovery, use a matching REL app build and restart the MCP
connection; do not inspect internal storage to fill the gap.

## Update

Refresh the marketplace snapshot and reinstall the current plugin version:

```sh
codex plugin marketplace upgrade rel
codex plugin add rel@rel
```

Start another new task after updating so it uses the refreshed plugin cache.
