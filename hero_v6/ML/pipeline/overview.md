# HERO v6 — Modelling Overview

**Target:** `phase_3plus_percentage` — the share of an admin-1 population in IPC Phase 3+ ("Crisis or
worse"). Predicted on its native 0–100 scale, so MAE is in percentage points (pp).

**Two datasets, compared throughout** — identical feature-engineered admin-1 data, differing only in
missing-value handling:
- **`unimputed`** — missing values kept (tree models handle NaN natively)
- **`imputed`** — missing values filled in

**Models are drivers only** — no country identity, no coordinates. **13 features:** conflict (2 ACLED
per-100k), displacement (IDP rate), rainfall (`rain_3m`, `rain_anomaly_3m`), vegetation (2 NDVI),
food prices (WFP price + inflation), media (2 GDELT per-100k), and cyclical seasonality.

**Data note:** 28 *phantom* rows (`phase_all_number = 0` → no IPC analysis for that area-window, so
`phase_3plus_percentage = 0` is spurious, not a true 0%) are dropped on load. Left in, they poisoned
the nowcast lag structure and manufactured fake ±50pp swings; removing them raised the headline nowcast
R² by ≈0.10. 8,457 rows remain (507 areas, 37 countries).

Three rounds: **static inference**, **nowcasting**, and, within each, **localization** (global vs
regional vs per-country vs per-cluster models — two independent clustering schemes). See
[methodology.md](methodology.md) for the how/why.

---

## Round 1 — Static Inference

*Predict IPC from instantaneous drivers (cross-sectional). Validation: GroupKFold(5) by area,
out-of-fold — whole areas held out, so a random split can't leak the spatially/temporally
autocorrelated signal.*

### Leaderboard (GroupKFold OOF, XGBoost is the headline model)

| Model | unimputed R² | unimputed MAE | imputed R² | imputed MAE |
|---|---|---|---|---|
| **Country-mean baseline** | **0.549** | **8.55** | **0.549** | **8.55** |
| XGBoost | 0.530 | 8.89 | 0.529 | 8.77 |
| LightGBM | 0.521 | 8.99 | 0.519 | 8.90 |
| RandomForest | 0.505 | 9.06 | 0.486 | 9.11 |
| DecisionTree | 0.346 | 10.29 | 0.299 | 10.56 |

Drivers-only static is a **hard task**: on the cleaned data the **country-mean baseline (R²=0.549)
beats every driver model** in both datasets (best model 0.53). Knowing *which country* a row is in
explains more of the cross-sectional variance than all 13 drivers combined — the drivers add real
skill *within* a country (see localization) but don't out-predict the country prior globally. This is
why localization matters so much here. (The baseline is dataset-independent — it uses only the target.)

![Static unimputed — pred vs actual](results/static_inference/unimputed/pred_vs_actual_xgboost.png)
![Static imputed — pred vs actual](results/static_inference/imputed/pred_vs_actual_xgboost.png)

### Driver hierarchy (SHAP by data source)

| Source | unimputed | imputed |
|---|---|---|
| displacement (IDP) | **4.34** | 2.56 |
| conflict (ACLED) | 3.33 | 3.88 |
| prices (WFP) | 3.16 | **4.04** |
| seasonality | 2.84 | 3.38 |
| vegetation (NDVI) | 2.44 | 2.87 |
| rainfall | 2.16 | 1.76 |
| media (GDELT) | 1.95 | 2.15 |

Displacement leads on `unimputed`, same as in earlier data rounds; once imputed, **prices** takes over
as the top source (imputation still dilutes the sparse displacement signal — which source fills the gap
depends on the specific imputation round).

![Static unimputed — SHAP beeswarm](results/static_inference/unimputed/shap_beeswarm.png)
![Static imputed — SHAP beeswarm](results/static_inference/imputed/shap_beeswarm.png)

### Per-country performance

![Static unimputed — per-country](results/static_inference/unimputed/per_country_performance.png)
![Static imputed — per-country](results/static_inference/imputed/per_country_performance.png)

**Per-country skill over the country-mean baseline.** The global drivers-model beats "just predict the
country's average" in only **10 of 33** countries — the per-country echo of the leaderboard (baseline
0.549 > model 0.529). For stable, low-IPC countries the mean is genuinely hard to beat (SEN −134%: the
model's error dwarfs the tiny baseline error). This is exactly why localization matters: a *per-country*
model, not the global one, is what turns this around (next section).

![Static unimputed — skill vs country-mean](results/static_inference/unimputed/skill_vs_baseline.png)
![Static imputed — skill vs country-mean](results/static_inference/imputed/skill_vs_baseline.png)

### Localization — does a regional, per-country, or per-cluster model help?

Five training scopes, each routing a row to the model of its own subgroup: **global** (all countries),
**regional** (6-region map), **local** (one country), and two **cluster** scopes — **cluster_kmeans**
and **cluster_hierarchical** — from the colleague's unsupervised, feature-based clustering of each
area's driver time-series (`regioni_clusterizzate.csv`, joined by area code; see
[methodology.md](methodology.md)). Local and cluster models are only built where a full XGBoost is
defensible (≥300 rows); on this data round **every** data-rich country (11/11) clears that floor for a
local model, and 33 of 37 countries have enough scored rows (≥40) to be reported at all.

**Localizing is a broad win, and going local (per-country) wins hardest of all.**

*Per-country win counts:*

| scope beats global in… | unimputed | imputed |
|---|---|---|
| regional | 24/32 | 28/32 |
| local (of data-rich countries) | **11/11** | **11/11** |
| cluster_kmeans | 17/33 | 18/33 |
| cluster_hierarchical | 18/33 | 17/33 |

*Overall (pooled over each scope's scored rows, vs the global model on those same rows — imputed):*

| scope | n_rows | R² | MAE | global R² (same rows) | global MAE (same rows) | ΔR² |
|---|---|---|---|---|---|---|
| global | 8457 | 0.529 | 8.77 | — | — | — |
| regional | 8407 | 0.617 | 7.64 | 0.529 | 8.77 | **+0.088** |
| local | 5469 | 0.589 | 7.91 | 0.445 | 9.39 | **+0.144** |
| cluster_kmeans | 8415 | 0.527 | 8.66 | 0.529 | 8.78 | −0.002 |
| cluster_hierarchical | 8415 | 0.538 | 8.51 | 0.529 | 8.78 | +0.009 |

The overall table confirms the win-counts quantitatively: **regional (+0.088 R²) and local (+0.144)
genuinely lift performance**, while the two cluster scopes are flat (±0.01). Note local's global
comparison (0.445) is worse than global's headline 0.529 — because the 11 data-rich countries local
covers are the harder, higher-variance ones, and it's exactly there that a per-country model pays off.
The cluster scopes are unsupervised, driver-based, and static per area, so they're always assignable
ahead of time — no assignability caveat applies — but on this data they simply don't help.

Since the global static model is itself weak, **local** (per-country, where enough data exists) is the
clearest deployment win here, with regional as the fallback for thinner countries; the cluster scopes
are a smaller, secondary boost worth checking per country rather than a blanket recommendation.

> **Read R² and MAE together.** The R² panel (left) shows some countries with deeply negative values —
> SEN −2.8, GHA −2.0, BEN −1.3 — yet the MAE panel (right) shows those same countries at just 4–6pp
> error. They are stable, low-IPC countries with almost no within-country variance for R² to explain,
> so R² looks catastrophic while the model is actually accurate. R² only carries meaning where the
> target genuinely varies (SSD/YEM/SOM); elsewhere trust MAE.

*Per-country R² (left) & MAE (right) by scope — one marker per scope, best country at top:*

![Static unimputed — scopes by country](results/static_inference/unimputed/scope_comparison.png)
![Static imputed — scopes by country](results/static_inference/imputed/scope_comparison.png)

---

## Round 2 — Nowcasting

*Predict current IPC from the last assessment + latest drivers. Validation: rolling-origin
(walk-forward) expanding backtest, 5 origins 2023-07…2025-07, retrained per origin. Baseline:
persistence (carry the last IPC forward).*

### Skill over persistence (primary cell: train on all, evaluate on observed current windows)

Evaluated on **1,487 test rows** (current windows inside the 5 backtest folds, 2023-07…2026-01;
455 areas, 31 countries).

| | unimputed | imputed |
|---|---|---|
| Persistence R² | 0.625 | 0.625 |
| Best nowcast R² | 0.740 | **0.749** |
| Best nowcast MAE (pp) | 5.30 | **5.08** |
| Skill vs persistence | +14.3% | **+17.8%** |
| Change-direction r | 0.52 | 0.54 |

Both beat persistence; **imputation helps the nowcast** (0.749 vs 0.740) because the level + change
features it relies on become denser. (The feature set is drivers + lags + driver changes, no calendar
`months_since_last`; the honest per-country signal is the change-direction r ≈ 0.53, since pooled R² is
inflated by between-country level differences.)

**Per-country skill — the honest "is the model worth using here?" view.** Relative MAE improvement over
persistence, per country. This is the right per-country nowcast metric (well-defined even where R² is
not): the model **beats persistence in 17 of 21 countries**. Crucially, several countries the R² chart
condemns are actually strong here — MRT (+28% skill, R²=−2.8), SOM (+28%, R²=−0.4), HTI (+10%, R²=−0.1)
all beat persistence despite negative R² (their low within-country variance wrecks R², not the model).
The genuine underperformers — the only places the model is *worse* than carrying the last IPC forward —
are GTM (−13%), MOZ and SDN (−8%), and MLI (−4%).

![Nowcast unimputed — skill vs persistence](results/nowcast/unimputed/skill_vs_baseline.png)
![Nowcast imputed — skill vs persistence](results/nowcast/imputed/skill_vs_baseline.png)

### Where the skill comes from (XGBoost)

| Stage | unimputed R² | imputed R² |
|---|---|---|
| Autoregressive (lags) | 0.683 | 0.683 |
| + driver levels | 0.731 | 0.742 |
| + driver changes | 0.738 | **0.749** |

Most of the lift over persistence is the autoregressive structure (0.683); the exogenous drivers then
add on top — driver *levels* give the biggest single jump (to 0.73–0.74) and driver *changes* extend it
a little further, most on `imputed` (0.749). The **rainfall change** is the strongest exogenous signal.

![Nowcast unimputed — change captured](results/nowcast/unimputed/change_scatter.png)
![Nowcast imputed — change captured](results/nowcast/imputed/change_scatter.png)

### What drives the forecast (SHAP by source)

| Source | unimputed | imputed |
|---|---|---|
| persistence (lags) | **11.56** | **11.68** |
| rain | 2.47 | 2.26 |
| conflict | 1.04 | 1.41 |
| prices | 1.03 | 1.36 |
| vegetation | 1.25 | 1.19 |
| seasonality | 1.08 | 0.97 |
| media | 0.95 | 0.76 |
| displacement | 0.66 | 0.76 |

Persistence dominates and **rainfall leads the exogenous sources** in both.

![Nowcast unimputed — SHAP beeswarm](results/nowcast/unimputed/shap_beeswarm.png)
![Nowcast imputed — SHAP beeswarm](results/nowcast/imputed/shap_beeswarm.png)

### Country time series — actual vs walk-forward nowcast

![Nowcast unimputed — country grid](results/nowcast/unimputed/ts_grid.png)
![Nowcast imputed — country grid](results/nowcast/imputed/ts_grid.png)

Per-admin-1 detail (imputed model shown; the full set of `adm1_*.png` for both datasets is in the
`results/nowcast/*/` folders):

![Somalia — admin-1 nowcast](results/nowcast/imputed/adm1_somalia.png)
![South Sudan — admin-1 nowcast](results/nowcast/imputed/adm1_south_sudan.png)
![Mali — admin-1 nowcast](results/nowcast/imputed/adm1_mali.png)
![Nigeria — admin-1 nowcast](results/nowcast/imputed/adm1_nigeria.png)

### Per-country performance

![Nowcast unimputed — per-country](results/nowcast/unimputed/per_country_performance.png)
![Nowcast imputed — per-country](results/nowcast/imputed/per_country_performance.png)

### Localization — does a regional, per-country, or per-cluster model help?

Same five scopes as the static round (global / regional / local / cluster_kmeans /
cluster_hierarchical), scored by rolling-origin; 21 countries clear the ≥30-scored-row floor.

*Per-country win counts:*

| scope beats global in… | unimputed | imputed |
|---|---|---|
| regional | 10/21 | 8/21 |
| local (of data-rich countries) | 4/10 | 5/10 |
| cluster_kmeans | 8/21 | 11/21 |
| cluster_hierarchical | 10/21 | 9/21 |

*Overall (pooled over each scope's scored rows, vs the global model on those same rows — imputed):*

| scope | n_rows | R² | MAE | global R² (same rows) | global MAE (same rows) | ΔR² |
|---|---|---|---|---|---|---|
| global | 1487 | 0.742 | 5.23 | — | — | — |
| regional | 1487 | 0.734 | 5.26 | 0.742 | 5.23 | −0.008 |
| local | 810 | 0.649 | 5.37 | 0.638 | 5.41 | +0.012 |
| cluster_kmeans | 1478 | 0.751 | 5.16 | 0.744 | 5.21 | +0.007 |
| cluster_hierarchical | 1478 | 0.754 | 5.16 | 0.744 | 5.21 | +0.010 |

Localizing is **a wash** here — every scope's overall ΔR² vs global is within ±0.01. The nowcast's
power is the *universal* autoregressive structure (persistence), so splitting the training data rarely
helps decisively, and **one global model remains the sensible default**. The cluster scopes edge global
by a hair once imputed (ΔR² +0.007/+0.010) but nowhere near enough to justify the added machinery. Since
these clusters are static per area and driver-based (not target-derived), there's no assignability
caveat to weigh. (Same R²-vs-MAE caveat as the static round: read both panels. Full overall tables incl.
unimputed are in each round's `metrics_scopes_overall.csv` / README.)

*Per-country R² (left) & MAE (right) by scope:*

![Nowcast unimputed — scopes by country](results/nowcast/unimputed/scope_comparison.png)
![Nowcast imputed — scopes by country](results/nowcast/imputed/scope_comparison.png)

---

## Admin-2 extension

The same pipeline runs at admin-2 (`python run_all.py adm2`). Admin-2 data only exists as raw counts, so
the 5 rate drivers are reproduced in-pipeline (`prepare_adm2.py`: `raw / max(phase_all_number) × 1e5`,
a static per-area assessed-population proxy — see methodology), clusters are inherited from the parent
adm1, and it runs **unimputed** only. Scale: **36,938 rows, 3,043 areas, 38 countries** (vs 8,457 /
507 / 37 at adm1). Outputs live in `results/<round>/adm2/unimputed/`.

**Two things differ from adm1, both because a country now has many adm2 units:**

1. **Static drivers now beat the country-mean baseline** (unlike adm1, where they didn't):

   | model | R² | MAE |
   |---|---|---|
   | RandomForest | **0.610** | 8.72 |
   | XGBoost | 0.592 | 9.06 |
   | Country-mean baseline | 0.557 | 9.43 |

   With many adm2 units per country, there's real *within-country* spatial variation for the drivers to
   explain, so they add signal over the country prior — at adm1 the country mean already captured most
   of it.

2. **Localization is an even broader win, and clusters now help too.** Overall pooled R² vs the global
   model on the same rows (static):

   | scope | R² | MAE | ΔR² vs global |
   |---|---|---|---|
   | global | 0.592 | 9.06 | — |
   | regional | 0.673 | 7.88 | **+0.077** |
   | local | 0.696 | 7.46 | **+0.095** |
   | cluster_kmeans | 0.664 | 8.21 | +0.049 |
   | cluster_hierarchical | 0.673 | 8.08 | +0.059 |

   Local beats global in **24/24** data-rich countries and regional in 25/27; unlike adm1, the two
   cluster scopes are now clearly positive (+0.05–0.06) — with more areas per subgroup, per-cluster
   models are better-powered.

*Static — country-level performance (per-country R²/MAE by model; per-country R² & MAE by scope; skill
over the country-mean baseline):*

![adm2 static — per-country](results/static_inference/adm2/unimputed/per_country_performance.png)
![adm2 static — scopes](results/static_inference/adm2/unimputed/scope_comparison.png)
![adm2 static — skill vs country-mean](results/static_inference/adm2/unimputed/skill_vs_baseline.png)

**Nowcast** behaves like adm1: best R² **0.698** (XGBoost, `nowcast_change`), **+18.5%** skill over
persistence (0.517), change-direction r = 0.55, evaluated on 8,093 test rows. Localization is again a
**wash** (every scope's overall ΔR² within ±0.01) — keep one global nowcast model.

*Nowcast — country-level performance (per-country R²/MAE by model; per-country R² & MAE by scope; skill
over persistence):*

![adm2 nowcast — per-country](results/nowcast/adm2/unimputed/per_country_performance.png)
![adm2 nowcast — scopes](results/nowcast/adm2/unimputed/scope_comparison.png)
![adm2 nowcast — skill vs persistence](results/nowcast/adm2/unimputed/skill_vs_baseline.png)

**Caveats specific to adm2:** the population denominator is *assessed* population (`phase_all_number`),
not a true total, so adm1↔adm2 rates aren't directly comparable; no imputed variant; WFP (29%) and IDP
(39%) drivers are sparse at this granularity; ~23% of areas lack a cluster (parent adm1 not in the
cluster table); and a few adm2-only countries (DOM/LBN/PSE/MWI/…) fall outside the 6-region map so get
no regional scope. Full charts and tables: `results/{static_inference,nowcast}/adm2/unimputed/`.

---

## Summary & the imputed-vs-unimputed verdict

| | Static inference | Nowcasting |
|---|---|---|
| Question | Why is one area worse than another? | Is this area deteriorating? |
| Validation | GroupKFold by area (OOF) | Rolling-origin backtest |
| Best model R² — unimputed | 0.530 | 0.740 |
| Best model R² — imputed | 0.529 | **0.749** |
| Beats its baseline? | **No** — country-mean (0.549) wins globally | Yes (> persistence, +14–18%) |
| Best deployment scope | **Local** (per-country, 11/11) | Global |

**Impute for nowcast; imputation is neutral for static.** Static drivers-only does not beat the
country-mean baseline globally on either dataset (0.53 vs 0.549), and unimputed vs imputed is a tie
there (0.530 vs 0.529); nowcast is clearly best on `imputed` (0.749). Across both, **localize the
static round** — going per-country beats global for all 11 data-rich countries — **and keep the
nowcast round global**.

## Caveats
- **Phantom rows removed.** 28 area-windows with `phase_all_number = 0` (no analysis; spurious 0%
  target) are dropped on load — they had been inflating apparent volatility (fake ±50pp jumps, mostly
  Yemen) and depressing nowcast R².
- **R² vs MAE per country.** Per-country R² is variance-explained *within* a country, so stable
  low-IPC countries (SEN, BEN, GHA) show large-negative R² despite 4–6pp MAE — read the MAE chart
  alongside. Pooled headline R² is partly cross-sectional (ranking high- vs low-IPC countries); the
  honest within-country signals are per-country MAE, nowcast skill-vs-persistence, and
  change-direction r.
- **Two countries to watch.** **YEM** is intrinsically volatile — even after removing phantoms its IPC
  still swings ~9.5pp/window (vs 7pp global), which drives a large *static* error (~14pp MAE); the
  nowcast handles it via lags (it marginally beats persistence). **MRT (Mauritania)** has ACLED and IDP
  **entirely missing** at source (0/225 rows), so the model is blind on conflict + displacement there;
  the nowcast still beats persistence on lags alone, but the MRT gap is an upstream data issue worth
  flagging to the data owners.
