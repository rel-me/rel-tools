"""Crawlee's queue and handler lifecycle backed by REL pages, without BrowserPool."""

from __future__ import annotations

import asyncio
import os
import re
import uuid
from collections.abc import AsyncGenerator, Callable, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, fields
from datetime import timedelta
from typing import Any
from urllib.parse import urljoin, urlsplit

from crawlee._types import EnqueueLinksFunction, ExtractLinksFunction
from crawlee.crawlers import BasicCrawler, BasicCrawlingContext, ContextPipeline
from crawlee.errors import ContextPipelineInterruptedError
from crawlee.statistics import FinalStatistics
from rel_playwright.async_api import (
    Page,
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


class RelCrawler(BasicCrawler[RelCrawlingContext]):
    """Crawl GET URLs using isolated REL sessions and Crawlee 1.10.0.

    Each attempt creates a fresh session from the selected Profile. Supplying
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
        manager = async_playwright()
        playwright = await manager.__aenter__()

        async def cleanup() -> None:
            await manager.__aexit__(None, None, None)
            self._pending_cleanup.pop(manager, None)

        # Register before allocating: even a cancelled launch/new_page is cleaned up.
        self._pending_cleanup[manager] = cleanup
        context.register_deferred_cleanup(cleanup)
        try:
            browser = await playwright.chromium.launch(**self._rel_options)
            page = await browser.new_page()
            response = await page.goto(request.url, timeout=self._navigation_timeout_ms)
            request.loaded_url = page.url
            request.state = RequestState.AFTER_NAV
            self._raise_for_error_status_code(response.status)
            extract_links = self._extract_links(context, page)
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
            self._classify_error(request, error)
        except RelTimeoutError as error:
            raise asyncio.TimeoutError(str(error)) from error
        except Exception as error:
            self._classify_error(request, error)
            raise

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

        return extract_links
