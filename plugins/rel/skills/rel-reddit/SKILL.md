---
name: rel-reddit
description: Browse reddit.com in REL with authenticated cookie snapshots, independent Sessions, and bounded recovery from expired login or rate limits. Applies only to reddit.com and its subdomains; do not apply its cookie or routing workflow to other sites.
---

# Reddit in REL

## Session selection

Read [REL browser session guidance](../rel-browser/references/domain-sessions.md)
for Project scope, Profile discovery, native actions, and failure handling.
Reuse an explicitly selected Session; otherwise create independent state in the
chosen Project using the named Profile and retain the returned `session_id`.
The settings below describe a local REL.app Profile inspected on 2026-10-27,
not built-in defaults or evidence that the site was tested. Recheck the current
Profile before use; do not hard-code local proxy aliases or browser versions.

## Profile and login

The inspected `Reddit` Profile uses an ISP proxy, no ad blocking or image
blocking, no fingerprint overrides, and a saved cookie snapshot. A snapshot can
expire; `includes_cookies:true` does not prove a valid Reddit login.

1. Reuse a user-designated Reddit Session or create one from `Reddit` in the
   requested Project with `lifetime:{"type":"indefinite"}` for manual login and
   export (or keep an inactivity Session alive with `rel_ping_session`). Open
   `https://www.reddit.com/login/` in REL. Have the user
   complete login, MFA, and any interactive verification in that Session; do
   not ask for their password or print cookies.
2. Verify the account UI and one requested Reddit resource in that same Session.
   Keep this working login Session as the source; do not close it during recovery.
3. Open that Session's **Site Data** cookie controls and choose **Export…**.
   Save a private, absolute path such as `/private/path/reddit-fresh.cookies`.
   Export includes all Session cookies, including filtered-out domains. Prefer
   a dedicated Reddit Session to avoid including unrelated login data.
4. Use REL's versioned `.cookies` JSON export. It is plaintext login material;
   keep owner-only permissions and never commit, upload, print, or include its
   contents in diagnostics. Netscape files, raw Chromium databases, and a
   `.relprofile` settings transfer are not interchangeable with this file.

## Create with the fresh file

In REL.app, choose **File → Create Session from Profile**, select the intended
Project and `Reddit` Profile, keep browser state independent, and choose
**Starting cookies → Choose File…** with the freshly exported file. REL imports
it before the first page; a selected file replaces Profile cookies while
preserving saved passwords. Invalid files stop creation. Cookie files do not
include local storage or passwords, so verify login on the returned Session.
Use `rel_list_sessions` to discover its exact ID and Project before browsing.

For repeated MCP creation, edit the `Reddit` Profile's **Advanced → Starting
cookies** to select the file and save. Alternatively, **Copy Cookies from** can
snapshot the working login Session without a plaintext export. Then:

```json
{"project_id":"<selected-project-id>","profile":"Reddit"}
```

Pass this to `rel_create_session` and use its returned `session_id`. Saved
Profile cookies are a snapshot, not a live link to the source Session or file.
Updating them affects future Sessions only. Current CLI/MCP creation has no
cookie-file parameter; do not invent `--cookies-file`, `cookies_file`, cookie
injection tools, or a reset endpoint. If the app step cannot be performed,
report that capability gap instead of claiming fresh cookies were applied.

## 429, expired login, and routing

On HTTP 429, preserve the exact Session's debug state/trace, requested and final
URLs, status, and request ID. Pause requests, honor `Retry-After` when available,
and reduce concurrency and request frequency. There is no established safe
request count: a 429 does not prove that cookies expired or that the IP is blocked.

If the login has expired, refresh it in the working source Session and export a
new snapshot. After the rate-limit wait, create one independent replacement
Session with that snapshot as above and verify the original resource once.
This is replacement, not a public reset operation. Keep the original Session
until diagnostics and any needed state are preserved; close only a disposable
Session owned by this workflow. A second 429/block ends automatic recovery;
checkpoint the unfinished work and report it rather than looping replacements.

The requesting operator reports Reddit IP blocks after repeated requests.
For sustained authorized Reddit work, recommend a configured rotating proxy
option rather than assuming one fixed exit will remain usable. Discover available
aliases with `rel_list_proxies`. MCP creation inherits the Profile route and
has no proxy override argument. Select the route in the app/Profile, or use the
supported CLI `rel session create --project-id PROJECT_ID --profile Reddit
--proxy ALIAS` for a new Session after saving fresh cookies to the Profile.
Rotation depends on the provider configuration; creating a Session or selecting
an alias does not prove a new exit IP. Preserve a stable route while logging in
and verifying cookies, and use deliberate batch boundaries for any configured
rotation. Fresh cookies or a different IP cannot guarantee access or cancel an
account/server rate limit. Do not extend this Reddit routing recommendation to
other domains automatically.

Read requested posts and comment threads with `rel_read`; use observations and
native actions for expansion. Check subreddit, post permalink, sort, and visible
comment depth. A collapsed or partially loaded thread is not a complete export.
