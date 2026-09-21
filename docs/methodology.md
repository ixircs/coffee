# Methodology

Decisions, their rationale, and what was tried and rejected. Results are summarised
in the [README](../README.md); the analysis itself lives in `notebooks/`.

- [1. Research question and identification strategy](#1-research-question-and-identification-strategy)
- [2. Data sources](#2-data-sources)
- [3. Methodological decisions](#3-methodological-decisions)
- [4. Tried and rejected](#4-tried-and-rejected)
- [5. Limitations](#5-limitations)

---

## 1. Research question and identification strategy

**How large and how long-lasting is the effect of Brazilian weather shocks on global
coffee prices?**

Sub-questions:

1. Magnitude and duration of the July 2021 Brazil frost effect on Arabica prices, net of
   global trends and FX.
2. Spillover: does Robusta rise too, and with what lag?
3. Anticipation and market efficiency: how fast do prices absorb frost news?
4. Can weather anomalies improve price forecasts over a naive or ARIMA baseline?

**Treated:** Arabica, grown in Brazil's frost-exposed south-east.
**Control:** a series not exposed to the same frost (see below — the control changed when
the design changed).
**Event:** the Brazil frost of **20 July 2021**, documented by the International Coffee
Organization (ICO).

The project uses two designs:

| Design | Frequency | Control | Role |
|---|---|---|---|
| Difference-in-differences on the Arabica–Robusta log price gap | monthly | Robusta (Vietnam, Indonesia) | **Rejected** — documents why the design changed (§4) |
| Event study with a market model | daily | mean of cocoa (`CC=F`) and cotton (`CT=F`) futures | **Primary** causal estimate |

Both designs apply one identical specification to one treated event (2021-07) and two
placebo events (2016-07, 2019-07). Events are classified as treated or placebo from
supply-side evidence only — never from the price response, which would make the test
circular.

---

## 2. Data sources

| Source | Series | Frequency | Accessed | Vintage / notes |
|---|---|---|---|---|
| World Bank Commodity Price Data ("Pink Sheet") | Coffee, Arabica; Coffee, Robusta | monthly | by 2026-09-17 | file header: "Updated on September 02, 2026" |
| NASA POWER daily point API | `T2M_MIN`, `T2M_MAX`, `T2M`, `PRECTOTCORR` | daily | 2026-09-18 | `community=AG`, 1981-01-01 to 2026-08-31 |
| Yahoo Finance via `yfinance` | `BRL=X` | daily → monthly mean | 2026-09-18 | see gaps below |
| Yahoo Finance via `yfinance` | `KC=F`, `CC=F`, `CT=F` | daily | 2026-09-20 | 2015-01-02 to 2026-09-18 |
| ICO Coffee Market Reports | Jul 2016, Jul 2019, Jul 2021, May 2022 | monthly reports | 2026-09-19 | links in [`data/events.csv`](../data/events.csv) |

### 2.1 World Bank Pink Sheet

- Sheet `Monthly Prices`. **Two header rows**: row index 4 holds commodity names, row
  index 5 holds units. Data starts at row index 6.
- Both coffee series are in **USD/kg**, so they are directly comparable.
- Dates are formatted `1960M01`.
- Missing values are the ellipsis character `…`, not blank cells. The coffee columns are
  complete; other commodities are not.
- Columns are selected by name and the unit row is checked on load, so an inserted column
  or a change of unit raises an error instead of silently shifting the series.

### 2.2 NASA POWER

Three Arabica regions:

| Region | Latitude | Longitude | Note |
|---|---|---|---|
| Sul de Minas | −21.55 | −45.43 | highest frost risk, elevation ~869 m |
| Cerrado Mineiro | −18.94 | −46.99 | further north, less frost |
| Mogiana (São Paulo) | −20.54 | −47.40 | frost-prone |

- The earliest accepted `start` is **1981-01-01**, verified 2026-09-18. Earlier dates
  return HTTP 422: *"Your start date out of range. The data starts at 1981/01/01."*
- `-999.0` is the API's missing-value marker and is converted to NaN. Left in place it
  would pull monthly means far below zero and corrupt the frost percentile.
- Units: °C and mm/day, local solar time.
- ⚠️ **Resolution: the MERRA-2 grid is ~50 km, and `T2M` is measured at 2 m.** Localised
  sub-zero minima at plant level are smoothed away. The coldest grid reading in July 2021
  at Sul de Minas was **3.05 °C** during a frost that destroyed trees. This caveat drives
  several decisions in §3.

### 2.3 Yahoo Finance

- `BRL=X` (BRL per USD) is a required confounder control: Brazilian farmers sell in USD but
  pay costs in BRL, so the exchange rate moves coffee prices with no weather involved.
- ⚠️ **`BRL=X` history is incomplete**, verified 2026-09-18. It starts in **2003-12**, not
  2000, and has an 18-month hole from **2004-09 to 2006-02**. Together that leaves 65
  empty months in the 2000–2026 panel. The gaps are kept as NaN rather than interpolated.
- The month in progress is dropped from the monthly FX series, because its mean covers only
  the days elapsed so far.
- `KC=F` is priced in US cents/lb, unlike the Pink Sheet's USD/kg. It is used only in the
  daily design, where returns make the unit irrelevant.

### 2.4 ICO Coffee Market Reports — primary-source verification

The ICO July 2021 report was obtained and read directly:

| Fact | Value | Page |
|---|---|---|
| Frost date | **20 July 2021** — the only date the report names | 1, 3 |
| NY Arabica futures | 165.65 → 207.80 US c/lb, **+25.4% in one week** (20→26 July) | 3 |
| ICO composite price, July 2021 average | 152.24 US c/lb, highest since November 2014 | 1 |
| Intra-day volatility | Arabica peaked at 17% after the frost; Robusta 7.7% → 11% | 3 |
| Arabica–Robusta arbitrage | 83.26 → 87.39 US c/lb (+5%) | 3 |
| Severity | "one of the most intense frosts in living memory" | 5 |
| Mechanism | trees destroyed, with production effects "from crop year 2022/23 onwards" | 5 |

Yahoo's `KC=F` reproduces the ICO figures: 165.65 on 20 July and 207.80 on 26 July 2021,
a move of +25.45%.

For the placebo months, the ICO reports describe a frost **scare** without damage:

| Month | ICO wording | ICO composite |
|---|---|---|
| 2016-07 | "a second frost scare in Brazil", then "the threat of frost in Brazil receded" | 132.98 |
| 2019-07 | "Concerns over frost … dissipated by the end of the month"; title "Global coffee prices drift downwards" | 103.01 |
| 2021-07 | "one of the most intense frosts in living memory"; tree damage | 152.24 |

All three months show frost in all three regions of the weather data, so the weather
indicator is not detecting noise. The difference is scare versus damage.

---

## 3. Methodological decisions

### 3.1 Frost definition: percentile per location, not an absolute threshold

A day counts as frost when `T2M_MIN` falls at or below the **2nd percentile of that
location's own June–August distribution, 1981–2026**. Resulting thresholds: Sul de Minas
6.06 °C, Cerrado Mineiro 7.07 °C, Mogiana 7.35 °C.

**Why:** the absolute threshold detects nothing (§4.1). A per-location percentile asks
"how unusually cold was this for this grid cell" instead of "was it below freezing", which
the grid cannot resolve. The flag is computed on **daily** data before aggregating, because
a monthly mean would bury a single cold night.

The weather features **characterise** events; they do not **identify** them (§3.2).

### 3.2 Event dating: documented sources choose the events, an objective rule dates them

- **Which months are events, and whether each is a treatment or a placebo,** comes from ICO
  reports, not from the weather data. No percentile threshold separates the catastrophic
  July 2021 freeze from the minor May 2022 cold snap (§4.1), so the weather cannot decide
  which cold spell mattered.
- **The day within each month** comes from one objective rule, applied identically to all
  three events: the day with the lowest `T2M_MIN` across the three regions.
- The rule was validated on the documented case before it was applied to the others. For
  July 2021 it returns **2021-07-20**, the ICO date, without that date being an input.

| Event | Rule output | T2M_MIN | Region |
|---|---|---|---|
| 2016-07 | 2016-07-18 | 4.13 °C | Mogiana |
| 2019-07 | 2019-07-07 (Sunday → first trading day 2019-07-08) | 3.98 °C | Sul de Minas |
| 2021-07 | **2021-07-20** | 3.05 °C | Sul de Minas |

NASA POWER shows a second cold reading on 30 July 2021 (3.19 °C). ICO documents only
20 July, so 30 July is **not** treated as an event: grid data cannot establish severity.

### 3.3 Aggregating the three regions

`frost_regions` counts how many of the three regions had at least one frost day in the
month (0–3).

- **Not a mean temperature,** because two warm regions would cancel a frost in the third.
- **Not a binary "any region" flag,** because it cannot tell one region from three.
- **Not production-weighted,** because regional production shares were not collected.

`frost_regions` saturates at 3: June and July 2021 both score 3 despite 3 versus 13 frost
days. Two further columns keep intensity and severity:

- `frost_days_total`: frost days summed across regions.
- `min_tmin`: the coldest night in any region that month.

`frost_regions = 3` occurs in **25 of 548 months** since 1981.

Missing data never counts as "no frost": a month without observations, or a region missing
a month, stays NaN instead of reading as zero.

### 3.4 Analysis window

- **Monthly panel: 2000-01 to 2026-08.** Vietnam's Robusta industry was established by
  2000, so the control group's market structure is stable.
- **Regressions: 2006-03 onward** (`REGRESSION_START`). `brl_usd` has 65 empty months before
  that date (§2.3), and regressions controlling for FX need a complete series. The panel is
  still saved in full; notebooks do the filtering.
- **Raw weather: from 1981.** The frost percentile needs the whole distribution: download
  wide, analyse narrow.
- **Monthly event window: 12 months before, 18 after.** The monthly price gap peaked about
  11 months after the July 2021 frost, consistent with ICO's statement that production
  effects land in crop year 2022/23.
- **Daily windows:** estimation t−130 to t−11 trading days (120 days); event t−10 to t+60.

### 3.5 HAC standard errors: lag length scales with sample size

Where HAC standard errors are used, `maxlags = 4·(T/100)^(2/9)`, the Newey–West rule of
thumb. T=31 gives 3.08, so **3**.

Even with this rule, the monthly DiD reports **no p-values**. With n=31, one event and
autocorrelated residuals, no standard-error estimator is dependable. At T=19, HAC with 3
lags still returned standard errors below plain OLS. Trying estimators until one gives a
usable p-value would be results-driven selection, so the monthly design reports coefficient
magnitudes and their instability only.

### 3.6 Forecasting: exogenous regressors are lagged, never contemporaneous

When forecasting next month's price, next month's weather is unknown. The forecasting
models therefore use only lagged regressors, with lags fixed before any model was run:

| Regressor | Lags (months) | Mechanism |
|---|---|---|
| `frost_days_total`, `min_tmin` | 6, 12 | a July frost damages the following year's harvest |
| `rain_anom` | 3, 6 | drought affects flowering and fruit fill over months |
| `log(brl_usd)` | 1 | FX acts quickly through farmers' selling decisions |

A regressor lagged L months is known at forecast origin O for target O+h only when
**L ≥ h**. Regressors failing that test are dropped for that horizon, not forecast
separately: h=1 uses 7 regressors, h=3 uses 6, h=6 uses 5.

Validation is a walk-forward expanding window from 2018-01, refitting every model at every
origin (103 origins). Leakage is checked on the **values** at every origin, by recomputing
each regressor from the raw panel with date arithmetic, not only on column names.

---

## 4. Tried and rejected

### 4.1 An absolute frost threshold of 2 °C

**Result: zero frost days detected in July 2021.** The coldest grid reading was 3.05 °C.

The percentile definition that replaced it was then tested against the known ranking of
events. According to ICO and press reports, July 2021 was devastating and May 2022 was
minor. **No threshold reproduced that ranking:**

| Percentile | Mean threshold | Jul 2021 frost days | May 2022 frost days | Ranks correctly? |
|---|---|---|---|---|
| 0.25% | 3.68 °C | 0 | 3 | No |
| 0.5% | 4.69 °C | 4 | 7 | No |
| 1% | 5.85 °C | 9 | 9 | Tie |
| 2% | 6.82 °C | 13 | 14 | No |
| 5% | 8.07 °C | 16 | 16 | Tie |
| Degree-days below 2% | — | 22.0 | 27.5 | No |

The coldest daily minima at Sul de Minas were nearly identical: 3.05, 3.19, 4.10 and
5.26 °C in July 2021, against 3.47, 3.59, 5.50 and 5.61 °C in May 2022.

The data cannot separate the two because:

1. ~50 km grid smoothing erases the localised sub-zero minima that cause damage.
2. `T2M` is measured at 2 m; the plant-level surface is colder.
3. Damage depends on frost **interacting** with prior drought stress and tree condition,
   which temperature alone does not capture.

**Consequence:** the threshold was not tuned until July 2021 looked worst. That would be
results-driven selection. Events are dated from documented sources instead (§3.2).

### 4.2 Monthly difference-in-differences

Outcome: `gap_t = log(arabica_t) − log(robusta_t)`, estimated per event with post-event
bins (0–5, 6–11, 12–18 months), a time trend and `log(brl_usd)`.

**Parallel trends fail beyond 18 months:**

| Pre-event window | Slope per month | p | R² | Parallel? |
|---|---|---|---|---|
| 12 months | 0.0039 | 0.138 | 0.21 | yes |
| 18 months | 0.0040 | 0.077 | 0.18 | marginal |
| 24 months | 0.0097 | <0.0001 | 0.59 | no |
| 36 months | 0.0132 | <0.0001 | 0.87 | no |
| 48 months | 0.0117 | <0.0001 | 0.91 | no |

(Plain OLS on the pre-event gap, before any HAC decision.)

Over 36 months the pre-trend accumulates to +61%, larger than the effect being measured.
Two Arabica-specific supply shocks preceded the frost: the 2020–21 drought and an
anticipated biennial off-year. The 12-month window was not chosen because it passes.

**Estimates are unstable across a defensible specification change.** Fitting the trend on
the pre-period only (interrupted-time-series practice) instead of the full window moves the
estimates substantially:

| Event | Bin | Full-window trend | Pre-only trend |
|---|---|---|---|
| 2021-07 damage | 6–11 months | +11.4% | +7.2% |
| 2021-07 damage | 12–18 months | +1.1% | −3.5% |
| 2019-07 scare | 6–11 months | +7.4% | +19.4% |
| 2019-07 scare | 12–18 months | −1.2% | +14.9% |

**The placebos are uninterpretable, not merely large.** The 2019 post-event window
(Jul 2019 – Jan 2021) overlaps the 2021 pre-event window (Jul 2020 – Jun 2021) by seven
months. The 2016 placebo is dominated by the long 2017–18 Arabica decline (−26%).

**Why the design was dropped:** at monthly resolution the drought, the biennial off-year and
the frost merge into one rising line, and there is no room for a non-overlapping placebo.
The only result stable across specifications is the **sign** of the 2021 estimate at
6–11 months. See [`notebooks/02_causal_did.ipynb`](../notebooks/02_causal_did.ipynb).

### 4.3 HAC standard errors with `maxlags = 12`

The first version of the monthly DiD used a blanket 12 lags. At T=19, the second stage of
the pre-only trend model, standard errors **shrank** as lags were added:

| Estimator | SE, 6–11 month bin |
|---|---|
| Plain OLS | 0.0185 |
| HAC, 3 lags | 0.0052 |
| HAC, 12 lags | 0.0034 |
| Naive `sd/√n` | 0.0081 |

A HAC correction for positively autocorrelated residuals should **increase** standard
errors. Getting a result below both OLS and `sd/√n` means the estimator broke down on a
small sample. It was not extra precision. **Every p-value computed with 12 lags was
withdrawn.**

### 4.4 An event study with one dummy per event-time month

The first monthly event-study specification was `gap ~ C(k)`, k ∈ [−12, +18], with k = −1
as reference. That is a panel design: per-period dummies are identified only when several
units are observed in each period. With one gap series there is one observation per month,
so 31 dummies on 31 observations gave a **saturated model**: R² = 1, zero residual degrees
of freedom, and a spurious p = 0.000 everywhere. Adding Arabica and Robusta as two units does
not help, because month fixed effects absorb all common variation and leave exactly the
gap. Post-event **bins** replaced the dummies.

---

## 5. Limitations

**Identification**

- **One treated event.** A single damaging frost in 11 years of daily data. The CAR+5
  estimate is strong, but it does not generalise to "damaging frosts" in general.
- **The 2016-07 placebo is confounded.** ICO reports a Colombian truckers' strike and BRL
  moves in the same month.
- **Biennial bearing.** ICO describes 2021/22 as an off year in Arabica's two-year production
  cycle, so part of the price rise was anticipated before the frost. The cycle is
  Arabica-specific, so it moves the treated series and not the control. The short daily
  window largely isolates the dated frost from this gradual cycle, but does not remove it.
- **COVID-19 and Robusta.** In July–September 2021, Vietnam's Delta-wave lockdown disrupted
  Robusta exports, lifting the monthly control group in the same months as the frost.

**Weather data**

- **The ~50 km grid cannot rank severity.** It confirms that July 2021 was cold but cannot
  distinguish a damaging frost from a harmless cold snap (§4.1).
- **The 30 July 2021 reading.** The market fell sharply that day. That is *consistent with*
  the cold not being a second damaging frost, but does not prove it: profit-taking after a
  25% run, damage surveys arriving below fears, and Friday/month-end positioning are all
  possible explanations.

**Daily event study**

- **Constant σ_AR.** The t-statistic uses the estimation-window volatility, but Arabica
  volatility spiked after the frost (ICO: intra-day volatility peaked at 17%). At long
  horizons this makes the test too lenient, not too strict.
- **A weak control.** Daily returns of `KC=F` correlate only 0.18 with the cocoa–cotton
  control, with market-model betas of 0.21–0.48, so the model removes little common
  movement. Sugar was excluded as a control because Brazilian cane was hit by the same frost.
- **Low power at long horizons.** The denominator σ_AR·√(k+1) grows quickly, so a CAR+60 of
  +11.3% is not distinguishable from zero.

**Monthly analysis and forecasting**

- **Low power.** n=31 per event in the monthly DiD; no p-values are reported (§3.5).
- **One market, one period.** Forecasting results cover monthly Arabica prices over 103
  origins from 2018-01. They say nothing about other commodities or frequencies.
- **ARIMA order is chosen by AIC,** not by out-of-sample accuracy. That choice avoids leaking
  the test set, but the order may not be optimal for forecasting.
- **Longer horizons use fewer regressors** (5 of 7 at h=6) because of the leakage rule.
- **FX gaps.** `BRL=X` is missing before 2006-03, which shortens every regression that
  controls for FX.
