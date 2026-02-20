# MiLB Sync – Known Issues & Fixes

This document records issues encountered with the MLB Stats API schedule sync for minor leagues (AAA, AA, A+, A) and how they were resolved.

## Issue 1: Missing dates on large syncs

**Symptom:** When syncing a full season (e.g., Apr 1–Sep 30), some dates had zero games in DoltHub even though the API returns games for those dates. Small syncs (e.g., 7–8 days) worked fine.

**Root cause:** The MLB Stats API returns incomplete/truncated data for large date ranges (e.g., 30 or 90 days). Some date blocks are dropped from the response—likely due to response size limits or undocumented truncation.

**Fix:** Use small chunks when fetching from the API. See `MAX_DAYS_PER_REQUEST` in `core/mlb_client.py`—currently set to **7 days**. Do not increase this without testing; larger values have been observed to drop dates.

## Issue 2: Games on wrong dates (timezone)

**Symptom:** Games could appear under the wrong calendar date when game start times crossed midnight UTC.

**Root cause:** We previously derived the game date from `gameDate` (UTC → ET conversion). For late-night games, this could shift the date.

**Fix:** Use the API's `officialDate` (the date block the API groups each game under) instead of deriving from `gameDate`. See `_parse_game()` in `core/mlb_client.py`.

## Issue 3: DoltHub batch failures on large syncs

**Symptom:** Some batches could fail during upsert (transient timeouts, rate limiting).

**Fix (in `app/core/dolthub_client.py`):**
- Retry failed batches once after a 2-second delay
- 0.3s delay between batches to reduce rate limiting
- Improved error logging with sample primary keys when a batch fails

## Diagnostic commands

To verify coverage after a sync:

```bash
flask sports-admin check-coverage --league AA --start 2026-07-15 --end 2026-07-22
```

If dates are missing, compare with a small sync over the same range. If the small sync populates the dates but the full-season sync does not, the issue is likely the MLB API chunk size—reduce `MAX_DAYS_PER_REQUEST` further.
