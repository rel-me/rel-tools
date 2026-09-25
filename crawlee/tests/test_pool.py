import asyncio
from dataclasses import FrozenInstanceError
from datetime import timedelta

from test_crawler import AgentTestCase

from crawlee import ConcurrencySettings


class PoolTests(AgentTestCase):
    async def test_bounded_exclusive_reuse_and_metrics(self):
        crawler = self.crawler(
            session_pool_size=2,
            concurrency_settings=ConcurrencySettings(
                min_concurrency=2, desired_concurrency=2, max_concurrency=2
            ),
        )
        active = set()
        entered = asyncio.Event()

        @crawler.router.default_handler
        async def handler(ctx):
            session = ctx.page.session_id
            self.assertNotIn(session, active)
            active.add(session)
            if len(active) == 2:
                entered.set()
            await asyncio.wait_for(entered.wait(), 5)
            await asyncio.sleep(0.025)
            self.assertEqual(self.agent.sessions[session], ctx.request.url)
            self.assertEqual(await ctx.extract_links(), [])
            active.remove(session)

        before = crawler.metrics
        stats = await crawler.run([f"https://example.test/{i}" for i in range(6)])
        self.assertEqual(stats.requests_finished, 6)
        self.assertEqual(len(self.agent.created), 2)
        self.assertEqual(len(self.agent.deleted), 2)
        metrics = crawler.metrics
        self.assertEqual(metrics.sessions_created, 2)
        self.assertEqual(metrics.session_reuses, 4)
        self.assertEqual(metrics.requests_started, 6)
        self.assertGreater(metrics.navigation_seconds, 0)
        self.assertGreater(metrics.handler_seconds, 0.1)
        self.assertGreater(metrics.link_extraction_seconds, 0)
        self.assertGreater(metrics.cleanup_seconds, 0)
        self.assertEqual(before.requests_started, 0)
        with self.assertRaises(FrozenInstanceError):
            metrics.sessions_created = 9

    async def test_waiting_workers_do_not_exceed_pool_capacity(self):
        crawler = self.crawler(
            session_pool_size=1,
            concurrency_settings=ConcurrencySettings(
                min_concurrency=2, desired_concurrency=2, max_concurrency=2
            ),
        )

        @crawler.router.default_handler
        async def handler(ctx):
            await asyncio.sleep(0.04)

        stats = await crawler.run(["https://example.test/a", "https://example.test/b"])
        self.assertEqual(stats.requests_finished, 2)
        self.assertEqual(crawler.metrics.sessions_created, 1)
        self.assertEqual(crawler.metrics.session_reuses, 1)
        self.assertGreater(crawler.metrics.session_wait_seconds, 0.03)

    async def test_failure_retires_after_error_handler(self):
        crawler = self.crawler(session_pool_size=1, max_request_retries=1)
        attempts = []
        error_pages = []

        @crawler.router.default_handler
        async def handler(ctx):
            attempts.append(ctx.page.session_id)
            if ctx.request.retry_count == 0:
                raise RuntimeError("retry fixture")

        @crawler.error_handler
        async def error(ctx, exc):
            await asyncio.sleep(0.02)
            self.assertNotIn(ctx.page.session_id, self.agent.deleted)
            error_pages.append(await ctx.page.title())

        stats = await crawler.run(["https://example.test/retry"])
        self.assertEqual(stats.requests_finished, 1)
        self.assertEqual(error_pages, ["Fixture"])
        self.assertEqual(len(set(attempts)), 2)
        self.assertEqual(crawler.metrics.sessions_retired, 1)
        self.assertEqual(crawler.metrics.sessions_created, 2)
        self.assertEqual(len(self.agent.deleted), 2)

    async def test_navigation_failure_retires_before_retry(self):
        self.agent.failures["https://example.test/a"] = [("UPSTREAM_UNAVAILABLE", True)]
        crawler = self.crawler(
            session_pool_size=1,
            max_request_retries=1,
            request_handler=lambda ctx: asyncio.sleep(0),
        )
        stats = await crawler.run(["https://example.test/a"])
        self.assertEqual(stats.requests_finished, 1)
        self.assertEqual(crawler.metrics.sessions_created, 2)
        self.assertEqual(crawler.metrics.sessions_retired, 1)
        self.assertEqual(len(self.agent.deleted), 2)

    async def test_age_limit_and_metrics_reset_between_runs(self):
        crawler = self.crawler(
            session_pool_size=1,
            max_requests_per_session=2,
            request_handler=lambda ctx: asyncio.sleep(0),
        )
        stats = await crawler.run([f"https://example.test/{i}" for i in range(5)])
        self.assertEqual(stats.requests_finished, 5)
        self.assertEqual(crawler.metrics.sessions_created, 3)
        self.assertEqual(crawler.metrics.session_reuses, 2)
        self.assertEqual(crawler.metrics.sessions_retired, 2)
        self.assertEqual(len(self.agent.deleted), 3)
        stats = await crawler.run(["https://example.test/again"])
        self.assertEqual(stats.requests_finished, 1)
        self.assertEqual(crawler.metrics.sessions_created, 1)
        self.assertEqual(crawler.metrics.session_reuses, 0)
        self.assertEqual(len(self.agent.deleted), 4)

    async def test_cancelled_capture_drains_then_retires(self):
        self.agent.block_capture = True
        crawler = self.crawler(
            session_pool_size=1,
            max_request_retries=0,
            request_handler_timeout=timedelta(milliseconds=50),
        )

        @crawler.router.default_handler
        async def handler(ctx):
            await ctx.page.content()

        task = asyncio.create_task(crawler.run(["https://example.test/a"]))
        self.assertTrue(await asyncio.to_thread(self.agent.capture_started.wait, 5))
        await asyncio.sleep(0.1)
        self.assertFalse(self.agent.deleted)
        self.agent.capture_release.set()
        stats = await task
        self.assertEqual(stats.requests_failed, 1)
        self.assertEqual(crawler.metrics.sessions_retired, 1)
        self.assertEqual(len(self.agent.deleted), 1)
        self.assertFalse(self.agent.deleted_during_capture)

    async def test_delete_failure_retains_capacity_until_close_succeeds(self):
        self.agent.delete_failures = 2
        crawler = self.crawler(
            session_pool_size=1,
            max_requests_per_session=1,
            max_request_retries=0,
            request_handler=lambda ctx: asyncio.sleep(0),
        )
        stats = await crawler.run(["https://example.test/a", "https://example.test/b"])
        self.assertEqual(stats.requests_finished, 1)
        self.assertEqual(stats.requests_failed, 1)
        self.assertEqual(len(self.agent.created), 1)
        self.assertEqual(len(self.agent.deleted), 1)
        self.assertFalse(crawler._pending_cleanup)
        self.assertEqual(crawler.metrics.sessions_retired, 1)

    async def test_run_cancellation_with_waiting_lease_closes_pool(self):
        crawler = self.crawler(
            session_pool_size=1,
            concurrency_settings=ConcurrencySettings(
                min_concurrency=2, desired_concurrency=2, max_concurrency=2
            ),
        )
        entered = asyncio.Event()
        never = asyncio.Event()

        @crawler.router.default_handler
        async def handler(ctx):
            entered.set()
            await never.wait()

        task = asyncio.create_task(
            crawler.run(["https://example.test/a", "https://example.test/b"])
        )
        await asyncio.wait_for(entered.wait(), 5)
        await asyncio.sleep(0.02)
        task.cancel()
        # Crawlee treats run cancellation as an interrupted crawl and returns stats.
        await asyncio.wait_for(task, 5)
        self.assertEqual(len(self.agent.created), 1)
        self.assertEqual(len(self.agent.deleted), 1)
        self.assertIsNone(crawler._pool)
        self.assertFalse(crawler._pending_cleanup)

    def test_pool_configuration_is_explicit(self):
        for options in (
            {"session_pool_size": 0},
            {"session_pool_size": True},
            {"session_pool_size": 1, "persist": True},
            {"session_pool_size": 1, "session_id": "Session99"},
            {"session_pool_size": 1, "max_requests_per_session": 0},
            {"max_requests_per_session": 2},
        ):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.crawler(**options)
