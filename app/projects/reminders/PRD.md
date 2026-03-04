# Reminder App — Requirements

## Overview

A personal reminder web app for individual users. Users create reminders with a title and optional body, choose a time, and receive an email around that time.

## Core Concept

Users set reminders using structured form input. The app stores reminders and delivers them via email at approximately the requested time, using a cron job running every 5 minutes on Render.

## Input

- **Structured input** — form-based entry (title required, body optional, datetime picker)
- **Natural language** — future enhancement (e.g. "Remind me to call the dentist in 3 days")

## Reminder Fields

- **Title** — required; used as the email subject
- **Body** — optional; included in the email body
- **Remind at** — required datetime; entered in the user's timezone, stored in UTC
- **Sent at** — nullable datetime; set when the reminder email is successfully sent

## Timing & Scheduling

- Reminders fire within a ~5-minute window of the requested time (Render cron minimum granularity)
- The UI uses 5 or 15-minute time increments to reflect this reality
- Reminders cannot be set in the past
- No maximum future limit

## Delivery Channels

- **Email** — first and only channel for v1
- **SMS / Phone call** — added later via Twilio or equivalent

## Email Content

- Subject: reminder title
- Body: reminder body (if provided), plus a link back to the Reminders page to manage reminders
- No confirmation email on creation; the reminder appears in the UI immediately

## UI / Pages

### Reminder List (index)
- **Upcoming** section: pending reminders, sorted by `remind_at` ascending
- **Past** section: sent reminders, collapsed or visually separated
- Each reminder shows title, scheduled time (in user's timezone), and status
- Actions per reminder: **Edit**, **Delete**, **Duplicate** (quickly create a new one pre-filled with the same title/body)

### Create / Edit Reminder
- Title (required), body (optional), datetime picker (user's timezone, 15-minute increments)
- Datetime must be in the future (validated server-side)

### Test Now Button
- Immediately sends the reminder email to the user's address
- Costs 1 credit (same as a real send)
- Useful for verifying email delivery and content

## Credits

- Each email send (scheduled or test) costs 1 credit from the site-wide credits system
- Credits are not deducted at creation time, only at send time
- If a user has 0 credits, their reminders due in the current window are skipped and will not be retried — a missed reminder is simply not sent
- The UI shows the user's current credit balance and displays a warning if they have more pending reminders than available credits

## Cron Job (Render)

- A Render Cron Job runs every 5 minutes
- It queries for reminders where `remind_at` falls within a narrow window (e.g. `now - 10 minutes` to `now + 5 minutes`), `sent_at IS NULL`, and the user has at least 1 credit
- The lookback buffer (e.g. 10 minutes) accounts for cron delays or brief downtime; reminders outside this window are never retried
- For each matching reminder, it sends the email, deducts 1 credit, and sets `sent_at`
- If the email send itself fails (e.g. Mailgun error), `sent_at` remains NULL and the error is logged; it may be retried if the next cron run still falls within the window

## Users

Regular people managing personal tasks. No business accounts, no client-facing features.

## Out of Scope (for now)

- **Recurring reminders** — e.g. "every weekday except holidays"
- **Snooze via reply** — user replies "snooze 1 hour" to shift the reminder
- **In-app snooze** — future UI feature to reschedule a sent reminder
- **Confirmation email** on creation
- **Natural language input**
- **Calendar integrations**
- **SMS / other channels**
- **is_cancelled / soft delete** — reminders are hard deleted for now
