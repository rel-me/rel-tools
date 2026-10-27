---
name: rel-loopnet
description: Read loopnet.com commercial-property searches and listing details in REL using its saved Profile and explicit geographic and property filters. Does not cover other property sites.
---

# LoopNet in REL

## Session selection

Read [REL browser session guidance](../rel-browser/references/domain-sessions.md)
for Project scope, Profile discovery, native actions, and failure handling.
Reuse an explicitly selected Session; otherwise create independent state in the
chosen Project using the named Profile and retain the returned `session_id`.
The settings below describe a local REL.app Profile inspected on 2026-10-27,
not built-in defaults or evidence that the site was tested. Recheck the current
Profile before use; do not hard-code local proxy aliases or browser versions.

## Profile strategy

The inspected `LoopNet` Profile uses an ISP proxy, no ad blocking or image
blocking, laptop viewport, no fingerprint overrides, and no saved cookies.
Start with the named Profile; a Profile does not confer access to gated listings.

## Commercial listings

Record market, sale/lease mode, property type, price/rent range, area units,
and visible filters. Use rendered result cards and native pagination or map
controls; keep the selected geographic area explicit. Capture listing URLs,
address, displayed availability, area, and asking terms with their units and
capture time. Distinguish annual from monthly rent and per-area rates from total
prices; retain ambiguous or withheld values as displayed rather than guessing.

Follow selected listings in the same Session. Treat login gates, contact-only
pricing, removed records, and missing details as limits on available evidence.
Do not submit broker-contact forms without a request. Bound result expansion,
deduplicate by listing URL/ID, and preserve diagnostics on blocked navigation.
Do not apply Reddit's cookie/replacement/rotating-IP procedure here.
