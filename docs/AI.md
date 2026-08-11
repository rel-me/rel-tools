# REL Chat and models

REL includes a session-scoped Chat interface in every browser tab's bottom
panel. Chat uses the model profile configured in **REL → Settings… → Models**
and can inspect, navigate, and act through REL's typed browser tools.

## Configure a model

Add a profile in **Settings → Models**, choose its provider and model ID, then
make it the default. Supported provider kinds are OpenAI and compatible
endpoints, Anthropic, Google Gemini, and Ollama.

Hosted profiles store the name of an API-key environment variable, not the key.
That variable must be present in REL's process environment before Chat starts.
Ollama profiles do not require an API key. Endpoint overrides and the bounded
maximum turn count are stored with the profile in:

```text
~/Library/Application Support/Rel/Data/ai-providers.toml
```

The file never contains provider credentials.

## Use Chat

Open the bottom panel in a browser tab and select **Chat**. Each tab owns an
independent native conversation view and Rust harness process. The ordinary
Terminal tab has a separate PTY and is not reused or interrupted.

The harness keeps structured conversation history until it is cleared or
restarted. Browser tool calls are pinned to the immutable session ID of the tab
where Chat was opened, even if a model attempts to supply another session ID.
Assistant responses render as rich, selectable Markdown through the Textual
Swift package.

Chat controls are:

| Control | Action |
| --- | --- |
| `Return` | Send the prompt |
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
