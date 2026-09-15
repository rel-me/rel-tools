"""Bounded, per-run metrics. Durations are summed monotonic seconds."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RelCrawlMetrics:
    """Snapshot of the current/latest run; concurrent durations can overlap.

    Handler time includes link extraction. Cleanup includes pool shutdown.
    No URLs, credentials, or per-request histories are retained in this summary.
    """

    requests_started: int = 0
    sessions_created: int = 0
    session_reuses: int = 0
    sessions_retired: int = 0
    session_wait_seconds: float = 0.0
    session_acquire_seconds: float = 0.0
    navigation_seconds: float = 0.0
    handler_seconds: float = 0.0
    link_extraction_seconds: float = 0.0
    cleanup_seconds: float = 0.0
