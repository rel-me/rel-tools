---
title: macOS app
description: Configure REL Profiles, AI models, Sessions, and repeating scheduled prompts in the macOS app.
editUrl: false
---
The macOS app owns REL's embedded Chromium runtime, persistent Sessions, browser
Profiles, and AI chat. Keep REL running whenever local clients or scheduled
prompts need to use it.

## Free and Pro

REL Free does not require registration. It includes one Session at a time, one
scheduled prompt, one custom Profile, and one configured AI model provider.
Proxies cannot be created, configured, assigned, or used on the Free plan.

Register a REL Pro license in **REL → Settings… → Plan** to use proxies and
remove those limits. If Pro registration expires or is removed, REL preserves
existing Sessions and configuration instead of deleting them. Free prevents
additional creation beyond its limits, and any stored proxy assignment runs as
a direct connection until Pro access is restored.

## Profiles and Sessions

A **Profile** is a reusable template for a new Session. Profiles select the
connection, network filters, and any browser data that should be copied when a
Session is created. A **Session** is the persistent browser created from that
template; later Profile changes do not modify existing Sessions.

Manage templates in **REL → Settings… → Profiles**. The built-in Default,
AdBlock, and BandwidthSaver Profiles are always available. Custom Profiles can
also use a configured proxy and imported cookies or passwords.

Use **Import Profile…** and **Export Profile…** in that settings tab to move a
template in a versioned `.relprofile` SQLite archive. An export can include the
Profile's cookies, saved passwords, referenced Proxy configuration, and saved
Proxy credentials. REL requires a transfer passphrase whenever any of those
secrets are selected. On import, REL previews the included data and asks for
the passphrase before creating the Profile and restoring its browser data.

Manage upstream connections in **REL → Settings… → Proxies**. **Import Proxy…**
and **Export Proxy…** read and write versioned `.relproxy` SQLite archives. An
export can omit credentials or include the saved username and password in
passphrase-protected form. Choose the credential-free option when the file
only needs to recreate routing settings.

Both file types use the same versioned SQLite schema: `metadata`, `proxies`,
`profiles`, `cookies`, and `passwords`. A standalone Proxy archive and a Proxy
embedded in a Profile archive use the identical `proxies` table. Secret values
are stored only as encrypted BLOBs; the passphrase is not written into the
file. Import creates a new Profile or Proxy and does not overwrite an existing
name or alias. Version 1 imports accept only this SQLite format; legacy JSON
transfers are not supported.

## AI models

Configure providers and choose the default AI model in **REL → Settings… →
Models**. API keys are stored in macOS Keychain. Scheduled prompts use this
default model when their new Session starts. REL Free supports one configured
provider; REL Pro supports multiple providers.

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

REL Free supports one saved schedule; REL Pro supports multiple schedules.

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
