#!/usr/bin/env python3
"""
Backfill Travel Log entry place-detail columns from Google Place Details (New).

Uses stored TlogEntry.place_id and updates:
  primary_type, primary_type_display_name, short_formatted_address,
  addr_locality, addr_admin_area_1, addr_admin_area_2, addr_admin_area_3,
  addr_country_code

Requires:
  - DATABASE_URL, SECRET_KEY, ADMIN_EMAIL (Flask app startup)
  - GOOGLE_PLACES_API_KEY
  - DB migration applied so the columns exist

Usage (from repo root, with venv active):
  python scripts/tlog_backfill_place_details.py --dry-run
  python scripts/tlog_backfill_place_details.py
  python scripts/tlog_backfill_place_details.py --force --limit 5
  python scripts/tlog_backfill_place_details.py --entry-id 42

Options:
  --dry-run     Print actions only; no DB writes.
  --force       Refetch for every entry with a place_id (even if details already set).
  --limit N     Process at most N entries (after filters).
  --entry-id N  Only this entry (must have place_id).
  --delay SEC   Sleep between distinct Place Details API calls (default 0.15).
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime
from itertools import groupby
from pathlib import Path

# Repo root on sys.path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app import create_app, db
from app.projects.travel_log.models import TlogEntry
from app.projects.travel_log.services.places import fetch_place_details
from app.projects.travel_log.utils import extract_place_detail_from_api_place

logger = logging.getLogger("tlog_backfill")


def entry_has_any_place_detail(entry: TlogEntry) -> bool:
    return any(
        [
            entry.primary_type,
            entry.primary_type_display_name,
            entry.short_formatted_address,
            entry.addr_locality,
            entry.addr_admin_area_1,
            entry.addr_admin_area_2,
            entry.addr_admin_area_3,
            entry.addr_country_code,
        ]
    )


def apply_details_to_entry(entry: TlogEntry, details: dict) -> None:
    entry.primary_type = details.get("primary_type")
    entry.primary_type_display_name = details.get("primary_type_display_name")
    entry.short_formatted_address = details.get("short_formatted_address")
    entry.addr_locality = details.get("addr_locality")
    entry.addr_admin_area_1 = details.get("addr_admin_area_1")
    entry.addr_admin_area_2 = details.get("addr_admin_area_2")
    entry.addr_admin_area_3 = details.get("addr_admin_area_3")
    entry.addr_country_code = details.get("addr_country_code")
    now = datetime.utcnow()
    entry.updated_at = now
    if entry.collection:
        entry.collection.last_modified = now


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill Travel Log place details from Google Places API.")
    parser.add_argument("--dry-run", action="store_true", help="Do not write to the database.")
    parser.add_argument("--force", action="store_true", help="Update all entries with place_id, not only empty details.")
    parser.add_argument("--limit", type=int, default=0, metavar="N", help="Max entries to process (0 = no limit).")
    parser.add_argument("--entry-id", type=int, default=0, metavar="N", help="Single entry id.")
    parser.add_argument("--delay", type=float, default=0.15, help="Seconds between API calls (default 0.15).")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    app = create_app()
    with app.app_context():
        q = TlogEntry.query.filter(TlogEntry.place_id.isnot(None), TlogEntry.place_id != "")
        if args.entry_id:
            q = q.filter(TlogEntry.id == args.entry_id)
        entries = q.order_by(TlogEntry.place_id, TlogEntry.id).all()

        if args.entry_id and not entries:
            print(f"No entry {args.entry_id} with a non-empty place_id.", file=sys.stderr)
            return 1

        if not args.force:
            entries = [e for e in entries if not entry_has_any_place_detail(e)]

        if args.limit and args.limit > 0:
            entries = entries[: args.limit]

        if not entries:
            print("No entries to process.")
            return 0

        print(f"Processing {len(entries)} entries ({len({e.place_id for e in entries})} distinct place_id values).")
        if args.dry_run:
            print("DRY RUN — no database changes.")

        updated_entries = 0
        api_calls = 0

        for place_id, group_iter in groupby(entries, key=lambda e: e.place_id):
            group = list(group_iter)
            api_calls += 1
            if args.dry_run:
                raw = fetch_place_details(place_id)
                details = extract_place_detail_from_api_place(raw) if raw else {}
                nonempty = {k: v for k, v in details.items() if v}
                summary = nonempty if nonempty else "(no fields returned)"
                for entry in group:
                    if not raw:
                        print(
                            f"  [dry-run] entry {entry.id} place_id={place_id[:20]}… → API returned nothing"
                        )
                    else:
                        print(
                            f"  [dry-run] entry {entry.id} place_id={place_id[:20]}… → {summary}"
                        )
                    updated_entries += 1
            else:
                raw = fetch_place_details(place_id)
                if not raw:
                    logger.warning("Skip %d entries: no API data for place_id starting %s", len(group), place_id[:16])
                    continue
                details = extract_place_detail_from_api_place(raw)
                for entry in group:
                    apply_details_to_entry(entry, details)
                    updated_entries += 1
                db.session.commit()
                logger.info(
                    "Updated %d entries from place_id=%s…",
                    len(group),
                    place_id[:20],
                )

            if args.delay > 0:
                time.sleep(args.delay)

        print(f"Done. Entries touched: {updated_entries}. Place Details API calls: {api_calls}.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
