"""
Serie A and Champions League adapter, backed by football-data.org (free
tier: 12 competitions incl. Serie A/SA and Champions League/CL, 10 requests
per minute, JSON, X-Auth-Token header). Get a free key at
https://www.football-data.org/client/register — takes about a minute, no
card required — then set it as the FOOTBALL_DATA_API_KEY GitHub secret.

football-data.org's `venue` field is populated for most but not all
matches, so this adapter falls back to a static home-stadium table when the
API leaves it blank. That table only needs to be accurate for clubs whose
home city is one of the six Serie A cities the app cares about (San Siro is
Milano regardless of whether Inter or Milan is designated "home"), since
everything else gets filtered out by the geo rule anyway.
"""
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

from backend.ingest.adapters.base import Adapter, RawEvent

API_BASE = "https://api.football-data.org/v4"
ROME_TZ = ZoneInfo("Europe/Rome")

# Fallback only — used when football-data.org doesn't supply a venue for a match.
HOME_VENUES = {
    "Inter Milan": ("San Siro", "Milano"),
    "AC Milan": ("San Siro", "Milano"),
    "Juventus FC": ("Allianz Stadium", "Torino"),
    "Torino FC": ("Stadio Olimpico Grande Torino", "Torino"),
    "AS Roma": ("Stadio Olimpico", "Roma"),
    "SS Lazio": ("Stadio Olimpico", "Roma"),
    "ACF Fiorentina": ("Stadio Artemio Franchi", "Firenze"),
    "Bologna FC 1909": ("Stadio Renato Dall'Ara", "Bologna"),
    "Atalanta BC": ("Gewiss Stadium", "Bergamo"),
    # Other clubs fall outside the six-city rule for Serie A, so a rough
    # value is fine here — it's never used to decide inclusion.
    "SSC Napoli": ("Stadio Diego Armando Maradona", "Napoli"),
    "Como 1907": ("Stadio Giuseppe Sinigaglia", "Como"),
    "Udinese Calcio": ("Bluenergy Stadium", "Udine"),
    "US Sassuolo Calcio": ("Mapei Stadium", "Reggio Emilia"),
    "Cagliari Calcio": ("Unipol Domus", "Cagliari"),
    "Genoa CFC": ("Stadio Luigi Ferraris", "Genova"),
    "US Cremonese": ("Stadio Giovanni Zini", "Cremona"),
    "Parma Calcio 1913": ("Stadio Ennio Tardini", "Parma"),
    "US Lecce": ("Stadio Via del Mare", "Lecce"),
    "Hellas Verona FC": ("Stadio Marcantonio Bentegodi", "Verona"),
    "Pisa SC": ("Arena Garibaldi", "Pisa"),
}


class FootballDataAdapter(Adapter):
    source_type = "api"

    def __init__(self, competition_code: str, category: str, days_ahead: int = 45):
        self.competition_code = competition_code
        self.category = category
        self.days_ahead = days_ahead
        self.name = f"football-data.org ({competition_code})"

    def fetch(self) -> list[dict]:
        key = os.environ.get("FOOTBALL_DATA_API_KEY")
        if not key:
            raise RuntimeError(
                "FOOTBALL_DATA_API_KEY is not set — register a free key at "
                "football-data.org and add it as a GitHub Actions secret."
            )
        date_from = datetime.now(timezone.utc).date()
        date_to = date_from + timedelta(days=self.days_ahead)
        resp = requests.get(
            f"{API_BASE}/competitions/{self.competition_code}/matches",
            headers={"X-Auth-Token": key},
            params={"dateFrom": date_from.isoformat(), "dateTo": date_to.isoformat()},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("matches", [])

    def parse(self, raw: list[dict]) -> list[RawEvent]:
        events = []
        for m in raw:
            status_map = {
                "SCHEDULED": "scheduled", "TIMED": "scheduled",
                "POSTPONED": "postponed", "CANCELLED": "cancelled",
                "FINISHED": "completed", "AWARDED": "completed",
            }
            status = status_map.get(m.get("status"), "scheduled")

            utc_dt = datetime.fromisoformat(m["utcDate"].replace("Z", "+00:00"))
            local_dt = utc_dt.astimezone(ROME_TZ)

            home = m["homeTeam"]["name"]
            fallback_venue, fallback_city = HOME_VENUES.get(home, ("Not available", "Not available"))
            # football-data.org's `venue` field, when present, is a venue name only
            # (no city), so city always comes from the home-stadium table.
            venue = m.get("venue") or fallback_venue
            city = fallback_city

            events.append(RawEvent(
                name=f"{home} vs {m['awayTeam']['name']}",
                date=local_dt.date().isoformat(),
                start_time=local_dt.strftime("%H:%M"),
                venue=venue,
                city=city,
                category=self.category,
                organiser="Lega Serie A" if self.competition_code == "SA" else "UEFA",
                source_name=self.name,
                source_url=f"https://www.football-data.org/competitions/{self.competition_code}",
                external_event_id=str(m.get("id")),
                status=status,
            ))
        return events


class SerieAAdapter(FootballDataAdapter):
    def __init__(self):
        super().__init__(competition_code="SA", category="Serie A")


class ChampionsLeagueAdapter(FootballDataAdapter):
    def __init__(self):
        super().__init__(competition_code="CL", category="Champions League")
