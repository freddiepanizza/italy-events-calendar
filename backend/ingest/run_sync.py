"""
Daily sync entrypoint. Run via cron / GitHub Actions schedule:
  0 5 * * *  python -m ingest.run_sync

Each adapter's failure is isolated so one broken source never blocks the rest.
"""
import sqlite3
import traceback
from datetime import datetime, timezone

from backend.ingest.dedupe import dedupe_key, normalize_city
from backend.ingest.adapters.base import Adapter
from backend.ingest.export_json import export as export_json

# Register adapters here as you add sources — this is the only place a new
# source needs to be wired in.
ADAPTERS: list[Adapter] = [
    # SerieAAdapter(), UefaAdapter(), TicketOneAdapter(), ...
]

DB_PATH = "backend/events.db"


def get_or_create(cur, table, unique_cols: dict, extra_cols: dict = None):
    where = " AND ".join(f"{k}=?" for k in unique_cols)
    cur.execute(f"SELECT id FROM {table} WHERE {where}", list(unique_cols.values()))
    row = cur.fetchone()
    if row:
        return row[0]
    cols = {**unique_cols, **(extra_cols or {})}
    cur.execute(
        f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})",
        list(cols.values()),
    )
    return cur.lastrowid


def upsert_event(cur, source_id, e):
    city_id = get_or_create(cur, "cities", {"name_it": normalize_city(e.city)})
    venue_id = get_or_create(cur, "venues", {"name": e.venue, "city_id": city_id})
    org_id = get_or_create(cur, "organisers", {"name": e.organiser or "Not available"})
    key = dedupe_key(e.name, e.date, e.start_time, e.venue, e.city)

    cur.execute("SELECT id FROM events WHERE external_key=?", (key,))
    row = cur.fetchone()
    now = datetime.now(timezone.utc).isoformat()

    if row:
        event_id = row[0]
        cur.execute(
            """UPDATE events SET status=?, updated_at=? WHERE id=?""",
            (e.status, now, event_id),
        )
        outcome = "updated"
    else:
        cur.execute(
            """INSERT INTO events (external_key, name, description, date, start_time, end_time,
               venue_id, city_id, category, organiser_id, status, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (key, e.name, e.description, e.date, e.start_time, e.end_time,
             venue_id, city_id, e.category, org_id, e.status, now),
        )
        event_id = cur.lastrowid
        outcome = "added"

    cur.execute(
        """INSERT OR REPLACE INTO event_sources (event_id, source_id, source_url, external_event_id)
           VALUES (?,?,?,?)""",
        (event_id, source_id, e.source_url, e.external_event_id),
    )
    return outcome


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    for adapter in ADAPTERS:
        started = datetime.now(timezone.utc).isoformat()
        source_id = get_or_create(cur, "sources", {"name": adapter.name},
                                   {"source_type": adapter.source_type})
        try:
            events = adapter.run()
            added = updated = 0
            for e in events:
                outcome = upsert_event(cur, source_id, e)
                added += outcome == "added"
                updated += outcome == "updated"
            cur.execute(
                """UPDATE sources SET last_successful_sync=?, last_attempted_sync=?,
                   events_found=?, events_added=?, events_updated=?, error_status=NULL WHERE id=?""",
                (started, started, len(events), added, updated, source_id),
            )
            status = "success"
        except Exception:
            err = traceback.format_exc()
            cur.execute(
                """UPDATE sources SET last_attempted_sync=?, error_status=? WHERE id=?""",
                (started, err[:2000], source_id),
            )
            status = "failed"

        cur.execute(
            "INSERT INTO sync_runs (started_at, finished_at, source_id, status) VALUES (?,?,?,?)",
            (started, datetime.now(timezone.utc).isoformat(), source_id, status),
        )
        conn.commit()

    conn.close()
    n = export_json(db_path=DB_PATH, out_path="events.json")
    print(f"Sync complete. Exported {n} events to events.json")


if __name__ == "__main__":
    main()
