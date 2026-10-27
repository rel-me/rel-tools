---
name: rel-craigslist
description: Read craigslist.org regional searches and postings with REL using the Craigslist Profile and explicit city and category scope. Does not apply to other classified sites.
---

# Craigslist in REL

## Session selection

Read [REL browser session guidance](../rel-browser/references/domain-sessions.md)
for Project scope, Profile discovery, native actions, and failure handling.
Reuse an explicitly selected Session; otherwise create independent state in the
chosen Project using the named Profile and retain the returned `session_id`.
The settings below describe a local REL.app Profile inspected on 2026-10-27,
not built-in defaults or evidence that the site was tested. Recheck the current
Profile before use; do not hard-code local proxy aliases or browser versions.

## Profile strategy

The inspected `Craigslist` Profile uses an ISP proxy, no ad blocking or image
blocking, and no fingerprint overrides. Start with that saved configuration;
verify the regional hostname before reading results.

## Regional search and postings

Use the requested city/region subdomain, category, query, and price/other filters.
Keep the region explicit when following nearby-area results. Read the rendered
listing and follow selected post URLs, retaining post ID, URL, displayed date,
location, and asking price. Deduplicate reposts only when the evidence supports
it; do not merge distinct listings solely because their titles match.

Stop on removed/expired postings and label them unavailable rather than treating
the error page as listing content. Bound pagination and avoid repeatedly
fetching completed posts. Reply/contact controls can reveal personal data or
start communication; use them only when requested. Do not send inquiries or
post ads as part of a read-only research task. Preserve blocks and diagnostics;
do not apply Reddit's cookie or rotating-IP procedure here.
