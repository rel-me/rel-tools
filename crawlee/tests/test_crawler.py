from __future__ import annotations

import asyncio
import json
import re
import tempfile
import threading
import unittest
from collections import Counter
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from crawlee._service_locator import ServiceLocator
from crawlee.configuration import Configuration
from crawlee.events import LocalEventManager
from crawlee.storage_clients import FileSystemStorageClient, MemoryStorageClient
from crawlee.storages import RequestQueue
from rel_crawlee import RelCrawler
from rel_playwright.async_api import UnsupportedError, async_playwright

from crawlee import ConcurrencySettings, Request


class FakeAgent(ThreadingHTTPServer):
    def __init__(self):
        super().__init__(("127.0.0.1", 0), AgentHandler)
        self.sessions = {"Session99": "https://example.test/"}
        self.created = []
        self.deleted = []
        self.delete_failures = 0
        self.navigations = []
        self.calls = []
        self.html = {}
        self.failures = {}
        self.redirects = {}
        self.sequence = 0
        self.statuses = {}
        self.capture_started = threading.Event()
        self.capture_release = threading.Event()
        self.block_capture = False
        self.deleted_during_capture = False
        self.capturing = False


class AgentHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.handle_rpc()

    def do_POST(self):
        self.handle_rpc()

    def do_DELETE(self):
        self.handle_rpc()

    def handle_rpc(self):
        agent = self.server
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        data = json.loads(raw) if raw else {}
        agent.calls.append((self.command, self.path, data))
        if self.path == "/v1/health":
            result = {"overall_status": "ok"}
        elif self.path == "/v1/sessions":
            agent.sequence += 1
            session = f"Session{agent.sequence}"
            agent.sessions[session] = "about:blank"
            agent.created.append((session, data))
            result = {"session": {"id": session}}
        elif self.path.startswith("/v1/sessions/"):
            session = self.path.rsplit("/", 1)[1]
            if self.command == "DELETE":
                if agent.delete_failures:
                    agent.delete_failures -= 1
                    self.reply(
                        {
                            "status": "error",
                            "error": {
                                "id": "UPSTREAM_UNAVAILABLE",
                                "code": 10302,
                                "message": "cleanup fixture failure",
                                "retryable": True,
                            },
                        },
                        502,
                    )
                    return
                agent.deleted_during_capture |= agent.capturing
                agent.sessions.pop(session, None)
                agent.deleted.append(session)
                result = {"deleted_id": session}
            else:
                result = {"session": {"id": session}}
        elif self.path in ("/v1/navigate", "/v1/capture", "/v1/perform"):
            session = data["session_id"]
            if self.path == "/v1/navigate":
                url = data["url"]
                agent.navigations.append((session, url))
                failures = agent.failures.get(url, [])
                if failures:
                    error_id, retryable = failures.pop(0)
                    self.reply(
                        {
                            "status": "error",
                            "error": {
                                "id": error_id,
                                "code": 10302,
                                "message": "fixture failure",
                                "retryable": retryable,
                            },
                        },
                        502,
                    )
                    return
                agent.sessions[session] = agent.redirects.get(url, url)
            if self.path == "/v1/capture" and agent.block_capture:
                agent.capturing = True
                agent.capture_started.set()
                agent.capture_release.wait(5)
                agent.capturing = False
            url = agent.sessions[session]
            output = Path(data["output"])
            output.write_text(
                agent.html.get(
                    url, "<html><title>Fixture</title><body>OK</body></html>"
                )
            )
            result = {
                "page": {"id": f"page_{session}", "session_id": session, "url": url},
                "capture": {
                    "output_path": str(output),
                    "bytesize": output.stat().st_size,
                    "target_http_status": agent.statuses.get(url, 200),
                },
            }
        else:
            raise AssertionError(f"Unexpected RPC {self.path}")
        self.reply({"status": "ok", "data": result})

    def reply(self, body, status=200):
        body["request_id"] = "req_fixture"
        encoded = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


class CrawleeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.storage_patch = patch.object(
            ServiceLocator, "global_storage_instance_manager", None
        )
        self.storage_patch.start()
        self.addCleanup(self.storage_patch.stop)
        self.agent = FakeAgent()
        self.thread = threading.Thread(target=self.agent.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.agent.server_port}/v1"
        self.temp = tempfile.TemporaryDirectory()

    async def asyncTearDown(self):
        self.agent.capture_release.set()
        await asyncio.to_thread(self.agent.shutdown)
        self.agent.server_close()
        self.thread.join()
        self.temp.cleanup()

    def crawler(self, **kwargs):
        return RelCrawler(
            rel_base_url=self.url,
            storage_client=kwargs.pop("storage_client", MemoryStorageClient()),
            configuration=Configuration(
                storage_dir=self.temp.name, purge_on_start=False
            ),
            configure_logging=False,
            event_manager=LocalEventManager(),
            **kwargs,
        )

    async def test_real_crawlee_queue_router_dataset_and_cleanup(self):
        root = "https://example.test/start"
        final = "https://example.test/catalog/index"
        self.agent.redirects[root] = final
        self.agent.html[final] = """<base href="../items/"><a href="one">1</a>
            <a href="one#again">duplicate</a><a href="two">2</a>
            <a href="mailto:x@y.test">mail</a><a href="https://elsewhere.test">offsite</a>"""
        crawler = self.crawler(profile="Research")

        @crawler.router.default_handler
        async def start(ctx):
            self.assertEqual(ctx.request.loaded_url, final)
            self.assertIsNone(ctx.session)
            self.assertIsNone(ctx.proxy_info)
            await ctx.enqueue_links(label="item", user_data={"kind": "product"})

        @crawler.router.handler("item")
        async def item(ctx):
            self.assertEqual(ctx.request.user_data["kind"], "product")
            await ctx.push_data({"url": ctx.page.url, "title": await ctx.page.title()})

        stats = await crawler.run([root])
        self.assertEqual(stats.requests_finished, 3)
        data = await crawler.get_data()
        self.assertEqual(
            {row["url"] for row in data.items},
            {"https://example.test/items/one", "https://example.test/items/two"},
        )
        self.assertEqual(len(self.agent.created), 3)
        self.assertEqual(len(self.agent.deleted), 3)
        self.assertTrue(
            all(options["profile"] == "Research" for _, options in self.agent.created)
        )

    async def test_bounded_retries_and_nonretryable_errors(self):
        retry = "https://example.test/retry"
        fatal = "https://example.test/fatal"
        self.agent.failures[retry] = [("UPSTREAM_UNAVAILABLE", True)]
        self.agent.failures[fatal] = [("INVALID_ARGUMENT", False)] * 3
        crawler = self.crawler(max_request_retries=1)
        failed = []

        @crawler.router.default_handler
        async def handler(ctx):
            await ctx.push_data({"url": ctx.page.url})

        @crawler.failed_request_handler
        async def failure(ctx, error):
            failed.append(ctx.request.url)

        stats = await crawler.run([retry, fatal])
        self.assertEqual(stats.requests_finished, 1)
        self.assertEqual(stats.requests_failed, 1)
        self.assertEqual(
            Counter(url for _, url in self.agent.navigations), {retry: 2, fatal: 1}
        )
        self.assertEqual(failed, [fatal])
        self.assertEqual(len(self.agent.deleted), 3)

    async def test_status_errors_and_unsupported_requests(self):
        self.agent.statuses["https://example.test/missing"] = 404
        self.agent.statuses["https://example.test/server"] = 503
        crawler = self.crawler(max_request_retries=1)
        failures = []

        @crawler.failed_request_handler
        async def failure(ctx, error):
            failures.append(ctx.request.url)

        stats = await crawler.run(
            [
                "https://example.test/missing",
                "https://example.test/server",
                Request.from_url(
                    "https://example.test/post", method="POST", payload="x"
                ),
                Request.from_url(
                    "https://example.test/headers", headers={"X-Test": "x"}
                ),
            ]
        )
        self.assertEqual(stats.requests_failed, 4)
        self.assertEqual(len(failures), 4)
        self.assertEqual(
            Counter(url for _, url in self.agent.navigations),
            {"https://example.test/missing": 1, "https://example.test/server": 2},
        )

    async def test_concurrency_isolates_sessions(self):
        crawler = self.crawler(
            concurrency_settings=ConcurrencySettings(
                min_concurrency=2, desired_concurrency=2, max_concurrency=2
            )
        )
        arrived = asyncio.Event()
        active = set()
        peak = 0

        @crawler.router.default_handler
        async def handler(ctx):
            nonlocal peak
            active.add(ctx.page.session_id)
            peak = max(peak, len(active))
            if len(active) == 2:
                arrived.set()
            await asyncio.wait_for(arrived.wait(), 5)
            self.assertEqual(await ctx.page.title(), "Fixture")
            active.remove(ctx.page.session_id)

        await crawler.run(["https://example.test/one", "https://example.test/two"])
        self.assertEqual(peak, 2)
        self.assertEqual(len(self.agent.deleted), 2)

    async def test_borrowed_session_preserved_and_reusable_run(self):
        crawler = self.crawler(session_id="Session99")
        seen = []

        @crawler.router.default_handler
        async def handler(ctx):
            seen.append(ctx.page.session_id)

        await crawler.run(["https://example.test/one", "https://example.test/two"])
        await crawler.run(["https://example.test/three"])
        self.assertEqual(seen, ["Session99"] * 3)
        self.assertFalse(self.agent.created)
        self.assertFalse(self.agent.deleted)
        self.assertIn("Session99", self.agent.sessions)

    async def test_persistent_owned_sessions_are_retained(self):
        crawler = self.crawler(persist=True)

        @crawler.router.default_handler
        async def handler(ctx):
            pass

        await crawler.run(["https://example.test/"])
        self.assertEqual(len(self.agent.created), 1)
        self.assertFalse(self.agent.deleted)

    async def test_handler_timeout_drains_capture_before_cleanup(self):
        self.agent.block_capture = True
        crawler = self.crawler(
            request_handler_timeout=timedelta(milliseconds=50), max_request_retries=0
        )
        failures = []

        @crawler.router.default_handler
        async def handler(ctx):
            await ctx.page.content()

        @crawler.failed_request_handler
        async def failure(ctx, error):
            failures.append(error)

        task = asyncio.create_task(crawler.run(["https://example.test/"]))
        await asyncio.to_thread(self.agent.capture_started.wait, 5)
        await asyncio.sleep(0.1)
        self.assertFalse(self.agent.deleted)
        self.agent.capture_release.set()
        stats = await task
        self.assertEqual(stats.requests_failed, 1)
        self.assertEqual(len(failures), 1)
        self.assertFalse(self.agent.deleted_during_capture)
        self.assertEqual(len(self.agent.deleted), 1)

    async def test_error_handler_keeps_page_until_cleanup(self):
        crawler = self.crawler(max_request_retries=0)
        observed = []

        @crawler.router.default_handler
        async def handler(ctx):
            raise RuntimeError("handler failed")

        @crawler.failed_request_handler
        async def failure(ctx, error):
            observed.append(await ctx.page.title())
            self.assertFalse(self.agent.deleted)

        await crawler.run(["https://example.test/"])
        self.assertEqual(observed, ["Fixture"])
        self.assertEqual(len(self.agent.deleted), 1)

    async def test_send_request_is_blocked_without_retry_or_external_http(self):
        crawler = self.crawler(max_request_retries=3)

        @crawler.router.default_handler
        async def handler(ctx):
            await ctx.send_request("https://external.test/")

        with patch(
            "impit.AsyncClient.request", side_effect=AssertionError("external HTTP")
        ):
            stats = await crawler.run(["https://example.test/"])
        self.assertEqual(stats.requests_failed, 1)
        self.assertEqual(len(self.agent.navigations), 1)

    async def test_named_queue_resumes_with_new_storage_client(self):
        config = Configuration(storage_dir=self.temp.name, purge_on_start=False)
        first_storage = FileSystemStorageClient()
        queue = await RequestQueue.open(
            name="resume", configuration=config, storage_client=first_storage
        )
        await queue.add_requests(
            ["https://example.test/one", "https://example.test/two"]
        )
        crawler = self.crawler(
            storage_client=first_storage,
            request_manager=queue,
            max_requests_per_crawl=1,
        )

        @crawler.router.default_handler
        async def first(ctx):
            pass

        await crawler.run()
        ServiceLocator.global_storage_instance_manager = None
        second_storage = FileSystemStorageClient()
        resumed_queue = await RequestQueue.open(
            name="resume", configuration=config, storage_client=second_storage
        )
        resumed = self.crawler(
            storage_client=second_storage, request_manager=resumed_queue
        )

        @resumed.router.default_handler
        async def second(ctx):
            pass

        await resumed.run()
        self.assertEqual(
            Counter(url for _, url in self.agent.navigations),
            {"https://example.test/one": 1, "https://example.test/two": 1},
        )

    async def test_link_filters_transform_base_and_zero_limit(self):
        root = "https://example.test/"
        self.agent.html[root] = (
            '<a href="one">1</a><a href="two">2</a><a href="three">3</a>'
        )
        crawler = self.crawler()

        @crawler.router.default_handler
        async def handler(ctx):
            self.assertEqual(await ctx.extract_links(limit=0), [])
            links = await ctx.extract_links(
                base_url="https://example.test/items/",
                include=[re.compile(r".*/(one|two)$")],
                exclude=[re.compile(r".*/two$")],
                limit=1,
                transform_request_function=lambda request: {**request, "label": "item"},
            )
            self.assertEqual(
                [(r.url, r.label) for r in links],
                [("https://example.test/items/one", "item")],
            )

        stats = await crawler.run([root])
        self.assertEqual(stats.requests_finished, 1)

    async def test_same_domain_is_offline_and_redirects_stay_in_scope(self):
        root = "https://www.example.com/start"
        self.agent.html[root] = (
            '<a href="https://cdn.example.com/one">One</a><a href="https://other.com/two">Offsite</a>'
        )
        self.agent.redirects["https://cdn.example.com/one"] = "https://elsewhere.com/"
        crawler = self.crawler()
        handled = []

        @crawler.router.default_handler
        async def handler(ctx):
            handled.append(ctx.page.url)
            links = await ctx.extract_links(strategy="same-domain")
            self.assertEqual([r.url for r in links], ["https://cdn.example.com/one"])
            await ctx.enqueue_links(strategy="same-domain")

        with patch(
            "requests.sessions.Session.request",
            side_effect=AssertionError("PSL download"),
        ):
            stats = await crawler.run(
                [Request.from_url(root, enqueue_strategy="same-domain")]
            )
        self.assertEqual(handled, [root])
        self.assertEqual(stats.requests_failed, 0)
        self.assertEqual(len(self.agent.navigations), 2)
        self.assertEqual(len(self.agent.deleted), 2)

    async def test_cleanup_failure_is_retried_at_shutdown(self):
        self.agent.delete_failures = 1
        crawler = self.crawler(request_handler=lambda ctx: asyncio.sleep(0))
        stats = await crawler.run(["https://example.test/cleanup"])
        self.assertEqual(stats.requests_finished, 1)
        self.assertEqual(len(self.agent.deleted), 1)
        self.assertFalse(crawler._pending_cleanup)

    async def test_permanent_cleanup_failure_is_surfaced(self):
        self.agent.delete_failures = 100
        crawler = self.crawler(request_handler=lambda ctx: asyncio.sleep(0))
        with self.assertRaises(ExceptionGroup) as caught:
            await crawler.run(["https://example.test/cleanup"])
        self.assertIn("REL session cleanup failed", str(caught.exception))
        self.assertEqual(len(self.agent.created), 1)
        self.assertFalse(self.agent.deleted)
        self.agent.delete_failures = 0
        await crawler._cleanup_all()
        self.assertEqual(len(self.agent.deleted), 1)

    async def test_competing_borrowed_lease_and_recovery(self):
        first = self.crawler(session_id="Session99")
        second = self.crawler(
            session_id="Session99", request_handler=lambda ctx: asyncio.sleep(0)
        )
        async with first._resources():
            with self.assertRaisesRegex(RuntimeError, "already leased"):
                await second.run(["https://example.test/borrowed"])
            self.assertFalse(self.agent.navigations)
        stats = await second.run(["https://example.test/borrowed"])
        self.assertEqual(stats.requests_finished, 1)
        self.assertEqual(
            self.agent.navigations, [("Session99", "https://example.test/borrowed")]
        )
        self.assertFalse(self.agent.deleted)

    async def test_repeated_cancellation_during_allocation_still_cleans_session(self):
        started, release = threading.Event(), threading.Event()
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(rel_base_url=self.url)
            original = browser._impl._client.create_session

            def create(**kwargs):
                started.set()
                release.wait(5)
                return original(**kwargs)

            with patch.object(
                browser._impl._client, "create_session", side_effect=create
            ):
                task = asyncio.create_task(browser.new_page())
                self.assertTrue(await asyncio.to_thread(started.wait, 5))
                task.cancel()
                await asyncio.sleep(0)
                task.cancel()
                await asyncio.sleep(0)
                self.assertFalse(task.done())
                release.set()
                with self.assertRaises(asyncio.CancelledError):
                    await task
        self.assertEqual(len(self.agent.created), 1)
        self.assertEqual(len(self.agent.deleted), 1)

    def test_configuration_rejects_unsupported_features(self):
        for kwargs in (
            {"respect_robots_txt_file": True},
            {"http_client": object()},
            {"proxy_configuration": object()},
            {"use_session_pool": True},
            {"retry_on_blocked": True},
            {"profile": "Research", "session_id": "Session99"},
            {"session_id": "Session99", "concurrency_settings": ConcurrencySettings()},
        ):
            with (
                self.subTest(kwargs=kwargs),
                self.assertRaises((UnsupportedError, ValueError)),
            ):
                self.crawler(**kwargs)


if __name__ == "__main__":
    unittest.main()
