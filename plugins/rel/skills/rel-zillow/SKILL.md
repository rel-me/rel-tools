---
name: rel-zillow
description: Read Zillow searches and property details through REL using a Zillow Profile, rendered results, and explicit map or filter state. Applies to zillow.com, not general real-estate browsing.
---

# Zillow in REL

## Session selection

Read [REL browser session guidance](../rel-browser/references/domain-sessions.md)
for Project scope, Profile discovery, native actions, and failure handling.
Reuse an explicitly selected Session; otherwise create independent state in the
chosen Project using the named Profile and retain the returned `session_id`.
The settings below describe a local REL.app Profile inspected on 2026-10-27,
not built-in defaults or evidence that the site was tested. Recheck the current
Profile before use; do not hard-code local proxy aliases or browser versions.

## Profile strategy

The inspected `Zillow` Profile uses an ISP proxy, ad blocking, images blocked
above 100 KB, laptop viewport, and no fingerprint overrides. Reuse the saved
configuration first. If photos, maps, or controls appear incomplete, inspect
visually and consider an explicit Session-only image/adblock change before
concluding a listing is missing. Do not silently rewrite the saved Profile.

## Search and details

Record location, buy/rent mode, price range, beds, and other requested filters.
Use native filter controls and inspect the rendered result list. Keep the map
viewport/search area explicit; moving the map can change the result set.
Capture canonical property URLs and read selected details in the same Session.
Label price, availability, and estimates as displayed at capture time. Deduplicate
by property URL or visible listing identifier; distinguish sponsored cards from
property records. Bound pagination or scrolling and state result coverage.

If a verification control or block replaces the results, preserve diagnostics
and ask for user completion in the same Session when needed. Do not apply the
Reddit cookie/replacement/rotating-IP workflow to Zillow.
