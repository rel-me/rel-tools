# Claude Code plugin

The REL plugin connects Claude Code to REL's persistent embedded Chromium
sessions. It configures the MCP server bundled with the installed app and adds
the namespaced `/rel:rel-browser` skill with workflow, action, screenshot,
session, proxy, and safety guidance.

Related documents: [MCP server](MCP.md) and [CLI](CLI.md).

## Requirements

- macOS 15 or later;
- REL installed at `/Applications/REL.app`;
- a current Claude Code release with plugin marketplace support.

REL.app must be installed so Claude Code can start its bundled
`Contents/Resources/rel mcp` adapter. The app does not need to be running for
plugin discovery or `rel_status`; other validated tool calls start it lazily.

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

- the bundled REL MCP server configuration, using the absolute installed-app
  path;
- the namespaced `/rel:rel-browser` skill for safe session selection and browser
  workflows;
- all ten MCP tools, including observations, session-group closing, and inline or
  file-backed screenshots;
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

Claude Code should discover seven REL MCP tools without opening REL. If REL is
already running, `rel_status` reports the app, local agent, Browser Proxy, and
embedded Chromium bridge. Otherwise it returns the local connection error
without launching the app; `rel_list_sessions` then starts REL lazily.

## Update

Update the installed plugin, then restart Claude Code to apply it:

```sh
claude plugin update rel@rel
```
