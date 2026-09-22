# Coffee Weather Shocks
### Detecting the 2021 Brazil Frost in Global Coffee Prices

An end-to-end analysis of whether a Brazilian frost can be detected and measured
in global coffee price data, built from three public sources.

---

## 1. The question

Brazil is the biggest Arabica producer in the world, and in July 2021 a severe
frost hit its coffee-growing regions. Prices rose sharply right after.

The problem is that prices were already rising before the frost. So the obvious
reading — frost happened, prices went up, therefore the frost did it — is not
something the data supports on its own. What I wanted to find out is whether the
frost really is the driver here, or whether other things were pushing prices up
at the same time.

That question turns into two smaller ones I can actually check:

1. **Can a weather shock in Brazil be detected and measured in the price data at
   all?**
2. **Do Arabica and Robusta normally move together, and did they separate after
   July 2021?**

The second one matters because Robusta is grown in Vietnam and Indonesia, not
Brazil. It sits in the same market — same shipping costs, same global demand,
same inflation — but it is not exposed to Brazilian frost. That gives me
something to compare Arabica against.

---

## 2. Data

Three independent sources, combined into one monthly analysis panel.

| Source | What it provides | Frequency | Coverage | Why this source |
|---|---|---|---|---|
| **World Bank Pink Sheet** (CMO) | Arabica and Robusta prices, USD/kg | Monthly | 1960– | Official World Bank data, and it carries Arabica and Robusta in the same file in the same unit ($/kg) — the two series are directly comparable with no conversion. |
| **NASA POWER** (MERRA-2) | Daily min/max temperature, precipitation | Daily | 1981– | Free, no API key, daily resolution back to 1981, and it accepts any lat/lon — so I can pull the specific growing regions rather than a country average. My pull had no missing values across the full history. |
| **Yahoo Finance** (`BRL=X`) | BRL/USD exchange rate | Daily | 2003– | Brazilian farmers sell in USD but spend in BRL, so the exchange rate moves coffee prices even with no weather event at all. It has to be accounted for; `BRL=X` is a free daily series. |

### Weather stations

Three Arabica-growing regions in Brazil:

| Region | Latitude | Longitude | Note |
|---|---|---|---|
| Sul de Minas | −21.55 | −45.43 | Highest frost risk, elevation ~869 m |
| Cerrado Mineiro | −18.94 | −46.99 | Further north, lower frost exposure |
| Mogiana (São Paulo) | −20.54 | −47.40 | Frost-prone |

A single grid cell proves little on its own — one unusual reading could be an
artefact of that cell. Three separate growing regions let me check whether a cold
anomaly shows up consistently, and the percentile thresholds end up differing
between them (6.06 °C to 7.35 °C), which confirms that each region needs its own
baseline rather than a shared one.

### Data quirks worth documenting

- The Pink Sheet has **two header rows** (commodity names, then units); data starts on the third.
- Missing values in the Pink Sheet are the ellipsis character `…`, not blanks or `NaN`.
- NASA POWER encodes missing values as **`-999.0`**. If this is not converted to
  `NaN`, Python reads it as a temperature of −999 °C — which makes that day the
  coldest on record and corrupts every percentile computed from the series.

---

## 3. Finding A — an absolute frost threshold does not work

I first defined a frost day as any day where NASA POWER's `T2M_MIN` fell to 2 °C
or below. That is the physically obvious threshold: water freezes at 0 °C, and
2 °C leaves a margin.

It detected **zero frost days in July 2021** — for a frost that is extensively
documented and that ICO called "one of the most intense frosts in living memory."

The data was not wrong. The lowest reading at Sul de Minas was **3.05 °C on
20 July**, against a normal July minimum of **8–12 °C** — clearly anomalous, just
not below 2 °C. Two properties of the measurement explain the gap:

- The MERRA-2 grid cell is roughly **50 km across**, so each value is an average
  over a wide area. Local cold pockets are smoothed away.
- `T2M_MIN` is measured **2 metres above the ground**, while the surface — where
  the damage to the plant actually happens — is colder than the air above it.

I replaced the absolute threshold with a percentile-based one, computed per
location from that location's own **June–August** history: a frost day is a day
whose `T2M_MIN` falls below roughly the 2nd percentile of that distribution.

| Region | Threshold |
|---|---|
| Sul de Minas | 6.06 °C |
| Cerrado Mineiro | 7.07 °C |
| Mogiana | 7.35 °C |

The thresholds differ by region, which is what you would expect — each region has
its own climate, so each needs its own definition of "unusually cold."

The lesson: the threshold had to come from the data's own distribution rather
than from the physics of freezing, because the instrument does not measure what
its name suggests. "Minimum temperature" here means the minimum of a 50 km
average, two metres up — not the temperature at the leaf.

---

## 4. Finding B — verifying the event against a primary source

The frost date is the input to every downstream step in this project, so I
verified it against a primary source rather than a secondary summary: the **ICO
Coffee Market Report, July 2021**.

The report confirms the date as **20 July 2021** (pp. 1, 3) and records the market
reaction: NY Arabica futures rose from **165.65 to 207.80 US cents/lb in one
week**, and the ICO composite indicator price (I-CIP) reached **152.24 US
cents/lb — its highest level since November 2014**. It also notes that the
production impact falls on the **2022/23 crop year**, not the harvest then
underway.

Reading it also corrected two things I had taken from secondary sources.

**There was only one frost wave.** A widely repeated claim that there were two —
20 July and 29–30 July — is not supported by the ICO report, which documents only
20 July. The NASA data does show a second dip on 30 July (3.19 °C), but gridded
data cannot establish severity. The project uses 20 July only.

**Part of the price rise was already anticipated.** ICO notes that 2021/22 was
already an "off year" in Arabica's biennial bearing cycle — the tree alternates
between a heavy and a light crop — so the market was expecting a smaller harvest
before the frost happened. This is a limitation, recorded in section 5.

Verifying the date mattered more than it looks. An error here would not have
raised an exception: the code would have run, produced numbers, and every result
downstream would have been quietly wrong.

---

## 5. What I did not conclude

**Parallel trends are not clean.** Over a 36-month pre-period, Arabica had
already diverged from Robusta by about **+61%** — before the frost. That is
larger than the roughly 20% divergence that shows up after it. A naive
before/after comparison would credit the frost with a rise that was already
underway.

**The weather data cannot rank severity.** July 2021 was severe and May 2022 was
mild, but no threshold I tested reproduced that ordering — several percentile
cut-offs and a degree-day measure all rated May 2022 as equal or worse. The
causes are the ones in section 3: a 50 km grid and a 2 m measurement height. So
the weather data *characterises* the event; it does not *identify* it. Event
dates come from documented sources, not from the temperature series.

**The control group is contaminated.** Vietnam's COVID Delta lockdown disrupted
Robusta exports in July–September 2021, lifting the control group for reasons that have
nothing to do with Brazil. Since the comparison rests on the gap between the two
series, a control that rises on its own makes the frost effect look smaller than
it actually was.

**Arabica's biennial cycle was already pushing prices up.** Arabica trees
alternate between a heavy crop year and a light one — a large harvest drains the
tree, so the next year's is smaller on its own. ICO notes that 2021/22 was
already an "off year", so the market was pricing in a smaller harvest before the
frost happened. This matters twice: it moves Arabica but not Robusta, so the
control group does not absorb it, and it was already in motion before July 2021,
which makes it one likely explanation for the pre-trend above.

The repository also contains exploratory event-study and forecasting notebooks.
I have not validated their causal interpretation to my own satisfaction, so I do
not present their estimates as findings here.

---

## 6. Future work

Deliberately out of scope, with reasons:

| Not done | Why not |
|---|---|
| LSTM / deep learning | ~312 monthly observations — would overfit and lose interpretability |
| Prophet, XGBoost | ARIMA/SARIMAX is sufficient at this sample size |
| Synthetic control | Complexity not justified for a two-unit comparison |
| ERA5-Land (~9 km grid) | Better resolution, but requires a Copernicus CDS account, a queued API and NetCDF handling; the percentile method already mitigates the problem it would solve |
| Airflow / scheduling | This is a one-off analysis, not a live pipeline |
| USDA FAS production data | Would fill the middle link: frost → production drop → price rise |
| INMET station records | Could confirm the grid-smoothing argument for a single date |

---

## 7. Repository layout

```
data/events.csv    documented frost events, with the ICO source for each
data/raw/          immutable — never overwritten (gitignored)
data/interim/      regenerable intermediates (gitignored)
data/processed/    analysis-ready; panel_monthly.csv (gitignored)
src/ingestion/     worldbank.py, nasa_power.py, yahoo.py, daily_prices.py, events.py
src/processing/    weather_features.py, build_panel.py, event_study.py,
                   daily_event_study.py, forecasting.py
notebooks/         00_feasibility, 01_eda, 02_causal_did, 04_daily_event_study, 05_forecasting
reports/figures/   exported charts
docs/              methodology.md
requirements.txt   pinned dependencies
README.md          this file
.gitignore         excludes .venv/, the three data/ subfolders above, caches, source PDFs
```

Raw data is not committed. `.gitignore` excludes `data/` and `.venv/`.

---

## 8. Reproducing

```bash
git clone <repo-url>
cd coffee
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

Then download the price file manually and place it in `data/raw/`:

- **World Bank Commodity Markets ("Pink Sheet")**
  Landing page: https://www.worldbank.org/en/research/commodity-markets
  File: `CMO-Historical-Data-Monthly.xlsx`, sheet `Monthly Prices`
  Accessed: 17 September 2026

<!-- Note: link to the landing page, not the direct file URL — the file
     is replaced monthly and direct links break. -->

Weather and FX data are fetched by the ingestion scripts:

```bash
python -m src.ingestion.nasa_power
python -m src.ingestion.yahoo
python -m src.processing.build_panel
```

---

## Author

Ryan Christopher Setiawan — Data Science, BINUS University
Solo project: scope design, data source selection and verification, pipeline
implementation, analysis, and documentation.
