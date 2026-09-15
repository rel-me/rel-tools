# Crawlee integration

`rel-crawlee` runs Crawlee **1.10.0** through REL's visible Chromium sessions.
Crawlee owns the request queue, deduplication, router, retries, concurrency,
statistics, and datasets. REL owns browser sessions, native input, cookies,
Profile configuration, and proxy routing.

The integration extends Crawlee's `BasicCrawler` with `RelCrawler` and
`RelCrawlingContext`. Crawlee's built-in `PlaywrightCrawler` requires browser,
JavaScript, cookie, and network APIs outside REL's supported surface. Changing
its browser plugin alone does not make it compatible. See
[Crawlee's extension guide](https://crawlee.dev/python/docs/guides/extending-crawlee).

## Install

Requirements: macOS with REL running, Python 3.11 or newer, and a saved REL
Profile if you need custom browser settings or proxy routing.

Install both packages from the same checkout:

```sh
git clone https://github.com/rel-me/rel-tools.git
cd rel-tools
python3 -m venv .venv
.venv/bin/python -m pip install -e playwright -e crawlee
```

The adapter requires `rel-playwright>=0.1.1,<0.2`, which drains in-flight RPC
workers before propagating cancellation. There is no Playwright browser download
or `playwright install` step. Crawlee is pinned because the adapter uses its
context pipeline and protected enqueue helpers; upgrade the pin only after
running the compatibility tests.

## Crawl and save data

```python
import asyncio

from rel_crawlee import RelCrawler, RelCrawlingContext


async def main():
    crawler = RelCrawler(max_requests_per_crawl=10, max_request_retries=2)

    @crawler.router.default_handler
    async def handle(context: RelCrawlingContext):
        await context.push_data({
            "url": context.page.url,
            "title": await context.page.title(),
            "status": context.response.status,
        })
        await context.enqueue_links(strategy="same-hostname")

    await crawler.run(["https://example.com/"])
    await crawler.export_data("results.json")


asyncio.run(main())
```

`context.page` exposes the async [REL Playwright surface](PLAYWRIGHT.md),
including CSS locators, screenshots, navigation, native clicks, and form input.
`context.response` contains main-frame URL and status metadata, without response
headers or body access. Use `page.content()` for rendered HTML. Status `0` means
REL did not provide a main-frame HTTP status.

`extract_links()` reads fresh rendered HTML, handles relative URLs and the first
`<base href>`, and returns Crawlee Requests. `enqueue_links()` submits those
requests through Crawlee. Both support selector, attribute, label, user data,
request transformation, include/exclude patterns, limit, explicit base URL, and
Crawlee's four enqueue strategies. Same-domain matching uses the bundled Public
Suffix List without making a metadata download. Duplicate request keys are
collapsed before the extraction limit is applied; the queue also deduplicates
across pages.

Links redirected outside their enqueue scope are skipped before the handler.
Crawlee's `max_crawl_depth`, named queues, dataset helpers, error handlers, and
request retry limits remain available.

## Profiles, sessions, and concurrency

```python
from crawlee import ConcurrencySettings
from rel_crawlee import RelCrawler

crawler = RelCrawler(
    profile="Research",
    concurrency_settings=ConcurrencySettings(
        min_concurrency=1, desired_concurrency=2, max_concurrency=2,
    ),
)
```

By default, each request attempt gets a fresh, isolated REL Session copied from
that Profile. Omitting `profile` uses REL's configured default. Concurrency defaults
to one and is capped by Crawlee's `max_concurrency`. Choose capacity appropriate
for the local Mac and its available REL sessions.

For a crawl that must retain live login state between requests:

```python
crawler = RelCrawler(session_id="Session12")
```

A supplied session runs serially, is never deleted by the adapter, and cannot
be combined with `profile`. Its cookies and storage remain in REL.
`context.session` and `context.proxy_info` are `None`: the integration disables
Crawlee's separate session pool and cookie/proxy management. The REL session ID
is available as `context.page.session_id`.

A supplied session is reserved across active RelCrawler instances in the same
Python process. Give that session exclusive use during the run; this lease does
not lock out the REL UI, other clients, or other Python processes. Do not start
unawaited background tasks that retain `context.page` after a handler returns.

In fresh-session mode, adapter-created sessions are deleted after each attempt,
including its error handlers.
`persist=True` retains them for inspection, including sessions from failed
attempts. `group="my-crawl"` makes those retained sessions easy to find and close.
REL Profile snapshots do not synchronize storage between newly created sessions.

## Optional session pool

Set `session_pool_size` to opt into a bounded pool of REL Sessions:

```python
crawler = RelCrawler(
    profile="Research",
    session_pool_size=2,
    max_requests_per_session=100,
    concurrency_settings=ConcurrencySettings(
        desired_concurrency=2, max_concurrency=2,
    ),
)
```

The pool creates sessions lazily and reuses healthy pages across requests. Each
slot has its own cookie jar and browser storage. A request holds its slot until
its handler, error handlers, and in-flight RPC workers have finished. Excess
workers wait for a slot. The pool closes all its sessions when the run ends.

A failed navigation, handler error, cancellation, explicitly closed page, or the
request-use limit retires a session. Its replacement is created only after
cleanup succeeds. A failed delete keeps occupying its slot, so cleanup failures
cannot cause the pool to exceed its capacity. `max_requests_per_session` defaults
to 100 and counts attempts. Crawlee still owns the request retry budget.

Pooling is incompatible with `session_id` and `persist=True`. Keep the default
`session_pool_size=None` when each attempt must start from an independent
Profile snapshot. The pool preserves cookies, storage, history, and page settings
within each slot; it does not clear them between requests, synchronize them across
slots, or provide URL/account affinity. Use a caller-owned `session_id` for a
serial workflow that needs one specific live login. Do not create additional
pages from a pooled page's browser/context or retain pages in background tasks.

Each `run()` starts a new pool. Queue resume does not restore an earlier pool's
live browser state.

## Timing metrics

`crawler.metrics` returns a frozen `RelCrawlMetrics` snapshot during or after a
run. It resets when a new run starts and retains no per-request history, URLs, or
credentials. To save it:

```python
from dataclasses import asdict

await crawler.run(["https://example.com/"])
print(asdict(crawler.metrics))
```

| Field | Meaning |
| --- | --- |
| `requests_started` | Accepted request attempts entering the REL pipeline, including retries |
| `sessions_created` | Successfully created adapter-owned pages/sessions, excluding borrowed sessions |
| `session_reuses` | Requests that reuse an existing pooled page |
| `sessions_retired` | Distinct pooled sessions retired due to failure, closure, or the use limit |
| `session_wait_seconds` | Time spent obtaining a pool slot |
| `session_acquire_seconds` | Session setup or reuse, excluding queue wait |
| `navigation_seconds` | REL navigation and main-frame status validation |
| `handler_seconds` | Request-handler pipeline time, including extraction; excludes error handlers |
| `link_extraction_seconds` | `extract_links()` work, including rendered-HTML capture and filtering |
| `cleanup_seconds` | Session cleanup attempts, including retries and pool shutdown |

Durations use a monotonic clock and are summed across attempts. Concurrent work
and nested phases overlap: handler time includes link extraction, and acquisition
can include cleanup of a previously failed slot. Do not add these durations to
estimate wall-clock runtime. Use Crawlee's runtime statistics or a timer around
`run()` for total elapsed time. Navigation and handler failures also contribute
the time spent before the failure.

## Compare fresh and pooled sessions

The benchmark example crawls Books to Scrape's homepage and nine product pages
with the selected saved Profile, using concurrency two in both modes. By default
it runs two paired rounds in fresh/pooled then pooled/fresh order, with separate
processes and storage directories. It checks identical extracted records,
Profile/proxy assignments, request completion, and session cleanup.

```sh
.venv/bin/python crawlee/examples/benchmark.py \
  --rel-base-url http://127.0.0.1:17319/v1 \
  --profile Research \
  --output /absolute/path/to/new-benchmark-results
```

Use the explicit worktree endpoint for Debug tests. `--pairs` changes the number
of paired rounds. Results include individual reports, logs, timing metrics, and
`summary.json`. This measures the combined effect of browser reuse, caching, the
proxy, and the target site. It does not establish performance on other sites or
under sustained load.

## Errors and cancellation

Crawlee owns request retries. Retryable REL errors and handler failures consume
`max_request_retries`. Nonretryable REL errors and unsupported operations fail
without retrying. HTTP 4xx statuses fail without retries; HTTP 5xx statuses use
the request retry budget. Automatic block detection, session rotation, and
`Retry-After` behavior are not provided.

`navigation_timeout` accepts a positive `datetime.timedelta` and defaults to
30 seconds. `request_handler_timeout` uses Crawlee's handler timeout separately.
Navigation uses REL's main-frame readiness contract; Playwright `networkidle`
semantics are unavailable.

On timeout or cancellation, the async adapter waits for any already-running RPC
worker before closing or reusing its session. Cancellation may therefore finish
after the requested deadline, up to the operation's transport timeout. Failed
cleanup is surfaced if it cannot complete during crawler shutdown. Error
handlers can inspect pages after navigation succeeded and before cleanup.

## Explicit limits

Only GET navigation without custom request headers, payloads, or Crawlee request
session IDs is supported. Browser configuration comes from REL Profiles.

The adapter rejects custom HTTP clients, Crawlee proxy/session pools, automatic
block retries, and HTTP error-status overrides. `send_request`, HTTP streaming,
and automatic robots.txt fetching are unavailable; they fail explicitly rather
than using an HTTP client outside REL. Arbitrary JavaScript, request interception,
Playwright browser launch options, and the other [REL limits](PLAYWRIGHT.md#explicit-limits)
also apply. Configure crawl scope and allowed URLs before starting the crawl.

## Resume a queue

Use a named Crawlee queue and retain its storage directory:

```python
from crawlee.configuration import Configuration
from crawlee.storages import RequestQueue

configuration = Configuration(storage_dir="./crawl-storage", purge_on_start=False)
queue = await RequestQueue.open(name="catalog", configuration=configuration)
crawler = RelCrawler(configuration=configuration, request_manager=queue)
# Register your router handlers, then run. On restart, open the same named queue.
await crawler.run(["https://example.com/"])
```

Queue persistence is independent of REL browser state. Fresh-session retries
replay navigation; attach a supplied session when live browser state must persist.
Handlers and dataset writes should tolerate replay after process interruption.

## Test

From the repository root:

```sh
.venv/bin/python -m unittest discover -s crawlee/tests -v
.venv/bin/python -m unittest discover -s playwright/tests -v
```

The suite runs real Crawlee against a fake loopback REL agent. It covers queue
resume, link extraction, routing, datasets, retries, ownership, concurrency,
timeouts, pool retirement/capacity, timing snapshots, and cancellation without
accessing an installed app.

For maintainers, the explicit runtime verifier creates local HTML and proxy
fixtures. First build/open the worktree's RELDebug and verify its staged build ID.
Pass its bundled CLI and its assigned endpoint; the verifier requires Debug
health and the exact build ID before creating uniquely grouped test resources:

```sh
.venv/bin/python crawlee/tests/verify_runtime.py \
  --rel-cli /absolute/path/to/rel/dist/RELDebug.app/Contents/Resources/rel \
  --rel-base-url http://127.0.0.1:WORKTREE_PORT/v1 \
  --expected-build-id STAGED_BUILD_ID
```

The runtime verifier checks Profile proxy routing, isolated cookies, borrowed
session persistence, pooled cookie isolation/reuse, redirects, link enqueueing,
native form actions, retries,
cancellation, cleanup, and queue resume. It removes its own resources afterward.
