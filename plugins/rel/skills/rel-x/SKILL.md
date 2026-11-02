---
name: rel-x
description: Read x.com and twitter.com in REL with the X Profile, verified account state, rendered search filters, and bounded timeline expansion. Does not apply to other social networks.
---

# X in REL

## Session selection

Read [REL browser session guidance](../rel-browser/references/domain-sessions.md)
for Project scope, Profile discovery, native actions, and failure handling.
Reuse an explicitly selected Session; otherwise create independent state in the
chosen Project using the named Profile and retain the returned `session_id`.
The settings below describe a local REL.app Profile inspected on 2026-10-27,
not built-in defaults or evidence that the site was tested. Recheck the current
Profile before use; do not hard-code local proxy aliases or browser versions.

## Profile strategy

The inspected `X` Profile uses a direct connection, ad blocking, no image
blocking, laptop viewport, no fingerprint overrides, and a saved cookie
snapshot. Verify the visible login state; saved cookies may expire. Reuse the
user's selected signed-in Session when account context matters. If login or
MFA is needed, let the user complete it in REL and continue in that exact Session.

## Search, timelines, and threads

Record the query, account, search tab (such as Latest or Top), and any date
constraints. Use `rel_read` for rendered content and `rel_observe` plus native
actions for filters, scrolling, and replies. Timelines may render only a moving
window: accumulate post permalinks as you scroll and deduplicate by post ID.
Bound expansions and report the observed interval and coverage.

Open a post permalink for thread context. Distinguish original text, quoted
posts, replies, reposts, and displayed timestamps. Do not infer a complete
thread or search history from one viewport. Login walls, unavailable posts,
and rate limits are incomplete results, not evidence that no posts exist.
Preserve diagnostics and stop on repeated blocking; do not borrow Reddit's
fresh-cookie replacement or rotating-IP procedure. Posting, likes, follows,
and messages require a user request for those actions.
