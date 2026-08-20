"""Restartable source-page crawler implemented on REL RPC v1."""

from __future__ import annotations

import fcntl
import hashlib
import json
import logging
import math
import os
import re
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Protocol

from .api import (
    NavigationOperation,
    PageOperation,
    RelClient,
    RelRpcError,
    RelTransportError,
)
from .html import canonicalize_url, extract_links, extract_page_metadata
from .models import (
    CapturedPage,
    CrawlDefinition,
    CrawlFailure,
    CrawlItem,
    CrawlSummary,
    Link,
    SourcePage,
)

_STATE_VERSION = 1
_METADATA_SCHEMA_VERSION = 4
_STATUSES = {"pending", "in_progress", "captured", "failed"}
_SESSION_RESTART_RPC_IDS = {
    "AGENT_UNHEALTHY",
    "BROWSER_UNAVAILABLE",
    "SESSION_NOT_FOUND",
}
_LOGGER = logging.getLogger(__name__)
_LOGGER.addHandler(logging.NullHandler())


class CrawlError(Exception):
    """Base class for crawler failures."""


class CrawlConfigurationError(CrawlError):
    """The definition or checkpoint is not safe to execute."""


class CrawlAlreadyRunningError(CrawlError):
    """Another process owns this checkpoint's crawl lock."""


class CrawlRecoveryError(CrawlError):
    """REL could not restore the source page after a bounded link attempt."""


class CrawlPageError(CrawlError):
    """A captured target page had an unsuccessful HTTP status."""


class _Client(Protocol):
    def health(self) -> dict[str, Any]: ...

    def get_session(self, session_id: str) -> dict[str, Any] | None: ...

    def create_session(self, *, profile: str, group: str) -> str: ...

    def delete_session(self, session_id: str) -> None: ...

    def navigate(
        self,
        *,
        url: str,
        session_id: str,
        output: Path,
        timeout: float,
        wait: float,
    ) -> PageOperation: ...

    def perform(
        self,
        *,
        actions: list[dict[str, Any]],
        session_id: str,
        output: Path,
        timeout: float,
        wait: float,
    ) -> PageOperation: ...

    def back(
        self, *, session_id: str, timeout: float, wait: float
    ) -> NavigationOperation: ...


class RelCrawler:
    """Crawl selected links from one page using click, capture, and history back."""

    def __init__(
        self,
        definition: CrawlDefinition,
        *,
        state_path: str | Path,
        capture_dir: str | Path = "captures",
        client: _Client | None = None,
        rel_base_url: str | None = None,
        session_id: str | None = None,
        profile: str = "Direct",
        group: str | None = None,
        timeout: float = 90.0,
        wait: float = 1.0,
        action_delay: float = 2.0,
        max_attempts: int = 2,
        max_session_restarts: int = 1,
        max_links: int | None = None,
        skip_existing: bool = True,
        accept_http_errors: bool = False,
        close_owned_session_on_finish: bool = False,
    ) -> None:
        if client is not None and rel_base_url is not None:
            raise CrawlConfigurationError(
                "client and rel_base_url cannot be supplied together"
            )
        try:
            canonicalize_url(definition.start_url)
        except (ValueError, UnicodeError) as error:
            raise CrawlConfigurationError(str(error)) from error
        if not profile.strip():
            raise CrawlConfigurationError("profile must not be empty")
        for name, selector in (
            ("source_ready_selector", definition.source_ready_selector),
            ("capture_ready_selector", definition.capture_ready_selector),
        ):
            if selector is not None and (
                not isinstance(selector, str) or not selector.strip()
            ):
                raise CrawlConfigurationError(f"{name} must be a non-empty string")
        if (
            not math.isfinite(timeout)
            or timeout <= 0
            or not math.isfinite(wait)
            or wait < 0
        ):
            raise CrawlConfigurationError("timeout must be positive and wait non-negative")
        if not math.isfinite(action_delay) or action_delay < 0:
            raise CrawlConfigurationError("action_delay must be finite and non-negative")
        if max_attempts < 1:
            raise CrawlConfigurationError("max_attempts must be at least 1")
        if max_session_restarts < 0:
            raise CrawlConfigurationError("max_session_restarts must not be negative")
        if max_links is not None and max_links < 1:
            raise CrawlConfigurationError("max_links must be at least 1")

        self.definition = definition
        self.state_path = Path(state_path).expanduser().resolve()
        self.capture_dir = Path(capture_dir).expanduser().resolve()
        self.client = client if client is not None else RelClient(rel_base_url)
        self.requested_session_id = session_id
        self.profile = profile.strip()
        self.group = group.strip() if group is not None else self._default_group()
        if not self.group:
            raise CrawlConfigurationError("group must not be empty")
        self.timeout = float(timeout)
        self.wait = float(wait)
        self.action_delay = float(action_delay)
        self.max_attempts = max_attempts
        self.max_session_restarts = max_session_restarts
        self.max_links = max_links
        self.skip_existing = skip_existing
        self.accept_http_errors = accept_http_errors
        self.close_owned_session_on_finish = close_owned_session_on_finish
        self._state: dict[str, Any] = {}
        self._source_url = canonicalize_url(definition.start_url)
        self.source_ready_selector = (
            definition.source_ready_selector.strip()
            if definition.source_ready_selector is not None
            else None
        )
        self.capture_ready_selector = (
            definition.capture_ready_selector.strip()
            if definition.capture_ready_selector is not None
            else None
        )
        self._has_browser_action = False

    def run(self) -> CrawlSummary:
        """Run or resume the crawl while holding an exclusive checkpoint lock."""

        _LOGGER.info(
            "starting crawl source=%s checkpoint=%s captures=%s",
            self.definition.start_url,
            self.state_path,
            self.capture_dir,
        )
        with self._checkpoint_lock():
            _LOGGER.info("acquired checkpoint lock %s", self.state_path)
            self._has_browser_action = False
            self._state = self._load_state()
            _LOGGER.info(
                "loaded checkpoint with %d entries and session %s",
                len(self._state["entries"]),
                self._state.get("session_id") or "none",
            )
            self._recover_interrupted_entries()
            self._recover_misdirected_captures()
            _LOGGER.info("checking REL health")
            health = self.client.health()
            _LOGGER.info("REL is healthy: %s", health.get("version", "unknown version"))
            session_id = self._ensure_session()
            _LOGGER.info(
                "using REL session %s (managed=%s, generation=%s)",
                session_id,
                self._state["managed_session"],
                self._state["session_generation"],
            )

            self.capture_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="rel-crawler-") as temporary:
                temporary_dir = Path(temporary)
                session_id, source = self._load_source_with_session_recovery(
                    session_id, temporary_dir / "source.html"
                )
                self._merge_links(source)
                self._skip_existing_captures()
                self._backfill_metadata()
                session_id = self._crawl_pending(
                    session_id, temporary_dir / "recovery.html"
                )

            summary = self._summary(session_id)
            if (
                self.close_owned_session_on_finish
                and self._state["managed_session"]
                and summary.pending == 0
            ):
                _LOGGER.info("closing completed crawler-owned session %s", session_id)
                self.client.delete_session(session_id)
                self._state["session_id"] = None
                self._save_state()
                _LOGGER.info("closed completed crawler-owned session %s", session_id)
            _LOGGER.info(
                "crawl complete: discovered=%d captured=%d failed=%d pending=%d "
                "skipped_existing=%d session=%s",
                summary.discovered,
                summary.captured,
                summary.failed,
                summary.pending,
                summary.skipped_existing,
                summary.session_id,
            )
            return summary

    def _load_source_with_session_recovery(
        self, session_id: str, output: Path
    ) -> tuple[str, SourcePage]:
        restarts = 0
        while True:
            try:
                return session_id, self._load_source(session_id, output)
            except Exception as error:
                if (
                    restarts >= self.max_session_restarts
                    or not self._can_restart_session(error)
                ):
                    raise
                _LOGGER.warning(
                    "source load failed in session %s; replacing session: %s: %s",
                    session_id,
                    type(error).__name__,
                    error,
                )
                session_id = self._restart_managed_session(
                    session_id,
                    reason=f"source navigation failed: {type(error).__name__}: {error}",
                )
                restarts += 1

    def _load_source(self, session_id: str, output: Path) -> SourcePage:
        source_uri = canonicalize_url(self.definition.start_url)
        _LOGGER.info(
            "navigating to source %s%s",
            self.definition.start_url,
            (
                f" (URI {source_uri})"
                if self.definition.start_url != source_uri
                else ""
            ),
        )
        self._before_browser_action()
        operation = self.client.navigate(
            url=source_uri,
            session_id=session_id,
            output=output,
            timeout=self.timeout,
            wait=self.wait,
        )
        _LOGGER.info(
            "source navigation returned url=%s status=%s",
            operation.url,
            operation.target_http_status,
        )
        if self.source_ready_selector is not None:
            operation = self._wait_for_ready(
                session_id,
                self.source_ready_selector,
                output,
            )
        self._source_url = canonicalize_url(operation.url)
        self._state["source_url"] = operation.url
        self._save_state()
        _LOGGER.info("source is ready at %s; reading links", operation.url)
        try:
            html = operation.output_path.read_text(encoding="utf-8", errors="replace")
        except OSError as error:
            raise CrawlError(
                f"Could not read REL source capture {operation.output_path}: {error}"
            ) from error
        return SourcePage(
            url=operation.url,
            output_path=operation.output_path,
            html=html,
            target_http_status=operation.target_http_status,
        )

    def _merge_links(self, source: SourcePage) -> None:
        extractor = self.definition.extract_links
        discovered = (
            list(extractor(source))
            if extractor is not None
            else extract_links(source.html, source.url)
        )
        selected: list[tuple[str, Link]] = []
        selected_keys: set[str] = set()
        for link in discovered:
            if not isinstance(link, Link):
                raise CrawlConfigurationError("extract_links must yield Link instances")
            try:
                normalized_url = canonicalize_url(link.url)
            except (ValueError, UnicodeError) as error:
                raise CrawlConfigurationError(
                    f"extract_links yielded an invalid URL {link.url!r}: {error}"
                ) from error
            if normalized_url != link.url:
                link = Link(
                    index=link.index,
                    url=normalized_url,
                    text=link.text,
                    target=link.target,
                    rel=link.rel,
                    original_url=link.original_url or link.url,
                )
            if not self.definition.select_link(link):
                continue
            raw_key = self.definition.link_key(link)
            if not isinstance(raw_key, str):
                raise CrawlConfigurationError("link_key must return a string")
            key = raw_key.strip()
            if not key:
                raise CrawlConfigurationError("link_key must return a non-empty string")
            if key in selected_keys:
                continue
            selected_keys.add(key)
            selected.append((key, link))
            if self.max_links is not None and len(selected) >= self.max_links:
                break

        entries = self._state["entries"]
        existing = {entry["key"]: entry for entry in entries}
        path_updates: list[tuple[dict[str, Any], Path, Path]] = []
        for key, link in selected:
            entry = existing.get(key)
            if (
                entry is None
                or entry["status"] != "pending"
                or entry["attempts"] != 0
            ):
                continue
            current_path = Path(entry["output_path"])
            desired_path = self._capture_path(
                CrawlItem(
                    key=key,
                    index=entry["index"],
                    link=link,
                    attempt=1,
                )
            )
            if desired_path != current_path:
                entry["output_path"] = str(desired_path)
                path_updates.append((entry, current_path, desired_path))

        occupied_paths: dict[str, str] = {}
        for entry in entries:
            output_path = Path(entry["output_path"])
            for artifact_path in (output_path, self._metadata_path(output_path)):
                other_key = occupied_paths.get(str(artifact_path))
                if other_key is not None and other_key != entry["key"]:
                    raise CrawlConfigurationError(
                        f"checkpoint maps {entry['key']!r} and {other_key!r} "
                        f"to {artifact_path}"
                    )
                occupied_paths[str(artifact_path)] = entry["key"]
        for entry, previous_path, desired_path in path_updates:
            _LOGGER.info(
                "updated pending capture path for %s: %s -> %s",
                entry["url"],
                previous_path,
                desired_path,
            )
        for key, link in selected:
            if key in existing:
                continue
            item = CrawlItem(key=key, index=len(entries), link=link, attempt=1)
            output_path = self._capture_path(item)
            for artifact_path in (output_path, self._metadata_path(output_path)):
                other_key = occupied_paths.get(str(artifact_path))
                if other_key is not None and other_key != key:
                    raise CrawlConfigurationError(
                        f"capture_path maps {key!r} and {other_key!r} "
                        f"to {artifact_path}"
                    )
                occupied_paths[str(artifact_path)] = key
            entry = {
                "key": key,
                "index": item.index,
                "link_index": link.index,
                "url": link.url,
                "original_url": link.original_url or link.url,
                "text": link.text,
                "target": link.target,
                "rel": list(link.rel),
                "output_path": str(output_path),
                "status": "pending",
                "attempts": 0,
                "session_restarts": 0,
                "skipped_existing": False,
                "captured_url": None,
                "target_http_status": None,
                "last_error": None,
            }
            entries.append(entry)
            existing[key] = entry
        self._save_state()
        _LOGGER.info(
            "link discovery found %d anchors, selected %d, checkpoint now has %d entries",
            len(discovered),
            len(selected),
            len(entries),
        )

    def _skip_existing_captures(self) -> None:
        if not self.skip_existing:
            return
        changed = False
        for entry in self._state["entries"]:
            if entry["status"] != "pending" or entry["attempts"] != 0:
                continue
            output_path = Path(entry["output_path"])
            if not output_path.is_file():
                continue
            metadata_path = self._metadata_path(output_path)
            existing_metadata = self._read_existing_metadata(metadata_path)
            if existing_metadata is None:
                existing_metadata = self._read_existing_metadata(
                    self._legacy_metadata_path(output_path)
                )
            existing_page = (
                existing_metadata.get("page")
                if isinstance(existing_metadata, dict)
                else None
            )
            existing_url = (
                existing_page.get("url")
                if isinstance(existing_page, dict)
                and isinstance(existing_page.get("url"), str)
                else entry.get("captured_url")
            )
            if self._is_misdirected_capture(existing_url, entry["url"]):
                continue
            entry["status"] = "captured"
            entry["skipped_existing"] = True
            entry["captured_url"] = (
                existing_page.get("url")
                if isinstance(existing_page, dict)
                and isinstance(existing_page.get("url"), str)
                else entry["url"]
            )
            entry["target_http_status"] = (
                existing_page.get("target_http_status")
                if isinstance(existing_page, dict)
                and (
                    existing_page.get("target_http_status") is None
                    or isinstance(existing_page.get("target_http_status"), int)
                )
                else None
            )
            entry["last_error"] = None
            self._report_skip(
                f"existing capture {entry['url']} -> {output_path}"
            )
            changed = True
        if changed:
            self._save_state()

    def _crawl_pending(self, session_id: str, recovery_output: Path) -> str:
        while True:
            entry = next(
                (entry for entry in self._state["entries"] if entry["status"] == "pending"),
                None,
            )
            if entry is None:
                return session_id
            entry["attempts"] += 1
            entry["status"] = "in_progress"
            entry["last_error"] = None
            self._save_state()
            item = self._item(entry)
            operation: PageOperation | None = None
            failure: Exception | None = None
            failure_stage: str | None = None
            terminal = False
            output_path = Path(entry["output_path"])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                display_url = item.link.original_url or item.link.url
                _LOGGER.info(
                    "clicking %s%s (attempt %d/%d) -> %s",
                    display_url,
                    (
                        f" (URI {item.link.url})"
                        if display_url != item.link.url
                        else ""
                    ),
                    entry["attempts"],
                    self.max_attempts,
                    output_path,
                )
                self._before_browser_action()
                actions = [
                    {
                        "action": "click-link",
                        "link": item.link.url,
                        "match": {"type": "fuzzy-link", "threshold": 1.0},
                        "scroll": True,
                    }
                ]
                _LOGGER.info("click-link auto-scroll is enabled")
                if self.capture_ready_selector is not None:
                    _LOGGER.info(
                        "click will wait for target selector %r before capture",
                        self.capture_ready_selector,
                    )
                    actions.append(
                        {
                            "action": "wait-for",
                            "selector": self.capture_ready_selector,
                        }
                    )
                operation = self.client.perform(
                    actions=actions,
                    session_id=session_id,
                    output=output_path,
                    timeout=self.timeout,
                    wait=self.wait,
                )
                _LOGGER.info(
                    "click/capture returned url=%s status=%s bytes=%s",
                    operation.url,
                    operation.target_http_status,
                    operation.bytesize,
                )
                if self._is_misdirected_capture(operation.url, item.link.url):
                    captured_url = operation.url
                    operation = None
                    raise CrawlPageError(
                        f"clicking {item.link.url} remained on source page "
                        f"{captured_url}"
                    )
            except Exception as error:
                failure = error
                failure_stage = "perform"
                _LOGGER.warning(
                    "click attempt %d/%d failed for %s: %s: %s",
                    entry["attempts"],
                    self.max_attempts,
                    item.link.url,
                    type(error).__name__,
                    error,
                )
            if operation is not None:
                try:
                    _LOGGER.info("writing metadata for %s", operation.url)
                    captured = self._captured_page(item, operation)
                    _LOGGER.info("metadata written to %s", captured.metadata_path)
                except Exception as error:
                    failure = error
                    failure_stage = "metadata"
                    _LOGGER.warning(
                        "metadata failed for %s: %s: %s",
                        operation.url,
                        type(error).__name__,
                        error,
                    )
                if (
                    failure is None
                    and not self.accept_http_errors
                    and operation.target_http_status is not None
                    and operation.target_http_status >= 400
                ):
                    failure = CrawlPageError(
                        f"{operation.url} returned HTTP {operation.target_http_status}"
                    )
                    failure_stage = "http"
                if failure is None:
                    try:
                        _LOGGER.info("processing captured page %s", captured.url)
                        self.definition.process_capture(captured)
                        _LOGGER.info("finished processing captured page %s", captured.url)
                    except Exception as error:
                        failure = error
                        failure_stage = "callback"
                        _LOGGER.warning(
                            "capture callback failed for %s: %s: %s",
                            captured.url,
                            type(error).__name__,
                            error,
                        )

            if (
                failure is not None
                and operation is None
                and entry["session_restarts"] < self.max_session_restarts
                and self._can_restart_session(failure)
            ):
                entry["session_restarts"] += 1
                entry["status"] = "pending"
                entry["last_error"] = (
                    f"SessionRestart: {type(failure).__name__}: {failure}"
                )
                self._save_state()
                _LOGGER.warning(
                    "replacing session %s before retrying %s",
                    session_id,
                    item.link.url,
                )
                session_id = self._restart_managed_session(
                    session_id,
                    reason=(
                        f"link {item.link.url!r} failed: "
                        f"{type(failure).__name__}: {failure}"
                    ),
                )
                self._navigate_to_source(session_id, recovery_output)
                continue

            if failure is None and operation is not None:
                entry["status"] = "captured"
                entry["captured_url"] = operation.url
                entry["target_http_status"] = operation.target_http_status
                entry["last_error"] = None
                self._save_state()
                _LOGGER.info("captured %s -> %s", operation.url, output_path)
            else:
                assert failure is not None
                if operation is not None:
                    entry["captured_url"] = operation.url
                    entry["target_http_status"] = operation.target_http_status
                terminal = entry["attempts"] >= self.max_attempts
                entry["status"] = "failed" if terminal else "pending"
                entry["last_error"] = f"{type(failure).__name__}: {failure}"
                self._save_state()
                if not terminal:
                    _LOGGER.warning(
                        "will retry %s after %s",
                        item.link.url,
                        entry["last_error"],
                    )
                if terminal:
                    self._report_skip(
                        f"failed link {item.link.url} after {entry['attempts']} "
                        f"attempts: {entry['last_error']}"
                    )
                try:
                    _LOGGER.info(
                        "reporting %s failure for %s",
                        "terminal" if terminal else "retryable",
                        item.link.url,
                    )
                    self.definition.process_failure(
                        CrawlFailure(item=item, error=failure, terminal=terminal)
                    )
                    _LOGGER.info("finished failure callback for %s", item.link.url)
                except Exception as callback_error:
                    _LOGGER.warning(
                        "failure callback failed for %s: %s: %s",
                        item.link.url,
                        type(callback_error).__name__,
                        callback_error,
                    )
                    entry["last_error"] += (
                        "; process_failure raised "
                        f"{type(callback_error).__name__}: {callback_error}"
                    )
                    self._save_state()

            if (
                terminal
                and failure is not None
                and self._should_restart_after_terminal_failure(
                    failure_stage, operation
                )
            ):
                entry["session_restarts"] += 1
                self._save_state()
                _LOGGER.warning(
                    "discarding session %s after terminal failure for %s",
                    session_id,
                    item.link.url,
                )
                session_id = self._restart_managed_session(
                    session_id,
                    reason=(
                        f"terminal {failure_stage or 'crawl'} failure for "
                        f"{item.link.url!r}: {type(failure).__name__}: {failure}"
                    ),
                )
                self._navigate_to_source(session_id, recovery_output)
                continue

            try:
                if operation is not None:
                    self._back_to_source(session_id, recovery_output)
                else:
                    self._navigate_to_source(session_id, recovery_output)
            except Exception as recovery_error:
                if (
                    entry["session_restarts"] < self.max_session_restarts
                    and self._can_restart_session(recovery_error)
                ):
                    entry["session_restarts"] += 1
                    entry["last_error"] = (
                        f"SessionRestart: recovery failed with "
                        f"{type(recovery_error).__name__}: {recovery_error}"
                    )
                    self._save_state()
                    _LOGGER.warning(
                        "source recovery failed in session %s; replacing it: %s: %s",
                        session_id,
                        type(recovery_error).__name__,
                        recovery_error,
                    )
                    session_id = self._restart_managed_session(
                        session_id,
                        reason=(
                            f"source recovery after {item.link.url!r} failed: "
                            f"{type(recovery_error).__name__}: {recovery_error}"
                        ),
                    )
                    self._navigate_to_source(session_id, recovery_output)
                    continue
                raise CrawlRecoveryError(
                    f"Could not restore {self.definition.start_url!r} after {item.link.url!r}: "
                    f"{recovery_error}"
                ) from recovery_error

    def _captured_page(
        self, item: CrawlItem, operation: PageOperation
    ) -> CapturedPage:
        metadata_path = self._metadata_path(operation.output_path)
        self._write_page_metadata(
            item=item,
            page_url=operation.url,
            output_path=operation.output_path,
            bytesize=operation.bytesize,
            target_http_status=operation.target_http_status,
            session_id=operation.session_id,
            captured_at=datetime.now(timezone.utc),
            metadata_path=metadata_path,
            backfilled=False,
        )
        return CapturedPage(
            item=item,
            url=operation.url,
            output_path=operation.output_path,
            bytesize=operation.bytesize,
            target_http_status=operation.target_http_status,
            session_id=operation.session_id,
            metadata_path=metadata_path,
        )

    def _backfill_metadata(self) -> None:
        for entry in self._state["entries"]:
            if entry["status"] not in {"captured", "failed"}:
                continue
            output_path = Path(entry["output_path"])
            metadata_path = self._metadata_path(output_path)
            if not output_path.is_file():
                continue
            try:
                existing_path = metadata_path
                legacy_metadata_path = self._legacy_metadata_path(output_path)
                if not existing_path.exists() and legacy_metadata_path.exists():
                    existing_path = legacy_metadata_path
                existing = self._read_existing_metadata(existing_path)
                existing_schema = (
                    existing.get("schema_version")
                    if isinstance(existing, dict)
                    else None
                )
                if (
                    existing_path == metadata_path
                    and type(existing_schema) is int
                    and existing_schema >= _METADATA_SCHEMA_VERSION
                ):
                    continue
                _LOGGER.info("backfilling metadata for %s", output_path)
                captured_at = self._existing_capture_time(
                    existing,
                    datetime.fromtimestamp(output_path.stat().st_mtime, tz=timezone.utc),
                )
                existing_page = existing.get("page") if isinstance(existing, dict) else None
                existing_crawl = (
                    existing.get("crawl") if isinstance(existing, dict) else None
                )
                page_url = (
                    existing_page.get("url")
                    if isinstance(existing_page, dict)
                    and isinstance(existing_page.get("url"), str)
                    else entry.get("captured_url") or entry["url"]
                )
                session_id = (
                    existing_crawl.get("session_id")
                    if isinstance(existing_crawl, dict)
                    and isinstance(existing_crawl.get("session_id"), str)
                    else None
                )
                was_backfilled = (
                    existing.get("backfilled")
                    if isinstance(existing, dict)
                    and isinstance(existing.get("backfilled"), bool)
                    else True
                )
                checkpoint = (
                    existing.get("checkpoint")
                    if isinstance(existing, dict)
                    and isinstance(existing.get("checkpoint"), dict)
                    else None
                )
                if existing is None:
                    checkpoint = {
                        "status": entry["status"],
                        "last_error": entry.get("last_error"),
                        "skipped_existing": entry.get("skipped_existing", False),
                    }
                self._write_page_metadata(
                    item=self._item(entry),
                    page_url=page_url,
                    output_path=output_path,
                    bytesize=output_path.stat().st_size,
                    target_http_status=entry.get("target_http_status"),
                    session_id=session_id,
                    captured_at=captured_at,
                    metadata_path=metadata_path,
                    backfilled=was_backfilled,
                    checkpoint=checkpoint,
                )
                _LOGGER.info("backfilled metadata at %s", metadata_path)
            except OSError as error:
                raise CrawlError(
                    f"Could not backfill metadata for {output_path}: {error}"
                ) from error

    @staticmethod
    def _read_existing_metadata(metadata_path: Path) -> dict[str, Any] | None:
        if not metadata_path.exists():
            return None
        try:
            value = json.loads(metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        return value if isinstance(value, dict) else None

    @staticmethod
    def _existing_capture_time(
        metadata: dict[str, Any] | None, fallback: datetime
    ) -> datetime:
        value = metadata.get("captured_at") if metadata is not None else None
        if not isinstance(value, str):
            return fallback
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return fallback
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed

    def _write_page_metadata(
        self,
        *,
        item: CrawlItem,
        page_url: str,
        output_path: Path,
        bytesize: int,
        target_http_status: int | None,
        session_id: str | None,
        captured_at: datetime,
        metadata_path: Path,
        backfilled: bool,
        checkpoint: dict[str, Any] | None = None,
    ) -> None:
        try:
            html = output_path.read_text(encoding="utf-8", errors="replace")
        except OSError as error:
            raise CrawlError(f"Could not read REL capture {output_path}: {error}") from error
        captured_at_utc = captured_at.astimezone(timezone.utc)
        metadata: dict[str, Any] = {
            "schema_version": _METADATA_SCHEMA_VERSION,
            "captured_at": captured_at_utc.isoformat().replace("+00:00", "Z"),
            "backfilled": backfilled,
            "crawl": {
                "start_url": self.definition.start_url,
                "source_url": self._state.get("source_url"),
                "key": item.key,
                "index": item.index,
                "attempt": item.attempt,
                "session_id": session_id,
                "session_generation": self._state.get("session_generation", 0),
            },
            "link": {
                "document_index": item.link.index,
                "url": item.link.url,
                "original_url": item.link.original_url,
                "text": item.link.text,
                "target": item.link.target,
                "rel": list(item.link.rel),
            },
            "page": {
                "url": page_url,
                "output_path": str(output_path),
                "metadata_path": str(metadata_path),
                "bytesize": bytesize,
                "target_http_status": target_http_status,
                **extract_page_metadata(html, page_url),
            },
        }
        if checkpoint is not None:
            metadata["checkpoint"] = checkpoint
        self._write_json(metadata_path, metadata)

    def _back_to_source(self, session_id: str, recovery_output: Path) -> None:
        try:
            _LOGGER.info("navigating Back to source in session %s", session_id)
            self._before_browser_action()
            navigation = self.client.back(
                session_id=session_id, timeout=self.timeout, wait=self.wait
            )
            _LOGGER.info("Back navigation returned url=%s", navigation.url)
            if canonicalize_url(navigation.url) == self._source_url:
                if self.source_ready_selector is not None:
                    operation = self._wait_for_ready(
                        session_id,
                        self.source_ready_selector,
                        recovery_output,
                    )
                    if canonicalize_url(operation.url) != self._source_url:
                        raise CrawlRecoveryError(
                            f"source readiness check ended at {operation.url!r}"
                        )
                _LOGGER.info("source restored through browser history")
                return
            _LOGGER.warning(
                "Back reached unexpected url=%s; reloading source directly",
                navigation.url,
            )
        except Exception as error:
            _LOGGER.warning(
                "Back/source readiness failed; reloading source directly: %s: %s",
                type(error).__name__,
                error,
            )
        self._navigate_to_source(session_id, recovery_output)

    def _navigate_to_source(self, session_id: str, recovery_output: Path) -> None:
        source_uri = canonicalize_url(self.definition.start_url)
        _LOGGER.info(
            "reloading source directly at %s%s",
            self.definition.start_url,
            (
                f" (URI {source_uri})"
                if self.definition.start_url != source_uri
                else ""
            ),
        )
        self._before_browser_action()
        operation = self.client.navigate(
            url=source_uri,
            session_id=session_id,
            output=recovery_output,
            timeout=self.timeout,
            wait=self.wait,
        )
        _LOGGER.info(
            "source recovery navigation returned url=%s status=%s",
            operation.url,
            operation.target_http_status,
        )
        if self.source_ready_selector is not None:
            operation = self._wait_for_ready(
                session_id,
                self.source_ready_selector,
                recovery_output,
            )
        self._source_url = canonicalize_url(operation.url)
        self._state["source_url"] = operation.url
        self._save_state()
        _LOGGER.info("source recovery is ready at %s", operation.url)

    def _ensure_session(self) -> str:
        state_session = self._state.get("session_id")
        if self.requested_session_id is not None:
            _LOGGER.info("checking caller-owned REL session %s", self.requested_session_id)
            if state_session is not None and state_session != self.requested_session_id:
                raise CrawlConfigurationError(
                    f"checkpoint belongs to {state_session}, not {self.requested_session_id}"
                )
            if self.client.get_session(self.requested_session_id) is None:
                raise CrawlConfigurationError(
                    f"REL session {self.requested_session_id} does not exist"
                )
            self._state["session_id"] = self.requested_session_id
            self._state["managed_session"] = False
            self._state["session_generation"] = 0
            self._state["pending_session_restart"] = None
            self._save_state()
            return self.requested_session_id

        if isinstance(state_session, str):
            _LOGGER.info("checking checkpoint REL session %s", state_session)
            session = self.client.get_session(state_session)
            if session is not None:
                live_profile = session.get("profile")
                profile_changed = (
                    self._state.get("managed_session")
                    and isinstance(live_profile, str)
                    and live_profile.casefold() != self.profile.casefold()
                )
                if not profile_changed:
                    _LOGGER.info("reusing checkpoint REL session %s", state_session)
                    return state_session
                _LOGGER.info(
                    "checkpoint session profile changed from %r to %r",
                    live_profile,
                    self.profile,
                )
                return self._restart_managed_session(
                    state_session,
                    reason=(
                        f"profile changed from {live_profile!r} to {self.profile!r}"
                    ),
                )
            if not self._state.get("managed_session"):
                raise CrawlConfigurationError(
                    f"checkpoint's external REL session {state_session} no longer exists"
                )
            self._state["session_id"] = None
            self._save_state()
            _LOGGER.warning(
                "checkpoint session %s no longer exists; creating a replacement",
                state_session,
            )
            return self._create_managed_session(
                previous_session_id=state_session,
                reason="checkpoint session no longer exists",
            )

        _LOGGER.info("checkpoint has no session; creating one")
        return self._create_managed_session()

    def _can_restart_session(self, error: Exception) -> bool:
        if self.requested_session_id is not None or not self._state.get(
            "managed_session"
        ):
            return False
        if isinstance(error, RelTransportError):
            return True
        return isinstance(error, RelRpcError) and error.id in _SESSION_RESTART_RPC_IDS

    def _should_restart_after_terminal_failure(
        self, failure_stage: str | None, operation: PageOperation | None
    ) -> bool:
        if (
            self.max_session_restarts == 0
            or self.requested_session_id is not None
            or not self._state.get("managed_session")
        ):
            return False
        if failure_stage == "perform":
            return True
        status = operation.target_http_status if operation is not None else None
        return failure_stage == "http" and status is not None and (
            status in {403, 429} or status >= 500
        )

    def _before_browser_action(self) -> None:
        if self._has_browser_action and self.action_delay > 0:
            _LOGGER.info(
                "pacing browser actions: waiting %.3g seconds",
                self.action_delay,
            )
            time.sleep(self.action_delay)
        self._has_browser_action = True

    def _wait_for_ready(
        self,
        session_id: str,
        selector: str,
        output: Path,
    ) -> PageOperation:
        _LOGGER.info(
            "waiting for selector %r in session %s (timeout %.3g seconds)",
            selector,
            session_id,
            self.timeout,
        )
        self._before_browser_action()
        operation = self.client.perform(
            actions=[{"action": "wait-for", "selector": selector}],
            session_id=session_id,
            output=output,
            timeout=self.timeout,
            wait=self.wait,
        )
        _LOGGER.info("selector %r is ready at %s", selector, operation.url)
        return operation

    @staticmethod
    def _report_skip(message: str) -> None:
        _LOGGER.info("skipping %s", message)

    def _restart_managed_session(self, session_id: str, *, reason: str) -> str:
        if self.requested_session_id is not None or not self._state.get(
            "managed_session"
        ):
            raise CrawlRecoveryError("cannot replace a caller-owned REL session")
        self._state["session_id"] = None
        self._state["pending_session_restart"] = {
            "at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "previous_session_id": session_id,
            "reason": reason,
            "delete_error": None,
        }
        self._save_state()
        delete_error: str | None = None
        _LOGGER.info("closing REL session %s: %s", session_id, reason)
        try:
            self.client.delete_session(session_id)
            _LOGGER.info("closed REL session %s", session_id)
        except Exception as error:
            delete_error = f"{type(error).__name__}: {error}"
            _LOGGER.warning("could not close REL session %s: %s", session_id, delete_error)
            self._state["pending_session_restart"]["delete_error"] = delete_error
            self._save_state()
        return self._create_managed_session(
            previous_session_id=session_id,
            reason=reason,
            delete_error=delete_error,
        )

    def _create_managed_session(
        self,
        *,
        previous_session_id: str | None = None,
        reason: str | None = None,
        delete_error: str | None = None,
    ) -> str:
        pending_restart = self._state.get("pending_session_restart")
        if previous_session_id is None and isinstance(pending_restart, dict):
            pending_previous = pending_restart.get("previous_session_id")
            if isinstance(pending_previous, str):
                previous_session_id = pending_previous
                reason = (
                    pending_restart.get("reason")
                    if isinstance(pending_restart.get("reason"), str)
                    else reason
                )
                delete_error = (
                    pending_restart.get("delete_error")
                    if isinstance(pending_restart.get("delete_error"), str)
                    else delete_error
                )
        _LOGGER.info(
            "creating REL session with profile=%r group=%r",
            self.profile,
            self.group,
        )
        session_id = self.client.create_session(profile=self.profile, group=self.group)
        _LOGGER.info("created REL session %s", session_id)
        self._state["session_id"] = session_id
        self._state["managed_session"] = True
        self._state["pending_session_restart"] = None
        generation = self._state.get("session_generation", 0)
        self._state["session_generation"] = max(generation + 1, 1)
        if previous_session_id is not None:
            self._state["session_restart_count"] += 1
            self._state["last_session_restart"] = {
                "at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "previous_session_id": previous_session_id,
                "session_id": session_id,
                "reason": reason,
                "delete_error": delete_error,
            }
        self._save_state()
        return session_id

    def _capture_path(self, item: CrawlItem) -> Path:
        if self.definition.capture_path is not None:
            try:
                value = Path(self.definition.capture_path(item)).expanduser()
            except (TypeError, ValueError) as error:
                raise CrawlConfigurationError(
                    f"capture_path returned an invalid path for {item.key!r}"
                ) from error
            return value.resolve()
        path = item.link.url.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1]
        slug = re.sub(r"[^A-Za-z0-9._-]+", "-", path).strip("-.") or "page"
        digest = hashlib.sha256(item.key.encode("utf-8")).hexdigest()[:10]
        filename = f"{item.index + 1:04d}-{slug[:80]}-{digest}.html"
        return (self.capture_dir / filename).resolve()

    @staticmethod
    def _metadata_path(output_path: Path) -> Path:
        return output_path.with_suffix(".metadata.json")

    @staticmethod
    def _legacy_metadata_path(output_path: Path) -> Path:
        return output_path.with_name(f"{output_path.name}.metadata.json")

    def _item(self, entry: dict[str, Any]) -> CrawlItem:
        return CrawlItem(
            key=entry["key"],
            index=entry["index"],
            link=Link(
                index=entry["link_index"],
                url=entry["url"],
                text=entry["text"],
                target=entry["target"],
                rel=tuple(entry["rel"]),
                original_url=entry.get("original_url"),
            ),
            attempt=entry["attempts"],
        )

    def _default_group(self) -> str:
        digest = hashlib.sha256(str(self.state_path).encode("utf-8")).hexdigest()[:16]
        return f"rel-crawler-{digest}"

    def _load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {
                "version": _STATE_VERSION,
                "start_url": canonicalize_url(self.definition.start_url),
                "source_url": None,
                "session_id": None,
                "managed_session": False,
                "session_generation": 0,
                "session_restart_count": 0,
                "last_session_restart": None,
                "pending_session_restart": None,
                "entries": [],
            }
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise CrawlConfigurationError(
                f"Could not read checkpoint {self.state_path}: {error}"
            ) from error
        self._validate_state(state)
        self._normalize_checkpoint_urls(state)
        if state["start_url"] != canonicalize_url(self.definition.start_url):
            raise CrawlConfigurationError(
                f"checkpoint is for {state['start_url']!r}, not {self.definition.start_url!r}"
            )
        if "session_generation" not in state:
            state["session_generation"] = (
                1 if state.get("managed_session") and state.get("session_id") else 0
            )
        state.setdefault("session_restart_count", 0)
        state.setdefault("last_session_restart", None)
        state.setdefault("pending_session_restart", None)
        for entry in state["entries"]:
            entry.setdefault("session_restarts", 0)
            entry.setdefault("skipped_existing", False)
            entry.setdefault("original_url", entry["url"])
        return state

    def _normalize_checkpoint_urls(self, state: dict[str, Any]) -> None:
        try:
            state["start_url"] = canonicalize_url(state["start_url"])
            if isinstance(state.get("source_url"), str):
                state["source_url"] = canonicalize_url(state["source_url"])
            keys: set[str] = set()
            for entry in state["entries"]:
                old_url = entry["url"]
                normalized_url = canonicalize_url(old_url)
                entry.setdefault("original_url", old_url)
                entry["url"] = normalized_url
                if entry["key"] == old_url:
                    entry["key"] = normalized_url
                captured_url = entry.get("captured_url")
                if isinstance(captured_url, str):
                    try:
                        entry["captured_url"] = canonicalize_url(captured_url)
                    except (ValueError, UnicodeError):
                        # Older sidecars could supply arbitrary page metadata here.
                        pass
                if entry["key"] in keys:
                    raise CrawlConfigurationError(
                        "checkpoint contains URL-equivalent duplicate link keys"
                    )
                keys.add(entry["key"])
        except (ValueError, UnicodeError) as error:
            raise CrawlConfigurationError(
                f"checkpoint contains an invalid URL: {error}"
            ) from error

    def _validate_state(self, state: Any) -> None:
        if not isinstance(state, dict) or state.get("version") != _STATE_VERSION:
            raise CrawlConfigurationError("unsupported or malformed crawler checkpoint")
        if not isinstance(state.get("start_url"), str):
            raise CrawlConfigurationError("checkpoint start_url is invalid")
        if state.get("session_id") is not None and not isinstance(
            state.get("session_id"), str
        ):
            raise CrawlConfigurationError("checkpoint session_id is invalid")
        if not isinstance(state.get("managed_session"), bool):
            raise CrawlConfigurationError("checkpoint managed_session is invalid")
        if "session_generation" in state and (
            type(state["session_generation"]) is not int
            or state["session_generation"] < 0
        ):
            raise CrawlConfigurationError("checkpoint session_generation is invalid")
        if "session_restart_count" in state and (
            type(state["session_restart_count"]) is not int
            or state["session_restart_count"] < 0
        ):
            raise CrawlConfigurationError("checkpoint session_restart_count is invalid")
        if state.get("last_session_restart") is not None and not isinstance(
            state.get("last_session_restart"), dict
        ):
            raise CrawlConfigurationError("checkpoint last_session_restart is invalid")
        if state.get("pending_session_restart") is not None and not isinstance(
            state.get("pending_session_restart"), dict
        ):
            raise CrawlConfigurationError("checkpoint pending_session_restart is invalid")
        entries = state.get("entries")
        if not isinstance(entries, list):
            raise CrawlConfigurationError("checkpoint entries are invalid")
        keys: set[str] = set()
        for entry in entries:
            required = {
                "key": str,
                "index": int,
                "link_index": int,
                "url": str,
                "text": str,
                "rel": list,
                "output_path": str,
                "status": str,
                "attempts": int,
            }
            if not isinstance(entry, dict) or any(
                not isinstance(entry.get(name), expected)
                for name, expected in required.items()
            ):
                raise CrawlConfigurationError("checkpoint contains a malformed entry")
            if entry["status"] not in _STATUSES or entry["attempts"] < 0:
                raise CrawlConfigurationError("checkpoint entry status is invalid")
            if "session_restarts" in entry and (
                type(entry["session_restarts"]) is not int
                or entry["session_restarts"] < 0
            ):
                raise CrawlConfigurationError(
                    "checkpoint entry session_restarts is invalid"
                )
            if "skipped_existing" in entry and not isinstance(
                entry["skipped_existing"], bool
            ):
                raise CrawlConfigurationError(
                    "checkpoint entry skipped_existing is invalid"
                )
            if "original_url" in entry and not isinstance(entry["original_url"], str):
                raise CrawlConfigurationError(
                    "checkpoint entry original_url is invalid"
                )
            if entry.get("target") is not None and not isinstance(
                entry.get("target"), str
            ):
                raise CrawlConfigurationError("checkpoint link target is invalid")
            if not all(isinstance(value, str) for value in entry["rel"]):
                raise CrawlConfigurationError("checkpoint link rel is invalid")
            if not Path(entry["output_path"]).is_absolute():
                raise CrawlConfigurationError("checkpoint capture path must be absolute")
            if entry["key"] in keys:
                raise CrawlConfigurationError("checkpoint contains duplicate link keys")
            keys.add(entry["key"])

    def _recover_interrupted_entries(self) -> None:
        changed = False
        for entry in self._state["entries"]:
            if entry["status"] != "in_progress":
                continue
            terminal = entry["attempts"] >= self.max_attempts
            entry["status"] = "failed" if terminal else "pending"
            entry["last_error"] = "CrawlInterrupted: previous process stopped during this link"
            _LOGGER.warning(
                "recovered interrupted link %s as %s after %d attempts",
                entry["url"],
                entry["status"],
                entry["attempts"],
            )
            changed = True
        if changed:
            self._save_state()

    def _recover_misdirected_captures(self) -> None:
        changed = False
        for entry in self._state["entries"]:
            if entry["status"] != "captured" or not self._is_misdirected_capture(
                entry.get("captured_url"), entry["url"]
            ):
                continue
            entry["status"] = "pending"
            entry["attempts"] = 0
            entry["skipped_existing"] = False
            entry["target_http_status"] = None
            entry["last_error"] = (
                "CrawlCaptureMismatch: previous capture remained on the source page"
            )
            _LOGGER.info(
                "re-queueing misdirected capture %s (captured %s)",
                entry["url"],
                entry.get("captured_url"),
            )
            changed = True
        if changed:
            self._save_state()

    def _is_misdirected_capture(
        self,
        captured_url: Any,
        target_url: str,
    ) -> bool:
        if not isinstance(captured_url, str):
            return False
        try:
            captured = canonicalize_url(captured_url)
            target = canonicalize_url(target_url)
        except (ValueError, UnicodeError):
            return False
        source_urls = {
            canonicalize_url(self.definition.start_url),
            self._source_url,
        }
        state_source_url = self._state.get("source_url")
        if isinstance(state_source_url, str):
            try:
                source_urls.add(canonicalize_url(state_source_url))
            except (ValueError, UnicodeError):
                pass
        return captured in source_urls and target != captured

    def _summary(self, session_id: str) -> CrawlSummary:
        entries = self._state["entries"]
        counts = {
            status: sum(entry["status"] == status for entry in entries)
            for status in _STATUSES
        }
        return CrawlSummary(
            discovered=len(entries),
            captured=counts["captured"],
            failed=counts["failed"],
            pending=counts["pending"] + counts["in_progress"],
            skipped_existing=sum(
                bool(entry.get("skipped_existing")) for entry in entries
            ),
            session_id=session_id,
            session_generation=self._state["session_generation"],
            session_restart_count=self._state["session_restart_count"],
            state_path=self.state_path,
        )

    def _save_state(self) -> None:
        self._write_json(self.state_path, self._state)

    @staticmethod
    def _write_json(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{path.name}.", dir=path.parent
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                json.dump(value, output, indent=2, sort_keys=True)
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, path)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass

    @contextmanager
    def _checkpoint_lock(self) -> Iterator[None]:
        lock_path = self.state_path.with_name(f"{self.state_path.name}.lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise CrawlAlreadyRunningError(
                    f"another crawler is using {self.state_path}"
                ) from error
            yield
        finally:
            os.close(descriptor)
