"""Load coffee prices from the World Bank Pink Sheet (monthly)."""

from pathlib import Path

import pandas as pd

SHEET_NAME = "Monthly Prices"
NAMES_ROW = 4  # commodity names; the units row sits directly below it
DATA_START_ROW = 6

COLUMNS = {
    "Coffee, Arabica": "arabica_usd_kg",
    "Coffee, Robusta": "robusta_usd_kg",
}
EXPECTED_UNIT = "($/kg)"


def load_pink_sheet(path: str | Path) -> pd.DataFrame:
    """Return monthly Arabica and Robusta prices (USD/kg) indexed by month-start date."""
    header = pd.read_excel(
        path, sheet_name=SHEET_NAME, header=None, skiprows=NAMES_ROW, nrows=2
    )
    names, units = header.iloc[0], header.iloc[1]

    df = pd.read_excel(path, sheet_name=SHEET_NAME, header=None, skiprows=DATA_START_ROW)
    df.columns = list(names)
    df = df.rename(columns={df.columns[0]: "date"})

    missing = [c for c in COLUMNS if c not in df.columns]
    if missing:
        raise KeyError(f"Columns not found in '{SHEET_NAME}': {missing}")

    # Fail loudly if the World Bank ever changes the units of the coffee series.
    for name in COLUMNS:
        unit = str(units[list(names).index(name)]).strip()
        if unit != EXPECTED_UNIT:
            raise ValueError(f"Unexpected unit for '{name}': {unit!r}, expected {EXPECTED_UNIT!r}")

    # Drop trailing footnote/blank rows that don't look like "1960M01".
    df = df[df["date"].astype(str).str.fullmatch(r"\d{4}M\d{2}")]

    df["date"] = pd.to_datetime(df["date"].str.replace("M", "-"), format="%Y-%m")
    out = df.set_index("date")[list(COLUMNS)].rename(columns=COLUMNS)
    # Missing values in the Pink Sheet are the ellipsis "…"; coerce them to NaN.
    out = out.apply(pd.to_numeric, errors="coerce").astype("float64")
    out.index.name = "date"
    return out.sort_index()
