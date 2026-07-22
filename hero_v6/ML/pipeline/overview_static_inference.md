# Static Inference — Results Walkthrough

*Explaining IPC food-insecurity crisis levels from drivers: what we did, how well it works,
and why. Standalone narrative for the static ("why is this area worse than that one?") round —
**imputed dataset only**, admin-1.*

---

## 1 · The approach

**Question.** For a given area-month, can routinely-available *drivers* explain the share of the
population in **IPC Phase 3+** ("Crisis or worse", `phase_3plus_percentage`, a 0–100 scale)? This is
the *explanatory / targeting* use case — cross-sectional, "why is one place worse than another",
as opposed to tracking change over time.

**Inputs — drivers only, no geography.** 13 model features: 11 driver rates across six families
(conflict, displacement, rainfall, vegetation, food prices, media) plus cyclical seasonality
(`month_sin`, `month_cos`). We deliberately **exclude country identity and coordinates** — otherwise a
model just memorizes *which* place it is looking at instead of learning the driver→IPC relationship,
and gains no honest out-of-sample accuracy.

**Scale.** 8,457 area-months · 507 admin-1 areas · 37 countries.

**Validation — leakage-safe by construction.** `GroupKFold(5)` grouped **by area**, out-of-fold. IPC
is spatially and temporally autocorrelated and each area recurs across many windows, so a random row
split would leak an area's typical level into the test set. Holding out **whole areas** means every
scored area is genuinely unseen. Four tree models are compared (XGBoost is the headline); the
**baseline is the per-country mean** — "can drivers beat simply predicting each country's average
level?"

---

## 2 · The overall numbers

Out-of-fold leaderboard, imputed dataset:

| model | R² | MAE (pp) | RMSE (pp) |
|---|---|---|---|
| **Country-mean baseline** | **0.549** | **8.55** | 11.37 |
| XGBoost (drivers) | 0.529 | 8.77 | 11.62 |
| LightGBM | 0.519 | 8.90 | 11.75 |
| RandomForest | 0.486 | 9.11 | 12.14 |
| DecisionTree | 0.299 | 10.56 | 14.18 |

The models agree, XGBoost leads them — **and the drivers-only global model does not beat the
country-mean baseline** (R² 0.529 vs 0.549; MAE 8.77 vs 8.55 pp).

---

## 3 · Why we don't do well globally

This is an *insight*, not a failure of the drivers.

- **Knowing the country already captures most of the cross-sectional variance.** A large part of "why
  is this area worse" is simply *which country* it is in — chronic structural differences between,
  say, South Sudan and Guatemala. The country-mean baseline gets that for free.
- **One global driver→IPC mapping is asked to generalize across 37 very different contexts.** The same
  rainfall anomaly, the same conflict rate, the same displacement level mean different things in the
  Sahel, the Horn, Central America, and Yemen. Forcing a single function to fit them all averages away
  exactly the relationships that matter locally.

So the global model isn't the product. It tells us **where the value is: *within* countries and
regions, not in one global "why" model.** That points straight at localization.

---

## 4 · Localization works

We re-run the round at five training **scopes** — **global**, **regional** (6-region agro-climatic
map), **local** (one model per country), and two unsupervised **cluster** schemes
(`cluster_kmeans`, `cluster_hierarchical`, from the colleague's driver-fingerprint clustering). Every
row is routed to the model of its own subgroup; results are always reported per country. Local/cluster
models are only built where a full model is defensible (≥300 rows).

Pooled metrics per scope, with each scope re-compared to the global model **on exactly the rows it
scored** (apples-to-apples "did routing help?"):

| scope | overall R² | MAE (pp) | global on same rows (R²) | ΔR² |
|---|---|---|---|---|
| global | 0.529 | 8.77 | — | — |
| **regional** | **0.617** | **7.64** | 0.529 | **+0.088** |
| **local (per-country)** | **0.589** | **7.91** | 0.445 | **+0.144** |
| cluster_kmeans | 0.527 | 8.66 | 0.529 | −0.002 |
| cluster_hierarchical | 0.538 | 8.51 | 0.529 | +0.009 |

- **Regional lifts pooled R² from 0.529 → 0.617 and cuts MAE by more than a full point** (8.77 → 7.64 pp)
  — with near-complete coverage (35 of 37 countries).
- **Local wins hardest where it matters.** On the 11 data-rich countries where a per-country model is
  built, local beats the global model **in all 11** (ΔR² **+0.144** on those same rows). The gains are
  largest on the harder, higher-variance countries — e.g. TCD, NGA, SOM, SSD, GTM, HND all flip from
  negative to positive R² under a local or regional model.
- **The clusters don't help at admin-1** (ΔR² ±0.01 — effectively flat). The unsupervised
  driver-fingerprint groups aren't a better partition than the geography we already have here.

The per-country picture across all scopes — R² (left) and MAE (right), one marker per scope, best
country at the top:

![Static inference — per-country R² & MAE by training scope](results/static_inference/imputed/scope_comparison.png)

Read **both panels together**: R² is variance-explained *within* a country, so a stable, low-crisis
country (SEN, BEN, GHA) can post a large-negative R² while its MAE is only 3–6 pp — the model is
actually fine there, R² is just the wrong lens. What the chart shows cleanly is that for almost every
country the coloured **regional / local** markers sit to the right (higher R²) and to the left (lower
MAE) of the grey **global** marker.

---

## 5 · What drives food insecurity

Finally, the global model's explanation. Aggregated SHAP (mean |SHAP|) for XGBoost on the imputed
data, by data source:

![Static inference — SHAP beeswarm (global model, imputed)](results/static_inference/imputed/shap_beeswarm.png)

| driver family | mean \|SHAP\| |
|---|---|
| **food prices** | 4.04 |
| **conflict** | 3.88 |
| seasonality | 3.38 |
| vegetation | 2.87 |
| **displacement** | 2.56 |
| media | 2.15 |
| rainfall | 1.76 |

- **Food prices and conflict dominate the explanation** — the two strongest levers on how much of a
  population is in crisis, which matches the field intuition (price shocks and violence drive acute
  food insecurity).
- **Displacement, vegetation and rainfall add real context** but sit a tier below; media is the
  weakest single family.
- The hierarchy is **stable and interpretable** — a direct benefit of the drivers-only, no-geography
  design: because the model can't lean on "which country", every bit of signal it uses is an actual
  driver relationship we can read off.

**Does it scale?** Run the identical static round one geographic level finer and it **strengthens** — at
admin-2 the drivers *beat* the country-mean baseline (which they can't here), and localization wins even
more broadly. See [overview_admin2.md](overview_admin2.md).

---

*Reference: full pipeline mechanics in [methodology.md](methodology.md); complete results record
(both datasets, all rounds, admin-2) in [overview.md](overview.md). Companion narrative for the other
round: [overview_nowcast.md](overview_nowcast.md).*
