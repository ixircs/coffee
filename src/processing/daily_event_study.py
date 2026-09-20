"""Daily event study: abnormal returns of coffee futures around frost dates.

Short windows are the point of this design: drought and the biennial bearing cycle
move over months, so they are near-constant across a few weeks and cannot masquerade
as the event the way they do at monthly frequency.
"""

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

EST_START = -130  # trading days relative to the event
EST_END = -11  # inclusive, so the estimation window is 120 trading days
EVENT_START = -10
EVENT_END = 60
CAR_HORIZONS = (5, 10, 20, 60)


def event_index(dates: pd.DatetimeIndex, event_date: pd.Timestamp) -> int:
    """Return the position of the first trading day on or after the event date."""
    position = dates.searchsorted(pd.Timestamp(event_date))
    if position >= len(dates):
        raise ValueError(f"No trading day on or after {event_date}")
    return int(position)


def abnormal_returns(returns: pd.DataFrame, treated: str, control: str,
                     event_date: pd.Timestamp, market_model: bool = True) -> dict:
    """Return abnormal returns around one event, plus the estimation-window residual sd."""
    dates = returns.index
    t0 = event_index(dates, event_date)

    est = returns.iloc[t0 + EST_START: t0 + EST_END + 1]
    window = returns.iloc[t0 + EVENT_START: t0 + EVENT_END + 1]
    if len(est) < abs(EST_START) - abs(EST_END):
        raise ValueError(f"Estimation window incomplete for {event_date}")

    if market_model:
        fit = sm.OLS(est[treated], sm.add_constant(est[control])).fit()
        alpha, beta = fit.params["const"], fit.params[control]
        ar_est = est[treated] - (alpha + beta * est[control])
        ar = window[treated] - (alpha + beta * window[control])
    else:
        # Raw difference: imposes alpha=0, beta=1 instead of estimating them.
        alpha, beta = 0.0, 1.0
        ar_est = est[treated] - est[control]
        ar = window[treated] - window[control]

    k = np.arange(EVENT_START, EVENT_START + len(ar))
    ar = pd.Series(ar.values, index=k, name="AR")
    return {
        "ar": ar,
        "car": ar[ar.index >= 0].cumsum(),
        "sigma_ar": float(ar_est.std(ddof=2 if market_model else 1)),
        "n_est": len(est),
        "alpha": float(alpha),
        "beta": float(beta),
        "t0_date": dates[t0],
    }


def car_table(result: dict, horizons: tuple[int, ...] = CAR_HORIZONS) -> pd.DataFrame:
    """Return CAR, t-statistic and p-value at each horizon."""
    rows = []
    df = result["n_est"] - 2
    for k in horizons:
        if k not in result["car"].index:
            continue
        car = float(result["car"].loc[k])
        # Under the null the AR are iid, so the variance of a (k+1)-day sum scales linearly.
        t_stat = car / (result["sigma_ar"] * np.sqrt(k + 1))
        rows.append({
            "horizon": f"CAR+{k}",
            "car_log": car,
            "car_pct": (np.exp(car) - 1) * 100,
            "t": t_stat,
            "p": 2 * (1 - stats.t.cdf(abs(t_stat), df=df)),
        })
    return pd.DataFrame(rows).set_index("horizon")


def run_events(returns: pd.DataFrame, treated: str, control: str,
               events: dict[str, pd.Timestamp]) -> tuple[pd.DataFrame, dict]:
    """Run both specifications for every event and return a stacked table plus raw results."""
    tables, results = [], {}
    for label, date in events.items():
        for market_model, version in ((True, "(a) market model"), (False, "(b) selisih mentah")):
            result = abnormal_returns(returns, treated, control, date, market_model=market_model)
            table = car_table(result).assign(event=label, versi=version)
            tables.append(table.reset_index())
            results[(label, version)] = result
    stacked = pd.concat(tables).set_index(["event", "versi", "horizon"])
    return stacked, results
