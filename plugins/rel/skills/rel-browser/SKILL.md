---
name: rel-browser
description: Use REL's local MCP server to read web content, inspect service health, reuse persistent embedded Chromium sessions, capture rendered HTML or screenshots, attach to pages, perform browser actions, and select configured proxy aliases. Use when a request explicitly mentions REL or asks the agent to browse through an existing REL session, keep browser state on the local Mac, or automate a page with REL rather than another browser backend.
---

# Use REL Browser

Use the MCP server bundled with `/Applications/REL.app`. REL.app owns Chromium;
the standalone `rel-mcp` adapter only forwards supported calls through the
local versioned API.

## Workflow

1. Call `rel_status` only when the user asks for diagnostics or a browser tool
   reports a readiness failure. Operational tools already start REL lazily and
   surface supported-path errors, so a routine status call is redundant.
2. When the user names a session, preserve its canonical `Session<number>` ID.
   Otherwise call `rel_list_sessions` before reusing browser state. Do not omit
   `session_id` merely to inspect existing state because omission can create a
   persistent session. When intentionally creating several related sessions,
   give each the same `group` rather than overloading its unique display name.
   When creating a session with requested browser defaults, pass its unique
   `profile` name; profile and session ID are mutually exclusive.
3. Use `rel_read` for reading or research when bounded semantic Markdown and
   links are sufficient. Supply `query` to rank relevant sections. Use
   `rel_observe` when action refs are needed, and request hybrid or visual mode
   only for canvas-heavy pages, missing semantics, visual ambiguity, or explicit
   visual verification.
4. Use `rel_capture` for one-shot navigation, actions, and rendered HTML. Use
   `rel_page_attach` followed by `rel_page_action` for a multi-step workflow on
   one attached page. Each `rel_page_action` call accepts exactly one action.
5. Put `wait-for` immediately before `click` when a target may render
   asynchronously. A click checks the current DOM snapshot once and does not
   poll for a missing target.
6. Use `rel_take_screenshot` to inspect or verify the visible result. Omit
   `output_uri` when the agent should receive inline image content; provide an
   absolute `file:///` URI when the user needs a saved image resource.
7. Call `rel_list_proxies` when a proxy alias is requested or needs selection.
   Pass only the alias; do not seek or expose stored credentials.
8. Summarize the outcome and surface returned `file:///` resource links. Preserve
   structured REL errors instead of reducing them to a generic failure.
9. Use `rel_close_session_group` only when the user asks to close every session
   in that group. Report the returned canonical `deleted_ids`.

## Actions

Pass an ordered `actions` array to `rel_capture`. For an attached page, pass one
of these objects as the `action` field of `rel_page_action`:

```json
{"action":"click","selector":"button.more"}
{"action":"wait-for","selector":"#loaded-content"}
{"action":"type","selector":"#search","text":"Magickraft"}
{"action":"fill","selector":"#email","text":"listener@example.com"}
{"action":"clear","selector":"#query"}
{"action":"press","selector":"#search","key":"Enter"}
{"action":"select","selector":"#genre","value":"disco"}
{"action":"wait","seconds":0.5}
{"action":"click-link","link":"https://example.com/more","match":{"type":"fuzzy-link","threshold":0.9}}
```

- `click` targets the first match for the supported selector. `click` and
  `click-link` accept optional `mouse_move` and `scroll` booleans, both defaulting
  to `true`. These use Chromium-local input and never move the macOS cursor.
- `wait-for` waits for selector presence. Use it before an action whose target is
  rendered asynchronously.
- `type` appends nonempty text. `fill` replaces the current value and may use an
  empty string. `clear` explicitly empties the selected editable control.
- `press` accepts `Enter`, `Tab`, `Escape`, `Backspace`, `Delete`, `ArrowUp`,
  `ArrowDown`, `ArrowLeft`, `ArrowRight`, `Home`, `End`, `PageUp`, `PageDown`, or
  `Space`.
- `select` chooses one enabled `<option>` by exact `value`.
- `wait` adds an explicit nonnegative delay between actions.
- `click-link` resolves anchors by URL with the required `fuzzy-link` match rule;
  `threshold` must be between 0 and 1.

Selector actions accept tag, universal, ID, class, presence or value attribute
selectors and descendant, child, adjacent-sibling, or general-sibling
combinators. Pseudo-classes, pseudo-elements, namespaces, and CSS escapes are
unsupported. REL does not accept caller-supplied JavaScript or fall back to a
different target when an action fails.

## Guardrails

- Prefer `rel_list_sessions` and `rel_list_proxies` before browser actions when
  they resolve ambiguity. Reserve `rel_status` for diagnostics.
- Treat navigation, clicks, and other page actions as effects on the selected
  website. State what changed, especially for submissions, purchases, deletes,
  or other consequential actions.
- Use absolute local `file:///` URIs for `output_uri`.
- Keep page IDs within the current MCP process; they expire when the REL agent
  restarts.
- Do not read REL's SQLite database, logs, Chromium storage, or proxy secrets.
- Do not launch a second Chrome or substitute another browser backend when REL
  fails. Surface the supported-path error clearly.

## Tools

- `rel_status`: inspect app, agent, Browser Proxy, and Chromium readiness.
- `rel_list_sessions`: list persistent sessions and canonical IDs.
- `rel_close_session_group`: close every persistent session in a named group.
- `rel_list_proxies`: list proxy aliases and non-secret configuration.
- `rel_capture`: load a URL, optionally act, and save rendered HTML.
- `rel_page_attach`: attach an automation page to a persistent session.
- `rel_navigate`: navigate and return the first semantic or visual observation.
- `rel_read`: return bounded, query-directed semantic Markdown and links without
  action refs or an image.
- `rel_page_action`: perform one action on an attached page.
- `rel_take_screenshot`: capture the current or attached page as PNG, JPEG, or
  WebP, inline or at an explicit file URI.
- `rel_observe`: return bounded rendered semantics and an optional synchronized
  viewport image for the current or attached page.
- `rel_find`: search a stored observation's public content and element fields.
- `rel_action`: perform ordered ref, hover, scroll, and wait actions through one
  observation and return a single resulting observation.
