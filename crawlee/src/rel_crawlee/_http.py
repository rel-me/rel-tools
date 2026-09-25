"""Prevent Crawlee helpers from making requests outside REL."""

from typing import Any

from crawlee.http_clients import HttpClient
from rel_playwright.async_api import UnsupportedError


class BrowserOnlyHttpClient(HttpClient):
    def __init__(self) -> None:
        super().__init__(persist_cookies_per_session=False)

    async def crawl(self, *args: Any, **kwargs: Any) -> Any:
        raise UnsupportedError("RelCrawler fetches pages through REL navigation")

    async def send_request(self, *args: Any, **kwargs: Any) -> Any:
        raise UnsupportedError(
            "send_request is unavailable; use context.page.goto() through REL"
        )

    def stream(self, *args: Any, **kwargs: Any) -> Any:
        raise UnsupportedError("HTTP streaming is unavailable through REL")

    async def cleanup(self) -> None:
        pass
