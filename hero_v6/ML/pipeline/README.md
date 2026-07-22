# HERO v6 — modelling pipeline

Clean, self-contained pipeline that predicts **IPC Phase 3+** (`phase_3plus_percentage`, the share of
an admin-1 population in "Crisis or worse") from food-security drivers, on the feature-engineered
admin-1 data. Two datasets are compared, differing **only** in missing-value handling:

- **`unimputed`** — missing values kept (tree models handle NaN natively)
- **`imputed`** — missing values filled in

Models are **drivers only** — no country identity, no coordinates.

## Files

| File | What it is |
|---|---|
| `config.py` | Every modelling decision in one place: datasets, the 13 driver features, models, validation settings, region map, localization floors, output paths. Start here. |
| `features.py` | Shared feature engineering (`build_features`, `build_panel`, `make_features`), scoring, SHAP-by-source, and the validation/localization helpers used by both rounds. |
| `static_inference.py` | **Round 1** — predict IPC from instantaneous drivers (cross-sectional). GroupKFold-by-area validation, SHAP, and global/regional/local scopes. |
| `nowcast.py` | **Round 2** — predict current IPC from the last assessment + latest drivers (temporal). Rolling-origin backtest, skill vs persistence, SHAP, and scopes. |
| `plot_country_metrics.py` | Per-country R²/MAE dot charts for both rounds. |
| `nowcast_viz.py` | Nowcast time-series grids (country-mean + per-admin-1 walk-forward curves). |
| `run_all.py` | Runs everything for one spatial level (all its datasets). |
| `prepare_adm2.py` | One-time: builds the normalized admin-2 dataset from the raw adm2 merge (run before `run_all.py adm2`). |
| `overview.md` | Results narrative (imputed vs unimputed, all three rounds, + admin-2 extension). |
| `methodology.md` | How the analysis is done and why (validation, features, decisions). |

## How to run

```
# from hero_v6/ML/pipeline, with the `ewm` conda env:
python run_all.py                       # admin-1: both datasets, all rounds + figures
python static_inference.py imputed      # one round, one dataset (admin-1)
python nowcast.py unimputed
python plot_country_metrics.py imputed
python nowcast_viz.py imputed

# admin-2 (unimputed only) — build the dataset once, then run at that level:
python prepare_adm2.py
python run_all.py adm2
```

Outputs: `results/<round>/<dataset>/` for admin-1 (e.g. `results/static_inference/imputed/`) and
`results/<round>/adm2/<dataset>/` for admin-2. The spatial level is the `HERO_LEVEL` env var, which
`run_all.py` sets from its argument.

## Vocabulary

- **area** — an admin-1 unit (`adm1_pcode`); the spatial unit of analysis.
- **window** — an IPC assessment period (its start date `From`).
- **driver** — an input feature (conflict, displacement, rainfall, vegetation, prices, media, seasonality).
- **scope** — the breadth of training data for localization: **global** (all countries) / **regional**
  (6-region map) / **local** (one country).
- **dataset** — `imputed` or `unimputed` (the only thing that varies between the two runs).

## Notes

- Reads the shared parquets in `../../data/merged/`; writes only inside this folder.
- Admin-2 is a later phase — `config.AREA_COL` is the single knob that would switch the spatial level.
