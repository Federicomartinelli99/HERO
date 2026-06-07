import os

COUNTRIES = [
    "AFG", "AGO", "BDI", "BEN", "BFA", "BGD", "CAF", "CIV", "CMR", "COD",
    "CPV", "DJI", "DOM", "ECU", "ETH", "GHA", "GIN", "GMB", "GNB", "GTM",
    "HND", "HTI", "KEN", "LBN", "LBR", "LSO", "MDG", "MLI", "MOZ", "MRT",
    "MWI", "NAM", "NER", "NGA", "PAK", "PSE", "SDN", "SEN", "SLE", "SLV",
    "SOM", "SSD", "SWZ", "TCD", "TGO", "TLS", "TZA", "UGA", "YEM", "ZAF",
    "ZMB", "ZWE",
]
DATE_FROM = "2017-01-01"

# Drop an IDP match if its snapshot is older than this many days before the IPC period end
# (carry-forward staleness cap). Set to None to disable the filter.
MAX_IDP_STALENESS_DAYS = 400

APP_NAME       = "hapi-align-test"
EMAIL          = "jonas.demeyer1@gmail.com"
APP_IDENTIFIER = ""  # paste a token here to skip auto-generation

API_BASE = "https://hapi.humdata.org/api"
API_VER  = "v2"
THEMES   = {
    "ipc":  "food-security-nutrition-poverty/food-security",
    "acled": "coordination-context/conflict-events",
    "idp":  "affected-people/idps",
}
# Note: rainfall and WFP are NOT fetched from the API.
# - data/raw/rainfall.parquet is supplied externally (ISO3 + PCODE + adm_level,
#   wide rain_1m/3m columns) and read directly by merge.py via raw_file("rainfall").
# - WFP prices come from hero_v5/data/wfp_with_pcodes.parquet, produced by the
#   two-script prep chain in hero_v5/libs/ (wfp_consolidate.py + wfp_spatial_mapping.py).
#   See WFP_WITH_PCODES below and DECISIONS.md for the contract.

LIMIT   = 10000
TIMEOUT = 60
PAUSE   = 0.1

# pyarrow's DLLs are broken in the ewm env; fastparquet works there.
PARQUET_ENGINE = "fastparquet"

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
RAW_DIR    = os.path.join(BASE_DIR, "data", "raw")
FINAL_DIR  = os.path.join(BASE_DIR, "data", "final")

# Legacy single-output paths (kept for backwards compatibility with widen.py defaults).
FINAL_FILE      = os.path.join(FINAL_DIR, "hapi_merged_2017.parquet")
FINAL_FILE_WIDE = os.path.join(FINAL_DIR, "hapi_merged_2017_wide.parquet")

# Admin-level-split outputs (current).
FINAL_FILE_ADM1      = os.path.join(FINAL_DIR, "hapi_merged_2017_adm1.parquet")
FINAL_FILE_ADM2      = os.path.join(FINAL_DIR, "hapi_merged_2017_adm2.parquet")
FINAL_FILE_ADM1_WIDE = os.path.join(FINAL_DIR, "hapi_merged_2017_adm1_wide.parquet")
FINAL_FILE_ADM2_WIDE = os.path.join(FINAL_DIR, "hapi_merged_2017_adm2_wide.parquet")

# WFP food prices: input contract from the hero_v5/libs/ prep chain.
# Produced by hero_v5/libs/wfp_consolidate.py + hero_v5/libs/wfp_spatial_mapping.py
# (PIP + intentional elastic buffer for coastal markets).
WFP_WITH_PCODES = os.path.join(BASE_DIR, "..", "hero_v5", "data", "wfp_with_pcodes.parquet")

# Boundary GeoJSONs (referenced only by future extensions/, not by merge.py itself).
BOUNDARIES_DIR  = os.path.join(BASE_DIR, "..", "hero_v5", "data", "boundaries")


def raw_file(theme_key):
    """Path to the single global parquet for a theme (one file per domain)."""
    return os.path.join(RAW_DIR, f"{theme_key}.parquet")
