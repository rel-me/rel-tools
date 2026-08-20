---
name: crawl-websites-with-rel
description: Design, implement, diagnose, or operate restartable website crawlers through REL's embedded Chromium sessions. Use for interaction-heavy or difficult sites that require rendered-link discovery, native clicking, page-readiness waits, browser-history Back, named Profiles, HTML and metadata captures, checkpoints, bounded retries, or session recovery. Prefer rel-browser for one-off browsing that does not need a reusable crawl.
---

# Crawl Websites With REL

Use the public `rel-crawler` Python package when the outcome is a reusable crawl,
captured files, or resumable batch work. Keep REL as the sole browser and network
owner; do not add Playwright, Selenium, or a direct-HTTP fallback around a
site-specific failure.

## Workflow

1. Inspect the source and one target interactively with REL. Identify a source
   selector and target selector that prove the expected content is ready. Verify
   that chosen links are visible and interactable, not merely present in saved
   HTML.
2. Define a `CrawlDefinition`: `start_url`, a strict URL-based `select_link`,
   page-specific readiness selectors, output mapping, and processing callbacks.
   Use a custom `extract_links` callback when inactive or hidden duplicate
   anchors appear outside the visible content region.
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

The maintained implementation and runnable public example are in
[`rel-tools/crawler`](https://github.com/rel-me/rel-tools/tree/main/crawler).
For hard-site failure diagnosis and selector rules, read
[`references/hard-site-playbook.md`](references/hard-site-playbook.md).

## Guardrails

- Normalize IRIs to ASCII URIs for exact click matching while preserving the
  original readable URL in metadata and logs.
- Reject a click result that remains on the source page. Never deliver it as a
  successful child capture.
- Use selector waits after navigate, click, and Back. Fixed pacing may reduce
  load but cannot prove readiness.
- Do not loop indefinitely on a missing target, challenge page, HTTP error, or
  stale checkpoint link. Exhaust a small attempt budget, record the failure, and
  advance.
- Keep crawler-owned sessions open when they are needed for later resume; close
  the managed group only when the user or crawl lifecycle explicitly calls for
  cleanup. Never close caller-owned sessions automatically.
