"""Public crawler exception hierarchy."""


class CrawlError(Exception):
    """Base class for crawler failures."""


class CrawlConfigurationError(CrawlError):
    """The definition or checkpoint is not safe to execute."""


class CrawlAlreadyRunningError(CrawlError):
    """Another process owns this checkpoint's crawl lock."""


class CrawlRecoveryError(CrawlError):
    """REL could not restore the source page after a bounded link attempt."""


class CrawlPageError(CrawlError):
    """A captured target page had an unsuccessful HTTP status."""
