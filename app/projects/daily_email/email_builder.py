"""Assemble the HTML digest email from per-module render results."""

import os
from datetime import datetime
from zoneinfo import ZoneInfo


def build_subject(user) -> str:
    user_tz = ZoneInfo(user.time_zone or "UTC")
    now_local = datetime.now(user_tz)
    return f"Your morning digest \u2014 {now_local.strftime('%A, %b %-d')}"


def build_digest_html(user, profile, module_results: dict) -> str:
    """
    Assemble the full HTML email.

    module_results keys: "weather", "stocks", "sports", "jobs"
    Each value is: HTML (rendered card), "" (module omits, no error), or
    None (fetch failed; shows error card for that module). Toggle off omits
    the module.
    """
    user_tz = ZoneInfo(user.time_zone or "UTC")
    now_local = datetime.now(user_tz)
    date_str = now_local.strftime("%A, %B %-d, %Y")
    tz_label = user.time_zone or "UTC"

    base_url = os.getenv("BASE_URL", "https://gregmichnikov.com").rstrip("/")
    settings_url = f"{base_url}/daily-email/settings"

    module_order = [
        ("weather", profile.include_weather, "&#9729; Weather"),
        ("stocks", profile.include_stocks, "&#x1F4C8; Stocks"),
        ("sports", profile.include_sports, "&#x1F3C0; Sports Scores"),
        ("jobs", profile.include_jobs, "&#x1F4BC; Job Listings"),
    ]

    sections_html = ""
    enabled_count = 0
    for key, enabled, label in module_order:
        if not enabled:
            continue
        result = module_results.get(key)
        if result is None:
            sections_html += _error_card(label)
        elif result == "":
            # Module chose to omit (e.g. Ashby: zero matches after filter)
            pass
        else:
            sections_html += result
            enabled_count += 1

    if (
        not sections_html
        and enabled_count == 0
        and not any(
            module_results.get(k) for k, e, _ in module_order if e
        )
    ):
        sections_html = _nothing_loaded_card(settings_url)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Morning Digest</title>
<style>
  body {{
    margin: 0; padding: 0;
    background-color: #f4f4f4;
    font-family: Arial, Helvetica, sans-serif;
    font-size: 15px;
    color: #222;
  }}
  .de-email-wrap {{
    max-width: 600px;
    margin: 0 auto;
    background-color: #ffffff;
  }}
  .de-email-header {{
    background-color: #1a1a2e;
    color: #ffffff;
    padding: 28px 24px 20px;
    text-align: center;
  }}
  .de-email-header h1 {{
    margin: 0 0 6px;
    font-size: 22px;
    font-weight: 700;
    letter-spacing: 0.3px;
  }}
  .de-email-header p {{
    margin: 0;
    font-size: 13px;
    color: #aab0c6;
  }}
  .de-email-body {{
    padding: 16px 20px;
  }}
  .de-module {{
    margin-bottom: 20px;
    border: 1px solid #e8e8e8;
    border-radius: 6px;
    overflow: hidden;
  }}
  .de-module-header {{
    background-color: #f0f2f5;
    padding: 10px 14px;
    font-weight: 700;
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: #444;
    border-bottom: 1px solid #e0e0e0;
  }}
  .de-module-weather {{}}
  .de-module-location {{
    padding: 12px 14px;
    border-bottom: 1px solid #f0f0f0;
  }}
  .de-module-location:last-child {{ border-bottom: none; }}
  .de-module-location-name {{
    font-weight: 700;
    font-size: 14px;
    margin-bottom: 4px;
    color: #1a1a2e;
  }}
  .de-weather-today {{
    font-size: 14px;
    margin-bottom: 8px;
    color: #333;
  }}
  .de-weather-condition {{ font-weight: 600; }}
  .de-weather-range {{ color: #555; }}
  .de-weather-precip {{ color: #3a7dc9; }}
  .de-weather-week {{
    width: 100%;
    border-collapse: collapse;
    font-size: 11px;
    table-layout: fixed;
  }}
  .de-weather-day {{
    text-align: center;
    padding: 4px 2px;
    border-top: 1px solid #f0f0f0;
    vertical-align: top;
  }}
  .de-weather-day-date {{ font-weight: 600; color: #555; }}
  .de-weather-day-cond {{ color: #777; margin: 2px 0; }}
  .de-weather-day-range {{ font-weight: 600; color: #333; }}
  .de-error-card {{
    padding: 14px;
    background-color: #fffbf0;
    color: #888;
    font-size: 13px;
    font-style: italic;
    border-left: 3px solid #f0c040;
  }}
  .de-nothing-loaded {{
    padding: 24px;
    text-align: center;
    color: #888;
  }}
  .de-nothing-loaded a {{ color: #3a7dc9; }}
  .de-email-footer {{
    padding: 16px 20px;
    border-top: 1px solid #e8e8e8;
    font-size: 12px;
    color: #999;
    text-align: center;
  }}
  .de-email-footer a {{ color: #3a7dc9; text-decoration: none; }}
</style>
</head>
<body>
<div class="de-email-wrap">
  <div class="de-email-header">
    <h1>Good morning &#9728;</h1>
    <p>{date_str} &nbsp;&bull;&nbsp; {tz_label}</p>
  </div>
  <div class="de-email-body">
    {sections_html}
  </div>
  <div class="de-email-footer">
    <a href="{settings_url}">Manage your digest preferences</a>
    &nbsp;&bull;&nbsp;
    You're receiving this because you opted in to the daily digest.
  </div>
</div>
</body>
</html>"""


def _error_card(label: str) -> str:
    return (
        f'<div class="de-module">'
        f'<div class="de-module-header">{label}</div>'
        f'<div class="de-error-card">{label.split(None, 1)[-1]} temporarily unavailable.</div>'
        f"</div>"
    )


def _nothing_loaded_card(settings_url: str) -> str:
    return (
        '<div class="de-module">'
        '<div class="de-module-header">Morning Digest</div>'
        '<div class="de-nothing-loaded">'
        "<p>We weren&#x2019;t able to load any sections for today&#x2019;s digest.</p>"
        f'<p><a href="{settings_url}">Check your preferences</a> or try again tomorrow.</p>'
        "</div>"
        "</div>"
    )
