"""Walk-forward forecasting of Arabica prices: naive, ARIMA and SARIMAX with lagged weather.

Leakage rule: a regressor lagged L months is known at origin O for a target month
O+h only when L >= h. Anything with L < h would require knowing the regressor's
future value, so it is dropped for that horizon rather than forecast separately.
"""

import warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.statespace.sarimax import SARIMAX

TARGET = "arabica_usd_kg"
FIRST_ORIGIN = "2018-01-01"
HORIZONS = (1, 3, 6)
ARIMA_GRID = [(p, 1, q) for p in range(3) for q in range(3)]

# regressor -> lags in months
EXOG_LAGS = {
    "frost_days_total": (6, 12),
    "min_tmin": (6, 12),
    "rain_anom": (3, 6),
    "log_brl": (1,),
}


def build_exog(panel: pd.DataFrame) -> pd.DataFrame:
    """Return the lagged exogenous regressors, one column per regressor-lag pair."""
    source = panel.copy()
    source["log_brl"] = np.log(source["brl_usd"])
    columns = {}
    for name, lags in EXOG_LAGS.items():
        for lag in lags:
            # Cast first: frost counts are nullable Int64, which would make the whole
            # exog matrix dtype object and fail inside statsmodels' linear algebra.
            columns[f"{name}_lag{lag}"] = source[name].astype("float64").shift(lag)
    return pd.DataFrame(columns, index=panel.index, dtype="float64")


def usable_exog(horizon: int) -> list[str]:
    """Return regressors whose lag is at least the horizon, i.e. known at the origin."""
    return [f"{name}_lag{lag}" for name, lags in EXOG_LAGS.items()
            for lag in lags if lag >= horizon]


def assert_no_leakage(origin: pd.Timestamp, horizon: int, columns: list[str]) -> None:
    """Fail loudly if any regressor would need data published after the origin."""
    for column in columns:
        lag = int(column.rsplit("lag", 1)[1])
        needed = (origin.to_period("M") + horizon - lag).to_timestamp()
        if needed > origin:
            raise AssertionError(
                f"Leakage: {column} for target {origin.to_period('M') + horizon} "
                f"needs {needed:%Y-%m}, which is after origin {origin:%Y-%m}"
            )


def pick_arima_order(train: pd.Series) -> tuple[int, int, int]:
    """Return the (p, d, q) with the lowest AIC on this training sample."""
    best, best_aic = (1, 1, 0), np.inf
    for order in ARIMA_GRID:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                aic = ARIMA(train, order=order).fit().aic
        except Exception:
            continue
        if aic < best_aic:
            best, best_aic = order, aic
    return best


def walk_forward(panel: pd.DataFrame, first_origin: str = FIRST_ORIGIN,
                 horizons: tuple[int, ...] = HORIZONS) -> pd.DataFrame:
    """Refit every model at every origin and return one row per origin-horizon-model."""
    y = np.log(panel[TARGET])
    exog_all = build_exog(panel)
    origins = panel.index[(panel.index >= pd.Timestamp(first_origin))]
    rows, failures = [], []

    for origin in origins:
        train = y.loc[:origin]
        if len(train) < 24:
            continue
        order = pick_arima_order(train)

        for horizon in horizons:
            target_date = (origin.to_period("M") + horizon).to_timestamp()
            if target_date not in panel.index:
                continue
            actual = panel.loc[target_date, TARGET]

            # 1. naive: today's price is the forecast for every horizon
            preds = {"naif": float(train.iloc[-1])}

            # 2. ARIMA, order re-selected on this origin's training sample
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    fit = ARIMA(train, order=order).fit()
                preds["ARIMA"] = float(fit.forecast(steps=horizon).iloc[-1])
            except Exception as exc:
                preds["ARIMA"] = np.nan
                failures.append({"origin": origin, "horizon": horizon, "model": "ARIMA", "error": repr(exc)})

            # 3. SARIMAX with lagged weather, only regressors known at the origin
            columns = usable_exog(horizon)
            assert_no_leakage(origin, horizon, columns)
            try:
                exog_train = exog_all.loc[train.index, columns]
                future = pd.period_range(origin.to_period("M") + 1, periods=horizon, freq="M")
                exog_future = exog_all.loc[[p.to_timestamp() for p in future], columns]
                usable = exog_train.notna().all(axis=1)
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    sarimax = SARIMAX(train[usable], exog=exog_train[usable], order=order,
                                      enforce_stationarity=False, enforce_invertibility=False).fit(disp=False)
                preds["SARIMAX"] = float(sarimax.forecast(steps=horizon, exog=exog_future).iloc[-1])
            except Exception as exc:
                preds["SARIMAX"] = np.nan
                failures.append({"origin": origin, "horizon": horizon, "model": "SARIMAX", "error": repr(exc)})

            for model, log_pred in preds.items():
                rows.append({
                    "origin": origin,
                    "horizon": horizon,
                    "model": model,
                    "target_date": target_date,
                    "actual": actual,
                    # Back-transform: metrics are reported in USD/kg, not log points.
                    "pred": np.exp(log_pred) if np.isfinite(log_pred) else np.nan,
                    "arima_order": str(order),
                    "n_exog": len(columns),
                })
    out = pd.DataFrame(rows)
    # Surfaced, never swallowed: a model that silently fails everywhere would
    # otherwise look like a missing row rather than a bug.
    out.attrs["failures"] = pd.DataFrame(failures)
    return out


def score(predictions: pd.DataFrame) -> pd.DataFrame:
    """Return MAE, RMSE, MAPE in USD/kg plus the MAE ratio against the naive baseline."""
    rows = []
    for (horizon, model), group in predictions.groupby(["horizon", "model"]):
        group = group.dropna(subset=["pred"])
        error = group.pred - group.actual
        rows.append({
            "horizon": horizon,
            "model": model,
            "n": len(group),
            "MAE": error.abs().mean(),
            "RMSE": np.sqrt((error**2).mean()),
            "MAPE_pct": (error.abs() / group.actual).mean() * 100,
        })
    table = pd.DataFrame(rows)
    naive = table[table.model == "naif"].set_index("horizon")["MAE"]
    table["MAE_vs_naif"] = table.apply(lambda r: r.MAE / naive.loc[r.horizon], axis=1)
    return table.set_index(["horizon", "model"]).sort_index()
