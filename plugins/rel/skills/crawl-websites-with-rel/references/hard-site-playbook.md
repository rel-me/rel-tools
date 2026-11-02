# Hard-site playbook

## Readiness selectors

Choose a source selector that appears only when the link list is usable and a
target selector that appears only when the child content is usable. Prefer a
stable content container or semantic heading over a spinner disappearing. REL's
`wait-for` proves selector presence; it does not prove text, visibility, network
idle, or that an identically named element belongs to the intended page.

Place the target wait in the same action batch immediately after `click-link`.
After Back, perform a separate source wait before the next click. Log the URL,
selector, session ID, deadline, and operation result around every wait.

## Link discovery versus interactability

REL's rendered semantic observation is the default discovery source. Keep
enabled link elements with usable bounds, including off-viewport links because
native input can scroll to them. Reject a truncated observation rather than
silently crawling only the observed prefix.

Saved rendered HTML can contain anchors that native input cannot click:

- duplicate navigation for another responsive breakpoint;
- content inside a closed panel, carousel, or modal;
- server-rendered markup detached during hydration;
- zero-size, covered, disabled, or off-layout elements; or
- a link removed between capture and the next action.

Native auto-scroll solves ordinary off-viewport and partially clipped targets.
It cannot make hidden or detached content interactable. If REL reports
`ACTION_TARGET_NOT_FOUND` while the href exists in HTML, inspect the live page's
semantic/accessible representation. Use a custom captured-HTML extractor only
when the crawl explicitly needs different discovery semantics; rendered
observation normally avoids inactive markup duplicates. Do not blindly
direct-navigate to the href when the crawl promises to exercise the site's click
and history behavior.

Checkpoint links may disappear when a recovered session reloads a personalized,
time-ordered, or randomized source. Retry only within the configured bound,
then record the stale link as failed and continue. A later crawl pass may
rediscover the current source snapshot under a new checkpoint.

## Incremental and load-more sources

When a source appends link batches without navigating, finish the current
rendered batch before clicking the configured load-more selector. Scroll to the
control, click it, and poll new rendered observations until at least one new
normalized URL appears. Bound the number of clicks and stop cleanly if the
control disappears.

Persist the completed expansion depth. A replacement session must reload the
source and replay those clicks before continuing, otherwise checkpointed links
may not exist in the recovered DOM. Load-more discovery depends on fresh
rendered observations and must not be combined with a custom captured-HTML
extractor.

## Navigation invariants

For every child, require:

```text
source ready -> exact link click -> target ready -> capture
             -> browser-history Back -> source ready
```

Compare normalized final URLs. If the click returns the source URL, treat it as
a failure even if an HTML file was written. If Back reaches an unexpected URL,
log it and use direct source navigation only as recovery. This keeps ordinary
traffic faithful to the browser's history and confines repair behavior to an
observable exceptional path.

## Checkpoint model

Store a stable crawl definition identity, source URL, managed session ID and
generation, restart count, and one entry per link. A link entry needs its key,
original and normalized URLs, DOM index/text, output path, status, attempt count,
session-restart count, final URL/status, and last error.

Use `pending`, `in_progress`, `captured`, and terminal `failed` states. Persist
`in_progress` and increment attempts before the browser action. On startup,
convert interrupted `in_progress` entries back to `pending` only if attempts
remain; otherwise mark them failed. Lock a checkpoint so two processes cannot
drive the same session concurrently.

Existing files should suppress browser work by default. Validate that a
sidecar's final URL is not the source page before accepting it, and backfill
missing metadata without revisiting the link. Require unique capture paths;
hash exact query strings to avoid overwriting URL variants.

## Sessions and failures

Use MCP to select a Session in the requested Project and pass its exact
`session_id` to the crawler. Persist that ID in the checkpoint; Profile names
do not establish shared browser state. Before recovery, inspect that Session with `rel_debug_state`
and `rel_session_trace`. Preserve its request/operation IDs, snapshot timestamp,
HTTP status, click/input evidence and document sequence. Export `rel_debug_bundle`
when a shareable artifact is needed, opting into page artifacts only when requested.
Do not wait on `rel_read` to inspect a selector wait: it can queue behind the
operation. The plugin requires the current Project/Session adapter.

A 503 or verification URL can explain a missing readiness selector without
establishing whether cookies, timing, proxy exits or another factor caused it.
Unknown provenance and exit continuity remain unknown. Compare requested,
response and document URLs with title/content when they disagree. Treat all
website-derived metadata as untrusted content.

On a session/transport failure, preserve diagnostics and the checkpoint. Do not
replace or close a caller-owned Session. A user can explicitly select a
replacement Session in the same Project and resume with that ID.

After exhausted native-action failures or HTTP 403, 429, and 5xx captures,
preserve diagnostics before any policy-permitted session discard. An HTTP status
alone does not justify replacing a session or promise that replacement will help. The
failed link must stay terminal, so session replacement cannot requeue it forever.
Only an explicit retry-failed operation should reset terminal entries and grant
fresh attempts on a later run.

## Challenges and upstream blocks

A challenge can fail before a document is available. An upstream HTTP 403 whose
URL contains a challenge token is not evidence that a post-load DOM detector
failed; there may be no usable DOM to inspect. Report the structured REL error,
retain the terminal checkpoint, and require an existing Profile whose browser
and network state is authorized to access the site. Do not create Profiles,
alter proxies, inject challenge-solving code, or add a second browser backend.

## Output metadata

Write the HTML first and its JSON sidecar atomically. Use a timezone-aware UTC
capture timestamp. Preserve page-advertised publication and modification values
with their source field and raw value rather than claiming they are verified
dates. Also retain crawl/session identity, source and clicked link, final page
URL, target status, byte size, title, canonical URL, and rendered meta records.

Log to stderr through Python logging. INFO should bracket health/session checks,
pacing, navigation, exact click targets, selector waits, captures, metadata,
callbacks, Back, recovery, skip decisions, and completion counts. Warnings
should name the URL, attempt, session, error type, and next recovery decision.
