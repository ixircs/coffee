"""Merge prices, weather and FX into the analysis-ready monthly panel."""

from pathlib import Path

import pandas as pd

from src.ingestion.nasa_power import REGIONS, fetch_weather
from src.ingestion.worldbank import load_pink_sheet
from src.ingestion.yahoo import fetch_fx
from src.processing.weather_features import combine_regions, monthly_features

ROOT = Path(__file__).resolve().parents[2]
PRICE_FILE = ROOT / "data" / "raw" / "CMO-Historical-Data-Monthly.xlsx"
OUT_FILE = ROOT / "data" / "processed" / "panel_monthly.csv"

WEATHER_START = "19810101"  # earliest date NASA POWER accepts
ANALYSIS_START = "2000-01-01"  # CLAUDE.md 3: Vietnam's Robusta market is stable by then
# brl_usd has 65 NaN months before this date, so regressions that control for FX
# start here. The panel itself is still saved in full; notebooks do the filtering.
REGRESSION_START = "2006-03-01"

COLUMN_ORDER = [
    "arabica_usd_kg",
    "robusta_usd_kg",
    "frost_regions",
    "frost_days_total",
    "min_tmin",
    "rain_anom",
    "brl_usd",
]
WEATHER_COLUMNS = ["frost_regions", "frost_days_total", "min_tmin", "rain_anom"]


def build_panel(weather_end: str, analysis_start: str = ANALYSIS_START) -> pd.DataFrame:
    """Return the monthly panel of prices, frost exposure, rain anomaly and FX."""
    prices = load_pink_sheet(PRICE_FILE)

    # Features come from the full 1981+ history, because the frost percentile
    # needs the whole distribution even though only 2000+ is analysed.
    per_region = {
        name: monthly_features(fetch_weather(lat, lon, WEATHER_START, weather_end))
        for name, (lat, lon) in REGIONS.items()
    }
    weather = combine_regions(per_region)
    fx = fetch_fx(start=analysis_start)

    # Left join on prices: the panel exists per price month, and a month without
    # FX stays NaN rather than dropping a coffee observation.
    panel = prices.join(weather[WEATHER_COLUMNS], how="left").join(fx, how="left")
    panel = panel.loc[analysis_start:, COLUMN_ORDER]
    # Counts, so keep them integral; Int64 still allows NaN.
    panel["frost_regions"] = panel["frost_regions"].astype("Int64")
    panel["frost_days_total"] = panel["frost_days_total"].astype("Int64")
    panel.index.name = "month"
    return panel


def save_panel(panel: pd.DataFrame, out_file: Path = OUT_FILE) -> Path:
    """Write the panel to CSV and return the path written."""
    out_file.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(out_file)
    return out_file


def load_panel(path: Path = OUT_FILE) -> pd.DataFrame:
    """Read the saved panel back with the dtypes build_panel produced."""
    panel = pd.read_csv(path, index_col="month", parse_dates=["month"], date_format="%Y-%m-%d")
    for column in ("frost_regions", "frost_days_total"):
        panel[column] = panel[column].astype("Int64")
    return panel[COLUMN_ORDER]
