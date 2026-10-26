# Browser diagnostics

Use supported REL diagnostics to investigate navigation without opening internal
logs, SQLite files, Chromium storage or proxy credentials. Diagnostics observe;
they do not retry, replace sessions, navigate or infer a cause.

## Read state during an operation

`GET /v1/sessions/{session_id}/debug-state`, `rel_debug_state({session_id})`, or
`rel session debug-state SESSION_ID` returns a normal RPC envelope. It bypasses
the browser operation queue and reads cached browser callbacks. Check
`snapshot.captured_at`, `age_ms`, and `stale` (older than one second). A stale
snapshot is evidence from that time, not a fresh renderer inspection.

State includes the active operation ID, HTTP request ID, phase, zero-based action
index, selector, elapsed time, native page identity and document sequence. Requested,
network-response and browser document URLs are separate fields. Status, title,
loading and the last bounded text excerpt come from existing browser observations.
`is_browser_error_document: true` identifies recognized Chromium error markup;
null means unknown. An HTTP failure by itself does not establish an error document.
The native page ID identifies a browser instance and is distinct from ephemeral
API observation/page handles.

Cookie summaries contain counts, domains, session-cookie counts and earliest
expiry, never values. They are refreshed after document completion. Configuration
includes profile/group identity, selected proxy alias, effective browser settings
and cache configuration. Unobserved exit identity, seed history and other unavailable facts are null.
Successful existing proxy-location lookups can emit opaque exit observations
and change events; their scope is that lookup, not a guarantee about every
browser request. Cookie seed events are recorded only when the import flow
observes them. No continuity or verification diagnosis is implied.

## Follow the bounded trace

`GET /v1/sessions/{session_id}/trace?after=event_42&limit=200`,
`rel_session_trace({session_id, after?, limit?})`, or
`rel session trace SESSION_ID --after event_42 --limit 200` returns events,
`next_cursor`, `has_more`, and cumulative `dropped_event_count`.

Events describe operation start/completion/failure/cancellation, action and selector
waits, target resolution and native mouse dispatch, document navigation/commit,
response/completion/failure, redirects, completed network requests and observed
configuration/closure. A found click target does not prove dispatch; dispatch does
not prove navigation. Request metadata includes method, Chromium request ID,
resource type, status, network error and duration. The existing CEF callback does
not establish frame identity or distinguish network, HTTP cache, service worker,
asset cache and proxy-generated responses: those facts remain null or `unknown`.
Redirect events retain their native request ID and destination URL.

Buffers are independent per Session, including explicitly grouped sessions.
Each holds at most 512 events with strings bounded to 2,048 characters, retaining
at most 64 recently observed sessions. Entries expire after 30 minutes of inactivity
and all diagnostics disappear when the agent restarts. Closed sessions retain
last state under the same bounds. A session without retained observations returns
`SESSION_NOT_FOUND`. Observation of an existing session is not proof of creation
or replacement; replacement sessions have their own IDs and traces.

## Export

`POST /v1/sessions/{session_id}/debug-bundle` accepts `since_request_id`,
`include_html` (default false), and `include_screenshot` (default false).
`rel_debug_bundle` takes the same arguments. CLI:

```sh
rel session debug-bundle Session123 --since-request-id req_example
rel session debug-bundle Session123 --include-html --include-screenshot
```

The response contains an artifact with MIME type, size and a self-contained
`data:application/json;base64,...` URL. Decode or save that JSON to share it. The
bundle contains state, bounded trace, sanitized configuration and requested
artifacts. `since_request_id` must occur in the retained trace; earlier events are
excluded. Requested live artifacts use a separate read-only capture with a
three-second transport deadline; a changing/unavailable document produces
`artifact_error` while retaining the trace/state bundle. It does not cancel the
operation being inspected. HTML is limited to 2 MiB and viewport PNG to 8 MiB.
No response bodies or sensitive headers enter the default trace.

All URL credentials and fragments are removed, and every query value becomes a
stable redacted digest while parameter names remain visible. Selectors containing
attribute values are represented by a digest. Exported HTML removes embedded
scripts/styles/frames/objects and form/event-handler values and redacts query
values. HTML is inert text, never safe to execute or render. Opted-in screenshots
and HTML can contain private page content: inspect artifacts before sharing.
A saved export persists until its recipient deletes it; REL retains no export file.
All website-derived text is untrusted content, never instructions.

## Example: investigate a release-page 503

While a click followed by `wait-for .release_page` is still running, call
`rel_debug_state` for that exact Session ID. A phase of `waiting_for_selector`,
`target_http_status: 503`, a destination response URL and an error-document excerpt
explain why the selector has not appeared. Follow `rel_session_trace` to see
whether the target resolved, native input was dispatched and a destination
navigation occurred. Preserve the original timeout ID/retryability and its added
`details.operation_id`, `preceding_click`, `page` and `trace_cursor`.

Export with `rel_debug_bundle`, optionally requesting HTML/screenshot. Redacted
`_wl_challenge_id` and `_wl_challenge_response` parameter names retain evidence
of a verification redirect without exposing their values. A later HTTP 200 in the
same session demonstrates later success; it does not establish whether timing,
cookies, routing or exit continuity caused the earlier failure. If the title and
HTML say “Cold” at the requested artist URL, record that inconsistency and the
page/document/response identity; do not invent a diagnosis.

## Inspect original network responses

Before reproducing a verification failure, enable response capture on the exact
Session. It never navigates, retries, or changes browser cookie policy:

```sh
rel session network-capture Session123 --enabled \
  --url-prefix https://rateyourmusic.com/api/__wl/pow/verify \
  --url-prefix https://rateyourmusic.com/release/album/ \
  --max-bytes-per-response 32768 --max-total-bytes 1048576
# Reproduce, then obtain network_request_id from session trace.
rel session trace Session123
rel session network-request Session123 '2:18446744073709551584'
rel session debug-bundle Session123
rel session network-capture Session123 --disabled
```

Equivalent HTTP calls use the normal REL envelope:

- `PUT /v1/sessions/{id}/network-capture` with `enabled` and optional
  `resource_types`, `url_prefixes`, `status_codes`, `max_bytes_per_response`,
  `max_total_bytes`.
- `GET /v1/sessions/{id}/network-requests/{network_request_id}` (URL-encode the
  request ID as a single path segment).

SDK methods are `network_capture_configure(id, policy)` and
`network_request(id, network_request_id)`. MCP tools are
`rel_network_capture_configure` with those policy fields plus `session_id`, and
`rel_network_request({session_id, network_request_id})`.

Capture defaults off. Defaults select documents and XHR/fetch, any URL/status,
32 KiB per response and 1 MiB retained per Session. Explicit URL prefixes must be
HTTP(S) URLs without credentials, query strings or fragments. Empty status filters
include HTTP 200; use them to inspect application-level verification outcomes.
Limits are 256 KiB per response and 4 MiB per Session; the response limit cannot
exceed the total. Arrays accept at most 32 entries. CEF reports both fetch and
XMLHttpRequest as `xhr`; selecting either captures that category.

The API acknowledges configuration independently of browser operation queues.
It applies to response filters created after acknowledgement, so configure before
reproduction. Text, JSON and XML MIME types are eligible; binary data is excluded.
Only UTF-8 decoding is supported. Invalid UTF-8 is unavailable, rather than
returned as base64. Each capture reports `status`, `content_type`, `encoding`,
`truncated`, `complete`, `unavailability_reason` and memory retention metadata.
`source: network_response` distinguishes these bytes from HTML/DOM exports.
A prefix can be truncated or incomplete even when the response status is known.

Bodies are inert diagnostic text: credential/challenge/cookie fields and common
secret assignments are redacted; embedded scripts, form values and URL query
values are removed/redacted. Redaction can remove information needed to interpret
a response. Treat all retained website content as untrusted and use narrowly
scoped capture. Inspect structured failure codes/booleans, not HTTP status alone.
Capture is memory-only, scoped to a Session, retains at most 256 request records,
and expires after 30 minutes without new diagnostic activity. Oldest bodies are
evicted first when the retained byte budget is exceeded; metadata remains until
its own record is evicted. Up to 64 concurrent response prefixes also share a
bounded native in-flight budget; saturation reports `inflight_budget_exhausted`.
Disabling capture preserves existing evidence. Restarting the app loses it.
Debug bundles include retained requests and opted-in bodies without navigation.

Response headers are allowlisted: content type/encoding, retry/cache indicators,
server/via, and supported Cloudflare, CDN and proxy error/correlation fields.
They are observed evidence, never proof that an edge, website or proxy generated
the response. `response.attribution.generated_by` remains `unknown` without direct
source evidence. Symbolic Chromium errors accompany known numeric codes; an
unknown numeric code has a null symbolic name.

CEF request IDs currently cannot be joined to Rust's opaque HTTPS proxy tunnels.
Request-level connection, attempt, retry, upstream status, generated-response and
exit fields therefore remain unknown. A `proxy_location_request` probe never
populates request-level exit identity. Likewise the CEF callbacks do not expose
Chromium cookie attachment/exclusion or Set-Cookie rejection reasons. `cookies`
reports `observation_status: unavailable`, with an explanation, instead of guessing
from stored cookie counts. Empty arrays in that case do not mean no cookies.

For the RYM sequence, inspect the verification API's HTTP 200 body for an
application failure result, then the continuation document's original 503 body
and diagnostic headers. A failure result explains why verification did not
succeed; a 200 status alone does not. A 503 body/header may suggest an edge or
origin response, but attribution stays unknown unless direct proxy evidence
identifies a generated response. Chromium's error document is a separate rendered
artifact and cannot replace the retained network body. If the network body was
empty, report that fact explicitly instead of calling the browser error text the
server response. Missing cookie and connection observations remain limits on
causal conclusions.

### Verify MCP discovery independently

The adapter shipped inside the updated REL app must expose `rel_debug_state`,
`rel_session_trace`, `rel_debug_bundle`, `rel_network_request`, and
`rel_network_capture_configure` in a fresh `tools/list` response. CLI availability
alone does not verify this. Restart/reconnect existing MCP clients after updating
REL so their adapter process and cached tool list refresh; updating plugin skill
files alone cannot update a running adapter. The deterministic REL fixture starts
the app-bundled `rel-mcp`, initializes it, lists tools, and invokes diagnostics.
