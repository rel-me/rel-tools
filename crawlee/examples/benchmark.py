"""Compare fresh and pooled sessions on ten Books to Scrape pages per run.

Each run uses a separate process/storage directory. Paired rounds alternate order
so the first mode does not always pay for a cold browser/network path. This is a
small end-to-end proxy/site benchmark, not a controlled browser microbenchmark.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import subprocess
import sys
import time
import uuid
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen

from crawlee.configuration import Configuration
from crawlee.events import LocalEventManager
from crawlee.storage_clients import FileSystemStorageClient
from rel_crawlee import RelCrawler

from crawlee import ConcurrencySettings


async def crawl(args) -> None:
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)

    def rpc_get(path):
        with urlopen(args.rel_base_url.rstrip("/") + path, timeout=10) as response:
            envelope = json.load(response)
        if envelope["status"] != "ok":
            raise RuntimeError(envelope)
        return envelope["data"]

    profiles = (await asyncio.to_thread(rpc_get, "/profiles"))["profiles"]
    profile = next((p for p in profiles if p["name"] == args.profile), None)
    if profile is None:
        raise ValueError(f"Saved REL Profile not found: {args.profile}")
    group = "crawlee-benchmark-" + uuid.uuid4().hex[:12]
    crawler = RelCrawler(
        profile=args.profile,
        rel_base_url=args.rel_base_url,
        group=group,
        session_pool_size=2 if args.mode == "pooled" else None,
        max_requests_per_crawl=10,
        max_request_retries=1,
        navigation_timeout=timedelta(seconds=45),
        concurrency_settings=ConcurrencySettings(
            desired_concurrency=2, max_concurrency=2
        ),
        configuration=Configuration(storage_dir=str(output / "storage")),
        storage_client=FileSystemStorageClient(),
        event_manager=LocalEventManager(),
    )
    pages, failures = [], []

    @crawler.router.default_handler
    async def handler(ctx):
        session = (
            await asyncio.to_thread(rpc_get, "/sessions/" + ctx.page.session_id)
        )["session"]
        if session.get("profile") != args.profile or session.get(
            "proxy_alias"
        ) != profile.get("proxy_alias"):
            raise RuntimeError("Session did not inherit the selected Profile and proxy")
        item = {
            "url": ctx.page.url,
            "status": ctx.response.status,
            "title": await ctx.page.title(),
            "session_id": ctx.page.session_id,
            "profile": session["profile"],
            "proxy_alias": session.get("proxy_alias"),
        }
        if ctx.request.label == "book":
            item["name"] = await ctx.page.locator("h1").inner_text()
            item["price"] = await ctx.page.locator(
                ".product_main .price_color"
            ).inner_text()
        else:
            await ctx.enqueue_links(selector="h3 a", label="book", limit=9)
        await ctx.push_data(item)
        pages.append(item)

    @crawler.failed_request_handler
    async def failed(ctx, error):
        failures.append(
            {
                "url": ctx.request.url,
                "error_type": type(error).__name__,
                "error": str(error),
                "retries": ctx.request.retry_count,
            }
        )

    start = time.perf_counter()
    stats = await crawler.run(["https://books.toscrape.com/"])
    elapsed = time.perf_counter() - start
    remaining = (await asyncio.to_thread(rpc_get, "/sessions"))["sessions"]
    leftover = [s["id"] for s in remaining if s.get("group") == group]
    report = {
        "mode": args.mode,
        "profile": args.profile,
        "elapsed_seconds": elapsed,
        "statistics": stats.to_dict(),
        "metrics": asdict(crawler.metrics),
        "pages": pages,
        "failures": failures,
        "remaining_sessions": leftover,
    }
    (output / "report.json").write_text(json.dumps(report, indent=2, default=str))
    if stats.requests_finished != 10 or stats.requests_failed or leftover:
        raise RuntimeError(
            f"Benchmark failed or left sessions behind; see {output / 'report.json'}"
        )


def compare(args) -> None:
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    reports = []
    for pair in range(args.pairs):
        order = ("fresh", "pooled") if pair % 2 == 0 else ("pooled", "fresh")
        for mode in order:
            run_dir = output / f"{pair + 1}-{mode}"
            command = [
                sys.executable,
                str(Path(__file__).resolve()),
                "--mode",
                mode,
                "--rel-base-url",
                args.rel_base_url,
                "--profile",
                args.profile,
                "--output",
                str(run_dir),
            ]
            with (output / f"{pair + 1}-{mode}.log").open("w") as log:
                subprocess.run(
                    command, stdout=log, stderr=subprocess.STDOUT, check=True
                )
            report = json.loads((run_dir / "report.json").read_text())
            reports.append(report)
            print(
                f"{pair + 1} {mode}: {report['elapsed_seconds']:.2f}s, "
                f"{report['metrics']['sessions_created']} sessions, "
                f"{report['metrics']['session_reuses']} reuses",
                flush=True,
            )
    records = [
        {(p["url"], p.get("name"), p.get("price")) for p in report["pages"]}
        for report in reports
    ]
    if any(value != records[0] for value in records[1:]):
        raise RuntimeError(
            "Modes extracted different records; inspect individual reports"
        )
    means = {
        mode: statistics.mean(
            r["elapsed_seconds"] for r in reports if r["mode"] == mode
        )
        for mode in ("fresh", "pooled")
    }
    summary = {
        "profile": args.profile,
        "pairs": args.pairs,
        "mean_elapsed_seconds": means,
        "pooled_time_reduction_percent": 100 * (1 - means["pooled"] / means["fresh"]),
        "identical_records": True,
        "runs": reports,
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps({k: v for k, v in summary.items() if k != "runs"}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rel-base-url", required=True, help="Explicit local RPC v1 root"
    )
    parser.add_argument("--profile", required=True)
    parser.add_argument("--output", required=True, help="A new results directory")
    parser.add_argument("--pairs", type=int, default=2)
    parser.add_argument("--mode", choices=("fresh", "pooled"), help=argparse.SUPPRESS)
    args = parser.parse_args()
    endpoint = urlsplit(args.rel_base_url)
    if (
        endpoint.scheme != "http"
        or endpoint.hostname not in {"127.0.0.1", "localhost", "::1"}
        or endpoint.path.rstrip("/") != "/v1"
        or endpoint.username is not None
        or endpoint.password is not None
        or endpoint.query
        or endpoint.fragment
    ):
        parser.error(
            "--rel-base-url must be an HTTP loopback RPC v1 root without credentials"
        )
    if args.pairs < 1:
        parser.error("--pairs must be positive")
    if args.mode:
        asyncio.run(crawl(args))
    else:
        compare(args)
