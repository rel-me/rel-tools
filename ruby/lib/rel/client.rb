# frozen_string_literal: true

require "json"
require "net/http"
require "uri"

module REL
  DEFAULT_AGENT_PORT = 17_319
  DEFAULT_REQUEST_TIMEOUT = 10
  MAX_CLIENT_TIMEOUT = 7 * 24 * 60 * 60
  RPC_ERROR_CODES = {
    "INVALID_REQUEST" => 10_000,
    "ROUTE_NOT_FOUND" => 10_001,
    "METHOD_NOT_ALLOWED" => 10_002,
    "PAYLOAD_TOO_LARGE" => 10_003,
    "UNSUPPORTED_MEDIA_TYPE" => 10_004,
    "VALIDATION_FAILED" => 10_005,
    "UNSUPPORTED_MODALITY" => 10_006,
    "OBSERVATION_TOO_LARGE" => 10_007,
    "SESSION_NOT_FOUND" => 10_100,
    "PAGE_NOT_FOUND" => 10_101,
    "PAGE_MISMATCH" => 10_102,
    "PROXY_NOT_FOUND" => 10_103,
    "ACTIVE_PAGE_NOT_FOUND" => 10_104,
    "CONFLICT" => 10_200,
    "BROWSER_BUSY" => 10_201,
    "NETWORK_PAUSED" => 10_202,
    "ACTION_TARGET_NOT_FOUND" => 10_203,
    "REQUEST_CANCELLED" => 10_204,
    "RATE_LIMITED" => 10_205,
    "ACTION_TIMEOUT" => 10_206,
    "OBSERVATION_STALE" => 10_207,
    "PRO_REQUIRED" => 10_208,
    "UPSTREAM_UNAVAILABLE" => 10_300,
    "BROWSER_UNAVAILABLE" => 10_301,
    "AGENT_UNHEALTHY" => 10_302,
    "TIMEOUT" => 10_303,
    "PROXY_CONFIGURATION_FAILED" => 10_304,
    "BROWSER_CREATION_FAILED" => 10_305,
    "SEMANTIC_EXTRACTION_FAILED" => 10_306,
    "INTERNAL_ERROR" => 10_999
  }.freeze

  Response = Struct.new(:status, :request_id, :data, keyword_init: true)

  CaptureEvent = Struct.new(
    :status,
    :request_id,
    :event,
    :data,
    :error,
    keyword_init: true
  )

  class Error < StandardError; end
  class TransportError < Error; end
  class ProtocolError < Error; end

  class RPCError < Error
    attr_reader :id, :code, :retryable, :details, :request_id, :http_status

    def initialize(id:, code:, message:, retryable:, details:, request_id:, http_status:)
      super("#{id}: #{message}")
      @id = id
      @code = code
      @retryable = retryable
      @details = details
      @request_id = request_id
      @http_status = http_status
    end

    def to_h
      {
        "id" => id,
        "code" => code,
        "message" => message.delete_prefix("#{id}: "),
        "retryable" => retryable,
        "details" => details
      }.compact
    end
  end

  class CaptureStream
    include Enumerable

    attr_reader :request_id, :exit_code

    def initialize(&operation)
      @operation = operation
      @consumed = false
      @finished = false
    end

    def each
      return enum_for(:each) unless block_given?
      raise ProtocolError, "REL capture stream has already been consumed" if @consumed

      @consumed = true
      @operation.call(self) { |event| yield event }
      self
    end

    def finished?
      @finished
    end

    def start(request_id)
      @request_id = request_id
    end

    def finish(exit_code)
      @exit_code = exit_code
      @finished = true
    end
  end

  class Client
    attr_reader :base_url, :open_timeout, :request_timeout

    def self.local(**options)
      port = Integer(ENV.fetch("REL_AGENT_PORT", DEFAULT_AGENT_PORT), exception: false)
      port = DEFAULT_AGENT_PORT unless port&.between?(1, 65_535)
      new("http://127.0.0.1:#{port}/v1", **options)
    end

    def initialize(base_url, open_timeout: DEFAULT_REQUEST_TIMEOUT,
                   request_timeout: DEFAULT_REQUEST_TIMEOUT)
      @base_url = base_url.to_s.sub(%r{/+\z}, "")
      @open_timeout = positive_timeout(open_timeout, "open_timeout")
      @request_timeout = positive_timeout(request_timeout, "request_timeout")
      validate_base_url!
    end

    def health
      request_json(:get, "/health")
    end

    def status
      request_json(:get, "/status")
    end

    def list_notifications
      request_json(:get, "/notifications")
    end

    def navigate(payload)
      page_request(:post, "/navigate", payload)
    end

    def navigate_and_observe(payload)
      page_request(:post, "/navigate/observe", payload)
    end

    def perform(payload)
      page_request(:post, "/perform", payload)
    end

    def capture_current_page(payload = {})
      page_request(:post, "/capture", payload)
    end

    def screenshot_current_page(payload = {})
      page_request(:post, "/screenshot", payload)
    end

    def observe_current_page(payload = {})
      page_request(:post, "/observe", payload)
    end

    def capture(payload)
      validate_payload!(payload)
      stream = CaptureStream.new do |capture_stream, &emit|
        stream_capture(payload, capture_stream, &emit)
      end
      return stream unless block_given?

      stream.each { |event| yield event }
      stream
    end

    def attach_page(payload)
      page_request(:post, "/pages", payload)
    end

    def perform_page_action(page_id, payload)
      page_request(:post, "/pages/#{segment(page_id)}/actions", payload)
    end

    def take_page_screenshot(page_id, payload = {})
      page_request(:post, "/pages/#{segment(page_id)}/screenshot", payload)
    end

    def observe_page(page_id, payload = {})
      page_request(:post, "/pages/#{segment(page_id)}/observe", payload)
    end

    def perform_observation_action(observation_id, payload)
      page_request(:post, "/observations/#{segment(observation_id)}/actions", payload)
    end

    def find_in_observation(observation_id, payload)
      request_json(:post, "/observations/#{segment(observation_id)}/find", body: payload)
    end

    def get_observation(observation_id)
      request_json(:get, "/observations/#{segment(observation_id)}")
    end

    def list_proxies
      request_json(:get, "/proxies")
    end

    def get_proxy(alias_name)
      request_json(:get, "/proxies/#{segment(alias_name)}")
    end

    def create_proxy(payload)
      request_json(:post, "/proxies", body: payload)
    end

    def update_proxy(alias_name, payload)
      request_json(:patch, "/proxies/#{segment(alias_name)}", body: payload)
    end

    def delete_proxy(alias_name)
      request_json(:delete, "/proxies/#{segment(alias_name)}")
    end

    def rotate_proxy_session(alias_name)
      request_json(:post, "/proxies/#{segment(alias_name)}/rotate-session", body: {})
    end

    def export_proxy_transfer(payload)
      request_json(:post, "/proxy-transfers/export", body: payload)
    end

    def import_proxy_transfer(payload)
      request_json(:post, "/proxy-transfers/import", body: payload)
    end

    def list_sessions
      request_json(:get, "/sessions")
    end

    def get_session(session_id)
      request_json(:get, "/sessions/#{segment(session_id)}")
    end

    def create_session(payload = {})
      request_json(:post, "/sessions", body: payload)
    end

    def update_session(session_id, payload)
      request_json(:patch, "/sessions/#{segment(session_id)}", body: payload)
    end

    def ping_session(session_id)
      request_json(:post, "/sessions/#{segment(session_id)}/ping", body: {})
    end

    def pause_session(session_id)
      request_json(:post, "/sessions/#{segment(session_id)}/pause", body: {})
    end

    def play_session(session_id)
      request_json(:post, "/sessions/#{segment(session_id)}/play", body: {})
    end

    def delete_session(session_id)
      request_json(:delete, "/sessions/#{segment(session_id)}")
    end

    def close_session_group(group)
      request_json(:post, "/sessions/close", body: { group: group })
    end

    def list_profiles
      request_json(:get, "/profiles")
    end

    def create_profile(payload)
      request_json(:post, "/profiles", body: payload)
    end

    def update_profile_data(profile_id, payload)
      request_json(:patch, "/profiles/#{segment(profile_id)}", body: payload)
    end

    def delete_profile(profile_id)
      request_json(:delete, "/profiles/#{segment(profile_id)}")
    end

    def export_profile_transfer(payload)
      request_json(:post, "/profile-transfers/export", body: payload)
    end

    def import_profile_transfer(payload)
      request_json(:post, "/profile-transfers/import", body: payload)
    end

    private

    REQUEST_CLASSES = {
      get: Net::HTTP::Get,
      post: Net::HTTP::Post,
      patch: Net::HTTP::Patch,
      delete: Net::HTTP::Delete
    }.freeze

    def page_request(method, path, payload)
      validate_payload!(payload)
      request_json(method, path, body: payload, read_timeout: page_timeout(payload))
    end

    def request_json(method, path, body: nil, read_timeout: request_timeout)
      response = send_request(method, path, body: body, read_timeout: read_timeout)
      content_type = response["Content-Type"].to_s.downcase
      unless content_type.start_with?("application/json")
        raise ProtocolError, "REL RPC returned unsupported Content-Type #{content_type.inspect}"
      end

      payload = parse_json(response.body.to_s, "REL RPC response")
      if response.code.to_i.between?(200, 299)
        parse_success(response, payload)
      else
        raise rpc_error(response, payload)
      end
    end

    def stream_capture(payload, stream)
      timeout = capture_timeout(payload)
      uri = request_uri("/captures")
      request = build_request(:post, uri, payload)
      http_for(uri, timeout).start do |http|
        http.request(request) do |response|
          unless response.code.to_i.between?(200, 299)
            content_type = response["Content-Type"].to_s.downcase
            unless content_type.start_with?("application/json")
              raise ProtocolError,
                    "REL RPC returned unsupported Content-Type #{content_type.inspect}"
            end
            body = String.new
            response.read_body { |chunk| body << chunk }
            error_payload = parse_json(body, "REL RPC error response")
            raise rpc_error(response, error_payload)
          end

          content_type = response["Content-Type"].to_s.downcase
          unless content_type.start_with?("application/x-ndjson")
            raise ProtocolError,
                  "REL capture returned unsupported Content-Type #{content_type.inspect}"
          end

          request_id = response["X-Request-Id"].to_s
          raise ProtocolError, "REL capture response is missing X-Request-Id" if request_id.empty?

          stream.start(request_id)
          read_capture_body(response, stream) { |event| yield event }
        end
      end
    rescue Net::OpenTimeout, Net::ReadTimeout, SocketError, EOFError, IOError, SystemCallError => e
      raise TransportError, "REL RPC transport failed: #{e.message}"
    end

    def read_capture_body(response, stream)
      buffer = String.new
      response.read_body do |chunk|
        buffer << chunk
        while (newline = buffer.index("\n"))
          line = buffer.slice!(0, newline + 1).strip
          yield parse_capture_event(line, stream) unless line.empty?
        end
      end
      line = buffer.strip
      yield parse_capture_event(line, stream) unless line.empty?
      return if stream.finished?

      raise ProtocolError, "REL capture stream ended before capture.finished"
    end

    def parse_capture_event(line, stream)
      payload = parse_json(line, "REL capture event")
      raise ProtocolError, "REL capture event must be a JSON object" unless payload.is_a?(Hash)

      request_id = payload["request_id"]
      unless request_id == stream.request_id
        raise ProtocolError,
              "REL capture request ID mismatch: header #{stream.request_id.inspect}, " \
              "event #{request_id.inspect}"
      end

      event_name = payload["event"]
      unless event_name.is_a?(String) && !event_name.empty?
        raise ProtocolError, "REL capture event is missing its event name"
      end

      status = payload["status"]
      error = nil
      if status == "ok" && !payload["data"].nil? && payload["error"].nil?
        data = payload["data"]
      elsif status == "error" && payload.key?("error")
        data = payload["data"]
        error = build_rpc_error(payload["error"], request_id: request_id, http_status: 200)
      else
        raise ProtocolError, "REL capture event #{event_name.inspect} has an invalid envelope"
      end

      if event_name == "capture.finished"
        exit_code = data.is_a?(Hash) ? data["exit_code"] : nil
        unless exit_code.is_a?(Integer)
          raise ProtocolError, "REL capture.finished event is missing a valid exit_code"
        end
        stream.finish(exit_code)
      end

      CaptureEvent.new(
        status: status,
        request_id: request_id,
        event: event_name,
        data: data,
        error: error
      )
    end

    def send_request(method, path, body:, read_timeout:)
      uri = request_uri(path)
      request = build_request(method, uri, body)
      http_for(uri, read_timeout).request(request)
    rescue Net::OpenTimeout, Net::ReadTimeout, SocketError, EOFError, IOError, SystemCallError => e
      raise TransportError, "REL RPC transport failed: #{e.message}"
    end

    def build_request(method, uri, body)
      request_class = REQUEST_CLASSES.fetch(method) do
        raise ArgumentError, "unsupported HTTP method #{method.inspect}"
      end
      request = request_class.new(uri)
      request["Accept"] = "application/json, application/x-ndjson"
      request["Connection"] = "close"
      unless body.nil?
        validate_payload!(body)
        request["Content-Type"] = "application/json"
        request.body = JSON.generate(body)
      end
      request
    rescue JSON::GeneratorError => e
      raise ProtocolError, "REL RPC request is not valid JSON: #{e.message}"
    end

    def http_for(uri, read_timeout)
      Net::HTTP.new(uri.host, uri.port).tap do |http|
        http.use_ssl = uri.scheme == "https"
        http.open_timeout = open_timeout
        http.read_timeout = read_timeout
      end
    end

    def parse_success(response, payload)
      unless payload.is_a?(Hash) && payload["status"] == "ok" && payload.key?("data")
        raise ProtocolError, "REL RPC success response has an invalid envelope"
      end
      validate_request_id!(response, payload["request_id"])
      Response.new(status: payload["status"], request_id: payload["request_id"], data: payload["data"])
    end

    def rpc_error(response, payload)
      unless payload.is_a?(Hash) && payload["status"] == "error"
        raise ProtocolError,
              "REL RPC returned HTTP #{response.code} with an invalid error envelope"
      end
      validate_request_id!(response, payload["request_id"])
      build_rpc_error(
        payload["error"],
        request_id: payload["request_id"],
        http_status: response.code.to_i
      )
    end

    def build_rpc_error(payload, request_id:, http_status:)
      valid = payload.is_a?(Hash) &&
              payload["id"].is_a?(String) && !payload["id"].empty? &&
              payload["code"].is_a?(Integer) && payload["code"] >= 10_000 &&
              payload["message"].is_a?(String) && !payload["message"].empty? &&
              [true, false].include?(payload["retryable"]) &&
              (!payload.key?("details") || payload["details"].nil? || payload["details"].is_a?(Hash))
      expected_code = payload.is_a?(Hash) ? RPC_ERROR_CODES[payload["id"]] : nil
      valid &&= expected_code.nil? || expected_code == payload["code"]
      raise ProtocolError, "REL RPC error response has an incomplete error object" unless valid

      RPCError.new(
        id: payload["id"],
        code: payload["code"],
        message: payload["message"],
        retryable: payload["retryable"],
        details: payload["details"],
        request_id: request_id,
        http_status: http_status
      )
    end

    def validate_request_id!(response, request_id)
      header = response["X-Request-Id"]
      if request_id.to_s.empty?
        raise ProtocolError, "REL RPC response is missing request_id"
      elsif header.nil? || header.empty?
        raise ProtocolError, "REL RPC response is missing X-Request-Id"
      elsif header != request_id
        raise ProtocolError,
              "REL RPC request ID mismatch: header #{header.inspect}, body #{request_id.inspect}"
      end
    end

    def parse_json(body, label)
      JSON.parse(body)
    rescue JSON::ParserError => e
      raise ProtocolError, "#{label} is not valid JSON: #{e.message}"
    end

    def page_timeout(payload)
      bounded_timeout(number(payload, :timeout, 90) + number(payload, :wait, 1) + 30, 120)
    end

    def capture_timeout(payload)
      timeout = number(payload, :timeout, 90)
      wait = number(payload, :wait, 1)
      retry_count = number(payload, :retry, 1)
      retry_delay = number(payload, :retry_delay, 3)
      attempts = retry_count + 1
      seconds = [timeout + wait + 30, 30].max * attempts + retry_delay * retry_count
      bounded_timeout(seconds, 180)
    end

    def number(payload, key, default)
      value = payload[key]
      value = payload[key.to_s] if value.nil?
      value.is_a?(Numeric) ? value : default
    end

    def bounded_timeout(value, fallback)
      value = fallback unless value.is_a?(Numeric) && value.finite? && value.positive?
      [value, MAX_CLIENT_TIMEOUT].min
    end

    def positive_timeout(value, name)
      unless value.is_a?(Numeric) && value.finite? && value.positive?
        raise ArgumentError, "#{name} must be a positive finite number"
      end
      value
    end

    def validate_payload!(payload)
      return if payload.is_a?(Hash)

      raise ArgumentError, "REL RPC payload must be a Hash"
    end

    def validate_base_url!
      uri = URI.parse(base_url)
      valid = %w[http https].include?(uri.scheme) && uri.host && uri.query.nil? && uri.fragment.nil?
      raise ArgumentError, "base_url must be an absolute HTTP(S) URL" unless valid
    rescue URI::InvalidURIError
      raise ArgumentError, "base_url must be an absolute HTTP(S) URL"
    end

    def request_uri(path)
      URI.parse("#{base_url}#{path}")
    end

    def segment(value)
      string = value.to_s
      raise ArgumentError, "resource identifier cannot be empty" if string.empty?

      string.b.bytes.map do |byte|
        character = byte.chr
        if character.match?(/[A-Za-z0-9_.~-]/)
          character
        else
          format("%%%02X", byte)
        end
      end.join
    end
  end
end
