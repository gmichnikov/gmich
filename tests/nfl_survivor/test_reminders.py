import unittest
from datetime import datetime
from types import SimpleNamespace

from app.projects.nfl_survivor.reminders import (
    already_sent_today,
    build_user_payload,
    classify_entry,
    format_pick_count_line,
    reminder_subject,
    should_send_pref,
)
from app.projects.nfl_survivor.utils import EASTERN, UTC


class TestClassifyEntry(unittest.TestCase):
    def test_alive_under_two_losses(self):
        self.assertEqual(classify_entry(0, None), "alive")
        self.assertEqual(classify_entry(1, None), "alive")

    def test_new_out_on_second_loss(self):
        self.assertEqual(classify_entry(2, None), "new_out")

    def test_skip_after_notice_sent(self):
        self.assertEqual(classify_entry(2, datetime(2026, 9, 15)), "skip")


class TestShouldSendPref(unittest.TestCase):
    def setUp(self):
        self.wednesday = EASTERN.localize(datetime(2026, 9, 16, 8, 0))

    def test_none_does_not_send(self):
        self.assertFalse(
            should_send_pref(None, 2, None, self.wednesday)
        )

    def test_matching_weekday_sends(self):
        self.assertTrue(should_send_pref(2, 2, None, self.wednesday))

    def test_wrong_weekday_skips(self):
        self.assertFalse(should_send_pref(6, 2, None, self.wednesday))

    def test_already_sent_today_skips(self):
        sent_at = datetime(2026, 9, 16, 11, 0)  # naive UTC = 7am ET
        self.assertTrue(already_sent_today(sent_at, self.wednesday))
        self.assertFalse(should_send_pref(2, 2, sent_at, self.wednesday))

    def test_sent_yesterday_still_sends(self):
        sent_at = UTC.localize(datetime(2026, 9, 15, 12, 0))
        self.assertFalse(already_sent_today(sent_at, self.wednesday))
        self.assertTrue(should_send_pref(2, 2, sent_at, self.wednesday))

    def test_force_ignores_weekday_and_last_sent(self):
        sent_at = datetime(2026, 9, 16, 11, 0)
        self.assertTrue(
            should_send_pref(None, 2, sent_at, self.wednesday, force=True)
        )


class TestPayloadAndSubject(unittest.TestCase):
    def _season(self):
        return SimpleNamespace(name="2026 Survivor", max_weeks=18)

    def _entry(self, **kwargs):
        defaults = {
            "id": 1,
            "user_id": 9,
            "display_name": "Greg #1",
            "elimination_email_sent_at": None,
        }
        defaults.update(kwargs)
        return SimpleNamespace(**defaults)

    def _data(self, **overrides):
        data = {
            "current_week": 8,
            "last_week": 7,
            "last_week_revealed": True,
            "participants": [],
            "picks_by_entry": {},
            "wrong_counts": {},
            "team_lookup": {"KC": "Chiefs", "BUF": "Bills"},
            "matchup_by_name": {"Chiefs": "Chargers"},
            "result_by_team": {"KC": "win"},
            "alive_count": 14,
            "total_count": 40,
            "last_week_pick_counts": [("Chiefs", 11), ("Bills", 6)],
            "last_week_results_pending": False,
            "pick_week_open": True,
        }
        data.update(overrides)
        return data

    def test_nothing_to_send_without_entries(self):
        user = SimpleNamespace(id=9)
        self.assertIsNone(build_user_payload(self._season(), user, self._data()))

    def test_skips_already_notified_eliminated_entry(self):
        entry = self._entry(elimination_email_sent_at=datetime(2026, 9, 10))
        user = SimpleNamespace(id=9)
        data = self._data(
            participants=[entry],
            wrong_counts={1: 2},
        )
        self.assertIsNone(build_user_payload(self._season(), user, data))

    def test_alive_entry_needs_pick_and_recap(self):
        entry = self._entry()
        last_pick = SimpleNamespace(week=7, team="KC", is_correct=True)
        user = SimpleNamespace(id=9)
        data = self._data(
            participants=[entry],
            picks_by_entry={1: [last_pick]},
            wrong_counts={1: 0},
        )
        payload = build_user_payload(self._season(), user, data)
        self.assertEqual(payload["alive_count"], 14)
        self.assertTrue(payload["needs_any_pick"])
        self.assertEqual(payload["entries"][0]["last_week_team"], "Chiefs")
        self.assertEqual(payload["entries"][0]["last_week_outcome"], "Beat Chargers")
        self.assertTrue(payload["entries"][0]["needs_pick"])
        self.assertEqual(reminder_subject(payload), "NFL Survivor — Week 8 update")

    def test_new_out_only_uses_out_subject(self):
        entry = self._entry()
        user = SimpleNamespace(id=9)
        data = self._data(
            participants=[entry],
            wrong_counts={1: 2},
            pick_week_open=True,
        )
        payload = build_user_payload(self._season(), user, data)
        self.assertEqual(payload["entries"][0]["status"], "eliminated")
        self.assertEqual(payload["eliminated_entry_ids"], [1])
        self.assertFalse(payload["needs_any_pick"])
        self.assertEqual(reminder_subject(payload), "NFL Survivor — an entry is out")

    def test_mixed_entries_keep_week_subject(self):
        alive = self._entry(id=1, display_name="A")
        out = self._entry(id=2, display_name="B")
        user = SimpleNamespace(id=9)
        data = self._data(
            participants=[alive, out],
            picks_by_entry={
                1: [SimpleNamespace(week=8, team="BUF", is_correct=None)],
            },
            wrong_counts={1: 0, 2: 2},
        )
        payload = build_user_payload(self._season(), user, data)
        statuses = {row["display_name"]: row["status"] for row in payload["entries"]}
        self.assertEqual(statuses["A"], "alive")
        self.assertEqual(statuses["B"], "eliminated")
        self.assertFalse(payload["needs_any_pick"])
        self.assertEqual(reminder_subject(payload), "NFL Survivor — Week 8 update")

    def test_pick_count_line(self):
        self.assertEqual(
            format_pick_count_line([("Chiefs", 11), ("Bills", 6)]),
            "Chiefs (11), Bills (6)",
        )
        self.assertEqual(format_pick_count_line([]), "")
