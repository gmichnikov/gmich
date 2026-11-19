import unittest
from datetime import date

from app.projects.been.parsing import format_when, parse_paste_line, parse_when, when_input_value
from app.projects.been.places import build_paste_preview, clean_place, normalize_feature
from app.projects.been.water import WATER_BODIES, WATER_BY_SLUG, clean_activity, clean_water_slug
from app.projects.been.parsing import VisitInputError


LISBON = {
    "type": "Feature",
    "properties": {
        "osm_type": "R",
        "osm_id": 5400890,
        "osm_key": "place",
        "osm_value": "city",
        "type": "city",
        "name": "Lisbon",
        "country": "Portugal",
        "countrycode": "PT",
    },
    "geometry": {"type": "Point", "coordinates": [-9.1365919, 38.7077507]},
}

TEXAS = {
    "type": "Feature",
    "properties": {
        "osm_type": "R",
        "osm_id": 114690,
        "osm_key": "place",
        "osm_value": "state",
        "type": "state",
        "name": "Texas",
        "country": "United States",
        "countrycode": "US",
    },
    "geometry": {"type": "Point", "coordinates": [-98.5456116, 31.2638905]},
}


class WhenTests(unittest.TestCase):
    def test_blank_is_unknown(self):
        self.assertEqual(parse_when("  "), (None, None))

    def test_year_month_and_day(self):
        self.assertEqual(parse_when("2019"), (date(2019, 1, 1), "year"))
        self.assertEqual(parse_when("2019-05"), (date(2019, 5, 1), "month"))
        self.assertEqual(parse_when("2019-5-2"), (date(2019, 5, 2), "day"))

    def test_rejects_impossible_dates(self):
        with self.assertRaises(VisitInputError):
            parse_when("2019-13")
        with self.assertRaises(VisitInputError):
            parse_when("May 2019")
        with self.assertRaises(VisitInputError):
            parse_when("1234")

    def test_round_trip_input(self):
        visited_on, precision = parse_when("2019-05-02")
        self.assertEqual(when_input_value(visited_on, precision), "2019-05-02")
        self.assertEqual(format_when(visited_on, "month"), "May 2019")
        self.assertEqual(format_when(date(2019, 1, 1), "year"), "2019")


class PasteLineTests(unittest.TestCase):
    def test_splits_a_trailing_date_only(self):
        self.assertEqual(parse_paste_line("Lisbon, 2019-05"), {"query": "Lisbon", "when": "2019-05"})
        self.assertEqual(
            parse_paste_line("Lisbon, Portugal, 2019"),
            {"query": "Lisbon, Portugal", "when": "2019"},
        )
        self.assertEqual(parse_paste_line("Washington, DC"), {"query": "Washington, DC", "when": ""})
        self.assertEqual(parse_paste_line("Lisbon, 2019-13"), {"query": "Lisbon", "when": "2019-13"})

    def test_skips_blanks_and_comments(self):
        self.assertIsNone(parse_paste_line("  "))
        self.assertIsNone(parse_paste_line("# skip"))


class PlaceTests(unittest.TestCase):
    def test_city_and_region_kinds(self):
        lisbon = normalize_feature(LISBON)
        texas = normalize_feature(TEXAS)
        self.assertEqual(lisbon["kind"], "spot")
        self.assertEqual(lisbon["country_code"], "PT")
        self.assertEqual(lisbon["subtitle"], "Portugal")
        self.assertEqual(texas["kind"], "region")
        self.assertEqual(texas["subtitle"], "United States")

    def test_clean_place_keeps_saved_fields(self):
        cleaned = clean_place(normalize_feature(LISBON))
        self.assertEqual(cleaned["name"], "Lisbon")
        self.assertEqual(cleaned["osm_id"], 5400890)
        self.assertNotIn("subtitle", cleaned)

    def test_clean_place_rejects_a_nameless_point(self):
        with self.assertRaises(VisitInputError):
            clean_place({"name": "", "lat": 1, "lng": 2})


class PastePreviewTests(unittest.TestCase):
    def test_uses_the_top_match_and_keeps_going_after_a_miss(self):
        def search(query, limit=1):
            if query == "Lisbon":
                return [normalize_feature(LISBON)]
            return []

        preview = build_paste_preview("Lisbon, 2019-05\nNowhereville\n", search)
        self.assertEqual(len(preview["rows"]), 2)
        self.assertEqual(preview["rows"][0]["place"]["name"], "Lisbon")
        self.assertEqual(preview["rows"][1]["error"], "No match")
        self.assertFalse(preview["truncated"])

    def test_stops_calling_search_when_it_fails(self):
        calls = {"n": 0}

        def search(query, limit=1):
            calls["n"] += 1
            raise RuntimeError("down")

        preview = build_paste_preview("Lisbon\nRome\n", search)
        self.assertEqual(calls["n"], 1)
        self.assertEqual(preview["rows"][1]["error"], "Place search is unavailable.")

    def test_bad_date_does_not_search(self):
        def search(query, limit=1):
            raise AssertionError("should not search")

        preview = build_paste_preview("Lisbon, 2019-13\n", search)
        self.assertIn("2019", preview["rows"][0]["error"])
        self.assertIsNone(preview["rows"][0]["place"])


class WaterTests(unittest.TestCase):
    def test_slugs_are_unique(self):
        slugs = [body["slug"] for body in WATER_BODIES]
        self.assertEqual(len(slugs), len(set(slugs)))
        self.assertIn("atlantic-ocean", WATER_BY_SLUG)
        self.assertIn("tyrrhenian-sea", WATER_BY_SLUG)

    def test_clean_water_and_activity(self):
        self.assertIsNone(clean_water_slug("  "))
        self.assertEqual(clean_activity("Swam"), "swam")
        with self.assertRaises(VisitInputError):
            clean_water_slug("the-puddle")
        with self.assertRaises(VisitInputError):
            clean_activity("skied")
