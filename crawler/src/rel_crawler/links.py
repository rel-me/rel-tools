"""Link selection, checkpoint merging, and existing-capture skips."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .errors import CrawlConfigurationError
from .html import canonicalize_url
from .models import CrawlItem, Link

_LOGGER = logging.getLogger("rel_crawler.crawler")


class LinkQueueMixin:
    """Private engine mixin for the durable selected-link queue."""

    def _merge_links(
        self,
        discovered: list[Link],
        *,
        reconcile_unavailable: bool = True,
    ) -> tuple[set[str], set[str]]:
        eligible: list[tuple[str, Link]] = []
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
            eligible.append((key, link))

        selected = (
            eligible[: self.max_links] if self.max_links is not None else eligible
        )

        entries = self._state["entries"]
        existing = {entry["key"]: entry for entry in entries}
        path_updates: list[tuple[dict[str, Any], Path, Path]] = []
        for key, link in selected:
            entry = existing.get(key)
            if entry is None or entry["status"] != "pending" or entry["attempts"] != 0:
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
                "retry_requested": False,
                "captured_url": None,
                "target_http_status": None,
                "last_error": None,
            }
            entries.append(entry)
            existing[key] = entry
        active_keys = {key for key, _link in selected}
        unavailable_count = (
            self._reconcile_unavailable(selected_keys) if reconcile_unavailable else 0
        )
        self._save_state()
        _LOGGER.info(
            "link discovery found %d anchors, selected %d, marked %d unavailable, "
            "checkpoint now has %d entries",
            len(discovered),
            len(selected),
            unavailable_count,
            len(entries),
        )
        return selected_keys, active_keys

    def _reconcile_unavailable(self, discoverable_keys: set[str]) -> int:
        unavailable_count = 0
        for entry in self._state["entries"]:
            if entry["status"] != "pending" or entry["key"] in discoverable_keys:
                continue
            entry["status"] = "failed"
            entry["retry_requested"] = False
            entry["last_error"] = (
                "CrawlLinkUnavailable: the source page no longer exposes this URL "
                "as a rendered interactive anchor"
            )
            unavailable_count += 1
            _LOGGER.info(
                "skipping unavailable checkpoint link %s; it is not currently "
                "rendered and clickable on the source page",
                entry["url"],
            )
        if unavailable_count:
            self._save_state()
        return unavailable_count

    def _skip_existing_captures(
        self,
        *,
        allowed_keys: set[str] | None = None,
    ) -> None:
        if not self.skip_existing:
            return
        changed = False
        for entry in self._state["entries"]:
            if entry["status"] != "pending" or entry["attempts"] != 0:
                continue
            if allowed_keys is not None and entry["key"] not in allowed_keys:
                continue
            if entry.get("retry_requested", False):
                _LOGGER.info(
                    "retry will overwrite any existing failed capture for %s",
                    entry["url"],
                )
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
            entry["retry_requested"] = False
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
            self._report_skip(f"existing capture {entry['url']} -> {output_path}")
            changed = True
        if changed:
            self._save_state()
