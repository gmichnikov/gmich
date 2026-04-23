"""Stocks module — yfinance quotes for user-chosen tickers."""

import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

logger = logging.getLogger(__name__)

_VALIDATE_TIMEOUT = 6  # seconds per ticker validation call


def validate_ticker(symbol: str) -> bool:
    """
    Check whether a ticker symbol is valid by fetching fast_info from yfinance.
    Returns True if a current price is available, False otherwise.
    Runs in a thread so we can enforce a hard timeout.
    """
    import yfinance as yf

    def _check():
        info = yf.Ticker(symbol).fast_info
        price = getattr(info, "last_price", None)
        return price is not None and price > 0

    with ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(_check)
        try:
            return future.result(timeout=_VALIDATE_TIMEOUT)
        except (FuturesTimeoutError, Exception) as exc:
            logger.warning("daily_email stocks: validate_ticker %r failed: %s", symbol, exc)
            return False


def _fetch_one(symbol: str) -> dict | None:
    """Fetch previous close and latest price for a single ticker."""
    import yfinance as yf

    try:
        hist = yf.Ticker(symbol).history(period="2d")
        if hist.empty or len(hist) < 1:
            return None

        latest = hist.iloc[-1]
        price = float(latest["Close"])

        if len(hist) >= 2:
            prev_close = float(hist.iloc[-2]["Close"])
        else:
            prev_close = price

        change = price - prev_close
        pct_change = (change / prev_close * 100) if prev_close else 0.0

        return {
            "symbol": symbol.upper(),
            "price": round(price, 2),
            "change": round(change, 2),
            "pct_change": round(pct_change, 2),
        }
    except Exception as exc:
        logger.warning("daily_email stocks: fetch failed for %r: %s", symbol, exc)
        return None


def fetch_stocks(symbols: list[str]) -> list[dict]:
    """
    Fetch quotes for up to 10 tickers in parallel.
    Returns a list of result dicts (successful fetches only; failed tickers omitted).
    """
    if not symbols:
        return []

    results = []
    with ThreadPoolExecutor(max_workers=min(len(symbols), 10)) as ex:
        futures = {ex.submit(_fetch_one, s): s for s in symbols[:10]}
        for future, symbol in futures.items():
            try:
                result = future.result(timeout=10)
                if result:
                    results.append(result)
            except Exception as exc:
                logger.warning("daily_email stocks: future failed for %r: %s", symbol, exc)

    # Preserve the original order
    order = {s.upper(): i for i, s in enumerate(symbols)}
    results.sort(key=lambda r: order.get(r["symbol"], 99))
    return results


def render_stocks_section(tickers: list) -> str | None:
    """
    Fetch quotes for the user's saved tickers and render an HTML card.

    tickers: list of DailyEmailStockTicker model instances.
    Returns HTML string or None if no data could be fetched.
    """
    if not tickers:
        return None

    symbols = [t.symbol for t in tickers]
    quotes = fetch_stocks(symbols)

    if not quotes:
        return None

    rows = ""
    for q in quotes:
        change = q["change"]
        pct = q["pct_change"]
        color = "#1a7d3f" if change >= 0 else "#c0392b"
        arrow = "▲" if change >= 0 else "▼"
        sign = "+" if change >= 0 else ""
        rows += (
            f'<tr>'
            f'<td style="padding:7px 12px;font-weight:700;font-size:14px;">{q["symbol"]}</td>'
            f'<td style="padding:7px 12px;font-size:14px;text-align:right;">${q["price"]:,.2f}</td>'
            f'<td style="padding:7px 12px;font-size:13px;text-align:right;color:{color};">'
            f'{arrow} {sign}{change:,.2f} ({sign}{pct:.2f}%)'
            f'</td>'
            f'</tr>'
        )

    table = (
        f'<table style="width:100%;border-collapse:collapse;">'
        f'<thead><tr style="background:#f8f8f8;font-size:11px;color:#888;text-transform:uppercase;">'
        f'<th style="padding:5px 12px;text-align:left;font-weight:600;">Ticker</th>'
        f'<th style="padding:5px 12px;text-align:right;font-weight:600;">Price</th>'
        f'<th style="padding:5px 12px;text-align:right;font-weight:600;">Day Change</th>'
        f'</tr></thead>'
        f'<tbody>{rows}</tbody>'
        f'</table>'
        f'<div style="padding:4px 12px 8px;font-size:10px;color:#bbb;">'
        f'Data from Yahoo Finance. Unofficial; may be delayed. Not financial advice.'
        f'</div>'
    )

    return (
        '<div class="de-module de-module-stocks">'
        '<div class="de-module-header">&#x1F4C8; Stocks</div>'
        + table
        + "</div>"
    )
