"""Fetch daily futures closes from Yahoo Finance for the daily event study."""

from pathlib import Path

import pandas as pd
import yfinance as yf

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"

TREATED = "KC=F"  # Arabica coffee futures, US cents/lb
CONTROLS = ("CC=F", "CT=F")  # cocoa, cotton: soft commodities outside Brazil's frost belt
TICKERS = (TREATED, *CONTROLS)


def fetch_daily(ticker: str, start: str, end: str | None = None,
                raw_dir: str | Path = RAW_DIR, use_cache: bool = True) -> pd.Series:
    """Return the daily close for one ticker, archiving the raw response as CSV."""
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    safe = ticker.replace("=", "_")
    out_file = raw_dir / f"yahoo_daily_{safe}_{start}_{end or 'today'}.csv"

    if use_cache and out_file.exists():
        raw = pd.read_csv(out_file, index_col=0)
    else:
        raw = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=False)
        if raw.empty:
            # Never substitute another ticker silently: the control set is a design choice.
            raise RuntimeError(f"Yahoo Finance returned no rows for {ticker!r} ({start}..{end})")
        # yfinance returns a MultiIndex header that does not survive a CSV round-trip,
        # so flatten it to OHLCV before archiving. The values are untouched.
        if isinstance(raw.columns, pd.MultiIndex):
            raw = raw.droplevel(1, axis=1)
        raw.index.name = "date"
        raw.to_csv(out_file)

    close = raw["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    close.index = pd.to_datetime(close.index, format="%Y-%m-%d")
    close.index.name = "date"
    return close.rename(ticker).astype("float64").sort_index()


def load_daily_prices(tickers: tuple[str, ...] = TICKERS, start: str = "2015-01-01",
                      end: str | None = None, **kwargs) -> tuple[pd.DataFrame, dict[str, str]]:
    """Return closes for every ticker that downloaded, plus a dict of the ones that failed."""
    series, failed = {}, {}
    for ticker in tickers:
        try:
            series[ticker] = fetch_daily(ticker, start=start, end=end, **kwargs)
        except Exception as exc:  # reported to the caller, never swapped for a substitute
            failed[ticker] = str(exc)
    return pd.DataFrame(series).sort_index(), failed


def log_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Return log differences of closes, dropping the first row."""
    import numpy as np

    return np.log(prices).diff().dropna(how="all")
