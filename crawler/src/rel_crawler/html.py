"""Serialized-HTML helpers for custom link discovery and page metadata."""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import SplitResult, quote, urldefrag, urljoin, urlsplit, urlunsplit

from .models import Link

_PUBLISHED_TIMESTAMP_FIELDS = {
    "articlepublishedtime",
    "date",
    "dateissued",
    "datepublished",
    "dcdate",
    "dcdateissued",
    "dctermsissued",
    "publicationdate",
    "pubdate",
    "publishdate",
    "releasedate",
    "uploaddate",
}
_MODIFIED_TIMESTAMP_FIELDS = {
    "articlemodifiedtime",
    "datemodified",
    "dctermsmodified",
    "lastmodified",
    "modifiedtime",
    "ogupdatedtime",
}
_PUBLISHED_TIMESTAMP_SUFFIXES = {
    "dateissued",
    "datepublished",
    "publicationdate",
    "pubdate",
    "publishdate",
    "releasedate",
    "uploaddate",
}
_MODIFIED_TIMESTAMP_SUFFIXES = {
    "datemodified",
    "lastmodified",
    "modifiedtime",
    "updatedtime",
}
_VALID_PERCENT_ESCAPE = re.compile(r"%([0-9A-Fa-f]{2})")
_STRAY_PERCENT = re.compile(r"%(?![0-9A-Fa-f]{2})")
_PATH_SAFE = "/:@!$&'()*+,;=-._~%"
_QUERY_SAFE = "/?:@!$&'()*+,;=-._~%"


def _uri_component(value: str, *, safe: str) -> str:
    normalized = _STRAY_PERCENT.sub("%25", value)
    normalized = _VALID_PERCENT_ESCAPE.sub(
        lambda match: f"%{match.group(1).upper()}",
        normalized,
    )
    return quote(normalized, safe=safe, encoding="utf-8", errors="strict")


def _timestamp_kind(field: str) -> str | None:
    normalized = "".join(
        character for character in field.casefold() if character.isalnum()
    )
    if normalized in _PUBLISHED_TIMESTAMP_FIELDS or any(
        normalized.endswith(suffix) for suffix in _PUBLISHED_TIMESTAMP_SUFFIXES
    ):
        return "published"
    if normalized in _MODIFIED_TIMESTAMP_FIELDS or any(
        normalized.endswith(suffix) for suffix in _MODIFIED_TIMESTAMP_SUFFIXES
    ):
        return "modified"
    return None


def _append_timestamp(
    timestamps: dict[str, list[dict[str, Any]]],
    kind: str,
    record: dict[str, Any],
) -> None:
    if record not in timestamps[kind]:
        timestamps[kind].append(record)


def canonicalize_url(url: str) -> str:
    """Return a stable ASCII HTTP(S) URI without changing query ordering."""

    split = urlsplit(url)
    scheme = split.scheme.lower()
    hostname = split.hostname or ""
    if scheme not in {"http", "https"} or not hostname:
        raise ValueError(f"expected an HTTP(S) URL, got {url!r}")
    if split.username is not None or split.password is not None:
        raise ValueError("URL credentials are not supported")

    if ":" in hostname:
        hostname = _uri_component(hostname.lower(), safe=":.%-_~")
    else:
        hostname = hostname.encode("idna").decode("ascii").lower()

    port = split.port
    if (scheme, port) in {("http", 80), ("https", 443)}:
        port = None
    host = f"[{hostname}]" if ":" in hostname else hostname
    if port is not None:
        host = f"{host}:{port}"
    return urlunsplit(
        SplitResult(
            scheme,
            host,
            _uri_component(split.path or "/", safe=_PATH_SAFE),
            _uri_component(split.query, safe=_QUERY_SAFE),
            "",
        )
    )


class _AnchorParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.links: list[Link] = []
        self._active: dict[str, object] | None = None

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag.casefold() != "a":
            return
        if self._active is not None:
            self._finish_anchor()
        values = {name.casefold(): value for name, value in attrs}
        self._active = {
            "href": values.get("href"),
            "target": values.get("target"),
            "rel": tuple((values.get("rel") or "").split()),
            "text": [],
        }

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self.handle_starttag(tag, attrs)
        if tag.casefold() == "a":
            self._finish_anchor()

    def handle_data(self, data: str) -> None:
        if self._active is not None:
            text = self._active["text"]
            assert isinstance(text, list)
            text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "a" and self._active is not None:
            self._finish_anchor()

    def close(self) -> None:
        super().close()
        if self._active is not None:
            self._finish_anchor()

    def _finish_anchor(self) -> None:
        active = self._active
        self._active = None
        if active is None:
            return
        href = active["href"]
        if not isinstance(href, str) or not href.strip():
            return
        resolved, _fragment = urldefrag(urljoin(self.base_url, href.strip()))
        original_url = resolved
        split = urlsplit(resolved)
        if split.scheme.lower() not in {"http", "https"} or not split.hostname:
            return
        try:
            resolved = canonicalize_url(resolved)
        except (ValueError, UnicodeError):
            return
        if resolved == canonicalize_url(self.base_url):
            return

        raw_text = active["text"]
        assert isinstance(raw_text, list)
        text = " ".join("".join(str(part) for part in raw_text).split())
        target = active["target"]
        rel = active["rel"]
        self.links.append(
            Link(
                index=len(self.links),
                url=resolved,
                text=text,
                target=target if isinstance(target, str) else None,
                rel=rel if isinstance(rel, tuple) else (),
                original_url=original_url,
            )
        )


def extract_links(html: str, base_url: str) -> list[Link]:
    """Extract absolute, defragmented HTTP(S) links from serialized HTML."""

    canonicalize_url(base_url)
    parser = _AnchorParser(base_url)
    parser.feed(html)
    parser.close()
    return parser.links


class _PageMetadataParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.title: str | None = None
        self.canonical_url: str | None = None
        self.meta: list[dict[str, str]] = []
        self.content_timestamps: dict[str, list[dict[str, Any]]] = {
            "published": [],
            "modified": [],
        }
        self.json_ld_documents: list[str] = []
        self._title_chunks: list[str] | None = None
        self._json_ld_chunks: list[str] | None = None

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        tag = tag.casefold()
        values = {name.casefold(): value for name, value in attrs}
        if tag == "title" and self.title is None:
            self._title_chunks = []
            return
        if tag == "script":
            content_type = values.get("type")
            if (
                self._json_ld_chunks is None
                and isinstance(content_type, str)
                and content_type.split(";", 1)[0].strip().casefold()
                == "application/ld+json"
            ):
                self._json_ld_chunks = []
            return
        if tag == "meta":
            record = {
                name: value
                for name in ("name", "property", "http-equiv", "itemprop", "charset")
                if isinstance((value := values.get(name)), str) and value
            }
            content = values.get("content")
            if isinstance(content, str):
                record["content"] = content
            if record:
                self.meta.append(record)
            if isinstance(content, str) and content.strip():
                for attribute in ("itemprop", "property", "name", "http-equiv"):
                    field = values.get(attribute)
                    if not isinstance(field, str):
                        continue
                    kind = _timestamp_kind(field)
                    if kind is not None:
                        _append_timestamp(
                            self.content_timestamps,
                            kind,
                            {
                                "value": content.strip(),
                                "source": "meta",
                                "field": field,
                                "attribute": attribute,
                            },
                        )
            return
        itemprop = values.get("itemprop")
        if isinstance(itemprop, str):
            value = next(
                (
                    candidate.strip()
                    for attribute in ("datetime", "content", "value")
                    if isinstance((candidate := values.get(attribute)), str)
                    and candidate.strip()
                ),
                None,
            )
            if value is not None:
                for field in itemprop.split():
                    kind = _timestamp_kind(field)
                    if kind is not None:
                        _append_timestamp(
                            self.content_timestamps,
                            kind,
                            {
                                "value": value,
                                "source": "element",
                                "field": field,
                                "element": tag,
                            },
                        )
        if tag != "link" or self.canonical_url is not None:
            return
        rel = values.get("rel")
        href = values.get("href")
        if not isinstance(rel, str) or not isinstance(href, str):
            return
        if "canonical" not in {value.casefold() for value in rel.split()}:
            return
        resolved, _fragment = urldefrag(urljoin(self.base_url, href))
        try:
            self.canonical_url = canonicalize_url(resolved)
        except (ValueError, UnicodeError):
            return

    def handle_data(self, data: str) -> None:
        if self._title_chunks is not None:
            self._title_chunks.append(data)
        if self._json_ld_chunks is not None:
            self._json_ld_chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if tag == "title" and self._title_chunks is not None:
            title = " ".join("".join(self._title_chunks).split())
            self.title = title or None
            self._title_chunks = None
        if tag == "script" and self._json_ld_chunks is not None:
            document = "".join(self._json_ld_chunks).strip()
            if document:
                self.json_ld_documents.append(document)
            self._json_ld_chunks = None


def _extract_json_ld_timestamps(
    documents: list[str], timestamps: dict[str, list[dict[str, Any]]]
) -> None:
    for script_index, document in enumerate(documents):
        try:
            root = json.loads(document)
        except (json.JSONDecodeError, TypeError):
            continue
        pending = [root]
        visited = 0
        while pending and visited < 100_000:
            value = pending.pop()
            visited += 1
            if isinstance(value, list):
                pending.extend(value)
                continue
            if not isinstance(value, dict):
                continue
            for field, child in value.items():
                kind = _timestamp_kind(str(field))
                timestamp_value = child
                if (
                    kind is not None
                    and isinstance(child, dict)
                    and isinstance(child.get("@value"), (str, int, float))
                ):
                    timestamp_value = child["@value"]
                if kind is not None and isinstance(
                    timestamp_value, (str, int, float)
                ):
                    rendered = str(timestamp_value).strip()
                    if rendered:
                        _append_timestamp(
                            timestamps,
                            kind,
                            {
                                "value": rendered,
                                "source": "json-ld",
                                "field": str(field),
                                "script_index": script_index,
                            },
                        )
                if isinstance(child, (dict, list)):
                    pending.append(child)


def extract_page_metadata(html: str, base_url: str) -> dict[str, Any]:
    """Extract document identity, meta elements, and content timestamps."""

    canonicalize_url(base_url)
    parser = _PageMetadataParser(base_url)
    parser.feed(html)
    parser.close()
    _extract_json_ld_timestamps(parser.json_ld_documents, parser.content_timestamps)
    return {
        "title": parser.title,
        "canonical_url": parser.canonical_url,
        "meta": parser.meta,
        "content_timestamps": parser.content_timestamps,
    }
