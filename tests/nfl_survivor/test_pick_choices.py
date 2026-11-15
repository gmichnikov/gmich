import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.projects.nfl_survivor.utils import teams_available_for_week

BEARS = ("6", "Chicago Bears")
CHIEFS = ("16", "Kansas City Chiefs")
RAIDERS = ("17", "Las Vegas Raiders")
PAIRS = [BEARS, CHIEFS, RAIDERS]


def _spread(home, road):
    return SimpleNamespace(home_team=home, road_team=road)


class TestTeamsAvailableForWeek(unittest.TestCase):
    def setUp(self):
        self.season = SimpleNamespace(id=1)
        self.pairs = patch(
            "app.projects.nfl_survivor.utils.load_nfl_teams_as_pairs",
            return_value=PAIRS,
        )
        self.locked = patch(
            "app.projects.nfl_survivor.utils.is_team_kickoff_locked",
            return_value=False,
        )
        self.games = patch("app.projects.nfl_survivor.utils.NflSurvivorGame")
        self.spreads = patch("app.projects.nfl_survivor.utils.NflSurvivorSpread")
        self.pairs.start()
        self.locked.start()
        self.game_model = self.games.start()
        self.spread_model = self.spreads.start()
        self.addCleanup(self.pairs.stop)
        self.addCleanup(self.locked.stop)
        self.addCleanup(self.games.stop)
        self.addCleanup(self.spreads.stop)

    def _set_games(self, team_ids):
        self.game_model.query.filter_by.return_value.all.return_value = [
            SimpleNamespace(team_id=team_id) for team_id in team_ids
        ]

    def _set_spreads(self, matchups):
        self.spread_model.query.filter_by.return_value.all.return_value = [
            _spread(home, road) for home, road in matchups
        ]

    def test_bye_team_is_omitted_when_schedule_is_loaded(self):
        self._set_games(["16", "17"])
        result = teams_available_for_week(self.season, 11, [])
        self.assertEqual(result, [CHIEFS, RAIDERS])
        self.spread_model.query.filter_by.assert_not_called()

    def test_bye_team_is_omitted_from_spreads_when_schedule_is_missing(self):
        self._set_games([])
        self._set_spreads([("Kansas City Chiefs", "Las Vegas Raiders")])
        result = teams_available_for_week(self.season, 11, [])
        self.assertEqual(result, [CHIEFS, RAIDERS])

    def test_all_teams_stay_when_week_has_no_schedule_or_spreads(self):
        self._set_games([])
        self._set_spreads([])
        result = teams_available_for_week(self.season, 14, [])
        self.assertEqual(result, PAIRS)

    def test_used_team_stays_out(self):
        self._set_games(["16", "17"])
        result = teams_available_for_week(self.season, 11, ["16"])
        self.assertEqual(result, [RAIDERS])
