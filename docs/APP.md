# REL app

The macOS app owns REL's embedded Chromium runtime, persistent Sessions, browser
Profiles, and AI chat. Keep REL running whenever local clients or scheduled
prompts need to use it.

REL's embedded browser includes the Clark Browser and ungoogled-Chromium patch
sets. The privacy layer removes built-in Google service integrations and
blocks substituted background-service destinations. Websites you visit can
still load Google resources, and you can open Google pages explicitly.

REL honors Chromium's standard `Referrer-Policy` behavior. Cross-origin requests
send only the referring origin by default; explicit `no-referrer` policies still
suppress it. This allows CDNs that require an embedding origin to serve images
without disabling Cross-Origin-Resource-Policy enforcement.

REL configures Sessions to retain cookies, site storage, and saved logins when
it quits. The privacy layer does not enable automatic clearing on exit. This
preserves website login state; it does not enable Chromium's password manager
or guarantee that every sign-in flow is compatible.

The patch sets also remove Safe Browsing malware/download reputation checks,
automatic extension updates, browser Google account synchronization, and
Google-backed Web Push. Third-party cookie restrictions and disabled FedCM can
affect federated sign-in. The current ungoogled download patch also removes
macOS quarantine metadata. These are retained source-policy tradeoffs, not
just telemetry removal.

## Session viewport presets

Use **Session Viewport** beside the address field to choose **Desktop 1440w**, **Wide Laptop 1280w**,
**Laptop 1024w**, **Tablet 768w**, or **Mobile 320w**. Each preset sets the actual page width in
CSS pixels and follows the available window height. The page is centered in a
scrollable canvas; narrower windows keep the selected width and allow horizontal
scrolling. These presets resize the viewport without changing the Session's
browser identity or emulating a device.

The selection is saved separately for each Session and survives restarting REL.
Choose **Fit Window** to use the available space, or **App Default** to inherit
the viewport configured in Settings. Background Sessions retain their selected
width and last visible height.

The bottom panel floats over the page. Opening, resizing, and expanding it leave
the page viewport unchanged.

## Quitting REL

Closing the main window leaves REL running. Use **REL → Quit REL** or **⌘Q**
to exit. REL saves workspace state and flushes cookies before closing its
browsers. Cookie saves overlap in small batches to reduce the wait when many
Sessions are open. Quit retains its four-second deadline for asynchronous
cleanup; it does not wait indefinitely for a stalled browser.

## Start on Login

Enable **Settings → General → Startup → Start on Login** to open REL
automatically when you log in to your Mac. REL uses the native macOS login item
registration for the app. Turn the setting off to remove that registration.

If macOS requires approval, click **Open Login Items Settings…** and allow REL.
The setting refreshes from macOS when you return to REL, including changes made
in System Settings. Registration errors appear below the Startup controls.

## Update channels

Choose **Settings → General → Updates → Update Channel** to select which
releases REL offers:

- **Regular** receives regular releases and is the default.
- **Beta** also receives preview releases.
- **Dev** receives development releases as well as Beta and regular releases.

The selection is saved across app restarts. Changing channels changes which
future updates are eligible; it does not downgrade an installed version.

## AI provider presets

In **Model Providers → Add**, choose **Fireworks**, **Amazon Bedrock**,
or **Baseten** to fill in an OpenAI-compatible endpoint. Enter that service's API
key, then add the provider. Keys are stored in macOS Keychain. REL discovers the
available models for the Chat picker.

| Preset | Default endpoint |
| --- | --- |
| Fireworks | `https://api.fireworks.ai/inference/v1` |
| Amazon Bedrock | `https://bedrock-mantle.us-east-1.api.aws/v1` |
| Baseten | `https://inference.baseten.co/v1` |

For Amazon Bedrock, change `us-east-1` to your AWS region as needed and use an
Amazon Bedrock API key. AWS access key IDs and secret access keys are not accepted
by this preset. Model availability depends on the endpoint, region, and account.
All three presets use the existing `openai-compatible` provider kind and Chat
Completions API. Endpoints remain editable for custom deployments.

See the provider setup references for [Fireworks](https://docs.fireworks.ai/tools-sdks/openai-compatibility),
[Amazon Bedrock](https://docs.aws.amazon.com/bedrock/latest/userguide/inference-chat-completions-mantle.html),
and [Baseten](https://docs.baseten.co/reference/inference-api/overview).

### Jev browser decisions

Choose **TypeSafe AI** as the provider, select a paired LLM in provider setup,
then choose the **Jev + paired LLM** selection in the Chat model picker.
Enter your TypeSafe API key when adding the provider. The model uses the
`jev-latest` alias; its exported service name is `TypeSafe AI`.

## Session and workspace errors

Click the warning icon in the main toolbar to open **Session and Workspace
Errors**. The sheet shows session and workspace persistence errors separately,
with scrollable, selectable details. **Copy Details** copies both error messages.

For session errors, use **Refresh Sessions** to reload the session list, then
retry the failed action. **Open Settings** lets you review session limits and
the default Profile. Refresh is available while the local agent is running and
no session refresh or save is in progress.

**Save Current Workspace** requests a save of the current tabs and layout for
the next launch; it does not restore a previous layout. When the agent rejects a
save as invalid, REL preserves the current draft and allows another save after
the problem is corrected. If the save outcome is uncertain or the workspace
revision has changed, REL blocks further writes until you restart. The button
cannot bypass that protection. **Report a Bug** opens the
report form for further help.

In Debug builds, **Debug → Error Recovery** can trigger a session error, a
workspace error, or both. These simulated errors appear in the same toolbar
warning and details sheet without changing sessions, files, or permissions.
Use **Refresh Sessions** and **Save Current Workspace** to exercise recovery.

## Keeping and deleting Sessions

Close the REL window or quit REL to keep Sessions and their saved logins for
next time. Session deletion cannot be undone.

**Delete Session…** in a Session's context menu and the Session tab's close
button show a confirmation before deleting anything. **Close Session…** (⌘W)
shows the same confirmation when no browser popup is open; when a popup is
open, it closes only that popup. The confirmation names the Session and warns
that deletion removes its cookies, saved logins, saved passwords, and other
browser data. **Cancel** is the default action and keeps the Session intact.

**Settings → General → Browser Data → Delete All Sessions…** also requires
confirmation and warns that all Sessions and their browser data will be deleted.
These confirmations apply to app controls; API and CLI deletion operations
remain explicit destructive operations without an interactive confirmation.

## Database migration and recovery

REL validates its local database before starting normal service. Supported
schema versions 3 through 15 are supported, with older schemas upgraded to schema 15. Before any upgrade or
repair, REL creates a consistent SQLite snapshot including committed WAL data
under `Data/Recovery/<run-id>/original.sqlite3` in its Application Support
folder. Debug builds use their isolated worktree Application Support folder.
Legacy root-level databases and schemas older than version 3 are not imported.

Migration runs against a separate candidate. If a supported migration or data
validation fails, REL rebuilds the current schema and copies valid records.
Invalid optional descriptive metadata can be cleared independently. Records
that cannot be converted safely remain in the original snapshot and are omitted
from the active database. Sessions and Profiles referencing an unrecoverable
proxy are withheld as well; recovery never changes that assignment to a direct
connection. Invalid fingerprint settings withhold the affected record rather
than silently changing its browser identity. Valid sessions remain available.

REL checks types, application decoding, schema structure, and references before
committing the candidate. Activation is one SQLite transaction: interruption
leaves the original database or the complete upgraded database. A concurrent
writer causes recovery to stop so its changes are not overwritten. Restarting
retries from the current data. A successful recovery is not repeated on every
launch.

When records or fields need review, REL displays a recovery notice. Choose
**Show Report**, or **Settings → Service → Show Recovery Report**, to locate
`report.json`. It lists retained counts and affected tables, record IDs, fields,
and reasons. Original values remain in the snapshot. The database's recovery
history identifies committed runs; a folder left by an interrupted attempt is
not proof that its candidate was activated. Recovery does not access or export
Keychain credentials.

Chromium session folders, cookies, and saved logins are preserved. A durable
`Data/Recovery/preserve-browser-storage` marker prevents automatic orphan-folder
cleanup after recovery, including on subsequent launches. Existing session IDs
are reserved so new sessions cannot inherit withheld sessions' storage. Keep the
marker and original snapshot while reviewing recovery. Quarantined records are
not automatically restored; use the original snapshot for diagnosis and careful
repair. Recovery does not manufacture missing records or browser data.

Storage, permission, locking, unreadable database pages, and backup failures
stop recovery without resetting the database. A database from a newer REL build
requires updating REL and is never downgraded. The app remains open with the
service error and **Retry Local Service**. Correct the reported condition and
retry. The service only becomes ready after validation; the supervisor allows
startup backup and recovery to finish instead of restarting them after its
normal health-poll threshold.

## Anonymous diagnostics

On the first normal startup, REL asks whether to share anonymous app usage and
reliability events. Diagnostics remain off unless you select **Share
Diagnostics**. You can change the choice later under **REL → Settings… →
General → Diagnostics**.

The fixed event schema includes app and macOS versions, launch and update
outcomes, agent availability, and the number of open Sessions. Events use a
random identifier that lasts only for the current app launch. They do not
include an account or persistent installation ID, URLs, page content, prompts,
Profile names, credentials, or local logs. Delivery is best effort and failed
events are not stored for retry.

## Free and Pro

REL Free does not require registration. It includes one Session at a time, one
scheduled prompt, one custom Profile, and one configured AI model provider.
Proxies cannot be created, configured, assigned, or used on the Free plan.

REL Pro costs $20 as a single upfront payment for one year of access. It does
not renew automatically. Register the license in **REL → Settings… → Plan** to
use proxies and remove the Free plan limits. If Pro registration expires or is
removed, REL preserves existing Sessions and configuration instead of deleting
them. Free prevents additional creation beyond its limits, and any stored proxy
assignment runs as a direct connection until Pro access is restored.

You can also enter a `REL-PRO-...` promo code in the same Plan field when one
has been provided to you. Promo codes grant one, two, or three calendar months
of REL Pro without a checkout or payment method. Each trial can be redeemed on
one REL installation, and a campaign code stops working after its configured
number of redemptions.

REL displays the trial end date in Plan settings. It checks the grant with REL
at most once per day and supports up to seven days offline, without extending
access beyond that end date. At expiry, REL automatically returns to Free and
keeps existing Sessions and configuration under the Free plan limits described
above.

## Profiles and Sessions

A **Profile** is a reusable template for a new Session. Profiles select the
connection, network filters, and any browser data that should be copied when a
Session is created. A **Session** is the persistent browser created from that
template; later Profile changes do not modify existing Sessions.

Manage saved configurations in **Profiles**. There are no built-in Profiles.
Profiles can use a configured proxy and imported cookies or passwords. The Profiles
list includes a **Browser Identity** column showing Private, Custom Privacy,
or Native.

In **New Profile**, choose **Proxy → New Proxy…** to add a proxy without leaving
the profile draft. Saving selects the new proxy automatically. Cancelling returns
to the draft without changing its proxy selection. A saved proxy remains available
in Proxies even if you later cancel the profile.

**Create Session**, **New Session** (Command-T), and the session tab bar’s plus
button create a session immediately using the configured default Profile, or
Custom defaults when none is set. You can change AdBlock, image blocking, Proxy,
and Browser Identity afterward. Changing Browser Identity shows a banner so you can reload when ready.
Browser data is copied or imported rather than switched as a setting.

Cookies and saved passwords can be imported while Chrome or another supported
Chromium browser is running. REL reads temporary copies of the database and its
recovery journals, including committed changes, without modifying the source
browser's data. Newly created REL sessions initialize their cookie database before
the imported records are written. The temporary copies are removed after import. If the source
files keep changing during capture, REL asks you to retry the import.

Use the session toolbar's **Proxy** menu to select a saved proxy, or **None** for
a direct connection. Saved proxies from earlier REL versions remain selectable
without recreating them or enabling provider-specific sticky sessions.
A proxy can enable either Oxylabs or Bright Data session handling. Changing
its active provider renews the assigned sessions' sticky IDs; editing targeting
within the same provider preserves them. Unrelated edits and transfers retain
saved targeting settings for disabled providers.
REL upgrades stored proxy settings automatically when the updated app starts.
The upgrade preserves saved proxies, sessions, sticky IDs, and login data; it
does not require recreating proxies or importing them again. Earlier app versions
cannot open the upgraded database.

The toolbar **(+) → New Session from Profile** submenu lists saved Profiles.
Selecting a Profile creates a session immediately with its settings and browser
data. The submenu appears only when saved Profiles exist.

Use **File → Create Session from Profile** (Option-Command-T) to choose settings
before creation or copy a saved Profile’s browser data. This form starts with
**Custom** and shows the Profile picker only
when saved Profiles exist. Selecting one loads its configuration into the form;
all settings remain editable and changes apply only to the new Session. AdBlock,
Browser Identity, Proxy, Image Blocking, and Browser Data share one section
with equal-height setting rows. Choosing **Custom Privacy** in Create Session
opens a separate editor; **Use Identity** applies it to the draft and **Cancel**
preserves the previous identity. **Edit** reopens a custom identity.
**Show Config** below the section opens a read-only popover with the session
settings and all browser privacy controls, including controls left native. Proxy
uses the same dropdown style as the other settings.
New Custom drafts start with **Allow all images**. **Proxy → New Proxy…** creates
and selects a proxy without losing the draft. Cancelling keeps the current selection.

**Settings → General → Default Profile** controls immediate session creation
in the app and clients that omit a profile, including CLI, SDK, MCP, and Python. With no saved default, they use Custom:
direct networking, AdBlock on, all images allowed, and Private. The creation
form uses its explicit settings and browser-data choice instead. **None** does
not inherit another Profile’s browser data. Renaming a saved default preserves
its selection; deleting it requires choosing another default or Custom.
Changing this preference restarts the local agent and preserves existing Sessions.

Schedules that referenced former built-in Profiles keep their settings as explicit
Custom session configurations. New schedules can create a Custom session without
requiring a saved Profile.

## Browser identity

New Sessions use the form’s **Browser Identity**. New Custom configurations
and Profile drafts use **Private**, which enables all
seven supported privacy controls. In Profile forms, **Show** to the left of its
value opens a read-only popover without expanding the form. Create Session uses
**Show Config** below the main section instead. In Profile forms, Browser Identity is in the
main section. Choose **New Browser Identity…** in its dropdown to customize the
current settings in a separate editor. **Use Identity** applies them to the draft
as **Custom Privacy**; **Cancel** leaves the previous identity unchanged. These
settings are saved with the Profile. Use **Edit** beside Custom Privacy to change
them later. Starting from **Native** leaves every override off, so you can enable
only the controls you need. **Native** uses Chromium's native values.

For identities with overrides, every creation path generates a fresh numeric
readback seed for the Session, then keeps it stable for that Session. Profile edits apply to future Sessions.
Use a Session's tab menu to change its identity; saving recreates only that
Session's Chromium context and returns it to the same page.

**Private** uses **Automatic** for language and locale. REL selects the default
language for the proxy's configured country using macOS locale data and keeps
that country as the locale's region. Bright Data country targeting and Oxylabs
country or US state targeting supply this location. For example, Germany uses
`de-DE`, Canada uses `en-CA`, and Belgium uses `nl-BE`. Without a configured
location, REL uses your macOS preferred language.

The proxy editor's **Detect Exit Locale** option is on by default for new proxies.
It uses the detected exit country instead of the configured target and the
detected IANA timezone instead of the saved profile timezone. The timezone control must be
enabled. For Automatic language or enabled timezone controls, REL requests
`https://ipwho.is/` through the browser session's agent-owned proxy before preparing
the browser. IPWHOIS.io sees the proxy's exit IP. Successful results are cached for up to 30 minutes per session and upstream
route; a provider session rotation changes that route. A failed lookup reports an
error rather than using a different locale or timezone. The option is preserved
in proxy and profile transfers; older transfers import with detection off.
Existing saved proxies keep their current setting, including an explicit off choice.

A country does not identify every resident's preferred language. In Custom
Privacy, choose **Custom** in the Language row to set an explicit locale such as
`fr-CA`. Custom takes precedence over automatic language selection. The timezone
control can still trigger a lookup and use the detected timezone independently.
Disabling the language control keeps native Chromium language and locale.
The former proxy-level manual locale is retained in storage and API responses,
but Automatic now uses country targeting or exit detection.

For HTTP clients, proxy create/update accepts `detect_exit_locale` (boolean,
default `true` on create and preserved when omitted on update). Proxy responses
include that setting. Session responses include `proxy_country` (configured ISO
country or null) and `proxy_detect_exit_locale`. With detection enabled,
`GET /v1/sessions/{id}/proxy-location` returns
`{ "country": "DE", "timezone": "Europe/Berlin" }` in the standard response envelope, or an error if detection is disabled, the session has
no proxy, or the lookup fails. This lookup does not write a language to the proxy.

Privacy controls cover graphics, audio, device surfaces, language and locale,
time zone, network information, and the CPU thread count reported to pages.
When Network Information protection is enabled, JavaScript RTT/downlink and
opted-in HTTP RTT/Downlink hints use the same rounded session values.
Network measurements are not exposed through those hints. Disabling the control
retains native estimates. Sites must still opt in to receive the hints, and
Permissions Policy can suppress them. These reported values do not change actual
connection speed or route traffic through a proxy.

Chromium generates the User-Agent in every mode with its product version reduced
to `MAJOR.0.0.0` (for example, `Chrome/152.0.0.0`). The engine supplies its native
brand list and client hints; these are not editable. High-entropy client hints
can still expose the engine’s full version when requested by a site.

Graphics protection changes Canvas and WebGL readbacks together with the graphics identity and
makes WebGPU unavailable. Text geometry, native input, and other unlisted
surfaces remain native.

Native Chromium uses the same patched privacy layer. Its WebRTC default also
restricts non-proxied UDP connections. Audio protection makes small changes to
AudioBuffer's live sample arrays, which can also affect later playback.

An identity profile is a compatibility tool, not an anonymity guarantee. Its
seed is stable across sites in that Session, so sites may still correlate
visits. Network identity is also separate: use a Session proxy when traffic
must leave through another route. Proxied Sessions prevent WebRTC from using a
non-proxied UDP route, but REL does not turn a direct Session into a VPN.

## Shared asset cache

Enable **Reuse cacheable assets across sessions** in **REL → Settings… → Cache**
to reuse HTTP resources between Sessions. This is off by default, with a 512 MiB
size limit. You can change the limit or clear the shared cache there.

Any resource type can qualify, including compressed resources and responses
without `Cache-Control: public`. Responses need an explicit fresh `max-age`,
`s-maxage`, or `Expires` lifetime. REL respects `private`, `no-store`, and
`no-cache`; requests carrying cookies or authorization and responses setting
cookies are excluded. Partial responses, downloads with Content-Disposition,
and bodies larger than 32 MiB after decoding are also excluded.

Direct Sessions share one cache partition. Proxy Sessions share only within
the same proxy alias. Cookies, site storage, and Session identity remain
separate. The shared cache reduces repeated downloads; it does not combine
Chromium renderer processes. Clearing private Session caches leaves the shared
cache intact, and clearing the shared cache leaves private Session data intact.

## Navigation feedback, errors, and retry

Back, Forward, submitted addresses, and link navigations show loading feedback
as soon as navigation starts. The address-bar indicator appears immediately,
and **Reload Page** becomes **Stop Loading**. The current page remains visible
until Chromium replaces it with the next document.

In **Settings → General → Browsing → Page Transition**, choose **Nothing** (the
default) to keep this behavior, or **Fade out** to fade the page away while the
next page loads. The new page appears when loading finishes; stopping restores
the visible page. The preference applies to open Sessions immediately and is
saved across launches. With macOS Reduce Motion enabled, Fade out hides the
page without animation. Loading feedback and Stop remain available in either
mode.

Choose **Stop Loading** to cancel the current load without pausing the Session's
network activity. If the new document has not committed, REL restores the
previous page's address and state. Once the new document has committed, Stop
leaves that document in place. A user-requested stop does not show a navigation
error. Stopping a load also cancels any active browser automation request in
that Session.

Navigation failures show a readable explanation and retain the original source
error. Proxy tunnel failures include the proxy name, upstream HTTP status line,
and available provider diagnostics such as `Proxy-Status` and Bright Data error
codes. For example, Bright Data's `403` / `policy_20000` restriction appears with
the provider's access-denied explanation instead of only Chromium's generic
connection error. Check the provider's policy or configuration before retrying
a persistent rejection.

Expand **Technical Details** for long diagnostics, or use **Copy Details** to
copy the explanation, full retained diagnostics, Chromium error, and requested
URL. Short errors are shown directly. Details remain selectable and the page
scrolls when needed. Credentials, authentication challenges, and cookies are
excluded from proxy diagnostics; retained text is bounded to 8,192 characters
with a truncation marker. Website-generated HTTP error documents remain visible
rather than being replaced by REL's failure page.

Submitting an address immediately makes it the Session's active URL. If the
page or proxy fails, the address field, Application panel, and **Try Again**
button refer to that request. After submitting a different address, refresh
retries the new URL even if it also fails. Typing without submitting does not
change the retry target.

Back and Forward include pages opened by website links in a new window or tab.
Back first walks through the new page's own history, then returns to its opener;
Forward revisits the retained page without reloading its document. Nested pages
use the same controls, with no separate Return button. Navigating to a new
address or opening another page after going Back discards the forward pages.
A website can still close its own popup and return to the opener.

Back and Forward also work with history entries created within the same page.
Submitting an address that only changes its `#fragment` also keeps the current
document available without waiting for a full page reload.

Each Session also preserves its root-page HTTP(S) Back/Forward history and
current position across restarts. Opening the saved page restores that history
without loading its earlier or later pages. Visiting a new page after going Back
discards the forward branch. Clearing the Session’s browsing data removes its
saved history. Popup history, form values, POST bodies, and scroll positions
are not restored across restarts.

Chromium's automatic retries keep the error visible until the page returns a
response. A browser startup failure can be retried with **Try Again**, refresh,
or a newly submitted address; REL recreates that Session's browser and keeps
the latest requested URL.

If AdBlock blocks the main page, REL shows **This Page Was Blocked** with the
requested URL and a filter explanation. Check **AdBlock** in the Session's
**Filters** panel before trying again; retrying with the same blocking rule still
blocks the page. Blocked scripts, images, or embedded frames remain filter log
events and do not mark the main page as failed.

### Proxy-provider AdBlock exclusions

In Sessions using a proxy, REL excludes known proxy-provider destinations and
their subdomains from AdBlock by default, including provider websites, APIs, gateways, and diagnostic URLs.
The maintained list covers Bright Data/Luminati, Oxylabs, Decodo/Smartproxy,
IPRoyal, Webshare, SOAX, and Rayobyte. For example, `geo.brdtest.com`,
`ip.oxylabs.io`, and `ip.decodo.com` can load with AdBlock enabled.

These exclusions apply only while a Session has a proxy configured, to main
pages and subresources, with cached or newly downloaded rules. Direct Sessions
use normal AdBlock rules. Removing a Session's proxy restores normal filtering;
assigning a proxy enables the exclusions again. Image blocking and image
size limits still apply. Unrelated requests from provider pages remain subject
to AdBlock, as do ordinary destinations reached through a proxy.

The provider-domain list is maintained with REL app updates. It does not discover every proxy domain
automatically; new provider domains need to be added to that list.

## Session logs

Open **Logs** in a Session's bottom panel to follow its activity. Logging runs
while the Session is active, even when the panel is closed, and works with both
direct and proxied connections.

- **Network → Requests** shows Chromium HTTP and HTTPS request results for pages,
  scripts, stylesheets, images, frames, and fetch/XHR traffic. Entries include
  the method, URL, HTTP status or failure, elapsed milliseconds, and received
  bytes. Redirects include their destination. Results appear when a request
  finishes, fails, or is canceled; an open stream appears when it ends.
- **Network → Filtered Requests** explains requests blocked by Session filters.
- **Chromium → Runtime** includes browser open/close, navigation starts, finishes
  and failures, Back, Forward, Reload, Stop, and network pause/resume activity.
- **Clients → Requests** includes browser operations and individual automation
  actions, with their completion or failure and elapsed time.

Chromium request and activity entries omit request/response bodies, headers,
entered text, URL credentials, and URL fragments. Query parameter names remain
visible with their values replaced by `REDACTED`. Proxy transport diagnostics
remain separate from Chromium request results, so a proxied request can have
both a transport entry and a browser result.

Use the category menu to filter the stream. **Clear Logs** clears only the
selected Session and live logging continues. Logs remain local to this app's
data directory.

### Log record schema

The log inspector, copied records, and local NDJSON logs use the same flat JSON
object. NDJSON contains one object per line. There is no `data` wrapper, nested
object, or array. Optional fields are omitted when unavailable, never written as
`null`. All names use `snake_case`.

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | string, required | Opaque record ID, suitable for deduplication. |
| `created_at` | integer, required | UTC Unix timestamp in seconds. |
| `category` | string, required | `agent`, `chromium`, `chromium.profile`, `network`, `network.filtered`, or `proxy`. |
| `level` | string, required | Severity, normally `info`, `warn`, or `error`; diagnostic sources can also emit `trace`, `debug`, `warning`, or `fault`. |
| `message` | string, required | Short human-readable summary. Use structured fields for filtering and analysis instead of parsing this text. |
| `session_id` | string | The Session associated with the event. Omitted for unscoped records. This is the only Session identity field; there is no `browser_profile_id` or `tab_name`. |
| `event` | string | Machine-readable event name, such as `navigation_started`, `browser_request`, `browser_action`, or `agent_request`. Unstructured diagnostics may omit it. |
| `url` | string | Destination associated with the event. |
| `method` | string | HTTP method. |
| `path` | string | Local API request path. |
| `page_id` | string | Page handle associated with an API request. |
| `group` | string | Session group associated with an API request. |
| `operation` | string | Browser operation or action, such as `navigate`, `click`, or `type`. |
| `request_id` | string | Request or action correlation ID. Interpret within its Session and event source. |
| `status` | string | Outcome, such as `completed`, `failed`, `canceled`, or `redirect`. |
| `status_code` | integer | HTTP status code, when available. |
| `error_code` | integer | Nonzero Chromium/CEF error code, when available. |
| `resource_type` | string | Chromium resource classification, such as `document`, `script`, `image`, or `xhr`. |
| `reason` | string | Filter reason, such as `adblock`. |
| `duration_ms` | integer | Elapsed milliseconds. Zero is a valid measurement. |
| `received_bytes` | integer | Received byte count reported by Chromium. Zero is a valid measurement. |
| `redirect_url` | string | Redirect destination. |

Event-specific fields appear only when relevant. Additional scalar fields
(strings, numbers, or booleans) may be added; consumers should tolerate them.
Event fields cannot overwrite the required fields or `session_id`.

Navigation example:

```json
{"id":"e57b6b74-170c-4fcd-a9bf-e96a9af98448","created_at":1788762428,"category":"chromium","level":"info","session_id":"Session78","event":"navigation_started","message":"Navigation started: about:","url":"about:"}
```

Request result example:

```json
{"id":"b37c10ef-a84c-4e11-9ad8-4f531e96eaad","created_at":1788762429,"category":"network","level":"info","session_id":"Session78","event":"browser_request","message":"GET https://example.com/: HTTP 200","method":"GET","url":"https://example.com/","resource_type":"document","request_id":"1:42","status":"completed","status_code":200,"duration_ms":42,"received_bytes":1024}
```

Activity messages use `Summary: URL` when a URL is present. Request messages
use `METHOD URL: result`; timing, size, resource type, and redirect destination
remain in their own fields. Browser URLs retain the redaction described above.
Non-HTTP(S) URLs are reduced to their scheme, such as `about:` or `data:`, so
inline document content is never included.

This format replaces the nested log schema. Existing nested records are not
converted or supported by the new readers.

## Site permissions

Website permissions are stored by origin inside each Session's isolated
Chromium profile. A request for location, notifications, microphone, camera,
or clipboard access shows a browser-attached prompt with **Not Now**, **Don't
Allow**, and **Allow**. Not Now saves no decision. Don't Allow remains denied,
and Allow is reported only after Chromium stores the real permission.

Open the Session tab menu and choose **Site Permissions** to inspect the current
site. **Revoke** returns one capability to Chromium's default prompt state for
that origin and Session. Decisions do not move to another Session. Before a
microphone or camera allow decision, device enumeration hides device labels and
stable IDs.

## Settings configuration transfers

In **Settings → Profiles, Proxies, Schedules, or Providers**, the glass button
group contains **Add (+)**, **Edit**, a divider, **Import (down arrow)**, and
**Export (up arrow)**. Select a row to enable export. Import opens a text editor with a **Paste** button to insert the clipboard
contents; export shows selectable text with a **Copy** button. No file picker is involved.
Imports create new records and remain subject to the plan's creation limits.
Existing records are not overwritten.

Profiles, schedules, and providers use a versioned JSON envelope:
`{"format":"rel.<kind>","version":1,"configuration":{...}}`. The kind is
`profile`, `schedule`, or `provider`. Export produces one line; pasted JSON may
include whitespace. Paste the complete object, without Markdown fences. JSON
input is limited to 1 MiB. Profile setups additionally accept version 2, as
described below. Other versions, mismatched kinds, malformed JSON,
and invalid configurations are rejected.

### Profiles: single-line JSON

```json
{"configuration":{"adblock_enabled":true,"fingerprint_profile":null,"image_blocking_mode":"none","image_size_limit_kb":40,"includes_cookies":false,"includes_passwords":false,"name":"Research","proxy_alias":null},"format":"rel.profile","version":1}
```

The configuration uses the profile-creation fields documented in the
[RPC guide](RPC.md). `name`, network filters, `fingerprint_profile`, and
`proxy_alias` are copied. A null fingerprint selects Native Chromium. Keep an
exported fingerprint object intact when preserving a configured identity.
`image_blocking_mode` is `none`, `all`, or `over_limit`; `image_size_limit_kb`
is an integer from 1 through 1048576.

Cookies, passwords, browser storage, and referenced proxy definitions are not
included. Both `includes_cookies` and `includes_passwords` must be false.
A non-null proxy alias must already exist on the importing device; import the
proxy first or set `proxy_alias` to null. The new profile receives a new ID.

### Case studies and reusable Actions

**Settings → Actions** is the reusable library. An Action contains named prompt
steps, optional inputs, a starting URL, and setup instructions. It can have an
optional default profile and be attached to multiple existing profiles. Profiles
continue to describe browser configuration.

Copy a case study's `ACTION.json` into **Import Action**. The portable envelope
is `{"format":"rel.action","version":1,"configuration":{"setup":{...},"profile":{...}}}`.
`setup` follows the [setup schema](RPC.md#profile-setup-definitions). `profile` is
optional and follows the ordinary profile configuration schema, without `setup`,
cookies, or passwords. Imports validate definitions and never execute steps.

Choose **Use Action**, edit inputs, and select a destination:

- A new session uses the Action's chosen default profile, its included portable
  profile configuration, or REL's default profile, in that order. You can select
  another profile for this use. A missing selected profile is an error.
- An existing session keeps its current browser configuration. Its Actions panel
  also offers **Add Action from Library**.
- Profiles selected under **Edit Action → Attached Profiles** receive the same
  definition in future app-created sessions, using that profile's configuration.
  Attachments reference one library definition; they do not duplicate it.

**Add Action** installs fresh, disabled session steps. Review their inputs,
destinations, model, and access checklist before enabling. **Enable Actions**
enables only the batch being reviewed, including any saved schedules. Reviewing
never executes steps. Use the session's **Run Now** for a live run, which can send
messages if configured. Sessions own their execution state, edits, and history;
library edits or deletion do not change previously installed steps.

Inputs are text or finite numbers. `{{key}}` placeholders are substituted once.
Portable definitions support manual work or weekday/time schedules, multiple
prompt steps, and stop-on-error behavior. Configure repeat intervals, completion
behavior, and event triggers in the session editor. Scheduled times use the Mac's
time zone; REL must be running and the Mac awake. Checklist confirmations are
manual, not automatic login or destination verification.

**Export Action** includes steps and optional browser configuration, excluding
credentials, browser data, local attachments, session IDs, enabled state, and run
history. Proxy aliases must be configured on the receiving Mac. Existing version
2 `rel.profile` setup imports remain supported for historical packages. The
library is app-owned; CLI, MCP, and SDK session creation does not install its
attached Actions.

### Proxies: curl command

```sh
curl --proxy 'http://proxy.example.com:8080' --proxy-user 'username:example-password' 'https://example.com'
```

Import reads `--proxy` (`-x`) and optional `--proxy-user` (`-U`), including
quoted values and `--option=value` forms. The proxy must use HTTP with an
explicit port from 1 through 65535; bracket IPv6 addresses. Commands are limited
to 64 KiB. REL parses the command without executing it, expanding shell syntax,
or requesting the target URL. The populated proxy editor opens for review and
requires **Save** before creation.

Export includes the endpoint, configured username, and saved password. REL
retrieves the password through the owning app’s authorized credential action;
if retrieval fails, export shows an error. The command quotes credentials for
shell use. Bright Data geographic
and ASN targeting and Oxylabs location targeting are encoded in the username.
Session suffixes are parsed as session templates, not reused as persistent
session IDs. REL treats the documentation placeholder `[replace with password]`
as an empty password on import. A pasted real password is
placed in the editor's password field and saved through REL's secure proxy
credential storage only when you save.

A curl transfer does not include the alias, locale override, or custom TLS CA
certificate. Review those fields in the editor. Recognized Bright Data endpoints
select Bright Data trust; other endpoints start with system trust. Options such
as `-k`, request headers, and the destination URL are not imported as proxy
settings. Use the archive API below if you need to preserve the complete proxy
configuration.

### Schedules: single-line JSON

```json
{"configuration":{"completionAction":{"type":"none"},"destination":{"existingSession":{"sessionID":"session-1","sessionName":"Work"}},"hour":9,"minute":30,"name":"Morning","prompt":"Check the page and report changes.","usesTimer":true,"weekdays":[2,3,4,5,6]},"format":"rel.schedule","version":1}
```

The optional `startingURL` field preserves the Action's starting page.

`name`, `prompt`, `destination`, `completionAction`, `weekdays`, `hour`, `minute`,
and `usesTimer` are required. Weekdays are 1 (Sunday) through 7 (Saturday), with
at least one day; hours are 0–23 and minutes 0–59 in the importing device's local
time zone. `usesTimer:false` creates a webhook-triggered schedule.

The destination is one of:

- `{"existingSession":{"sessionID":"...","sessionName":"..."}}`
- `{"newSession":{"profileID":"...","profileName":"..."}}`
- `{"configuredSession":{"settings":{...}}}`, preserving the exported custom
  session settings, including filters, proxy alias, and fingerprint draft.

Completion actions are `{"type":"none"}`, `{"type":"shortcut","name":"..."}`,
or `{"type":"webhook","id":"<UUID>"}`. Destination and completion references
are local to the importing device; their referenced sessions, profiles, proxies,
webhooks, and Shortcuts are not bundled. Review and repair them in the editor.

Every imported schedule receives a fresh ID and starts **disabled**, regardless
of the source schedule's state. Run history, errors, and timestamps are omitted.
Import never runs a prompt or completion action. Enable the schedule after
reviewing its destination, prompt, completion action, and local execution time.

### Providers: single-line JSON

```json
{"configuration":{"maxTurns":10,"name":"OpenAI"},"format":"rel.provider","version":1}
```

Required fields are `name` and `maxTurns`; `baseURL` and `apiKey` are optional,
except that services using the OpenAI-compatible adapter require a base URL.
There is no separate `provider` field. `name` identifies the service and must be
one of `OpenAI`, `OpenAI-compatible`, `OpenRouter`, `TypeSafe AI`, `Anthropic`,
`Google Gemini`, `Ollama`, `REL`, `Fireworks`, `Amazon Bedrock`, or `Baseten`, with
that capitalization. Custom connection names are not used for this field.
Named presets must use a matching endpoint; custom gateways use
`OpenAI-compatible`. Turn limits and URLs are validated using the provider
editor's rules.

Exports preserve an explicit `modelID`, optional `jevPairedModel`, and optional
`jevAdditionalPairedModels` list. A pairing
refers to configured provider identities on that Mac; after importing on another
installation, edit Jev to choose an available companion. Importing a REL provider
never downloads weights; select the model in Model Providers to open its download setup.

Exporting multiple providers uses `"format":"rel.providers"` with an array in
`configuration`. The import validates every entry before saving. Import saves
directly and defaults to **Skip** for existing services; **Overwrite** preserves
the existing connection's ID, internal name, and default selection. If multiple
saved connections use the same service, overwrite reports an ambiguity instead
of choosing one. Repeated services in an imported list follow the selected skip
or overwrite policy.

Export excludes API keys unless **Export Including API Keys** is selected.
Included keys are readable in the JSON and saved in Keychain on import. An
omitted key preserves an existing connection's key. Import without credentials
is allowed; the connection remains unready until configured. The exported
provider's own record ID, model discovery results, and default-provider preference
are excluded. A new first provider becomes the default normally.

### CLI and RPC archive transfers

CLI/RPC `.relprofile` and `.relproxy` SQLite archive transfers remain separate
from Settings text transfers. See the [CLI](CLI.md) and [RPC](RPC.md) guides for
archive operations. Archives can preserve browser data, complete proxy settings,
and passphrase-protected credentials. The new Settings JSON envelope is not an
archive or a replacement input for the archive APIs.

## AI models

Use **Choose Model** in the chat input to browse models, including REL’s local
catalog. **Open Models** opens Model Providers, where **Add** creates a provider
connection. Cancel returns without changing the selected model.

Configure providers and choose the default AI model in **REL → Settings… →
Model Providers**. Use the primary **Add** button to add a connection, or
double-click a provider to edit it. **Download**, next to Add, opens REL’s model
installer.
Provider names have **Ready** or **Needs Setup** status chips. Click a Needs Setup chip to
open configuration; hover over it for details. **Local** identifies REL models
and Ollama connections on this Mac. Use **Import** and **Export** for provider
configuration transfers. The Chat model picker’s **Open Models** button opens
model configuration. The **Models** column lists available models;
hover over a truncated list to see all its names. API keys are stored in macOS Keychain. Ollama connections can use
the local server at `http://127.0.0.1:11434` without an API key. Scheduled
prompts use the default provider and model when their new Session starts. REL
Free supports one configured external provider alongside REL’s built-in local
models; REL Pro supports multiple external providers.

The Chat model picker uses the provider's display name when available, or the
exact model ID when no display name is supplied. This also applies to newly
discovered models. API requests always use the model ID.

Chat displays response text as the model generates it, including local Ollama models such as Qwen. A model may think before its first text appears. The Stop button remains available during generation. Ordinary questions and writing requests can be answered directly without browser tools.

Choose **New Provider**, then open the searchable **Provider** menu. Remote
services, **Ollama**, and **REL** appear together; local providers have a **local**
chip. Both the provider menu and Model Providers table are alphabetical by
displayed name. The menu’s horizontal **All**, **Local**, **Remote**, **Frontier**,
**Hosted**, and **Custom** chips filter the list; search narrows the selected
category. Click the selected chip again to return to All. Frontier includes
OpenAI, Anthropic, and Google Gemini. Hosted includes OpenRouter, Fireworks,
Amazon Bedrock, and Baseten; Custom shows the OpenAI-compatible preset.
There is no separate Remote/Local picker.

**REL** appears in Model Providers by default with its supported model catalog,
currently **Qwen2.5 1.5B**. Selecting an undownloaded REL model in Chat, a Profile's
default model picker, or an Action opens its download setup. Choose
**Download & Add** to download and verify the 1.12 GB model from Hugging Face.
The setup shows progress and supports cancellation and retry. The selection is
applied only after successful installation. Already installed weights can be
added without downloading again. Model weights are not bundled with the app.
This model works for ordinary text chat and simple tasks; using it with Jev is
optional. Double-click REL or click **Download** in Model Providers to
open the same setup.

**Ollama** connects to an Ollama server using its endpoint settings. Install and
manage models in Ollama, then use **Refresh Models** in REL to discover them.
REL’s **Download** action manages REL’s native models.

Each Chat response stops after 12 model calls or a 64,000-token request budget.
REL uses the preceding model call's reported usage to avoid starting a call
that would predictably exceed the remaining budget. A retryable browser error
gets one recovery attempt. If the same error recurs through another tool or
argument set, REL removes browser tools for the rest of that response so the
model answers from collected evidence or explains the limitation. When an
exhaustive request exceeds a page or tool output bound, the response summarizes
the available evidence and states what was omitted.

## Streaming responses and tool activity

Chat displays answer text as the model generates it. Self-contained requests,
such as original writing or lorem ipsum, use ordinary text responses.

When a provider streams tool-call arguments, Chat shows **Preparing browser
work** before execution. The activity updates as the tool runs and finishes.
Preparation does not execute an incomplete tool call. Stopping a response cancels
its unfinished preparations.

The chat debug inspector shows preparation progress and redacted argument
previews. Incomplete JSON is shown as a received-byte count; complete arguments
use the same redaction as executed calls. Providers that deliver tool calls only
as complete objects, including the current Ollama adapter, cannot show
incremental argument progress.

## Chat restoration

REL saves each Session's open Chat tabs, their order and selection, conversation
messages, completed-work details, and unsent drafts in its local SQLite database.
Quitting and reopening REL restores them. Completed question-and-answer exchanges
are restored to the AI harness before you send a follow-up. An interrupted response
is not resumed automatically; its submitted prompt remains visible in the chat.
Database upgrades use transactional migrations. Existing workspace layout and token
usage are imported once from the current runtime’s old workspace file. If restoration
fails, REL reports the error and blocks replacement writes. A save failure preserves
the current draft in memory. Validation rejections allow another save; uncertain
save outcomes and revision conflicts require a restart before saving again.

Database recovery preserves healthy conversations and drafts. Damaged messages or
chats belonging to an unrecoverable Session remain in the original recovery snapshot
instead of the active workspace. Missing tab selections are cleared without discarding
healthy chats. The recovery report identifies affected records.

Closing a Chat tab removes its saved conversation and draft. Clearing a conversation
removes its saved messages. Deleting a Session removes its saved chats.

## Reading chat history

Chat follows new messages and activity while you are near the bottom. Scroll up
to read earlier messages without being pulled back down. Choose **Jump to latest**
to return to the newest content and resume following, or scroll back near the
bottom yourself.

## Agent instructions and current-page context

Open **REL → Settings… → Agent** to edit the system prompt used by native Chat.
REL adds these instructions after its protected browser and tool rules, and
changes apply to the next message in existing chats.

Every native Chat turn also includes the current page URL from its attached
Session. The default system prompt uses that context for requests such as
“summarize this page” or “summarize the top 3 links”: it reads the current page,
identifies the requested links in page order, reads their destinations, and
then answers. Restoring the default prompt returns to this behavior.

## Actions

When creating or editing an Action, **Starting URL** optionally specifies the
page to open before the first step. Enter a complete `http://` or `https://` URL,
or leave it blank to use the Session's current page. REL opens it in the Action's
Session once per run, before executing its prompt steps. Later steps continue
from the page reached by the preceding step. Navigation failures use the Action's
**On Error** setting.

Open the session's **Actions** panel to edit, run, or delete installed work.
Each session Action owns its prompt steps, trigger, completion behavior, and run
history. **Settings → Actions** manages reusable definitions and their profile
attachments. See [reusable Actions](#case-studies-and-reusable-actions) for imports
and destination selection.

Schedules, incoming webhooks, and built-in browser events execute the same saved
session Action. Editing it updates the work performed by its triggers. REL runs
at most one execution per session Action at a time, including manual runs.
Existing session Actions retain their IDs and webhook routing.

### Built-in events

In the Action editor, enable **Page Changed** or **Notification Received** and
choose a **Source Session**. Both are off by default. Page Changed fires when
the source session's URL changes, including same-document URL changes. It does
not watch arbitrary DOM mutations or compare page contents. Notification
Received fires when that session displays an allowed website notification.
Website notification permissions still apply. Notification Actions are separate
from sharing notifications with the agent's recent-notifications feed.

Events pass the source session and URL or notification details as untrusted
data after the saved prompt. Event content cannot select the Action or its
completion destination. Events for other sessions are ignored. Events received
while the Action is running are skipped, and automatic events are limited to
one run per Action every 30 seconds to bound cascades. These events are live
and are not replayed after restarting REL.

## Scheduled prompts

In a Session's Action editor, choose **When → Schedule** to run on selected
weekdays at a local time, or **When → Repeat every** to run at a fixed interval.
The repeat interval defaults to **30 minutes**. Enter any whole number from
1 to 10,080 minutes (one week). The Actions table shows the interval, and editing
an Action restores its saved repeat setting. REL Free supports one scheduled
Action; REL Pro supports multiple scheduled Actions.

Choose **Ends** to control how long the Action repeats:

- **Never** keeps repeating until you disable the Action.
- **After runs** stops after the specified number of scheduled attempts, from
  1 to 10,000. Failed attempts count; missed runs and manual **Run Now** executions
  do not. The count is saved before each attempt and survives restarts.
- **On date and time** prevents new scheduled runs at or after the chosen time.
  An Action already running can finish. For today only, choose tomorrow at
  midnight in the Mac's local time zone.

REL must be running when an Action is due. A new repeat setting first runs after
one full interval. Restarting REL, editing the prompt, or using **Run Now** does
not reset its cadence or run count. Changing the interval or end condition starts
a fresh cadence and count. Disabling and re-enabling preserves both.
Missed occurrences are skipped when REL starts again, and runs never overlap.
A run that lasts longer than its interval resumes at the next future occurrence
after it finishes. The table shows **Repeat ended** when its end condition is met;
manual **Run Now** remains available while the Action is enabled.

Use **Run Now** to execute the Action immediately. Disable the Action to pause
its timer. Weekday schedules follow the Mac's current time zone; repeat intervals
measure elapsed minutes. Results and failures remain visible in the Action's
status.

## Notifications

Open **REL → Settings… → Notifications** in the Browser section to control
**Send notifications to the agent** and inspect recent shared website notifications.
Sharing is off by default. Websites must first receive permission to send
notifications. Sharing adds untrusted website data to the feed. To start a turn automatically,
enable **Notification Received** for an Action and choose its source session in
**Settings → Actions**.

The page refreshes automatically and shows up to 256 shared notifications, newest
first, with each notification's origin, title, body, session ID, and display time.
The Recent section appears only when shared notifications are available.
Turning sharing off stops new entries; existing entries remain until the local
agent restarts. The queue is not a permanent notification archive. Debug runtimes
with website notifications disabled show that status on the page.

## Webhooks

Open **REL → Settings… → Webhooks** to add a JSON webhook, Discord integration,
or WhatsApp Cloud API integration. A configuration can send messages, receive
events, or do both. Its URL and credentials are stored in the current REL app
variant's Keychain, separately from browser sessions. Settings can send an
explicit test message and delete a destination.

To deliver an Action's final response, edit it in **Actions** and choose
**Send Result to Webhook**. A completion action can use either a webhook or a
macOS Shortcut. Keep Discord results within 2,000 characters and WhatsApp text
results within 4,096 characters. Delivery errors mark the prompt run as failed;
REL does not automatically resend messages.

To execute an Action from an incoming event, create the Action first, then
select it under **Run an Action on incoming events** when adding the webhook.
No schedule is required. Keep the Action enabled. Incoming data is appended
as untrusted JSON; write the Action prompt to describe which fields to process.
REL runs one event at a time per Action and keeps events queued while the
Action is busy, disabled, or missing.

**Copy Local Callback** copies the loopback receive URL. External services need
a public HTTPS relay forwarding only that path. The [RPC webhook guide](RPC.md#webhooks)
documents signing, provider setup, callback responses, inbox limits, and direct
HTTP calls. The inbox holds up to 64 events and resets when REL quits; use a
separate durable relay if events must survive app restarts.

For Discord sending, paste the channel webhook URL. Incoming Discord Webhook
Events require the application's public key and event subscriptions in the
Developer Portal. These subscriptions are distinct from ordinary channel
messages delivered through the Discord Gateway. See the official
[Discord webhook reference](https://docs.discord.com/developers/resources/webhook)
and [Webhook Events setup](https://docs.discord.com/developers/events/webhook-events).

For WhatsApp sending, supply your versioned Graph API messages endpoint, access
token, and recipient. Incoming events require the Meta app secret and a
verification token; REL handles callback verification and ignores delivery
status receipts. Text messages require an open customer service window. For
messages outside that window, callers can send an approved template using the
RPC `payload` option. See Meta's
[WhatsApp Cloud API reference](https://www.postman.com/meta/whatsapp-business-platform/documentation/wlk6lh4/whatsapp-cloud-api).

## Browser configuration changes

Saving browser identity or proxy configuration leaves the current page running.
If a change requires a new browser context, REL shows a banner above the page:
**Browser configuration changed. Reload to apply.** Choose **Reload** when you
are ready. Saving alone does not reload the page, so unsaved form input remains
available until you reload. Reverting all pending context changes removes the
banner.

Changes to upstream routing apply to new connections; existing connections
continue until they close. Browser identity, proxy assignment, and certificate
trust changes that require a new context wait for Reload when there is page
state to preserve. An empty browser with no active page, popup, or navigation
history applies these changes automatically without a reload banner. Sessions
that have not opened a browser yet start with their latest configuration.

## Proxy certificate trust

In **Settings → Proxies**, create or edit a proxy and choose **HTTPS Certificates → Trust**:

- **System trust** uses Chromium's ordinary certificate verification and macOS trust. Existing proxies retain this setting.
- **Bright Data certificate** adds REL's bundled Bright Data root CA for `brd.superproxy.io:44445`. Creating a proxy with the Bright Data type preselects this option; an existing proxy requires an explicit change.
- **Custom certificate** imports a PEM bundle or DER CRT file. REL saves the certificate contents with the proxy, so the original file is no longer needed. PEM bundles may contain 1–16 CA certificates, up to 64 KiB; private keys and website leaf certificates are rejected.

Additional CAs are trusted only in REL sessions using that proxy. They permit the proxy provider to inspect those sessions' HTTPS traffic. Hostnames, expiry dates, and certificate chains remain checked for pages and subresources. REL never installs these roots in Keychain or disables TLS verification. Saving a certificate change shows the configuration banner in affected open browsers. Reload applies the new trust settings while preserving session storage. Switching to another proxy or a direct connection replaces or clears the additional roots.

CLI/RPC proxy and profile archives preserve certificate settings. Settings curl transfers omit custom certificates. The import sheet identifies transfers that add a trusted proxy CA. Older transfer versions import with system trust.

## Remote access

**Settings → Remote Access** serves a small HTTPS dashboard for another computer.
It supports viewing and creating Sessions, deleting Sessions, navigation,
screenshots, creating Profiles, renaming custom Profiles, and adding prompt
Actions to custom Profiles. Profile Actions are saved as setup templates; adding
one does not run a prompt immediately. There is no live browser video or remote
macOS desktop.

1. Keep REL running on the Mac and arrange connectivity through your private
   network or VPN.
2. Obtain a PEM certificate chain and matching private key for a hostname your
   other computer can reach. The other computer must trust the certificate.
   Store the private key in a file readable only by your macOS account.
3. In **Settings → Remote Access**, enter the listener IP and port, such as
   `192.168.1.20:17443`, and the matching HTTPS origin, such as
   `https://rel.example:17443`. Use the certificate's hostname. Do not include a
   trailing slash or path. Enter the certificate and key file paths.
4. Click **Enable Remote Access**, then **Generate Pairing Code**.
5. Open that HTTPS address on the other computer. Enter a device name and the
   pairing code. Codes are single-use and expire after five minutes.

The default listener address is loopback-only. Select your private-network or
VPN address to allow another computer to connect. REL does not open firewall
ports, configure DNS, or obtain certificates. The existing local HTTP API stays
on loopback and must not be exposed directly.

Each paired browser has owner-level access to the dashboard's supported
operations for seven days. Use **Revoke** beside a browser in native Settings to
block new requests, or **Disable Remote Access** to revoke all browsers and stop
listening. Work already submitted may finish. Signing out revokes that browser.
Remote access is off again after REL restarts.

The **Activity** tab retains submitted jobs and results while remote access is
running, including when the browser disconnects. Select **View result** to load a
job's output or screenshot. An interrupted submission can be retried with its
original action key without running it twice. History is scoped to the paired
browser and limited to 64 jobs, with four jobs running at once. At capacity, wait
for work to finish, disable and re-enable remote access, and pair again.
Restarting remote access clears job history and pairings; do not resubmit
uncertain work without checking its effects on the Mac first.

Screenshots are limited to 4 MiB. Session deletion removes that Session's data
and asks for confirmation. Credentials and app-only password reveal operations
are not available through this dashboard.

## Jev browser decisions and page questions

Select the Jev provider for bounded decisions over the active Session's page.
Jev can click observed controls, scroll, wait for updates, clear text fields,
and type exact text supplied in double quotes. For example: `Enter "Ada" in
Name, then click Save.` REL executes native browser input and checks a fresh
observation before choosing the next action.

You can also ask for source information, such as `what are all the post titles`
or `list the product names`. REL supplies observed text passages grouped with
their section and control context. Jev selects which passages answer the request,
and REL returns those passages verbatim in
chat. A reading answer can require zero browser actions. It covers a bounded
current page observation, not every item in an infinite feed or unloaded page.
Scroll to more content and ask again when needed.

Jev chooses an operation and compatible target together. It returns typed
decisions rather than free-form answers. Its confidence percentage describes
how concentrated the model's choices are, not how clear your instruction is or
how much of the task is complete. Several useful next steps may share probability;
a valid choice below 50% can still proceed. Invalid choices, unsupported work,
unchanged-page repetition, and exhausted budgets still stop execution. A completion result is a model assessment;
independently check the requested route, date, passengers, cabin, and visible
results before treating a flight search as successful.

When adding **TypeSafe AI / Jev** in **New Provider**, choose its required
**Paired LLM** before saving. Use **Add Pairing** to add other configured LLMs
to the same Jev provider. Each saved pairing appears separately in the model
picker, with a name such as **Jev + qwen3:1.7b** or **Jev + gpt-5.6-luna**.
Pairings are remembered across relaunches, and each selection uses its own
companion. Edit the provider to change or remove additional pairings.

If a companion is removed or unavailable, click the **Choose a paired LLM…**
warning to open its provider configuration and choose another. REL does not
substitute a companion. Use **Add LLM Provider…** from Jev setup if none is
configured yet.

A small model can reduce field-entry latency; actual speed depends on hardware,
model and provider latency. Configured OpenAI, OpenRouter, OpenAI-compatible,
Ollama, and installed REL text models can be paired. Remote companions must
support chat completions with JSON-object output and token usage. Anthropic and
Gemini native adapters are not offered as companions. No local model is assumed
or selected automatically.

To install a local model, open **Model Providers → REL**, select
**Qwen2.5 1.5B**, and choose **Download & Add**. This explicit setup downloads
**Qwen2.5-1.5B-Instruct Q4_K_M** (1.12 GB), then adds an ordinary REL provider.
It can be used for chat independently or selected later as Jev’s paired LLM.
The installer offers progress, **Cancel**, and **Retry Download & Add**. A cancelled
or failed installation does not add a provider. Downloads have a 30-minute overall
timeout and a 60-second read timeout; retry starts a fresh transfer.

REL verifies the exact size and SHA-256 before installing weights in
`~/Library/Application Support/REL/Data/Models/jev-text/`. This historical cache
path is reused across app updates; Debug runtimes keep their own model directory.
Incomplete or corrupt weights are never loaded. Missing weights produce an error
pointing to provider setup. Chats and scheduled actions never start downloads.

The app includes llama.cpp with Metal in `rel-harness`, without model weights.
No Ollama installation, helper server, or additional API key is required for REL
models. Ordinary local chat accepts text and bounded browser tools, with a
32,768-token context, up to 2,048 output tokens, and a 120-second generation
limit. Replies arrive after generation completes. Small models may struggle with
complex tasks; no model is guaranteed to handle every site or control.

Jev still uses the configured TypeSafe API for browser decisions. The integration
follows the [Jev Ultrafast](https://github.com/browser-use/jev-ultrafast) approach:
Jev chooses actions, and a text model supplies field values when needed. REL uses
its existing native browser input, without the upstream Chrome backend or page
JavaScript.

The local helper loads lazily at the first generated field and retains its weights
for that chat process. It uses a fresh 4096-token context per field and the model's
non-thinking chat template. Output is constrained to JSON containing `text`, with
at most 128 generated tokens. If the selected field label or context specifies
`YYYY-MM-DD`, `MM/DD/YYYY`, or `DD/MM/YYYY`, REL validates and formats the generated
date in code. Invalid dates stop before typing. Correct values are not guaranteed
for every website; empty or malformed output stops before typing.

Local installation is separate from the chat protocol. `rel-harness local-models
list` reports the catalog and verified installation status. `rel-harness
local-models install qwen2.5-1.5b-instruct-q4_k_m` explicitly installs the model.
Both commands write newline-delimited JSON: `inventory` contains `models` with
`id`, `name`, `size`, and `installed`; `progress` contains `downloaded`, `total`, and
`status` (`checking`, `downloading`, `ready`); `error` contains `message` and exits
nonzero. Wait for successful process exit before treating an installation as ready.
Closing the installer process cancels its download. Use `--provider rel --model
qwen2.5-1.5b-instruct-q4_k_m` for ordinary local chat after installation.

For a shell client, explicitly select the local model with
`REL_JEV_TEXT_LOCAL=qwen2.5-1.5b-instruct-q4_k_m`, or set `REL_JEV_TEXT_PROFILE` to a named `openai`,
`openrouter`, `openai-compatible`, or `ollama` profile. Select exactly one.
`REL_JEV_TEXT_MODEL` chooses a discovered model within the named provider, overriding
its stored model ID. The helper reads `REL_JEV_TEXT_CONFIG` when set,
otherwise `REL_AI_CONFIG`, otherwise this runtime's default provider registry.
A separate helper registry avoids editing the file generated by REL Settings:

```toml
[providers.field_text]
kind = "openai-compatible"
model = "YOUR_TEXT_MODEL_ID"
base_url = "https://YOUR_PROVIDER/v1"
credential_service = "YOUR_KEYCHAIN_SERVICE"
credential_account = "YOUR_KEYCHAIN_ACCOUNT"
```

The model must support OpenAI-compatible chat completions with JSON-object
output and report token usage. `openai-compatible` profiles may omit both
Keychain references when their endpoint does not require authentication. Supplying
only one reference is an error. For a local Ollama model, for example:

```toml
[providers.local_text]
kind = "openai-compatible"
model = "qwen3.5:9b"
base_url = "http://127.0.0.1:11434/v1"
```

Select it with `REL_JEV_TEXT_PROFILE=local_text`. If the chosen text endpoint
supports reasoning controls, `REL_JEV_TEXT_REASONING=none` disables reasoning
for short field values. Other accepted settings are `minimal`, `low`, `medium`,
`high`, and `max`; unsupported provider settings fail explicitly.

For authenticated providers, store the key as a macOS generic-password item,
and authorize this runtime's bundled `Contents/Resources/rel-harness` to read
that item. Credentials are read in Rust and never enter model context or TOML.
For shell clients, these variables must be present in the harness process. App
chat uses the selected Jev provider’s saved pairing and its generated provider registry; shell
helper overrides do not replace that choice. REL writes only nonsecret Keychain
references for companion providers, and the Rust harness reads the credential.
A missing optional key is allowed for keyless endpoints; denied Keychain access
is an error. Scheduled Jev actions use their selected provider’s pair; install any required
local model in provider setup before running the schedule.

For example, navigate a Session to
[Google Flights](https://www.google.com/travel/flights?hl=en), select Jev, and ask:

> Find one-way flights from Zurich to London on September 27, 2026, for one adult
> in economy. Stop when matching flight options are visible.

For a multi-step search like this, select the 96k response token budget in
**Chat Options**. The default 24k budget can stop before the form is complete;
Jev and text-helper calls share that budget.

To use a running Debug runtime from a shell, navigate with its bundled `rel`
CLI, then invoke the same bundle's `rel-harness run --provider jev --model
jev-latest --session-id SESSION_ID --api-key-stdin -- GOAL`. Supply the Jev key
on private stdin. Set one of the companion environment selections above. There is no implicit
local helper or automatic fallback.
Use the worktree's runtime wrapper to select its endpoint.

Interaction decisions use visible controls and bounded page text. Passage-selection
questions are sent only after Jev selects a reading operation, which uses a
separate model call. A helper call counts against the same response call and
token budgets as Jev. It has a 30-second timeout and cannot execute browser tools.
If the page changes between observation and input, REL displays the rejected
action, observes the same Session, and asks Jev for a new decision. This happens
at most twice per response and never replays the old input automatically.
Invalid helper output, unavailable credentials, or exhausted budgets stop before typing. Native input
still checks the observation after text generation. Existing double-quoted
literal values remain available without a text helper. The Flights example stops
before choosing or booking a flight. A model's completion claim still requires
independent verification.

## Control REL through WhatsApp

In **Settings → WhatsApp**, enable the integration, connect your account by
scanning the QR code from WhatsApp's **Linked Devices**, and choose a group.
Turn on **Remote control** to accept commands. This uses REL's native linked-device
connection; no public webhook or inbound network port is required. The client is
unofficial and WhatsApp protocol changes can interrupt it.

Send commands from the **same WhatsApp account you linked**, using your phone or
another linked device, into the selected group. Every command starts with `/rel`.
Other group members cannot control REL, but everyone in that group can read its
replies. Choose a private group for sensitive tasks.

| Message | Result |
| --- | --- |
| `/rel help` | Show available commands |
| `/rel ask Find the delivery date for my order` | Chat with REL's AI and use its browser tools |
| `/rel status` | Report session and running Action counts |
| `/rel sessions` | List browser session names and IDs |
| `/rel new-session` | Create a session using REL's defaults |
| `/rel open SESSION_ID https://example.com` | Navigate an existing session |
| `/rel close-session SESSION_ID` | Close that session |
| `/rel actions` | List saved session Actions and their UUIDs |
| `/rel run ACTION_UUID` | Run an Action once and reply with its final result |
| `/rel new` | Reset the remote AI conversation |
| `/rel cancel` | Cancel current remote work and clear queued commands |

You can put a natural-language request directly after `/rel`; `ask` lets you
start a request with a reserved command word. AI requests use your configured
default model and its normal credentials and tools. The remote conversation is
separate from desktop chats and is kept in memory until reset, cancelled,
disabled, or REL restarts. Explicit session commands require the IDs from
`/rel sessions`; REL does not assume the selected desktop tab is your target.

Action runs use existing budget checks, multi-step behavior, and run history.
An explicit run can execute a disabled Action without enabling its schedule.
Configured Shortcut and webhook completion handlers still run. The remote
reply replaces the Action's optional WhatsApp notification for that run.

Keep REL running and your Mac awake and connected. Normal commands execute one
at a time; `cancel` interrupts the queue. Commands older than five minutes, from
before remote startup or its last access change, duplicate messages, non-text
messages, and commands from other senders or groups are ignored. Up to 16 commands
can wait; excess commands are discarded with a Settings status message. Messages
must fit within 4,096 Unicode scalar values. Long responses are shortened with
an explicit notice. Delivery failures appear in WhatsApp Settings.

Disabling the integration or Remote control, changing the selected group, or
removing the account invalidates queued commands and replies. The desktop
checks for cancellation every two seconds; already completed browser or external
actions cannot be undone, and an in-flight reply cannot be recalled. Commands are consumed before execution and are never
automatically retried after a crash or uncertain reply delivery. Check the
result before submitting a command again.

## Browser Use tests

With the Debug menu enabled, choose **Debug → Browser Use Tests → Run Scripted
Smoke Tests…** in either Release or Debug builds. REL opens a new test tab and
runs scripted browser checks using bundled fixtures. Python 3 must be available
on the app's PATH; no source checkout is required. These checks do not call AI
models or measure model accuracy.

The runner uses the calling app's bundled CLI and verifies its agent build
identity before each trial. Choose **Show Test Report** to view progress and
results, or **Cancel Current Test** to stop. The test tab remains open for
inspection, and the report links to the full trace in a temporary directory.


### Delegating browser work to Jev

Use a normal chat model for the conversation and add a Jev provider in REL
Settings with its TypeSafe API key. Restart the conversation's harness after
changing providers. The assistant can then call `rel_delegate_browser` after
observing a page. With several Jev providers, it must name the intended profile.

The assistant supplies a bounded goal and exact text values with field meanings,
so instructions do not need quoted strings. Jev selects operations and observed
controls; REL performs native input in the observed session. Planning, text
composition, page reading, visual reasoning, and final verification remain with
the main assistant. Missing values, unsupported controls, uncertain outcomes, and
completion proposals hand control back with completed-action history and evidence.
The assistant can resume the remaining goal without restarting the workflow.

Optional `finish_when` predicates check observable results independently. A
`verified` result means those predicates passed, not that arbitrary requirements
were proved. A Jev `done` proposal always requires host verification. Each call
permits at most 12 decisions, has a 20,000-token local budget, and checks elapsed
time against 60 seconds before further model decisions or actions; in-flight
native operations use their normal deadlines. Jev usage counts toward the main
response and conversation budgets.

Settings writes only nonsecret Keychain service/account references into
`ai-providers.toml`. The Rust harness reads the helper credential directly from
Keychain. The app and harness are separate Keychain clients. In Keychain Access,
authorize the app’s bundled `Contents/Resources/rel-harness` to read the Jev
profile’s API-key item; the registry reference alone does not grant access.
REL does not change credential permissions automatically. Locked Keychain or
missing access produces an explicit error without waiting for a background
authentication dialog. For a manually managed registry, pass `--config` or set `REL_AI_CONFIG` to its path when launching
the harness and put `credential_service` and
`credential_account` on the Jev profile, pointing to its macOS generic-password
item that authorizes the bundled harness. Model keys must never be placed in the registry. The existing standalone
Jev provider still supports its direct decision and page-passage mode.


Semantic browser observations report current native form values, including empty
fields and checked/unchecked state after input. If current form state cannot be
read, observation fails explicitly rather than substituting initial HTML attributes.

Semantic scroll offsets and document dimensions use CSS pixels, including on
Retina displays. Native input continues to use observation-scoped references.
