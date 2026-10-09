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

For provider setup and per-Session assignment, see [Configure proxies](PROXIES.md).

## CAPTCHA attention alerts

When a CAPTCHA persists in a live Session, REL sends a time-sensitive macOS
notification and shows a prominent red alert beside its menu bar label. Click
the notification or choose **Go to CAPTCHA in [Session]** at the top of the
REL menu bar menu. REL activates its window, selects the affected Session, and
focuses its existing browser so you can complete the challenge without reloading
or losing its state. Additional affected Sessions appear under **Other CAPTCHAs**.

REL recognizes common reCAPTCHA, hCaptcha, Turnstile, Arkose, DataDome, GeeTest,
and AWS WAF widgets, plus custom human-verification controls such as
Zillow-style press-and-hold challenges. Recognition is heuristic: a site's new
or unusual challenge can require you to open the Session manually. Loading a
CAPTCHA library alone does not trigger an alert, and REL does not solve CAPTCHAs
automatically. Existing client request deadlines still apply.

macOS asks for notification permission when REL first needs to alert you. Enable
REL under **System Settings > Notifications** and allow time-sensitive alerts
if you want them delivered during Focus. The menu bar alert remains available
when notifications are disabled. REL avoids repeated alerts for the same active
challenge and clears the alert when the challenge disappears, the page changes,
or the Session closes.

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

### Debug app lifetime

RELDebug stays running when you start it manually from Finder, Dock, a Run
action, or `make dev-open`. Closing its window leaves it running; quit from the
app menu or press **⌘Q** when finished. If you started it with `make dev-open`,
**Ctrl-C** in that terminal also requests a normal quit.

Automated verification can opt into a 15-minute quit timer with
`make REL_DEBUG_AUTO_QUIT=1 dev-open`. The flag applies only to that launched
Debug process and is not saved in preferences or the app bundle. Later manual
launches stay open. Release builds have no automatic quit timer.

### Building locally from source

In a REL source checkout, `make release-build` builds and signs
`dist/REL.app` using the current version. It does not reserve a release version,
notarize, package, publish, install, or open the app. It requires the configured
Release signing certificate and normal build dependencies. Builds reuse compiler
results and immutable Metal libraries under `~/Builds/RELBuildCache`, while each
checkout owns its writable build outputs. An unchanged local build verifies and
reuses its signed app; changed sources, settings, toolchains, frameworks, or signing
identities rebuild it. Reuse preserves the existing build timestamp and number.
Remove `dist/.release-build-reuse.json` to force staging. For build prerequisites
and the publication workflow, see the
[repository release guide](https://github.com/rel-me/rel/blob/main/docs/RELEASES.md).

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
- **Staging** receives staging releases as well as Beta and regular releases.

Existing Dev selections carry forward as Staging. Settings encode this channel as
`staging`. The Sparkle feed keeps its historical `dev` identifier so installed
clients continue receiving updates.

The selection is saved across app restarts. Changing channels changes which
future updates are eligible; it does not downgrade an installed version.

## Chat model picker

Open the model control in the Chat composer to search models, filter by provider,
and choose a recent model. Two rows prioritize OpenAI, Anthropic, Google, Ollama,
and OpenRouter. Provider filters with an arrow open setup for that provider;
configured providers filter the model list. The ellipsis at the end of the second
row and the CPU button open Models settings for all providers. Search includes
models from every configured provider.

For models that support them, **Thinking** and **Speed** appear at the bottom of
the picker. Changing the model, Thinking, or Speed applies to the next turn while
keeping the current messages and draft. The composer shows the selected thinking
level and any nonstandard speed; Priority appears as **Fast**. Unsupported controls are omitted.

## AI provider presets

In **Models → Providers → Add Provider**, choose **Fireworks**, **Amazon Bedrock**,
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

Add **TypeSafe AI** in Models → Providers with your TypeSafe API key. Jev is a
separate decision capability, available to the assistant through
[`rel_delegate_browser`](#delegating-browser-work-to-jev). Select an LLM for chat.
There is no paired-LLM setting, and Jev cannot be a chat default. Existing Jev
transcripts remain readable; select an LLM to start a new conversation.

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

REL keeps its `Data` directory accessible only to the current macOS user
(`0700`), with the database and its WAL/shared-memory files set to `0600`.
Concurrent workspace and Session operations use SQLite-managed connections so
opening another connection preserves the database's existing file locks.

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

### Cookie files

Open a Session’s **Overview → Options → Site Data** to import or export cookies.
**Export…** saves all cookies in that Session, including cookies hidden by the
search filter, with a suggested filename such as `Session123.cookies`.
**Import…** reads a REL `.cookies` file and adds its cookies to the current Session,
replacing cookies with the same domain, path, and name. Other cookies remain.
Reload the page after importing. REL reports any cookies rejected by Chromium.
An empty file leaves a running Session’s cookies unchanged.

In **File → Create Session from Profile**, use **Starting cookies → Choose File…**
to start a new Session from a cookie file. REL imports the file before opening the
first page. If you also choose a Profile’s Browser Data, the file replaces its
cookies while preserving saved passwords. An empty file starts without cookies.
An invalid or unreadable file stops creation with an error.

**New Profile** and **Edit Profile** also offer **Starting cookies**. Saving imports
a snapshot of the file into the Profile’s encrypted browser storage. Each new
Session created from that Profile starts with those cookies; you can move or
delete the original file afterward. Choosing a new file when editing replaces the
Profile’s startup cookies, preserves saved passwords, and leaves existing Sessions
unchanged. In a new Profile, the cookie file takes the place of another browser
data source. Removing a selected file before saving cancels that selection.

REL cookie files are versioned JSON containing values and cookie attributes,
including expiration, Secure, HttpOnly, SameSite, and priority. They are plaintext
and can contain login data. Exports have owner-only file permissions; keep them
private. REL accepts its own cookie file format, rather than browser database
files or Netscape cookie files. Cookie files do not include saved passwords,
local storage, or other site data.

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

Enable the proxy editor's **Detect Exit Locale** option to detect the exit country.
It is off by default for new proxies.
It uses the detected exit country instead of the configured target for
Automatic language. When the **Timezone** control is enabled, it also uses the
detected IANA timezone instead of the saved identity timezone. With detection
off, the saved timezone applies; with the control disabled, Chromium stays native. See
[timezone detection and browser identity](PROXIES.md#timezone-detection-and-browser-identity).
For Automatic language or an enabled Timezone control, REL requests
`https://ipwho.is/` through the browser session's agent-owned proxy before preparing
the browser. IPWHOIS.io sees the proxy's exit IP. Successful results are cached for up to 30 minutes per session and upstream
route; a provider session rotation changes that route. A failed lookup reports an
error rather than using a different locale or timezone. The option is preserved
in proxy and profile transfers; older transfers import with detection off.
Existing saved proxies keep their current setting, including an explicit off choice.

A country does not identify every resident's preferred language. In Custom
Privacy, choose **Custom** in the Language row to set an explicit locale such as
`fr-CA`. Custom takes precedence over automatic language selection. The timezone
control can still use the detected timezone independently.
Disabling the language control keeps native Chromium language and locale.
The former proxy-level manual locale is retained in storage and API responses,
but Automatic now uses country targeting or exit detection.

For HTTP clients, proxy create/update accepts `detect_exit_locale` (boolean,
default `false` on create and preserved when omitted on update). Proxy responses
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

### Loopback AdBlock exclusions

REL allows local development destinations through AdBlock: `localhost`, its
subdomains (such as `app.localhost`), IPv4 loopback addresses in `127.0.0.0/8`,
and IPv6 `::1`. This applies to main pages and subresources in direct and proxied
Sessions, even when a downloaded rule would block them.

Only the destination host is exempt. External requests made by local pages still
use AdBlock rules. Image blocking and image size limits still apply.

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

In **Settings → Profiles, Proxies, or Schedules**, the glass button
group contains **Add (+)**, **Edit**, a divider, **Import (down arrow)**, and
**Export (up arrow)**. Select a row to enable export. Import opens a text editor with a **Paste** button to insert the clipboard
contents; export shows selectable text with a **Copy** button. No file picker is involved.
Imports create new records and remain subject to the plan's creation limits.
Existing records are not overwritten.

Profiles and schedules use a versioned JSON envelope:
`{"format":"rel.<kind>","version":1,"configuration":{...}}`. The kind is
`profile` or `schedule`. Export produces one line; pasted JSON may
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
`unique_user_agent_per_request` is an optional boolean that defaults to false.
When true, each HTTP or HTTPS request from a new session gets a distinct
User-Agent suffix. Page JavaScript and User-Agent Client Hints retain their
configured values.

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

Models uses Fritz's provider transfer format and editor:

```json
{"configuration":{"name":"OpenAI"},"format":"fritz.provider","version":1}
```

`name` identifies the service. `modelID`, `baseURL`, and `apiKey` are optional;
OpenAI-compatible connections require a base URL. There is no provider turn-limit
setting. The shared editor validates service names and endpoints. Multiple
providers use `"format":"fritz.providers"` with an array in `configuration`.
The import menu supports **Skip** and **Overwrite** for existing services.
Keys are excluded unless **Export Including API Keys** is selected. Included
keys are readable in JSON; store and share those exports carefully.

Older `rel.provider` and `rel.providers` envelopes remain accepted by the shared
transfer reader for compatible services. Retired REL-only configuration fields
are not exported. Native weights are installed separately from provider imports.

### CLI and RPC archive transfers

CLI/RPC `.relprofile` and `.relproxy` SQLite archive transfers remain separate
from Settings text transfers. See the [CLI](CLI.md) and [RPC](RPC.md) guides for
archive operations. Archives can preserve browser data, complete proxy settings,
and passphrase-protected credentials. The new Settings JSON envelope is not an
archive or a replacement input for the archive APIs.

## AI models

Open **REL → Settings… → Models**, or the main window's **Models** button.
REL uses the same single Models page and provider editor as Fritz. Use **+** to
add a provider, double-click a row to edit it, and use the **…** menu to refresh,
import, export, or choose the default provider. There is no separate Local Models
page or Providers tab.

The table shows provider names, readiness, local/default badges, and available
models. The provider picker groups LLM and System One decision services, with
local and remote filters. **Fritz** supplies native local LLMs; **Ollaya** supplies
local decision models; **TypeSafe AI** supplies hosted Jev decisions. Decision
models cannot become the chat default.

The Fritz editor includes its model catalog, download progress and cancellation,
model status, **Start**/**Stop**, **Show in Finder**, and the **First use** or
**App start** policy. Ollama connects to an existing Ollama server. Manage its
weights in Ollama and refresh Models to discover them. Provider records and
native model management are owned by Fritz; adding providers has no REL-specific
provider limit.

For a new Chat, a session Profile's explicit model takes precedence. Otherwise
REL uses the most recently selected available model, then the default provider's
explicitly configured model. If the default OpenAI provider has no explicit
model, REL prefers its newest available general-purpose GPT generation, using
the shortest model alias within that generation. Legacy completion models such
as `babbage-002` and `davinci-002` are excluded from automatic selection and
recommended picker rows, but remain searchable. Saved conversation selections
are preserved. Use **Chat → Reset Chat** to apply the current default to an
existing conversation.
The Chat menu contains response budgets and model-call limits. Chat displays
response text during generation; Stop remains available. Models' display names
are for presentation; requests use the actual model ID.

On the first launch after this update, REL migrates the former Models records
into Fritz's provider storage for that app variant. Names, connection identities,
endpoints, explicit models, and the default selection are preserved. Fritz copies
referenced keys in Rust and atomically saves provider records with migration
completion. A restart uses that saved completion instead of importing again.
Existing destination records and keys are preserved. Unsupported or conflicting
records produce an error and a retry action; the original metadata and Keychain
items remain available for recovery. Saved chat, Profile, and Action model
selections resolve through the migrated connection identities.

Chat starts page summaries and inventories with bounded semantic reading. Its
reading tools can inspect the current page, navigate to a source, and recall
retained text without loading the same page again. They do not expose click or
input tools. Omit a specific search phrase when asking for a general overview;
Chat uses a focused query only when it has a useful literal label or fact to find.
Loaded-page coverage and output limits remain explicit, including on dynamic feeds.

During reading and interaction tasks, Chat retains semantic read and recall
selections from up to eight source snapshots. Successful semantic interaction
observations also contribute bounded text selections from their captured content.
Complementary lookups from the same snapshot stay together, so reading stock
after an identifier does not discard the identifier. Each source can use up to
8,000 characters within a shared 16,000-character working set, including
source and coverage information. Smaller selections leave room for longer ones;
clipping and omitted selections remain explicit. The latest tool result is not
duplicated. Images, raw HTML and action references are not retained there.
Switching from reading to interaction and using controls within the same document
keeps these selected snapshots available. This helps a bounded feed inventory
retain earlier post titles and permalinks after the page removes their cards.
Chat can recall a saved observation when requested facts are missing from these
bounded selections.
A new user turn, explicit interaction navigation, a control that changes the page URL,
document replacement, stale observation error or switch to another task type
clears these excerpts. During interaction, changing the target Session also
expires selected evidence, even when the pages have the same URL. Reading
comparisons can retain multiple sources; recalling a saved snapshot does not
change the live browser target. These excerpts describe captured evidence,
not a guarantee that a page remains unchanged or that an infinite feed
has reached its end.

Chat manages excerpt sizes itself. Its model-facing reading tools accept a
source and optional literal query; character and section controls remain
available in the public SDK and RPC reader. Comparisons use already available
facts directly and recall sources when requested facts are missing. Repeating
an identical recall once restores the retained snapshot without loading a page;
further identical repetitions stop. Unknown snapshot IDs return a correction
hint without discarding unrelated evidence. Control-reference search is exposed
for interaction tasks, while reading tasks search source text through recall.

For several missing named fields, Chat can recall literal field labels together
from the same saved snapshots. Each source is fetched once and results keep the
field, matching passages and coverage together. Complete matched fields take
priority over broad excerpts and unsuccessful label guesses in the working set;
any field that cannot fit is omitted whole with explicit status. Ordinary passage
queries automatically retain a compact exact match when its selected records fit
completely, using the same saved snapshot; their search output remains unchanged.
Matching ignores case and repeated
whitespace while preserving punctuation and identifier boundaries. A matched label
does not prove that its value is complete. A missing label applies only to captured
content blocks and named contexts; alternative wording, control-only values or
uncaptured content can still contain the information.
Field batches contain up to eight labels and 32,768 output characters; ordinary
passage recall keeps its 12,000-character output bound. These are evidence-payload
bounds, not response token limits. Public reader selection preserves identifiable
table rows and list records, omitting a whole record when it cannot fit.

HTML is reserved for explicit source inspection. Automatic observation stays
semantic for nonvisual work, even when the page contains SVGs, canvas elements or
unnamed controls. A visual task, or an explicit promotion to inspect pixels, can
request a bounded screenshot when the selected model supports image tool results.
Switching to interaction makes controls available through scoped native references.

Element references belong to the observation that displayed them. A text read
provides a searchable observation handle, but Chat must find its controls before
acting. After a stale-reference error, Chat observes the visible page again.
Current-page metadata cannot repair an element reference. Action batches have a
15-second default deadline plus explicit waits, capped at 60 seconds. The deadline
is enforced by the browser operation, so timed-out input is not retried in the
background. Chat returns a final answer when its model-call limit is reached or
a browser error code fails twice, including errors marked non-retryable.

By default, each Chat response allows 64 model calls with no cumulative response
token cap. **Chat Options** can set an explicit token budget; previously saved
choices remain in effect. Select **Unlimited** to remove a saved response token
cap. Protocol requests may omit `response_token_budget` or pass zero for unlimited
response tokens. With a positive budget, REL uses the preceding model call's
reported usage to avoid starting a call that would predictably exceed it.
REL imposes no per-call output cap or cumulative conversation token budget.
Provider/model ceilings and browser action deadlines still apply. A retryable browser error
gets one recovery attempt. If the same error recurs through another tool or
argument set, REL removes browser tools for the rest of that response so the
model answers from collected evidence or explains the limitation. When an
exhaustive request exceeds a page or tool output bound, the response summarizes
the available evidence and states what was omitted.

When browser work stops early, the final answer includes a **REL stop reason**
with the factual explanation. Instructions that tell the model to stop using
tools and answer from collected evidence remain internal. A retry-limit message
identifies the recurring error code; inspect the failed tool's result in the
completed-work details for its underlying error message.

Output caps are omitted for OpenAI, OpenAI-compatible, OpenRouter, Gemini and
Ollama requests. Anthropic requires `max_tokens`, so REL uses the selected
endpoint's advertised model ceiling from `/v1/models/{model}`. An endpoint that
cannot supply a positive ceiling returns an explicit setup error. Local chat
models can use the remaining context capacity instead of a fixed output cap.
The synthetic provider-compatibility probe remains bounded.

## GPT-6 reasoning and estimated costs

The profile model picker supports **None**, **Low**, **Medium**, **High**, **XHigh**
and **Max** reasoning for `gpt-6-luna` and `gpt-6-sol`. `gpt-6-astra` and
`gpt-6.1-sol` support **Low** through **Max**. Date snapshots use their family's
settings. A restored **Minimal** setting, or **None** for a model without that
option, becomes **Low**. Selecting a model does not mark it REL-verified.

REL estimates Standard-tier GPT-6 costs from each call's reported usage. Rates
per million input/cached-input/output tokens are $0.10/$0.01/$0.50 for Luna,
$2/$0.20/$10 for Sol, $10/$1/$50 for Astra and $2/$0.10/$10 for 6.1 Sol. Cache
writes use 1.25 times the input rate. Calls above 272,000 input tokens use twice
the input/cache rate and 1.5 times the output rate. These estimates use the
[OpenAI model rates](https://developers.openai.com/api/docs/models/gpt-6-luna)
and [cache accounting](https://developers.openai.com/api/docs/guides/prompt-caching).
Provider-reported cost takes precedence. Restored logs containing only aggregate
usage cannot resolve per-call thresholds and show no GPT-6 estimate.

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
“summarize this page” or “list these links”. Page identity alone does not establish
its contents: REL answers from loaded or retained page evidence, preserving page
order when listing items. It reads linked destinations only when their contents
are needed and can search within the document without replacing the task with a
web search. Restoring the default prompt returns to this behavior. Existing
unmodified defaults upgrade automatically; customized instructions are preserved.

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

Chat uses the Fritz harness with REL’s configured LLM, instructions, response
limits, and browser tools. The assistant composes field text, reads pages, and
checks results. An optional configured Jev decision model can execute bounded
browser work through [delegation](#delegating-browser-work-to-jev).

Direct `rel-harness chat/run --provider jev` is no longer supported. Select an
LLM provider for chat and scheduled actions. Jev pairing and `REL_JEV_TEXT_*`
helper configuration have been removed. Saved Jev conversations require an LLM
selection before another message can be sent; no companion is selected implicitly.

### Installed local chat models

Open **Models → + → Fritz** to choose a native LLM, or edit an existing Fritz
connection. Use the shared catalog's memory and size filters, select a model,
and choose **Download**. The installer shows progress and supports cancellation
and retry. Chats never download weights automatically.

Fritz owns native inference, installation, and the local service. REL retains
its browser tools, response budgets, and conversation history. REL supplies its
existing `Data/rel-data.sqlite3` database and variant-specific Keychain reference
to Fritz. Provider records share that database; no Fritz default storage or
credential namespace is used. Native model files use the flat `~/Models/`
directory, shared across REL variants. The first actual download creates the
root directory if it is missing. Opening Models, checking inventory, and app
startup do not create it. Model weights are not bundled with the app.

The provider-record migration retains the previous local model selection.
Existing weight files remain untouched. The shared editor reports whether the
selected model is installed in Fritz's flat cache layout; install missing weights
there before using that model.

Use `rel-harness chat/run --connection ID` to select a stored provider, with
`REL_AGENT_PORT`, `REL_MODELS_DIRECTORY`, and `REL_MODELS_KEYCHAIN_SERVICE` matching
the owning app variant. The Debug runtime wrapper supplies those references.
Connection metadata is read through `GET /v1/model-providers`; credentials stay in
Rust and Keychain.
The former `--config` TOML provider registry is retired.

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
were proved. A Jev `done` proposal always requires host verification. Delegation
has no separate step, token or elapsed-time budget and no decision-request
timeout. The `max_steps` argument is removed. Calls share the host's model-call
limit and any explicitly selected response token budget, reserving one model
call for host verification. Native operations retain their normal deadlines,
and observation bounds and repeated-action checks still apply.

Jev connections and keys use Fritz's provider store and Keychain namespace.
The Rust browser harness resolves the selected decision connection and reads its
credential without exposing keys to the UI or model context. A missing key or
denied Keychain access produces an explicit error. Restart the conversation's
harness after changing decision providers.
Jev cannot be used as a Chat provider and requires no paired LLM.

### Local decision models

For local judgments, add **Ollaya** in Models → Providers and explicitly download
an experimental decision model such as **Kev 4B**. Select an LLM for the
conversation. A configured Ollaya connection is available through the same
`rel_delegate_browser` tool; with multiple decision connections, the assistant
must name its intended profile. Local inference requires no API key and never
downloads weights automatically.

REL uses Fritz's shared typed decision runtime with REL-owned model locations.
The model selects among observed controls and supplied exact values. Chat keeps
planning, reading, composition and verification. Local decision input does not
clean or rewrite the conversation. Context limits produce explicit errors;
missing evidence is not silently removed, and another provider is not substituted.
The local decision child has a 120-second terminal deadline and cancels when its
owning request closes. Single-option choices are resolved in code.
Local decision tokens remain in usage and response-budget accounting, but are
excluded from the chat model's hosted-price estimate.

Experimental availability does not establish workflow accuracy. Qualify each
model's choices, uncertainty and latency for the intended task; a completion
proposal still requires independent verification. The local typed interface
validates every returned answer, while existing Jev delegation validates the
selected branch. Uncertainty in unused branches does not itself stop delegation.


Semantic browser observations report current native form values, including empty
fields and checked/unchecked state after input. If current form state cannot be
read, observation fails explicitly rather than substituting initial HTML attributes.

Semantic scroll offsets and document dimensions use CSS pixels, including on
Retina displays. Native input continues to use observation-scoped references.
