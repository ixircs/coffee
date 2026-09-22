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

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"

DEFAULT_START = "19810101"  # earliest date the API accepts
# Pinned to the vintage every notebook was run on, so rebuilding reproduces the
# published numbers. The cache is keyed on start/end, so build_panel must use the same pair.
DEFAULT_END = "20260831"

# The three Brazilian Arabica regions used as the treatment area (docs/methodology.md 2.2).
REGIONS: dict[str, tuple[float, float]] = {
    "sul_de_minas": (-21.55, -45.43),
    "cerrado_mineiro": (-18.94, -46.99),
    "mogiana": (-20.54, -47.40),
}


def raw_path(lat: float, lon: float, start: str, end: str, raw_dir: str | Path = RAW_DIR) -> Path:
    """Return where the raw JSON response for this request is archived."""
    return Path(raw_dir) / f"nasa_power_{lat}_{lon}_{start}_{end}.json"


def fetch_weather(
    lat: float,
    lon: float,
    start: str,
    end: str,
    params: Sequence[str] = DEFAULT_PARAMS,
    raw_dir: str | Path = RAW_DIR,
    use_cache: bool = True,
) -> pd.DataFrame:
    """Return daily weather for one point, indexed by date; saves the raw JSON response."""
    out_file = raw_path(lat, lon, start, end, raw_dir)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    # Reuse the archived response so the panel can be rebuilt without network access.
    if use_cache and out_file.exists():
        payload = json.loads(out_file.read_text(encoding="utf-8"))
    else:
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
        out_file.write_text(json.dumps(payload), encoding="utf-8")

    records = payload["properties"]["parameter"]
    df = pd.DataFrame({name: pd.Series(values) for name, values in records.items()})
    df.index = pd.to_datetime(df.index, format="%Y%m%d")
    df.index.name = "date"
    # -999.0 means missing; left as-is it would poison means and frost percentiles.
    return df.astype("float64").replace(FILL_VALUE, np.nan).sort_index()


if __name__ == "__main__":
    for name, (lat, lon) in REGIONS.items():
        weather = fetch_weather(lat, lon, DEFAULT_START, DEFAULT_END)
        path = raw_path(lat, lon, DEFAULT_START, DEFAULT_END).relative_to(ROOT)
        print(f"{path}  {len(weather)} rows  ({name})")
