import os

# Base directories
TS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(TS_DIR, "..", "..", ".."))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

# Dataset Path (Step 1 Imputed Parquet)
DATASET_PATH = os.path.join(DATA_DIR, "merged", "merged_adm1_wide_norm_f_imputed.parquet")

# Output directory for results (saved in TSclusters/results)
OUTPUT_DIR = os.path.abspath(os.path.join(TS_DIR, "..", "results"))
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Target column for univariate clustering
TARGET_COL = "phase_3plus_percentage"

# Columns to use for multivariate clustering
MULTIVARIATE_COLS = [
    "phase_3plus_percentage",
    "rain_anomaly_3m",
    "wfp_price",
    "ndvi_vim",
    "acled_political_violence_events_per_100k_population",
    "idp_population_over_adm1_population"
]

# Minimum number of valid regions a country must have to be eligible for country-level clustering
ELIGIBLE_MIN_REGIONS = 4

# Number of clusters to evaluate for Silhouette score
K_VALUES = [2, 3, 4, 5]
