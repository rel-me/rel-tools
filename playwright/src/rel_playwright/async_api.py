"""Asynchronous Playwright-shaped API backed by REL."""

from __future__ import annotations

import asyncio
from types import TracebackType
from typing import Any, Literal

from . import _core
from ._core import Error, RelRpcError, TimeoutError, UnsupportedError


class Response:
    def __init__(self, impl: _core.Response) -> None:
        self._impl = impl

    @property
    def url(self) -> str:
        return self._impl.url

    @property
    def status(self) -> int:
        return self._impl.status

    @property
    def ok(self) -> bool:
        return self._impl.ok

    @property
    def status_text(self) -> str:
        return self._impl.status_text


class Locator:
    def __init__(self, impl: _core.Locator) -> None:
        self._impl = impl

    @property
    def page(self) -> Page:
        return Page(self._impl.page)

    @property
    def first(self) -> Locator:
        return Locator(self._impl.first)

    @property
    def last(self) -> Locator:
        return Locator(self._impl.last)

    def nth(self, index: int) -> Locator:
        return Locator(self._impl.nth(index))

    def locator(self, selector: str) -> Locator:
        return Locator(self._impl.locator(selector))

    async def count(self) -> int:
        return await asyncio.to_thread(self._impl.count)

    async def all(self) -> list[Locator]:
        return [Locator(locator) for locator in await asyncio.to_thread(self._impl.all)]

    async def all_text_contents(self) -> list[str]:
        return await asyncio.to_thread(self._impl.all_text_contents)

    async def all_inner_texts(self) -> list[str]:
        return await asyncio.to_thread(self._impl.all_inner_texts)

    async def text_content(self, **kwargs: Any) -> str | None:
        return await asyncio.to_thread(self._impl.text_content, **kwargs)

    async def inner_text(self, **kwargs: Any) -> str:
        return await asyncio.to_thread(self._impl.inner_text, **kwargs)

    async def inner_html(self, **kwargs: Any) -> str:
        return await asyncio.to_thread(self._impl.inner_html, **kwargs)

    async def get_attribute(self, name: str, **kwargs: Any) -> str | None:
        return await asyncio.to_thread(self._impl.get_attribute, name, **kwargs)

    async def input_value(self, **kwargs: Any) -> str:
        return await asyncio.to_thread(self._impl.input_value, **kwargs)

    async def click(self, **kwargs: Any) -> None:
        await asyncio.to_thread(self._impl.click, **kwargs)

    async def fill(self, value: str, **kwargs: Any) -> None:
        await asyncio.to_thread(self._impl.fill, value, **kwargs)

    async def type(self, text: str, **kwargs: Any) -> None:
        await asyncio.to_thread(self._impl.type, text, **kwargs)

    async def press(self, key: str, **kwargs: Any) -> None:
        await asyncio.to_thread(self._impl.press, key, **kwargs)

    async def select_option(self, value: str | None = None, **kwargs: Any) -> list[str]:
        return await asyncio.to_thread(self._impl.select_option, value, **kwargs)

    async def wait_for(self, **kwargs: Any) -> None:
        await asyncio.to_thread(self._impl.wait_for, **kwargs)

    async def evaluate(self, *args: Any, **kwargs: Any) -> Any:
        return await asyncio.to_thread(self._impl.evaluate, *args, **kwargs)

    async def evaluate_all(self, *args: Any, **kwargs: Any) -> Any:
        return await asyncio.to_thread(self._impl.evaluate_all, *args, **kwargs)


class Page:
    def __init__(self, impl: _core.Page) -> None:
        self._impl = impl

    @property
    def context(self) -> BrowserContext:
        return BrowserContext(self._impl.context)

    @property
    def url(self) -> str:
        return self._impl.url

    @property
    def session_id(self) -> str:
        return self._impl.session_id

    def is_closed(self) -> bool:
        return self._impl.is_closed()

    def locator(self, selector: str, **kwargs: Any) -> Locator:
        return Locator(self._impl.locator(selector, **kwargs))

    async def set_default_timeout(self, timeout: float) -> None:
        await asyncio.to_thread(self._impl.set_default_timeout, timeout)

    async def set_default_navigation_timeout(self, timeout: float) -> None:
        await asyncio.to_thread(self._impl.set_default_navigation_timeout, timeout)

    async def goto(self, url: str, **kwargs: Any) -> Response:
        return Response(await asyncio.to_thread(self._impl.goto, url, **kwargs))

    async def content(self) -> str:
        return await asyncio.to_thread(self._impl.content)

    async def title(self) -> str:
        return await asyncio.to_thread(self._impl.title)

    async def click(self, selector: str, **kwargs: Any) -> None:
        await asyncio.to_thread(self._impl.click, selector, **kwargs)

    async def fill(self, selector: str, value: str, **kwargs: Any) -> None:
        await asyncio.to_thread(self._impl.fill, selector, value, **kwargs)

    async def type(self, selector: str, text: str, **kwargs: Any) -> None:
        await asyncio.to_thread(self._impl.type, selector, text, **kwargs)

    async def press(self, selector: str, key: str, **kwargs: Any) -> None:
        await asyncio.to_thread(self._impl.press, selector, key, **kwargs)

    async def select_option(
        self, selector: str, value: str | None = None, **kwargs: Any
    ) -> list[str]:
        return await asyncio.to_thread(
            self._impl.select_option, selector, value, **kwargs
        )

    async def wait_for_selector(self, selector: str, **kwargs: Any) -> Locator:
        return Locator(
            await asyncio.to_thread(self._impl.wait_for_selector, selector, **kwargs)
        )

    async def wait_for_timeout(self, timeout: float) -> None:
        await asyncio.to_thread(self._impl.wait_for_timeout, timeout)

    async def wait_for_load_state(
        self,
        state: Literal["load", "domcontentloaded", "commit"] = "load",
        **kwargs: Any,
    ) -> None:
        await asyncio.to_thread(self._impl.wait_for_load_state, state, **kwargs)

    async def screenshot(self, **kwargs: Any) -> bytes:
        return await asyncio.to_thread(self._impl.screenshot, **kwargs)

    async def go_back(self, **kwargs: Any) -> Response | None:
        response = await asyncio.to_thread(self._impl.go_back, **kwargs)
        return None if response is None else Response(response)

    async def go_forward(self, **kwargs: Any) -> Response | None:
        response = await asyncio.to_thread(self._impl.go_forward, **kwargs)
        return None if response is None else Response(response)

    async def reload(self, **kwargs: Any) -> Response:
        return Response(await asyncio.to_thread(self._impl.reload, **kwargs))

    async def close(self, **kwargs: Any) -> None:
        await asyncio.to_thread(self._impl.close, **kwargs)

    async def evaluate(self, *args: Any, **kwargs: Any) -> Any:
        return await asyncio.to_thread(self._impl.evaluate, *args, **kwargs)


class BrowserContext:
    def __init__(self, impl: _core.BrowserContext) -> None:
        self._impl = impl

    @property
    def browser(self) -> Browser:
        return Browser(self._impl.browser)

    @property
    def pages(self) -> list[Page]:
        return [Page(page) for page in self._impl.pages]

    async def new_page(self) -> Page:
        return Page(await asyncio.to_thread(self._impl.new_page))

    async def set_default_timeout(self, timeout: float) -> None:
        await asyncio.to_thread(self._impl.set_default_timeout, timeout)

    async def set_default_navigation_timeout(self, timeout: float) -> None:
        await asyncio.to_thread(self._impl.set_default_navigation_timeout, timeout)

    async def close(self, **kwargs: Any) -> None:
        await asyncio.to_thread(self._impl.close, **kwargs)


class Browser:
    def __init__(self, impl: _core.Browser) -> None:
        self._impl = impl

    @property
    def contexts(self) -> list[BrowserContext]:
        return [BrowserContext(context) for context in self._impl.contexts]

    def is_connected(self) -> bool:
        return self._impl.is_connected()

    async def new_context(self, **kwargs: Any) -> BrowserContext:
        return BrowserContext(await asyncio.to_thread(self._impl.new_context, **kwargs))

    async def new_page(self, **kwargs: Any) -> Page:
        return Page(await asyncio.to_thread(self._impl.new_page, **kwargs))

    async def close(self, **kwargs: Any) -> None:
        await asyncio.to_thread(self._impl.close, **kwargs)


class BrowserType:
    def __init__(self, impl: _core.BrowserType) -> None:
        self._impl = impl
        self.name = impl.name

    async def launch(self, **kwargs: Any) -> Browser:
        return Browser(await asyncio.to_thread(self._impl.launch, **kwargs))

    async def connect(self, *args: Any, **kwargs: Any) -> Browser:
        return Browser(await asyncio.to_thread(self._impl.connect, *args, **kwargs))

    async def connect_over_cdp(self, *args: Any, **kwargs: Any) -> Browser:
        return Browser(
            await asyncio.to_thread(self._impl.connect_over_cdp, *args, **kwargs)
        )


class Playwright:
    def __init__(self, impl: _core.Playwright | None = None) -> None:
        self._impl = impl or _core.Playwright()
        self.chromium = BrowserType(self._impl.chromium)
        self.firefox = BrowserType(self._impl.firefox)
        self.webkit = BrowserType(self._impl.webkit)

    async def stop(self) -> None:
        await asyncio.to_thread(self._impl.stop)


class PlaywrightContextManager:
    def __init__(self) -> None:
        self._playwright: Playwright | None = None

    async def __aenter__(self) -> Playwright:
        return await self.start()

    async def __aexit__(
        self,
        _type: type[BaseException] | None,
        _value: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        if self._playwright is not None:
            await self._playwright.stop()

    async def start(self) -> Playwright:
        if self._playwright is None:
            self._playwright = Playwright()
        return self._playwright


def async_playwright() -> PlaywrightContextManager:
    """Return an async context manager matching Playwright's entry point."""

    return PlaywrightContextManager()


__all__ = [
    "Browser",
    "BrowserContext",
    "BrowserType",
    "Error",
    "Locator",
    "Page",
    "Playwright",
    "RelRpcError",
    "Response",
    "TimeoutError",
    "UnsupportedError",
    "async_playwright",
]
