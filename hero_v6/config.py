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
# - WFP prices ship pre-prepared at data/raw/wfp_with_pcodes.parquet. They originate
#   from a prep chain that ran upstream (PIP + elastic-buffer market->pcode mapping);
#   that chain is not part of this folder. See WFP_WITH_PCODES below and README.md.

LIMIT   = 10000
TIMEOUT = 60
PAUSE   = 0.1

# pyarrow's DLLs are broken in the ewm env; fastparquet works there.
PARQUET_ENGINE = "fastparquet"

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
RAW_DIR    = os.path.join(BASE_DIR, "data", "raw")
FINAL_DIR  = os.path.join(BASE_DIR, "data", "merged")

# Legacy single-output paths (kept for backwards compatibility with widen.py defaults).
FINAL_FILE      = os.path.join(FINAL_DIR, "merged.parquet")
FINAL_FILE_WIDE = os.path.join(FINAL_DIR, "merged_wide.parquet")

# Admin-level-split outputs. merge.py writes the long *_adm{1,2}.parquet; widen.py pivots
# them to the wide *_adm{1,2}_wide.parquet (the files shipped in data/merged/).
FINAL_FILE_ADM1      = os.path.join(FINAL_DIR, "merged_adm1.parquet")
FINAL_FILE_ADM2      = os.path.join(FINAL_DIR, "merged_adm2.parquet")
FINAL_FILE_ADM1_WIDE = os.path.join(FINAL_DIR, "merged_adm1_wide.parquet")
FINAL_FILE_ADM2_WIDE = os.path.join(FINAL_DIR, "merged_adm2_wide.parquet")

# WFP food prices: ships pre-prepared in data/raw/. Provenance is an upstream prep chain
# (PIP + intentional elastic buffer for coastal markets); see README.md.
WFP_WITH_PCODES = os.path.join(RAW_DIR, "wfp_with_pcodes.parquet")

# GDELT media-based conflict signals: monthly panel pre-aggregated into 4 CAMEO QuadClasses
# (3 metrics x 4 QuadClasses). Separate files for ADM1 and ADM2.
GDELT_FILE_ADM1 = os.path.join(RAW_DIR, "df_gdelt4_adm1.parquet")
GDELT_FILE_ADM2 = os.path.join(RAW_DIR, "df_gdelt4_adm2.parquet")

# NDVI vegetation signals (WFP/HDX): dekadal, both admin levels, keyed on PCODE + adm_level.
# Explicit path because the filename isn't ndvi.parquet.
NDVI_FILE = os.path.join(RAW_DIR, "wfp_ndvi.parquet")


def raw_file(theme_key):
    """Path to the single global parquet for a theme (one file per domain)."""
    return os.path.join(RAW_DIR, f"{theme_key}.parquet")
