# Methodology

How the pipeline predicts IPC Phase 3+ and why each choice is made. Companion to
[overview.md](overview.md) (the results). Code: `config.py` (decisions), `features.py` (shared
logic), `static_inference.py`, `nowcast.py`.

## 1. Objective
Predict `phase_3plus_percentage` — the share of an admin-1 population in IPC Phase 3+ ("Crisis or
worse") — from food-security drivers, and understand *what drives it* and *where the model works*.
Two complementary rounds: **static inference** (why is one area worse than another, cross-sectional)
and **nowcasting** (is an area deteriorating, over time). Each round also asks whether a
**localized** (regional / per-country / per-cluster) model beats one global model.

## 2. Environment
- Interpreter: the `ewm` conda env. Libraries: pandas, numpy, scikit-learn, xgboost, lightgbm, shap,
  matplotlib.
- `config.py` sets OpenMP/MKL guards before numpy is imported (XGBoost/LightGBM bundle their own
  OpenMP; without the guards, numpy-MKL calls crash on Windows). It is imported first everywhere.
- Determinism: `random_state = 42`; headless matplotlib (`Agg`).

## 3. Data & the two datasets
The colleague's feature-selected + rate-normalized admin-1 data (`hero_v6/data/Imputation and
clustering/`, `v3` round). "Normalized" means counts were turned into **rates** (per-100k /
per-population), **not** standardized — the target keeps its native 0–100 scale, so MAE (pp) and R²
are directly interpretable. The two datasets differ **only** in missing-value handling (8485 rows
each in the files; 8457 used after the validity guard below):

- **`unimputed`** (`merged_adm1_wide_norm_v3.parquet`) — missing values kept; the tree models split on
  missingness natively.
- **`imputed`** (`merged_adm1_wide_norm_imputato_v3.parquet`) — every driver's missing value filled in.

Comparing them isolates the effect of imputation. `phase_all_number` (analysed population) is used
only as a denominator/validity flag, never a feature; all `phase_*` columns are excluded (leakage
guard).

**Data-validity guard (`features.load_dataset`).** Rows with `phase_all_number` ≤ 0 have *no analysed
population* — no IPC analysis existed for that area-window, so every phase count is a mechanical 0 and
`phase_3plus_percentage` = 0 is a **phantom** value, not a true "0% in crisis". These are dropped on
load (28 rows, ~0.3%, concentrated in YEM and NGA). Left in, they contaminated training and — because
they became `lag1`/`lag2` — manufactured huge spurious window-to-window swings (Yemen showed ±50pp
"changes" that were entirely these rows). Dropping them raised the headline nowcast R² by ≈0.10. 8457
rows remain (both datasets).

## 4. Features (`config.DRIVERS` + seasonality)
**13 model features, drivers only** — no country identity, no latitude/longitude:
conflict (`acled_political_violence_events_per_100k`, `acled_total_fatalities_per_100k`),
displacement (`idp_population_over_adm1_population`), rainfall (`rain_3m`, `rain_anomaly_3m`),
vegetation (`ndvi_vim`, `ndvi_viq`), food prices (`wfp_price`, `wfp_inflation`), media
(`gdelt_material_coop_per_100k`, `gdelt_verbal_conflict_per_100k`), and cyclical seasonality
(`month_sin`, `month_cos` — no absolute year, so the model sees the seasonal cycle, not a time
artifact). Nowcasting adds autoregressive terms and driver changes (§6).

Country and coordinates are deliberately excluded: they let a model memorize location rather than
learn driver→IPC relationships, and add no honest out-of-sample accuracy.

## 5. Static inference — validation
**GroupKFold(5) grouped by area, out-of-fold (OOF) — the only split.** Why not a random split: IPC
is **spatially and temporally autocorrelated**, and each area appears in many time windows. A random
row split would put some of an area's rows in train and some in test, so the model could recognise
the area (and its typical level) instead of learning the drivers — an optimistic, leaked score.
Grouping by area holds out **whole areas**, so a scored area is genuinely unseen; 5-fold OOF is
low-variance (every area tested once) and gives a complete predicted-vs-actual set. The OOF feeds the
model leaderboard, the pred-vs-actual plot, the per-country table, and the "global" localization
scope.

- **Baseline:** per-country mean (fit on the training fold only) — "can the drivers beat just
  predicting each country's average level?"
- **Metrics:** R² (variance explained, comparable), MAE and RMSE (percentage points).
- **Models:** DecisionTree, RandomForest, XGBoost, LightGBM — fixed params, no tuning (all handle
  NaN natively; the leaderboard is a cross-model robustness check).
- **Explainability:** RandomForest impurity importance + SHAP (XGBoost), aggregated by data source.

## 6. Nowcasting — validation
Estimate an area's *current* IPC from its **last assessment** plus the **latest drivers**.

- **Panel:** one row per (area, window `From`); when IPC re-classifies a window across analyses we
  keep the authoritative reading (current > first projection > second projection). Two panels:
  current windows only, and current + projection windows.
- **Autoregressive features:** `lag1`, `lag2`, `recent_trend = lag1 − lag2`.
- **Driver changes:** `change_<driver>` = the driver's change since the area's previous window
  (nowcasting is about *change*; e.g. the rainfall change is the strongest exogenous signal).
- **Nested feature sets** decompose where skill comes from: `autoregressive` ⊂ `nowcast` (+ driver
  levels) ⊂ `nowcast_change` (+ changes); plus `drivers_only` (no lag).
- **Baseline:** persistence — carry the last known IPC forward. It is strong (IPC is persistent), so
  **skill = MAE improvement over persistence** is the honest measure.
- **Split:** rolling-origin (walk-forward) **expanding** backtest. For each of 5 origins
  (2023-07 … 2025-07) the model trains on **all** windows before the origin and is tested on the next
  6 months — never using the future to predict the past. Primary evaluation cell: train on all data,
  score on **observed current** windows. Also reported: change-direction correlation (predicted vs
  actual change since the last assessment).

## 7. Localization (both rounds)
Each round is re-run at five training **scopes**: **global** (all countries), **regional**
(6-region agro-climatic map), **local** (one country), and two **cluster** scopes — **cluster_kmeans**
and **cluster_hierarchical** — each under its round's own validation. Every row is routed to the model
of its own subgroup, and results are always reported per country. A **local** or **cluster** model is
only built where a full XGBoost is defensible (it overfits below a few hundred rows), enforced by the
floors in `config.py`: ≥300 rows to attempt one, ≥100 rows per rolling-origin fold, ≥6 areas for the
static area hold-out. A per-country metric is only **reported** above a scored-row floor
(`MIN_ROWS_TO_REPORT_*`), set **per round** because "scored rows" mean different things: static counts
out-of-fold rows (plentiful → floor **40**), while nowcast counts current windows inside the backtest
eval folds (a small recent slice by design → floor **30**, so data-rich countries with few recent test
windows aren't dropped). Global and regional scopes (thousands of rows) are always well-powered.

**Per-country scope chart.** `scope_comparison.png` is a two-panel dot chart — per-country **R²** (left)
and **MAE (pp)** (right), one marker per scope, best country at top. Both panels are shown because R² is
unstable in low-variance countries: a stable, low-IPC country (e.g. SEN, BEN, GHA) can post R² of −2 to
−3 while its MAE is only 3–6pp — the model is actually fine, R² is just the wrong lens. R² is
variance-explained *within* a country, so it only carries meaning where the target genuinely varies;
read it alongside MAE. (Note: the headline pooled R² per round is inflated by *between*-country level
differences; the honest within-country signals are per-country MAE, nowcast skill-vs-persistence, and
change-direction r.)

The two **cluster** scopes come from `regioni_clusterizzate.csv` — a static, one-row-per-area table
joined onto both datasets by `adm1_pcode` (`config.CLUSTER_SCOPES`), so, unlike the previous
`cluster_assegnato` label, they are available for **both** `unimputed` and `imputed`. They are
**unsupervised, feature-based clusters of each area's driver time-series** (statistical descriptors
like volatility, entropy, and historical structure — see the colleague's `Clustering approach` note),
not derived from the target. `cluster_kmeans` and `cluster_hierarchical` are the two clustering
algorithms run on the same "no coordinates" feature set (excluding lat/long, so the grouping stays
behavioral rather than geographic); they disagree substantially with each other, which is why both are
kept as separate scopes rather than merged into one. Being a fixed per-area attribute (not per-window),
a cluster is always knowable ahead of time for any known area — the old scope's "must be assignable at
prediction time" caveat no longer applies. A few subgroups within each scheme are very small (2–3 of
the ~507 areas); these simply fall below the floors above and are skipped, not fitted.

## 8. Outputs
`results/<round>/<dataset>/` — `metrics_*.csv` (incl. `metrics_scopes_overall.csv`: pooled R²/MAE per
scope over the rows it scored, plus the global model on those same rows for an apples-to-apples "did
routing help overall?" ΔR²), `shap_*`, `pred_vs_actual_*`, `per_country_performance.png`,
`scope_comparison.png` (two-panel dot chart: per-country R² & MAE by scope),
`skill_vs_baseline.png` (per-country % MAE improvement of the headline model over its naive baseline —
persistence for nowcast, country-mean for static; the honest "is the model worth using here?" view,
well-defined even where R² isn't), `README.md` (auto-generated findings), and (nowcast) `ts_grid.png` /
`adm1_*.png`.

## 9. Spatial level — admin-1 and admin-2
The level is the `HERO_LEVEL` env var (`config.LEVEL`), set by `run_all.py`'s CLI arg
(`python run_all.py` = adm1, `python run_all.py adm2` = adm2). It fixes `AREA_COL`
(`adm1_pcode` / `adm2_pcode`), `DATASETS`, and the results tree (adm2 nests under
`results/<round>/adm2/…` so adm1 is untouched); everything else keys off `AREA_COL` unchanged.

- **adm2 data prep (`prepare_adm2.py`).** Admin-2 exists only as a raw merge with event *counts*, not
  the rate drivers. The script reproduces the adm1 normalization (`raw / population × 1e5`, and
  `idp / population`) using a **static per-area proxy** for population — `max(phase_all_number)` per
  adm2 unit — and writes `merged_adm2_wide_norm.parquet`. Clusters are inherited from the parent adm1
  (`CLUSTER_JOIN_COL = adm1_pcode`, joined at load). adm2 runs **unimputed only** (native-NaN); no
  imputed variant exists.
- **adm2 caveats:** the denominator is *assessed* population, not total, so adm1↔adm2 rates aren't
  directly comparable (each level's model is internally consistent); WFP (29%) and IDP (39%) drivers
  are sparse at adm2; ~23% of areas lack a cluster (parent adm1 absent from the cluster table); a few
  adm2-only countries fall outside the 6-region map (no regional scope for them).

## 10. Other limitations
- **No hyperparameter tuning** (fixed params) — deliberate, to keep the pipeline simple; expected
  gains are small.
- Static per-country R² is variance-explained *within* a country, so stable low-IPC countries can
  show low/negative R² despite small MAE — use MAE alongside R² there.
