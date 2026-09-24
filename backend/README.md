# Italy Events Calendar — backend

## Why this couldn't run inside this chat
This session has no outbound network access and no persistent process, so a
daily scraping job can't live here. Everything below is real, deployable
code — you (or Claude Code, running with network access) run it on a
schedule somewhere that stays on: a $5/mo VPS with cron, a GitHub Actions
scheduled workflow, or a Fly.io/Render cron job. SQLite is a single file, so
there's no database server to manage.

## Recommended sources by category (researched, not guaranteed — verify
current terms before deploying)
- **Serie A**: legaseriea.it publishes the official fixture list; it has no
  public JSON API but the fixture pages are structured HTML, scrapeable
  respecting robots.txt. SportRadar/API-Football offer paid APIs with
  reliable venue data if you want to avoid scraping.
- **Champions League**: uefa.com match pages, same approach.
- **Concerts**: TicketOne and Vivaticket are Italy's two dominant ticketing
  platforms and both expose structured event listing pages; treat them as
  your primary concert sources. Major venues (San Siro, Unipol Forum,
  Arena di Verona) also publish their own calendars.
- **Festivals/fairs/fashion/theatre/comedy**: no single national feed
  exists. Start with city-level sources you actually care about (Comune di
  Milano, Comune di Roma events pages; Camera della Moda for fashion week;
  major theatres like La Scala, La Fenice, Teatro alla Scala for their own
  listings) and add more adapters over time — the architecture is built for
  that.

## Layout
```
backend/
  schema.sql              # run once: sqlite3 events.db < schema.sql
  ingest/
    dedupe.py             # normalization + composite dedupe key
    run_sync.py           # daily entrypoint, isolates per-source failures
    adapters/
      base.py             # Adapter interface + Serie A / UCL geo rules
      # add one file per source here, e.g. serie_a.py, ticketone.py
```

## Adding a new source
1. Create `ingest/adapters/<source>.py`, subclass `Adapter`, implement
   `fetch()` (HTTP call) and `parse()` (raw → `RawEvent` list).
2. Register the instance in `ADAPTERS` in `run_sync.py`.
3. Nothing else changes — geo rules, dedupe, and the DB layer are shared.

## Setup
```
python -m venv venv && source venv/bin/activate
pip install requests beautifulsoup4   # add feedparser/icalendar if using RSS/ICS sources
sqlite3 events.db < schema.sql
python -m ingest.run_sync             # manual first run
```

## Scheduling (pick one)
- **cron** (VPS): `0 5 * * * cd /path/to/backend && venv/bin/python -m ingest.run_sync`
- **GitHub Actions**: a workflow with `on: schedule: cron: '0 5 * * *'` that
  checks out the repo, runs the sync, and commits/pushes `events.db` (or
  writes to a hosted SQLite like Turso/LiteFS if you want it queryable
  without a redeploy).

## Serving events to the frontend
The published calendar app currently uses in-page sample data. To wire it to
real data, add a thin read-only JSON endpoint (a few lines with Flask/FastAPI,
or a static `events.json` export written at the end of `run_sync.py` if you'd
rather keep it serverless) and swap the `EVENTS` array for a `fetch()` call.
