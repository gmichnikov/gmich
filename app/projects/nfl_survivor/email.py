"""Email sending for NFL Survivor reminder updates."""

import html
import os

from app.projects.nfl_survivor.reminders import format_pick_count_line, reminder_subject
from app.utils.email_service import send_email


def _entry_text(entry, last_week):
    lines = [entry["display_name"]]
    if entry["status"] == "eliminated":
        lines.append("This entry is out (2 losses).")
    lines.append(f"Losses: {entry['losses']}")
    if last_week:
        if entry["last_week_team"]:
            lines.append(
                f"Week {last_week}: {entry['last_week_team']} — {entry['last_week_outcome']}"
            )
        else:
            lines.append(f"Week {last_week}: no pick")
    if entry["status"] == "alive":
        if entry["needs_pick"]:
            lines.append("This week: no pick yet")
        elif entry["this_week_team"]:
            lines.append(f"This week: {entry['this_week_team']}")
        else:
            lines.append("This week: no pick needed")
    return "\n".join(lines)


def _entry_html(entry, last_week):
    name = html.escape(entry["display_name"])
    bits = [f'<p style="margin:0 0 8px 0;font-weight:bold;color:#013369;">{name}</p>']
    if entry["status"] == "eliminated":
        bits.append(
            '<p style="margin:0 0 8px 0;color:#92400e;font-weight:600;">'
            "This entry is out (2 losses).</p>"
        )
    bits.append(f'<p style="margin:0 0 4px 0;">Losses: {entry["losses"]}</p>')
    if last_week:
        if entry["last_week_team"]:
            team = html.escape(entry["last_week_team"])
            outcome = html.escape(entry["last_week_outcome"] or "")
            bits.append(
                f'<p style="margin:0 0 4px 0;">Week {last_week}: {team} — {outcome}</p>'
            )
        else:
            bits.append(
                f'<p style="margin:0 0 4px 0;">Week {last_week}: no pick</p>'
            )
    if entry["status"] == "alive":
        if entry["needs_pick"]:
            bits.append(
                '<p style="margin:0;font-weight:600;color:#d50a0a;">'
                "This week: no pick yet</p>"
            )
        elif entry["this_week_team"]:
            team = html.escape(entry["this_week_team"])
            bits.append(f'<p style="margin:0;">This week: {team}</p>')
        else:
            bits.append('<p style="margin:0;">This week: no pick needed</p>')
    border = "#fcd34d" if entry["status"] == "eliminated" else "#d8dee9"
    bg = "#fffbeb" if entry["status"] == "eliminated" else "#f8fafc"
    return (
        f'<div style="margin:16px 0;padding:14px 16px;background:{bg};'
        f'border:1px solid {border};border-radius:8px;">{"".join(bits)}</div>'
    )


def send_reminder_email(user, payload):
    """Send the weekly survivor update/reminder. Raises on Mailgun failure."""
    base_url = os.getenv("BASE_URL", "https://gregmichnikov.com").rstrip("/")
    pick_url = f"{base_url}/nfl-survivor/pick"
    standings_url = f"{base_url}/nfl-survivor/view-picks"
    subject = reminder_subject(payload)
    last_week = payload.get("last_week")
    season_name = payload["season_name"]
    alive = payload["alive_count"]
    total = payload["total_count"]

    pool_line = f"{alive} of {total} entries still have fewer than 2 losses."
    if payload.get("last_week_results_pending") and last_week:
        pool_line += f" Week {last_week} results are not all in yet."

    pick_counts = format_pick_count_line(payload.get("last_week_pick_counts") or [])
    pick_count_text = ""
    pick_count_html = ""
    if pick_counts and last_week:
        pick_count_text = f"Week {last_week} picks in the pool: {pick_counts}\n"
        pick_count_html = (
            f'<p style="margin:0 0 16px 0;"><strong>Week {last_week} picks in the pool:</strong> '
            f"{html.escape(pick_counts)}</p>"
        )

    entry_text = "\n\n".join(_entry_text(entry, last_week) for entry in payload["entries"])
    entry_html = "".join(_entry_html(entry, last_week) for entry in payload["entries"])

    cta_text = ""
    cta_html = ""
    if payload.get("needs_any_pick"):
        cta_text = f"Make your pick: {pick_url}\n"
        cta_html = (
            '<p style="margin:24px 0 8px 0;">'
            f'<a href="{pick_url}" style="display:inline-block;padding:12px 20px;'
            "background-color:#013369;color:#ffffff !important;text-decoration:none;"
            'border-radius:6px;font-weight:bold;">Make your pick</a></p>'
        )
        cta_html += (
            '<p style="margin:0 0 16px 0;font-size:13px;color:#5c6578;">'
            "Picks lock when that team's game starts.</p>"
        )
    else:
        cta_text = f"View standings: {standings_url}\n"

    text_content = f"""{season_name} — Week {payload["current_week"]}

{pool_line}
{pick_count_text}
{entry_text}

{cta_text}
Standings: {standings_url}

Change your reminder day (or turn emails off) in the NFL Survivor header after you log in:
{pick_url}
"""

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #1a1f2e; }}
        .ns-mail-container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .ns-mail-footer {{ margin-top: 28px; font-size: 12px; color: #5c6578; border-top: 1px solid #d8dee9; padding-top: 12px; }}
    </style>
</head>
<body>
    <div class="ns-mail-container">
        <h2 style="margin:0 0 8px 0;color:#013369;">{html.escape(season_name)}</h2>
        <p style="margin:0 0 16px 0;color:#5c6578;">Week {payload["current_week"]}</p>
        <p style="margin:0 0 12px 0;">{html.escape(pool_line)}</p>
        {pick_count_html}
        {entry_html}
        {cta_html}
        <p style="margin:16px 0 0 0;"><a href="{standings_url}" style="color:#013369;">View standings</a></p>
        <div class="ns-mail-footer">
            <p style="margin:0;">
                Change your reminder day (or turn emails off) in the NFL Survivor header
                after you <a href="{pick_url}" style="color:#013369;">log in</a>.
            </p>
        </div>
    </div>
</body>
</html>
"""

    send_email(
        to_email=user.email,
        subject=subject,
        text_content=text_content,
        html_content=html_content,
        from_name="NFL Survivor",
    )
    return True


def send_sunday_nudge_email(user, week, *, missing_names, list_entries, bcc=None):
    """Mandatory Sunday missing-pick email. Raises on Mailgun failure."""
    from app.projects.nfl_survivor.sunday_nudge import (
        sunday_nudge_html,
        sunday_nudge_subject,
        sunday_nudge_text,
    )

    base_url = os.getenv("BASE_URL", "https://gregmichnikov.com").rstrip("/")
    pick_url = f"{base_url}/nfl-survivor/pick"
    send_email(
        to_email=user.email,
        subject=sunday_nudge_subject(week),
        text_content=sunday_nudge_text(
            week, pick_url, missing_names, list_entries
        ),
        html_content=sunday_nudge_html(
            week, pick_url, missing_names, list_entries
        ),
        from_name="NFL Survivor",
        bcc=bcc,
    )
    return True
