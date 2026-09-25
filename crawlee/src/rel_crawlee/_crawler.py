"""Crawlee's queue and handler lifecycle backed by REL pages, without BrowserPool."""

from __future__ import annotations

import asyncio
import os
import re
import uuid
from collections.abc import AsyncGenerator, Callable, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass, fields
from datetime import timedelta
from time import perf_counter
from typing import Any
from urllib.parse import urljoin, urlsplit

from crawlee._types import EnqueueLinksFunction, ExtractLinksFunction
from crawlee.crawlers import BasicCrawler, BasicCrawlingContext, ContextPipeline
from crawlee.errors import ContextPipelineInterruptedError
from crawlee.statistics import FinalStatistics
from rel_playwright.async_api import (
    Page,
    PlaywrightContextManager,
    RelRpcError,
    Response,
    UnsupportedError,
    async_playwright,
)
from rel_playwright.async_api import (
    TimeoutError as RelTimeoutError,
)
from selectolax.parser import HTMLParser
from tldextract import TLDExtract

from crawlee import ConcurrencySettings, Request, RequestState

from ._http import BrowserOnlyHttpClient
from ._metrics import RelCrawlMetrics

# A supplied session is exclusive across crawlers in this Python process.
# Other clients/processes must not operate on that session during the crawl.
_BORROWED_SESSIONS: set[tuple[int, str]] = set()
# Use the bundled Public Suffix List; never fetch metadata outside REL.
_DOMAIN = TLDExtract(suffix_list_urls=(), cache_dir=None)


def _same_domain(target: str, origin: str) -> bool:
    target_url, origin_url = urlsplit(target), urlsplit(origin)
    if (
        target_url.scheme not in {"http", "https"}
        or not target_url.hostname
        or not origin_url.hostname
    ):
        return False

    def domain(host: str) -> str:
        return _DOMAIN(host).top_domain_under_public_suffix or host

    return domain(target_url.hostname) == domain(origin_url.hostname)


@dataclass(frozen=True)
class RelCrawlingContext(BasicCrawlingContext):
    """Crawlee utilities plus a REL page and main-frame response metadata."""

    page: Page
    response: Response
    enqueue_links: EnqueueLinksFunction
    extract_links: ExtractLinksFunction


@dataclass(eq=False)
class _SessionSlot:
    manager: PlaywrightContextManager | None = None
    page: Page | None = None
    uses: int = 0
    retired: bool = True
    retirement_counted: bool = False


class RelCrawler(BasicCrawler[RelCrawlingContext]):
    """Crawl GET URLs using isolated REL sessions and Crawlee 1.10.0.

    By default each attempt creates a fresh session. session_pool_size opts into
    exclusive reuse of a bounded set of sessions from the selected Profile. Supplying
    session_id reuses that caller-owned session serially, preserving its login
    and storage. Crawlee remains the only request retry and queue owner.
    """

    def __init__(
        self,
        *,
        profile: str | None = None,
        session_id: str | None = None,
        rel_base_url: str | None = None,
        group: str | None = None,
        persist: bool = False,
        session_pool_size: int | None = None,
        max_requests_per_session: int = 100,
        navigation_timeout: timedelta = timedelta(seconds=30),
        concurrency_settings: ConcurrencySettings | None = None,
        **kwargs: Any,
    ) -> None:
        # These BasicCrawler options would bypass REL's ownership or our pipeline.
        forbidden = {
            "http_client",
            "proxy_configuration",
            "session_pool",
            "max_session_rotations",
            "_context_pipeline",
            "_additional_context_managers",
            "ignore_http_error_status_codes",
            "additional_http_error_status_codes",
        }
        for name in forbidden.intersection(kwargs):
            raise UnsupportedError(
                f"RelCrawler does not support {name}; browser configuration belongs to REL"
            )
        for name in ("use_session_pool", "retry_on_blocked", "respect_robots_txt_file"):
            if kwargs.pop(name, False) is not False:
                raise UnsupportedError(f"RelCrawler requires {name}=False")
        if profile is not None and session_id is not None:
            raise ValueError(
                "Choose profile or session_id; a supplied session already has its configuration"
            )
        if session_id is not None and not re.fullmatch(
            r"Session[1-9][0-9]*", session_id, re.IGNORECASE
        ):
            raise ValueError("session_id must use the Session<number> format")
        if navigation_timeout.total_seconds() <= 0:
            raise ValueError("navigation_timeout must be positive")
        concurrency_settings = concurrency_settings or ConcurrencySettings(
            max_concurrency=1, desired_concurrency=1
        )
        if session_id is not None and concurrency_settings.max_concurrency != 1:
            raise ValueError("A supplied session_id requires max_concurrency=1")
        if session_pool_size is not None:
            if (
                isinstance(session_pool_size, bool)
                or not isinstance(session_pool_size, int)
                or session_pool_size < 1
            ):
                raise ValueError("session_pool_size must be a positive integer or None")
            if session_id is not None or persist:
                raise ValueError(
                    "Session pooling cannot be combined with session_id or persist=True"
                )
        if (
            isinstance(max_requests_per_session, bool)
            or not isinstance(max_requests_per_session, int)
            or max_requests_per_session < 1
        ):
            raise ValueError("max_requests_per_session must be a positive integer")
        if session_pool_size is None and max_requests_per_session != 100:
            raise ValueError("max_requests_per_session requires session_pool_size")
        self._pool_size = session_pool_size
        self._max_requests_per_session = max_requests_per_session
        self._pool: asyncio.Queue[_SessionSlot] | None = None
        self._pool_stopping = False
        self._metrics = asdict(RelCrawlMetrics())
        self._rel_options = {
            "profile": profile,
            "session_id": session_id,
            "rel_base_url": rel_base_url
            or f"http://127.0.0.1:{os.environ.get('REL_AGENT_PORT', '17319')}/v1",
            "group": group or f"rel-crawlee-{uuid.uuid4().hex}",
            "persist": persist,
        }
        self._navigation_timeout_ms = navigation_timeout.total_seconds() * 1000
        self._pending_cleanup: dict[object, Callable[..., Any]] = {}
        self._rel_active = False
        super().__init__(
            **kwargs,
            concurrency_settings=concurrency_settings,
            use_session_pool=False,
            retry_on_blocked=False,
            respect_robots_txt_file=False,
            http_client=BrowserOnlyHttpClient(),
            _context_pipeline=ContextPipeline().compose(self._navigate),
        )

    @property
    def metrics(self) -> RelCrawlMetrics:
        """Immutable, bounded snapshot of timings and counters for the latest run."""
        return RelCrawlMetrics(**self._metrics)

    async def run(
        self,
        requests: Sequence[str | Request] | None = None,
        *,
        purge_request_queue: bool = True,
    ) -> FinalStatistics:
        # Reserve before Crawlee changes run/queue state. Failed lease acquisition
        # is safe to retry after the competing crawl finishes.
        async with self._resources():
            return await super().run(requests, purge_request_queue=purge_request_queue)

    @asynccontextmanager
    async def _resources(self) -> AsyncGenerator[None, None]:
        session_id = self._rel_options["session_id"]
        # Loopback host aliases and /v1 spellings identify the same runtime port.
        key = (
            urlsplit(str(self._rel_options["rel_base_url"])).port or 80,
            str(session_id).lower(),
        )
        if self._rel_active or (session_id and key in _BORROWED_SESSIONS):
            raise RuntimeError(
                "This REL session is already leased by an active crawler"
            )
        self._rel_active = True
        if session_id:
            _BORROWED_SESSIONS.add(key)
        try:
            # Unresolved cleanup from an earlier run must succeed before allocating
            # a new pool; failed deletion never grants additional capacity.
            await self._cleanup_all()
            self._metrics = asdict(RelCrawlMetrics())
            self._pool_stopping = False
            if self._pool_size is not None:
                self._pool = asyncio.Queue(maxsize=self._pool_size)
                for _ in range(self._pool_size):
                    self._pool.put_nowait(_SessionSlot())
            yield
        finally:
            try:
                cleanup_task = asyncio.create_task(self._cleanup_all())
                try:
                    await asyncio.shield(cleanup_task)
                except asyncio.CancelledError:
                    # Finish all leases even if shutdown itself is cancelled again.
                    while not cleanup_task.done():
                        try:
                            await asyncio.shield(cleanup_task)
                        except asyncio.CancelledError:
                            continue
                    cleanup_task.result()
                    raise
            finally:
                self._pool = None
                self._rel_active = False
                _BORROWED_SESSIONS.discard(key)

    async def _cleanup_all(self) -> None:
        errors = []
        for cleanup in list(self._pending_cleanup.values()):
            try:
                await cleanup()
            except Exception as error:
                errors.append(error)
        if errors:
            raise ExceptionGroup("REL session cleanup failed", errors)

    @staticmethod
    def _classify_error(request: Request, error: Exception | None) -> None:
        if isinstance(error, UnsupportedError) or (
            isinstance(error, RelRpcError) and not error.retryable
        ):
            request.no_retry = True

    async def _run_request_handler(self, context: BasicCrawlingContext) -> None:
        try:
            await super()._run_request_handler(context)
        except asyncio.CancelledError:
            # Crawlee cancels workers sequentially during shutdown. Stop queued
            # lessees before the first cancelled worker gives its slot back.
            self._pool_stopping = True
            raise

    async def _navigate(
        self, context: BasicCrawlingContext
    ) -> AsyncGenerator[RelCrawlingContext, None]:
        request = context.request
        if (
            request.method != "GET"
            or request.payload is not None
            or request.headers
            or request.session_id
        ):
            request.no_retry = True
            raise UnsupportedError(
                "RelCrawler accepts GET requests without headers, payloads, or Crawlee session IDs"
            )
        self._metrics["requests_started"] += 1
        wait_start = perf_counter()
        try:
            slot = await self._pool.get() if self._pool is not None else _SessionSlot()
        finally:
            self._metrics["session_wait_seconds"] += perf_counter() - wait_start
        # Reserve through deferred cleanup, including error handlers and cancelled
        # RPC workers. Slots are never made available by pipeline finalization.
        context.register_deferred_cleanup(lambda: self._release_slot(slot))
        try:
            if self._pool is not None and self._pool_stopping:
                raise asyncio.CancelledError
            acquire_start = perf_counter()
            try:
                if slot.retired or (slot.page is not None and slot.page.is_closed()):
                    await self._close_slot(slot)
                if slot.page is None:
                    slot.manager = async_playwright()
                    self._pending_cleanup[slot] = lambda: self._close_slot(slot)
                    playwright = await slot.manager.__aenter__()
                    browser = await playwright.chromium.launch(**self._rel_options)
                    slot.page = await browser.new_page()
                    slot.uses = 0
                    slot.retirement_counted = False
                    if self._rel_options["session_id"] is None:
                        self._metrics["sessions_created"] += 1
                else:
                    self._metrics["session_reuses"] += 1
                page = slot.page
                slot.uses += 1
            finally:
                self._metrics["session_acquire_seconds"] += (
                    perf_counter() - acquire_start
                )
            # Only a completed, successful pipeline makes a slot reusable.
            slot.retired = True
            navigation_start = perf_counter()
            try:
                response = await page.goto(
                    request.url, timeout=self._navigation_timeout_ms
                )
                request.loaded_url = page.url
                request.state = RequestState.AFTER_NAV
                self._raise_for_error_status_code(response.status)
            finally:
                self._metrics["navigation_seconds"] += perf_counter() - navigation_start
            extract_links = self._extract_links(context, page)
            handler_start = perf_counter()
            try:
                error = yield RelCrawlingContext(
                    **{
                        field.name: getattr(context, field.name)
                        for field in fields(BasicCrawlingContext)
                    },
                    page=page,
                    response=response,
                    extract_links=extract_links,
                    enqueue_links=self._create_enqueue_links_function(
                        context, extract_links
                    ),
                )
            finally:
                self._metrics["handler_seconds"] += perf_counter() - handler_start
            self._classify_error(request, error)
            task = asyncio.current_task()
            slot.retired = error is not None or bool(task and task.cancelling())
        except RelTimeoutError as error:
            raise asyncio.TimeoutError(str(error)) from error
        except Exception as error:
            self._classify_error(request, error)
            raise

    async def _release_slot(self, slot: _SessionSlot) -> None:
        if self._pool is None:
            await self._close_slot(slot)
            return
        slot.retired |= (
            self._pool_stopping
            or slot.uses >= self._max_requests_per_session
            or bool(slot.page and slot.page.is_closed())
        )
        try:
            if slot.retired:
                if slot.page is not None and not slot.retirement_counted:
                    slot.retirement_counted = True
                    self._metrics["sessions_retired"] += 1
                await self._close_slot(slot)
        finally:
            # Failed deletion retains this same retired slot. Its next lessee must
            # successfully close it before creating a replacement.
            self._pool.put_nowait(slot)

    async def _close_slot(self, slot: _SessionSlot) -> None:
        if slot.manager is None:
            return
        start = perf_counter()
        try:
            await slot.manager.__aexit__(None, None, None)
            slot.manager = None
            slot.page = None
            slot.uses = 0
            self._pending_cleanup.pop(slot, None)
        finally:
            self._metrics["cleanup_seconds"] += perf_counter() - start

    async def _check_url_after_redirects(
        self, context: RelCrawlingContext
    ) -> AsyncGenerator[RelCrawlingContext, None]:
        if context.request.enqueue_strategy == "same-domain":
            if context.request.loaded_url and not _same_domain(
                context.request.loaded_url, context.request.url
            ):
                raise ContextPipelineInterruptedError(
                    "REL navigation redirected outside the requested domain"
                )
            yield context
        else:
            async for checked in super()._check_url_after_redirects(context):
                yield checked

    def _enqueue_links_filter_iterator(
        self, request_iterator: Any, origin_url: str, **kwargs: Any
    ) -> Any:
        if kwargs.get("strategy") != "same-domain":
            yield from super()._enqueue_links_filter_iterator(
                request_iterator, origin_url, **kwargs
            )
            return
        # Crawlee's same-domain filter downloads a PSL by default. Resolve only
        # that comparison locally, retaining Crawlee's include/exclude filtering.
        limit = kwargs.pop("limit", None)
        if limit is not None and limit <= 0:
            return
        kwargs["strategy"] = "all"
        count = 0
        for request in super()._enqueue_links_filter_iterator(
            request_iterator, origin_url, **kwargs
        ):
            if _same_domain(
                request.url if isinstance(request, Request) else request, origin_url
            ):
                if isinstance(request, Request):
                    request.enqueue_strategy = "same-domain"
                yield request
                count += 1
                if limit is not None and count >= limit:
                    break

    def _extract_links(
        self, context: BasicCrawlingContext, page: Page
    ) -> Callable[..., Any]:
        async def extract_links(
            *,
            selector: str = "a",
            attribute: str = "href",
            label: str | None = None,
            user_data: Mapping[str, Any] | None = None,
            transform_request_function: Callable[..., Any] | None = None,
            **kwargs: Any,
        ) -> list[Request]:
            unknown = kwargs.keys() - {
                "limit",
                "base_url",
                "strategy",
                "include",
                "exclude",
            }
            if unknown:
                raise TypeError(f"Unknown link options: {', '.join(sorted(unknown))}")
            if kwargs.get("limit") is not None and kwargs["limit"] <= 0:
                return []
            html = HTMLParser(await page.content())
            document_url = page.url
            base = html.css_first("base[href]")
            base_url = kwargs.pop("base_url", None) or (
                urljoin(document_url, base.attributes["href"]) if base else document_url
            )
            strategy = kwargs.setdefault("strategy", "same-hostname")
            candidates: list[Request] = []
            seen: set[str] = set()
            for element in html.css(selector):
                href = element.attributes.get(attribute)
                if href is None:
                    continue
                try:
                    url = urljoin(base_url, href.strip())
                    if urlsplit(url).scheme not in {"http", "https"}:
                        continue
                except ValueError as error:
                    context.log.debug("Skipping malformed link: %s", error)
                    continue
                options = {
                    "url": url,
                    "label": label,
                    "user_data": dict(user_data or {}),
                    "enqueue_strategy": strategy,
                }
                if transform_request_function:
                    transformed = transform_request_function(options.copy())
                    if transformed == "skip":
                        continue
                    if transformed != "unchanged":
                        options = transformed
                try:
                    request = Request.from_url(**options)
                except ValueError as error:
                    context.log.debug("Skipping malformed request URL: %s", error)
                    continue
                if request.unique_key not in seen:
                    candidates.append(request)
                    seen.add(request.unique_key)
            return list(
                self._enqueue_links_filter_iterator(
                    iter(candidates), document_url, **kwargs
                )
            )

        async def timed_extract_links(**kwargs: Any) -> list[Request]:
            start = perf_counter()
            try:
                return await extract_links(**kwargs)
            finally:
                self._metrics["link_extraction_seconds"] += perf_counter() - start

        return timed_extract_links
