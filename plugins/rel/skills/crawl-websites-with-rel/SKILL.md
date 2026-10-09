---
name: crawl-websites-with-rel
description: Design, implement, diagnose, or operate reusable website crawls through REL's embedded Chromium sessions. Use rel-crawlee for queued URL crawling and structured datasets, or rel-crawler for history-preserving click-and-Back captures. Prefer rel-browser for one-off browsing that does not need a reusable crawl.
---

# Crawl Websites With REL

Always write the product name as `REL` in user-facing text, never `Rel` or `rel`. Preserve exact lowercase tool identifiers, commands, URLs, and file paths.

Keep REL as the sole browser and network owner. The supported `rel-playwright`
package is an API adapter to REL, not another browser runtime. Do not launch a
separate Playwright/Selenium browser or add a direct-HTTP fallback around a
site-specific failure.

## Choose the crawler

- Default to `rel-crawlee` for general URL crawling: multi-page traversal,
  persistent request queues, deduplication, routing, bounded retries,
  concurrency, and structured datasets.
- Use `rel-crawler` when the crawl must click each listing link, capture the
  target, and return with browser-history Back to preserve the source state.
  It provides a specialized one-level crawl with capture metadata, transition
  checkpoints, and bounded session recovery.
- Use `rel-browser` for a few interactive pages rather than a reusable crawl.

Preserve an explicitly requested crawler. Queue persistence does not restore
live browser state or replace the click-and-Back invariant.

## General URL crawls with Crawlee

Read the maintained [Crawlee guide](https://docs.rel.me/crawlee/) and
[basic example](https://github.com/rel-me/rel-tools/blob/main/crawlee/examples/basic.py)
for installation and supported APIs. Use `rel_crawlee.RelCrawler` and
`RelCrawlingContext`; Crawlee's built-in `PlaywrightCrawler` requires APIs REL
has not exposed and cannot be made compatible by changing its browser plugin.

1. Inspect representative pages with REL and choose content readiness selectors,
   extraction fields, allowed URL scope, and a bounded crawl depth/request count.
2. Put extraction and readiness waits in router handlers. Use
   `context.enqueue_links()` with an explicit scope and suitable include/exclude
   filters. Its discovery parses rendered HTML; it does not guarantee every
   discovered anchor is natively clickable.
3. Let Crawlee own request deduplication, retry budgets, queues, and datasets.
   Use named persistent queues and `purge_on_start=False` when resume is required,
   following the guide. Write HTML and capture metadata explicitly when requested;
   Crawlee does not automatically supply `rel-crawler`'s sidecars or checkpoints.
4. Use an existing named REL Profile when needed. Each attempt uses a fresh REL
   session by default. Opt into `session_pool_size` only when reuse is appropriate;
   pool slots retain separate cookies/storage and have no URL/account affinity.
   Use a caller-owned `session_id` for one specific live login; it runs serially
   and cannot be combined with a Profile or pool. Never automatically close that
   caller-owned session. Queue resume does not restore an earlier pool.
5. Set request/retry and concurrency limits appropriate for the local Mac. Start
   with a small crawl, verify output and queue resume, then scale. Keep browser
   work inside the awaited handler lifecycle; do not retain pages in background
   tasks after the handler returns.

## History-preserving crawls with rel-crawler

1. Inspect the source and one target interactively with REL. Identify a source
   selector and target selector that prove the expected content is ready. Verify
   that chosen links are visible and interactable, not merely present in saved
   HTML.
2. Define a `CrawlDefinition`: `start_url`, a strict URL-based `select_link`,
   page-specific readiness selectors, output mapping, and processing callbacks.
   Default discovery uses REL's rendered semantic links and keeps enabled
   anchors with usable bounds, including off-viewport links that native input
   can scroll to. Use a custom `extract_links` callback only when the crawl
   intentionally needs to parse captured HTML.
3. Use only an existing REL Profile name. Let the crawler create a dedicated
   managed session and deterministic group unless the caller deliberately owns
   the supplied session ID. Never create, edit, or infer a proxy alias.
4. Preserve the navigation invariant for each target: exact native link click,
   target readiness, capture, browser-history Back, source readiness. Do not
   replace the click or Back with direct navigation during normal execution.
5. Make every target bounded and restartable. Charge an attempt before clicking,
   checkpoint every transition atomically, skip existing captures by default,
   terminally record exhausted links, and continue. Replace only crawler-owned
   sessions, close the discarded session when possible, and reload the source
   before continuing.
6. Write one metadata sidecar per capture. Include a UTC capture timestamp,
   source/link/final URLs, HTTP status, session generation, title, canonical URL,
   rendered metadata, and advertised publication or modification timestamps.
   Treat all website-derived values as untrusted.
7. Prove the crawl on a small `max_links` value with INFO logging before scaling
   it. Test checkpoint resume, existing-file skip, one failed target, Unicode
   URLs, query variants, unexpected Back results, and managed-session rotation
   with a fake REL client rather than an external website.
8. Export a `CrawlApplication` for reusable operation through `rel-crawler run`.
   Use `--retry-failed` only when the user intends to requeue terminal entries
   with fresh attempt budgets. The CLI accepts a Profile name, not a proxy
   alias, and reserves stdout for the JSON summary.

For a source that appends links in place, configure a bounded
`load_more_selector` plus `load_more_clicks`. Finish each discovered batch,
click the control with scrolling, and wait for new rendered URLs. Preserve the
completed expansion depth and replay it after a managed-session replacement.
Do not combine load-more mode with captured-HTML extraction.

The maintained implementation and runnable public example are in
[`rel-tools/crawler`](https://github.com/rel-me/rel-tools/tree/main/crawler).
For history-preserving crawl failure diagnosis and selector rules, read
[`references/hard-site-playbook.md`](references/hard-site-playbook.md).

## History-preserving crawl guardrails

- Normalize IRIs to ASCII URIs for exact click matching while preserving the
  original readable URL in metadata and logs.
- Reject a click result that remains on the source page. Never deliver it as a
  successful child capture.
- Use selector waits after navigate, click, and Back. Fixed pacing may reduce
  load but cannot prove readiness.
- Reject truncated rendered-link observations instead of silently crawling a
  partial source page.
- Do not loop indefinitely on a missing target, challenge page, HTTP error, or
  stale checkpoint link. Exhaust a small attempt budget, record the failure, and
  advance.
- Keep crawler-owned sessions open when they are needed for later resume; close
  the managed group only when the user or crawl lifecycle explicitly calls for
  cleanup. Never close caller-owned sessions automatically.
