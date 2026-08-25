---
title: macOS app
description: Configure REL Profiles, AI models, Sessions, and repeating scheduled prompts in the macOS app.
editUrl: false
---
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

## AI models

Configure providers and choose the default AI model in **REL → Settings… →
Models**. API keys are stored in macOS Keychain. Scheduled prompts use this
default model when their new Session starts.

REL loads each configured provider's current model list and removes known
non-chat model families. OpenRouter results must explicitly support tool calls
and completion-token limits because native Chat sends both on every request.
Models with a **REL Verified** badge have completed REL's bounded text and
synthetic tool-call round trip. Other models may remain available as
provider-compatible or unverified as provider catalogs change.

Use **Compatibility Test → Test** while adding or editing a provider to run the
same small, explicit check for one model. The test can incur a small provider
charge. Its result distinguishes an unsupported model from temporary quota,
rate-limit, or service failures; it does not open or control a browser.

Clients can inspect REL's versioned verification catalog at
[`https://rel.me/supported-models.json`](https://rel.me/supported-models.json).
The JSON response includes `schema_version`, `catalog_version`,
`minimum_rel_version`, the verification contract, provider adapters, exact
model IDs, verification dates, and tested capabilities. Treat the list as a
curated compatibility floor rather than a complete provider catalog: a missing
model is unverified, not necessarily unsupported.

OpenRouter requests require routed endpoints to honor REL's parameters and cap
each completion at 1,024 output tokens; other providers use an 8,192-token
ceiling. REL preserves the account's existing
privacy and data-retention restrictions rather than weakening them to find an
endpoint. When OpenRouter reports a request cost, native Chat displays that
amount in its token/cost overlay.

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
