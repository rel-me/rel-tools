# REL app

The macOS app owns REL's embedded Chromium runtime, persistent Sessions, browser
Profiles, and AI chat. Keep REL running whenever local clients or scheduled
prompts need to use it.

## Profiles and Sessions

A **Profile** is a reusable template for a new Session. Profiles select the
connection, network filters, and any browser data that should be copied when a
Session is created. A **Session** is the persistent browser created from that
template; later Profile changes do not modify existing Sessions.

Manage templates in **REL → Settings… → Profiles**. The built-in Default,
AdBlock, and BandwidthSaver Profiles are always available. Custom Profiles can
also use a configured proxy and imported cookies or passwords.

## Session identity

The app assigns every new Session a curated compatibility profile with a
coherent User-Agent, hardware profile, locale, time zone, and network profile.
This includes quick-created Sessions and Sessions created from built-in or
saved Profiles. REL generates a fresh numeric seed for each Session, then keeps
that seed stable for the life of the Session. Choose Native Chromium in the
Custom creation form to opt out.

Use the Session's tab menu to inspect, change, or disable its identity profile.
Identity is configured per Session; there is no app-wide identity setting.
Saving an identity change closes and recreates only that Session's Chromium
context, then returns it to the same page. Choose Native Chromium to remove the
profile and use the embedded Chromium runtime without identity overrides.

Compatibility profiles keep the selected browser, platform, locale, time zone,
hardware, screen, graphics, storage, and network claims coherent. REL applies
small deterministic changes to copied Canvas, WebGL, and Web Audio readbacks so
two Sessions use different values while one Session stays stable. Text and
element geometry remains native so clicks, accessibility bounds, and
screenshots keep matching the page. A profiled Session reports WebGPU as
unavailable rather than exposing native graphics details that contradict its
profile. Font enumeration and other unlisted surfaces remain native.

An identity profile is a compatibility tool, not an anonymity guarantee. Its
seed is stable across sites in that Session, so sites may still correlate
visits. Network identity is also separate: use a Session proxy when traffic
must leave through another route. Proxied Sessions prevent WebRTC from using a
non-proxied UDP route, but REL does not turn a direct Session into a VPN.

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

## AI models

Configure providers and choose the default AI model in **REL → Settings… →
Providers**. API keys are stored in macOS Keychain. Ollama connections can use
the local server at `http://127.0.0.1:11434` without an API key. Scheduled
prompts use the default provider and model when their new Session starts.

Each Chat response stops after 12 model calls or a 64,000-token request budget.
REL uses the preceding model call's reported usage to avoid starting a call
that would predictably exceed the remaining budget. A retryable browser error
gets one recovery attempt. If the same error recurs through another tool or
argument set, REL removes browser tools for the rest of that response so the
model answers from collected evidence or explains the limitation. When an
exhaustive request exceeds a page or tool output bound, the response summarizes
the available evidence and states what was omitted.

## Agent instructions and current-page context

Open **REL → Settings… → Agent** to edit the system prompt used by native Chat.
REL adds these instructions after its protected browser and tool rules, and
changes apply to the next message in existing chats.

Every native Chat turn also includes the current page URL from its attached
Session. The default system prompt uses that context for requests such as
“summarize this page” or “summarize the top 3 links”: it reads the current page,
identifies the requested links in page order, reads their destinations, and
then answers. Restoring the default prompt returns to this behavior.

## Scheduled prompts

Open **REL → Settings… → Scheduled** to create repeating prompts. Each schedule
contains:

- a name;
- the Profile used to create a fresh Session;
- the prompt that runs in that Session;
- one or more weekdays and one local time; and
- an enabled or disabled state.

Create separate schedule rows when the same prompt should run at multiple times
on the selected days. Times follow the Mac's current time zone.

REL must be running when a schedule is due. At that time REL creates a new
persistent Session from the selected Profile, starts chat with the default AI
model, submits the prompt, and waits for the assistant response. The Scheduled
table shows the next run and whether the last run completed or failed. A failed
run leaves its new Session available for inspection.

Use **Run Now** to execute a schedule immediately without changing its next
repeating run. Disable a row to pause it without deleting its configuration.
If its Profile is later deleted, REL marks the Profile as missing and the
schedule cannot run until it is edited to select an available Profile.
