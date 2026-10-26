# Claude Code plugin

The REL plugin connects Claude Code to REL's persistent embedded Chromium
sessions. It configures the MCP server bundled with the installed app and adds
the namespaced `/rel:rel-browser` skill for interactive browser work plus
`/rel:crawl-websites-with-rel` for restartable, history-preserving crawls.

Related documents: [MCP server](MCP.md), [browser diagnostics](BROWSER_DIAGNOSTICS.md),
[session scope](SESSIONS.md) and [CLI](CLI.md).

## Requirements

- macOS 15 or later;
- REL 0.1.156 or later installed on the Mac, with the Project/Session MCP adapter;
- a current Claude Code release with plugin marketplace support.

The launcher requires adapter version 0.1.156 or later and the
`rel-project-sessions-v1` API contract. An unsupported adapter stops with an
update instruction before exposing tools. Operational calls reject older local
runtimes as well. Restart the MCP connection after updating the plugin or app.

REL.app must be installed so Claude Code can start its bundled
`Contents/Resources/rel-mcp` adapter. The app does not need to be running for
plugin discovery or `rel_status`; other validated tool calls start it lazily.

The plugin checks `/Applications/REL.app`, `~/Applications/REL.app`, then macOS
application registration using bundle ID `me.rel.Rel`. Set `REL_APP_PATH` in the
MCP host's environment to select a custom bundle path. Discovery does not launch
REL; an invalid override reports an error without falling back.

## Install

Add this repository as a Claude Code marketplace, then install the `rel` plugin:

```sh
claude plugin marketplace add rel-me/rel-tools
claude plugin install rel@rel
```

Restart Claude Code after installation. If an interactive installation asks for
MCP approval or reports that a reload is required, approve the local REL server
and run `/reload-plugins`.

## What the plugin adds

The plugin contains:

- the bundled REL MCP server configuration, with automatic app discovery;
- the namespaced `/rel:rel-browser` skill for safe session selection and browser
  workflows;
- the namespaced `/rel:crawl-websites-with-rel` skill for rendered-link
  discovery, readiness, checkpoints, capture metadata, bounded retries, and
  session recovery;
- the app-bundled MCP tools, including bounded semantic reading, opt-in untrusted website notifications,
  observations, session traces, non-blocking debug state, optional diagnostic
  bundles, and inline or file-backed screenshots;
- all eight canonical page actions: `click`, `wait-for`, `type`, `clear`,
  `press`, `select`, `wait`, and `click-link`.

The plugin does not add another browser backend. REL.app remains the only
Chromium owner, and every tool call flows through the local versioned API. See
the [MCP tool reference](MCP.md#tools) for complete inputs and action semantics.

## Verify

Begin with a read-only check after restarting or reloading plugins:

```text
Use the REL MCP server. Call rel_status, then rel_list_sessions. Do not navigate anywhere.
```

Claude Code should discover the REL MCP tools supplied by the installed app without opening REL. If REL is
already running, `rel_status` reports the app, local agent, Browser Proxy, and
embedded Chromium bridge. Otherwise it returns the local connection error
without launching the app; `rel_list_sessions` then starts REL lazily.

## Diagnose navigation

While a selected Session is waiting or after it fails, use `rel_debug_state`
and `rel_session_trace` with its exact ID. Preserve the original error details
and snapshot age before retrying or replacing the Session. Use `rel_debug_bundle`
for a bounded shareable artifact; HTML and screenshots default to off.

Select a Project with `rel_list_projects`, then inspect its Sessions with
`rel_list_sessions({"project_id":"ProjectDefault"})`. To create independent
browser state, use `rel_create_session` with `project_id` and optional `profile`;
reuse the returned `session_id`. A Profile name never identifies a live login.
Use `rel_close_session` for one exact Session when the workflow owns cleanup.

## Update

Update the installed plugin, then restart Claude Code to apply it:

```sh
claude plugin update rel@rel
```
