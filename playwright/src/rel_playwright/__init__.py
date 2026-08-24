"""Playwright-shaped Python scraping backed by REL RPC v1."""

from ._core import Error, RelRpcError, TimeoutError, UnsupportedError

__all__ = ["Error", "RelRpcError", "TimeoutError", "UnsupportedError"]
