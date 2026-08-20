"""Public API for the REL history-preserving crawler."""

from .api import (
    NavigationOperation,
    PageOperation,
    RelClient,
    RelError,
    RelProtocolError,
    RelRpcError,
    RelTransportError,
)
from .crawler import (
    CrawlAlreadyRunningError,
    CrawlConfigurationError,
    CrawlError,
    CrawlPageError,
    CrawlRecoveryError,
    RelCrawler,
)
from .html import canonicalize_url, extract_links, extract_page_metadata
from .models import (
    CapturedPage,
    CrawlDefinition,
    CrawlFailure,
    CrawlItem,
    CrawlSummary,
    Link,
    SourcePage,
)

__all__ = [
    "CapturedPage",
    "CrawlAlreadyRunningError",
    "CrawlConfigurationError",
    "CrawlDefinition",
    "CrawlError",
    "CrawlFailure",
    "CrawlItem",
    "CrawlPageError",
    "CrawlRecoveryError",
    "CrawlSummary",
    "Link",
    "NavigationOperation",
    "PageOperation",
    "RelClient",
    "RelCrawler",
    "RelError",
    "RelProtocolError",
    "RelRpcError",
    "RelTransportError",
    "SourcePage",
    "canonicalize_url",
    "extract_links",
    "extract_page_metadata",
]
