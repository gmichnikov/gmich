# 5am Morning Briefing Email — Project Spec

A Python script that runs at 5am daily, fetches data from several APIs, assembles an HTML email, and sends it automatically. No server required — runs as a cron job, GitHub Actions workflow, or cloud function.

---

## Email sections

### 1. Weather — today's forecast + week ahead

- **API:** Open-Meteo (free, no key required)
- Today: temperature, rain chance, conditions
- Week: 7-day outlook
- Also pull **air quality / AQI** from Open-Meteo at no extra cost

### 2. Top headlines

- **API:** NewsAPI.org (free tier)
- 3–5 top headlines with source name and link

### 3. Portfolio

- **API:** `yfinance` Python library (free, unofficial Yahoo Finance)
- Hardcode tickers and share counts in config
- Show: total value, day's P&L, per-ticker price and % change

### 4. Today's agenda

- **API:** Google Calendar API (free, requires OAuth2 setup)
- Pull today's events with time and title

### 5. Last night's scores

- **API:** ESPN undocumented API (`site.api.espn.com/apis/site/v2/sports/...`) or API-Sports free tier
- Hardcode leagues and teams to watch

### 6. Local events this week

- **API:** Ticketmaster Discovery API (free tier) or Eventbrite API (free tier)
- Filter by location (zip code or city)

### 7. Job listings monitor

- **API:** Ashby public job board API (no auth required)
- Endpoint pattern: `https://api.ashbyhq.com/posting-api/job-board/{companySlug}`
- Also check Greenhouse (`boards-api.greenhouse.io/v1/boards/{slug}/jobs`) and Lever (`api.lever.co/v0/postings/{slug}`) for companies that use those ATS platforms
- Filter results by keywords (title, department, location) defined in config
- Only include results that meet conditions — omit section if no matches

---

## Script structure

```
run.py
├── fetch_weather()       → Open-Meteo
├── fetch_headlines()     → NewsAPI
├── fetch_portfolio()     → yfinance
├── fetch_calendar()      → Google Calendar API
├── fetch_scores()        → ESPN API
├── fetch_events()        → Ticketmaster / Eventbrite
├── fetch_jobs()          → Ashby / Greenhouse / Lever
├── build_email()         → assembles HTML
└── send_email()          → SendGrid or Gmail SMTP
```

---

## Email format

Single-column HTML email, dark header with date and location, one section per card. Suggested order:

```
Good morning — [Weekday, Month Day]
[City, State]

☁ WEATHER
[Today's conditions + 7-day strip]

📰 TOP HEADLINES
[3–5 bullets with source links]

📈 PORTFOLIO
[Total value + day P&L + per-ticker rows]

📅 TODAY'S AGENDA
[Time-sorted event list]

🏀 LAST NIGHT'S SCORES
[Team A X – Team B Y]

📍 LOCAL EVENTS THIS WEEK
[Event name, day, venue]

💼 JOB LISTINGS
[Only shown if matches found]
[Title — Company — Location — link]
```

---

## Sending the email

- **SendGrid** — free tier (100 emails/day), clean Python SDK
- **Alternative:** Gmail SMTP with an app password (zero cost, minimal setup)

---

## Scheduling

- **GitHub Actions** (recommended) — free, cron trigger, script lives in a private repo
- **cron on a home server / Raspberry Pi** — full local control
- **Railway, Render, or Fly.io** — free-tier cloud hosting with cron support

---

## Suggested build order

1. Open-Meteo + email pipeline (proves the plumbing works)
2. NewsAPI headlines
3. SendGrid — confirm email arrives and renders correctly
4. yfinance portfolio
5. Google Calendar (OAuth setup is the most involved step)
6. Scores and local events
7. Job listings monitor

---

## Config file (separate from script)

All user-specific values should live in a `config.py` or `.env`:

- Location (lat/lon, zip, city name)
- Portfolio tickers and share counts
- Teams and leagues to follow
- Job board slugs and filter keywords
- API keys
- Recipient email address
