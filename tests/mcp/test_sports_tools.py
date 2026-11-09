"""
MCP sports tool tests. Uses the Flask test client. No network.

Run:
  python -m unittest tests.mcp.test_sports_tools -v
"""
import json
import unittest
from datetime import datetime, timedelta

from flask import Flask

from app.projects.mcp.routes import mcp_bp
from app.projects.mcp.sports_tools import (
    _BUCKETS,
    client_ip,
    enforce_query_rate_limit,
    prune_rate_buckets,
    reset_rate_buckets,
)
from app.projects.mcp import sports_tools
from app.projects.sports_schedules.core.run_query import ScheduleQueryResult


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SERVER_NAME"] = "localhost"
    app.register_blueprint(mcp_bp, url_prefix="/mcp")
    return app


class TestSportsMcpTools(unittest.TestCase):
    def setUp(self):
        self.app = _app()
        self.client = self.app.test_client()
        reset_rate_buckets()

    def tearDown(self):
        reset_rate_buckets()

    def _rpc(self, method, params=None, headers=None):
        return self.client.post(
            "/mcp/",
            json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
            headers=headers,
        )

    def test_initialize_names_the_server_gmich(self):
        body = self._rpc("initialize").get_json()
        self.assertEqual(body["result"]["serverInfo"]["name"], "gmich")

    def test_tools_list_includes_schedule_tools(self):
        tools = self._rpc("tools/list").get_json()["result"]["tools"]
        names = [tool["name"] for tool in tools]
        self.assertEqual(
            names,
            ["get_personal", "get_work", "get_schedule_options", "query_schedules"],
        )
        for tool in tools:
            if tool["name"] in ("get_schedule_options", "query_schedules"):
                self.assertEqual(tool["inputSchema"]["type"], "object")

    def test_get_schedule_options_skips_dolthub(self):
        from unittest.mock import patch

        with patch("app.projects.sports_schedules.core.run_query.DoltHubClient") as dolt:
            response = self._rpc("tools/call", {"name": "get_schedule_options", "arguments": {}})
        dolt.assert_not_called()
        self.assertFalse(response.get_json()["result"]["isError"])
        payload = json.loads(response.get_json()["result"]["content"][0]["text"])
        self.assertIn("NBA", [league["code"] for league in payload["leagues"]])
        self.assertIn("NJ", payload["states"])
        self.assertEqual(len(payload["today"]), 10)
        self.assertNotIn("coverage", payload)

    def test_bad_league_is_a_tool_error(self):
        from unittest.mock import patch

        with patch("app.projects.sports_schedules.core.run_query.DoltHubClient") as dolt:
            response = self._rpc("tools/call", {
                "name": "query_schedules",
                "arguments": {
                    "date_mode": "today",
                    "dimensions": ["date"],
                    "filters": {"league": ["NOTALEAGUE"]},
                },
            })
        dolt.assert_not_called()
        result = response.get_json()["result"]
        self.assertTrue(result["isError"])
        self.assertIn("NOTALEAGUE", result["content"][0]["text"])

    def test_successful_call_is_compact_and_omits_sql(self):
        from unittest.mock import patch

        fake = ScheduleQueryResult(
            rows=[{
                "date": "2026-11-07",
                "time": "7:00 PM",
                "league": "NHL",
                "home_team": "Devils",
                "road_team": "Rangers",
            }],
            row_count=1,
            truncated=False,
            date_range_used={"start": "2026-11-06", "end": "2026-11-08"},
            applied={
                "dimensions": ["date", "time", "league", "home_team", "road_team"],
                "filters": {"home_state": ["NJ"]},
                "date_mode": "this_weekend",
                "limit": 100,
            },
            sql="SELECT secret",
        )
        with patch("app.projects.mcp.sports_tools.run_schedule_query", return_value=fake):
            with patch("app.projects.mcp.sports_tools._record_query"):
                response = self._rpc("tools/call", {
                    "name": "query_schedules",
                    "arguments": {"date_mode": "this_weekend", "filters": {"home_state": ["NJ"]}},
                })
        result = response.get_json()["result"]
        self.assertFalse(result["isError"])
        payload = json.loads(result["content"][0]["text"])
        self.assertEqual(
            payload["columns"],
            ["date", "time", "league", "home_team", "road_team"],
        )
        self.assertEqual(payload["rows"], [["2026-11-07", "7:00 PM", "NHL", "Devils", "Rangers"]])
        self.assertIn("date_range_used", payload)
        self.assertIn("applied", payload)
        self.assertNotIn("sql", payload)

    def test_personal_tool_still_returns_data(self):
        response = self._rpc("tools/call", {"name": "get_personal", "arguments": {}})
        result = response.get_json()["result"]
        self.assertFalse(result["isError"])
        self.assertIn("bio", result["content"][0]["text"])

    def test_landing_page_lists_schedule_tools(self):
        html = self.client.get("/mcp/").get_data(as_text=True)
        self.assertIn("query_schedules", html)
        self.assertIn("get_schedule_options", html)

    def test_client_ip_uses_the_last_forwarded_hop(self):
        with self.app.test_request_context(headers={"X-Forwarded-For": "9.9.9.9, 8.8.8.8"}):
            self.assertEqual(client_ip(), "8.8.8.8")
        with self.app.test_request_context(environ_base={"REMOTE_ADDR": "10.1.2.3"}):
            self.assertEqual(client_ip(), "10.1.2.3")

    def test_prune_drops_expired_ip_keys(self):
        now = datetime.utcnow()
        _BUCKETS["stale"] = [now - timedelta(minutes=2)]
        _BUCKETS["fresh"] = [now]
        prune_rate_buckets(now)
        self.assertNotIn("stale", _BUCKETS)
        self.assertIn("fresh", _BUCKETS)

    def test_enforce_prunes_after_the_interval(self):
        sports_tools._LAST_PRUNE = datetime.utcnow() - timedelta(minutes=10)
        _BUCKETS["stale"] = [datetime.utcnow() - timedelta(minutes=2)]
        with self.app.test_request_context(environ_base={"REMOTE_ADDR": "1.2.3.4"}):
            enforce_query_rate_limit()
        self.assertNotIn("stale", _BUCKETS)
        self.assertIn("1.2.3.4", _BUCKETS)
