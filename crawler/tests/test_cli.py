from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rel_crawler import CrawlApplication, CrawlSummary
from rel_crawler.cli import load_application, main

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "hackernews.py"


class FakeApplication:
    def __init__(self, state_path: Path) -> None:
        self.state_path = state_path
        self.overrides: dict[str, object] | None = None

    def run(self, **overrides: object) -> CrawlSummary:
        self.overrides = overrides
        print("callback output")
        return CrawlSummary(
            discovered=4,
            captured=3,
            failed=1,
            pending=0,
            skipped_existing=2,
            session_id="Session9",
            session_generation=2,
            session_restart_count=1,
            state_path=self.state_path,
        )


class CrawlerCliTests(unittest.TestCase):
    def test_loads_application_from_python_file(self) -> None:
        with patch.dict(
            "os.environ",
            {"REL_PROFILE": "Research", "HN_MAX_LINKS": "3"},
        ):
            application = load_application(f"{EXAMPLE}:app")

        self.assertIsInstance(application, CrawlApplication)
        self.assertEqual(application.profile, "Research")
        self.assertEqual(application.max_links, 3)
        self.assertEqual(application.definition.source_ready_selector, "a.morelink")

    def test_run_applies_overrides_and_prints_json_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application = FakeApplication(Path(temporary) / "checkpoint.json")
            stdout = io.StringIO()
            stderr = io.StringIO()
            with (
                patch("rel_crawler.cli.load_application", return_value=application),
                patch("rel_crawler.cli.logging.basicConfig"),
                patch("sys.stdout", stdout),
                patch("sys.stderr", stderr),
            ):
                result = main(
                    [
                        "run",
                        "crawler_config:app",
                        "--profile",
                        "Oxylabs",
                        "--retry-failed",
                        "--action-delay",
                        "0",
                        "--max-links",
                        "5",
                    ]
                )

        self.assertEqual(result, 0)
        self.assertEqual(
            application.overrides,
            {
                "profile": "Oxylabs",
                "action_delay": 0.0,
                "max_links": 5,
                "retry_failed": True,
            },
        )
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["captured"], 3)
        self.assertEqual(payload["session_id"], "Session9")
        self.assertTrue(payload["state_path"].endswith("checkpoint.json"))
        self.assertNotIn("callback output", stdout.getvalue())
        self.assertIn("callback output", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
