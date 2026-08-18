# REL MCP server

REL includes a local Model Context Protocol server for agents that support MCP.
Run `rel-mcp` as a stdio subprocess; the adapter exposes a focused set of
browser tools and forwards every tool call through the public
[`rel-client`](SDK.md) crate and [RPC v1](RPC.md). It does not read SQLite,
logs, or Chromium state directly.

Related documents: [Codex plugin](CODEX_PLUGIN.md),
[Claude Code plugin](CLAUDE_CODE_PLUGIN.md), [CLI](CLI.md), [RPC](RPC.md), and
[Rust SDK](SDK.md).

## Configure an MCP client

Use the CLI bundled in the installed app or install the public `rel-cli`
package as described in the [CLI guide](CLI.md). An absolute path to the bundled
binary is the most reliable choice for GUI clients that do not inherit an
interactive shell's `PATH`:

```json
{
  "mcpServers": {
    "rel": {
      "command": "/Applications/REL.app/Contents/Resources/rel-mcp"
    }
  }
}
```

For clients that use TOML configuration:

```toml
[mcp_servers.rel]
command = "/Applications/REL.app/Contents/Resources/rel-mcp"
```

The Settings command-line task creates `rel` only in a writable directory
already in `PATH`, but an MCP host may use a different process environment.

### Codex

The Codex desktop app, CLI, and IDE extension use the same plugin and MCP
configuration on one machine. The recommended setup installs the REL plugin
from this repository's marketplace:

```sh
codex plugin marketplace add rel-me/rel-tools
codex plugin add rel@rel
```

See the [Codex plugin guide](CODEX_PLUGIN.md) for requirements, updates, and
verification.

Start a new Codex task after installation so Codex loads the plugin's MCP server
and `rel-browser` skill.

To configure only the MCP server without installing the plugin:

1. Open **Codex Settings → MCP servers**.
2. Add a STDIO server named `rel`.
3. Set the command to
   `/Applications/REL.app/Contents/Resources/rel-mcp` with no arguments.
4. Save the server and restart Codex.

The equivalent global entry in `~/.codex/config.toml` is:

```toml
[mcp_servers.rel]
command = "/Applications/REL.app/Contents/Resources/rel-mcp"
```

Use `.codex/config.toml` in a trusted project instead when REL should only be
available in that project. If the `codex` command is installed in the shell's
`PATH`, it can create and inspect the same configuration:

```sh
codex mcp add rel -- /Applications/REL.app/Contents/Resources/rel-mcp
codex mcp list
```

After restarting Codex, start with a read-only prompt:

```text
Use the REL MCP server. Call rel_status, then rel_list_sessions. Do not navigate anywhere.
```

Codex should discover the ten tools listed below, and `rel_status` should report
the installed app, local agent, Browser Proxy, and embedded Chromium bridge.
In the Codex terminal UI, `/mcp` also shows configured servers and their tools.

For an end-to-end browser test, use:

```text
Use rel_capture to capture https://example.com and report the saved output URI.
```

Unlike the first check, this loads a website and saves rendered HTML. Omitting
`session_id` can also create a persistent REL browser session.

After a page is attached or selected, verify visual output with:

```text
Use rel_take_screenshot to take a full-page WebP screenshot and describe the image.
```

### Claude Code

The recommended Claude Code setup installs the same shared plugin from this
repository's Claude marketplace:

```sh
claude plugin marketplace add rel-me/rel-tools
claude plugin install rel@rel
```

Restart Claude Code after installation, or run `/reload-plugins` when the
interactive installer requests it. Claude Code applies its ordinary per-server
approval to the bundled local MCP process. See the
[Claude Code plugin guide](CLAUDE_CODE_PLUGIN.md) for requirements, updates, and
verification.

### Direct protocol smoke test

An MCP host is not required to verify the adapter. This legacy handshake lists
the tools and calls the read-only status tool over the STDIO transport:

```sh
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"rel-smoke-test","version":"1"}}}' \
  '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
  '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"rel_status","arguments":{}}}' \
  | /Applications/REL.app/Contents/Resources/rel-mcp
```

The server writes three JSON-RPC responses: initialization information, the
tool list, and the status result. Protocol messages use standard output;
diagnostics use standard error.

`rel-mcp` accepts no MCP options; `--help` and `--version` are available for
direct inspection. Startup, discovery, initialization, tool listing, ping, and
`rel_status` never launch the REL app. A validated call to any other tool starts
REL in the background only when its agent is unavailable. Concurrent adapters
serialize that cold start and recheck agent health before launching, so only one
adapter opens the app. The adapter keeps serving its original stdin/stdout
connection until the MCP client closes stdin or terminates the process.
`REL_AGENT_PORT` changes the loopback RPC port from its default, `17319`.

The dedicated process name makes adapters clearly identifiable separately from
the `rel` CLI and app-owned `rel --agent` process.

Browser tool calls also use the [RPC session-selection behavior](RPC.md#transport):
while REL is inactive, their target session is selected by default without bringing
the app forward. The General setting **Follow browser commands** controls this.

## Transport and protocol versions

The server uses the standard MCP stdio transport. Each input and output message
is one UTF-8 JSON-RPC 2.0 object on one physical line. Standard output is
reserved for protocol messages; diagnostics go to standard error. Notifications
do not receive responses.

REL supports both MCP protocol eras used by current clients:

| Protocol revision | Connection flow |
| --- | --- |
| `2026-07-28` | The client calls `server/discover`; subsequent requests carry the current per-request MCP metadata. |
| `2024-11-05`, `2025-03-26`, `2025-06-18`, or `2025-11-25` | The client sends `initialize`, receives the selected legacy revision, then sends `notifications/initialized`. |

Discovery and initialization advertise only the `tools` capability. REL does
not expose MCP resources or prompts, and its fixed tool list does not emit
list-changed notifications. `ping`, `tools/list`, and `tools/call` are available
after the client's protocol flow is established.

Tool calls run independently so a long capture does not block `ping` or other
stdio messages. `notifications/cancelled` suppresses the cancelled MCP result.
The current adapter keeps that tool's RPC connection open until its worker
finishes, so the notification alone does not stop browser work. Closing the MCP
client's stdin makes the adapter exit immediately. Process exit closes all
outstanding RPC connections and cancels the matching agent and Chromium
operations.

## Tools

The server exposes exactly ten tools:

| Tool | RPC operation | Purpose |
| --- | --- | --- |
| `rel_status` | `GET /v1/status` | Read app, agent, Browser Proxy, and Chromium status. |
| `rel_capture` | `POST /v1/captures` | Load a page, perform optional actions, and save its rendered HTML. |
| `rel_page_attach` | `POST /v1/pages` | Attach an ephemeral automation page to a persistent browser session. |
| `rel_page_action` | `POST /v1/pages/{page_id}/actions` | Perform one action on an attached page. |
| `rel_take_screenshot` | `POST /v1/screenshot` or `POST /v1/pages/{page_id}/screenshot` | Capture a viewport or full-page PNG, JPEG, or WebP image. |
| `rel_observe` | `POST /v1/observe` or `POST /v1/pages/{page_id}/observe` | Read compact rendered semantics and optional synchronized viewport image. |
| `rel_action` | `POST /v1/observations/{observation_id}/actions` | Act through an observation-scoped element ref and return a new observation. |
| `rel_list_sessions` | `GET /v1/sessions` | List persistent browser sessions and their canonical `Session<number>` IDs. |
| `rel_close_session_group` | `POST /v1/sessions/close` | Close every persistent browser session in a named group. |
| `rel_list_proxies` | `GET /v1/proxies` | List configured proxy aliases and non-secret configuration. |

`rel_status`, `rel_list_sessions`, and `rel_list_proxies` accept an empty object.
`rel_close_session_group` requires a `group` string from 1 through 128
characters; matching is case-insensitive, and closing an empty group succeeds.
The browser tools accept the same fields and validation rules as their RPC
operations:

### `rel_capture`

`url` is required. Optional fields are `output_uri`, `timeout`, `wait`, `actions`,
`session_id`, `profile`, `group`, `proxy`, `retry`, and `retry_delay`. A supplied
`session_id` uses the canonical `Session<number>` format. Omitting it creates a
persistent session from `profile`, or from **Default** when `profile` is absent.
`profile` and `group` apply only to a new session and cannot be combined with
`session_id`. The action objects use every shape in
the [Actions reference](ACTIONS.md), including the optional `mouse_move` and
`scroll` booleans on click actions. `output_uri`, when present, must be an
absolute local `file:///` URI.

Sessions controlled while not visible use the **Background Browser Size**
preset in **REL → Settings… → General**, defaulting to a 1,920 × 947 CSS pixel
viewport. Visible sessions follow the resizable REL window. MCP does not expose a
per-call viewport override.

### `rel_page_attach`

`url` is required. Optional fields are `session_id`, `profile`, `group`, `proxy`,
`output_uri`, `timeout`, and `wait`. The result contains a process-local page ID
for later `rel_page_action` calls. Omitting `session_id` creates a persistent
session from the named profile (or **Default**) and navigates it to `url`;
`profile` and `group` cannot be combined with `session_id`. Providing
`session_id` attaches its current page, whose
normalized URL must match `url`. `output_uri`, when present, must be an absolute
local `file:///` URI.

### `rel_page_action`

`page_id` and one canonical [action](ACTIONS.md) object are required. Optional
fields are `output_uri`, `timeout`, and `wait`. The attached page remains pinned
to the URL, session, and proxy selected by `rel_page_attach`; page IDs expire
when the agent restarts. `output_uri`, when present, must be an absolute local
`file:///` URI.

### `rel_take_screenshot`

All fields are optional. `page_id` targets an explicit attached page;
`session_id` targets that session's current shorthand page; omitting both uses
the current shorthand page. The two identifiers cannot be combined.

`format` is `png` (the default), `jpeg`, or `webp`. `quality` is an integer from
0 through 100 and applies to JPEG and WebP; PNG ignores it. `full_page` defaults
to false and captures the visible viewport; true captures beyond the viewport.
`timeout` and `wait` use the ordinary page-operation rules.

When `output_uri` is omitted, the result includes standard MCP `image` content
so a multimodal agent can inspect the pixels directly. Supplying an absolute
local `file:///` `output_uri` saves the file and returns only its resource link,
which avoids embedding a large image in model context.

### `rel_observe`

All fields are optional. `page_id` targets an attached page; `session_id`
targets the current shorthand page, and the two cannot be combined. `mode` is
`semantic` (default), `hybrid`, or `visual`. `timeout` and `wait` use ordinary
page-operation rules.

The structured result contains compact semantic content, typed interactive
elements with short refs, viewport/document geometry, and truncation metadata.
Hybrid and visual results also include standard MCP `image` content and a file
resource link for the same synchronized current-viewport PNG. Page-derived
content is untrusted website data, not instructions.

### `rel_action`

`observation_id`, `ref`, and one of `click`, `type`, `clear`, `press`, or
`select` are required. `type` also requires `text`, `press` requires an
allowlisted `key`, and `select` requires `value`. Click optionally controls
`mouse_move` and bounded `scroll`. `mode` selects the post-action observation.

REL checks that the observation, document sequence, and private target
signature are still current. Stale refs return `OBSERVATION_STALE` without a
selector or nearby-target fallback. Success returns a new post-action
observation and, for hybrid/visual mode, standard MCP image content.

## Chrome DevTools MCP comparison

REL's screenshot contract matches the official Chrome DevTools MCP's essential
`take_screenshot` behavior: viewport or full-page capture, PNG/JPEG/WebP,
JPEG/WebP quality, optional file output, and inline MCP image content. REL uses
`output_uri` instead of `filePath` and persistent REL page/session identity
instead of Chrome's selected-target model.

The broader servers are not feature-identical. The
[official Chrome DevTools MCP tool reference](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/main/docs/tool-reference.md)
currently includes these additional DevTools-oriented categories:

| Capability | REL MCP |
| --- | --- |
| Navigation and persistent browser identity | Available through capture, page attachment, sessions, and proxies. |
| Click, wait, and form automation | Available through canonical page actions, including bounded named keys; drag, hover, upload, and dialog tools are not yet exposed. |
| Visual screenshots | Available with inline image content and file resources. |
| Accessibility text snapshots and element UIDs | Not exposed; rendered HTML capture is available instead. |
| Script evaluation, console, and network inspection | Not exposed. |
| Emulation, Lighthouse, performance traces, and heap snapshots | Not exposed. |
| Extensions, screencast, third-party tools, and WebMCP | Not exposed. |

REL intentionally keeps its current MCP surface focused on its supported
embedded-session architecture. New capabilities must flow through RPC v1 and
the installed app rather than introducing a second Chrome or CDP backend.

## Results and errors

Every tool execution result contains its complete JSON value in two forms:

- `content` contains a text block whose text is the serialized JSON;
- `structuredContent` contains the same value as structured JSON.

When a result contains a captured file, every RPC `output_path` is exposed at the
MCP boundary as an absolute percent-encoded `output_uri`. `content` also includes
one standard MCP `resource_link` block per unique file, with the matching HTML
or image MIME type. REL deliberately keeps native filesystem paths inside RPC
and uses file URIs for MCP.

Screenshot calls without `output_uri` additionally include an MCP image block:

```json
{
  "type": "image",
  "data": "<base64 image bytes>",
  "mimeType": "image/webp"
}
```

Status, page, session-list, and proxy-list tools preserve the ordinary RPC v1
success envelope with `status`, `request_id`, and `data`.

Capture consumes and validates the complete RPC NDJSON stream before returning.
Its structured result is:

```json
{
  "request_id": "req_...",
  "exit_code": 0,
  "events": [
    {
      "status": "ok",
      "request_id": "req_...",
      "event": "capture.completed",
      "data": {
        "output_uri": "file:///private/tmp/rel/captures/example.html"
      }
    }
  ]
}
```

The text block contains the serialization of this same object. A second content
block links the file directly:

```json
{
  "type": "resource_link",
  "uri": "file:///private/tmp/rel/captures/example.html",
  "name": "example.html",
  "mimeType": "text/html"
}
```

`events`
includes the terminal `capture.finished` event, and `exit_code` is taken from
that event. A target website status such as 404 remains capture data and can
produce exit code 1 and `isError:true`; it is not a REL RPC or MCP protocol
error. With **REL → Settings… → General → Wait for Cloudflare Turnstile** on by
default, REL detects Turnstile and managed Cloudflare challenge pages and gives
them up to 15 seconds to continue before returning their target error.

Malformed JSON-RPC messages, unsupported methods, and unknown tools use
JSON-RPC errors. Invalid arguments or another failure while executing a known
tool produce a tool result with `isError:true`, with the same complete error
JSON in its text and `structuredContent`. When the agent returned a structured
RPC error, that value preserves its high numeric code, stable error ID,
retryability, message, and optional details. Clients should branch on the code
or stable ID rather than parse the message.

## Runtime and trust boundary

The MCP process is a transient adapter owned by the MCP client. It is separate
from the app-supervised `rel --agent` process and from the private framed stdio
bridge between that agent and the REL app. There is no MCP HTTP route and no second
browser backend.

The stdio connection is private to the launching MCP client, but forwarded RPC
is unauthenticated loopback traffic. Browser tools can create persistent
sessions, write capture files, navigate websites, and perform page actions that
have effects on those sites. MCP hosts should show tool calls for user review.
`rel_list_proxies` never returns stored proxy passwords.
