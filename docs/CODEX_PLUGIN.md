# Codex plugin

The REL plugin connects Codex to REL's persistent embedded Chromium sessions.
It configures the MCP server bundled with the installed app and adds the
`rel-browser` skill with workflow, action, screenshot, session, proxy, and safety
guidance.

Related documents: [MCP server](MCP.md) and [CLI](CLI.md).

## Requirements

- macOS 15 or later;
- REL installed at `/Applications/REL.app`;
- a Codex release with plugin marketplace support.

REL.app must be available before the plugin can start its bundled
`Contents/Resources/rel mcp` adapter.

## Install

Add this repository as a Codex marketplace, then install the `rel` plugin:

```sh
codex plugin marketplace add rel-me/rel-tools
codex plugin add rel@rel
```

Start a new Codex task after installation so the task loads the plugin's skill
and MCP tools.

## What the plugin adds

The plugin contains:

- the bundled REL MCP server configuration, using the absolute installed-app
  path;
- the `rel-browser` skill for safe session selection and browser workflows;
- all seven MCP tools, including inline or file-backed screenshots;
- all nine canonical page actions: `click`, `wait-for`, `type`, `fill`, `clear`,
  `press`, `select`, `wait`, and `click-link`.

The plugin does not add another browser backend. REL.app remains the only
Chromium owner, and every tool call flows through the local versioned API. See
the [MCP tool reference](MCP.md#tools) for complete inputs and action semantics.

## Verify

Begin with a read-only check in a new task:

```text
Use the REL MCP server. Call rel_status, then rel_list_sessions. Do not navigate anywhere.
```

Codex should discover seven `rel_*` tools. `rel_status` should report the app,
local agent, Browser Proxy, and embedded Chromium bridge.

## Update

Refresh the marketplace snapshot and reinstall the current plugin version:

```sh
codex plugin marketplace upgrade rel
codex plugin add rel@rel
```

Start another new task after updating so it uses the refreshed plugin cache.
