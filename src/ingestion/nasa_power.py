"""Fetch daily weather for a point from the NASA POWER API."""

import json
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd
import requests

BASE_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
COMMUNITY = "AG"
DEFAULT_PARAMS = ("T2M_MIN", "T2M_MAX", "T2M", "PRECTOTCORR")
FILL_VALUE = -999.0  # NASA POWER's "missing" marker, NOT a real temperature
TIMEOUT = 60

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"


def fetch_weather(
    lat: float,
    lon: float,
    start: str,
    end: str,
    params: Sequence[str] = DEFAULT_PARAMS,
    raw_dir: str | Path = RAW_DIR,
) -> pd.DataFrame:
    """Return daily weather for one point, indexed by date; saves the raw JSON response."""
    query = {
        "parameters": ",".join(params),
        "community": COMMUNITY,
        "latitude": lat,
        "longitude": lon,
        "start": start,
        "end": end,
        "format": "JSON",
    }
    response = requests.get(BASE_URL, params=query, timeout=TIMEOUT)
    response.raise_for_status()
    payload = response.json()

    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    out_file = raw_dir / f"nasa_power_{lat}_{lon}_{start}_{end}.json"
    out_file.write_text(json.dumps(payload), encoding="utf-8")

    records = payload["properties"]["parameter"]
    df = pd.DataFrame({name: pd.Series(values) for name, values in records.items()})
    df.index = pd.to_datetime(df.index, format="%Y%m%d")
    df.index.name = "date"
    # -999.0 means missing; left as-is it would poison means and frost percentiles.
    return df.astype("float64").replace(FILL_VALUE, np.nan).sort_index()
