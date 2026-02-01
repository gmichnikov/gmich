from datetime import datetime
import pytz

def calculate_american_odds_payout(wager, odds):
    """
    Calculate the potential payout for American odds.
    Positive odds (+150): Profit = wager * (odds / 100)
    Negative odds (-110): Profit = wager * (100 / abs(odds))
    Total Payout = Profit + Wager
    """
    if odds > 0:
        profit = wager * (odds / 100.0)
    else:
        profit = wager * (100.0 / abs(odds))
    
    return round(profit + wager, 2)

def format_odds_display(odds):
    """Format odds with a + prefix if positive."""
    if odds > 0:
        return f"+{odds}"
    return str(odds)

def format_currency(amount):
    """Format amount as $X.XX or -$X.XX for negative values."""
    if amount < 0:
        return f"-${abs(amount):,.2f}"
    return f"${amount:,.2f}"

def get_user_localized_time(utc_dt, user_timezone='UTC'):
    """Convert UTC datetime to user's localized timezone."""
    if not utc_dt:
        return None
    
    # Ensure utc_dt is aware of UTC
    if utc_dt.tzinfo is None:
        utc_dt = pytz.utc.localize(utc_dt)
        
    try:
        user_tz = pytz.timezone(user_timezone)
        return utc_dt.astimezone(user_tz)
    except Exception:
        return utc_dt # Fallback to UTC if timezone is invalid
