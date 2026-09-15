"""Explicit, local-only verification against an already staged RELDebug runtime.

Run from rel-tools with --rel-cli, --rel-base-url, and --expected-build-id.
This creates and removes only resources in a unique fixture group.
"""

from __future__ import annotations

import argparse
import asyncio
import html
import json
import os
import tempfile
import threading
import uuid
from collections import Counter
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request as HttpRequest
from urllib.request import urlopen

from crawlee.configuration import Configuration
from crawlee.events import LocalEventManager
from crawlee.storage_clients import FileSystemStorageClient
from crawlee.storages import RequestQueue
from rel_crawlee import RelCrawler

from crawlee import ConcurrencySettings


class FixtureHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_CONNECT(self):
        self.send_error(502, "Fixture proxy does not connect to external hosts")

    def do_GET(self):
        parsed = urlsplit(self.path)
        if parsed.hostname and parsed.hostname != "rel-crawlee.invalid":
            self.send_error(404)
            return
        path = parsed.path
        self.server.hits[path] += 1
        if parsed.hostname:
            self.server.proxy_hits.append(path)
        if path == "/start":
            self.send_response(302)
            self.send_header("Location", "/catalog/index")
            self.end_headers()
            return
        if path == "/catalog/index":
            body = """<base href="../items/"><a href="one">One</a>
                <a href="one#duplicate">Duplicate</a><a href="two">Two</a>"""
        else:
            body = (
                '<p id="cookie">' + html.escape(self.headers.get("Cookie", "")) + "</p>"
            )
            body += """<input id="name"><button id="submit" onclick="document.querySelector('#result').textContent=document.querySelector('#name').value">Submit</button><p id="result"></p>"""
        body += '<script>document.cookie="fixture=visited; path=/";</script>'
        encoded = (
            "<html><head><title>REL Crawlee Fixture</title></head><body>"
            + body
            + "</body></html>"
        ).encode()
        status = 503 if path == "/flaky" and self.server.hits[path] == 1 else 200
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


async def verify(args):
    parsed = urlsplit(args.rel_base_url)
    if (
        parsed.hostname != "127.0.0.1"
        or parsed.scheme != "http"
        or parsed.path != "/v1"
    ):
        raise ValueError(
            "Use the explicit worktree HTTP endpoint at 127.0.0.1:<port>/v1"
        )
    cli_path = Path(args.rel_cli).resolve()
    if "RELDebug.app" not in cli_path.parts:
        raise ValueError("--rel-cli must be the worktree's bundled RELDebug.app CLI")
    env = {**os.environ, "REL_AGENT_PORT": str(parsed.port)}

    async def cli(*command):
        proc = await asyncio.create_subprocess_exec(
            str(cli_path),
            *command,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode:
            raise RuntimeError(stderr.decode())
        result = json.loads(stdout)
        assert result["status"] == "ok", result
        return result["data"]

    health = await cli("health")
    assert health["build"]["configuration"] == "Debug", health
    assert health["build"]["id"] == args.expected_build_id, health

    def rpc(method, path, payload=None):
        data = None if payload is None else json.dumps(payload).encode()
        request = HttpRequest(
            args.rel_base_url + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=30) as response:
            result = json.load(response)
        assert result["status"] == "ok", result
        return result["data"]

    group = "crawlee-test-" + uuid.uuid4().hex[:12]
    server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
    server.hits = Counter()
    server.proxy_hits = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = "http://rel-crawlee.invalid"
    alias = group
    profile = None
    proxy_created = False
    with tempfile.TemporaryDirectory(prefix="rel-crawlee-verify-") as temp:

        def crawler(name, **kwargs):
            if "session_id" not in kwargs:
                kwargs.setdefault("profile", group)
            return RelCrawler(
                rel_base_url=args.rel_base_url,
                group=group,
                configuration=Configuration(
                    storage_dir=str(Path(temp) / name), purge_on_start=False
                ),
                storage_client=FileSystemStorageClient(),
                event_manager=LocalEventManager(),
                configure_logging=False,
                **kwargs,
            )

        try:
            # A saved Profile directs Chromium to a local proxy fixture. It never
            # connects externally; only requests for rel-crawlee.invalid are served.
            await cli(
                "proxy",
                "create",
                "--alias",
                alias,
                "--upstream-host",
                "127.0.0.1",
                "--upstream-port",
                str(server.server_port),
            )
            proxy_created = True
            profile = await asyncio.to_thread(
                rpc,
                "POST",
                "/profiles",
                {"name": group, "proxy_alias": alias, "adblock_enabled": False},
            )
            crawl = crawler(
                "links",
                profile=group,
                concurrency_settings=ConcurrencySettings(
                    min_concurrency=2, max_concurrency=2, desired_concurrency=2
                ),
            )
            sessions = set()

            @crawl.router.default_handler
            async def handler(ctx):
                sessions.add(ctx.page.session_id)
                if ctx.page.url.endswith("/catalog/index"):
                    await ctx.enqueue_links(label="item")
                else:
                    await ctx.push_data(
                        {
                            "url": ctx.page.url,
                            "cookie": await ctx.page.locator("#cookie").inner_text(),
                        }
                    )

            @crawl.router.handler("item")
            async def item(ctx):
                await handler(ctx)
                await ctx.page.locator("#name").fill("Crawlee")
                await ctx.page.locator("#submit").click()
                assert await ctx.page.locator("#result").inner_text() == "Crawlee"

            stats = await crawl.run(["http://rel-crawlee.invalid/start"])
            assert stats.requests_finished == 3 and stats.requests_failed == 0, stats
            rows = (await crawl.get_data()).items
            assert len(rows) == 2 and all(row["cookie"] == "" for row in rows), rows
            assert len(sessions) == 3, sessions
            assert {"/start", "/catalog/index", "/items/one", "/items/two"} <= set(
                server.proxy_hits
            )
            remaining = await cli("session", "list")
            assert not any(s["id"] in sessions for s in remaining["sessions"]), (
                remaining
            )
            print(
                "PASS: redirect/base links, deduplication, native actions, dataset, isolated sessions, Profile proxy, cleanup"
            )

            borrowed = (
                await cli("session", "create", "--group", group, "--profile", group)
            )["session"]["id"]
            reuse = crawler("borrowed", session_id=borrowed)
            cookies = []

            @reuse.router.default_handler
            async def reuse_handler(ctx):
                cookies.append(await ctx.page.locator("#cookie").inner_text())

            stats = await reuse.run(
                [origin + "/borrowed-one", origin + "/borrowed-two"]
            )
            assert stats.requests_finished == 2, stats
            assert cookies == ["", "fixture=visited"], cookies
            assert (await cli("session", "get", borrowed))["session"]["id"] == borrowed
            print(
                "PASS: borrowed session preserves cookies and remains owned by caller"
            )

            retry = crawler("retry", max_request_retries=1)

            @retry.router.default_handler
            async def retry_handler(ctx):
                await ctx.push_data({"status": ctx.response.status})

            stats = await retry.run([origin + "/flaky"])
            assert stats.requests_finished == 1 and server.hits["/flaky"] == 2, stats
            print("PASS: HTTP 503 retries through Crawlee")

            cancelled = crawler(
                "cancel",
                max_request_retries=0,
                request_handler_timeout=timedelta(milliseconds=100),
            )
            cancelled_sessions = []

            @cancelled.router.default_handler
            async def slow(ctx):
                cancelled_sessions.append(ctx.page.session_id)
                await asyncio.sleep(10)

            stats = await cancelled.run([origin + "/cancel"])
            assert stats.requests_failed == 1, stats
            remaining = await cli("session", "list")
            assert not any(s["id"] in cancelled_sessions for s in remaining["sessions"])
            print("PASS: handler cancellation cleans up its session")

            config = Configuration(
                storage_dir=str(Path(temp) / "resume"), purge_on_start=False
            )
            queue = await RequestQueue.open(
                name="resume",
                configuration=config,
                storage_client=FileSystemStorageClient(),
            )
            await queue.add_requests([origin + "/resume-one", origin + "/resume-two"])
            first = crawler(
                "resume",
                request_manager=queue,
                max_requests_per_crawl=1,
                request_handler=retry_handler,
            )
            await first.run()
            second = crawler(
                "resume", request_manager=queue, request_handler=retry_handler
            )
            await second.run()
            assert server.hits["/resume-one"] == server.hits["/resume-two"] == 1
            print("PASS: named request queue resumes pending URLs")
            print("Verified REL build:", health["build"]["id"])
        finally:
            # Unique group/alias/profile only. Never touch unrelated sessions.
            try:
                await cli("session", "close", "--group", group)
            finally:
                try:
                    if profile:
                        await asyncio.to_thread(
                            rpc, "DELETE", "/profiles/" + profile["profile"]["id"]
                        )
                finally:
                    if proxy_created:
                        await cli("proxy", "delete", alias)
                    server.shutdown()
                    server.server_close()
                    thread.join()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rel-cli", required=True)
    parser.add_argument("--rel-base-url", required=True)
    parser.add_argument("--expected-build-id", required=True)
    asyncio.run(verify(parser.parse_args()))
