import unittest
from datetime import datetime
from types import SimpleNamespace

from app.projects.nfl_survivor.utils import (
    UTC,
    choose_last_game_auto_pick,
    resolve_last_game_sides,
    select_last_game_rows,
)

CHIEFS = "Kansas City Chiefs"
RAIDERS = "Las Vegas Raiders"
BILLS = "Buffalo Bills"
JETS = "New York Jets"
ID_TO_NAME = {
    "16": CHIEFS,
    "17": RAIDERS,
    "4": BILLS,
    "25": JETS,
}


def _game(team_id, kickoff, espn_event_id="100"):
    return SimpleNamespace(
        team_id=team_id, kickoff=kickoff, espn_event_id=espn_event_id
    )


def _spread(home, road, home_spread, road_spread):
    return SimpleNamespace(
        home_team=home,
        road_team=road,
        home_team_spread=home_spread,
        road_team_spread=road_spread,
    )


class TestSelectLastGame(unittest.TestCase):
    def test_uses_latest_kickoff(self):
        sunday = UTC.localize(datetime(2026, 9, 20, 17, 0))
        monday = UTC.localize(datetime(2026, 9, 22, 0, 15))
        rows, kickoff = select_last_game_rows(
            [
                _game("4", sunday, "sun"),
                _game("25", sunday, "sun"),
                _game("16", monday, "mnf"),
                _game("17", monday, "mnf"),
            ]
        )
        self.assertEqual(kickoff, monday)
        self.assertEqual({row.team_id for row in rows}, {"16", "17"})

    def test_same_kickoff_picks_lower_event_id(self):
        monday = UTC.localize(datetime(2026, 9, 22, 0, 15))
        rows, _kickoff = select_last_game_rows(
            [
                _game("16", monday, "200"),
                _game("17", monday, "200"),
                _game("4", monday, "100"),
                _game("25", monday, "100"),
            ]
        )
        self.assertEqual({row.team_id for row in rows}, {"4", "25"})


class TestResolveLastGameSides(unittest.TestCase):
    def setUp(self):
        self.kickoff = UTC.localize(datetime(2026, 9, 22, 0, 15))
        self.games = [
            _game("16", self.kickoff),
            _game("17", self.kickoff),
        ]

    def test_favorite_is_more_negative_spread(self):
        info = resolve_last_game_sides(
            self.games,
            [_spread(CHIEFS, RAIDERS, -9.5, 9.5)],
            ID_TO_NAME,
        )
        self.assertTrue(info["found"])
        self.assertEqual(info["favorite"], CHIEFS)
        self.assertEqual(info["underdog"], RAIDERS)

    def test_pickem_treats_home_as_favorite(self):
        info = resolve_last_game_sides(
            self.games,
            [_spread(CHIEFS, RAIDERS, 0, 0)],
            ID_TO_NAME,
        )
        self.assertEqual(info["favorite"], CHIEFS)
        self.assertEqual(info["underdog"], RAIDERS)

    def test_no_spread(self):
        info = resolve_last_game_sides(
            self.games, [_spread(BILLS, JETS, -3, 3)], ID_TO_NAME
        )
        self.assertFalse(info["found"])
        self.assertEqual(info["reason"], "no_spread")


class TestChooseLastGameAutoPick(unittest.TestCase):
    def setUp(self):
        self.last_game = {
            "found": True,
            "favorite": CHIEFS,
            "underdog": RAIDERS,
        }

    def test_unused_favorite(self):
        team, reason = choose_last_game_auto_pick([BILLS], self.last_game)
        self.assertEqual(team, CHIEFS)
        self.assertEqual(reason, "favorite")

    def test_used_favorite_gets_underdog(self):
        team, reason = choose_last_game_auto_pick([CHIEFS], self.last_game)
        self.assertEqual(team, RAIDERS)
        self.assertEqual(reason, "underdog")

    def test_both_used_gets_nobody(self):
        team, reason = choose_last_game_auto_pick(
            [CHIEFS, RAIDERS], self.last_game
        )
        self.assertIsNone(team)
        self.assertEqual(reason, "both_used")
