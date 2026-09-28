-- Italy Events Calendar — SQLite schema
-- Every statement is idempotent (IF NOT EXISTS) so it's safe to run on
-- every sync, whether the database already exists or not.

CREATE TABLE IF NOT EXISTS cities (
  id INTEGER PRIMARY KEY,
  name_it TEXT UNIQUE NOT NULL,       -- Milano, Torino, Roma...
  region TEXT
);

CREATE TABLE IF NOT EXISTS venues (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  address TEXT,
  city_id INTEGER REFERENCES cities(id),
  UNIQUE(name, city_id)
);

CREATE TABLE IF NOT EXISTS organisers (
  id INTEGER PRIMARY KEY,
  name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS sources (
  id INTEGER PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  url TEXT,
  source_type TEXT,                   -- api | rss | ics | scrape
  last_successful_sync TEXT,
  last_attempted_sync TEXT,
  events_found INTEGER DEFAULT 0,
  events_added INTEGER DEFAULT 0,
  events_updated INTEGER DEFAULT 0,
  events_removed INTEGER DEFAULT 0,
  error_status TEXT
);

CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY,
  external_key TEXT UNIQUE,           -- normalized dedupe key, see ingest/dedupe.py
  name TEXT NOT NULL,
  description TEXT,
  date TEXT NOT NULL,                 -- YYYY-MM-DD
  start_time TEXT,                    -- HH:MM
  end_time TEXT,
  venue_id INTEGER REFERENCES venues(id),
  city_id INTEGER REFERENCES cities(id) NOT NULL,
  category TEXT NOT NULL,             -- Serie A | Champions League | Concert | Festival | Fashion | Theatre | Comedy | Fair
  subcategory TEXT,
  organiser_id INTEGER REFERENCES organisers(id),
  status TEXT DEFAULT 'scheduled',    -- scheduled | postponed | cancelled | completed
  data_confidence REAL DEFAULT 1.0,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS event_sources (  -- an event can have several source URLs (dedup keeps one event)
  event_id INTEGER REFERENCES events(id),
  source_id INTEGER REFERENCES sources(id),
  source_url TEXT,
  external_event_id TEXT,
  PRIMARY KEY (event_id, source_id)
);

CREATE TABLE IF NOT EXISTS sync_runs (
  id INTEGER PRIMARY KEY,
  started_at TEXT,
  finished_at TEXT,
  source_id INTEGER REFERENCES sources(id),
  status TEXT,                        -- success | partial | failed
  log TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_date ON events(date);
CREATE INDEX IF NOT EXISTS idx_events_city ON events(city_id);
CREATE INDEX IF NOT EXISTS idx_events_category ON events(category);
