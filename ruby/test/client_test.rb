# frozen_string_literal: true

require "minitest/autorun"
require "socket"
require "timeout"

require "rel"

class FakeServer
  Request = Struct.new(:method, :path, :headers, :body, keyword_init: true)

  attr_reader :requests

  def initialize(*responses)
    @responses = responses
    @requests = Queue.new
    @server = TCPServer.new("127.0.0.1", 0)
    @thread = Thread.new { serve }
  end

  def base_url
    "http://127.0.0.1:#{@server.addr[1]}/v1"
  end

  def pop_request
    Timeout.timeout(2) { requests.pop }
  end

  def close
    @thread.join(2)
    @server.close unless @server.closed?
  end

  private

  def serve
    @responses.each do |response|
      socket = @server.accept
      request_line = socket.gets
      method, path, = request_line.split
      headers = {}
      while (line = socket.gets)
        break if line == "\r\n"

        key, value = line.split(":", 2)
        headers[key.downcase] = value.strip
      end
      length = headers.fetch("content-length", "0").to_i
      body = length.positive? ? socket.read(length) : ""
      requests << Request.new(method: method, path: path, headers: headers, body: body)
      socket.write(response)
      socket.close
    end
  rescue IOError, Errno::EBADF
    nil
  ensure
    @server.close unless @server.closed?
  end
end

class RELClientTest < Minitest::Test
  def setup
    @server = nil
  end

  def teardown
    @server&.close
  end

  def test_local_honors_valid_agent_port_and_rejects_invalid_one
    original = ENV["REL_AGENT_PORT"]
    ENV["REL_AGENT_PORT"] = "43123"
    assert_equal "http://127.0.0.1:43123/v1", REL::Client.local.base_url

    ENV["REL_AGENT_PORT"] = "not-a-port"
    assert_equal "http://127.0.0.1:17319/v1", REL::Client.local.base_url
  ensure
    ENV["REL_AGENT_PORT"] = original
  end

  def test_parses_a_success_response_and_preserves_request_id
    @server = FakeServer.new(json_response(200, "req-1", data: { "version" => "1.2.3" }))
    response = client.health

    assert_equal "ok", response.status
    assert_equal "req-1", response.request_id
    assert_equal({ "version" => "1.2.3" }, response.data)
    request = @server.pop_request
    assert_equal "GET", request.method
    assert_equal "/v1/health", request.path
  end

  def test_sends_json_and_percent_encodes_a_resource_identifier
    @server = FakeServer.new(json_response(200, "req-2", data: { "proxy" => {} }))
    client.update_proxy("office west/1", username: nil)

    request = @server.pop_request
    assert_equal "PATCH", request.method
    assert_equal "/v1/proxies/office%20west%2F1", request.path
    assert_equal({ "username" => nil }, JSON.parse(request.body))
    assert_equal "application/json", request.headers["content-type"]
  end

  def test_raises_a_structured_rpc_error
    @server = FakeServer.new(
      json_response(
        404,
        "req-3",
        status: "error",
        error: {
          "id" => "SESSION_NOT_FOUND",
          "code" => 10_100,
          "message" => "Browser session Session404 was not found.",
          "retryable" => false,
          "details" => { "id" => "Session404" }
        }
      )
    )

    error = assert_raises(REL::RPCError) { client.get_session("Session404") }
    assert_equal "SESSION_NOT_FOUND", error.id
    assert_equal 10_100, error.code
    assert_equal false, error.retryable
    assert_equal({ "id" => "Session404" }, error.details)
    assert_equal "req-3", error.request_id
    assert_equal 404, error.http_status
  end

  def test_rejects_a_request_id_mismatch
    @server = FakeServer.new(
      http_response(
        200,
        "application/json",
        JSON.generate("status" => "ok", "request_id" => "body-id", "data" => {}),
        request_id: "header-id"
      )
    )

    error = assert_raises(REL::ProtocolError) { client.status }
    assert_match(/request ID mismatch/, error.message)
  end

  def test_rejects_a_known_error_id_with_the_wrong_code
    @server = FakeServer.new(
      json_response(
        400,
        "req-invalid-code",
        status: "error",
        error: {
          "id" => "VALIDATION_FAILED",
          "code" => 10_999,
          "message" => "Invalid request.",
          "retryable" => false
        }
      )
    )

    error = assert_raises(REL::ProtocolError) { client.create_session }
    assert_match(/incomplete error object/, error.message)
  end

  def test_streams_capture_events_and_records_the_exit_code
    events = [
      {
        "status" => "ok",
        "request_id" => "req-stream",
        "event" => "capture.started",
        "data" => { "url" => "https://example.com/", "session_id" => "Session1" }
      },
      {
        "status" => "ok",
        "request_id" => "req-stream",
        "event" => "capture.finished",
        "data" => { "exit_code" => 0 }
      }
    ]
    body = events.map { |event| JSON.generate(event) }.join("\n") + "\n"
    @server = FakeServer.new(
      http_response(200, "application/x-ndjson", body, request_id: "req-stream")
    )

    stream = client.capture(url: "https://example.com")
    assert_equal %w[capture.started capture.finished], stream.map(&:event)
    assert_equal "req-stream", stream.request_id
    assert_equal 0, stream.exit_code
    assert stream.finished?
    assert_raises(REL::ProtocolError) { stream.to_a }

    request = @server.pop_request
    assert_equal "/v1/captures", request.path
    assert_equal({ "url" => "https://example.com" }, JSON.parse(request.body))
  end

  def test_exposes_in_stream_rpc_errors_without_losing_the_finished_event
    events = [
      {
        "status" => "error",
        "request_id" => "req-stream-error",
        "event" => "capture.failed",
        "error" => {
          "id" => "UPSTREAM_UNAVAILABLE",
          "code" => 10_300,
          "message" => "The target was unavailable.",
          "retryable" => true
        }
      },
      {
        "status" => "ok",
        "request_id" => "req-stream-error",
        "event" => "capture.finished",
        "data" => { "exit_code" => 1 }
      }
    ]
    body = events.map { |event| JSON.generate(event) }.join("\n") + "\n"
    @server = FakeServer.new(
      http_response(200, "application/x-ndjson", body, request_id: "req-stream-error")
    )

    stream = client.capture(url: "https://example.com")
    received = stream.to_a
    assert_instance_of REL::RPCError, received.first.error
    assert_equal "UPSTREAM_UNAVAILABLE", received.first.error.id
    assert received.first.error.retryable
    assert_equal 1, stream.exit_code
  end

  def test_raises_a_structured_error_for_capture_preflight_failure
    @server = FakeServer.new(
      json_response(
        422,
        "req-preflight",
        status: "error",
        error: {
          "id" => "VALIDATION_FAILED",
          "code" => 10_005,
          "message" => "The URL is required.",
          "retryable" => false
        }
      )
    )

    error = assert_raises(REL::RPCError) { client.capture(url: "").to_a }
    assert_equal "VALIDATION_FAILED", error.id
    assert_equal "req-preflight", error.request_id
    assert_equal 422, error.http_status
  end

  def test_rejects_a_truncated_capture_stream
    body = JSON.generate(
      "status" => "ok",
      "request_id" => "req-truncated",
      "event" => "capture.started",
      "data" => {}
    )
    @server = FakeServer.new(
      http_response(200, "application/x-ndjson", body, request_id: "req-truncated")
    )

    error = assert_raises(REL::ProtocolError) do
      client.capture(url: "https://example.com").to_a
    end
    assert_match(/before capture.finished/, error.message)
  end

  def test_validates_configuration_and_payloads
    assert_raises(ArgumentError) { REL::Client.new("not a URL") }
    assert_raises(ArgumentError) { REL::Client.new("http://localhost/v1", request_timeout: 0) }
    assert_raises(ArgumentError) { REL::Client.local.navigate("https://example.com") }
    assert_raises(ArgumentError) { REL::Client.local.get_session("") }
  end

  private

  def client
    REL::Client.new(@server.base_url)
  end

  def json_response(code, request_id, status: "ok", data: nil, error: nil)
    payload = { "status" => status, "request_id" => request_id }
    payload["data"] = data if status == "ok"
    payload["error"] = error if status == "error"
    http_response(code, "application/json", JSON.generate(payload), request_id: request_id)
  end

  def http_response(code, content_type, body, request_id:)
    reason = code == 200 ? "OK" : "Error"
    [
      "HTTP/1.1 #{code} #{reason}",
      "Content-Type: #{content_type}",
      "Content-Length: #{body.bytesize}",
      "X-Request-Id: #{request_id}",
      "Connection: close",
      "",
      body
    ].join("\r\n")
  end
end
