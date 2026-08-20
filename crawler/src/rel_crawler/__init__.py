"""Public API for the REL history-preserving crawler."""

from .api import (
    LinkObservation,
    NavigationOperation,
    PageOperation,
    RelClient,
    RelError,
    RelProtocolError,
    RelRpcError,
    RelTransportError,
    RenderedLink,
)
from .application import CrawlApplication
from .crawler import RelCrawler
from .errors import (
    CrawlAlreadyRunningError,
    CrawlConfigurationError,
    CrawlError,
    CrawlPageError,
    CrawlRecoveryError,
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
from .protocols import CrawlerClient

__all__ = [
    "CapturedPage",
    "CrawlAlreadyRunningError",
    "CrawlApplication",
    "CrawlConfigurationError",
    "CrawlDefinition",
    "CrawlError",
    "CrawlFailure",
    "CrawlItem",
    "CrawlPageError",
    "CrawlRecoveryError",
    "CrawlSummary",
    "CrawlerClient",
    "Link",
    "LinkObservation",
    "NavigationOperation",
    "PageOperation",
    "RelClient",
    "RelCrawler",
    "RelError",
    "RelProtocolError",
    "RelRpcError",
    "RelTransportError",
    "RenderedLink",
    "SourcePage",
    "canonicalize_url",
    "extract_links",
    "extract_page_metadata",
]
