"""Choose which contracts to keep, and which number to chart."""

PARTY_ONLY_NAMES = {
    "democratic",
    "democrat",
    "democratic party",
    "republican",
    "republican party",
    "independent",
    "green",
    "green party",
    "libertarian",
}

LIVE_STATUSES = {"active", "open"}
CALLED_STATUSES = {"determined", "finalized"}


def display_price(bid, ask, last):
    """Midpoint of the Yes book. Last trade when a side is missing or the book is empty.

    A bid of 0 is a real quote. None means that side was absent. A settled
    contract comes back as a bid of 0 and an ask of 1, so the midpoint is 50
    even after the race is called. That empty book uses the last trade.
    """
    if bid is not None and ask is not None and not (bid == 0 and ask == 1):
        return (bid + ask) / 2
    for value in (last, bid, ask):
        if value is not None:
            return value
    return None


def market_is_called(status, result):
    """True once Kalshi has a result, or the contract is determined or finalized."""
    if (result or "").strip():
        return True
    return (status or "").lower() in CALLED_STATUSES


def parse_party(subtitle):
    """Pull a short party name out of a Kalshi subtitle, when it has one."""
    if not subtitle:
        return None
    text = subtitle.lower()
    if "independent" in text:
        return "Independent"
    if "green" in text:
        return "Green"
    if "libertarian" in text:
        return "Libertarian"
    if "democrat" in text:
        return "Democrat"
    if "republican" in text:
        return "Republican"
    return None


def _as_float(value):
    if value is None or value == "":
        return None
    return float(value)


def _candidate_name(market):
    name = (market.get("yes_sub_title") or "").strip()
    return name or None


def _is_person(name):
    return name is not None and name.lower() not in PARTY_ONLY_NAMES


def select_markets(markets, min_price=0.05, keep_top=2):
    """Keep live person-contracts: the top contenders, plus anyone at min_price.

    Drops party-only lines and long-shot names that share an event with the
    real field. Ranking uses the same price the chart will draw.
    """
    people = []
    for market in markets:
        status = (market.get("status") or "").lower()
        if status not in LIVE_STATUSES:
            continue
        name = _candidate_name(market)
        if not _is_person(name):
            continue
        price = display_price(
            _as_float(market.get("yes_bid_dollars")),
            _as_float(market.get("yes_ask_dollars")),
            _as_float(market.get("last_price_dollars")),
        )
        people.append((price if price is not None else -1, market))

    people.sort(key=lambda item: item[0], reverse=True)
    chosen = []
    for index, (price, market) in enumerate(people):
        if index < keep_top or price >= min_price:
            chosen.append(market)
    return chosen
