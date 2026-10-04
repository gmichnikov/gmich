import unittest
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
