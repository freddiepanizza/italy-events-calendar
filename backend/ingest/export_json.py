"""
Reads events.db and writes events.json at the repo root, in the shape the
frontend (index.html) expects. Called automatically at the end of
run_sync.main() — you don't need to run this separately.
"""
import json
import sqlite3

def export(db_path="backend/events.db", out_path="events.json"):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT e.id, e.name, e.date, e.start_time AS start, e.status,
               v.name AS venue, c.name_it AS city, e.category,
               o.name AS organiser
        FROM events e
        LEFT JOIN venues v ON e.venue_id = v.id
        LEFT JOIN cities c ON e.city_id = c.id
        LEFT JOIN organisers o ON e.organiser_id = o.id
        WHERE e.status != 'cancelled'
        ORDER BY e.date, e.start_time
    """)
    rows = [dict(r) for r in cur.fetchall()]
    for r in rows:
        r["id"] = f"e{r['id']}"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    conn.close()
    return len(rows)

if __name__ == "__main__":
    n = export()
    print(f"Exported {n} events to events.json")
