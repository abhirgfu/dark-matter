"""The MCP server speaks the protocol: no network is touched by these tests."""
import importlib.util
import json
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("dm_mcp", ROOT / "mcp" / "server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


class Protocol(unittest.TestCase):
    def test_initialize_echoes_the_client_version(self):
        reply = server.handle({"id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}})
        self.assertEqual(reply["result"]["protocolVersion"], "2024-11-05")
        self.assertIn("tools", reply["result"]["capabilities"])

    def test_notifications_get_no_reply(self):
        self.assertIsNone(server.handle({"method": "notifications/initialized"}))

    def test_tools_are_listed_with_schemas(self):
        reply = server.handle({"id": 2, "method": "tools/list"})
        names = {t["name"] for t in reply["result"]["tools"]}
        self.assertEqual(names, set(server.TOOLS))
        self.assertTrue(all("inputSchema" in t for t in reply["result"]["tools"]))

    def test_unknown_method_and_tool_are_errors(self):
        self.assertIn("error", server.handle({"id": 3, "method": "nope"}))
        self.assertIn("error", server.handle({"id": 4, "method": "tools/call", "params": {"name": "nope"}}))

    def test_a_failing_tool_reports_to_the_model(self):
        original = server.RESULTS
        server.RESULTS = pathlib.Path(tempfile.gettempdir()) / "dark-matter-missing.json"
        try:
            reply = server.handle({"id": 5, "method": "tools/call", "params": {"name": "revenue_source"}})
        finally:
            server.RESULTS = original
        self.assertTrue(reply["result"]["isError"])

    def test_daily_series_refuses_a_bad_name(self):
        original = server.results
        server.results = lambda: {"weigh": {"series": []}, "flows": {"daily": []}, "activity": []}
        try:
            reply = server.handle({"id": 6, "method": "tools/call", "params": {"name": "daily_series", "arguments": {"name": "x"}}})
            good = server.handle({"id": 7, "method": "tools/call", "params": {"name": "daily_series", "arguments": {"name": "weight"}}})
        finally:
            server.results = original
        self.assertTrue(reply["result"]["isError"])
        self.assertEqual(json.loads(good["result"]["content"][0]["text"])["rows"], [])


if __name__ == "__main__":
    unittest.main()
