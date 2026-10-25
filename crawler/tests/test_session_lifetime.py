import unittest
from unittest.mock import patch
from rel_crawler.api import RelClient


class SessionLifetimeTests(unittest.TestCase):
    def test_creation_forwards_policy_and_ping_uses_session_route(self):
        client = RelClient("http://127.0.0.1:17319/v1")
        self.addCleanup(getattr(client, "close", lambda: None))
        with patch.object(client, "_request", return_value={"session": {"id": "Session1"}}) as request:
            lifetime = {"type": "inactivity", "timeout_seconds": 30}
            self.assertEqual(client.create_session(profile=None, lifetime=lifetime), "Session1")
            self.assertEqual(request.call_args.args[2]["lifetime"], lifetime)
            self.assertNotIn("group_id", request.call_args.args[2])
            client.ping_session("Session1")
            request.assert_called_with("POST", "/sessions/Session1/ping", {}, timeout=5.0)

    def test_explicit_project_wins_over_environment(self):
        client = RelClient("http://127.0.0.1:17319/v1")
        self.addCleanup(getattr(client, "close", lambda: None))
        with patch.dict("os.environ", {"REL_PROJECT_ID": "ProjectEnvironment"}), patch.object(client, "_request", return_value={"session": {"id": "Session1"}}) as request:
            client.create_session(profile=None, project_id="ProjectResearch")
            self.assertEqual(request.call_args.args[2]["project_id"], "ProjectResearch")
            client.create_session(profile=None)
            self.assertEqual(request.call_args.args[2]["project_id"], "ProjectEnvironment")
