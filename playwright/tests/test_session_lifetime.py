import unittest
from unittest.mock import patch
from rel_playwright._rpc import RelRpcClient


class SessionLifetimeTests(unittest.TestCase):
    def client(self):
        client = RelRpcClient("http://127.0.0.1:17319/v1")
        self.addCleanup(getattr(client, "close", lambda: None))
        return client

    def test_creation_forwards_policy_and_ping_uses_session_route(self):
        client = self.client()
        with patch.object(client, "_request", return_value={"session": {"id": "Session1", "group_id": "Group7"}}) as request:
            lifetime = {"type": "inactivity", "timeout_seconds": 30}
            self.assertEqual(client.create_session(profile=None, lifetime=lifetime), "Session1")
            self.assertEqual(request.call_args.args[2], {"lifetime": lifetime})
            client.ping_session("Session1")
            request.assert_called_with("POST", "/sessions/Session1/ping", {}, timeout=5.0)
            client.delete_owned_session("Session1", owns_group=True)
            request.assert_called_with("DELETE", "/groups/Group7", None, timeout=10.0)

    def test_existing_group_adds_tab_and_cleanup_preserves_group(self):
        client = self.client()
        with patch.object(client, "_request", return_value={"session": {"id": "Session2", "group_id": "Group7"}}) as request:
            self.assertEqual(client.create_session(profile=None, group_id="Group7"), "Session2")
            self.assertEqual(request.call_args.args[2], {"group_id": "Group7"})
            client.delete_owned_session("Session2", owns_group=False)
            request.assert_called_with("DELETE", "/sessions/Session2", None, timeout=10.0)

    def test_resumed_managed_session_recovers_its_group_for_cleanup(self):
        client = self.client()
        with patch.object(client, "_request", return_value={"session": {"id": "Session1", "group_id": "Group7"}}) as request:
            client.delete_owned_session("Session1", owns_group=True)
            self.assertEqual(request.call_args_list[0].args[:2], ("GET", "/sessions/Session1"))
            request.assert_called_with("DELETE", "/groups/Group7", None, timeout=10.0)
