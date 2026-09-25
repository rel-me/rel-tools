# REL Ruby SDK

`rel-client` is the Ruby client for REL RPC v1. It exposes the public browser,
observation, proxy, session, and profile routes with structured responses and
errors, plus incremental NDJSON capture streaming.

The gem source is available under the MIT license in
[`rel-me/rel-tools`](https://github.com/rel-me/rel-tools/tree/main/ruby). REL's
application source and internal runtime implementation are not publicly
distributed.

Related documents: [Actions](ACTIONS.md) and [RPC](RPC.md).

## Install

Until a RubyGems release is announced, add the repository gemspec to Bundler:

```ruby
gem "rel-client",
    git: "https://github.com/rel-me/rel-tools.git",
    glob: "ruby/*.gemspec"
```

The gem supports Ruby 3.1 and newer and uses only the Ruby standard library at
runtime.

## Connect

```ruby
require "rel"

client = REL::Client.local
status = client.status
puts status.data.fetch("overall_status")
```

`REL::Client.local` connects to `http://127.0.0.1:17319/v1` and honors
`REL_AGENT_PORT`. Pass an explicit RPC v1 base URL to `REL::Client.new` when a
test or worktree agent uses another endpoint:

```ruby
client = REL::Client.new(
  "http://127.0.0.1:17319/v1",
  open_timeout: 5,
  request_timeout: 15
)
```

The client is transport-only. It does not launch REL, read the app's SQLite
database, or access Chromium through another backend. Ensure REL.app and its
agent are running before making calls.

## Responses and errors

Methods accept the same request hashes documented by RPC v1. Ordinary calls
return `REL::Response`, whose `status`, `request_id`, and `data` readers preserve
the response envelope:

```ruby
sessions = client.list_sessions
sessions.data.fetch("sessions").each do |session|
  puts session.fetch("id")
end
```

REL application failures raise `REL::RPCError`. Branch on `id` or `code`, not
the human-readable message:

```ruby
begin
  client.get_session("Session404")
rescue REL::RPCError => error
  warn "#{error.id} (#{error.code}): #{error.message}"
  retry if error.retryable
end
```

The error also exposes `details`, `request_id`, and `http_status`.
`REL::TransportError` represents connection and timeout failures, while
`REL::ProtocolError` reports a response that does not satisfy the RPC contract.

## Use a persistent browser session

```ruby
session = client.create_session(
  group: "research",
  lifetime: { type: "inactivity", timeout_seconds: 300 }
)
session_id = session.data.fetch("session").fetch("id")

client.navigate(url: "https://example.com", session_id: session_id)
client.perform(
  session_id: session_id,
  actions: [
    { action: "type", selector: "#search", text: "REL" },
    { action: "press", selector: "#search", key: "Enter" }
  ]
)

page = client.capture_current_page(session_id: session_id)
puts page.data.fetch("capture").fetch("output_path")
```

See the [Actions reference](ACTIONS.md) for every supported action object. Page
operations derive their read deadline from the request's `timeout` and `wait`
values rather than the shorter ordinary request deadline.

## Stream a capture

`capture` returns a single-use `REL::CaptureStream`. Each iteration value is a
`REL::CaptureEvent`; the body is parsed as incremental NDJSON without buffering
the complete capture.

```ruby
stream = client.capture(
  url: "https://example.com",
  output: "/tmp/example.html",
  retry: 1
)

stream.each do |event|
  puts event.event
  warn event.error.message if event.error
end

abort "capture failed" unless stream.exit_code.zero?
```

Once the response starts, `stream.request_id` contains the validated request
ID. After `capture.finished`, `stream.exit_code` contains the capture result and
`stream.finished?` is true. Ending the response before that terminal event raises
`REL::ProtocolError`.

## Route methods

The Ruby client covers every route in the public [RPC route table](RPC.md#routes):

| Area | Methods |
| --- | --- |
| Agent | `health`, `status`, `list_notifications` |
| Current page | `navigate`, `navigate_and_observe`, `perform`, `capture_current_page`, `screenshot_current_page`, `observe_current_page` |
| Capture stream | `capture` |
| Attached pages | `attach_page`, `perform_page_action`, `take_page_screenshot`, `observe_page` |
| Observations | `get_observation`, `perform_observation_action`, `find_in_observation` |
| Proxies | `list_proxies`, `get_proxy`, `create_proxy`, `update_proxy`, `delete_proxy`, `rotate_proxy_session`, `export_proxy_transfer`, `import_proxy_transfer` |
| Sessions | `list_sessions`, `get_session`, `create_session`, `update_session`, `ping_session`, `pause_session`, `play_session`, `delete_session`, `close_session_group` |
| Profiles | `list_profiles`, `create_profile`, `update_profile_data`, `delete_profile`, `export_profile_transfer`, `import_profile_transfer` |

Resource identifiers are percent-encoded as individual path segments. The REL
agent remains the authority for closed request objects, field validation, and
stable RPC error semantics.
