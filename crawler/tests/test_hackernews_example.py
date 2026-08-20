from __future__ import annotations

import logging
import runpy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from rel_crawler import CrawlItem, Link


EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "hackernews.py"


class HackerNewsExampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with patch.dict(
            "os.environ",
            {"REL_PROFILE": "Research", "HN_MAX_LINKS": "3"},
        ):
            cls.module = runpy.run_path(str(EXAMPLE), run_name="hackernews_example")
        cls.root = cls.module["ROOT"]
        cls.post_path = staticmethod(cls.module["post_path"])
        cls.is_post = staticmethod(cls.module["is_post"])
        cls.configure_logging = staticmethod(cls.module["configure_logging"])
        cls.definition = cls.module["definition"]
        cls.crawler = cls.module["crawler"]

    @staticmethod
    def item(url: str) -> CrawlItem:
        return CrawlItem(
            key=url,
            index=0,
            link=Link(index=0, url=url, text="post"),
            attempt=1,
        )

    def test_selects_hacker_news_discussion_links(self) -> None:
        self.assertTrue(
            self.is_post(
                Link(
                    index=0,
                    url="https://news.ycombinator.com/item?id=123456",
                    text="12 comments",
                )
            )
        )
        self.assertFalse(
            self.is_post(
                Link(
                    index=1,
                    url="https://news.ycombinator.com/item?id=123456",
                    text="12 comments",
                    target="_blank",
                )
            )
        )
        self.assertFalse(
            self.is_post(
                Link(
                    index=2,
                    url="https://news.ycombinator.com/user?id=example",
                    text="user",
                )
            )
        )

    def test_post_path_uses_the_item_id(self) -> None:
        path = self.post_path(
            self.item("https://news.ycombinator.com/item?id=123456")
        )

        self.assertEqual(
            path.relative_to(self.root),
            Path("item/123456/index.html"),
        )

    def test_query_variants_use_stable_distinct_index_names(self) -> None:
        plain = self.post_path(
            self.item("https://news.ycombinator.com/item?id=123456")
        )
        first = self.post_path(
            self.item("https://news.ycombinator.com/item?id=123456&view=top")
        )
        repeated = self.post_path(
            self.item("https://news.ycombinator.com/item?id=123456&view=top")
        )
        second = self.post_path(
            self.item("https://news.ycombinator.com/item?id=123456&view=new")
        )

        self.assertEqual(first, repeated)
        self.assertNotEqual(first, second)
        self.assertNotEqual(plain, first)
        self.assertRegex(first.name, r"^index\.query-[0-9a-f]{12}\.html$")

    def test_rejects_malformed_item_ids(self) -> None:
        for url in (
            "https://news.ycombinator.com/item",
            "https://news.ycombinator.com/item?id=",
            "https://news.ycombinator.com/item?id=../tmp",
            "https://news.ycombinator.com/item?id=123&id=456",
        ):
            with self.subTest(url=url):
                self.assertFalse(self.is_post(Link(index=0, url=url, text="post")))

    def test_configures_profile_and_readiness(self) -> None:
        self.assertEqual(self.crawler.profile, "Research")
        self.assertEqual(self.crawler.max_links, 3)
        self.assertEqual(self.definition.source_ready_selector, "a.morelink")
        self.assertEqual(
            self.definition.capture_ready_selector,
            "table.comment-tree",
        )

    def test_script_configures_info_logging_to_stderr(self) -> None:
        with patch("logging.basicConfig") as basic_config:
            self.configure_logging()

        basic_config.assert_called_once_with(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
            stream=sys.stderr,
        )


if __name__ == "__main__":
    unittest.main()
