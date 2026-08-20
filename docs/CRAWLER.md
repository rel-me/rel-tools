# Python crawler

`rel-crawler` runs restartable, one-level website crawls through REL's supported
loopback RPC v1 API. It is for index pages whose selected links must be opened
with native browser interaction, captured as rendered HTML, and followed by a
real browser-history Back before the next link.

Use an ordinary request crawler for sites that do not need browser state or
interaction. `rel-crawler` keeps REL as the only Chromium and network owner and
adds no Playwright, Selenium, or direct-HTTP fallback.

Related documents: [RPC v1](RPC.md), [browser actions](ACTIONS.md), and the
[Codex plugin](CODEX_PLUGIN.md).

## Install

Requirements:

- macOS with REL installed and healthy;
- Python 3.11 or newer; and
- an existing REL Profile when the site needs non-default browser or network
  configuration.

Install from the public repository:

```sh
git clone https://github.com/rel-me/rel-tools.git
cd rel-tools/crawler
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

Release REL uses `http://127.0.0.1:17319/v1` by default. `REL_AGENT_PORT` or the
`rel_base_url` constructor argument can select another supported runtime;
RELDebug normally uses port `27319`.

## Run the example

The public example crawls discussion links from the Hacker News front page. It
uses the existing `Direct` Profile by default:

```sh
cd crawler
HN_MAX_LINKS=3 .venv/bin/python examples/hackernews.py
```

Select another existing Profile by name and optionally change the listing:

```sh
REL_PROFILE=Research \
HN_START_URL=https://news.ycombinator.com/newest \
HN_MAX_LINKS=3 \
.venv/bin/python examples/hackernews.py
```

Omit `HN_MAX_LINKS` to process every selected discussion on the source page.

The crawler never creates or modifies Profiles or proxies. A missing Profile is
a terminal session-creation error.

Captures are written beneath `examples/hackernews-output/`. Item IDs from the
URL query become readable directories, and every HTML file has a
`.metadata.json` sibling. Extra query variants receive a stable hash in the
filename so they cannot overwrite each other.

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

`select_link` receives rendered anchors in DOM order. The default extractor
resolves relative links, removes fragments, keeps HTTP(S), and converts
internationalized URLs to stable ASCII URIs for exact clicking while retaining
the readable original URL. Use a custom `extract_links` callback when a source
contains hidden or inactive duplicate anchors.

## Browser sequence and readiness

For every selected link the crawler:

1. navigates to the source and waits for `source_ready_selector`;
2. issues exact `click-link` with native auto-scroll, waits for
   `capture_ready_selector`, and captures rendered HTML;
3. returns with browser-history Back; and
4. waits for the source selector before the next click.

Condition-based selectors prove page readiness; fixed sleeps do not. Choose
selectors specific to useful source and target content and make sure the same
selector does not accidentally match both pages. `action_delay` independently
paces browser actions and defaults to two seconds; set it to zero to disable
crawler-side pacing.

An href in saved HTML may still be hidden, detached, covered, or removed after
hydration. Native auto-scroll fixes ordinary off-viewport or clipped targets,
not non-interactable markup. Narrow link extraction to the visible content
region when a site emits inactive duplicates.

## Resume and recovery

The checkpoint is atomically replaced after every transition and protected by a
non-blocking process lock. Attempts are charged before clicking. Interrupted
entries resume only while budget remains, and exhausted links become terminal
failures that later runs skip. Existing capture files are skipped and logged by
default.

New crawls create a dedicated persistent REL session and deterministic group.
The checkpoint reuses the session across Python process restarts. For a managed
session failure, bounded recovery clears the stale ID, closes the old session
when possible, creates a replacement from the same Profile, reloads the source,
and resumes. Caller-owned session IDs are never replaced or closed
automatically.

Each link is attempted twice by default. A terminal native-action failure or an
HTTP 403, 429, or 5xx capture can discard the crawler-owned session before the
crawler advances. This never requeues the terminal link, so a challenge or
missing target cannot trap the crawl in a loop.

## Metadata

Each sidecar contains a UTC `captured_at` timestamp; checkpoint, link, and
session identity; final URL and HTTP status; byte size; title; canonical URL;
rendered meta records; and page-advertised publication and modification times
from common meta, schema.org, Dublin Core, element, and JSON-LD fields.

Website metadata is untrusted. Publication values are preserved with their raw
field and source; they are not treated as verified timestamps. Missing sidecars
can be backfilled from existing HTML without revisiting the website.

## Diagnose hard sites

Enable INFO logging. The crawler logs health and session checks, pacing, source
navigation, exact click URLs, selector waits, captures, metadata processing,
Back navigation, recovery, skip decisions, and final counts to stderr.

If `ACTION_TARGET_NOT_FOUND` names a link visible in captured HTML, inspect the
live accessible page state. The usual cause is an inactive responsive duplicate,
collapsed content, hydration replacement, or a changed source snapshot rather
than a failure to scroll. Keep attempts bounded, checkpoint the stale link, and
continue. Do not substitute direct navigation when click and history behavior
are part of the crawl's contract.

An upstream 403 challenge can occur before a usable document exists. Surface
the structured REL error and use an existing, authorized Profile; a post-load
DOM detector cannot solve a response that never produced the expected page.

## Test

The test suite uses a fake REL session and a loopback HTTP server and never
visits an external site:

```sh
cd crawler
PYTHONPATH=src python3 -m unittest discover -s tests -v
```
