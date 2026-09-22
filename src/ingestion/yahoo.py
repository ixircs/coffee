"""Fetch the BRL/USD exchange rate from Yahoo Finance."""

from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[2]
INTERIM_FILE = ROOT / "data" / "interim" / "brl_usd_monthly.csv"

TICKER = "BRL=X"  # BRL per 1 USD
COLUMN = "brl_usd"


def fetch_fx(ticker: str = TICKER, start: str = "2000-01-01", end: str | None = None) -> pd.DataFrame:
    """Return the monthly average exchange rate, indexed by month-start date."""
    raw = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=False)
    if raw.empty:
        raise RuntimeError(f"Yahoo Finance returned no rows for {ticker!r} ({start}..{end})")

    close = raw["Close"]
    if isinstance(close, pd.DataFrame):  # yfinance returns MultiIndex columns for one ticker too
        close = close.iloc[:, 0]

    # Monthly mean, not month-end close: a single day's spike should not stand in
    # for the rate coffee was actually traded at over the month.
    monthly = close.resample("MS").mean().to_frame(COLUMN)

    # The month in progress averages only the days elapsed so far, which would
    # enter the panel looking like a complete month. Drop it.
    current_month = pd.Timestamp.today().normalize().replace(day=1)
    monthly = monthly.drop(index=current_month, errors="ignore")

    monthly.index.name = "date"
    return monthly


if __name__ == "__main__":
    fx = fetch_fx()
    # build_panel downloads FX itself; this checkpoint only makes the step inspectable.
    INTERIM_FILE.parent.mkdir(parents=True, exist_ok=True)
    fx.to_csv(INTERIM_FILE)
    missing = int(fx[COLUMN].isna().sum())
    print(f"{INTERIM_FILE.relative_to(ROOT)}  {len(fx)} rows  "
          f"({fx.index.min():%Y-%m} to {fx.index.max():%Y-%m}, {missing} months missing)")
