import os

# Base directories
CODES_DIR = os.path.dirname(os.path.abspath(__file__))
TS_INDIVIDUAL_DIR = os.path.abspath(os.path.join(CODES_DIR, ".."))
PROJECT_ROOT = os.path.abspath(os.path.join(TS_INDIVIDUAL_DIR, "..", ".."))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

# Dataset paths
DATASET_PATH = os.path.join(DATA_DIR, "merged", "merged_adm1_wide_norm_f_imputed.parquet")
WFP_PATH = os.path.join(DATA_DIR, "raw", "wfp_with_pcodes.parquet")
GEOJSON_PATH = os.path.join(DATA_DIR, "boundaries", "afg", "afg_admin1.geojson")

# Output directories (Hierarchical structure)
OUTPUT_DIR = os.path.join(TS_INDIVIDUAL_DIR, "results")
DOCS_DIR = os.path.join(TS_INDIVIDUAL_DIR, "docs")

# Subdirectories for each task
STATIONARITY_STL_DIR = os.path.join(OUTPUT_DIR, "01_stationarity_stl")
CROSS_CORRELATION_DIR = os.path.join(OUTPUT_DIR, "02_cross_correlation")
MATRIX_PROFILE_DIR = os.path.join(OUTPUT_DIR, "03_matrix_profile")
SHAPELETS_DIR = os.path.join(OUTPUT_DIR, "04_shapelets")
CATCH22_DIR = os.path.join(OUTPUT_DIR, "05_catch22")
CLUSTERING_DIR = os.path.join(OUTPUT_DIR, "06_clustering_dtw_ncd")
MARKET_NETWORK_DIR = os.path.join(OUTPUT_DIR, "07_market_network")
SPATIAL_AUTOCORRELATION_DIR = os.path.join(OUTPUT_DIR, "08_spatial_autocorrelation")
DBSCAN_OUTLIERS_DIR = os.path.join(OUTPUT_DIR, "09_dbscan_outliers")
NATIONAL_LEVEL_DIR = os.path.join(OUTPUT_DIR, "10_national_level")

# Create all folders
for folder in [OUTPUT_DIR, DOCS_DIR, STATIONARITY_STL_DIR, CROSS_CORRELATION_DIR,
               MATRIX_PROFILE_DIR, SHAPELETS_DIR, CATCH22_DIR, CLUSTERING_DIR,
               MARKET_NETWORK_DIR, SPATIAL_AUTOCORRELATION_DIR, DBSCAN_OUTLIERS_DIR,
               NATIONAL_LEVEL_DIR]:
    os.makedirs(folder, exist_ok=True)

# Analysis settings
COUNTRY = "AFG"
TARGET_COL = "phase_3plus_percentage"

# Columns to use for multivariate TS analysis
MULTIVARIATE_COLS = [
    "phase_3plus_percentage",
    "rain_anomaly_3m",
    "wfp_price",
    "ndvi_vim",
    "acled_political_violence_events_per_100k_population",
    "idp_population_over_adm1_population"
]

# Benchmark representative provinces for detailed visualization
REPRESENTATIVE_PROVINCES = ["Kabul", "Hirat", "Kandahar", "Balkh"]
