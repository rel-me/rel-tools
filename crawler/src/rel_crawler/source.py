"""Source navigation and rendered-link discovery."""

from __future__ import annotations

import logging
from pathlib import Path

from .errors import CrawlError, CrawlRecoveryError
from .html import canonicalize_url
from .models import Link, SourcePage

_LOGGER = logging.getLogger("rel_crawler.crawler")


class SourceMixin:
    """Private engine mixin for loading and observing the source page."""

    def _load_source_with_session_recovery(
        self, session_id: str, output: Path
    ) -> tuple[str, SourcePage, list[Link]]:
        restarts = 0
        while True:
            try:
                source = self._load_source(session_id, output)
                return session_id, source, self._discover_links(session_id, source)
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
            (f" (URI {source_uri})" if self.definition.start_url != source_uri else ""),
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
        _LOGGER.info("source is ready at %s; discovering links", operation.url)
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

    def _discover_links(self, session_id: str, source: SourcePage) -> list[Link]:
        extractor = self.definition.extract_links
        if extractor is not None:
            _LOGGER.info("running custom source link extractor")
            return list(extractor(source))

        _LOGGER.info(
            "observing rendered interactive links in session %s at %s",
            session_id,
            source.url,
        )
        self._before_browser_action()
        observation = self.client.observe_links(
            session_id=session_id,
            timeout=self.timeout,
            wait=self.wait,
        )
        if canonicalize_url(observation.url) != canonicalize_url(source.url):
            raise CrawlRecoveryError(
                "REL link observation moved away from the source page: "
                f"expected {source.url}, got {observation.url}"
            )
        if observation.truncated:
            raise CrawlError(
                "REL's rendered-link observation was truncated "
                f"after visiting {observation.visited_node_count} DOM nodes "
                f"({observation.omitted_node_count} omitted); refusing partial "
                "discovery"
            )

        source_url = canonicalize_url(source.url)
        discovered: list[Link] = []
        for rendered in observation.links:
            try:
                normalized_url = canonicalize_url(rendered.url)
            except (ValueError, UnicodeError):
                continue
            if normalized_url == source_url:
                continue
            discovered.append(
                Link(
                    index=rendered.index,
                    url=normalized_url,
                    text=rendered.text,
                    original_url=rendered.url,
                )
            )
        offscreen = sum(not link.in_viewport for link in observation.links)
        _LOGGER.info(
            "REL rendered-link observation found %d clickable anchors "
            "(%d currently outside the viewport) from %d interactive elements",
            len(observation.links),
            offscreen,
            observation.element_count,
        )
        return discovered
