"""Capture paths, metadata sidecars, and checkpoint item conversion."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .api import PageOperation
from .errors import CrawlConfigurationError, CrawlError
from .html import extract_page_metadata
from .models import CapturedPage, CrawlItem, Link

METADATA_SCHEMA_VERSION = 4
_LOGGER = logging.getLogger("rel_crawler.crawler")


class CaptureMixin:
    """Private engine mixin for captured files and metadata sidecars."""

    def _captured_page(self, item: CrawlItem, operation: PageOperation) -> CapturedPage:
        metadata_path = self._metadata_path(operation.output_path)
        self._write_page_metadata(
            item=item,
            page_url=operation.url,
            output_path=operation.output_path,
            bytesize=operation.bytesize,
            target_http_status=operation.target_http_status,
            session_id=operation.session_id,
            captured_at=datetime.now(UTC),
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
                    and existing_schema >= METADATA_SCHEMA_VERSION
                ):
                    continue
                _LOGGER.info("backfilling metadata for %s", output_path)
                captured_at = self._existing_capture_time(
                    existing,
                    datetime.fromtimestamp(
                        output_path.stat().st_mtime,
                        tz=UTC,
                    ),
                )
                existing_page = (
                    existing.get("page") if isinstance(existing, dict) else None
                )
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
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return fallback
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
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
            raise CrawlError(
                f"Could not read REL capture {output_path}: {error}"
            ) from error
        captured_at_utc = captured_at.astimezone(UTC)
        metadata: dict[str, Any] = {
            "schema_version": METADATA_SCHEMA_VERSION,
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
