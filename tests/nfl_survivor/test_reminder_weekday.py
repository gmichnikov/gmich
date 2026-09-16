import unittest

from app.projects.nfl_survivor.utils import (
    parse_reminder_weekday,
    reminder_weekday_choices,
)


class TestReminderWeekday(unittest.TestCase):
    def test_none_and_empty_mean_off(self):
        self.assertIsNone(parse_reminder_weekday(None))
        self.assertIsNone(parse_reminder_weekday(""))

    def test_wed_through_sun(self):
        self.assertEqual(parse_reminder_weekday("2"), 2)
        self.assertEqual(parse_reminder_weekday("6"), 6)
        self.assertEqual(parse_reminder_weekday(4), 4)

    def test_rejects_monday_and_garbage(self):
        with self.assertRaises(ValueError):
            parse_reminder_weekday("0")
        with self.assertRaises(ValueError):
            parse_reminder_weekday("1")
        with self.assertRaises(ValueError):
            parse_reminder_weekday("monday")

    def test_choices_start_with_none_and_skip_mon_tue(self):
        values = [value for value, _label in reminder_weekday_choices()]
        self.assertEqual(values[0], "")
        self.assertNotIn("0", values)
        self.assertNotIn("1", values)
        self.assertEqual(values[1:], ["2", "3", "4", "5", "6"])
