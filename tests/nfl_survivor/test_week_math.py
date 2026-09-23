import unittest
from datetime import datetime
from types import SimpleNamespace

from app.projects.nfl_survivor.utils import (
    EASTERN,
    format_week_choice_label,
    get_week_date_range,
    get_week_pick_lock_time,
    get_week_picks_reveal_time,
    is_week_picks_revealed,
)


def _season(week_2_start):
    return SimpleNamespace(week_2_start=week_2_start, max_weeks=18)


class TestWeekPicksReveal(unittest.TestCase):
    def test_week1_reveals_sunday_830_before_tuesday_rollover(self):
        week_2_start = EASTERN.localize(datetime(2026, 9, 15, 0, 0))
        season = _season(week_2_start)
        reveal = get_week_picks_reveal_time(season, 1)
        self.assertEqual(reveal, EASTERN.localize(datetime(2026, 9, 13, 20, 30)))
        self.assertLess(reveal, get_week_pick_lock_time(season, 1))

    def test_later_weeks_are_the_following_sundays(self):
        week_2_start = EASTERN.localize(datetime(2026, 9, 15, 0, 0))
        season = _season(week_2_start)
        self.assertEqual(
            get_week_picks_reveal_time(season, 2),
            EASTERN.localize(datetime(2026, 9, 20, 20, 30)),
        )

    def test_reveal_does_not_depend_on_exact_tuesday_clock_time(self):
        week_2_start = EASTERN.localize(datetime(2026, 9, 15, 10, 0))
        season = _season(week_2_start)
        self.assertEqual(
            get_week_picks_reveal_time(season, 1),
            EASTERN.localize(datetime(2026, 9, 13, 20, 30)),
        )

    def test_is_revealed_at_and_after_830(self):
        week_2_start = EASTERN.localize(datetime(2026, 9, 15, 0, 0))
        season = _season(week_2_start)
        just_before = EASTERN.localize(datetime(2026, 9, 13, 20, 29))
        at_reveal = EASTERN.localize(datetime(2026, 9, 13, 20, 30))
        self.assertFalse(is_week_picks_revealed(season, 1, when=just_before))
        self.assertTrue(is_week_picks_revealed(season, 1, when=at_reveal))
        self.assertFalse(is_week_picks_revealed(season, 2, when=at_reveal))


class TestWeekDateRange(unittest.TestCase):
    def test_week1_is_tuesday_through_monday_before_week2_start(self):
        week_2_start = EASTERN.localize(datetime(2026, 9, 15, 0, 0))
        season = _season(week_2_start)
        tuesday, monday = get_week_date_range(season, 1)
        self.assertEqual(tuesday.isoformat(), "2026-09-08")
        self.assertEqual(monday.isoformat(), "2026-09-14")
        self.assertEqual(
            format_week_choice_label(season, 1),
            "Week 1 · Tue Sep 8 – Mon Sep 14",
        )

    def test_later_weeks_shift_by_seven_days(self):
        week_2_start = EASTERN.localize(datetime(2026, 9, 15, 10, 0))
        season = _season(week_2_start)
        tuesday, monday = get_week_date_range(season, 2)
        self.assertEqual(tuesday.isoformat(), "2026-09-15")
        self.assertEqual(monday.isoformat(), "2026-09-21")
