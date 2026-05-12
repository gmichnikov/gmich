from datetime import date, timedelta

def get_summer_2026_mondays():
    """
    Returns a list of date objects for Mondays in Summer 2026 (NJ window).
    Typically June 22 through August 31.
    """
    mondays = []
    # Start: Monday, June 22, 2026
    current = date(2026, 6, 22)
    # End: Monday, August 31, 2026
    end_date = date(2026, 8, 31)
    
    while current <= end_date:
        mondays.append(current)
        current += timedelta(days=7)
        
    return mondays

def get_week_range(monday_date):
    """
    Returns (start, end) for a Monday-Sunday range.
    """
    return monday_date, monday_date + timedelta(days=6)
