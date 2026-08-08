---
name: rel-browser
description: Use Rel's local MCP server to inspect service health, reuse persistent embedded Chromium sessions, capture rendered HTML, attach to pages, perform browser actions, and select configured proxy aliases. Use when a request explicitly mentions Rel or asks Codex to browse through an existing Rel session, keep browser state on the local Mac, or automate a page with Rel rather than another browser backend.
---

# Use Rel Browser

Use the MCP server bundled with `/Applications/Rel.app`. Rel.app owns Chromium;
the MCP adapter only forwards supported calls through the local versioned API.

## Workflow

1. Call `rel_status` before the first browser operation. If a required service is
   unhealthy, report the returned error and stop the Rel workflow.
2. When the user names a session, preserve its canonical `Session<number>` ID.
   Otherwise call `rel_list_sessions` before reusing browser state. Do not omit
   `session_id` merely to inspect existing state because omission can create a
   persistent session.
3. Use `rel_capture` for one-shot navigation, actions, and rendered HTML. Use
   `rel_page_attach` followed by `rel_page_action` for a multi-step workflow on
   one attached page.
4. Call `rel_list_proxies` when a proxy alias is requested or needs selection.
   Pass only the alias; do not seek or expose stored credentials.
5. Summarize the outcome and surface returned `file:///` resource links. Preserve
   structured Rel errors instead of reducing them to a generic failure.

## Guardrails

- Prefer read-only `rel_status`, `rel_list_sessions`, and `rel_list_proxies`
  calls before browser actions when they can resolve ambiguity.
- Treat navigation, clicks, and other page actions as effects on the selected
  website. State what changed, especially for submissions, purchases, deletes,
  or other consequential actions.
- Use absolute local `file:///` URIs for `output_uri`.
- Keep page IDs within the current MCP process; they expire when the Rel agent
  restarts.
- Do not read Rel's SQLite database, logs, Chromium storage, or proxy secrets.
- Do not launch a second Chrome or substitute another browser backend when Rel
  fails. Surface the supported-path error clearly.

## Tools

- `rel_status`: inspect app, agent, Browser Proxy, and Chromium readiness.
- `rel_list_sessions`: list persistent sessions and canonical IDs.
- `rel_list_proxies`: list proxy aliases and non-secret configuration.
- `rel_capture`: load a URL, optionally act, and save rendered HTML.
- `rel_page_attach`: attach an automation page to a persistent session.
- `rel_page_action`: perform one action on an attached page.
