"""
Email sending for Sports Schedules weekly digest.
"""
import html
import os

from app.utils.email_service import send_email


def send_digest_email(digest, query_results):
    """
    Send the weekly digest email to the digest's user.

    Args:
        digest: SportsScheduleScheduledDigest instance (with .user relationship loaded)
        query_results: List of dicts with keys:
            - name (str): Query name
            - rows (list): List of row dicts
            - count (bool): True if count query
            - url (str): "View full results" link
            - error (str | None): Error message if query failed

    Raises:
        Exception if email send fails
    """
    user = digest.user
    base_url = os.getenv("BASE_URL", "https://gregmichnikov.com").rstrip("/")
    manage_url = f"{base_url}/sports-schedules"

    subject = "Sports Schedules: Your weekly digest"

    sections_html = []
    sections_text = []

    for q in query_results:
        name = html.escape(q["name"])
        url = q.get("url", manage_url)

        if q.get("error"):
            sections_html.append(
                f'<div class="ss-digest-section">'
                f'<h3 class="ss-digest-query-name">{name}</h3>'
                f'<p class="ss-digest-error">Could not load: {html.escape(q["error"])}</p>'
                f'<p><a href="{url}" class="ss-digest-link">View full results</a></p>'
                f"</div>"
            )
            sections_text.append(f"{q['name']}\nCould not load: {q['error']}\nView: {url}\n")
            continue

        rows = q.get("rows", [])

        if q.get("count"):
            # Count query: show "X games"
            count_val = 0
            if rows and len(rows) > 0:
                # Column may be "# Games" or similar
                for key, val in rows[0].items():
                    if "game" in key.lower() or key == "# Games":
                        try:
                            count_val = int(val)
                        except (TypeError, ValueError):
                            count_val = val
                        break
                    elif isinstance(val, (int, float)):
                        count_val = int(val)
                        break
            sections_html.append(
                f'<div class="ss-digest-section">'
                f'<h3 class="ss-digest-query-name">{name}</h3>'
                f'<p class="ss-digest-count">{count_val} games</p>'
                f'<p><a href="{url}" class="ss-digest-link">View full results</a></p>'
                f"</div>"
            )
            sections_text.append(f"{q['name']}: {count_val} games\nView: {url}\n")
        elif not rows:
            sections_html.append(
                f'<div class="ss-digest-section">'
                f'<h3 class="ss-digest-query-name">{name}</h3>'
                f'<p class="ss-digest-empty">No games found for {name}</p>'
                f'<p><a href="{url}" class="ss-digest-link">View full results</a></p>'
                f"</div>"
            )
            sections_text.append(f"{q['name']}: No games found\nView: {url}\n")
        else:
            # Build HTML table from rows (max 25)
            cols = list(rows[0].keys()) if rows else []
            header = "".join(f"<th class=\"ss-digest-th\">{html.escape(str(c))}</th>" for c in cols)
            body_rows = []
            for row in rows[:25]:
                cells = "".join(
                    f"<td class=\"ss-digest-td\">{html.escape(str(row.get(c, '')))}</td>"
                    for c in cols
                )
                body_rows.append(f"<tr class=\"ss-digest-tr\">{cells}</tr>")
            table_html = (
                f'<table class="ss-digest-table">'
                f"<thead><tr>{header}</tr></thead>"
                f"<tbody>{''.join(body_rows)}</tbody>"
                f"</table>"
            )
            if len(rows) > 25:
                table_html += f'<p class="ss-digest-more">(Showing first 25 of {len(rows)} games)</p>'

            sections_html.append(
                f'<div class="ss-digest-section">'
                f'<h3 class="ss-digest-query-name">{name}</h3>'
                f"{table_html}"
                f'<p><a href="{url}" class="ss-digest-link">View full results</a></p>'
                f"</div>"
            )

            # Plain text: simple row listing
            text_lines = [f"{q['name']}:"]
            for row in rows[:25]:
                text_lines.append("  " + " | ".join(str(row.get(c, "")) for c in cols))
            if len(rows) > 25:
                text_lines.append(f"  (Showing first 25 of {len(rows)} games)")
            text_lines.append(f"View: {url}\n")
            sections_text.append("\n".join(text_lines))

    html_body = "\n".join(sections_html)
    text_body = "\n\n".join(sections_text)

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .ss-digest-container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .ss-digest-section {{ margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid #eee; }}
        .ss-digest-query-name {{ margin: 0 0 8px 0; font-size: 16px; }}
        .ss-digest-table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
        .ss-digest-th, .ss-digest-td {{ border: 1px solid #ddd; padding: 6px 8px; text-align: left; }}
        .ss-digest-th {{ background: #f5f5f5; font-weight: bold; }}
        .ss-digest-count, .ss-digest-empty, .ss-digest-error {{ margin: 8px 0; }}
        .ss-digest-more {{ font-size: 12px; color: #666; margin-top: 4px; }}
        .ss-digest-link {{ color: #0066cc; }}
        .ss-digest-footer {{ margin-top: 30px; font-size: 12px; color: #999; border-top: 1px solid #eee; padding-top: 12px; }}
    </style>
</head>
<body>
    <div class="ss-digest-container">
        <h2 class="ss-digest-title">Your Sports Schedules Digest</h2>
        <p>Here are your saved queries for this week:</p>
        {html_body}
        <div class="ss-digest-footer">
            <p>Emails go out every Thursday. <a href="{manage_url}" class="ss-digest-link">Manage your digest</a></p>
        </div>
    </div>
</body>
</html>"""

    text_content = f"""Your Sports Schedules Digest

{text_body}

Manage your digest: {manage_url}
"""

    send_email(
        to_email=user.email,
        subject=subject,
        text_content=text_content,
        html_content=html_content,
    )
