---
name: rel-google
description: Search google.com through REL with native browser identity, explicit query and locale, and verifiable result links. Does not cover other Google apps or unrelated search engines.
---

# Google in REL

## Session selection

Read [REL browser session guidance](../rel-browser/references/domain-sessions.md)
for Project scope, Profile discovery, native actions, and failure handling.
Reuse an explicitly selected Session; otherwise create independent state in the
chosen Project using the named Profile and retain the returned `session_id`.
The settings below describe a local REL.app Profile inspected on 2026-10-27,
not built-in defaults or evidence that the site was tested. Recheck the current
Profile before use; do not hard-code local proxy aliases or browser versions.

## Profile strategy

The inspected `Google` Profile uses a direct connection, native identity
(`fingerprint_profile:null`), no ad blocking or image blocking, and no saved
cookies. Preserve those settings rather than importing another site's proxy or
fingerprint strategy. Reuse an explicitly selected signed-in Session when the
user needs its account state; the Profile name alone does not provide a login.

## Search

Keep the exact query, language/region, and any date or other filters with the
results. Use `rel_read` for rendered result links and snippets, and native
controls for consent, tabs, and filters. Separate ads, snippets, and generated
summaries from linked source evidence. Open the primary source before treating
a snippet as verified content; personalization and locale can alter rankings.
Bound pagination and cache already visited source links.

If Google displays unusual-traffic or verification UI, stop automated searches
and preserve the selected Session for user action. Do not add proxy rotation as
an automatic response. Google's [unusual-traffic guidance](https://support.google.com/websearch/answer/86640?hl=en)
notes that automated traffic and shared networks can trigger this condition.
