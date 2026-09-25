"""Synchronous Playwright-shaped API backed by REL."""

from __future__ import annotations

from types import TracebackType

from ._core import (
    Browser,
    BrowserContext,
    BrowserType,
    Error,
    Locator,
    Page,
    Playwright,
    RelRpcError,
    Response,
    TimeoutError,
    UnsupportedError,
)


class PlaywrightContextManager:
    def __init__(self) -> None:
        self._playwright: Playwright | None = None

    def __enter__(self) -> Playwright:
        return self.start()

    def __exit__(
        self,
        _type: type[BaseException] | None,
        _value: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        if self._playwright is not None:
            self._playwright.stop()

    def start(self) -> Playwright:
        if self._playwright is None:
            self._playwright = Playwright()
        return self._playwright


def sync_playwright() -> PlaywrightContextManager:
    """Return a context manager matching Playwright's synchronous entry point."""

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
    "sync_playwright",
]
