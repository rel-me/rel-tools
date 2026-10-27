---
name: rel-duckduckgo
description: Search duckduckgo.com through REL using its saved Profile and rendered result links with explicit query and regional settings. Does not apply to other search engines.
---

# DuckDuckGo in REL

## Session selection

Read [REL browser session guidance](../rel-browser/references/domain-sessions.md)
for Project scope, Profile discovery, native actions, and failure handling.
Reuse an explicitly selected Session; otherwise create independent state in the
chosen Project using the named Profile and retain the returned `session_id`.
The settings below describe a local REL.app Profile inspected on 2026-10-27,
not built-in defaults or evidence that the site was tested. Recheck the current
Profile before use; do not hard-code local proxy aliases or browser versions.

## Profile strategy

The inspected `DuckDuckGo` Profile uses an ISP proxy, ad blocking, no image
blocking, no fingerprint overrides, and no saved cookies. Use the saved Profile
rather than inheriting Google or Reddit configuration.

## Search

Retain the exact query, region, Safe Search, time filter, and result mode.
Read rendered results with `rel_read`, separating sponsored entries from organic
links. Follow original source URLs for verification instead of relying only on
snippets or answer panels. Use native controls for more results, with a bounded
number of expansions and URL deduplication. Record partial coverage if the
result list cannot be expanded. Preserve diagnostics on a block and stop
repeated retries; do not apply Reddit cookie refresh or IP rotation automatically.
