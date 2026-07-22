import os

# Base directories
CODES_DIR = os.path.dirname(os.path.abspath(__file__))
TS_GRAPH_DIR = os.path.abspath(os.path.join(CODES_DIR, ".."))
PROJECT_ROOT = os.path.abspath(os.path.join(CODES_DIR, "..", "..", "..", ".."))

DATA_DIR = os.path.join(PROJECT_ROOT, "hero_v6", "data")

# Dataset paths
WFP_PATH = os.path.join(DATA_DIR, "raw", "wfp_with_pcodes.parquet")
GEOJSON_PATH = os.path.join(DATA_DIR, "boundaries", "afg", "afg_admin1.geojson")

# Output directory (hierarchical by Country)
OUTPUT_DIR = os.path.join(TS_GRAPH_DIR, "results")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Target countries to process (set to None for ALL)
TARGET_COUNTRIES = None

# Graph configuration
GLOBAL_HUB_COUNT = 5 # Number of top markets per country to include in the Global Graph
LAGS = [0, 1, 2, 3] # Months of delay

# Threshold Parameters
TOPOLOGICAL_PERCENTILE = 95 # Keep top 5% of edges
N_PERMUTATIONS = 100 # For statistical significance of STE/MI
P_VALUE_THRESH = 0.05

FIXED_THRESHOLDS = {
    'Pearson': 0.92,
    'STE': 0.22,
    'MI': 0.10
}
