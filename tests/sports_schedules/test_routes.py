"""
Unit tests for Sports Schedules API routes.
Uses Flask test client with mocked DoltHub (no network).
"""
import unittest
from unittest.mock import patch

from flask import Flask

from app.projects.sports_schedules.routes import sports_schedules_bp


def _create_test_app():
    """Minimal app with only sports_schedules blueprint."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    app.register_blueprint(sports_schedules_bp)
    return app


class TestApiQueryValidation(unittest.TestCase):
    """API returns 400 for invalid params."""

    def setUp(self):
        self.app = _create_test_app()
        self.client = self.app.test_client()

    def test_no_params_returns_400(self):
        r = self.client.get("/sports-schedules/api/query")
        self.assertEqual(r.status_code, 400)
        data = r.get_json()
        self.assertIn("error", data)
        self.assertIn("dimension", data["error"].lower())

    def test_no_dimensions_count_off_returns_400(self):
        r = self.client.get("/sports-schedules/api/query?limit=10")
        self.assertEqual(r.status_code, 400)

    def test_invalid_limit_returns_400(self):
        r = self.client.get("/sports-schedules/api/query?dimensions=league&limit=10000")
        self.assertEqual(r.status_code, 400)
        data = r.get_json()
        self.assertIn("error", data)

    def test_count_true_without_dimensions_returns_200(self):
        """count=1 with no dimensions is valid (single total count)."""
        with patch("app.projects.sports_schedules.routes.DoltHubClient") as mock_dolt:
            mock_dolt.return_value.execute_sql.return_value = {"rows": [{"# Games": 42}]}
            r = self.client.get("/sports-schedules/api/query?count=1")
            self.assertEqual(r.status_code, 200)
            data = r.get_json()
            self.assertIn("rows", data)
            self.assertIn("sql", data)


class TestApiQuerySuccess(unittest.TestCase):
    """API returns 200 with rows and sql when DoltHub succeeds."""

    def setUp(self):
        self.app = _create_test_app()
        self.client = self.app.test_client()

    @patch("app.projects.sports_schedules.routes.DoltHubClient")
    def test_valid_query_returns_rows_and_sql(self, mock_dolt_cls):
        mock_dolt_cls.return_value.execute_sql.return_value = {
            "rows": [{"league": "NBA", "date": "2026-02-19"}],
        }
        r = self.client.get("/sports-schedules/api/query?dimensions=league,date&limit=5")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIn("rows", data)
        self.assertIn("sql", data)
        self.assertEqual(len(data["rows"]), 1)
        self.assertEqual(data["rows"][0]["league"], "NBA")
        self.assertIn("SELECT", data["sql"])
        self.assertIn("league", data["sql"])

    @patch("app.projects.sports_schedules.routes.DoltHubClient")
    def test_empty_results_returns_200(self, mock_dolt_cls):
        mock_dolt_cls.return_value.execute_sql.return_value = {"rows": []}
        r = self.client.get("/sports-schedules/api/query?dimensions=league&limit=5")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertEqual(data["rows"], [])
        self.assertIn("sql", data)

    @patch("app.projects.sports_schedules.routes.DoltHubClient")
    def test_filters_passed_to_query(self, mock_dolt_cls):
        mock_dolt_cls.return_value.execute_sql.return_value = {"rows": []}
        r = self.client.get(
            "/sports-schedules/api/query"
            "?dimensions=league,date&sport=basketball&league=NBA&limit=5"
        )
        self.assertEqual(r.status_code, 200)
        call_args = mock_dolt_cls.return_value.execute_sql.call_args[0][0]
        self.assertIn("NBA", call_args)
        self.assertIn("basketball", call_args)


class TestApiQueryDoltHubError(unittest.TestCase):
    """API returns 500 when DoltHub fails."""

    def setUp(self):
        self.app = _create_test_app()
        self.client = self.app.test_client()

    @patch("app.projects.sports_schedules.routes.DoltHubClient")
    def test_dolthub_error_returns_500(self, mock_dolt_cls):
        mock_dolt_cls.return_value.execute_sql.return_value = {"error": "API token missing"}
        r = self.client.get("/sports-schedules/api/query?dimensions=league&limit=5")
        self.assertEqual(r.status_code, 500)
        data = r.get_json()
        self.assertIn("error", data)
        self.assertIn("Unable to load data", data["error"])
