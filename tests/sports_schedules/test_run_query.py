"""
Unit tests for the sports schedule query runner.

Run:
  python -m unittest tests.sports_schedules.test_run_query -v
"""
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

from app.projects.sports_schedules.core.distance_prepare import DistancePrepareResult
from app.projects.sports_schedules.core.geocode import (
    GeocodeBudgetExceeded,
    filter_rows_by_distance,
)
from app.projects.sports_schedules.core.run_query import (
    ScheduleQueryError,
    run_schedule_query,
)


class _FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        # Monday 00:30 UTC is still Sunday evening in New York.
        base = datetime(2026, 11, 9, 0, 30, tzinfo=timezone.utc)
        if tz is None:
            return base
        return base.astimezone(tz)


class _Dolt:
    def __init__(self, rows=None, error=None):
        self.rows = rows if rows is not None else []
        self.error = error
        self.sql = None
        self.calls = 0

    def execute_sql(self, sql):
        self.calls += 1
        self.sql = sql
        if self.error is not None:
            return {"error": self.error}
        return {"rows": self.rows}


def _patch_dolt(dolt):
    return patch(
        "app.projects.sports_schedules.core.run_query.DoltHubClient",
        return_value=dolt,
    )


def _weekend_nj():
    return {
        "dimensions": ["date", "time", "home_team", "road_team"],
        "filters": {"home_state": ["NJ"]},
        "date_mode": "this_weekend",
    }


class TestRunScheduleQuery(unittest.TestCase):
    def test_nj_this_weekend_uses_eastern_sunday(self):
        dolt = _Dolt(rows=[{"date": "2026-11-07", "home_team": "Devils", "road_team": "Rangers"}])
        with patch("app.projects.sports_schedules.core.run_query.datetime", _FrozenDateTime):
            with _patch_dolt(dolt):
                result = run_schedule_query(_weekend_nj())
        self.assertIn("`home_state` IN ('NJ')", result.sql)
        self.assertIn("BETWEEN '2026-11-06' AND '2026-11-08'", result.sql)
        self.assertNotIn("2026-11-13", result.sql)
        self.assertEqual(result.date_range_used, {"start": "2026-11-06", "end": "2026-11-08"})
        self.assertEqual(result.applied["filters"]["home_state"], ["NJ"])

    def test_massachusetts_normalizes_and_unknown_league_does_not_query(self):
        dolt = _Dolt()
        with _patch_dolt(dolt):
            result = run_schedule_query({
                "date_mode": "today",
                "filters": {"home_state": ["Massachusetts"]},
                "dimensions": ["date"],
            })
        self.assertIn("`home_state` IN ('MA')", result.sql)
        self.assertEqual(dolt.calls, 1)

        dolt_again = _Dolt()
        with _patch_dolt(dolt_again):
            with self.assertRaises(ScheduleQueryError) as caught:
                run_schedule_query({
                    "date_mode": "today",
                    "filters": {"league": ["NOTALEAGUE"]},
                    "dimensions": ["date"],
                })
        self.assertIn("NOTALEAGUE", str(caught.exception))
        self.assertEqual(dolt_again.calls, 0)

    def test_either_team_matchup_and_three_teams_rejected(self):
        dolt = _Dolt()
        with _patch_dolt(dolt):
            with self.assertRaises(ScheduleQueryError) as caught:
                run_schedule_query({
                    "date_mode": "today",
                    "filters": {"either_team": ["Celtics", "Knicks", "Lakers"]},
                    "dimensions": ["date"],
                })
        self.assertIn("play each other", str(caught.exception))
        self.assertEqual(dolt.calls, 0)

        with _patch_dolt(dolt):
            result = run_schedule_query({
                "date_mode": "today",
                "filters": {"either_team": ["Celtics", "Knicks"]},
                "dimensions": ["date"],
            })
        self.assertIn("Celtics", result.sql)
        self.assertIn("Knicks", result.sql)
        self.assertGreaterEqual(result.sql.count("LIKE"), 4)
        self.assertIn(" AND ", result.sql)

    def test_womens_gender_contradicts_nba(self):
        dolt = _Dolt()
        with _patch_dolt(dolt):
            with self.assertRaises(ScheduleQueryError) as caught:
                run_schedule_query({
                    "date_mode": "today",
                    "filters": {"gender": ["W"], "league": ["NBA"]},
                    "dimensions": ["date"],
                })
        self.assertIn("NBA", str(caught.exception))
        self.assertEqual(dolt.calls, 0)

    def test_missing_date_mode_does_not_query(self):
        dolt = _Dolt()
        with _patch_dolt(dolt):
            with self.assertRaises(ScheduleQueryError) as caught:
                run_schedule_query({"dimensions": ["date"], "filters": {"home_state": ["NJ"]}})
        self.assertIn("date_mode", str(caught.exception))
        self.assertEqual(dolt.calls, 0)

    def test_limit_clamp_and_exact_truncation(self):
        wide = _Dolt(rows=[{"date": "2026-11-08"}] * 501)
        with patch("app.projects.sports_schedules.core.run_query.datetime", _FrozenDateTime):
            with _patch_dolt(wide):
                capped = run_schedule_query({
                    "date_mode": "today",
                    "dimensions": ["date"],
                    "limit": 5000,
                })
        self.assertEqual(capped.applied["limit"], 500)
        self.assertIn("LIMIT 501", capped.sql)
        self.assertTrue(capped.truncated)
        self.assertEqual(capped.row_count, 500)

        exact = _Dolt(rows=[{"date": "2026-11-08"}] * 2)
        with patch("app.projects.sports_schedules.core.run_query.datetime", _FrozenDateTime):
            with _patch_dolt(exact):
                full = run_schedule_query({
                    "date_mode": "today",
                    "dimensions": ["date"],
                    "limit": 2,
                })
        self.assertIn("LIMIT 3", exact.sql)
        self.assertFalse(full.truncated)
        self.assertEqual(full.row_count, 2)

        extra = _Dolt(rows=[{"date": "2026-11-08"}] * 3)
        with patch("app.projects.sports_schedules.core.run_query.datetime", _FrozenDateTime):
            with _patch_dolt(extra):
                page = run_schedule_query({
                    "date_mode": "today",
                    "dimensions": ["date"],
                    "limit": 2,
                })
        self.assertTrue(page.truncated)
        self.assertEqual(page.row_count, 2)

    def test_near_overfetches_then_slices(self):
        dolt = _Dolt(rows=[{"date": "2026-11-07", "home_city": "Newark", "home_state": "NJ"}] * 2)

        def _prepare(params):
            params["filters"].pop("near", None)
            params["filters"]["home_state"] = ["NJ", "NY"]
            params["include_international"] = True
            return DistancePrepareResult(True, (40.7, -74.0), 25.0, [], None, False)

        def _apply(rows, params, dpr, max_seconds=None):
            self.assertEqual(max_seconds, 15)
            return [{"date": str(i)} for i in range(12)]

        with patch("app.projects.sports_schedules.core.run_query.datetime", _FrozenDateTime):
            with patch("app.projects.sports_schedules.core.run_query.prepare_distance_filter", _prepare):
                with patch("app.projects.sports_schedules.core.run_query.apply_post_sql_distance", _apply):
                    with _patch_dolt(dolt):
                        result = run_schedule_query({
                            "date_mode": "today",
                            "dimensions": ["date"],
                            "limit": 10,
                            "filters": {"near": {"zip": "07928", "radius": 30}},
                        })
        self.assertIn("LIMIT 500", dolt.sql)
        self.assertNotIn("LIMIT 11", dolt.sql)
        self.assertIn("`home_state` IN ('NJ', 'NY')", dolt.sql)
        self.assertEqual(result.row_count, 10)
        self.assertTrue(result.truncated)
        self.assertEqual(result.applied["radius_used"], 25)

    def test_unknown_zip_is_returned_verbatim(self):
        dolt = _Dolt()

        def _prepare(params):
            return DistancePrepareResult(
                False, None, None, [], "Zip code '00000' not found.", False
            )

        with patch("app.projects.sports_schedules.core.run_query.prepare_distance_filter", _prepare):
            with _patch_dolt(dolt):
                with self.assertRaises(ScheduleQueryError) as caught:
                    run_schedule_query({
                        "date_mode": "today",
                        "dimensions": ["date"],
                        "filters": {"near": {"zip": "00000", "radius": 10}},
                    })
        self.assertEqual(str(caught.exception), "Zip code '00000' not found.")
        self.assertEqual(dolt.calls, 0)

    def test_geocode_budget_returns_no_rows(self):
        dolt = _Dolt(rows=[{"date": "2026-11-07", "home_city": "Newark", "home_state": "NJ"}])

        def _prepare(params):
            params["filters"].pop("near", None)
            params["filters"]["home_state"] = ["NJ"]
            return DistancePrepareResult(True, (40.7, -74.0), 50.0, [], None, False)

        def _apply(rows, params, dpr, max_seconds=None):
            raise GeocodeBudgetExceeded()

        with patch("app.projects.sports_schedules.core.run_query.prepare_distance_filter", _prepare):
            with patch("app.projects.sports_schedules.core.run_query.apply_post_sql_distance", _apply):
                with _patch_dolt(dolt):
                    with self.assertRaises(ScheduleQueryError) as caught:
                        run_schedule_query({
                            "date_mode": "today",
                            "dimensions": ["date"],
                            "filters": {"near": {"zip": "07928", "radius": 50}},
                        })
        message = str(caught.exception)
        self.assertIn("Try again shortly", message)
        self.assertNotIn("Newark", message)

    def test_count_plus_near_is_rejected(self):
        dolt = _Dolt()
        with _patch_dolt(dolt):
            with self.assertRaises(ScheduleQueryError) as caught:
                run_schedule_query({
                    "date_mode": "today",
                    "count": True,
                    "dimensions": ["league"],
                    "filters": {"near": {"zip": "07928", "radius": 50}},
                })
        self.assertIn("Distance counts", str(caught.exception))
        self.assertEqual(dolt.calls, 0)

    def test_dolthub_error_hides_the_upstream_message(self):
        secret = "https://secret.example/token"
        dolt = _Dolt(error=secret)
        with _patch_dolt(dolt):
            with self.assertRaises(ScheduleQueryError) as caught:
                run_schedule_query({"date_mode": "today", "dimensions": ["date"]})
        self.assertNotIn(secret, str(caught.exception))
        self.assertIn("Unable to load schedules", str(caught.exception))


class TestGeocodeBudget(unittest.TestCase):
    def test_second_uncached_city_is_not_looked_up_after_the_clock(self):
        looked_up = []

        def _coords(city, state):
            looked_up.append(city)
            return (40.7, -74.0)

        clock = iter([0.0, 20.0])

        rows = [
            {"home_city": "Newark", "home_state": "NJ"},
            {"home_city": "Albany", "home_state": "NY"},
        ]
        with patch(
            "app.projects.sports_schedules.core.geocode._nominatim_would_run",
            return_value=True,
        ):
            with patch(
                "app.projects.sports_schedules.core.geocode.citystate_to_coords",
                side_effect=_coords,
            ):
                with patch(
                    "app.projects.sports_schedules.core.geocode.time.perf_counter",
                    side_effect=lambda: next(clock),
                ):
                    with self.assertRaises(GeocodeBudgetExceeded):
                        filter_rows_by_distance(
                            rows, 40.7, -74.0, 50, max_seconds=15
                        )
        self.assertEqual(looked_up, ["Newark"])


class TestFrozenAnchor(unittest.TestCase):
    def test_sunday_evening_eastern_is_not_monday_utc(self):
        eastern = _FrozenDateTime.now(ZoneInfo("America/New_York"))
        self.assertEqual(eastern.date().isoformat(), "2026-11-08")
        self.assertEqual(eastern.weekday(), 6)
