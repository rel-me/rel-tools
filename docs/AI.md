# REL Chat and models

REL includes a session-scoped Chat interface in every browser tab's bottom
panel. Chat uses the model profile configured in **REL → Settings… → Models**
and can inspect, navigate, and act through REL's typed browser tools.

## Configure a model

Add a profile in **Settings → Models** and choose a provider. REL checks the
configured credential and automatically loads the models available from that
provider. The model picker remains editable, so you can enter an exact model ID
when a provider cannot list models or a newly released model is not returned.

REL suggests a profile name from the provider and selected model, and makes the
first profile the default. Additional profiles can be made the default from the
same sheet. Advanced settings contain the profile name, API-key variable,
bounded maximum turn count, and optional endpoint overrides.

Supported provider kinds are OpenAI, OpenAI-compatible endpoints, Anthropic,
Google Gemini, and Ollama. OpenAI-compatible endpoints are a distinct provider
type and require an explicit endpoint; their API key is optional. Ollama does
not require an API key.

Hosted profiles store the name of an API-key environment variable, not the key.
That variable must be present in REL's process environment before model
discovery or Chat starts. Endpoint overrides and other non-secret settings are
stored with the profile in:

```text
~/Library/Application Support/Rel/Data/ai-providers.toml
```

The file never contains provider credentials.

If discovery fails, confirm that the variable shown in the sheet is available
to REL, then select **Refresh Models**. You can inspect the same normalized
model listing from Terminal without printing the credential:

```sh
/Applications/REL.app/Contents/Resources/rel-ai-service \
  models --provider openai --api-key-env OPENAI_API_KEY

/Applications/REL.app/Contents/Resources/rel-ai-service \
  models --provider openai-compatible \
  --base-url http://127.0.0.1:1234/v1
```

The command returns JSON with credential availability, discovered model IDs and
display names, and any provider error. For OpenAI-compatible services, the
endpoint must expose the usual `/models` API beneath the configured base URL.

## Use Chat

Open the bottom panel in a browser tab and select **Chat**. Each tab owns an
independent native conversation view and Rust harness process. The ordinary
Terminal tab has a separate PTY and is not reused or interrupted.

The composer’s model menu starts with a curated set of OpenAI chat models that
use `OPENAI_API_KEY`. Profiles from **Settings → Models** are merged into that
list, so custom providers and endpoints are available beside the built-in
choices. New tabs begin with the configured default profile, or the first
built-in model when no default exists, while each open tab can select its own
model. Choose **Add or Manage Models…** at the bottom of the menu to configure
another provider model and add it to the list.

Changing models before sending the first message is immediate. Changing models
after a conversation has started asks for confirmation because it starts a new
conversation in that tab.

The harness keeps structured conversation history until it is cleared or
restarted. Browser tool calls are pinned to the immutable session ID of the tab
where Chat was opened, even if a model attempts to supply another session ID.
Assistant responses render as rich, selectable Markdown through the Textual
Swift package.

Chat controls are:

| Control | Action |
| --- | --- |
| `Return` | Send the prompt |
| Model menu | Choose the model for this tab or configure more models |
| Clear button | Clear conversation history without changing browser state |
| Restart button | Restart the model harness |

## Process boundary

The installed app uses native SwiftUI for Chat and bundles the Textual Swift
package for Markdown rendering. REL launches the Rust `rel-ai-service`
directly and exchanges strict newline-delimited JSON over its standard streams.
Rig owns the provider conversation and tool loop, and its tools reach Chromium
only through the supported [RPC v1](RPC.md) client boundary.

For protocol diagnostics, the bundled harness can be run directly. `chat`
requires `--session-id` or `REL_SESSION_ID`, reads requests from stdin, and
writes one `ready`, `assistant`, `cleared`, or `error` event per stdout line:

```sh
printf '%s\n' '{"type":"clear"}' | \
  /Applications/REL.app/Contents/Resources/rel-ai-service \
    chat --provider ollama --model qwen3 --session-id Session1
```

Diagnostics use stderr. The conversation process is created on demand and does
not contact a model until a prompt is submitted.
