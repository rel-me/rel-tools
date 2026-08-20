"""Public data types used to define and process a REL crawl."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Link:
    """One rendered anchor with an ASCII URI and optional original IRI."""

    index: int
    url: str
    text: str
    target: str | None = None
    rel: tuple[str, ...] = ()
    original_url: str | None = None


@dataclass(frozen=True, slots=True)
class SourcePage:
    """The rendered source page supplied to a custom link extractor."""

    url: str
    output_path: Path
    html: str
    target_http_status: int | None = None


@dataclass(frozen=True, slots=True)
class CrawlItem:
    """A selected link and its stable identity within the crawl."""

    key: str
    index: int
    link: Link
    attempt: int


@dataclass(frozen=True, slots=True)
class CapturedPage:
    """A child page captured by REL after clicking its source-page link."""

    item: CrawlItem
    url: str
    output_path: Path
    bytesize: int
    target_http_status: int | None
    session_id: str
    metadata_path: Path


@dataclass(frozen=True, slots=True)
class CrawlFailure:
    """A bounded link failure that the crawler checkpointed and skipped."""

    item: CrawlItem
    error: Exception
    terminal: bool


@dataclass(frozen=True, slots=True)
class CrawlSummary:
    """Final checkpoint counts returned by :meth:`RelCrawler.run`."""

    discovered: int
    captured: int
    failed: int
    pending: int
    skipped_existing: int
    session_id: str
    session_generation: int
    session_restart_count: int
    state_path: Path


SelectLink = Callable[[Link], bool]
ExtractLinks = Callable[[SourcePage], Iterable[Link]]
CapturePath = Callable[[CrawlItem], str | Path]
ProcessCapture = Callable[[CapturedPage], None]
ProcessFailure = Callable[[CrawlFailure], None]
LinkKey = Callable[[Link], str]


def _select_every_link(_link: Link) -> bool:
    return True


def _ignore_capture(_capture: CapturedPage) -> None:
    return None


def _ignore_failure(_failure: CrawlFailure) -> None:
    return None


def _url_key(link: Link) -> str:
    return link.url


@dataclass(frozen=True, slots=True)
class CrawlDefinition:
    """Callbacks that describe which links to crawl and how to handle captures."""

    start_url: str
    select_link: SelectLink = _select_every_link
    capture_path: CapturePath | None = None
    process_capture: ProcessCapture = _ignore_capture
    process_failure: ProcessFailure = _ignore_failure
    extract_links: ExtractLinks | None = None
    link_key: LinkKey = _url_key
    source_ready_selector: str | None = None
    capture_ready_selector: str | None = None
    load_more_selector: str | None = None
    load_more_clicks: int = 0
