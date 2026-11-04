import unittest

from app.projects.election2026.selection import display_price, parse_party, select_markets


def market(name, last, status="active", subtitle=None):
    return {
        "yes_sub_title": name,
        "last_price_dollars": last,
        "yes_bid_dollars": None,
        "yes_ask_dollars": None,
        "status": status,
        "subtitle": subtitle,
    }


class SelectionTest(unittest.TestCase):
    def test_midpoint_uses_both_sides(self):
        self.assertAlmostEqual(display_price(0.80, 0.84, 0.10), 0.82)

    def test_zero_bid_is_a_real_quote(self):
        self.assertEqual(display_price(0.0, 0.02, 0.01), 0.01)

    def test_last_trade_when_a_side_is_missing(self):
        self.assertEqual(display_price(None, 0.20, 0.15), 0.15)

    def test_party_from_subtitle(self):
        self.assertEqual(parse_party("Abdul El-Sayed:: Democrat"), "Democrat")
        self.assertEqual(parse_party("Republican party:: Republican party"), "Republican")
        self.assertIsNone(parse_party(None))

    def test_keeps_top_two_and_drops_longshots_and_party_lines(self):
        chosen = select_markets([
            market("Mary Peltola", "0.70", subtitle="Democratic party:: Democratic party"),
            market("Dan Sullivan", "0.30", subtitle="Republican party:: Republican party"),
            market("Gerald Heikes", "0.005"),
            market("Democratic party", "0.50"),
            market("Haley Stevens", "0.01", status="finalized"),
        ])
        names = [item["yes_sub_title"] for item in chosen]
        self.assertEqual(names, ["Mary Peltola", "Dan Sullivan"])


if __name__ == "__main__":
    unittest.main()
