# REL RPC v1

## Profiles, groups, and sessions

See [Projects, Profiles and Sessions](SESSIONS.md) for explicit Project scope,
independent Session state, deliberate sharing and configuration reapply. Profile
names do not imply shared state. Public management uses Session IDs; group
resource and reset APIs are not supported.

## Transport

- Base URL: `http://127.0.0.1:17319/v1`
- `REL_AGENT_PORT` overrides port `17319`.
- HTTP/1.1, one request per connection, `Connection: close`.
- RPC JSON request limit: 16 MiB; request line and headers together: 64 KiB.
- Request headers and body must arrive within two seconds of connection acceptance.
  Sending bytes gradually does not extend this deadline. This read deadline is
  separate from the browser operation's `timeout`.
- The agent parses up to 64 incoming connections concurrently. A stalled request
  does not block acceptance of other clients, including health/status checks.
  When all connection readers are occupied, new connections receive a retryable
  `RATE_LIMITED` error when writable, or close without a response. Retry only when
  the operation is safe to repeat.
- Ordinary responses use `application/json`.
- Capture streams use `application/x-ndjson` and terminate at connection close.
- The agent is loopback-only but currently has no client authentication.

## Native local inference

Fritz owns local model installation, inference, and its loopback service.
The service address and model controls are shown in the shared **Models** editor.
REL's browser agent no longer serves `/api/tags`, `/api/chat`, or `/api/generate`.
Browser and app operations continue to use the versioned `/v1` API below.

Every parsed `/v1` request receives an opaque ID. Ordinary RPC responses include it in the
`X-Request-Id` header and body. Every capture-stream line includes the same ID.

Closing a browser operation's HTTP connection before its response finishes
cancels that operation. The agent also sends cancellation through its private
Chromium bridge, so navigation, waits, and actions stop instead of continuing
in the background. Cancellation is request-scoped: the persistent browser
session, the REL app, and the resident agent remain running for other clients.

By default, a browser operation selects its target session when REL is inactive, so
the affected page is visible the next time the app is viewed. REL is not
activated or brought forward. Turn off **REL → Settings… → General → Follow
browser commands** to preserve the current selection. This presentation setting
does not change RPC results or session behavior.

## Browser concurrency

REL runs up to eight browser operations concurrently across sessions by default.
Additional operations wait in FIFO order for capacity; each session still executes
its own requests in order. Open or idle sessions do not consume execution slots.
Session lifecycle operations and health/status requests remain independently
available while browser work is queued. The health worker’s `active_count` includes
requests waiting for this shared capacity, so it can exceed the concurrency limit.

Set `REL_BROWSER_CONCURRENCY` to an integer from `1` through `32` in the REL app's
launch environment to change the limit. The app-owned agent reads it at startup;
setting it only on a CLI or SDK client does not change a running agent. An invalid
value prevents the agent from starting and reports a configuration error. For
worktree development, for example, use `REL_BROWSER_CONCURRENCY=4 make dev-open`.

Queued work observes its queue deadline, client disconnect, and session closure.
This limit does not change the maximum number of persistent sessions or bypass
per-session ordering. Higher concurrency may increase latency and memory without
increasing throughput; measure against the intended workload.

For profiling, `REL_BROWSER_PERFORMANCE_TRACE=1` in the app launch environment
records `browser_timing` agent-log events with queue and execution milliseconds.
It is off by default. Events contain operation metadata, not page contents.

## Response envelope

Every successful ordinary response is:

```json
{
  "status": "ok",
  "request_id": "req_01J...",
  "data": {}
}
```

Every failure is:

```json
{
  "status": "error",
  "request_id": "req_01J...",
  "error": {
    "id": "SESSION_NOT_FOUND",
    "code": 10100,
    "message": "Browser session Session42 was not found.",
    "retryable": false,
    "details": {
      "id": "Session42"
    }
  }
}
```

`id`, `code`, `message`, and `retryable` are required. `details` is an optional
JSON object. Numeric RPC codes begin at 10,000 and are independent of HTTP
transport statuses. Clients can branch on `code` or `id`, but must never parse
`message` or infer application meaning from the HTTP status. The same error
object is used in ordinary responses and NDJSON streams.

`retryable:true` means retrying the same idempotent operation may succeed without
user correction. It does not mean every mutation is automatically safe to
repeat.

### Standard error codes

| Code | ID | Retryable | Meaning |
| ---: | --- | --- | --- |
| `10000` | `INVALID_REQUEST` | no | Malformed HTTP or JSON |
| `10001` | `ROUTE_NOT_FOUND` | no | No v1 route matches |
| `10002` | `METHOD_NOT_ALLOWED` | no | Resource exists but method is unsupported |
| `10003` | `PAYLOAD_TOO_LARGE` | no | Request body exceeds 16 MiB |
| `10004` | `UNSUPPORTED_MEDIA_TYPE` | no | JSON endpoint received unsupported content |
| `10005` | `VALIDATION_FAILED` | no | Parsed request violates field constraints |
| `10006` | `UNSUPPORTED_MODALITY` | no | The selected adapter cannot carry the requested observation modality |
| `10007` | `OBSERVATION_TOO_LARGE` | no | A semantic snapshot or image exceeds its independent bound |
| `10100` | `SESSION_NOT_FOUND` | no | Session ID does not exist |
| `10101` | `PAGE_NOT_FOUND` | no | Ephemeral attached page does not exist |
| `10102` | `PAGE_MISMATCH` | yes | Attached page state no longer matches the request; refresh the page binding before retrying |
| `10103` | `PROXY_NOT_FOUND` | no | Proxy does not exist |
| `10104` | `ACTIVE_PAGE_NOT_FOUND` | no | The shorthand workflow has no current page |
| `10200` | `CONFLICT` | no | Name/state/last-session conflict |
| `10201` | `BROWSER_BUSY` | yes | Chromium is servicing incompatible work |
| `10202` | `NETWORK_PAUSED` | no | Session networking is paused |
| `10203` | `ACTION_TARGET_NOT_FOUND` | no | Click target could not be found |
| `10204` | `REQUEST_CANCELLED` | yes | Browser work was cancelled |
| `10205` | `RATE_LIMITED` | yes | REL itself is rate limiting the caller |
| `10206` | `ACTION_TIMEOUT` | yes | A browser action's local timeout expired |
| `10207` | `OBSERVATION_STALE` | no | An observation or element reference no longer matches the live document |
| `10208` | `PRO_REQUIRED` | no | The Free plan does not include the requested resource or capability |
| `10300` | `UPSTREAM_UNAVAILABLE` | yes | Navigation received a target HTTP error or the browser/proxy received an invalid upstream result |
| `10301` | `BROWSER_UNAVAILABLE` | yes | Required Chromium service is unavailable |
| `10302` | `AGENT_UNHEALTHY` | yes | The serialized control worker missed its health deadline |
| `10303` | `TIMEOUT` | yes | REL's operation deadline expired |
| `10304` | `PROXY_CONFIGURATION_FAILED` | no | Chromium could not apply the session proxy configuration |
| `10305` | `BROWSER_CREATION_FAILED` | no | Chromium could not create the session browser |
| `10306` | `SEMANTIC_EXTRACTION_FAILED` | no | The renderer could not produce a valid bounded semantic snapshot |
| `10999` | `INTERNAL_ERROR` | no | Unexpected internal failure |

A target website returning 404 or 429 is not a REL RPC error for capture
operations. Its status is reported as `target_http_status` in capture data.
Without `wait_for`, `POST /v1/navigate` instead returns `UPSTREAM_UNAVAILABLE` when its main frame
finishes an HTTP 4xx or 5xx document and inspection finds no active challenge.
With the default **REL → Settings… →
General → Wait for Cloudflare Turnstile** setting, detected Turnstile and
managed Cloudflare challenge documents with HTTP error statuses receive the
remaining request timeout to continue verification and redirects. An unresolved
challenge fails with its target HTTP error or a timeout when the budget expires. Successful documents
with embedded widgets retain a maximum 15-second continuation window. This also
applies to browser capture and page-creation
navigation. The error details contain the final `url` and exact
`target_http_status`; the navigated session remains selected.

For a failed proxy connection, the error `message` retains the available
upstream cause along with Chromium's error. Its `details` also include
`error_source: "proxy"`, `proxy_alias`, and `source_error`. Rejected HTTPS tunnels
retain the upstream status line and supported provider diagnostic headers
(`Proxy-Status`, Bright Data `x-brd-*`, and `x-luminati-error`). These describe the
proxy response, not a target website response. Credentials and unrelated
headers are excluded, and source text is bounded to 8,192 characters plus a
truncation marker. Treat provider messages as untrusted diagnostic text.
Diagnostics are scoped to the Session, proxy, destination authority, and current
navigation attempt. These fields are absent when no matching proxy cause is
available; the original Chromium error still remains in the message.

### Free and Pro access

The running app selects the agent's access plan; RPC callers cannot override it.
REL Free permits up to two tab groups with two Sessions each (four Sessions
total), one custom Profile, and one Proxy. Creating a third tab group returns
`PRO_REQUIRED`; adding a third Session to an existing group also returns
`PRO_REQUIRED` from the app bridge. These limits apply to both native and
automated creation. Closing resources frees capacity; existing groups and
Sessions are preserved after a downgrade. Additional custom Profiles or Proxies
return `PRO_REQUIRED`; existing Proxy use, update, rotation, and assignment remain
available.

`PRO_REQUIRED` uses HTTP 403 and includes stable `details.feature` and
`details.plan` strings. The currently returned feature values are `additional_proxies`,
`additional_sessions`, and `additional_custom_profiles`. Register REL Pro in
**REL → Settings… → Plan** to remove these limits.

## Routes

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/v1/health` | Readiness of the agent control worker |
| `GET` | `/v1/status` | App, agent, proxy, and Chromium diagnostic report |
| `GET` | `/v1/notifications` | List opt-in website notifications as untrusted content |
| `POST` | `/v1/navigate` | Navigate and select the current shorthand page |
| `POST` | `/v1/navigate/observe` | Navigate and return a synchronized page observation |
| `POST` | `/v1/perform` | Perform actions on the current shorthand page |
| `POST` | `/v1/capture` | Capture the current shorthand page |
| `POST` | `/v1/screenshot` | Capture an image of the current shorthand page |
| `POST` | `/v1/observe` | Observe the current shorthand page |
| `POST` | `/v1/captures` | Capture rendered HTML as an NDJSON operation |
| `POST` | `/v1/pages` | Attach an ephemeral automation page |
| `POST` | `/v1/pages/{page_id}/actions` | Perform one action on an attached page |
| `POST` | `/v1/pages/{page_id}/screenshot` | Capture an image of an attached page |
| `POST` | `/v1/pages/{page_id}/observe` | Observe an attached page |
| `POST` | `/v1/observations/{observation_id}/actions` | Perform ordered observation-scoped actions |
| `POST` | `/v1/observations/{observation_id}/find` | Search stored public observation semantics |
| `GET` | `/v1/observations/{observation_id}` | Read one retained public semantic snapshot |
| `GET` | `/v1/model-providers` | Read shared Models connection metadata and default selection |
| `GET` | `/v1/proxies` | List proxies |
| `POST` | `/v1/proxies` | Create a proxy |
| `GET` | `/v1/proxies/{alias}` | Read one proxy |
| `PATCH` | `/v1/proxies/{alias}` | Partially update a proxy |
| `DELETE` | `/v1/proxies/{alias}` | Delete and detach a proxy |
| `POST` | `/v1/proxy-transfers/export` | Export a versioned proxy transfer |
| `POST` | `/v1/proxy-transfers/import` | Import a versioned proxy transfer |
| `GET` | `/v1/sessions` | List persistent browser sessions |
| `POST` | `/v1/sessions` | Create a browser session |
| `GET` | `/v1/profiles` | List saved session configurations |
| `POST` | `/v1/profiles` | Create a custom session profile |
| `PATCH` | `/v1/profiles/{id}` | Update custom-profile browser-data availability |
| `DELETE` | `/v1/profiles/{id}` | Delete a custom session profile |
| `POST` | `/v1/profile-transfers/export` | Export a versioned profile transfer |
| `POST` | `/v1/profile-transfers/import` | Import a versioned profile transfer |
| `GET` | `/v1/sessions/{id}` | Read one browser session |
| `POST` | `/v1/sessions/{id}/ping` | Refresh session inactivity without browser work |
| `POST` | `/v1/sessions/{id}/pause` | Pause session network activity |
| `POST` | `/v1/sessions/{id}/play` | Resume session network activity |
| `DELETE` | `/v1/sessions/{id}` | Delete a browser session |
| `POST` | `/v1/sessions/{id}/reapply` | Reapply configuration while preserving identity and data |
| `GET` | `/v1/sessions/{id}/proxy-status` | Read session proxy status |
| `POST` | `/v1/sessions/{id}/reset-proxy-session` | Rotate the selected Session’s proxy binding |
| `GET` | `/v1/sessions/{id}/debug-state` | Read non-blocking cached diagnostics |
| `GET` | `/v1/sessions/{id}/trace` | Read bounded cursor-paginated events |
| `POST` | `/v1/sessions/{id}/debug-bundle` | Export retained diagnostics and opt-in artifacts |
| `GET` | `/v1/projects` | List Projects |
| `POST` | `/v1/projects` | Create a Project |

There are deliberately no log read, clear, or ingestion routes.

The [`rel-client`](SDK.md) Rust crate exposes typed methods for supported
operations. Check its installed version and schema for newer runtime routes.
The bundled CLI is built on that crate and uses resource commands
such as `rel capture`, `rel page`, `rel proxy`, and `rel session`; it has no
direct database or log-file command path.

The bundled `rel-mcp` adapter also calls this API only through `rel-client`. It
maps its discovered MCP tools to status, opt-in website notifications, bounded
semantic reading, HTML and image
capture, page attachment and actions, observations, session-group closing, and
session and proxy listing.
MCP does not add an HTTP `/mcp` route or another response shape to RPC v1. See
[MCP](MCP.md) for its stdio lifecycle and result wrapping.
The [`rel-client` Ruby gem](RUBY.md) exposes the same route table with Ruby hash
payloads, structured response and error objects, and incremental capture
streaming.
`rel_read` is a `rel-client` composition over `POST /v1/navigate/observe` and
`POST /v1/observe`. The SDK's `read_observation` helper applies the same bounded
selection to `GET /v1/observations/{observation_id}`; neither helper adds an
alternate browser transport.

## Health

### `GET /v1/health`

HTTP 200 while the worker is ready or operating within its deadline:

```json
{
  "status": "ok",
  "request_id": "req_...",
  "data": {
    "version": "0.1.8",
    "pid": 123,
    "browser_proxy_port": 17400,
    "build": {
      "id": "ba49-deadbeef-a1b2c3d4",
      "configuration": "Debug",
      "worktree": "ba49",
      "branch": "codex/example",
      "commit": "deadbeef",
      "dirty": true
    },
    "worker": { "state": "idle" },
    "database_recovery": null
  }
}
```

`build` identifies the installed worktree build and is `null` for agents that
were not launched from a metadata-bearing app bundle. Worker state is
`starting`, `idle`, or `busy`. A startup/operation deadline
violation or failed worker returns `AGENT_UNHEALTHY`, with the worker
snapshot in `error.details.worker`. Health deadlines diagnose stalls; they do not
cancel the active request.

`database_recovery` is `null` when no committed database upgrade/recovery report
exists. Otherwise it contains `schema_version` (integer), `backup_path` and
`report_path` (local absolute paths), `issue_count` (number of reported repair or
quarantine items, not necessarily distinct records), and `retained_sessions`
(number of sessions retained at recovery time). The most recent report with
issues remains visible across restarts and later successful upgrades; when
there are no such reports, the latest upgrade report is returned. Paths point
to the agent host, not to a remote client. See [database recovery](APP.md#database-migration-and-recovery)
for backup, quarantine, and failure behavior.

The health endpoint is not ready during startup migration. Successful health
means schema and data validation completed; it does not mean every original
record could be recovered.

### `GET /v1/status`

The diagnostic call succeeds with HTTP 200 even when a component is down:

```json
{
  "status": "ok",
  "request_id": "req_...",
  "data": {
    "overall_status": "ok",
    "running_count": 4,
    "total_count": 4,
    "build": {
      "id": "ba49-deadbeef-a1b2c3d4",
      "configuration": "Debug",
      "worktree": "ba49",
      "branch": "codex/example",
      "commit": "deadbeef",
      "dirty": true
    },
    "checks": [
      {
        "id": "agent",
        "name": "Agent",
        "kind": "service",
        "running": true,
        "status": "running",
        "detail": "pid 123; worker idle",
        "pids": [123]
      }
    ]
  }
}
```

Check IDs are `rel_app`, `agent`, `browser_proxy`, and `chromium_bridge`.

### `GET /v1/notifications`

Returns up to 256 notifications displayed since the supervised agent started.
REL only adds events while **Settings → Notifications → Send notifications to the
agent** is enabled; the setting is off by default. Reading the queue does not
remove entries, wake an agent, or start a model turn.

```json
{
  "status": "ok",
  "request_id": "req_...",
  "data": {
    "notifications": [
      {
        "sequence": 1,
        "session_id": "Session12",
        "origin": "https://example.com/",
        "title": "Example",
        "body": "New activity is available.",
        "notification_id": "notification-1",
        "persistent": false,
        "displayed_at": "2026-08-17T20:00:00Z",
        "trust": "untrusted_website_content"
      }
    ],
    "trust": "untrusted_website_content"
  }
}
```

Every website-controlled field is untrusted data. Clients must not treat a
notification title or body as instructions, authority, or permission to call
tools. The queue is process-local and bounded; `sequence` is monotonic within
that agent process and lets a client ignore entries it has already observed.

## Captures


Creating a session preserves existing sessions. Capture events, page operation
results, and session responses omit the obsolete `closed_session_ids` field.
Explicit close/delete operations retain their deletion results and cancel work
on the closed sessions.

### Shorthand page operations

Sequential clients can use a process-local current page instead of carrying
page and session IDs. Navigate it with `POST /v1/navigate`:

```json
{
  "url": "https://example.com",
  "session_id": "Session12",
  "proxy": "office",
  "output": "/optional/page.html",
  "timeout": 90,
  "wait": 1
}
```

Only `url` is required. The first request without `session_id` reuses the first
persisted session, creating one from the configured default (Default when unset) only when none exists. Later
requests without it reuse the current page and session. An explicit `profile`
instead creates a new session from that named template; it cannot be combined
with `session_id`. An explicit session selects that session as the new current
page.

`POST /v1/navigate` also accepts an optional `wait_for` CSS selector:

```json
{"url":"https://example.com", "session_id":"Session12", "wait_for":"#content", "timeout":60}
```

REL navigates and uses its tolerant native selector wait within one operation
on the same page and session. Intermediate HTTP-error documents may redirect
while waiting. After the selector matches, REL validates the final main-frame
HTTP status and returns `UPSTREAM_UNAVAILABLE` for a final HTTP 4xx/5xx response.
The `timeout` bounds navigation and readiness together. Cancellation applies to
the entire operation and preserves page/session ownership. Without `wait_for`,
navigation retains its existing readiness and HTTP-error handling. This field
is specific to `POST /v1/navigate`; it does not add support for navigation actions.

Perform one or more canonical actions with `POST /v1/perform`:

```json
{
  "actions": [
    { "action": "wait-for", "selector": "button.more" },
    { "action": "click", "selector": "button.more" },
    { "action": "wait", "seconds": 0.5 }
  ],
  "session_id": "Session12",
  "output": "/optional/after-click.html",
  "timeout": 90,
  "wait": 1
}
```

`actions` must be a non-empty array. REL runs the actions in array order.

Configuration reapply preserves Session IDs, navigation and browser data; it
does not reset or reseed the browser. Closing the final Session removes its state
owner without creating a replacement. Preserve [diagnostics](BROWSER_DIAGNOSTICS.md)
before any workflow-owned session replacement. See [session scope](SESSIONS.md).

Capture HTML without another action with `POST /v1/capture`:

```json
{
  "session_id": "Session12",
  "output": "/optional/current.html",
  "timeout": 90,
  "wait": 1
}
```

The singular capture reads the currently visible page and treats its returned
`page.url` as authoritative. This refreshes the shorthand page binding after a
same-document History API, query, or fragment change instead of failing because
the previously tracked URL is stale.

All three return the same page-operation envelope documented under attached
pages. When `session_id` is supplied, `navigate` selects and updates that
session's current shorthand page; `perform` and singular `capture` target it.
For multiple independent crawls, create a session for each crawl and pass its
returned `session.id` as `session_id` on every navigation, action, observation,
and capture. Creation may reuse a compatible group, but each returned tab ID is
distinct and remains bound to that tab when siblings are created or selected.
Keep staged operations within one tab sequential so another request to that same
tab cannot change its page between stages. Separate tabs may run independently.
`PAGE_MISMATCH` is retryable: refresh the page binding with `POST /v1/capture`
using that same `session_id`, or navigate to the intended URL, before retrying an
idempotent operation. Inspect the result before replaying actions with side effects.
Navigation becomes ready after the requested HTTP(S) main frame starts,
finishes, and has nonempty rendered source. Subframe and page-initiated
background loading does not delay completion. The `wait` delay begins after
main-frame readiness and restarts if another main-frame navigation begins. Use
a timed `wait` action when a workflow needs additional settling time.
Without `wait_for`, if navigation commits an HTTP 4xx or 5xx main-frame response, it returns
`UPSTREAM_UNAVAILABLE` instead of waiting for unrelated background loading to
become idle. A detected Cloudflare Turnstile or managed challenge receives the
default-on continuation window described above. The error includes
the exact `target_http_status`, and the page remains the session's current
shorthand page.
Without `session_id`, they use the most recently navigated shorthand page for
compatibility. `perform` and singular `capture` return `ACTIVE_PAGE_NOT_FOUND`
with `ACTIVE_PAGE_NOT_FOUND` until a matching page has been selected by
navigation. This registry is process-local and is cleared by an agent restart
or when its session closes. Concurrent work within one session should use
explicit page IDs.

### Screenshots

Capture the visible viewport of the current shorthand page with
`POST /v1/screenshot`, or use `POST /v1/pages/{page_id}/screenshot` for an
explicit attached page:

```json
{
  "session_id": "Session12",
  "output": "/optional/page.webp",
  "format": "webp",
  "quality": 80,
  "full_page": true,
  "timeout": 90,
  "wait": 0
}
```

`session_id` is accepted only by the current-page route. `format` is `png`
(default), `jpeg`, or `webp`. `quality` is an integer from 0 through 100 and is
ignored for PNG. `full_page` defaults to false; true captures content beyond
the visible viewport. `output` follows the same absolute-response-path contract
as HTML capture. When omitted, REL writes under its temporary `screenshots`
directory. Every encoded image is limited to 16,384 pixels on either axis and
16,000,000 pixels total. REL checks full-page document dimensions before asking
Chromium to render the image and returns `OBSERVATION_TOO_LARGE` immediately
when the scaled page exceeds either bound.

Success uses the ordinary RPC envelope:

```json
{
  "page": {
    "id": "page_...",
    "session_id": "Session12",
    "url": "https://example.com/"
  },
  "screenshot": {
    "output_path": "/private/tmp/rel/screenshots/example.webp",
    "bytesize": 48231,
    "format": "webp",
    "mime_type": "image/webp",
    "width": 1280,
    "height": 2400
  }
}
```

The image bytes remain in the file rather than the JSON response. The MCP
adapter reads that validated file and emits standard image content when its
caller did not request a specific output URI.

### Page observations, semantic find, and reference actions

`POST /v1/navigate/observe` combines navigation and the first observation:

```json
{"url":"https://example.com","session_id":"Session12","mode":"hybrid","timeout":90,"wait":0}
```

It accepts the navigation fields `url`, `session_id`, `profile`, and `proxy`
plus the observation fields `mode`, `timeout`, and `wait`. It reuses the same
active-page and persistent-session rules as `POST /v1/navigate`, but returns an
observation instead of creating an HTML capture artifact.

Set `navigation` to `back`, `forward`, or `reload` to operate on the active
page's history and omit `url`, `profile`, and `proxy`. `navigation` defaults to
`url`, where `url` is required. An optional `session_id` scopes history
navigation to that session's active page. REL resolves the session's owning
group internally; do not supply `group_id` for history navigation.

`POST /v1/observe` observes the current shorthand page. The attached-page form
is `POST /v1/pages/{page_id}/observe`:

```json
{"session_id":"Session12","mode":"hybrid","timeout":90,"wait":0}
```

`session_id` is accepted only by the current-page route. `mode` is `semantic`
(the default), `hybrid`, or `visual`; `auto` is not an RPC mode. Semantic mode
returns compact rendered text and typed interactive elements. Hybrid also
returns a synchronized current-viewport PNG. Visual returns minimal semantics
plus that PNG. Screenshot bytes are kept in a typed temporary file resource,
with its dimensions and exact CSS-to-image scales in the response.

Each observation contains an ID, document sequence, capture time, title,
truncation counts, viewport/document geometry, semantic `content`, and typed
`elements`. Content and elements may include a bounded `context` path such as
`main > form: Checkout > table: Items > tr: Product A`; this preserves useful
landmark, form, dialog, list, table, and row relationships without exposing a
selector or durable DOM identity. `omitted_node_count` reports entries dropped by traversal or output
bounds, while `clipped_text_count` reports individual text fields shortened to
their field limit; `truncated` is true when either occurred. Tables preserve DOM
order with `table`, `table_row`, `table_caption`, and `table_cell` content kinds,
including repeated cell values. Elements hidden by rendered CSS visibility are
excluded along with `hidden` and `aria-hidden` subtrees. Element refs such as
`e17` are valid only for that page, document sequence, and observation. Private
locators never cross RPC.

Observations also include `captcha`, REL's current debounced human-verification
state: `{"active":true,"kind":"reCAPTCHA"}` when a stable challenge is detected,
or `{"active":false}` otherwise. This is the same native detector used by the
menu bar and attention notifications. A false value is not proof that a site has
no CAPTCHA: detection is heuristic and may still be pending. No challenge
selector, response token, or solver capability is exposed. Retained observations
report the state at capture time; request a new observation for current state.

Semantic observations visit at most 50,000 DOM nodes, retain at most 5,000
candidates and returned entries, limit individual text fields to 2,048 bytes,
and limit total returned semantics to 512 KiB. REL reports rather than silently
hiding any truncation caused by these independent bounds.

Act through a ref with
`POST /v1/observations/{observation_id}/actions`:

```json
{
  "actions": [
    {"ref":"e17","action":"hover","scroll":true},
    {"ref":"e18","action":"click","mouse_move":true,"scroll":true},
    {"action":"wait","seconds":0.25},
    {"action":"scroll","delta_x":0,"delta_y":-600}
  ],
  "mode":"hybrid"
}
```

`actions` contains 1–32 ordered items. Element actions are `click`, `type`
(requires `text`), `clear`, `press` (requires `key`), `select` (requires
`value`), and `hover`; each requires a ref. Page actions are `scroll`, with
integer `delta_x`/`delta_y` from -10000 through 10000 and at least one non-zero
delta. These are native wheel deltas: negative `delta_y` scrolls toward the
page bottom, positive `delta_y` scrolls toward the top, negative `delta_x`
scrolls right, and positive `delta_x` scrolls left. `wait` takes `seconds` from
0 through 60. REL stops at the first
failure and returns only one new post-action observation after the whole batch.
It revalidates the document sequence and every target signature before input. A
mismatch returns `OBSERVATION_STALE`; no selector or nearby-target fallback is
attempted.

Search the stored public snapshot without another browser read using
`POST /v1/observations/{observation_id}/find`:

```json
{"query":"continue","role":"button","limit":20}
```

At least `query` or `role` is required. Query matching is case-insensitive over
content text and public element role, name, value, and destination. Role is an
exact case-insensitive element filter. `limit` defaults to 20 and may be 1–100.
Results distinguish `content` and `element` matches, preserve actionable refs,
and report `total_matches` plus `truncated`. Private locators are never stored in
or returned from the searchable public snapshot.

Read the complete retained public snapshot using
`GET /v1/observations/{observation_id}`. It returns the ordinary page and
observation envelope. After the page navigates, REL erases the observation's
private locators and rejects actions with `OBSERVATION_STALE`, but its public
semantic content remains readable. The process-local registry retains at most
32 observations and removes them when their session closes or the agent exits.

### `POST /v1/captures`

```json
{
  "url": "https://example.com",
  "output": "/optional/page.html",
  "timeout": 90,
  "wait": 1,
  "actions": [],
  "session_id": "Session12",
  "proxy": "office",
  "retry": 1,
  "retry_delay": 3
}
```

| Field | Contract |
| --- | --- |
| `url` | Required HTTP(S) URL; scheme-less input is normalized by the agent. |
| `output` | Optional nonempty filesystem path or null; generated when absent. Relative input is resolved against the agent process directory. Responses always contain an absolute `output_path`. |
| `timeout` | Finite seconds greater than zero; default 90. |
| `wait` | Finite settling seconds after final main-frame readiness; default 1. Background loading does not restart it. |
| `actions` | Optional array of canonical [action objects](ACTIONS.md). |
| `session_id` | Optional existing canonical `Session<number>` ID. Omission creates a persistent session and returns its ID in capture events. |
| `profile` | Optional saved profile name for the newly created session. It cannot be combined with `session_id`; omission uses the configured default or Default. |
| `group` | Optional 1–128 character group for the newly created session. It cannot be combined with `session_id`; matching and bulk close are case-insensitive. |
| `proxy` | Optional unique proxy alias string, assigned to the created session or applied to the existing session. |
| `retry` | Integer 0 through 100; default 1. |
| `retry_delay` | Finite seconds 0 through 86400; default 3. |

The RPC accepts the same closed JSON objects as the CLI and MCP server. The
[Actions reference](ACTIONS.md) defines every action, selector constraint,
default, and failure behavior. Browser sessions controlled while not visible
use the global **Background Browser Size** preset; RPC has no per-request
viewport override.

Preflight failures use the ordinary error response. Once accepted, REL returns
HTTP 200 `application/x-ndjson`. Each physical line is one complete object; there
is no encoded stdout/stderr layer:

```json
{
  "status": "ok",
  "request_id": "req_...",
  "event": "capture.started",
  "data": {
    "url": "https://example.com/",
    "session_id": "Session12"
  }
}
```

Events, in normal order:

1. `capture.started`
2. `capture.browser_requested`
3. `capture.page_ready`
4. `capture.rendered`
5. `capture.writing`
6. `capture.retrying` when applicable
7. `capture.traffic`
8. `capture.completed` or `capture.failed`
9. `capture.finished`, containing `exit_code`

`capture.failed` uses the standard nested error object. `capture.completed`
contains an absolute output path, bytes, final URL, optional
`target_http_status`, session ID, capture ID, and proxy traffic. A target status
at least 400 is a completed capture with `outcome:"target_error"` and CLI exit
code 1; it is not an API error.

## Attached pages

### `POST /v1/pages`

```json
{
  "url": "https://example.com",
  "session_id": "Session12",
  "proxy": "office",
  "output": "/optional/page.html",
  "timeout": 90,
  "wait": 1
}
```

Omitting `session_id` creates a session from the named `profile`, or from
the configured default (Default when unset) when it is absent, and navigates it to `url`. `profile` and `group`
cannot be combined with `session_id`. Providing an
existing session attaches its current page without navigating; its final
normalized browser URL must equal the requested URL. Success data:

```json
{
  "page": {
    "id": "page_...",
    "session_id": "Session12",
    "url": "https://example.com/"
  },
  "capture": {
    "output_path": "/private/tmp/rel/captures/...html",
    "bytesize": 1234,
    "target_http_status": 200
  }
}
```

Page IDs are process-local and disappear when the agent restarts.

### `POST /v1/pages/{page_id}/actions`

```json
{
  "action": { "action": "click", "selector": "button.more" },
  "output": "/optional/page.html",
  "timeout": 90,
  "wait": 1
}
```

The response uses the same page/capture data. URL, proxy, and session come from
the attached page and cannot be overridden.

## Proxies

A proxy resource is:

```json
{
  "alias": "office",
  "upstream_host": "proxy.example.com",
  "upstream_port": 8000,
  "username": "optional",
  "password_set": true,
  "oxylabs": {
    "enabled": false,
    "location_parameter": null,
    "location_value": null
  }
}
```
If no Oxylabs configuration exists for a proxy, `oxylabs` is omitted.

Passwords are accepted on writes but never returned.

`oxylabs_masque_enabled` defaults to `true` for a new Oxylabs configuration when
omitted. An explicit `false` is honored for residential proxies too. Updates
that omit the field retain the saved value; startup and transfer imports preserve
it. MASQUE enables the trusted Rust session QUIC relay and uses the provider's
HTTP/3 CONNECT-UDP gateway for UDP; TCP continues through the configured HTTP
upstream. Changing the setting closes existing QUIC tunnels and publishes updated
session configuration. Open pages apply it when the user chooses Reload.

- `GET /v1/proxies` returns `data.proxies`, ordered by creation order.
- `GET /v1/proxies/{alias}` returns `data.proxy`.
- `POST /v1/proxies` requires `alias`, `upstream_host`, and `upstream_port`. Optional
  write fields are `username`, `password`, `oxylabs_enabled`, `oxylabs_masque_enabled`,
  `oxylabs_location_parameter`, `oxylabs_location_value`, `oxylabs_isp_ip_count`,
  `oxylabs_isp_page_limit`,
  `bright_data`, `webshare`, `locale`, and `detect_exit_locale`.
- `PATCH /v1/proxies/{alias}` is a true partial update. Missing fields are retained.
  `username:null`, `password:null`, or `locale:null` clears that value.
- `DELETE /v1/proxies/{alias}` detaches it from all sessions, then returns
  `data.deleted_alias`.


`POST /v1/proxies/{alias}/test` takes no body and runs connection diagnostics
against the saved proxy with a fresh provider session ID. It returns
`data.checks`, an array of `{id, title, status, detail, duration_ms}` records.
`status` is `passed`, `failed`, `warning`, or `skipped`. Connection failures are
check results; an unknown alias or invalid local configuration returns an API
error. Allow a 90-second client timeout. Early DNS/TCP failures stop dependent
network checks. HTTPS requests honor system and proxy-specific CA roots and
never retry directly. Credentials are never included in results. HTTPS checks target
`https://rel.me/proxy-test`. HTTP forwarding checks use its HTTP counterpart and
accept success or a redirect to that exact HTTPS URL. Exit metadata still uses
IPWHOIS.io.

The fixed test destinations are rel.me/proxy-test (HTTP and HTTPS) and IPWHOIS.io
(exit IP, country, timezone). Country targeting and exit-locale detection are
reported; browser overrides, leak behavior and MASQUE/UDP are not exercised.
See [proxy testing](PROXIES.md#test-a-saved-proxy).

`detect_exit_locale` is a boolean, on by default for new proxies and preserved
when omitted on update. Existing saved values and imported settings are unchanged. Automatic language controls use the active provider's configured country
(Bright Data country, Oxylabs country, or US state). When detection is enabled,
they instead resolve the exit country through the session's agent-owned proxy
using `https://ipwho.is/`. Country-to-language selection uses macOS locale data.
No configured country means the user's preferred language when detection is off.
Custom fingerprint locales take precedence and disabled language controls stay native.
Detection also applies the exit timezone independently of the identity's timezone
and language privacy controls, including Chrome and Native identities. It enables
only the effective timezone control needed for detection; the saved fingerprint
and other privacy controls are unchanged. With detection off, disabled timezone
controls stay native.

Proxy responses include `detect_exit_locale`; session responses include
`proxy_country` (configured ISO country or null) and `proxy_detect_exit_locale`.
`GET /v1/sessions/{id}/proxy-location` returns `data.country` (for example `DE`)
and `data.timezone` (for example `Europe/Berlin`, an IANA timezone identifier)
when detection is enabled or the proxy uses a fixed-IP ISP pool. It errors for a
missing proxy, disabled detection on other proxy types,
failed connection, or invalid lookup response. Successful results are cached for
30 minutes per session and upstream route; a reset changes the
route. Lookups have a 10-second timeout and never retry through a direct connection.

The response also includes `data.ip`, the validated IPv4 or IPv6 exit address when
provided by the detection service. Fixed-IP ISP pools permit this explicit lookup
even when automatic exit-locale detection is disabled, allowing group info to show
the assigned exit address without changing fingerprint locale settings. The lookup
uses the group's own agent-owned proxy route and rejects results if that route
rotates during detection. Cached results are scoped to the group and route.

The legacy `locale` field remains validated and preserved in storage and transfers,
but Automatic language selection now uses country targeting or exit detection.
Proxy responses retain `locale`, and session responses retain `proxy_locale`.
Version 6 proxy/profile transfers preserve detection; older transfers import with
it disabled.

Aliases are case-insensitively unique, immutable, and must start with a letter;
they may contain only letters, numbers, hyphens, and underscores (maximum 64
characters), and cannot be a UUID. An alias is the sole public proxy identifier: numeric database IDs
and UUIDs are neither accepted nor returned by proxy APIs.
Oxylabs location requires both parameter and value; parameter is `cc`, `country`,
or `st`. REL generates a distinct persistent sticky ID for each browser session.


For fixed-port Oxylabs ISP proxies, set `oxylabs_enabled:true`,
`oxylabs_masque_enabled:false`, and `oxylabs_isp_ip_count` to the number of
available IPs. The preset uses `disp.oxylabs.io`; existing `isp.oxylabs.io` gateways and
explicitly configured upstream endpoints are supported. Set `upstream_port` to the first assigned port, usually 8001. A count of
5 covers ports 8001 through 8005. The range must fit within 1 through 65535.
Location targeting and MASQUE cannot be combined with an ISP pool. Credentials
use `user-USERNAME` without generated session or location suffixes.

New browser sessions receive the least-used port, with lower ports breaking
ties. Assignments persist across reloads and restarts; sessions share ports once
all IPs are in use. Reset advances one port and wraps at the end of
the pool; a one-IP pool keeps the same IP. Resetting a profile advances every
assigned session. Changing the IP count reassigns sessions within the new range.
Omitting the count on PATCH preserves it; setting it to 0 disables fixed-port
allocation. Responses expose the count as `proxy.oxylabs.isp_ip_count`.
Proxy and profile transfer version 12 preserves the IP count; version 13 also
preserves the page limit. Older transfers default missing fields to 0.
Saved-proxy diagnostics test the first port of an ISP pool.

`oxylabs_isp_page_limit` is an integer from 0 through 4294967295. It defaults
to 0 (automatic rotation disabled), is preserved when omitted on PATCH, and
requires at least two IPs when positive. REL counts main-document HTTP(S) request
attempts before network dispatch, including failed attempts and reloads.
Subresources, subframes, and cached history changes are excluded; a redirect
chain counts once. The limit is shared across sessions using each port. An
exhausted IP's next document request moves only that session to the next port
with allowance remaining. Once all IPs are exhausted, a new round starts.
Runtime counts reset on agent restart or pool endpoint/count/limit changes.
Manual rotation does not clear an IP's shared page allowance.

`POST /v1/sessions/{id}/prepare-proxy-page` accepts `{}` and returns `rotated`.
With automatic ISP rotation enabled it returns `assigned_port`,
`page_request_count`, and `page_request_limit` for an admitted page. When the
current allowance is exhausted, it returns `rotation_required:true` and
`expected_proxy_session_id` without changing the route or consuming a page.
This admission lane is separate from browser automation. Do not call it again
for a navigation already handled by REL, because doing so can consume another
allowance. Route preparation and errors use the supported runtime path; they do
not provide a public reset API or establish cookie/exit continuity. For
investigation, preserve [diagnostics](BROWSER_DIAGNOSTICS.md) before changing a
Session.

`POST /v1/sessions/{id}/reset-proxy-session` accepts `{}` and returns
`data.rotated`. It selects a new sticky-session ID, or advances a multi-IP ISP
pool to its next port. It returns `false` for direct connections, fixed custom
proxies, and single-IP ISP pools. Rotation applies to the selected Session's
explicit shared state owner, closes its old proxy transports, and resets its
usage counters. It preserves browser data, Session IDs, tab membership, and
shared IP page allowances. Unknown Session IDs fail; expired provider bindings
return `PROXY_SESSION_EXPIRED`. The route does not retry website requests or
reload pages. See [automatic HTTP 429 reset](PROXIES.md#automatic-reset-on-http-429)
for REL's enabled-by-default app setting and its 30-second coalescing window.

Profiles accept notification-only `http_rules`; see the Profile contract below.
These rules do not reset browser state or replace Sessions.

`GET /v1/sessions/{id}/proxy-status` returns these fields under `data`:

```json
{
  "proxy_alias": "residential",
  "proxy_session_id": "a7b92d41",
  "assigned_port": null,
  "upstream_host": "proxy.example.com",
  "upstream_port": 33335,
  "can_rotate": true,
  "request_count": 42,
  "navigation_request_count": 8,
  "uploaded_bytes": 125000,
  "downloaded_bytes": 4500000,
  "active_connections": 3,
  "active_quic_tunnels": 1,
  "scope": "current_proxy_session_since_agent_start"
}
```

For ISP pools, `assigned_port` is the session's fixed upstream port and
`proxy_session_id` is null. The status panel shows **Assigned Port**. Other
providers return `assigned_port:null`. With automatic ISP rotation enabled,
status additionally returns `page_request_count` and `page_request_limit` for
the assigned IP, shared across its sessions. These fields are absent when the
page limit is disabled.

`upstream_host` and `upstream_port` identify the effective upstream endpoint,
including the assigned ISP port rather than the pool's starting port. They are
absent for direct sessions and never include credentials. The app's Overview
shows this endpoint separately from the detected ISP exit IP, country, and
timezone returned by the exit location lookup. The exit IP can differ from the
proxy host. Exit detection uses the current route and can be unavailable.

`navigation_request_count` counts main-document HTTP(S) requests admitted by
the navigation preparation lane for this session, including redirects and
attempts that subsequently fail or are cancelled. Route rotation or agent restart clears it. It is separate from the shared per-IP
`page_request_count` budget, which resets each pool round or agent restart.
Overview displays both counts, connections, and proxy upload/download totals.

The app's **Proxy Session Status** panel refreshes every two seconds. Counters
cover the current proxy assignment and sticky ID since the agent started;
rotation, reassignment, or agent restart resets them. `request_count` counts
plaintext HTTP requests and CONNECT tunnels, including unsuccessful attempts.
Individual HTTPS requests within an encrypted tunnel are not visible to the
proxy. Bytes include proxy protocol traffic and tunneled payload, rather than
provider billing or page resource sizes. UDP counters count forwarded payload
bytes and exclude QUIC/MASQUE framing. HTTP body bytes are added when their
relay completes. `active_quic_tunnels` counts active tunnels carried over the
session’s loopback HTTP/3 relay, including TCP CONNECT and CONNECT-UDP.
`active_connections` includes these tunnels and accepted TCP browser proxy connections
still being handled. A custom proxy without sticky sessions has a null
`proxy_session_id` and `can_rotate: false`; an unproxied session also has a null
`proxy_alias` and zero usage.

The app's New Proxy form suggests the first available alias for the selected
provider, such as `bright-data-1` or `oxylabs-residential-1`. Custom proxies use
`proxy-1`. Existing aliases are checked without regard to case. Changing the
provider or pasting a curl command updates the suggestion unless you have edited
the alias yourself. Existing proxy aliases remain immutable.

### Paste proxy settings from curl

In the app's proxy editor, choose **Paste curl command** to fill the proxy fields
from the clipboard. The importer accepts `--proxy` / `-x` and `--proxy-user` /
`-U`, including quoted values, `--option=value`, attached short options, and
credentials embedded in an HTTP proxy URL. The endpoint must include a port.

REL recognizes provider presets and extracts Bright Data or Oxylabs location
suffixes into their controls. Pasted session suffixes are replaced by REL's
per-browser-session IDs. Bright Data's `[replace with password]` placeholder is
left blank; enter the real password before saving. When importing into an existing
proxy, enter the imported proxy's password rather than reusing its saved password.
The alias remains unchanged. Review the form and save to apply the settings.

The command is parsed as text and is never executed. The destination URL and
other curl options are ignored, including `-k`; REL's certificate validation
settings still apply.

### Bright Data location and sessions

Select Bright Data in the app's proxy editor to configure a country and optional
state, city, or ASN. REL shows the resulting masked connection string and gives
each browser session its own persistent `-session-<id>` suffix.

The proxy create and update routes accept an optional `webshare` object:

```json
{
  "upstream_host": "p.webshare.io",
  "upstream_port": 80,
  "webshare": {"product": "proxy_server", "country": "us"}
}
```

`product` is `proxy_server`, `static_residential`, or `rotating_residential`.
`country` is an optional two-letter code. Supply the base username/password via
the existing credential path; the runtime adds a numeric sticky Session binding.
Do not include an existing session or `rotate` suffix in the base username.
Only one provider may be active: Webshare conflicts with enabled Oxylabs or
Bright Data. Omission on update preserves Webshare; `"webshare": null` clears it.
Responses include `webshare` or null. The Backbone host is `p.webshare.io`, with
ports 80, 1080, 3128, or 9999–19999. TLS keeps normal system trust. A new binding
is not proof of a new IP; verify actual routing when uniqueness matters.
These fields are available through the HTTP API and native editor; use a custom
HTTP request if your typed client does not expose them yet.

The proxy create and update routes accept a `bright_data` object:

```json
{
  "alias": "bright",
  "upstream_host": "brd.superproxy.io",
  "upstream_port": 44445,
  "username": "brd-customer-CUSTOMER-zone-ZONE",
  "password": "ZONE_PASSWORD",
  "tls": {"mode": "bright_data"},
  "bright_data": {
    "enabled": true,
    "country": "us",
    "state": "ny",
    "city": "newyork",
    "asn": "56386"
  }
}
```

Use the base username without location or session suffixes. REL appends country,
state, city, ASN, then its session ID. Country uses a two-letter code. State and
city require a country; city names have no spaces. State and city accept only
ASCII letters and digits, and ASN accepts digits. Values are trimmed and
lowercased. Targeting availability depends on the Bright Data zone and network;
see [Bright Data's configuration guide](https://docs.brightdata.com/proxy-networks/config-options).

Omitting `bright_data` on update preserves its configuration. Supplying the object
replaces it; omitted targeting fields clear those selections. Set `enabled:false`
to disable managed suffixes. Bright Data and Oxylabs cannot both be enabled.
Responses include `bright_data`; passwords and generated sticky IDs are excluded.

IDs survive reopening a session and editing its proxy location. Assigning a
different proxy, re-enabling managed sessions, or creating a new independent Session
generates its own routing identity. A sticky ID requests the same peer; Bright Data may replace an
unavailable peer. Location changes can also change the peer.

Version 4 proxy and profile transfer archives preserve Bright Data configuration.
Older versions remain importable with managed Bright Data settings disabled.

`POST /v1/proxy-transfers/export` accepts `alias`, `include_credentials`, and
an optional `passphrase`. It returns `data.filename` and `data.contents_base64`,
where `contents_base64` decodes to the complete versioned `.relproxy` SQLite
archive. Ordinary clients must set `include_credentials:false`. Including
app-protected credentials requires a nonempty passphrase and the private
authorization header held by the owning REL app.

`POST /v1/proxy-transfers/import` accepts `contents_base64`, an optional `alias`
override, and the passphrase when credentials are included. It validates and
decrypts the transfer in Rust and returns the newly created `data.proxy`.
Transfers are limited to 12 MiB and never overwrite an existing alias.

## Sessions

Use the [Project and Session contract](SESSIONS.md) for creation, deliberate
sharing, scope, reapply and closure. Every creation request requires `project_id`;
it does not implicitly join state based on a Profile or display name.

```json
{"project_id":"Research","profile":"Research"}
```

An independent Session resource includes its `id`, `project_id`, `name`, Profile
identity, filtering/connection settings and creation time. `group_id` is optional
and identifies only an explicit shared set. Use the Session ID for browser work;
there are no public group resources. Deleting the final Session does not create
another tab.

### Browser diagnostics

`GET /v1/sessions/{id}/debug-state` and `/trace?after={cursor}&limit=200` bypass
browser operation queues. `POST /v1/sessions/{id}/debug-bundle` exports bounded
state and trace with explicitly requested artifacts. Responses use the normal
RPC envelope; errors retain IDs/retryability with additive diagnostic details.
See [browser diagnostics](BROWSER_DIAGNOSTICS.md) for complete fields, privacy,
retention and an RYM 503 example.

## Profiles

Profiles are saved session configurations. REL ensures an editable **Default**
profile at startup. If a saved **REL** profile exists and Default is missing, REL
renames it in place, preserving its ID and configuration. Default cannot be
renamed or deleted, and it does not count toward the custom-profile limit.

Fingerprint `browser_version` and its matching `Chrome/` User-Agent token resolve
to REL's bundled Chromium version when read or imported. An optional
`chrome_version` equal to the supplied `browser_version` follows that engine
version automatically, including across future upgrades. Canonical profiles
persist `chrome_version_follows_engine`: true follows Chromium, while false
keeps an explicit fixed version even if the engine later matches it. This field
requires a non-null `chrome_version`. Older profiles without the field infer the
binding from version equality. A distinct explicit `chrome_version` is preserved;
omission keeps native Chromium branding. Startup
also persists refreshed versions for saved Sessions and Profiles without changing
other fingerprint settings or browser data.

A profile resource is:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "BandwidthSaver",
  "proxy_alias": null,
  "adblock_enabled": true,
  "image_blocking_mode": "over_limit",
  "image_size_limit_kb": 10,
  "includes_cookies": false,
  "includes_passwords": false,
  "fingerprint_profile": {
    "schema_version": 1,
    "seed": "12345",
    "platform": "macos",
    "browser_brand": "chromium",
    "browser_version": "154.0.8037.98",
    "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.8037.98 Safari/537.36",
    "locale": "en-US",
    "timezone": "America/Los_Angeles",
    "network_profile": "desktop",
    "hardware_concurrency": 8,
    "device_memory_gib": 8,
    "max_touch_points": 0,
    "screen": {
      "width": 1920,
      "height": 1080,
      "available_height": 985,
      "device_scale_factor": 2
    },
    "graphics_profile": "apple-m2",
    "storage_quota_bytes": 107374182400,
    "canvas_noise_mode": "deterministic",
    "audio_noise_mode": "deterministic"
  },
  "is_builtin": false,
  "created_at": 0
}
```

- `GET /v1/profiles` returns saved profiles sorted by name in `data.profiles`.
  Profiles do not expose a `color` field. Creation and updates reject `color`;
  the app no longer assigns or edits profile colors. Reserved database and
  archive columns remain for schema compatibility.
- `POST /v1/profiles` requires a case-insensitively unique `name`; it accepts
  the proxy, filtering, browser-data inclusion, and `fingerprint_profile`
  fields above and returns `data.profile`. Omitting `fingerprint_profile` uses
  the Private template. Set it to `null` for native Chromium identity.
- `viewport_preset` is optional: `null` (App Default), `fitWindow`, `desktop`
  (1440w), `wideLaptop` (1280w), `laptop` (1024w), `tablet` (768w), or `mobile`
  (320w). `POST /v1/profiles` stores the default for new sessions. On
  `PATCH /v1/profiles/{id}`, omission preserves it and explicit `null` clears it.
  Session creation copies it to the session resource’s `initial_viewport_preset`.
  The app initializes the session workspace with that preset; saved workspace
  selections take precedence, and later Profile changes leave existing sessions
  unchanged. Profile archive and settings-text transfers
  preserve this field.
- `asset_cache` defaults to `{"is_enabled":false,"maximum_size_bytes":536870912}`.
  Cross-reset asset caching is currently disabled. `POST /v1/profiles` and
  `PATCH /v1/profiles/{id}` reject `is_enabled:true` with a usage error.
  Both fields remain required when this object is supplied; `is_enabled` must
  be false, and `maximum_size_bytes` must be 134217728, 268435456, 536870912,
  or 1073741824. Omission on update preserves size metadata. Profile and Group
  responses report caching disabled, including for saved or imported settings
  that previously enabled it. Existing transfer schemas and
  `asset_cache_profile_id` remain readable. The app does not read or write the
  cross-reset asset cache while disabled. See
  [Profile asset caches](APP.md#profile-asset-caches).
- `http_rules` defaults to `[]`. Each entry requires `action:"notification"`,
  a unique integer `status_code` (100–599), and integer `repeats` (0–1,000,000).
  Up to 100 rules are accepted. For example:
  `[{"action":"notification","status_code":503,"repeats":0}]`.
  A matching rule notifies; it does not reset, rotate or replace Sessions.
  Zero repeats triggers on the first matching response; N repeats on match N + 1.
  New Sessions copy rules from their Profile; existing Sessions require explicit
  configuration reapply. On update, omission preserves rules and `[]` disables them.
- `PATCH /v1/profiles/{id}` accepts any editable profile setting and returns
  the updated custom profile in `data.profile`. REL.app uses the browser-data
  flags only after it has safely staged imported browser data; cookie and
  password values never cross RPC.
- `DELETE /v1/profiles/{id}` deletes a custom profile and returns
  `data.deleted_id`. Built-in IDs are not stored and cannot be deleted.

### Profile model defaults

Profiles accept an optional `default_model` object on creation and update:

```json
{"default_model":{"model_id":"<model-picker identifier>","effort":"high","speed":"priority"}}
```

`model_id` is the app's model-picker identifier, including its configured
provider connection where applicable. `effort` accepts `minimal`, `low`,
`medium`, `high`, or `xhigh` (default `medium`); `speed` accepts `standard`,
`priority`, or `flex` (default `standard`). The UI offers only supported controls.
Omitting `default_model` on update preserves it; `null` clears the override.
Session creation copies it from the Profile. `POST /v1/sessions` may supply an
explicit `default_model`, including `null` for application defaults. Session
responses include the copied preference. Existing chats retain their model.
Profile archives preserve model preferences; archives before version 7 have no
model override.

### Profile starting URL

Profile creation and update accept optional `starting_url`: an HTTP or HTTPS URL
with a host, no embedded whitespace, and at most 2,048 UTF-8 bytes after trimming.
Omit it or use `null` when creating without a starting page. On update, omission
preserves the value and `null` clears it. Profile responses include the value.
The app opens this page when creating a new Session from the Profile; existing
groups keep their state unless explicitly reset. Profile archives preserve it;
archives before version 9 import without a starting URL.

### Profile setup definitions

Saved Profile responses include optional `setup` (null for ordinary Profiles).
`POST /v1/profiles` accepts it and `PATCH /v1/profiles/{id}` replaces it in full;
omitting the field preserves it and explicit null removes it. This stores a
declarative template. It does not create a session or execute Actions.

```json
{
  "version": 1,
  "title": "Marketplace monitor",
  "description": "Find nearby used items and report new matches.",
  "sourceUrl": "https://github.com/rel-me/rel-case-studies/pull/3",
  "inputs": [
    {"key": "query", "label": "Search", "kind": "text", "defaultValue": "stroller wagon"},
    {"key": "radius", "label": "Radius in miles", "kind": "number", "defaultValue": "10"}
  ],
  "checklist": ["Sign in to the required sites in this session."],
  "actions": [{
    "name": "Find matches",
    "prompts": ["Find used {{query}} within {{radius}} miles."],
    "startingUrl": "https://www.facebook.com/marketplace",
    "schedule": {"weekdays": [1, 2, 3, 4, 5, 6, 7], "hour": 9, "minute": 0},
    "stopOnError": true
  }]
}
```

`setup.version` is 1, independently of the JSON transfer envelope and binary
archive versions. `sourceUrl`, `startingUrl`, and `schedule` may be omitted or
null. An absent schedule creates a manual Action; weekday numbers are Sunday=1
through Saturday=7, without duplicates. Hours are 0–23 and minutes 0–59 in the
Mac's current time zone. All other fields shown are required. `stopOnError` is a
Boolean. There is no enabled state, executable script, external integration
secret, session ID, or runtime Action ID in a setup.

Limits: 512,000 serialized bytes per setup; 1–20 Actions; up to 20 inputs and
checklist entries; 1–20 prompt steps per Action. Titles and input labels are at
most 120 characters, descriptions 4,000, checklist entries and default input
values 2,000, Action names 80, and each prompt 100,000. Required text is nonempty.
Input keys are unique, 1–64 ASCII letters/digits/underscores. Kinds are `text` or
`number`; numeric defaults and supplied values must parse as finite numbers.
Unknown fields, versions, undeclared prompt placeholders, and malformed schedules
are rejected. URLs must use HTTP(S), have a host, and contain no credentials.

REL app session creation substitutes inputs once and installs all templates in
one local Action persistence write, with fresh IDs and disabled state. Setup
instructions are retained with those Actions. The current CLI/MCP/SDK creation
paths apply browser defaults only; they do not install native Action templates.
Setup import and export never copy Action run state or browser authentication.

`POST /v1/profile-transfers/export` accepts `name`, `include_cookies`,
`include_passwords`, `include_proxy_credentials`, and an optional `passphrase`.
It returns `data.filename` plus `data.contents_base64`, which decodes to the
versioned `.relprofile` SQLite archive. A passphrase and the owning app's
private authorization header are required when any secret category is
selected. The Rust response contains the schema and Profile/Proxy records; the
app adds encrypted browser records before presenting the file to the user.

`POST /v1/profile-transfers/import` accepts `contents_base64`, optional `name`
and `passphrase` fields, and app-only `browser_data_ready`. It validates the
archive in Rust, decrypts embedded Proxy credentials, and returns the newly
created `data.profile`. The owning app sets `browser_data_ready:true` only
after it has authenticated and decrypted the browser records for restoration.
Transfer files are limited to 12 MiB and never overwrite an existing name.
Version 8 stores optional validated `setup_json` in `profiles`; older archives
import with no setup. Supported archive versions are 1 through 8.

Both transfer types use SQLite `application_id` `RELT`, schema version 8, and
the same five tables: `metadata`, `proxies`, `profiles`, `cookies`, and
`passwords`. The `proxies` table is identical for standalone Proxy archives
and Proxies embedded in Profile archives. Protected credential and browser
payloads are encrypted BLOBs. Version 1 accepts no legacy JSON representation.

Existing Sessions retain their stored settings and browser data after built-in
Profiles are removed. The old built-in names are no longer reserved: they can
be used for new saved configurations. Historical schema migrations retain their
original data-preserving rename behavior.

Profile names contain 1–128 non-control characters after trimming and are the
selector used during session creation. On `POST /v1/sessions`, omission selects
the **Default Profile** configured in **Settings → General**, or the saved **Default**
profile when no preference is set. This applies to clients that omit the field.
Create Session in the app can send explicit settings. `profile:null` keeps
standalone Custom configuration without inheriting a saved profile or browser data. An explicit saved profile always takes precedence. The preference
uses the stable profile ID, so renaming a custom profile preserves its selection.
If that profile is deleted, creation without an explicit profile reports an error
until another default is selected. Explicit session settings override the selected profile. A present
`proxy_alias:null` is a direct override; a non-null value must reference an
existing proxy. Automatically created sessions for capture, navigation, and
attached pages follow the same rule. Capture events and page responses include
the effective session ID. Browser-data payloads remain app-owned and never
cross RPC in plaintext; the inclusion flags describe what the app has attached to a custom
profile. Importing a selected category again replaces that category in the
app-owned template without changing sessions already created from it.

The fingerprint object is an identity template. Every session creation path
copies the selected profile through the agent. It preserves the template settings and generates a fresh
seed before the session's Chromium context is used. New profiles and Custom
sessions use Private when `fingerprint_profile` is omitted; explicit null
keeps native values. `POST /v1/sessions` also accepts `fingerprint_profile` as a
direct override of the selected configuration.


Fingerprint profiles also accept an optional `overrides` array. Omit the field
to enable all supported overrides, or provide an explicit list to leave
all unlisted controls native. An empty array applies no overrides. All existing
profile value fields remain required and validated; inactive values are stored
for later editing, but are not sent as browser overrides.

| Override | Applied behavior |
| --- | --- |
| `locale` | Language preferences and locale, applied only when resolved values differ from native |
| `timezone` | IANA timezone |
| `hardware_concurrency` | CPU thread count shared by windows, frames, and all worker types |
| `network` | Network information profile |
| `device_surfaces` | Linked memory, touch, screen/pixel ratio, PDF plugin fallback, and storage quota controls |
| `graphics` | Canvas noise and the selected graphics profile. `graphics_profile: "native"` preserves native WebGL/WebGPU; curated GPU profiles apply WebGL identity/extensions/readbacks and make WebGPU unavailable. |
| `audio` | Generated oscillator signal variation using the profile's audio mode; buffer and analyser reads preserve actual values |

With `device_surfaces` enabled, `device_memory_gib` supplies both JavaScript
device memory and the `Device-Memory` / `Sec-CH-Device-Memory` HTTP hints.
HTTP hints still require the site's client-hint opt-in and permissions policy.
CSS device-width and device-height queries use the profile's screen dimensions,
and resolution queries use its device scale factor;
color queries report 8 bits per component, sRGB, and standard dynamic range,
matching the profile's 24-bit screen surface. These settings do not resize the
page viewport. Native sessions and profiles with `device_surfaces` disabled
retain the engine's native values.

`locale_mode` accepts `automatic` or `custom`. Private defaults to
`automatic`. Resolution uses an explicit Custom `locale` first, then the
assigned proxy's configured `locale`, then the macOS user's preferred/default
locale. In Automatic mode the required legacy `locale` field is stored but does
not pin the effective value. A proxy country alone is never a language hint.
Matching native values skip both language and locale emulation; the stored
control selection stays enabled. A disabled `locale` control always stays native.

For older fingerprints without `locale_mode`, omitted `overrides` means
Automatic, while an explicit override list preserves Custom locale semantics.
Set `locale_mode` explicitly when writing new fingerprints. Resolution is shared
by app, CLI, SDK, MCP, and restored sessions when their Chromium contexts are
prepared. Proxy routing, data, and the remaining privacy controls are unchanged.

Browser identity overrides have been removed. Chromium generates the User-Agent
with a reduced product version and supplies native platform and client hints for every session, including
legacy full profiles. The retired `identity` selection is accepted only to read
old profiles and is removed during normalization. Stored browser identity fields
remain required for the existing schema but do not override browser identity.

For example, add `"overrides": ["timezone"]` to a valid profile with
`"timezone": "Asia/Tokyo"` to change only timezone. Unknown override names and
non-array values are rejected. Saving the profile preserves this list through
export/import. Missing lists in older profiles enable the remaining supported overrides.

New profile drafts and Custom session defaults use **Private**,
with all seven supported controls enabled. Its read-only details are hidden
by default in profiles, identity editors, and session information. Choose
**Show** to the left of the mode value to open a popover without expanding the parent
layout. The **Browser Identity** row belongs to the main Profile section.
Choose **Custom Privacy** to edit individual values and toggles in compact rows.
Profile forms open those settings in a separate editor; **New Browser Identity…**
starts from the current identity and **Use Identity** applies the custom settings
to the Profile draft.
The shared device preset appears once, info buttons explain linked settings,
and the readback seed is in an expandable section. **Native** turns off all
controls. Chromium generates the User-Agent with the product version reduced to
`MAJOR.0.0.0` in every mode. Native branding and client hints remain engine-owned
and are not editable. High-entropy client hints can still expose the full engine
version when requested by a site.

Custom Privacy saves an explicit `overrides` list, including when all seven
controls are enabled or all are disabled. It therefore reopens as Custom.
Private uses the omitted-list representation; selecting it resets custom
values to the standard full preset while retaining the session seed. Native
saves a null fingerprint. Existing explicit choices and saved session-creation
preferences are preserved. Saving recreates only the session's Chromium context.
Device surfaces and graphics remain linked groups in the pinned engine.
Individual fields within those groups cannot independently remain native.

On every supported database startup, REL refreshes engine-linked fingerprint
versions and matching user agents in Sessions and named Profiles before loading
them. Seeds and other fingerprint settings are preserved; changed session
fingerprints advance their generation once. This happens transactionally in the
current app database and does not reset browser data. API submissions must supply
a numeric four-component engine version and its matching User-Agent token; REL
resolves them to its bundled runtime. Future engine upgrades use the same refresh
without requiring a separate database migration.

### Proxy TLS configuration

Proxy create/update requests accept a `tls` object, also returned on proxy resources:

```json
{"tls":{"mode":"system"}}
{"tls":{"mode":"bright_data"}}
{"tls":{"mode":"custom","certificate_pem":"-----BEGIN CERTIFICATE-----\n…\n-----END CERTIFICATE-----\n"}}
```

Use `system` to clear additional roots. Omission on create selects system trust; omission on update preserves the existing setting. `bright_data` requires `brd.superproxy.io:44445`. `custom` requires a PEM bundle with 1–16 CA certificates and a maximum size of 64 KiB. Unknown modes/fields, malformed certificates, private keys, leaf certificates and inconsistent provider endpoints are rejected before updating the proxy. Normal hostname, validity and chain verification stays enabled.

Session resources additionally contain `proxy_ca_certificates`, a derived array of base64 DER CA certificates from the assigned proxy. Direct sessions return an empty array. This is read-only session metadata; configure trust on the proxy. Updating proxy certificates synchronizes affected open sessions. Empty browsers apply the changes automatically; browsers with page state show a configuration banner and recreate their browser views when the user chooses Reload. Proxy/profile transfer format version 3 stores the TLS configuration; versions 1 and 2 remain readable and default to system trust.

## Webhooks

Webhook calls use the same loopback RPC v1 API. Browser session cookies,
fingerprints, and proxy settings are not used. Configure up to 32 named webhooks;
REL stores their URLs, credentials, and routing configuration in the current app
variant's macOS Keychain. List and create responses contain metadata only.
Webhook request bodies are limited to 32 KiB.

| Method | Path | Result |
| --- | --- | --- |
| `GET` | `/v1/webhooks` | `{webhooks:[...]}` metadata |
| `POST` | `/v1/webhooks` | Create configuration; `{webhook:{...}}` |
| `DELETE` | `/v1/webhooks/{id}` | Remove configuration and its pending events; `{deleted:true}` |
| `POST` | `/v1/webhooks/{id}/send` | Send once; `{webhook_id,http_status,accepted:true}` |
| `GET` | `/v1/webhooks/events` | `{events:[...]}` pending inbound events |
| `DELETE` | `/v1/webhooks/events/{event_id}` | Acknowledge/remove an event; `{acknowledged:true}` |
| `POST` | `/v1/webhooks/{id}/receive` | Authenticated provider callback |
| `GET` | `/v1/webhooks/{id}/receive` | WhatsApp callback verification only |

There are no webhook CLI commands, MCP tools, or typed SDK methods yet. Scripts
can use these HTTP endpoints directly. Settings provides creation, deletion,
callback copying, and an explicit **Send Test** action.

### Configuration

Create a webhook with a unique `name`, `kind` (`json`, `discord`, or `whatsapp`),
and at least one direction:

```json
{
  "name": "Team updates",
  "kind": "discord",
  "url": "https://discord.com/api/webhooks/WEBHOOK_ID/WEBHOOK_TOKEN"
}
```

For outgoing calls, `url` is an absolute HTTPS URL. HTTP is allowed only for
`localhost`, `127.0.0.1`, and `::1` fixtures. URL userinfo and fragments are
rejected. Optional `bearer_token` sets the Authorization bearer token. WhatsApp
sending additionally requires `recipient` and `bearer_token`; set `url` to the
versioned Graph API `/{phone-number-id}/messages` endpoint. REL does not choose
or upgrade the Graph API version.

For incoming events, add:

```json
{
  "receive": {
    "schedule_id": "UUID-OF-A-SAVED-ACTION",
    "secret": "PROVIDER-SIGNING-SECRET-OR-DISCORD-PUBLIC-KEY",
    "verify_token": "WHATSAPP-VERIFICATION-TOKEN"
  }
}
```

`receive.schedule_id` is the UUID of an Action saved in REL. The historical
wire and Keychain field name is retained; it targets an Action, not a timer.
Existing saved prompts become Actions with the same UUID. Settings offers an
Action picker. `secret` must be 32 to 4096 bytes. For Discord it is the application's
64-digit hexadecimal Ed25519 public key. For WhatsApp it is the Meta app secret;
`verify_token` must contain at least 16 characters. JSON webhooks use an HMAC
signing secret and do not need `verify_token`.

Metadata is `{id,name,kind,can_send,schedule_id,receive_path}`. The last two
fields are null for destinations without an incoming trigger. Credentials and
outgoing URLs are never returned. To rotate or change a destination, create a
replacement, update prompt completion selections, and delete the old webhook.
Deletion does not silently redirect prompts to another destination.

### Sending

Send either `{"text":"Hello"}` or `{"payload":{...}}`, never both. The JSON
object `payload` is sent unchanged for service-specific messages such as
WhatsApp templates or Discord embeds. `text` maps to:

- JSON: `{"text":"Hello"}`.
- Discord: `{"content":"Hello","allowed_mentions":{"parse":[]}}`.
- WhatsApp: `{"messaging_product":"whatsapp","to":"RECIPIENT","type":"text","text":{"body":"Hello"}}`.

Text limits are 2,000 characters for Discord and 4,096 for WhatsApp. Longer
messages fail with `INVALID_REQUEST`; they are never silently truncated or
split. Shorten the saved prompt's expected output or supply a service-specific
payload. Discord calls set `wait=true`, preserving other query parameters.

Delivery has a 15-second timeout, disables redirects, and makes no automatic
retry. HTTP 2xx means the provider accepted the request, not that a person read
it. HTTP 429 returns `RATE_LIMITED`; other non-2xx statuses, including redirects,
return `UPSTREAM_UNAVAILABLE`, with `details.http_status`. Transport failures
also return `UPSTREAM_UNAVAILABLE`. These errors have `retryable:false`: after
a timeout or ambiguous failure, inspect the destination before sending again.
Provider response bodies and transport URLs are omitted from errors.

### Receiving and consuming events

The local agent stays bound to loopback. An external provider requires a public
HTTPS relay or reverse proxy forwarding **only** the selected
`/v1/webhooks/{id}/receive` path, preserving the raw JSON body, query string, and
signature headers. Buffer and size-limit the request at the relay. Never expose
management, send, inbox, browser, or other RPC routes to the public internet.
Relaying, DNS, TLS certificates, and provider subscriptions are configured
outside REL. REL must remain open and the Mac reachable.

- **JSON**: `X-REL-Webhook-Signature: sha256=<hex>` contains HMAC-SHA256 of the
  exact raw body using the configured secret. Include a unique event identifier
  in the body when otherwise identical events should run separately.
- **WhatsApp**: `X-Hub-Signature-256: sha256=<hex>` contains HMAC-SHA256 of the
  raw body with the Meta app secret. Verification accepts
  `hub.mode=subscribe`, the configured `hub.verify_token`, and a numeric
  `hub.challenge`; it returns the challenge as plain text. Signed message
  notifications for `object:whatsapp_business_account` enter the inbox. Status
  receipts are acknowledged without triggering a prompt, avoiding reply loops.
- **Discord Webhook Events**: verify `X-Signature-Ed25519` against the timestamp
  concatenated with the raw body. `X-Signature-Timestamp` must be within five
  minutes of the Mac's clock. A signed `type:0` PING receives an empty HTTP 204;
  signed `type:1` events enter the inbox and receive HTTP 204. This endpoint is
  for Discord Webhook Events, not Gateway events or interaction callbacks.

Missing, invalid, or stale signatures return HTTP 401. Other callback errors
use RPC error envelopes. JSON and WhatsApp accepted event responses use the
ordinary success envelope with `{accepted:true}`; exact duplicate bodies return
`{accepted:false}`. WhatsApp status-only receipts return plain text HTTP 200.
Discord callback acknowledgements and WhatsApp verification/status responses
use the provider's wire format without the ordinary RPC envelope/request ID.

Events have `{id,webhook_id,schedule_id,payload,trust}`; `trust` is always
`untrusted_webhook_content`. The inbox holds at most 64 pending events and
returns `RATE_LIMITED` (429) instead of dropping events when full. The most
recent 1,024 accepted body hashes, scoped to their webhook, suppress duplicates
even after acknowledgment. The inbox and duplicate history are in memory and
reset when the agent exits. This is not a durable queue or an exactly-once
processing guarantee.

The app polls every two seconds, waits for the selected Action to be enabled
and idle, acknowledges the event, and runs that saved Action with the body
explicitly labeled as untrusted data. The original saved prompt is unchanged.
Incoming data cannot select another prompt or completion destination. Missing,
disabled, and busy Actions leave events pending; remove their webhook or use
the event DELETE endpoint to clear them. A model failure is recorded as a failed
prompt run, without automatically replaying the event. A crash after
acknowledgment can interrupt an event's run. Separate consumers should not
acknowledge events intended for the app.


History navigation also crosses user-opened popup pages within a Session.
`back` traverses the active page's native history before returning to its opener;
`forward` can select the retained child again. New navigation after going Back
discards the retained forward pages. The toolbar and navigation API use the
same history.

## Workspace restoration

REL preserves each tab's root-page HTTP(S) Back/Forward history and current
position across app restarts. Sessions in one Group share storage and
configuration, while their navigation entries stay separate. `group_id` identifies
the owning group; it is not a caller-defined batch label. Opening a saved
page restores its native history without fetching earlier or later entries.
Visiting a new page after going Back discards that tab's forward branch.

The bridge captures URL-only entries from Chromium's navigation controller and
saves them with the tab in the workspace. Each record contains at most 1,000
entries and includes its current position. Existing single-tab Sessions retain
their stored history when first opened as a group. Clearing a group's browsing
data clears history for all its tabs. Popup history, form values, POST bodies,
and scroll positions are not restored across restarts. Saved URLs never include
embedded credentials.

`GET /v1/workspace` returns `data: {"revision": N, "state": ...}`. Revision zero
with `state: null` means no workspace has been saved. The Rust agent owns this
state in the current runtime's `Data/rel-data.sqlite3`; Release and each Debug
worktree remain isolated. On first access, the agent imports the released
layout/token-usage format from that runtime's `Data/workspace-state.json`, if
present, and retains the source. Import failure leaves the database workspace
uninitialized and prevents replacement writes through this endpoint.

`PUT /v1/workspace` accepts `{"revision": N, "state": ...}` using the revision
returned by GET or the previous successful PUT. It atomically saves the full
workspace snapshot and returns `data: {"revision": N+1}`. A stale revision returns
`CONFLICT` without changing stored data. An uncertain transport result must be
resolved by reloading the snapshot before another write. The native app serializes
writes and requires a restart after a conflict or uncertain save result.

A `VALIDATION_FAILED` rejection does not commit or advance the revision. If a
workspace snapshot refers to a session that was deleted, the native app reads
`GET /v1/sessions`, removes only confirmed missing sessions from the rejected
snapshot, and automatically saves again at the same revision. Edits and sessions
created during that read are preserved, and late browser or chat callbacks cannot
restore deleted workspace entries. If session membership cannot be read or the
validation failure persists, REL keeps the local state and shows the save error;
use **Save Current Workspace** to retry.

The state uses these camelCase fields:

| Field | Type / meaning |
| --- | --- |
| `schemaVersion` | Integer `1`, the workspace wire format, independent of the database migration version |
| `selectedSessionID` | Session ID or null; must be in `tabOrder` |
| `tabOrder` | Ordered unique session IDs present in `sessions` |
| `closedSessionIDs` | Pending session-close markers, default `[]` |
| `sessions` | Object keyed by existing session ID |

Each session value contains:

| Field | Type / meaning |
| --- | --- |
| `lastCommittedURL` | Selected tab's HTTP(S) URL without credentials, or null |
| `pageTabs` | Ordered tabs, default `[]` for existing single-tab state. Each entry has a unique nonempty `id` (at most 128 UTF-8 bytes), optional HTTP(S) `url` without credentials, optional finite `lastOpenedAt`, Boolean `isNetworkPaused` (default false), and optional `navigationHistory`. |
| `selectedPageTabID` | Tab ID or null; when present it must belong to this session's `pageTabs`. |
| `isNetworkPaused` | Boolean, default false |
| `workspace` | `{isBottomPanelPresented: Bool, isChatPresented: Bool, selectedTool: String, viewportPreset?: String}`; tool is `info`, `filters`, `schedules` (Actions), `logs`, or `terminal`; defaults are false, true, and `logs`. `viewportPreset` is `fitWindow`, `desktop` (1440w), `wideLaptop` (1280w), `laptop` (1024w), `tablet` (768w), or `mobile` (320w); omit it or use `null` to inherit the app default. |
| `chatTokenUsageByModel` | Object of cumulative native Chat usage records keyed by model usage key; default `{}` |
| `chats` | Conversation state described below; defaults to no conversations, null selection, and next sequence 2 |

A tab's `navigationHistory` is `{"urls": ["https://example.com/"], "currentIndex": 0}`.
It contains 1 to 1,000 HTTP(S) URLs without embedded credentials, with a zero-based
index inside that array. Omit the history or use null for a fresh tab. History,
tab order, and selection save atomically with the rest of the workspace. Invalid
history or tab membership rejects the entire PUT without advancing its revision.
`lastOpenedAt` uses the native workspace's seconds since 2001-01-01 UTC.

`chats` contains ordered `conversations`, nullable `selectedConversationID`, and
`nextSequence` (integer at least 2). Each conversation has a stable UUID `id`,
`title`, `draft`, and ordered `messages`. Selection references a conversation
within that session. Each message has a stable UUID `id`, `role` (`user`,
`assistant`, `error`, or `status`), `content`, and optional `completedWork`
(`{activities: [...], elapsedTime: seconds}`). Activity records contain `id`,
`title`, optional `detail`, and `status` (`running`, `completed`, or `failed`).

Messages may also include Jev's `decision`: `{"status": "done", "actions": 3,
"confidence": 0.9}`. Status is `done`, `uncertain`, `blocked`, `stalled`, or
`limit`; `actions` is a nonnegative integer and optional `confidence` is a number
from 0 through 1. Decision results are preserved for both session and global
chats. Omitting `decision` or sending null clears it; messages saved before this
field was introduced remain valid. The workspace wire version remains 1.

Conversations may include `chatConfiguration`, containing `model`, `effort`, and
`speed`. REL preserves this selection for both session and global chats, including
empty conversations. Omitting it or sending null clears the saved selection;
workspaces saved before this field was introduced remain valid.

`model` contains `id`, `displayName`, `provider`, `modelID`, `source`,
`verification`, `capabilities`, and `displayProvider`, with optional `profileName`,
`profileID`, and `createdAt`. `source` uses Swift Codable encoding:
`{"builtIn": {}}` or `{"configured": {}}`. `displayProvider` is
`{"adapter": {"_0": "openai"}}` (using the selected provider kind), or an empty
object case named `fireworks`, `amazonBedrock`, or `baseten`. `capabilities`
contains `supportsReasoningEffort`, `supportedSpeeds`, and
`isRecommendedInChatPicker`. These are model selection metadata, never API keys.

New conversations follow the [Chat model selection policy](APP.md#ai-models).

Each token-usage record contains nonnegative integer `modelCalls`,
`reportedModelCalls`, `knownTokens`, `inputTokens`, `outputTokens`,
`providerReportedTotalTokens`, `cachedInputTokens`, `cacheCreationInputTokens`,
`toolUsePromptTokens`, and `reasoningTokens`, plus optional nonnegative
`providerReportedCostUSD`. Reported model calls cannot exceed total model calls.
Session usage and `globalChat.usage` may also include `contextPricingUsage`:
`{"uncachedInput": 552500.5, "cachedInput": 50000, "output": 3001.5}`. These are
weighted per-call pricing totals; present values must be finite, nonnegative
numbers and may be fractional. Missing members default to zero. REL preserves
them across saves.
Omitting this object or sending null leaves context pricing unavailable; REL
does not infer it from aggregate tokens. Older records remain valid, and the
workspace wire version remains 1.
Workspace records ignore unknown JSON properties, including nested properties;
unknown properties are discarded rather than stored. Missing fields use empty
collections/strings, zero counts, absent optional values, or existing defaults:
wire version 1, Logs, chat visible, next chat sequence 2, title `Chat`, message
role `status`, completed activity status, and uncertain decisions. Missing record
IDs receive new UUIDs. Missing tab order is derived from saved open sessions;
missing session records receive defaults for referenced tabs. Unavailable
selections clear to none. Incomplete model selections clear without discarding
their conversations; missing effort/speed use medium/standard, and missing
verification metadata uses unverified. A missing total
model-call count uses the reported count. The save envelope still requires
`revision` and `state`; revision conflicts, unsupported wire versions, malformed
supplied values, and record ownership violations still fail without changing state.

Conversation and message IDs must be unique across the workspace and cannot move
between parents. Omitting a conversation or message removes its saved record.
Draft-only edits do not rewrite message rows. Session deletion removes its saved
workspace, conversations, and messages in the same database operation. Pending
close markers survive layout reconciliation until session deletion completes.

The standard 16 MiB request limit applies. Workspace request logs record the
method and route, without transcript or draft bodies. Database schema upgrades
are transactional, and newer unsupported database schemas are left untouched.


### Pending browser configuration

While an open session has configuration changes waiting for Reload, browser
automation reports `BROWSER_UNAVAILABLE` with a message asking you to reload, instead of running
with the previous browser configuration. Choose **Reload** in REL to apply the
saved changes, then retry. Saving configuration and pausing network activity
remain available while a reload is pending.

## Session lifetimes and keepalive

Every newly created session has a lifetime policy, including sessions created
implicitly by browser operations. Omitting `lifetime` selects
`{"type":"inactivity","timeout_seconds":120}`. Explicit `POST /v1/sessions`
requests may set a positive integer timeout (up to 4294967295 seconds), or
`{"type":"indefinite"}` to keep the session until it is explicitly closed.
For example:

```json
{"group":"research","lifetime":{"type":"inactivity","timeout_seconds":300}}
```

Session responses include `lifetime` and the Unix-seconds `last_activity_at`.
Session-directed requests and browser operations refresh activity. Active browser
operations do not expire while running. Background page traffic, health checks,
and listing sessions do not keep sessions alive.

`POST /v1/sessions/{id}/ping` with `{}` refreshes activity without browser work
and returns the ordinary session envelope (`data.session`). Ping comfortably
before the timeout, for example every 30 seconds with the default policy.
Pinging a closed session returns `SESSION_NOT_FOUND`; it never recreates it.
Expiry follows normal session close cleanup, invalidating attached pages.
Lifetime settings survive agent restarts. Existing sessions upgraded from older
versions retain an indefinite lifetime, as do explicitly created native app tabs.

## Native WhatsApp remote control

These routes belong to the owning REL app and require its existing app authorization.
They are not exposed to ordinary remote bearer-token, CLI, MCP, or SDK clients.
See [WhatsApp setup and commands](APP.md#control-rel-through-whatsapp) for the
user interface. Responses use the normal endpoint envelope and `Cache-Control: no-store`.

`GET /v1/whatsapp` includes `connection.remote_enabled` (default false) and
`connection.remote_epoch` (an opaque authorization generation) alongside linked
account and destination metadata.

| Method | Route | Body and behavior |
| --- | --- | --- |
| `POST` | `/v1/whatsapp/remote/enabled` | `{ "enabled": true }`; requires an enabled linked account and selected group. Persists the opt-in in the app's Keychain namespace and returns connection metadata. |
| `POST` | `/v1/whatsapp/remote/claim` | `{}`; consumes one fresh command, returning `{ "command": { "id": "…", "text": "status", "timestamp": 123 }, "epoch": "…" }`, or `command: null`. Text excludes `/rel`. Only the app's serial remote controller should claim. |
| `POST` | `/v1/whatsapp/remote/reply` | `{ "id": "…", "epoch": "…", "text": "…" }`; requires the currently claimed command and current opt-in, destination and epoch. Uses the saved group, adds `REL: `, and consumes reply permission before sending. |

Reply text including its prefix must contain at most 4,096 Unicode scalar values.
Replies have a 32 KiB request-body cap; other remote requests have a 4 KiB cap.
Changes to access or destination, and owner `/rel cancel` commands, replace the
epoch and clear pending work. A consumed command or uncertain send is not retried.
The app cancels execution if it loses the status/authorization channel.

Native `POST /v1/whatsapp/send` rejects output beginning with the reserved `/rel`
command prefix (followed by whitespace or end of text), preventing an Action
notification from executing as a command on another linked-device delivery.
Add a descriptive heading to such notification output. Remote replies already
receive the `REL: ` heading.

## Shared Models metadata

`GET /v1/model-providers` returns `data.version`, `data.connections`, and
`data.defaultConnectionId`, plus `data.modelDirectories`, which maps model IDs
to selected absolute download folders. Each connection has `id`, `name`, `provider`,
`baseUrl`, and `modelId`. Credentials are never returned. REL supplies its
current database and explicit Keychain reference to Fritz's shared Models service;
there is no separate Fritz provider database. Use the shared Models UI to edit
connections. Chat reads this metadata through the versioned API and reads its
explicit Keychain reference in Rust; it does not open the REL database directly.

## License activation

`POST /v1/license/activate` accepts `{ "license_key": "..." }` and forwards
activation to the owning REL app. The key must be one nonempty line, at most
4096 UTF-8 bytes. The app validates the product and stores the credential through
its existing registration flow. Do not log this request body. The success envelope
contains `{ "activated": true, "plan": "pro" }`. Failed activation returns
`VALIDATION_FAILED` with a credential-free message. Licensing must be
configured and an existing stored license must be managed in the app.

## App updates

`POST /v1/app/update` accepts an empty JSON object and requests the owning app's
native Sparkle update flow. It follows the app's saved update channel. The response
contains `{ "state": "requested", "channel": "regular", "user_interaction_required": true }`.
This acknowledges a request, not a completed update. Confirmation, download,
installation and restart remain in the native updater. Unconfigured builds return
`VALIDATION_FAILED`; a busy updater returns retryable `CONFLICT`. Extra request
fields are rejected. See [CLI app updates](CLI.md#app-updates).

While the app is checking registration/updates or requires an upgrade, the agent
runs in management mode. Only `GET /v1/health`, `GET /v1/status`,
`POST /v1/license/activate` and `POST /v1/app/update` remain available. Other
requests return retryable `CONFLICT`; Browser Proxy listeners remain stopped.
Normal operations resume when the owning app restores access.

## Native WhatsApp settings

These app-authorized routes manage the native linked-device connection. They
require the owning REL app's authorization and return `Cache-Control: no-store`.
They are separate from the WhatsApp Cloud API webhook integration.

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/v1/whatsapp` | Read connection status |
| `POST` | `/v1/whatsapp/connect` | Begin or resume pairing when enabled |
| `POST` | `/v1/whatsapp/enabled` | Persist `{"enabled":true}` or `{"enabled":false}` |
| `DELETE` | `/v1/whatsapp/connection` | Remove the saved connection and preferences |
| `GET` | `/v1/whatsapp/groups` | Refresh participating groups while connected |
| `POST` | `/v1/whatsapp/destination` | Save `{"id":"group@g.us"}` from the refreshed group list |
| `POST` | `/v1/whatsapp/send` | Send `{"text":"Final response"}` to the saved group |

Status and settings mutation responses contain `connection` with `phase`, `saved`,
`enabled`, `remote_enabled`, `qr`, `expires_at`, `message`, and `destination`. The destination is
null or an object with `id` and `name`. Group refresh returns `groups`, an array
of these objects. Pairing QR values are short-lived secrets.

Disabling sets `phase` to `disabled`, stops the native client, and retains the
account credentials and group. A disabled saved account does not reconnect on
restart. Enabling resumes a saved account; an account without saved credentials
still needs the connect route. The enabled preference defaults to true for
existing installations. Group selection persists immediately without sending a
message or enabling an Action.

The send route accepts only `text`, with 1–4,096 Unicode scalar values and at
least one non-whitespace character, within a 32 KiB JSON body. Recipient overrides
and unknown fields are rejected. Output must not begin with the reserved `/rel`
command prefix followed by whitespace or end of text; add a descriptive heading
when needed. It requires enabled WhatsApp, a saved linked
account, and a saved group. It waits up to 20 seconds for connection readiness
and up to 20 seconds for sending. Success data contains `message_id` and
`destination_id`; it does not confirm the recipient has read the message.
Failures use the standard error envelope. REL does not automatically retry;
a send timeout leaves delivery uncertain. Settings changes serialize with
sending, so disabling cannot recall an in-flight message.

Request inspection: `GET /v1/sessions/{id}/network-requests/{request_id}`. Opt-in capture: `PUT /v1/sessions/{id}/network-capture`. Both use the normal response envelope. See [capture policy, retention, redaction and attribution](BROWSER_DIAGNOSTICS.md#inspect-original-network-responses).
