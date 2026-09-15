"""Run with REL open; REL_AGENT_PORT can select a worktree Debug runtime."""

import asyncio

from rel_crawlee import RelCrawler, RelCrawlingContext


async def main() -> None:
    crawler = RelCrawler(max_requests_per_crawl=10, max_request_retries=2)

    @crawler.router.default_handler
    async def handle(context: RelCrawlingContext) -> None:
        await context.push_data(
            {
                "url": context.page.url,
                "title": await context.page.title(),
                "status": context.response.status,
            }
        )
        await context.enqueue_links(strategy="same-hostname")

    await crawler.run(["https://example.com/"])
    await crawler.export_data("results.json")


if __name__ == "__main__":
    asyncio.run(main())
