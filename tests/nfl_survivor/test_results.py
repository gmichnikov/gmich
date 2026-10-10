import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from app.projects.nfl_survivor.routes import _fetch_results_for_week
from app.projects.nfl_survivor.utils import is_pick_correct


class TestFetchResultsForWeek(unittest.TestCase):
    @patch("app.projects.nfl_survivor.routes.requests.get")
    def test_skips_uncompleted_games(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "week": {"teamsOnBye": [{"displayName": "Miami Dolphins"}]},
            "events": [
                {
                    "name": "Sunday Night Game",
                    "competitions": [
                        {
                            "status": {"type": {"completed": True}},
                            "competitors": [
                                {
                                    "team": {"displayName": "Kansas City Chiefs"},
                                    "winner": True,
                                },
                                {
                                    "team": {"displayName": "Denver Broncos"},
                                    "winner": False,
                                },
                            ],
                        }
                    ],
                },
                {
                    "name": "Monday Night Game",
                    "competitions": [
                        {
                            "status": {"type": {"completed": False}},
                            "competitors": [
                                {
                                    "team": {"displayName": "Buffalo Bills"},
                                },
                                {
                                    "team": {"displayName": "New York Jets"},
                                },
                            ],
                        }
                    ],
                },
            ],
        }
        mock_get.return_value = mock_response

        season = MagicMock(espn_season_year=2026)
        results = _fetch_results_for_week(season, 4)

        self.assertEqual(results.get("Miami Dolphins"), "did not play")
        self.assertEqual(results.get("Kansas City Chiefs"), "win")
        self.assertEqual(results.get("Denver Broncos"), "lose")
        # Monday night teams must not be in results
        self.assertNotIn("Buffalo Bills", results)
        self.assertNotIn("New York Jets", results)

    @patch("app.projects.nfl_survivor.routes.requests.get")
    def test_handles_ties(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "week": {"teamsOnBye": []},
            "events": [
                {
                    "competitions": [
                        {
                            "status": {"type": {"completed": True}},
                            "competitors": [
                                {
                                    "team": {"displayName": "Seattle Seahawks"},
                                    "winner": False,
                                },
                                {
                                    "team": {"displayName": "Arizona Cardinals"},
                                    "winner": False,
                                },
                            ],
                        }
                    ],
                }
            ],
        }
        mock_get.return_value = mock_response

        season = MagicMock(espn_season_year=2026)
        results = _fetch_results_for_week(season, 4)

        self.assertEqual(results.get("Seattle Seahawks"), "tie")
        self.assertEqual(results.get("Arizona Cardinals"), "tie")


class TestIsPickCorrect(unittest.TestCase):
    @patch("app.projects.nfl_survivor.utils.NflSurvivorWeeklyResult")
    def test_unrecorded_game_returns_none(self, mock_model):
        mock_model.query.filter_by.return_value.first.return_value = None
        self.assertIsNone(is_pick_correct(1, "BUF", 4))

    @patch("app.projects.nfl_survivor.utils.NflSurvivorWeeklyResult")
    def test_win_and_tie_return_true(self, mock_model):
        mock_model.query.filter_by.return_value.first.return_value = MagicMock(result="win")
        self.assertTrue(is_pick_correct(1, "KC", 4))

        mock_model.query.filter_by.return_value.first.return_value = MagicMock(result="tie")
        self.assertTrue(is_pick_correct(1, "SEA", 4))

    @patch("app.projects.nfl_survivor.utils.NflSurvivorWeeklyResult")
    def test_lose_returns_false(self, mock_model):
        mock_model.query.filter_by.return_value.first.return_value = MagicMock(result="lose")
        self.assertFalse(is_pick_correct(1, "DEN", 4))


class TestRecentlyFinishedWeek(unittest.TestCase):
    def setUp(self):
        from app.projects.nfl_survivor.utils import EASTERN
        # Season with week 2 starting on Tuesday, Sept 15, 2026
        self.season = MagicMock(
            week_2_start=EASTERN.localize(datetime(2026, 9, 15, 0, 0)),
            max_weeks=18,
        )

    def test_tuesday_5am_after_week_1_resolves_to_week_1(self):
        from app.projects.nfl_survivor.results import get_recently_finished_week
        from app.projects.nfl_survivor.utils import EASTERN

        tue_week1 = EASTERN.localize(datetime(2026, 9, 15, 5, 0))
        self.assertEqual(get_recently_finished_week(self.season, when=tue_week1), 1)

    def test_tuesday_5am_after_week_2_resolves_to_week_2(self):
        from app.projects.nfl_survivor.results import get_recently_finished_week
        from app.projects.nfl_survivor.utils import EASTERN

        tue_week2 = EASTERN.localize(datetime(2026, 9, 22, 5, 0))
        self.assertEqual(get_recently_finished_week(self.season, when=tue_week2), 2)

    def test_tuesday_5am_after_week_18_resolves_to_week_18(self):
        from app.projects.nfl_survivor.results import get_recently_finished_week
        from app.projects.nfl_survivor.utils import EASTERN

        # 17 weeks after Sept 15 is Jan 12, 2027
        tue_week18 = EASTERN.localize(datetime(2027, 1, 12, 5, 0))
        self.assertEqual(get_recently_finished_week(self.season, when=tue_week18), 18)

    def test_before_week_1_returns_none(self):
        from app.projects.nfl_survivor.results import get_recently_finished_week
        from app.projects.nfl_survivor.utils import EASTERN

        tue_preseason = EASTERN.localize(datetime(2026, 9, 8, 5, 0))
        self.assertIsNone(get_recently_finished_week(self.season, when=tue_preseason))

    def test_after_max_weeks_returns_none(self):
        from app.projects.nfl_survivor.results import get_recently_finished_week
        from app.projects.nfl_survivor.utils import EASTERN

        tue_postseason = EASTERN.localize(datetime(2027, 1, 19, 5, 0))
        self.assertIsNone(get_recently_finished_week(self.season, when=tue_postseason))

    def test_forced_run_on_other_weekdays_resolves_to_last_completed_week(self):
        from app.projects.nfl_survivor.results import get_recently_finished_week
        from app.projects.nfl_survivor.utils import EASTERN

        # Wednesday, Friday, Sunday between Week 1 and Week 2 games
        wed = EASTERN.localize(datetime(2026, 9, 16, 14, 0))
        fri = EASTERN.localize(datetime(2026, 9, 18, 10, 0))
        sun = EASTERN.localize(datetime(2026, 9, 20, 12, 0))
        self.assertEqual(get_recently_finished_week(self.season, when=wed), 1)
        self.assertEqual(get_recently_finished_week(self.season, when=fri), 1)
        self.assertEqual(get_recently_finished_week(self.season, when=sun), 1)


class TestTuesdayGuard(unittest.TestCase):
    def test_is_tuesday(self):
        from app.projects.nfl_survivor.results import is_tuesday
        from app.projects.nfl_survivor.utils import EASTERN

        tuesday = EASTERN.localize(datetime(2026, 9, 15, 5, 0))
        wednesday = EASTERN.localize(datetime(2026, 9, 16, 5, 0))
        sunday = EASTERN.localize(datetime(2026, 9, 20, 5, 0))
        self.assertTrue(is_tuesday(tuesday))
        self.assertFalse(is_tuesday(wednesday))
        self.assertFalse(is_tuesday(sunday))


class TestRunAutoUpdateResults(unittest.TestCase):
    @patch("app.projects.nfl_survivor.results.get_active_season")
    def test_skips_when_not_tuesday_and_not_forced(self, mock_season):
        from app.projects.nfl_survivor.results import run_auto_update_results
        from app.projects.nfl_survivor.utils import EASTERN

        wed = EASTERN.localize(datetime(2026, 9, 16, 5, 0))
        result = run_auto_update_results(force=False, now_eastern=wed)
        self.assertTrue(result.get("skipped_day"))
        mock_season.assert_not_called()

    @patch("app.projects.nfl_survivor.results.fetch_results_for_week")
    @patch("app.projects.nfl_survivor.results.update_weekly_results")
    @patch("app.projects.nfl_survivor.results.get_active_season")
    def test_runs_when_tuesday(self, mock_season, mock_update, mock_fetch):
        from app.projects.nfl_survivor.results import run_auto_update_results
        from app.projects.nfl_survivor.utils import EASTERN

        season = MagicMock(
            name="2026 Survivor",
            week_2_start=EASTERN.localize(datetime(2026, 9, 15, 0, 0)),
            max_weeks=18,
        )
        season.name = "2026 Survivor"
        mock_season.return_value = season
        mock_fetch.return_value = {"Kansas City Chiefs": "win"}
        mock_update.return_value = {"teams_updated": 32, "picks_updated": 10}

        tue = EASTERN.localize(datetime(2026, 9, 15, 5, 0))
        result = run_auto_update_results(force=False, now_eastern=tue)

        self.assertTrue(result.get("success"))
        self.assertEqual(result.get("week"), 1)
        mock_fetch.assert_called_once_with(season, 1)
        mock_update.assert_called_once_with(season, 1, {"Kansas City Chiefs": "win"}, source="cron")

    @patch("app.projects.nfl_survivor.results.fetch_results_for_week")
    @patch("app.projects.nfl_survivor.results.update_weekly_results")
    @patch("app.projects.nfl_survivor.results.get_active_season")
    def test_runs_when_forced_on_non_tuesday(self, mock_season, mock_update, mock_fetch):
        from app.projects.nfl_survivor.results import run_auto_update_results
        from app.projects.nfl_survivor.utils import EASTERN

        season = MagicMock(
            name="2026 Survivor",
            week_2_start=EASTERN.localize(datetime(2026, 9, 15, 0, 0)),
            max_weeks=18,
        )
        season.name = "2026 Survivor"
        mock_season.return_value = season
        mock_fetch.return_value = {"Kansas City Chiefs": "win"}
        mock_update.return_value = {"teams_updated": 32, "picks_updated": 10}

        wed = EASTERN.localize(datetime(2026, 9, 16, 12, 0))
        result = run_auto_update_results(force=True, now_eastern=wed)

        self.assertTrue(result.get("success"))
        self.assertEqual(result.get("week"), 1)
        mock_fetch.assert_called_once_with(season, 1)


class TestUpdateResultsCliCommand(unittest.TestCase):
    @patch("app.projects.nfl_survivor.results.run_auto_update_results")
    def test_cli_command_calls_runner(self, mock_run):
        from click.testing import CliRunner
        from app.projects.nfl_survivor.commands import nfl_survivor_cli

        mock_run.return_value = {"message": "Updated week 1 results: 32 teams"}
        runner = CliRunner()
        result = runner.invoke(nfl_survivor_cli, ["update-results", "--force"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Updated week 1 results", result.output)
        mock_run.assert_called_once_with(force=True)


