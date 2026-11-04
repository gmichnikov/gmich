"""Save Kalshi quotes at most once a minute, and shape them for the board."""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import requests
from sqlalchemy.exc import IntegrityError

from app import db
from app.projects.election2026.kalshi import KalshiError, get_event, get_markets
from app.projects.election2026.models import (
    Election2026Market,
    Election2026Price,
    Election2026Race,
)
from app.projects.election2026.selection import display_price, parse_party, select_markets
from app.projects.election2026.tracked import TRACKED_BY_EVENT, TRACKED_RACES

logger = logging.getLogger(__name__)

# Kalshi's own market list is cached for about 15 seconds. A minute is fresh
# enough for this board and keeps a room full of open tabs on one request.
STALE_AFTER = timedelta(seconds=60)


def _utcnow():
    return datetime.now(timezone.utc)


def _as_utc(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso(value):
    utc = _as_utc(value)
    if utc is None:
        return None
    return utc.isoformat()


def _parse_time(value):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _decimal(value):
    if value is None or value == "":
        return None
    return Decimal(str(value))


def _float(value):
    if value is None:
        return None
    return float(value)


def _last_observed_at():
    event_tickers = list(TRACKED_BY_EVENT)
    latest = (
        db.session.query(db.func.max(Election2026Price.observed_at))
        .join(Election2026Market)
        .join(Election2026Race)
        .filter(Election2026Race.event_ticker.in_(event_tickers))
        .scalar()
    )
    return _as_utc(latest)


def _is_stale(now):
    latest = _last_observed_at()
    if latest is None:
        return True
    return now - latest >= STALE_AFTER


def _sync_race(spec, payload):
    event = payload.get("event") or {}
    chosen = select_markets(payload.get("markets") or [])
    if not chosen:
        raise KalshiError(f"No candidate markets for {spec['label']}")

    race = Election2026Race.query.filter_by(event_ticker=spec["event_ticker"]).one_or_none()
    if race is None:
        race = Election2026Race(
            event_ticker=spec["event_ticker"],
            series_ticker=event.get("series_ticker") or spec["series_ticker"],
            title=event.get("title") or spec["label"],
            subtitle=event.get("sub_title") or None,
            category=event.get("category"),
            tags=event.get("tags"),
            mutually_exclusive=event.get("mutually_exclusive"),
            office=spec["office"],
            state=spec["state"],
        )
        db.session.add(race)
        db.session.flush()

    occurs_at = _parse_time(chosen[0].get("occurrence_datetime"))
    if occurs_at is not None and race.occurs_at is None:
        race.occurs_at = occurs_at

    existing = {market.ticker: market for market in race.markets}
    for raw in chosen:
        ticker = raw.get("ticker")
        if not ticker or ticker in existing:
            continue
        db.session.add(
            Election2026Market(
                race_id=race.id,
                ticker=ticker,
                title=(raw.get("title") or spec["label"])[:500],
                candidate_name=(raw.get("yes_sub_title") or "").strip() or None,
                party=parse_party(raw.get("subtitle")),
                status=raw.get("status"),
                result=raw.get("result") or None,
                rules_primary=raw.get("rules_primary"),
            )
        )
    db.session.commit()


def _sync_tracked_races():
    errors = []
    fetched = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {
            pool.submit(get_event, spec["event_ticker"]): spec for spec in TRACKED_RACES
        }
        for future in as_completed(futures):
            spec = futures[future]
            try:
                fetched.append((spec, future.result()))
            except (KalshiError, requests.RequestException) as exc:
                logger.warning("Election sync failed for %s: %s", spec["label"], exc)
                errors.append(f"{spec['label']} could not be loaded.")

    order = {spec["event_ticker"]: index for index, spec in enumerate(TRACKED_RACES)}
    fetched.sort(key=lambda item: order[item[0]["event_ticker"]])
    for spec, payload in fetched:
        try:
            _sync_race(spec, payload)
        except Exception:
            logger.exception("Election save failed for %s", spec["label"])
            db.session.rollback()
            errors.append(f"{spec['label']} could not be saved.")
    return errors


def _snapshot(now):
    markets = (
        Election2026Market.query.join(Election2026Race)
        .filter(Election2026Race.event_ticker.in_(list(TRACKED_BY_EVENT)))
        .all()
    )
    if not markets:
        return ["No races are saved yet, so there was nothing to price."]

    by_ticker = {market.ticker: market for market in markets}
    try:
        quotes = get_markets(list(by_ticker))
    except (KalshiError, requests.RequestException) as exc:
        logger.warning("Election price pull failed: %s", exc)
        db.session.rollback()
        return ["Kalshi did not return prices."]

    for raw in quotes:
        market = by_ticker.get(raw.get("ticker"))
        if market is None:
            continue
        if raw.get("status"):
            market.status = raw["status"]
        if raw.get("result"):
            market.result = raw["result"]
        if not market.party:
            market.party = parse_party(raw.get("subtitle"))
        price = Election2026Price(
            market_id=market.id,
            observed_at=now,
            yes_bid=_decimal(raw.get("yes_bid_dollars")),
            yes_ask=_decimal(raw.get("yes_ask_dollars")),
            last_price=_decimal(raw.get("last_price_dollars")),
            yes_bid_size=_decimal(raw.get("yes_bid_size_fp")),
            yes_ask_size=_decimal(raw.get("yes_ask_size_fp")),
            volume=_decimal(raw.get("volume_fp")),
            volume_24h=_decimal(raw.get("volume_24h_fp")),
            open_interest=_decimal(raw.get("open_interest_fp")),
        )
        try:
            with db.session.begin_nested():
                db.session.add(price)
        except IntegrityError:
            continue
    db.session.commit()
    return []


def refresh_if_stale():
    """Pull Kalshi only when the newest saved quote is at least a minute old.

    Returns whether this call talked to Kalshi, and any race that failed.
    """
    now = _utcnow()
    if not _is_stale(now):
        return {"pulled": False, "errors": []}
    errors = _sync_tracked_races()
    errors.extend(_snapshot(now))
    return {"pulled": True, "errors": errors}


def board_payload():
    """Tracked races, each candidate, and every saved price for the chart."""
    event_order = [race["event_ticker"] for race in TRACKED_RACES]
    races = (
        Election2026Race.query.filter(Election2026Race.event_ticker.in_(event_order))
        .all()
    )
    by_event = {race.event_ticker: race for race in races}
    markets = (
        Election2026Market.query.join(Election2026Race)
        .filter(Election2026Race.event_ticker.in_(event_order))
        .all()
    )
    prices = (
        Election2026Price.query.filter(
            Election2026Price.market_id.in_([market.id for market in markets] or [0])
        )
        .order_by(Election2026Price.observed_at)
        .all()
    )
    points_by_market = {}
    for price in prices:
        chart_price = display_price(
            _float(price.yes_bid),
            _float(price.yes_ask),
            _float(price.last_price),
        )
        if chart_price is None:
            continue
        points_by_market.setdefault(price.market_id, []).append(
            {"t": _iso(price.observed_at), "p": chart_price}
        )

    payload_races = []
    for event_ticker in event_order:
        race = by_event.get(event_ticker)
        spec = TRACKED_BY_EVENT[event_ticker]
        if race is None:
            continue
        candidates = [market for market in markets if market.race_id == race.id]
        candidates.sort(
            key=lambda market: (
                points_by_market.get(market.id) or [{"p": -1}]
            )[-1]["p"],
            reverse=True,
        )
        payload_races.append(
            {
                "event_ticker": race.event_ticker,
                "label": spec["label"],
                "office": race.office or spec["office"],
                "state": race.state or spec["state"],
                "candidates": [
                    {
                        "name": market.candidate_name or market.ticker,
                        "party": market.party,
                        "points": points_by_market.get(market.id, []),
                    }
                    for market in candidates
                ],
            }
        )

    return {
        "last_pulled_at": _iso(_last_observed_at()),
        "stale_after_seconds": int(STALE_AFTER.total_seconds()),
        "races": payload_races,
    }
