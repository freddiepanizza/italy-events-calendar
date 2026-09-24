from dataclasses import dataclass
from typing import Optional

SERIE_A_CITIES = {"Milano", "Torino", "Roma", "Firenze", "Bologna", "Bergamo"}
UCL_CITIES = {"Milano"}

@dataclass
class RawEvent:
    name: str
    date: str            # YYYY-MM-DD
    start_time: Optional[str]
    venue: str
    city: str             # already passed through normalize_city
    category: str
    organiser: str
    source_name: str
    source_url: str
    external_event_id: Optional[str] = None
    description: Optional[str] = None
    end_time: Optional[str] = None
    status: str = "scheduled"

class Adapter:
    """One subclass per source. Never let one adapter's failure take down
    the whole sync — the runner wraps each adapter call in try/except."""
    name: str
    source_type: str  # api | rss | ics | scrape

    def fetch(self) -> list[dict]:
        raise NotImplementedError

    def parse(self, raw: list[dict]) -> list[RawEvent]:
        raise NotImplementedError

    def run(self) -> list[RawEvent]:
        events = self.parse(self.fetch())
        return [e for e in events if self.passes_geo_rules(e)]

    @staticmethod
    def passes_geo_rules(e: RawEvent) -> bool:
        if e.category == "Serie A":
            return e.city in SERIE_A_CITIES
        if e.category == "Champions League":
            return e.city in UCL_CITIES
        return True  # concerts / festivals / fashion / theatre / comedy / fairs: all of Italy
