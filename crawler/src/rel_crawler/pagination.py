"""Incremental source-page expansion for rendered link batches."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from .api import RelRpcError
from .errors import CrawlError, CrawlPageError, CrawlRecoveryError
from .html import canonicalize_url
from .models import Link, SourcePage

_LOGGER = logging.getLogger("rel_crawler.crawler")


class PaginationMixin:
    """Private engine mixin that expands and restores load-more batches."""

    def _expand_source_with_session_recovery(
        self,
        session_id: str,
        output: Path,
        *,
        click_number: int,
    ) -> tuple[str, list[Link] | None]:
        restarts = 0
        while True:
            try:
                discovered = self._click_load_more_and_wait(
                    session_id,
                    output,
                    click_number=click_number,
                    replay=False,
                )
                return session_id, discovered
            except RelRpcError as error:
                if error.id == "ACTION_TARGET_NOT_FOUND":
                    _LOGGER.info(
                        "load-more selector %r is no longer clickable after %d clicks; "
                        "pagination is complete",
                        self.load_more_selector,
                        click_number - 1,
                    )
                    return session_id, None
                if (
                    restarts >= self.max_session_restarts
                    or not self._can_restart_session(error)
                ):
                    raise
                _LOGGER.warning(
                    "load-more click %d failed in session %s; "
                    "replacing session: %s: %s",
                    click_number,
                    session_id,
                    type(error).__name__,
                    error,
                )
                session_id = self._restart_managed_session(
                    session_id,
                    reason=(
                        f"load-more click {click_number} failed: "
                        f"{type(error).__name__}: {error}"
                    ),
                )
                self._navigate_to_source(session_id, output)
                restarts += 1
            except Exception as error:
                if (
                    restarts >= self.max_session_restarts
                    or not self._can_restart_session(error)
                ):
                    raise
                _LOGGER.warning(
                    "load-more click %d failed in session %s; "
                    "replacing session: %s: %s",
                    click_number,
                    session_id,
                    type(error).__name__,
                    error,
                )
                session_id = self._restart_managed_session(
                    session_id,
                    reason=(
                        f"load-more click {click_number} failed: "
                        f"{type(error).__name__}: {error}"
                    ),
                )
                self._navigate_to_source(session_id, output)
                restarts += 1

    def _click_load_more_and_wait(
        self,
        session_id: str,
        output: Path,
        *,
        click_number: int,
        replay: bool,
        previous: list[Link] | None = None,
    ) -> list[Link]:
        assert self.load_more_selector is not None
        if previous is None:
            previous = self._discover_links(
                session_id,
                SourcePage(
                    url=self._state.get("source_url") or self.definition.start_url,
                    output_path=output,
                    html="",
                ),
            )
        previous_urls = {link.url for link in previous}
        label = "replaying" if replay else "loading"
        _LOGGER.info(
            "%s source batch %d/%d: scrolling to and clicking selector %r",
            label,
            click_number,
            self.load_more_clicks,
            self.load_more_selector,
        )
        self._before_browser_action()
        operation = self.client.perform(
            actions=[
                {
                    "action": "click",
                    "selector": self.load_more_selector,
                    "scroll": True,
                }
            ],
            session_id=session_id,
            output=output,
            timeout=self.timeout,
            wait=self.wait,
        )
        if canonicalize_url(operation.url) != canonicalize_url(
            self._state.get("source_url") or self.definition.start_url
        ):
            raise CrawlRecoveryError(
                f"load-more click moved away from the source page: got {operation.url}"
            )
        if (
            not self.accept_http_errors
            and operation.target_http_status is not None
            and operation.target_http_status >= 400
        ):
            raise CrawlPageError(
                f"load-more source {operation.url} returned HTTP "
                f"{operation.target_http_status}"
            )
        self._state["source_url"] = operation.url
        self._save_state()
        try:
            html = operation.output_path.read_text(encoding="utf-8", errors="replace")
        except OSError as error:
            raise CrawlError(
                f"Could not read load-more capture {operation.output_path}: {error}"
            ) from error
        source = SourcePage(
            url=operation.url,
            output_path=operation.output_path,
            html=html,
            target_http_status=operation.target_http_status,
        )
        deadline = time.monotonic() + self.timeout
        observation_number = 0
        while True:
            observation_number += 1
            _LOGGER.info(
                "waiting for new rendered links after load-more click %d "
                "(observation %d)",
                click_number,
                observation_number,
            )
            discovered = self._discover_links(session_id, source)
            new_urls = {link.url for link in discovered} - previous_urls
            if new_urls:
                _LOGGER.info(
                    "load-more click %d added %d rendered links",
                    click_number,
                    len(new_urls),
                )
                return discovered
            if time.monotonic() >= deadline:
                raise CrawlError(
                    f"load-more click {click_number} did not add rendered links "
                    f"within {self.timeout:g} seconds"
                )

    def _replay_load_more(
        self,
        session_id: str,
        output: Path,
        *,
        depth: int,
    ) -> None:
        if depth <= 0:
            return
        _LOGGER.info(
            "restoring %d completed load-more clicks in session %s",
            depth,
            session_id,
        )
        previous: list[Link] | None = None
        for click_number in range(1, depth + 1):
            try:
                previous = self._click_load_more_and_wait(
                    session_id,
                    output,
                    click_number=click_number,
                    replay=True,
                    previous=previous,
                )
            except RelRpcError as error:
                if error.id == "ACTION_TARGET_NOT_FOUND":
                    raise CrawlRecoveryError(
                        "could not restore source expansion because load-more "
                        f"selector {self.load_more_selector!r} disappeared at "
                        f"click {click_number}/{depth}"
                    ) from error
                raise
        _LOGGER.info("restored %d load-more clicks", depth)
