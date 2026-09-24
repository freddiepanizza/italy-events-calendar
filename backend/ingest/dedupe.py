"""
Normalization + deduplication for the Italy events pipeline.

Every adapter emits a RawEvent (see adapters/base.py). Before insert, each
raw event is normalized into a dedupe key. Two raw events that produce the
same key are merged into a single `events` row, with both source URLs kept
in `event_sources`.
"""
import re
import unicodedata

CITY_ALIASES = {
    "milan": "Milano", "milano": "Milano",
    "turin": "Torino", "torino": "Torino",
    "rome": "Roma", "roma": "Roma",
    "florence": "Firenze", "firenze": "Firenze",
    "bologna": "Bologna",
    "bergamo": "Bergamo",
    "naples": "Napoli", "napoli": "Napoli",
    "venice": "Venezia", "venezia": "Venezia",
    "assago": "Assago", "siena": "Siena", "alba": "Alba",
}

def normalize_city(raw: str) -> str:
    key = raw.strip().lower()
    return CITY_ALIASES.get(key, raw.strip().title())

def normalize_name(raw: str) -> str:
    """Strip punctuation/venue suffixes/case so 'AC/DC - Milano' and
    'AC/DC Live in Milan' converge to the same normalized string."""
    s = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode()
    s = s.lower()
    s = re.sub(r"\b(live|in|tour|concert|the)\b", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def dedupe_key(name: str, date: str, start_time: str, venue: str, city: str) -> str:
    """The composite key events are matched on. start_time is bucketed to
    the nearest 15 minutes so minor source discrepancies (20:45 vs 20:46)
    still collide."""
    def bucket_time(t):
        if not t:
            return "??:??"
        h, m = t.split(":")
        m = str((int(m) // 15) * 15).zfill(2)
        return f"{h}:{m}"

    return "|".join([
        normalize_name(name),
        date,
        bucket_time(start_time),
        normalize_name(venue or ""),
        normalize_city(city),
    ])
