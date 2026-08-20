"""Command-line entry point for reusable REL crawler applications."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import logging
import sys
from collections.abc import Sequence
from contextlib import redirect_stdout
from dataclasses import asdict
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from types import ModuleType
from typing import Any

from .application import CrawlApplication
from .errors import CrawlError

_LOGGER = logging.getLogger("rel_crawler.cli")


class CrawlerCliError(CrawlError):
    """A CLI application specification could not be loaded."""


def _package_version() -> str:
    try:
        return version("rel-crawler")
    except PackageNotFoundError:
        return "unknown"


def load_application(specification: str) -> CrawlApplication:
    """Load ``module:attribute`` or ``path.py:attribute`` (default: ``app``)."""

    source, separator, attribute = specification.rpartition(":")
    if not separator:
        source, attribute = specification, "app"
    if not source or not attribute:
        raise CrawlerCliError(
            "application must be MODULE[:ATTRIBUTE] or PATH.py[:ATTRIBUTE]"
        )

    path = Path(source).expanduser()
    if path.suffix == ".py" and not path.is_file():
        raise CrawlerCliError(f"crawler application file does not exist: {path}")
    module = _load_path(path) if path.is_file() else _load_module(source)
    try:
        value = getattr(module, attribute)
    except AttributeError as error:
        raise CrawlerCliError(
            f"crawler application {specification!r} has no {attribute!r} attribute"
        ) from error
    if not isinstance(value, CrawlApplication):
        raise CrawlerCliError(
            f"{specification!r} resolved to {type(value).__name__}, "
            "not CrawlApplication"
        )
    return value


def _load_path(path: Path) -> ModuleType:
    resolved = path.resolve()
    module_name = (
        "_rel_crawler_config_"
        + hashlib.sha256(str(resolved).encode("utf-8")).hexdigest()[:16]
    )
    spec = importlib.util.spec_from_file_location(module_name, resolved)
    if spec is None or spec.loader is None:
        raise CrawlerCliError(f"could not load crawler application file {resolved}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as error:
        sys.modules.pop(module_name, None)
        raise CrawlerCliError(
            f"could not execute crawler application file {resolved}: "
            f"{type(error).__name__}: {error}"
        ) from error
    return module


def _load_module(name: str) -> ModuleType:
    try:
        return importlib.import_module(name)
    except Exception as error:
        raise CrawlerCliError(
            f"could not import crawler application {name!r}: "
            f"{type(error).__name__}: {error}"
        ) from error


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rel-crawler",
        description="Run restartable browser crawls through REL.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_package_version()}",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser(
        "run",
        help="run a CrawlApplication from a Python module or file",
    )
    run.add_argument(
        "application",
        help="MODULE[:ATTRIBUTE] or PATH.py[:ATTRIBUTE]; attribute defaults to app",
    )
    run.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
    )
    run.add_argument("--state-path")
    run.add_argument("--capture-dir")
    run.add_argument("--rel-base-url")
    run.add_argument("--session-id")
    run.add_argument("--profile", help="REL profile name")
    run.add_argument("--group")
    run.add_argument("--timeout", type=float)
    run.add_argument("--wait", type=float)
    run.add_argument("--action-delay", type=float)
    run.add_argument(
        "--max-attempts",
        type=int,
        help="maximum attempts for the initial source load and each link",
    )
    run.add_argument("--max-session-restarts", type=int)
    run.add_argument("--max-links", type=int)
    run.add_argument(
        "--skip-existing",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    run.add_argument(
        "--retry-failed",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    run.add_argument(
        "--accept-http-errors",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    run.add_argument(
        "--close-owned-session-on-finish",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    return parser


def _run_overrides(arguments: argparse.Namespace) -> dict[str, Any]:
    names = (
        "state_path",
        "capture_dir",
        "rel_base_url",
        "session_id",
        "profile",
        "group",
        "timeout",
        "wait",
        "action_delay",
        "max_attempts",
        "max_session_restarts",
        "max_links",
        "skip_existing",
        "retry_failed",
        "accept_http_errors",
        "close_owned_session_on_finish",
    )
    return {
        name: getattr(arguments, name)
        for name in names
        if getattr(arguments, name) is not None
    }


def _summary_payload(summary: Any) -> dict[str, Any]:
    payload = asdict(summary)
    payload["state_path"] = str(payload["state_path"])
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, arguments.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    try:
        # The CLI owns stdout for its machine-readable summary. User callbacks
        # and configuration modules retain visible output on stderr.
        with redirect_stdout(sys.stderr):
            application = load_application(arguments.application)
            summary = application.run(**_run_overrides(arguments))
    except (CrawlerCliError, CrawlError, OSError, ValueError, TypeError) as error:
        _LOGGER.error("%s: %s", type(error).__name__, error)
        return 1
    print(json.dumps(_summary_payload(summary), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
