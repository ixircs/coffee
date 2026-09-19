"""Load the hand-curated table of documented weather events."""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
EVENTS_FILE = ROOT / "data" / "events.csv"


def load_events(path: str | Path = EVENTS_FILE) -> pd.DataFrame:
    """Return documented events sorted by date; undated rows come back as NaT."""
    events = pd.read_csv(path)
    # errors="coerce" keeps placeholder dates such as 2022-05-XX as NaT instead of
    # failing or guessing a day the source has not confirmed.
    events["event_date"] = pd.to_datetime(events["event_date"], format="%Y-%m-%d", errors="coerce")
    return events.sort_values("event_date", na_position="last").reset_index(drop=True)
