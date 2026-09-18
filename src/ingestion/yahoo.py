"""Fetch the BRL/USD exchange rate from Yahoo Finance."""

import pandas as pd
import yfinance as yf

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
    monthly.index.name = "date"
    return monthly
