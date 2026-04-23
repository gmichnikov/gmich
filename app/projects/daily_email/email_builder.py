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

    pre = f"Weather, updates, and more for {date_str}."
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="color-scheme" content="light only">
<meta name="supported-color-schemes" content="light">
<title>Morning Digest</title>
<style>
  body {{
    margin: 0; padding: 0;
    -webkit-text-size-adjust: 100%;
    -ms-text-size-adjust: 100%;
    background-color: #e9ebf0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 15px;
    line-height: 1.5;
    color: #1f2933;
  }}
  .de-email-preheader {{
    display: none; max-height: 0; overflow: hidden; font-size: 1px; line-height: 1px; color: #e9ebf0; opacity: 0;
  }}
  .de-email-wrap {{
    max-width: 600px;
    margin: 0 auto;
    background-color: #ffffff;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  }}
  .de-email-header {{
    background: linear-gradient(165deg, #1a1a2e 0%, #16213e 100%);
    color: #ffffff;
    padding: 28px 24px 22px;
    text-align: center;
  }}
  .de-email-header h1 {{
    margin: 0 0 8px;
    font-size: 22px;
    font-weight: 700;
    letter-spacing: 0.2px;
  }}
  .de-email-header p {{
    margin: 0;
    font-size: 13px;
    color: #b8bfd4;
  }}
  .de-email-body {{
    padding: 20px 22px 8px;
  }}
  .de-module {{
    margin-bottom: 18px;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    overflow: hidden;
    background: #fff;
  }}
  .de-module-header {{
    background: linear-gradient(180deg, #f3f4f6 0%, #eef0f3 100%);
    padding: 11px 16px;
    font-weight: 700;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.55px;
    color: #3d4852;
    border-bottom: 1px solid #e0e3e7;
  }}
  .de-module-weather {{}}
  .de-module-location {{
    padding: 12px 16px;
    border-bottom: 1px solid #f0f2f5;
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
  .de-weather-precip {{ color: #2563eb; }}
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
    padding: 14px 16px;
    background-color: #fffbeb;
    color: #6b5b2b;
    font-size: 13px;
    line-height: 1.45;
    border-left: 3px solid #e5a50a;
  }}
  .de-nothing-loaded {{
    padding: 24px 16px 28px;
    text-align: center;
    color: #5c6770;
    font-size: 14px;
    line-height: 1.5;
  }}
  .de-nothing-loaded a {{ color: #2563eb; }}
  .de-email-footer {{
    padding: 18px 22px 24px;
    border-top: 1px solid #e8e8e8;
    font-size: 12px;
    line-height: 1.5;
    color: #7b8794;
    text-align: center;
  }}
  .de-email-footer a {{ color: #2563eb; text-decoration: none; font-weight: 500; }}
</style>
</head>
<body>
<div class="de-email-preheader">{pre}</div>
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
    <br><br>
    <span style="color:#9aa5b1;">You are receiving this because you opted in to the daily digest.</span>
  </div>
</div>
</body>
</html>"""


def _error_card(label: str) -> str:
    # `label` is e.g. "&#9729; Weather" or "&#x1F3C0; Sports Scores" (icon entity + name).
    display = label.split(None, 1)[-1] if " " in (label or "") else (label or "this section")
    return (
        f'<div class="de-module">'
        f'<div class="de-module-header">{label}</div>'
        f'<div class="de-error-card">We couldn’t load {display} right now. It may be back in the next send.</div>'
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
