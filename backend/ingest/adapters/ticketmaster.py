"""
Concert adapter, backed by the Ticketmaster Discovery API (official, free,
public REST API — no scraping). Free tier: 5000 calls/day, 5/sec, JSON.
Register a key at https://developer.ticketmaster.com/ (a couple of minutes,
no card) and set it as the TICKETMASTER_API_KEY GitHub secret.

Coverage caveat, stated plainly: TicketOne and Vivaticket are the dominant
ticketing platforms in Italy and neither offers a public API — TicketOne's
robots.txt explicitly disallows automated access, and Vivaticket sits behind
bot-protection. Ticketmaster's Italy coverage is real but thinner than
either of those, so this adapter is a legitimate starting point for
concerts, not a complete one. See backend/README.md for how to broaden it
(official venue calendars, RSS/ICS feeds) without touching disallowed sites.
"""
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from backend.ingest.adapters.base import Adapter, RawEvent
from backend.ingest.dedupe import normalize_city

API_BASE = "https://app.ticketmaster.com/discovery/v2/events.json"
ROME_TZ = ZoneInfo("Europe/Rome")


class ConcertAdapter(Adapter):
    name = "Ticketmaster Discovery API (IT, music)"
    source_type = "api"

    def __init__(self, page_size: int = 200, max_pages: int = 5):
        self.page_size = page_size
        self.max_pages = max_pages

    def fetch(self) -> list[dict]:
        key = os.environ.get("TICKETMASTER_API_KEY")
        if not key:
            raise RuntimeError(
                "TICKETMASTER_API_KEY is not set — register a free key at "
                "developer.ticketmaster.com and add it as a GitHub Actions secret."
            )
        events = []
        for page in range(self.max_pages):
            resp = requests.get(API_BASE, params={
                "apikey": key,
                "countryCode": "IT",
                "classificationName": "music",
                "size": self.page_size,
                "page": page,
                "sort": "date,asc",
            }, timeout=30)
            resp.raise_for_status()
            body = resp.json()
            batch = body.get("_embedded", {}).get("events", [])
            events.extend(batch)
            total_pages = body.get("page", {}).get("totalPages", 1)
            if page + 1 >= total_pages or not batch:
                break
        return events

    def parse(self, raw: list[dict]) -> list[RawEvent]:
        status_map = {
            "onsale": "scheduled", "offsale": "scheduled",
            "cancelled": "cancelled", "postponed": "postponed",
            "rescheduled": "postponed",
        }
        events = []
        for e in raw:
            venues = e.get("_embedded", {}).get("venues", [])
            venue = venues[0] if venues else {}
            city_raw = (venue.get("city") or {}).get("name") or "Not available"
            start = e.get("dates", {}).get("start", {})
            local_date = start.get("localDate")
            local_time = start.get("localTime")
            if local_time and len(local_time) > 5:
                local_time = local_time[:5]  # API gives HH:MM:SS; app uses HH:MM throughout
            if (not local_date or not local_time) and start.get("dateTime"):
                utc_dt = datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00"))
                local_dt = utc_dt.astimezone(ROME_TZ)
                local_date = local_date or local_dt.date().isoformat()
                local_time = local_time or local_dt.strftime("%H:%M")
            if not local_date:
                continue  # no usable date at all = skip rather than invent one

            classification = (e.get("classifications") or [{}])[0]
            genre = (classification.get("genre") or {}).get("name", "")
            category = "Festival" if "festival" in genre.lower() else "Concert"

            promoter = (e.get("promoter") or {}).get("name") or "Not available"

            events.append(RawEvent(
                name=e.get("name", "Not available"),
                date=local_date,
                start_time=local_time,
                venue=venue.get("name") or "Not available",
                city=normalize_city(city_raw),
                category=category,
                organiser=promoter,
                source_name=self.name,
                source_url=e.get("url", "https://www.ticketmaster.it"),
                external_event_id=e.get("id"),
                status=status_map.get(e.get("dates", {}).get("status", {}).get("code"), "scheduled"),
            ))
        return events
