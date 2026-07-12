import os

# Base directory for the TSA module
TSA_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(TSA_DIR, ".."))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

# Parquet file paths
WFP_PARQUET = os.path.join(DATA_DIR, "tmp", "wfp_monthly_adm1_index.parquet")
RAIN_PARQUET = os.path.join(DATA_DIR, "raw", "rainfall.parquet")
ACLED_PARQUET = os.path.join(DATA_DIR, "raw", "acled.parquet")
IDP_PARQUET = os.path.join(DATA_DIR, "raw", "idp.parquet")
MERGED_PARQUET = os.path.join(DATA_DIR, "merged", "merged_adm1_wide.parquet")

# Countries to run the pipeline on
TARGET_COUNTRIES = ['AFG']

# List of predictors for Stage 1 & Stage 2 models
PREDICTORS = [
    "wfp_price_mean", "wfp_inflation_mean", 
    "rain_1m", "rain_3m", "rain_anomaly_1m", "rain_anomaly_3m", 
    "acled_events", "acled_fatalities", 
    "idp_population"
]

# Forecast horizon (months ahead)
FORECAST_STEPS = 12

# Output directory for saving plots, metrics and reports
RESULTS_DIR = os.path.join(TSA_DIR, "results")

# Weights for calculating the Reliability Index
RELIABILITY_WEIGHTS = {
    "w_missing": 0.4,       # weight for total missing ratio
    "w_gap": 0.4,           # weight for max gap relative length
    "w_recent": 0.2         # weight for missing recent values (last 12 months)
}

# Ensure directories exist
os.makedirs(RESULTS_DIR, exist_ok=True)
