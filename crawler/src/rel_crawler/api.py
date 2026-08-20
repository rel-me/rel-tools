"""Typed subset of REL's loopback RPC v1 API used by the crawler."""

from __future__ import annotations

import json
import os
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen


class RelError(Exception):
    """Base class for REL client failures."""


class RelTransportError(RelError):
    """REL's loopback HTTP endpoint could not be reached or decoded."""


class RelProtocolError(RelError):
    """REL returned a response that did not match the RPC v1 envelope."""


class RelRpcError(RelError):
    """A structured error returned by REL RPC v1."""

    def __init__(
        self,
        *,
        error_id: str,
        code: int,
        message: str,
        retryable: bool,
        details: dict[str, Any] | None,
        request_id: str | None,
        http_status: int | None,
    ) -> None:
        super().__init__(f"{error_id}: {message}")
        self.id = error_id
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = details
        self.request_id = request_id
        self.http_status = http_status


@dataclass(frozen=True, slots=True)
class PageOperation:
    page_id: str
    session_id: str
    url: str
    output_path: Path
    bytesize: int
    target_http_status: int | None


@dataclass(frozen=True, slots=True)
class NavigationOperation:
    page_id: str
    session_id: str
    url: str


class RelClient:
    """Synchronous REL RPC client with no third-party dependencies."""

    def __init__(self, base_url: str | None = None) -> None:
        if base_url is None:
            port = os.environ.get("REL_AGENT_PORT", "17319")
            base_url = f"http://127.0.0.1:{port}/v1"
        self.base_url = _validate_base_url(base_url)

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health", None, timeout=5.0)

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        try:
            data = self._request(
                "GET", f"/sessions/{quote(session_id, safe='')}", None, timeout=5.0
            )
        except RelRpcError as error:
            if error.id == "SESSION_NOT_FOUND":
                return None
            raise
        session = data.get("session")
        if not isinstance(session, dict):
            raise RelProtocolError("REL session response is missing data.session")
        return session

    def create_session(self, *, profile: str, group: str) -> str:
        data = self._request(
            "POST",
            "/sessions",
            {"profile": profile, "group": group},
            timeout=10.0,
        )
        session = data.get("session")
        session_id = session.get("id") if isinstance(session, dict) else None
        if not isinstance(session_id, str) or not session_id:
            raise RelProtocolError("REL session response is missing data.session.id")
        return session_id

    def delete_session(self, session_id: str) -> None:
        self._request(
            "DELETE", f"/sessions/{quote(session_id, safe='')}", None, timeout=10.0
        )

    def navigate(
        self,
        *,
        url: str,
        session_id: str,
        output: Path,
        timeout: float,
        wait: float,
    ) -> PageOperation:
        data = self._request(
            "POST",
            "/navigate",
            {
                "url": url,
                "session_id": session_id,
                "output": str(output),
                "timeout": timeout,
                "wait": wait,
            },
            timeout=_browser_timeout(timeout, wait),
        )
        return _page_operation(data)

    def perform(
        self,
        *,
        actions: list[dict[str, Any]],
        session_id: str,
        output: Path,
        timeout: float,
        wait: float,
    ) -> PageOperation:
        data = self._request(
            "POST",
            "/perform",
            {
                "actions": actions,
                "session_id": session_id,
                "output": str(output),
                "timeout": timeout,
                "wait": wait,
            },
            timeout=_browser_timeout(timeout, wait),
        )
        return _page_operation(data)

    def back(
        self, *, session_id: str, timeout: float, wait: float
    ) -> NavigationOperation:
        data = self._request(
            "POST",
            "/navigate/observe",
            {
                "navigation": "back",
                "session_id": session_id,
                "mode": "semantic",
                "timeout": timeout,
                "wait": wait,
            },
            timeout=_browser_timeout(timeout, wait),
        )
        return _navigation_operation(data)

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None,
        *,
        timeout: float,
    ) -> dict[str, Any]:
        body = None
        headers = {"Accept": "application/json", "Connection": "close"}
        if payload is not None:
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        http_status: int | None = None
        try:
            with urlopen(request, timeout=timeout) as response:
                http_status = response.status
                raw = response.read()
        except HTTPError as error:
            http_status = error.code
            try:
                raw = error.read()
            finally:
                error.close()
        except (URLError, TimeoutError, socket.timeout, OSError) as error:
            raise RelTransportError(
                f"Could not reach REL at {self.base_url}: {error}"
            ) from error

        try:
            envelope = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise RelProtocolError(
                f"REL returned invalid JSON with HTTP status {http_status}"
            ) from error
        if not isinstance(envelope, dict):
            raise RelProtocolError("REL RPC response must be a JSON object")
        request_id = envelope.get("request_id")
        if envelope.get("status") == "error":
            _raise_rpc_error(envelope, http_status)
        if envelope.get("status") != "ok":
            raise RelProtocolError("REL RPC response has an invalid status")
        data = envelope.get("data")
        if not isinstance(request_id, str) or not isinstance(data, dict):
            raise RelProtocolError(
                "REL success response is missing request_id or data"
            )
        return data


def _validate_base_url(base_url: str) -> str:
    value = base_url.rstrip("/")
    split = urlsplit(value)
    if split.scheme != "http" or split.hostname not in {
        "127.0.0.1",
        "localhost",
        "::1",
    }:
        raise ValueError("REL base URL must be an HTTP loopback URL")
    if split.username is not None or split.password is not None:
        raise ValueError("REL base URL must not include credentials")
    if split.path not in {"", "/v1"} or split.query or split.fragment:
        raise ValueError("REL base URL must end at the /v1 API root")
    root = f"{split.scheme}://{split.netloc}"
    return f"{root}/v1"


def _browser_timeout(timeout: float, wait: float) -> float:
    return max(timeout + wait + 15.0, 30.0)


def _raise_rpc_error(envelope: dict[str, Any], http_status: int | None) -> None:
    error = envelope.get("error")
    if not isinstance(error, dict):
        raise RelProtocolError("REL error response is missing error")
    error_id = error.get("id")
    code = error.get("code")
    message = error.get("message")
    retryable = error.get("retryable")
    details = error.get("details")
    request_id = envelope.get("request_id")
    if (
        not isinstance(error_id, str)
        or not isinstance(code, int)
        or not isinstance(message, str)
        or not isinstance(retryable, bool)
        or (details is not None and not isinstance(details, dict))
    ):
        raise RelProtocolError("REL returned a malformed RPC error")
    raise RelRpcError(
        error_id=error_id,
        code=code,
        message=message,
        retryable=retryable,
        details=details,
        request_id=request_id if isinstance(request_id, str) else None,
        http_status=http_status,
    )


def _page_operation(data: dict[str, Any]) -> PageOperation:
    page = data.get("page")
    capture = data.get("capture")
    if not isinstance(page, dict) or not isinstance(capture, dict):
        raise RelProtocolError("REL page response is missing page or capture")
    page_id = page.get("id")
    session_id = page.get("session_id")
    url = page.get("url")
    output_path = capture.get("output_path")
    bytesize = capture.get("bytesize")
    target_http_status = capture.get("target_http_status")
    if (
        not isinstance(page_id, str)
        or not isinstance(session_id, str)
        or not isinstance(url, str)
        or not isinstance(output_path, str)
        or not isinstance(bytesize, int)
        or (target_http_status is not None and not isinstance(target_http_status, int))
    ):
        raise RelProtocolError("REL returned malformed page operation data")
    path = Path(output_path)
    if not path.is_absolute():
        raise RelProtocolError("REL returned a relative capture output path")
    return PageOperation(
        page_id=page_id,
        session_id=session_id,
        url=url,
        output_path=path,
        bytesize=bytesize,
        target_http_status=target_http_status,
    )


def _navigation_operation(data: dict[str, Any]) -> NavigationOperation:
    page = data.get("page")
    observation = data.get("observation")
    if not isinstance(page, dict) or not isinstance(observation, dict):
        raise RelProtocolError("REL observation response is missing page or observation")
    page_id = page.get("id")
    session_id = page.get("session_id")
    url = observation.get("url", page.get("url"))
    if not all(isinstance(value, str) for value in (page_id, session_id, url)):
        raise RelProtocolError("REL returned malformed navigation data")
    return NavigationOperation(page_id=page_id, session_id=session_id, url=url)
