"""Travel Log utilities."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from timezonefinder import TimezoneFinder


def get_visited_date_default(lat, lng):
    """
    Get today's date in the timezone of the given coordinates.
    Used for defaulting visited_date when creating entries with lat/lng.
    """
    tf = TimezoneFinder()
    tz_name = tf.timezone_at(lat=lat, lng=lng)
    if tz_name:
        return datetime.now(ZoneInfo(tz_name)).date()
    return date.today()
