"""
Central configuration for the HERO v6 modelling pipeline — every modelling decision lives here,
so the rest of the code reads as plain steps.

Predict `phase_3plus_percentage` (share of an admin-1 population in IPC Phase 3+, "Crisis or worse")
from food-security drivers, on the colleague's feature-engineered admin-1 data. Two datasets are
compared, differing ONLY in how missing values are handled:
    unimputed -> missing values kept (tree models handle NaN natively)
    imputed   -> missing values filled in
Models are drivers-only: no country identity, no coordinates.

`config` is imported first everywhere, so the OpenMP/MKL guards below run before numpy is imported.
"""

import os
# MUST be set before numpy is imported. XGBoost/LightGBM bundle their own OpenMP runtime; without
# these, numpy-MKL LAPACK calls (e.g. via matplotlib) crash on Windows with fatal exception 0xc06d007f.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("MKL_THREADING_LAYER", "SEQUENTIAL")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

from pathlib import Path
from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor
from lightgbm import LGBMRegressor

# ----------------------------------------------------------------------------- paths
PIPELINE_DIR = Path(__file__).resolve().parent            # .../hero_v6/ML/pipeline
HERO_ROOT    = PIPELINE_DIR.parents[1]                     # .../hero_v6
MERGED_DIR   = HERO_ROOT / "data" / "merged"
RESULTS_DIR  = PIPELINE_DIR / "results"

# ----------------------------------------------------------------------------- spatial level (the knob)
# LEVEL selects admin-1 or admin-2; set it via the HERO_LEVEL env var (run_all.py sets it from its CLI
# arg). It is read once, here, so every `from config import AREA_COL` across the pipeline stays valid.
#   adm1 -> the colleague's normalized+imputed v3 files (unimputed & imputed variants)
#   adm2 -> merged_adm2_wide_norm.parquet, built by prepare_adm2.py (unimputed only; native-NaN)
LEVEL = os.environ.get("HERO_LEVEL", "adm1").lower()
assert LEVEL in ("adm1", "adm2"), "HERO_LEVEL must be 'adm1' or 'adm2'"

IMPUTATION_DIR = HERO_ROOT / "data" / "Imputation and clustering"
if LEVEL == "adm1":
    DATASETS = {
        "unimputed": IMPUTATION_DIR / "merged_adm1_wide_norm_v3.parquet",
        "imputed":   IMPUTATION_DIR / "merged_adm1_wide_norm_imputato_v3.parquet",
    }
else:  # adm2 — only the in-pipeline-normalized unimputed variant exists
    DATASETS = {"unimputed": MERGED_DIR / "merged_adm2_wide_norm.parquet"}

CLUSTERS_PATH = IMPUTATION_DIR / "regioni_clusterizzate.csv"   # static per-adm1 cluster assignments

def results_dir(round_name: str, dataset: str) -> Path:
    """`results/<round_name>/<dataset>/` (adm1) or `results/<round_name>/adm2/<dataset>/` (adm2).

    adm2 is nested under an extra `adm2/` segment so the adm1 result tree (and its doc image links) is
    left completely untouched. Created on demand.
    """
    path = (RESULTS_DIR / round_name / dataset if LEVEL == "adm1"
            else RESULTS_DIR / round_name / "adm2" / dataset)
    path.mkdir(parents=True, exist_ok=True)
    return path

# ----------------------------------------------------------------------------- target & keys
TARGET      = "phase_3plus_percentage"   # what we predict, on its native 0-100 scale (no transform)
AREA_COL    = "adm1_pcode" if LEVEL == "adm1" else "adm2_pcode"   # spatial unit (the level knob)
CLUSTER_JOIN_COL = "adm1_pcode"          # clusters are per-adm1; both levels carry adm1_pcode to join on
COUNTRY_COL = "Country"                   # reporting dimension only — never a model feature
# Data-driven clusters (colleague's unsupervised, feature-based clustering of each area's driver
# time-series "fingerprint" — not derived from the target, and static per area, so joined into BOTH
# datasets from CLUSTERS_PATH by AREA_COL). Two schemes, each its own localization scope; both exclude
# lat/long so the grouping stays purely behavioral. Never a model feature.
CLUSTER_SCOPES = {
    "cluster_kmeans":       "kmeans_features_no_coords",
    "cluster_hierarchical": "hierarchical_features_no_coords",
}

# ----------------------------------------------------------------------------- driver features
# The colleague's already rate-normalized drivers (per-100k / per-population), taken as-is.
# Drivers only: no country, no latitude/longitude. `features.build_features` also adds cyclical
# seasonality (month_sin, month_cos), for 13 model features total.
DRIVERS = [
    "acled_political_violence_events_per_100k_population",   # conflict intensity
    "acled_total_fatalities_per_100k_population",            # conflict lethality
    "idp_population_over_adm1_population",                   # displacement rate
    "rain_3m", "rain_anomaly_3m",                           # rainfall level & anomaly
    "wfp_price", "wfp_inflation",                           # food prices
    "ndvi_vim", "ndvi_viq",                                 # vegetation / drought
    "gdelt_material_coop_events_per_100k_population",        # media: cooperation
    "gdelt_verbal_conflict_events_per_100k_population",      # media: conflict
]

# ----------------------------------------------------------------------------- models
RANDOM_STATE = 42

def make_models() -> dict:
    """Fresh estimators every call (clean folds). All four handle NaN natively; no tuning."""
    return {
        "decision_tree": DecisionTreeRegressor(
            random_state=RANDOM_STATE, min_samples_leaf=20),
        "random_forest": RandomForestRegressor(
            n_estimators=400, min_samples_leaf=5, n_jobs=-1, random_state=RANDOM_STATE),
        "xgboost": XGBRegressor(
            tree_method="hist", n_estimators=400, learning_rate=0.05, max_depth=6,
            subsample=0.8, colsample_bytree=0.8, random_state=RANDOM_STATE, n_jobs=-1),
        "lightgbm": LGBMRegressor(
            n_estimators=400, learning_rate=0.03, num_leaves=31, subsample=0.8,
            colsample_bytree=0.8, min_child_samples=40, random_state=RANDOM_STATE,
            n_jobs=1, verbose=-1),
    }

HEADLINE_MODEL   = "xgboost"   # used for SHAP explainability and the localization scopes
SHAP_SAMPLE_SIZE = 3000        # rows sampled for the SHAP TreeExplainer

# ----------------------------------------------------------------------------- static validation
# GroupKFold by area: whole areas are held out, so test areas are unseen. This is the only static
# split — a random split would leak (an area recurs across time windows and neighbours resemble
# each other, so the model would recognise the area instead of learning drivers -> IPC).
N_SPLITS = 5

# ----------------------------------------------------------------------------- nowcast validation
# Rolling-origin (walk-forward) expanding backtest: for each origin, train on all windows before it
# and test the next TEST_WINDOW_MONTHS — never uses the future to predict the past.
BACKTEST_ORIGINS   = ["2023-07-01", "2024-01-01", "2024-07-01", "2025-01-01", "2025-07-01"]
TEST_WINDOW_MONTHS = 6

# ----------------------------------------------------------------------------- localization scopes
# Region map over the ISO3 codes present (geographic / agro-climatic grouping).
REGIONS = {
    "Sahel/West Africa":    ["MLI", "BFA", "NER", "TCD", "SEN", "MRT", "GMB", "GNB",
                             "NGA", "GHA", "CIV", "LBR", "SLE", "TGO", "BEN", "GIN", "CPV"],
    "Horn/East Africa":     ["SOM", "ETH", "SSD", "KEN", "SDN", "DJI", "UGA", "TZA"],
    "Central Africa":       ["COD", "CAF", "CMR"],
    "Southern Africa":      ["MOZ", "ZMB", "ZWE", "NAM", "MDG", "ZAF"],
    "Latin America/Carib.": ["GTM", "HND", "HTI", "SLV", "ECU"],
    "Asia":                 ["AFG", "YEM", "PAK", "BGD", "TLS"],
}

# Only build a per-country (local) model where a full XGBoost is defensible — it overfits below a few
# hundred rows, and R² is unstable on few points. These floors keep localized results trustworthy.
MIN_ROWS_FOR_LOCAL_MODEL  = 300   # rows needed to attempt a per-country model
MIN_AREAS_FOR_LOCAL_MODEL = 6     # areas needed for a within-country area hold-out (static)
MIN_TRAIN_ROWS_PER_FOLD   = 100   # rows needed in a rolling-origin train fold to fit (nowcast)
# Scored rows needed to report a per-country metric. Per round because "scored rows" means different
# things: static = out-of-fold rows (plentiful), nowcast = current windows inside the backtest eval
# folds (a small recent slice by design), so the nowcast floor is lower to avoid dropping data-rich
# countries that simply have few recent test windows.
MIN_ROWS_TO_REPORT_STATIC  = 40
MIN_ROWS_TO_REPORT_NOWCAST = 30
