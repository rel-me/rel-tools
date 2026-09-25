"""Durable crawl checkpoint validation, migration, and locking."""

from __future__ import annotations

import fcntl
import hashlib
import json
import logging
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .errors import CrawlAlreadyRunningError, CrawlConfigurationError
from .html import canonicalize_url
from .models import CrawlSummary

STATE_VERSION = 1
STATUSES = {"pending", "in_progress", "captured", "failed"}
_LOGGER = logging.getLogger("rel_crawler.crawler")


class CheckpointMixin:
    """Private engine mixin for durable checkpoint state."""

    def _default_group(self) -> str:
        digest = hashlib.sha256(str(self.state_path).encode("utf-8")).hexdigest()[:16]
        return f"rel-crawler-{digest}"

    def _load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {
                "version": STATE_VERSION,
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
                f"checkpoint is for {state['start_url']!r}, "
                f"not {self.definition.start_url!r}"
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
            entry.setdefault("retry_requested", False)
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
        if not isinstance(state, dict) or state.get("version") != STATE_VERSION:
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
            raise CrawlConfigurationError(
                "checkpoint pending_session_restart is invalid"
            )
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
            if entry["status"] not in STATUSES or entry["attempts"] < 0:
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
            if "retry_requested" in entry and not isinstance(
                entry["retry_requested"], bool
            ):
                raise CrawlConfigurationError(
                    "checkpoint entry retry_requested is invalid"
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
                raise CrawlConfigurationError(
                    "checkpoint capture path must be absolute"
                )
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
            entry["last_error"] = (
                "CrawlInterrupted: previous process stopped during this link"
            )
            _LOGGER.warning(
                "recovered interrupted link %s as %s after %d attempts",
                entry["url"],
                entry["status"],
                entry["attempts"],
            )
            changed = True
        if changed:
            self._save_state()

    def _retry_failed_entries(self) -> None:
        if not self.retry_failed:
            return
        retried = 0
        for entry in self._state["entries"]:
            if entry["status"] != "failed":
                continue
            entry["status"] = "pending"
            entry["attempts"] = 0
            entry["session_restarts"] = 0
            entry["skipped_existing"] = False
            entry["retry_requested"] = True
            entry["captured_url"] = None
            entry["target_http_status"] = None
            entry["last_error"] = None
            retried += 1
            _LOGGER.info("re-queueing failed link %s for retry", entry["url"])
        if retried:
            self._save_state()
        _LOGGER.info("re-queued %d failed checkpoint links", retried)

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
            for status in STATUSES
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
