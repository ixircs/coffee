"""Event study on the Arabica-Robusta log price gap, run identically per event.

One gap series gives one observation per month, so a dummy per event-time month
would saturate the design (31 months, 31 parameters) and produce a perfect fit
with meaningless standard errors. Post-event months are therefore binned, which
also matches the question being asked: is the effect transient or persistent?
"""

import numpy as np
import pandas as pd
import statsmodels.api as sm

PRE_MONTHS = 12  # short window: pre-trends only hold this close to the event
POST_MONTHS = 18  # CLAUDE.md 3: the effect peaks ~11 months out
# Newey-West rule of thumb, maxlags = 4*(T/100)^(2/9): T=31 gives 3. A blanket 12
# ignored sample size and broke down, producing SEs smaller than plain OLS.
HAC_LAGS = 3
POST_BINS = {"post_0_5": (0, 5), "post_6_11": (6, 11), "post_12_18": (12, 18)}


def _gap(panel: pd.DataFrame) -> pd.Series:
    """Return log(arabica) - log(robusta), the DiD outcome."""
    return np.log(panel["arabica_usd_kg"]) - np.log(panel["robusta_usd_kg"])


def event_window(panel: pd.DataFrame, event: pd.Timestamp, pre: int = PRE_MONTHS,
                 post: int = POST_MONTHS) -> pd.DataFrame:
    """Return the panel around one event with an event-time column k (months from event)."""
    period = pd.Timestamp(event).to_period("M")
    k = [(p - period).n for p in panel.index.to_period("M")]
    window = panel.assign(k=k)
    return window[(window.k >= -pre) & (window.k <= post)].copy()


def pretrend(panel: pd.DataFrame, event: pd.Timestamp, pre: int = PRE_MONTHS) -> dict:
    """Test whether the gap already trends in the months before the event."""
    sample = event_window(panel, event, pre=pre, post=0)
    sample = sample[sample.k < 0]
    X = sm.add_constant(pd.Series(sample.k.values, index=sample.index, name="k"))
    fit = sm.OLS(_gap(sample), X).fit()
    return {"pretrend_slope": fit.params["k"], "pretrend_p": fit.pvalues["k"]}


def gap_path(panel: pd.DataFrame, event: pd.Timestamp, pre: int = PRE_MONTHS,
             post: int = POST_MONTHS) -> pd.Series:
    """Return the raw gap by event-time month, normalised to the month before the event."""
    window = event_window(panel, event, pre=pre, post=post)
    gap = _gap(window)
    gap.index = window.k
    return gap - gap.loc[-1]


def event_effects(panel: pd.DataFrame, event: pd.Timestamp, pre: int = PRE_MONTHS,
                  post: int = POST_MONTHS, control_fx: bool = True,
                  control_trend: bool = True) -> pd.DataFrame:
    """Estimate binned post-event shifts in the log price gap against the pre-event baseline."""
    window = event_window(panel, event, pre=pre, post=post)
    y = _gap(window)

    X = pd.DataFrame(index=window.index)
    if control_trend:
        # The gap already drifts before some events; without a trend that drift
        # would be collected as a treatment effect.
        X["trend"] = window.k.values
    if control_fx:
        # FX moves Arabica (Brazil) and Robusta (Vietnam) differently, so it can
        # open the gap with no weather involved at all.
        X["log_brl"] = np.log(window["brl_usd"]).values
    for name, (lo, hi) in POST_BINS.items():
        X[name] = ((window.k >= lo) & (window.k <= hi)).astype(float).values

    fit = sm.OLS(y, sm.add_constant(X), missing="drop").fit(
        cov_type="HAC", cov_kwds={"maxlags": HAC_LAGS}
    )

    rows = []
    for name in POST_BINS:
        coef, se = fit.params[name], fit.bse[name]
        rows.append({
            "bin": name,
            "coef": coef,
            "se": se,
            "p": fit.pvalues[name],
            "pct": (np.exp(coef) - 1) * 100,
            "lo_pct": (np.exp(coef - 1.96 * se) - 1) * 100,
            "hi_pct": (np.exp(coef + 1.96 * se) - 1) * 100,
        })
    out = pd.DataFrame(rows).set_index("bin")
    out.attrs["nobs"] = int(fit.nobs)
    out.attrs["df_resid"] = int(fit.df_resid)
    return out


def event_effects_its(panel: pd.DataFrame, event: pd.Timestamp, pre: int = PRE_MONTHS,
                      post: int = POST_MONTHS, control_fx: bool = True) -> pd.DataFrame:
    """Estimate binned effects against a counterfactual trend fitted on the pre-period only.

    A trend fitted across pre AND post is near-collinear with an effect that ramps to
    a peak around month 11, so it absorbs part of what it should measure. Standard ITS
    practice instead projects the pre-event trend forward and measures deviations from it.
    """
    window = event_window(panel, event, pre=pre, post=post)
    gap = _gap(window)

    def design(sample: pd.DataFrame) -> pd.DataFrame:
        X = pd.DataFrame({"trend": sample.k.values}, index=sample.index)
        if control_fx:
            X["log_brl"] = np.log(sample["brl_usd"]).values
        return sm.add_constant(X)

    pre_sample = window[window.k < 0]
    baseline = sm.OLS(gap.loc[pre_sample.index], design(pre_sample), missing="drop").fit()

    # Counterfactual: what the gap would have been had the pre-event trend continued.
    counterfactual = baseline.predict(design(window))
    deviation = gap - counterfactual

    post_sample = window[window.k >= 0]
    bins = pd.DataFrame(
        {name: ((post_sample.k >= lo) & (post_sample.k <= hi)).astype(float).values
         for name, (lo, hi) in POST_BINS.items()},
        index=post_sample.index,
    )
    # No intercept: each coefficient is the mean deviation from the projected trend.
    fit = sm.OLS(deviation.loc[post_sample.index], bins, missing="drop").fit(
        cov_type="HAC", cov_kwds={"maxlags": HAC_LAGS}
    )

    rows = []
    for name in POST_BINS:
        coef, se = fit.params[name], fit.bse[name]
        rows.append({
            "bin": name,
            "coef": coef,
            "se": se,
            "p": fit.pvalues[name],
            "pct": (np.exp(coef) - 1) * 100,
            "lo_pct": (np.exp(coef - 1.96 * se) - 1) * 100,
            "hi_pct": (np.exp(coef + 1.96 * se) - 1) * 100,
        })
    out = pd.DataFrame(rows).set_index("bin")
    out.attrs["nobs"] = int(fit.nobs)
    out.attrs["pretrend_slope"] = baseline.params["trend"]
    # The second stage treats the projected trend as known, so these SEs do not
    # carry the first-stage uncertainty. Stated as a limitation, not hidden.
    return out


def compare_trend_specs(panel: pd.DataFrame, event: pd.Timestamp, **kwargs) -> pd.DataFrame:
    """Return both trend specifications for one event, stacked for side-by-side reading."""
    versions = {
        "(a) tren full-window": event_effects(panel, event, **kwargs),
        "(b) tren pre-only": event_effects_its(panel, event, **kwargs),
    }
    frames = []
    for label, effects in versions.items():
        frame = effects[["coef", "se", "p", "pct"]].copy()
        frame["versi"] = label
        frames.append(frame.reset_index())
    out = pd.concat(frames)
    out["event"] = f"{pd.Timestamp(event):%Y-%m}"
    return out.set_index(["event", "versi", "bin"])


def summarise(panel: pd.DataFrame, event: pd.Timestamp, **kwargs) -> dict:
    """Condense one event into the row the comparison table needs."""
    effects = event_effects(panel, event, **kwargs)
    path = gap_path(panel, event)
    post_path = path[path.index >= 0]
    return {
        **pretrend(panel, event),
        "0-5 bln %": effects.loc["post_0_5", "pct"],
        "0-5 p": effects.loc["post_0_5", "p"],
        "6-11 bln %": effects.loc["post_6_11", "pct"],
        "6-11 p": effects.loc["post_6_11", "p"],
        "12-18 bln %": effects.loc["post_12_18", "pct"],
        "12-18 p": effects.loc["post_12_18", "p"],
        "puncak mentah %": (np.exp(post_path.max()) - 1) * 100,
        "puncak di bulan": int(post_path.idxmax()),
        "n": effects.attrs["nobs"],
    }
