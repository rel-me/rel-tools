from __future__ import annotations

import json
import threading
import unittest
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from rel_crawler import RelClient, RelRpcError


class _Server(ThreadingHTTPServer):
    responses: deque[tuple[int, dict[str, Any]]]
    requests: list[tuple[str, str, dict[str, Any] | None]]


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self._handle()

    def do_POST(self) -> None:
        self._handle()

    def _handle(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b""
        payload = json.loads(raw) if raw else None
        self.server.requests.append(  # type: ignore[attr-defined]
            (self.command, self.path, payload)
        )
        status, response = self.server.responses.popleft()  # type: ignore[attr-defined]
        body = json.dumps(response).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        return None


class RelClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = _Server(("127.0.0.1", 0), _Handler)
        self.server.responses = deque()
        self.server.requests = []
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.client = RelClient(f"http://{host}:{port}/v1")

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_navigate_uses_rpc_v1_and_parses_page_operation(self) -> None:
        self.server.responses.append(
            (
                200,
                {
                    "status": "ok",
                    "request_id": "req_1",
                    "data": {
                        "page": {
                            "id": "page_1",
                            "session_id": "Session2",
                            "url": "https://example.com/",
                        },
                        "capture": {
                            "output_path": "/tmp/page.html",
                            "bytesize": 42,
                            "target_http_status": 200,
                        },
                    },
                },
            )
        )

        result = self.client.navigate(
            url="https://example.com",
            session_id="Session2",
            output=Path("/tmp/page.html"),
            timeout=10,
            wait=0,
        )

        self.assertEqual(result.page_id, "page_1")
        self.assertEqual(result.bytesize, 42)
        method, path, payload = self.server.requests[0]
        self.assertEqual((method, path), ("POST", "/v1/navigate"))
        self.assertEqual(payload["session_id"], "Session2")  # type: ignore[index]

    def test_structured_http_error_is_preserved(self) -> None:
        self.server.responses.append(
            (
                503,
                {
                    "status": "error",
                    "request_id": "req_busy",
                    "error": {
                        "id": "BROWSER_BUSY",
                        "code": 10201,
                        "message": "busy",
                        "retryable": True,
                        "details": {"session_id": "Session2"},
                    },
                },
            )
        )

        with self.assertRaises(RelRpcError) as raised:
            self.client.health()

        self.assertEqual(raised.exception.id, "BROWSER_BUSY")
        self.assertEqual(raised.exception.code, 10201)
        self.assertTrue(raised.exception.retryable)
        self.assertEqual(raised.exception.request_id, "req_busy")

    def test_create_session_sends_profile_and_group(self) -> None:
        self.server.responses.append(
            (
                200,
                {
                    "status": "ok",
                    "request_id": "req_session",
                    "data": {
                        "session": {
                            "id": "Session9",
                            "profile": "Research",
                        }
                    },
                },
            )
        )

        session_id = self.client.create_session(profile="Research", group="crawler")

        self.assertEqual(session_id, "Session9")
        method, path, payload = self.server.requests[0]
        self.assertEqual((method, path), ("POST", "/v1/sessions"))
        self.assertEqual(payload, {"profile": "Research", "group": "crawler"})

    def test_rejects_non_loopback_base_url(self) -> None:
        with self.assertRaises(ValueError):
            RelClient("https://api.example.com/v1")


if __name__ == "__main__":
    unittest.main()
