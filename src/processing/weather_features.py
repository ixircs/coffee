"""Turn daily point weather into monthly frost and rainfall features."""

import numpy as np
import pandas as pd

FROST_PERCENTILE = 2.0  # of the historical Jun-Aug T2M_MIN distribution, per location
WINTER_MONTHS = (6, 7, 8)


def frost_threshold(daily: pd.DataFrame, percentile: float = FROST_PERCENTILE) -> float:
    """Return the T2M_MIN cutoff for one location, from its own Jun-Aug history."""
    winter = daily.loc[daily.index.month.isin(WINTER_MONTHS), "T2M_MIN"]
    return float(np.nanpercentile(winter.dropna(), percentile))


def monthly_features(daily: pd.DataFrame, percentile: float = FROST_PERCENTILE) -> pd.DataFrame:
    """Aggregate one location's daily weather to monthly frost days, rain anomaly and mean temp."""
    threshold = frost_threshold(daily, percentile)
    # Flag on daily data first: a monthly mean would bury a single cold night.
    # A NaN day compares False, so mask it back out — otherwise missing data
    # would be indistinguishable from an observed warm day.
    is_frost = (daily["T2M_MIN"] <= threshold).where(daily["T2M_MIN"].notna())

    # min_count=1 keeps an all-missing month as NaN instead of a confident 0,
    # which would otherwise read as "no frost" and "no rain at all".
    monthly = pd.DataFrame(
        {
            "frost_days": is_frost.resample("MS").sum(min_count=1),
            "rain_mm": daily["PRECTOTCORR"].resample("MS").sum(min_count=1),
            "temp_c": daily["T2M"].resample("MS").mean(),
        }
    )
    # Anomaly against the same calendar month, so seasonality is not read as a shock.
    normal = monthly.groupby(monthly.index.month)["rain_mm"].transform("mean")
    monthly["rain_anom"] = monthly["rain_mm"] - normal
    monthly.index.name = "date"
    return monthly


def combine_regions(per_region: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Collapse per-region monthly features into one row per month."""
    # NaN > 0 is False, so mask unknown months back to NaN before counting.
    hit = [m["frost_days"].gt(0).where(m["frost_days"].notna()) for m in per_region.values()]
    rain = [m["rain_anom"] for m in per_region.values()]
    temp = [m["temp_c"] for m in per_region.values()]

    # Count of regions hit (0-3) rather than a mean: averaging temperatures lets
    # two warm regions cancel a frost in the third. min_count covers every region,
    # so a month one region does not reach stays NaN rather than counting as 0 hit.
    combined = pd.DataFrame(
        {
            "frost_regions": pd.concat(hit, axis=1).sum(axis=1, min_count=len(hit)),
            "rain_anom": pd.concat(rain, axis=1).mean(axis=1),
            "temp_c": pd.concat(temp, axis=1).mean(axis=1),
        }
    )
    combined.index.name = "date"
    return combined
