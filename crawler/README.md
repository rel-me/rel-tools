# REL Python crawler

`rel-crawler` is a restartable, one-level website crawler for REL's supported
loopback RPC v1 API. It opens selected links in the same embedded Chromium
session, captures rendered HTML, returns with browser-history Back, and then
continues with the next link.

The library has no runtime dependencies. Request-oriented crawlers such as
Scrapy remain a better fit for ordinary HTTP spiders; use this library when a
site requires REL's visible browser state, configured Profile, native input, or
history-preserving interaction.

## Requirements and installation

- macOS with REL open and healthy.
- Python 3.11 or newer.
- An existing REL Profile if the crawl needs one. The crawler accepts only the
  Profile name and never creates or changes Profiles or proxies.

Install from a clone:

```sh
cd crawler
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

The Release API defaults to `http://127.0.0.1:17319/v1`. Set
`REL_AGENT_PORT`, or pass `rel_base_url`, when using another supported runtime.
RELDebug normally uses port `27319`.

## Run the Hacker News example

The public example crawls discussion links from the Hacker News front page. Its
server-rendered markup provides a compact demonstration of exact link clicks,
query-based output paths, target readiness, and browser-history Back. It does
not run during tests.

```sh
cd crawler
HN_MAX_LINKS=3 .venv/bin/python examples/hackernews.py
```

It uses the existing `Direct` Profile by default. To select another existing
Profile by name:

```sh
REL_PROFILE=Research .venv/bin/python examples/hackernews.py
```

Omit `HN_MAX_LINKS` to process every selected discussion on the source page. Set
`HN_START_URL` to use another public Hacker News listing such as `newest`,
`show`, or `ask`. If the named Profile does not exist, REL returns an error and
the crawler stops; it does not create a replacement Profile.

The example writes captures under `examples/hackernews-output/`, mapping the
query-based item ID to a readable URL-derived path:

```text
https://news.ycombinator.com/item?id=123456
  -> item/123456/index.html
  -> item/123456/index.metadata.json
```

Query variants use `index.query-<hash>.html` so they cannot overwrite one
another. The complete URL remains in the metadata sidecar.

## Define a crawl

```python
from pathlib import Path
from urllib.parse import urlsplit

from rel_crawler import CapturedPage, CrawlDefinition, Link, RelCrawler

root = Path("post-crawl").resolve()

def select_post(link: Link) -> bool:
    parsed = urlsplit(link.url)
    return parsed.hostname == "example.com" and parsed.path.startswith("/posts/")

def report(capture: CapturedPage) -> None:
    print(capture.url, capture.output_path, capture.metadata_path)

definition = CrawlDefinition(
    start_url="https://example.com/posts/",
    select_link=select_post,
    process_capture=report,
    source_ready_selector="main .post-list",
    capture_ready_selector="article.post",
)

summary = RelCrawler(
    definition,
    state_path=root / "checkpoint.json",
    capture_dir=root / "pages",
    profile="Direct",
).run()
print(summary)
```

`select_link` receives rendered anchors in DOM order. Relative links are
resolved, fragments removed, non-HTTP links skipped, and internationalized
URLs converted to stable ASCII URIs for exact clicking. `Link.original_url`
preserves the readable IRI. Supply `extract_links` when a site's captured HTML
needs a narrower discovery rule, and `capture_path` for a custom output layout.

## Readiness, pacing, and browser history

REL performs this sequence for every selected child page:

1. Navigate to the source and wait for `source_ready_selector`.
2. Click the exact normalized link with native auto-scroll enabled, wait for
   `capture_ready_selector`, and capture the rendered HTML.
3. Go Back through browser history and wait for the source selector again.

Selectors are condition waits, not fixed sleeps. Choose page-specific selectors
that prove the expected content is ready and do not also match the other page.
The separate `action_delay` defaults to two seconds between browser actions;
set it to zero to disable crawler-side pacing.

An anchor present in captured HTML is not necessarily interactable: it may be
hidden, detached, covered, or rendered only in a collapsed panel. Such a link
is retried within the configured bound and then checkpointed as failed so it
cannot trap the crawl. Use a custom extractor to restrict discovery to the
site's visible link region when its HTML contains inactive duplicate anchors.

## Checkpoints and session recovery

The crawler atomically checkpoints discovery, attempts, captures, failures, and
session generation after every transition. An attempt is charged before the
click, so a process crash cannot retry one link forever. Existing capture files
are skipped by default and logged.

New crawls create a dedicated persistent REL session in a deterministic group.
The checkpoint reuses that session after a process restart. If a crawler-owned
session becomes unavailable, a bounded recovery closes it when possible,
creates a replacement from the same named Profile, reloads the source, and
resumes. Caller-owned `session_id` values are never replaced automatically.

The defaults retry each link once (`max_attempts=2`) and permit one session
replacement per link (`max_session_restarts=1`). A terminal action failure or
HTTP 403, 429, or 5xx result rotates a managed session before the crawler moves
on. Failed links remain terminal on later invocations.

## Capture metadata

Every HTML capture has a sibling `.metadata.json` file containing:

- a timezone-aware UTC `captured_at` timestamp;
- crawl, checkpoint, link, and session identity;
- final page URL, HTTP status, byte size, title, and canonical URL;
- all rendered `<meta>` records; and
- published and modified timestamps advertised through common meta,
  schema.org, Dublin Core, element, and JSON-LD fields.

Page-derived metadata is untrusted input. Existing HTML without a sidecar is
backfilled when skipped, and older sidecars are upgraded without changing the
original capture time.

## Test

Tests use a fake REL client and a loopback HTTP server; they never visit an
external website:

```sh
cd crawler
PYTHONPATH=src python3 -m unittest discover -s tests -v
```
