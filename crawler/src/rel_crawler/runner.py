"""Per-link capture, callbacks, retries, and browser recovery."""

from __future__ import annotations

import logging
from pathlib import Path

from .api import PageOperation
from .errors import CrawlPageError, CrawlRecoveryError
from .models import CrawlFailure

_LOGGER = logging.getLogger("rel_crawler.crawler")


class LinkRunnerMixin:
    """Private engine mixin that drains pending checkpoint links."""

    def _crawl_pending(
        self,
        session_id: str,
        recovery_output: Path,
        *,
        allowed_keys: set[str] | None = None,
    ) -> str:
        while True:
            entry = next(
                (
                    entry
                    for entry in self._state["entries"]
                    if entry["status"] == "pending"
                    and (allowed_keys is None or entry["key"] in allowed_keys)
                ),
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
                    (f" (URI {item.link.url})" if display_url != item.link.url else ""),
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
            except Exception as error:  # noqa: BLE001 - bound arbitrary client errors
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
                except Exception as error:  # noqa: BLE001 - capture I/O is user-facing
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
                        _LOGGER.info(
                            "finished processing captured page %s",
                            captured.url,
                        )
                    except Exception as error:  # noqa: BLE001 - callbacks are user code
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
                entry["retry_requested"] = False
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
                if terminal:
                    entry["retry_requested"] = False
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
                except Exception as callback_error:  # noqa: BLE001 - callbacks are user code
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
                can_restart = entry[
                    "session_restarts"
                ] < self.max_session_restarts and self._can_restart_session(
                    recovery_error
                )
                if can_restart:
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
                    f"Could not restore {self.definition.start_url!r} "
                    f"after {item.link.url!r}: "
                    f"{recovery_error}"
                ) from recovery_error
