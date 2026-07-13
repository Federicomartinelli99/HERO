# HERO v6 — Methodology

Technical description of how the IPC Phase 3+ analysis was carried out, the design decisions
behind it, and what is still missing. Companion to [overview.md](overview.md) (which reports
the results). Code lives in [../codes/](../codes/).

---

## 1. Objective

Predict `phase_3plus_percentage` — the share of an admin-1 population in IPC Phase 3+ ("Crisis
or worse") — from food-security drivers, and understand *what drives it* and *where the models
work*. Three complementary rounds:

| Round | Question | Script |
|---|---|---|
| Static inference | Why is one area worse than another (cross-sectional)? | [static_inference.py](../codes/static_inference.py) |
| Nowcasting | Is an area deteriorating (intertemporal)? | [nowcast.py](../codes/nowcast.py) |
| Localization | Does a regional/per-country model beat one global model? | [localization.py](../codes/localization.py) |

Visualization: [nowcast_viz.py](../codes/nowcast_viz.py), [plot_country_metrics.py](../codes/plot_country_metrics.py).

---

## 2. Environment & reproducibility

- **Interpreter:** `C:/Users/jonas/miniconda3/envs/ewm/python.exe` (conda env `ewm`).
- **Libraries:** pandas, numpy, scikit-learn, xgboost, lightgbm, shap, matplotlib.
- **Windows guard:** every script sets `KMP_DUPLICATE_LIB_OK`, `MKL_THREADING_LAYER=SEQUENTIAL`,
  `OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1` **before** importing numpy. XGBoost/LightGBM bundle
  their own OpenMP runtime; without this, MKL LAPACK calls (via matplotlib) crash with Windows
  fatal exception `0xc06d007f`.
- **Determinism:** `random_state = 42` everywhere; `matplotlib.use("Agg")` (headless).
- **No imputation:** NaN is kept intact and handled natively by the tree models — a deliberate
  scope choice (imputation is a later round).

---

## 3. Data & panel construction

**Input:** `data/merged/merged_adm1_wide.parquet` — 10,024 rows × 62 columns; 9,869 rows carry a
non-null target. Keys: `adm1_pcode` (area), `From` (assessment-window start), `Country` (ISO3).

### Static round
`build_xy` filters to rows with a non-null target. No temporal structure is used, so no
deduplication is needed.

### Nowcast round — `build_panel`
The panel is a per-area **time series keyed by window start `From`** (one IPC value per
`(adm1_pcode, From)`), so lags and gaps are well defined.

- **Deduplication.** The same real-world window can appear multiple times because IPC
  re-classifies it across analyses (an early analysis calls window *W* a projection; a later one
  calls it `current`). Each `(area, From)` is collapsed to one row with preference order
  **current > first projection > second projection**, recording `is_projection` (1 if the kept
  value came from a projection). Within `current` alone there are 0 duplicate windows, so the
  dedup is a no-op there and only matters once projections are included.
- **Two panels:**
  - `panel_cur` — current windows only: **5,054 windows**, lag1 available 87.6%.
  - `panel_all` — current + projection windows (preference-deduped): **9,596 windows**
    (4,542 projection), lag1 available 93.5%, carries `is_projection`.

---

## 4. Feature engineering

### Driver features — `build_xy` (33 features, shared by all rounds)

| Group | Features | Notes |
|---|---|---|
| Conflict (ACLED) | 8 event/fatality counts | converted to **per-100k** using `phase_all_number` as the population denominator |
| Displacement | `idp_rate` = idp_population / pop | |
| Climate — rainfall | `rain_1m_sum`, `rain_1m`, `rain_3m`, `rain_anomaly_1m`, `rain_anomaly_3m` | |
| Climate — vegetation | `ndvi_vim`, `ndvi_viq` | NDVI = crop/pasture condition, drought proxy |
| Prices (WFP) | `wfp_price`, `wfp_inflation` | `wfp_obs_count` excluded (data-density, not a driver) |
| Media (GDELT) | 12 verbal/material coop/conflict event, mention, tone signals | |
| Context | `Country` (ordinal category codes), `year`, `month` | |

- **Leakage guard:** an assertion rejects any `phase_*` column. `phase_all_number` is used *only*
  as the per-100k denominator (zeros → NaN to avoid division blow-ups), never as a feature.
- NaN is preserved (native-NaN models).

### Autoregressive features — `build_panel` + `make_features` (nowcast only)
Computed per area on the sorted window series (leakage-safe, past values only):
- `lag1_phase3plus`, `lag2_phase3plus`, `recent_trend = lag1 − lag2`,
  `months_since_last` (day gap / 30.44), `is_projection`.
- **Driver deltas:** `make_features` also derives `d_<feature>` = per-area `groupby.diff()` of
  each continuous driver (change since the area's previous window). `Country/year/month` are not
  differenced.

### Feature sets — `feature_sets_for`
Four nested sets let us decompose where skill comes from:
`ar_only` (AR + is_proj) ⊂ `nowcast` (drivers + AR) ⊂ `nowcast_delta` (+ deltas); plus
`static` (drivers only, no AR).

---

## 5. Models & baselines

`make_models()` returns four estimators, **all NaN-native, no tuning** (fixed hand-set params):

| Model | Key params |
|---|---|
| DecisionTree | `min_samples_leaf=20` |
| RandomForest | `n_estimators=400, min_samples_leaf=5` |
| XGBoost | `tree_method=hist, n_estimators=400, lr=0.05, max_depth=6, subsample=0.8, colsample_bytree=0.8` |
| LightGBM | `n_estimators=400, lr=0.03, num_leaves=31, subsample=0.8, colsample_bytree=0.8, min_child_samples=40` |

**Baselines (the bars to beat):**
- Static: `country_mean_baseline` — per-country mean fit on the training fold only.
- Nowcast: **persistence** — carry the last known IPC (`lag1`) forward (fallback = training mean).
  Strong because IPC is highly persistent (R² ≈ 0.56–0.62).

---

## 6. Validation design

### Static round — spatial generalization
- **Geographic hold-out (primary):** `GroupShuffleSplit`, 80/20 by area — entire admin-1 areas
  withheld, so test areas are unseen.
- **GroupKFold CV (5-fold by area):** out-of-fold predictions across all rows; more robust than a
  single split.
- **Random hold-out:** same 80/20 size but rows shuffled — the gap vs geographic quantifies
  **spatial-autocorrelation inflation** (≈ 0.12–0.13 R²).
- **Country ablation:** GroupKFold with vs without the `Country` feature.

### Nowcast round — temporal generalization (never uses the future to predict the past)
- **Rolling-origin backtest, expanding window** (`run_backtest`): origins
  `2023-07 / 2024-01 / 2024-07 / 2025-01 / 2025-07`, 6-month test windows. Fold *k*: train
  `From < origin_k`, test `origin_k ≤ From < origin_k + 6mo`; each test row scored once,
  concatenated across folds (n = 1,856 primary-cell rows).
- **Three reported cells** (persistence recomputed per cell):
  1. `train_cur | eval_current` — exclude projections.
  2. `train_all | eval_current` — **primary**: does adding projection data improve nowcasts of
     reality? (test rows all have `is_projection == 0`.)
  3. `train_all | eval_projection` — reproducing IPC's own projections.
- **Single holdout** (`< 2024-01-01`) for clean pred-vs-actual plots.

### Localization round — `localization.py`
Three training **scopes** for XGBoost, each under its round's native validation:
- **global** (all countries), **regional** (6-region hand-drawn map), **local** (per country).
- Static scope run = GroupKFold by area within scope; nowcast scope run = rolling-origin backtest
  within scope. The "global" baseline is recomputed with GroupKFold so all three scopes are
  measured identically (hence numbers differ slightly from the single-split geo hold-out).
- **Small-data guards:** `MIN_LOCAL_WINDOWS = 60`, `MIN_LOCAL_AREAS = 5`, `MIN_EVAL = 5`,
  `n_splits = min(5, n_areas)`.

---

## 7. Metrics

- **MAE, RMSE, R²** (`scores`) — reported for every model / cell / scope.
- **Skill vs persistence** = `(MAE_persist − MAE_model) / MAE_persist` (positive ⇒ drivers add
  value beyond carrying the last assessment forward).
- **Change-direction correlation** = Pearson r between predicted and actual *change since the
  last assessment* (`pred − lag1` vs `actual − lag1`). Because level-R² is dominated by the lag,
  this is the honest measure of nowcasting skill (currently **r = 0.53**).
- **Per-country** breakdowns (`score_by_country`, min 5 evaluated rows).
- **Driver decomposition** — MAE gain moving `ar_only → +levels → +deltas`.

---

## 8. Explainability

- **Impurity (Gini) importance** from DecisionTree and RandomForest.
- **SHAP** (`TreeExplainer` on XGBoost, 3,000-row sample):
  - Static: with and without `Country` (to see what the country fixed-effect masks).
  - Nowcast: on the `nowcast_delta` XGBoost over `panel_all`.

---

## 9. Visualization

- [nowcast_viz.py](../codes/nowcast_viz.py) runs a **separate, extended** 11-origin semi-annual
  backtest (2020-07 → 2025-07, XGBoost nowcast only) purely for walk-forward OOF time-series
  plots — kept independent of the metrics backtest so it never affects reported numbers. Produces
  the country grid, per-country series + driver strip, and per-area admin-1 grids.
- [plot_country_metrics.py](../codes/plot_country_metrics.py) — per-country R²/MAE dot charts.
- `localization/scope_comparison.png` — per-country R² by scope.

---

## 10. Artifact map

```
ML/results/
├── overview.md                 results narrative
├── methodology.md              this file
├── static_inference/           README.md, metrics_*.csv, shap_*, gini_*,
│                               per_country_performance.png, pred_vs_actual_*
├── nowcast/                    README.md, metrics_*.csv, skill_vs_persistence.csv,
│                               driver_contribution.csv, change_scatter.png, shap_*,
│                               ts_* (time series), adm1_* (admin-1 grids)
└── localization/               README.md, metrics_{static,nowcast}.csv, scope_comparison.png
```

Each round folder has one `README.md` (auto-generated findings). Family prefixes group files:
`metrics_*`, `shap_*`, `gini_*`, `pred_vs_actual_*`, `ts_*`, `adm1_*`.

---

## 11. Key methodological decisions (and why)

- **Native-NaN tree models only** — the merged data is sparse (IDP 33%, WFP 64%, NDVI 86%);
  dropping incomplete rows would discard most of the panel, and imputing before understanding the
  signal risks fabricating it.
- **Geographic (not random) validation** for the static round — random splits leak spatial
  autocorrelation and overstate deployment R² by ~0.12–0.13.
- **Persistence as the nowcast bar** — IPC is so persistent that beating a naïve carry-forward is
  the only honest evidence that drivers add value.
- **Projection dedup with a preference order** — collapses the multi-analysis duplication of the
  same window into one authoritative value while retaining a provenance flag.
- **Region as the risk-managed middle scope** — per-country models overfit on thin data; regional
  pooling keeps most of the sample while grouping plausibly-homogeneous regimes.

---

## 12. Limitations & what is still missing (technical)

### Validation / leakage
- **Spatial leakage is reduced, not eliminated.** GroupKFold holds out whole areas but neighbouring
  areas still land in different folds; there is no spatial-buffer / blocked CV.
- **Single-split fragility.** The static geographic hold-out is high-variance for data-thin
  countries — e.g. MLI's −39 R² is largely a single-split artifact (GroupKFold gives +0.17). The
  headline table should be read alongside the CV numbers.
- **No statistical significance** on scope comparisons (global vs regional vs local) — no
  confidence intervals or repeated-seed variance, so small R² differences are not tested.

### Modelling
- **No hyperparameter tuning.** All params are hand-set; no nested CV. Regularization tuning could
  narrow the random-vs-geographic gap and curb per-country blow-ups.
- **No target transform.** The target is bounded [0, 100] and right-skewed, but models predict on
  the raw scale — unbounded predictions contribute to extreme negative R². A logit/beta-style
  transform or monotone constraints are untried.
- **No uncertainty quantification.** Point estimates only — no prediction intervals (quantile
  regression / conformal prediction).
- **No ensembling / stacking.**
- **`Country` is ordinal-encoded** (arbitrary integer codes). Fine-ish for trees but not ideal;
  target/frequency encoding untested.

### Features
- **Shallow AR history** (lag1/lag2 only). Deferred: lag3, rolling mean/volatility, and a
  national/neighbour-IPC spatial-lag context feature.
- **No missingness modelling.** No missing-indicator flags; NDVI coverage is low for some
  countries (e.g. KEN ~21%), so those areas silently lean on other features.
- **Contemporaneous drivers, not lagged-for-forecast.** The "nowcast" uses drivers *at the target
  window*; this is estimation of the present, not true out-of-horizon forecasting.
- **Upstream temporal alignment** of GDELT/rainfall/prices to the IPC window is assumed correct
  and not re-audited here.

### Scope not yet covered
- **True forecasting** (predict window *t + h* from data available at *t*).
- **Delta-target variant** (predict `target − lag1` directly).
- **Admin-2 level** modelling.
- **IPC's own projections** as an external benchmark (we reproduce them, we don't beat them).
- **Deployable specialized models** — Round 3 identified where regional/local wins, but those
  models are not yet packaged as artifacts.
- **KNN + imputation round** (missingness flags, denser WFP/IDP coverage).

### Diagnostics
- No residual analysis by phase level, no calibration plots, no seed-sensitivity study; SHAP is
  computed on a single 3,000-row sample.
