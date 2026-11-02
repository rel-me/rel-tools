"""Exercise the actual plugin launcher with isolated application locations."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest


class MCPLauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rel launcher ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.system_app = self.root / "Applications/REL.app"
        self.home = self.root / "home"
        self.user_app = self.home / "Applications/REL.app"
        self.custom_app = self.root / "Custom Apps/Renamed REL.app"
        self.env = {**os.environ, "HOME": str(self.home)}
        self.env.pop("REL_APP_PATH", None)
        self.env.pop("DISCOVERED_APP", None)
        self.lookup = self.root / "osascript"
        self.lookup.write_text('#!/bin/sh\nprintf "%s\\n" "${DISCOVERED_APP:-}"\n')
        self.lookup.chmod(0o755)
        config = json.loads((Path(__file__).parents[1] / ".mcp.json").read_text())
        self.server = config["mcpServers"]["REL"]
        self.script = self.server["args"][1].replace(
            "/Applications/REL.app", shlex.quote(str(self.system_app)), 2
        ).replace("/usr/bin/osascript", shlex.quote(str(self.lookup)))

    def install(self, app, marker, version="0.1.156", contract="rel-project-sessions-v1"):
        adapter = app / "Contents/Resources/rel-mcp"
        adapter.parent.mkdir(parents=True)
        adapter.write_text('#!/bin/sh\nif [ "${1:-}" = --version ]; then printf "rel-mcp %s\\n" ' + shlex.quote(version) + '; exit 0; fi\nif [ "${1:-}" = --api-contract ]; then printf "%s\\n" ' + shlex.quote(contract) + '; exit 0; fi\nprintf "%s\\n" ' + shlex.quote(marker) + '\nexit 7\n')
        adapter.chmod(0o755)

    def run_launcher(self):
        return subprocess.run(
            [self.server["command"], "-c", self.script],
            env=self.env, capture_output=True, text=True, check=False,
        )

    def assert_adapter(self, marker):
        result = self.run_launcher()
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertEqual(result.stdout, marker + "\n")
        self.assertEqual(result.stderr, "")

    def test_old_adapter_is_rejected_before_stdio(self):
        self.install(self.custom_app, "must not start", "0.1.155")
        self.env["REL_APP_PATH"] = str(self.custom_app)
        result = self.run_launcher()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("REL 0.1.156 or later is required", result.stderr)

    def test_stale_schema_is_rejected_even_with_supported_version(self):
        self.install(self.custom_app, "must not start", contract="")
        self.env["REL_APP_PATH"] = str(self.custom_app)
        result = self.run_launcher()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("does not support the current Project/Session API", result.stderr)

    def test_newer_adapter_is_accepted(self):
        self.install(self.custom_app, "newer", "0.1.158")
        self.env["REL_APP_PATH"] = str(self.custom_app)
        self.assert_adapter("newer")

    def test_invalid_adapter_version_is_rejected(self):
        for version in ["", "0.1", "0.1.156-beta", "garbage", "0.1.156\n0.1.155"]:
            with self.subTest(version=version):
                adapter = self.custom_app / "Contents/Resources/rel-mcp"
                if adapter.exists():
                    adapter.unlink()
                self.custom_app.mkdir(parents=True, exist_ok=True)
                adapter.parent.mkdir(parents=True, exist_ok=True)
                adapter.write_text('#!/bin/sh\nif [ "${1:-}" = --version ]; then printf "%s\\n" ' + shlex.quote(version) + '; exit 0; fi\necho "must not start"\n')
                adapter.chmod(0o755)
                self.env["REL_APP_PATH"] = str(self.custom_app)
                result = self.run_launcher()
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")

    def test_system_install_wins(self):
        self.install(self.system_app, "system")
        self.install(self.user_app, "user")
        self.install(self.custom_app, "registered")
        self.env["DISCOVERED_APP"] = str(self.custom_app)
        self.lookup.write_text('#!/bin/sh\necho "lookup should not run" >&2\nexit 1\n')
        self.assert_adapter("system")

    def test_user_install(self):
        self.install(self.user_app, "user")
        self.assert_adapter("user")

    def test_registered_renamed_app_with_spaces(self):
        self.install(self.custom_app, "registered")
        self.env["DISCOVERED_APP"] = str(self.custom_app) + "/"
        self.assert_adapter("registered")

    def test_explicit_override_wins(self):
        self.install(self.system_app, "system")
        self.install(self.custom_app, "override")
        self.env["REL_APP_PATH"] = str(self.custom_app)
        self.assert_adapter("override")

    def test_invalid_override_does_not_fall_back(self):
        self.install(self.system_app, "system")
        self.env["REL_APP_PATH"] = str(self.custom_app)
        result = self.run_launcher()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("REL_APP_PATH is not an app directory", result.stderr)

    def test_missing_app(self):
        result = self.run_launcher()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("REL.app was not found", result.stderr)

    def test_lookup_failure(self):
        self.lookup.write_text('#!/bin/sh\necho "not registered" >&2\nexit 1\n')
        result = self.run_launcher()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("REL.app was not found", result.stderr)
        self.assertNotIn("not registered", result.stderr)

    def test_missing_adapter(self):
        self.custom_app.mkdir(parents=True)
        self.env["REL_APP_PATH"] = str(self.custom_app)
        result = self.run_launcher()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("REL MCP adapter was not found", result.stderr)


if __name__ == "__main__":
    unittest.main()
