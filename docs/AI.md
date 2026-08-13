# REL Chat and models

REL includes a session-scoped Chat interface in every browser tab's bottom
panel. Chat uses the provider connections configured in **REL → Settings… → Models**
and can inspect, navigate, and act through REL's typed browser tools.

## Configure a provider

Choose **Add Provider…** in **Settings → Models** and configure the provider,
credential environment variable, and any custom endpoint. A model is not
required in Settings. REL checks the connection and automatically adds the
models returned by that provider to the model picker in Chat.

REL suggests a profile name from the provider and makes the first connection
the default. Additional connections can be made the default from the same
sheet. Advanced settings contain the profile name, API-key variable, bounded
maximum turn count, and optional endpoint overrides.

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
to REL, then select **Refresh Models**. The curated OpenAI choices remain
available in Chat. You can inspect the same normalized model listing from
Terminal without printing the credential:

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

Chat opens in the right-side panel by default for each browser tab. Use the
Chat button immediately after the address field to hide or show it. Each tab
owns an independent native conversation view and Rust harness process. The
ordinary Terminal tab has a separate PTY and is not reused or interrupted.

The composer menu starts with a curated set of OpenAI chat models that use
`OPENAI_API_KEY`. Models discovered through connections in **Settings →
Models** are merged into that list, so custom providers and endpoints are
available beside the built-in choices. Each browser tab keeps its own Model,
Effort, and Speed selection. Open **Model → Configure Providers…** to add
another provider connection.

Effort offers Minimal, Low, Medium, High, and Extra High reasoning for OpenAI
models. Speed chooses the Standard, Priority, or Flex OpenAI service tier.
Changing Model, Effort, or Speed before sending the first message is immediate.
Changing any of them after a conversation has started asks for confirmation
because it starts a new conversation in that tab.

The harness keeps structured conversation history until it is cleared or
restarted. Browser tool calls are pinned to the immutable session ID of the tab
where Chat was opened, even if a model attempts to supply another session ID.
Assistant responses render as rich, selectable Markdown through the Textual
Swift package.

Chat controls are:

| Control | Action |
| --- | --- |
| `Return` | Send the prompt |
| Chat configuration menu | Choose Model, Effort, or Speed for this tab |
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
    chat --provider openai --model gpt-5.6-sol \
    --effort xhigh --speed standard --session-id Session1
```

Diagnostics use stderr. The conversation process is created on demand and does
not contact a model until a prompt is submitted.
