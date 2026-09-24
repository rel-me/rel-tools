# REL Ruby client

`rel-client` is a dependency-free Ruby client for REL's local RPC v1 API. It
uses the REL-owned Chromium runtime and persistent browser sessions; it does not
launch another browser, read REL's database, or manage the app process.

REL.app must be installed and running. The client connects to the loopback-only
agent at `http://127.0.0.1:17319/v1` and honors `REL_AGENT_PORT`.

## Install

Until a RubyGems release is announced, install directly from the repository:

```ruby
# Gemfile
gem "rel-client",
    git: "https://github.com/rel-me/rel-tools.git",
    glob: "ruby/*.gemspec"
```

Then run `bundle install` and require the package:

```ruby
require "rel"
```

The gem supports Ruby 3.1 and newer and has no runtime dependencies outside the
Ruby standard library.

## Connect

```ruby
client = REL::Client.local
status = client.status

puts status.request_id
puts status.data.fetch("overall_status")
```

Use an explicit endpoint or transport deadlines when needed:

```ruby
client = REL::Client.new(
  "http://127.0.0.1:17319/v1",
  open_timeout: 5,
  request_timeout: 15
)
```

Browser methods derive a longer read deadline from the RPC payload's `timeout`,
`wait`, `retry`, and `retry_delay` fields. The configured `request_timeout`
continues to apply to ordinary resource operations.

## Browse with a persistent session

Requests and responses use plain Ruby hashes with the same field names as the
[RPC v1 contract](https://docs.rel.me/rpc/). Each successful call returns a
`REL::Response` containing `status`, `request_id`, and `data`.

```ruby
session = client.create_session(
  group: "research",
  lifetime: { type: "inactivity", timeout_seconds: 300 }
)
session_id = session.data.fetch("session").fetch("id")

client.navigate(
  url: "https://example.com",
  session_id: session_id
)

page = client.capture_current_page(session_id: session_id)
puts page.data.fetch("capture").fetch("output_path")

client.delete_session(session_id)
```

Use the canonical action objects for page interaction:

```ruby
client.perform(
  session_id: session_id,
  actions: [
    { action: "type", selector: "#search", text: "REL" },
    { action: "press", selector: "#search", key: "Enter" },
    { action: "wait", seconds: 0.5 }
  ]
)
```

## Stream a capture

`capture` returns a single-use `REL::CaptureStream`. It parses NDJSON as bytes
arrive instead of buffering the capture. The stream exposes its request ID once
the response starts and its exit code after `capture.finished`.

```ruby
stream = client.capture(
  url: "https://example.com",
  output: "/tmp/example.html",
  retry: 1
)

stream.each do |event|
  puts "#{event.event}: #{event.data.inspect}"
  warn event.error.message if event.error
end

abort "capture failed" unless stream.exit_code.zero?
```

The block form returns the consumed stream:

```ruby
stream = client.capture(url: "https://example.com") do |event|
  puts event.event
end
```

## Handle errors

Transport, protocol, and REL application failures are distinct:

```ruby
begin
  client.get_session("Session404")
rescue REL::RPCError => error
  warn "#{error.id} (#{error.code}): #{error.message}"
  retry if error.retryable
rescue REL::TransportError, REL::ProtocolError => error
  warn error.message
end
```

`REL::RPCError` also exposes `details`, `request_id`, and `http_status`. Branch on
the stable `id` or `code`; do not parse the human-readable message.

## API surface

The client provides one transport method for each route in the public RPC v1
route table:

- Health and status: `health`, `status`, `list_notifications`
- Current page: `navigate`, `navigate_and_observe`, `perform`,
  `capture_current_page`, `screenshot_current_page`, `observe_current_page`
- Capture stream: `capture`
- Attached pages: `attach_page`, `perform_page_action`,
  `take_page_screenshot`, `observe_page`
- Observations: `get_observation`, `perform_observation_action`,
  `find_in_observation`
- Proxies: `list_proxies`, `get_proxy`, `create_proxy`, `update_proxy`,
  `delete_proxy`, `rotate_proxy_session`, `export_proxy_transfer`,
  `import_proxy_transfer`
- Sessions: `list_sessions`, `get_session`, `create_session`, `update_session`,
  `ping_session`, `pause_session`, `play_session`, `delete_session`,
  `close_session_group`
- Profiles: `list_profiles`, `create_profile`, `update_profile_data`,
  `delete_profile`, `export_profile_transfer`, `import_profile_transfer`

Resource identifiers are percent-encoded as individual path segments. Request
objects remain closed and validated by REL according to the canonical contract.

## Develop

```sh
cd ruby
bundle install
bundle exec rake test
gem build rel-client.gemspec
```

The gem is MIT licensed. REL.app and the REL brand are not covered by that
license.
