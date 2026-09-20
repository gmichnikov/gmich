import unittest
from datetime import datetime
from types import SimpleNamespace

from app.projects.nfl_survivor.sunday_nudge import (
    collect_nudge_recipients,
    is_sunday,
    missing_entry_names,
    sunday_nudge_already_logged,
    sunday_nudge_log_prefix,
    sunday_nudge_subject,
    sunday_nudge_text,
)
from app.projects.nfl_survivor.utils import EASTERN


def _entry(**kwargs):
    defaults = {"id": 1, "user_id": 9, "display_name": "Greg #1"}
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _user(**kwargs):
    defaults = {
        "id": 9,
        "email": "greg@example.com",
        "email_verified": True,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _pick(week, is_correct=None):
    return SimpleNamespace(week=week, is_correct=is_correct)


class TestSundayGuards(unittest.TestCase):
    def test_sunday_is_weekday_6(self):
        sunday = EASTERN.localize(datetime(2026, 9, 20, 12, 0))
        monday = EASTERN.localize(datetime(2026, 9, 21, 12, 0))
        self.assertTrue(is_sunday(sunday))
        self.assertFalse(is_sunday(monday))

    def test_log_prefix_matches_week_and_season(self):
        prefix = sunday_nudge_log_prefix("2026 Survivor", 3)
        self.assertTrue(
            sunday_nudge_already_logged(
                [f"{prefix}: sent to 2 people (a@x.com, b@x.com)"],
                "2026 Survivor",
                3,
            )
        )
        self.assertFalse(
            sunday_nudge_already_logged(
                [f"{prefix}: sent to 2 people"],
                "2026 Survivor",
                4,
            )
        )


class TestMissingEntries(unittest.TestCase):
    def test_alive_without_pick_is_missing(self):
        entry = _entry()
        names = missing_entry_names(
            [entry], {1: []}, {1: 0}, current_week=3, pick_week_open=True
        )
        self.assertEqual(names, ["Greg #1"])

    def test_already_picked_is_not_missing(self):
        entry = _entry()
        names = missing_entry_names(
            [entry],
            {1: [_pick(3)]},
            {1: 0},
            current_week=3,
            pick_week_open=True,
        )
        self.assertEqual(names, [])

    def test_eliminated_is_not_missing(self):
        entry = _entry()
        names = missing_entry_names(
            [entry], {1: [_pick(1, False), _pick(2, False)]}, {1: 2},
            current_week=3,
            pick_week_open=True,
        )
        self.assertEqual(names, [])

    def test_closed_season_is_not_missing(self):
        entry = _entry()
        names = missing_entry_names(
            [entry], {1: []}, {1: 0}, current_week=19, pick_week_open=False
        )
        self.assertEqual(names, [])


class TestCollectRecipients(unittest.TestCase):
    def test_one_email_per_user_lists_only_missing_when_multi_entry(self):
        entries = [
            _entry(id=1, user_id=9, display_name="Greg #1"),
            _entry(id=2, user_id=9, display_name="Greg #2"),
        ]
        picks = {1: [_pick(3)], 2: []}
        users = {9: _user()}
        recipients, skipped = collect_nudge_recipients(
            entries, picks, {1: 0, 2: 0}, 3, True, users
        )
        self.assertEqual(skipped, 0)
        self.assertEqual(len(recipients), 1)
        self.assertEqual(recipients[0]["missing_names"], ["Greg #2"])
        self.assertTrue(recipients[0]["list_entries"])

    def test_single_entry_does_not_flag_list(self):
        entries = [_entry()]
        users = {9: _user()}
        recipients, _skipped = collect_nudge_recipients(
            entries, {1: []}, {1: 0}, 3, True, users
        )
        self.assertEqual(recipients[0]["missing_names"], ["Greg #1"])
        self.assertFalse(recipients[0]["list_entries"])

    def test_skips_unverified(self):
        entries = [_entry()]
        users = {9: _user(email_verified=False)}
        recipients, skipped = collect_nudge_recipients(
            entries, {1: []}, {1: 0}, 3, True, users
        )
        self.assertEqual(recipients, [])
        self.assertEqual(skipped, 1)

    def test_skips_users_who_already_picked(self):
        entries = [_entry()]
        users = {9: _user()}
        recipients, skipped = collect_nudge_recipients(
            entries, {1: [_pick(3)]}, {1: 0}, 3, True, users
        )
        self.assertEqual(recipients, [])
        self.assertEqual(skipped, 0)


class TestNudgeCopy(unittest.TestCase):
    def test_subject(self):
        self.assertEqual(
            sunday_nudge_subject(3),
            "NFL Survivor — you still need a Week 3 pick",
        )

    def test_single_entry_omits_names(self):
        text = sunday_nudge_text(3, "https://x/pick", ["Greg #1"], False)
        self.assertIn("week 3", text)
        self.assertIn("https://x/pick", text)
        self.assertNotIn("Greg #1", text)
        self.assertNotIn("Still need a pick", text)

    def test_multi_entry_lists_missing_names(self):
        text = sunday_nudge_text(3, "https://x/pick", ["Greg #2"], True)
        self.assertIn("Still need a pick:", text)
        self.assertIn("- Greg #2", text)
