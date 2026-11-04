"""Public Kalshi market-data reads. No API key."""

import requests

BASE_URL = "https://external-api.kalshi.com/trade-api/v2"
_TIMEOUT = 15


class KalshiError(Exception):
    pass


def get_json(path, params=None):
    response = requests.get(
        f"{BASE_URL}{path}",
        params=params,
        timeout=_TIMEOUT,
        headers={"User-Agent": "gmich-election2026"},
    )
    if response.status_code != 200:
        raise KalshiError(f"Kalshi {response.status_code} for {path}")
    return response.json()


def get_event(event_ticker):
    return get_json(f"/events/{event_ticker}")


def get_markets(tickers):
    """Current quotes for known tickers. Chunked so the query string stays short."""
    markets = []
    for start in range(0, len(tickers), 25):
        chunk = tickers[start : start + 25]
        payload = get_json(
            "/markets",
            {"tickers": ",".join(chunk), "limit": len(chunk)},
        )
        markets.extend(payload.get("markets") or [])
    return markets
