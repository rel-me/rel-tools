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

## AI models

Configure providers and choose the default AI model in **REL → Settings… →
Models**. API keys are stored in macOS Keychain. Scheduled prompts use this
default model when their new Session starts.

New chats use Medium reasoning effort and a 24-model-call limit by default.
You can choose a different effort per chat and configure a provider limit up to
128 calls. REL keeps model requests bounded by advertising only browser tools
that are useful for the current step, compacting older chat context, limiting
page evidence, and resizing large visual observations. OpenAI chat requests use
stable prompt-cache routing and bounded output; Anthropic chat requests enable
automatic prompt caching.

Turn on **REL → Settings… → General → Show token usage** to display the current
response's rounded token count and estimated cost above the chat input. Click
the badge for uncached and cached input, output, reasoning tokens, model calls,
the current-chat total, and the retained total for the selected model. Clearing
or starting a chat resets the response and chat totals, while the model total
remains available for comparison. Provider billing is authoritative, and REL
shows an em dash when it does not have pricing for the selected model.

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
