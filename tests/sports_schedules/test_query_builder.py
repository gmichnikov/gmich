"""
Unit tests for Sports Schedules query builder.

Run (with venv activated):
  python -m unittest tests.sports_schedules.test_query_builder -v
  pytest tests/sports_schedules/ -v
"""
import unittest

from app.projects.sports_schedules.core.query_builder import build_sql


class TestBuildSqlValidation(unittest.TestCase):
    """Run requirement and validation tests."""

    def test_no_dimensions_no_count_returns_error(self):
        sql, err = build_sql({"dimensions": [], "count": 0})
        self.assertIsNone(sql)
        self.assertIn("Select at least one dimension", err)

    def test_empty_dimensions_string_no_count_returns_error(self):
        sql, err = build_sql({"dimensions": "", "count": 0})
        self.assertIsNone(sql)
        self.assertIsNotNone(err)

    def test_invalid_row_limit_returns_error(self):
        sql, err = build_sql({"dimensions": ["league"], "limit": 10000})
        self.assertIsNone(sql)
        self.assertIn("1 and 5000", err)

    def test_zero_row_limit_returns_error(self):
        sql, err = build_sql({"dimensions": ["league"], "limit": 0})
        self.assertIsNone(sql)
        self.assertIsNotNone(err)

    def test_date_range_start_after_end_returns_error(self):
        sql, err = build_sql({
            "dimensions": ["date"],
            "date_mode": "range",
            "date_start": "2026-02-28",
            "date_end": "2026-02-01",
        })
        self.assertIsNone(sql)
        self.assertIn("before or equal", err)

    def test_last_n_days_zero_returns_error(self):
        sql, err = build_sql({
            "dimensions": ["league"],
            "date_mode": "last_n",
            "date_n": 0,
            "anchor_date": "2026-02-15",
        })
        self.assertIsNone(sql)
        self.assertIn("greater than 0", err)


class TestBuildSqlBasic(unittest.TestCase):
    """Basic SELECT and count tests."""

    def test_simple_select_dimensions(self):
        sql, err = build_sql({"dimensions": ["league", "date"], "limit": 10})
        self.assertIsNone(err)
        self.assertIn("SELECT", sql)
        self.assertIn("`league`", sql)
        self.assertIn("`date`", sql)
        self.assertIn("LIMIT 10", sql)
        self.assertIn("combined-schedule", sql)

    def test_dimensions_from_comma_separated_string(self):
        sql, err = build_sql({"dimensions": "league,date", "limit": 5})
        self.assertIsNone(err)
        self.assertIn("`league`", sql)
        self.assertIn("`date`", sql)

    def test_count_with_dimensions_has_group_by(self):
        sql, err = build_sql({"dimensions": ["league"], "count": 1})
        self.assertIsNone(err)
        self.assertIn("COUNT(*)", sql)
        self.assertIn("GROUP BY", sql)
        self.assertIn("# Games", sql)

    def test_count_no_dimensions_single_total(self):
        sql, err = build_sql({"dimensions": [], "count": 1})
        self.assertIsNone(err)
        self.assertIn("COUNT(*)", sql)
        self.assertNotIn("GROUP BY", sql)


class TestBuildSqlDateModes(unittest.TestCase):
    """Date filter tests."""

    def test_exact_date(self):
        sql, err = build_sql({
            "dimensions": ["date"],
            "date_mode": "exact",
            "date_exact": "2026-02-19",
        })
        self.assertIsNone(err)
        self.assertIn("2026-02-19", sql)

    def test_date_range(self):
        sql, err = build_sql({
            "dimensions": ["date"],
            "date_mode": "range",
            "date_start": "2026-02-01",
            "date_end": "2026-02-28",
        })
        self.assertIsNone(err)
        self.assertIn("BETWEEN", sql)
        self.assertIn("2026-02-01", sql)
        self.assertIn("2026-02-28", sql)

    def test_year_only(self):
        sql, err = build_sql({
            "dimensions": ["date"],
            "date_mode": "year",
            "date_year": "2026",
        })
        self.assertIsNone(err)
        self.assertIn("2026-01-01", sql)
        self.assertIn("2026-12-31", sql)

    def test_last_n_days_with_anchor(self):
        sql, err = build_sql({
            "dimensions": ["date"],
            "date_mode": "last_n",
            "date_n": 7,
            "anchor_date": "2026-02-15",
        })
        self.assertIsNone(err)
        self.assertIn("BETWEEN", sql)
        self.assertIn("2026-02-09", sql)  # 7 days back from 15th
        self.assertIn("2026-02-15", sql)

    def test_next_n_days_with_anchor(self):
        sql, err = build_sql({
            "dimensions": ["date"],
            "date_mode": "next_n",
            "date_n": 14,
            "anchor_date": "2026-02-15",
        })
        self.assertIsNone(err)
        self.assertIn("2026-02-15", sql)
        self.assertIn("2026-02-28", sql)  # 14 days forward


class TestBuildSqlFilters(unittest.TestCase):
    """Filter tests including contains escaping."""

    def test_low_cardinality_filter(self):
        sql, err = build_sql({
            "dimensions": ["league"],
            "filters": {"league": ["NBA", "NHL"]},
        })
        self.assertIsNone(err)
        self.assertIn("NBA", sql)
        self.assertIn("NHL", sql)
        self.assertIn("IN", sql)

    def test_contains_filter_escapes_single_quote(self):
        sql, err = build_sql({
            "dimensions": ["home_team"],
            "filters": {"home_team": "O'Brien"},
        })
        self.assertIsNone(err)
        self.assertIn("O''Brien", sql)
        self.assertIn("LIKE", sql)

    def test_contains_filter_escapes_percent(self):
        sql, err = build_sql({
            "dimensions": ["home_team"],
            "filters": {"home_team": "100%"},
        })
        self.assertIsNone(err)
        self.assertIn("\\%", sql)

    def test_contains_filter_case_insensitive(self):
        sql, err = build_sql({
            "dimensions": ["home_team"],
            "filters": {"home_team": "Celtics"},
        })
        self.assertIsNone(err)
        self.assertIn("LOWER", sql)
        self.assertIn("LIKE", sql)

    def test_multiple_contains_filters_combined_with_and(self):
        sql, err = build_sql({
            "dimensions": ["home_team", "road_team"],
            "filters": {"home_team": "Celtics", "home_city": "Boston"},
        })
        self.assertIsNone(err)
        self.assertIn("Celtics", sql)
        self.assertIn("Boston", sql)
        self.assertIn("AND", sql)  # both conditions combined with AND


class TestBuildSqlGender(unittest.TestCase):
    """Gender is derived from league in SQL, not a stored column."""

    def test_gender_dimension_uses_case_expression(self):
        sql, err = build_sql({"dimensions": ["gender", "date"]})
        self.assertIsNone(err)
        self.assertIn("CASE WHEN `league` IN", sql)
        self.assertIn("AS `gender`", sql)
        self.assertIn("WNBA", sql)
        self.assertIn("NCAAW", sql)
        self.assertNotIn("SELECT `gender`", sql)

    def test_filter_women_uses_women_leagues(self):
        sql, err = build_sql({
            "dimensions": ["date"],
            "filters": {"gender": ["W"]},
        })
        self.assertIsNone(err)
        self.assertIn("`league` IN (", sql)
        self.assertIn("WNBA", sql)
        self.assertIn("NWSL", sql)
        self.assertNotIn("NOT IN", sql)

    def test_filter_men_excludes_women_leagues(self):
        sql, err = build_sql({
            "dimensions": ["date"],
            "filters": {"gender": ["M"]},
        })
        self.assertIsNone(err)
        self.assertIn("`league` NOT IN (", sql)

    def test_filter_both_genders_omits_league_condition(self):
        sql, err = build_sql({
            "dimensions": ["date"],
            "filters": {"gender": ["M", "W"]},
        })
        self.assertIsNone(err)
        self.assertNotIn("NOT IN", sql)
        # No standalone gender/league IN from the gender filter
        self.assertNotIn("`league` IN (", sql)

    def test_invalid_gender_ignored(self):
        sql, err = build_sql({
            "dimensions": ["date"],
            "filters": {"gender": ["X"]},
        })
        self.assertIsNone(err)
        self.assertNotIn("`league` IN (", sql)
        self.assertNotIn("`league` NOT IN (", sql)

    def test_count_groups_by_gender_expression(self):
        sql, err = build_sql({"dimensions": ["gender"], "count": 1})
        self.assertIsNone(err)
        self.assertIn("GROUP BY", sql)
        self.assertIn("CASE WHEN `league` IN", sql)
        self.assertIn("COUNT(*)", sql)


class TestBuildSqlSort(unittest.TestCase):
    """Sort order tests."""

    def test_default_sort_when_count(self):
        sql, err = build_sql({"dimensions": ["league"], "count": 1})
        self.assertIsNone(err)
        self.assertIn("ORDER BY", sql)
        self.assertIn("# Games", sql)

    def test_sort_column_and_dir(self):
        sql, err = build_sql({
            "dimensions": ["league", "date"],
            "sort_column": "date",
            "sort_dir": "desc",
        })
        self.assertIsNone(err)
        self.assertIn("ORDER BY", sql)
        self.assertIn("DESC", sql)

    def test_sort_by_count_when_count_on(self):
        sql, err = build_sql({
            "dimensions": ["league"],
            "count": 1,
            "sort_column": "# Games",
            "sort_dir": "desc",
        })
        self.assertIsNone(err)
        self.assertIn("ORDER BY", sql)
        self.assertIn("# Games", sql)
        self.assertIn("DESC", sql)
