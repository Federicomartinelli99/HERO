"""
widen.py — Pivot hapi_merged_2017.parquet from long to wide format.

The long file has 7 rows per (location, period, ipc_type) — one per IPC phase
(1, 2, 3, 3+, 4, 5, all). This collapses them into 1 wide row with
phase_1_number ... phase_all_percentage columns, matching the column naming
conventions of the legacy workflow.

Pivot strategy:
  - Pivot only on the minimal key (no ACLED/IDP/rainfall in the index) to avoid
    pivot_table silently dropping rows where pass-through columns are NaN.
  - Join the pass-through columns (ACLED, IDP, rainfall, admin names, dates) from
    the 'all' phase rows — identical across all 7 phase rows per key.

Usage:
    python widen.py
"""

import pandas as pd
from config import FINAL_FILE, FINAL_FILE_WIDE, PARQUET_ENGINE

PHASE_SUFFIX = {
    "1": "1", "2": "2", "3": "3", "3+": "3plus", "4": "4", "5": "5", "all": "all"
}

# Minimal key that uniquely identifies one (location, period, ipc_type) at one admin level.
KEY_COLS = [
    "location_code", "admin1_code", "admin2_code", "admin_level",
    "ipc_start", "ipc_end", "ipc_type",
]


def main():
    df = pd.read_parquet(FINAL_FILE, engine=PARQUET_ENGINE)
    print(f"Loaded: {len(df):,} rows x {len(df.columns)} cols")

    # fastparquet reads nullable string columns back as pd.NA; groupby drops NaN keys.
    # Fill admin code NaN with '' so all rows survive the pivot.
    for col in ("admin1_code", "admin2_code"):
        df[col] = df[col].fillna("").astype(str)

    # Step 1: Pivot only on the minimal key — no pass-through cols in the index so NaN
    # values in ACLED/IDP/rainfall don't cause row drops.
    pivot = df.pivot_table(
        index=KEY_COLS,
        columns="ipc_phase",
        values=["population_in_phase", "population_fraction_in_phase"],
        aggfunc="first",
    )
    pivot.columns = [
        f"phase_{PHASE_SUFFIX[str(ph)]}_{('number' if val == 'population_in_phase' else 'percentage')}"
        for val, ph in pivot.columns
    ]
    pivot = pivot.reset_index()
    print(f"After pivot: {len(pivot):,} rows")

    # Step 2: Get pass-through columns from 'all' phase rows
    # (values are identical across all 7 phase rows for the same key).
    passthrough_cols = [c for c in df.columns
                        if c not in ("ipc_phase", "population_in_phase",
                                     "population_fraction_in_phase")
                        and c not in KEY_COLS]
    passthrough = (
        df[df["ipc_phase"] == "all"][KEY_COLS + passthrough_cols]
        .drop_duplicates(subset=KEY_COLS, keep="first")
        .copy()
    )

    # Step 3: Join pivot + pass-through.
    wide = pivot.merge(passthrough, on=KEY_COLS, how="left")

    # Convert fractions (0-1) to percentages (0-100).
    for col in [c for c in wide.columns if c.endswith("_percentage")]:
        wide[col] = wide[col] * 100

    # Rename to match legacy column conventions.
    wide = wide.rename(columns={
        "location_code":          "Country",   # match old file: ISO3 codes, not full names
        "location_name":          "location_name_full",
        "admin1_name":            "Level 1",
        "admin2_name":            "Area",
        "admin1_code":            "adm1_pcode",
        "admin2_code":            "adm2_pcode",
        "ipc_start":              "From",
        "ipc_end":                "To",
        "ipc_type":               "Validity period",
        "reference_period_start": "Date of analysis",
        "rain_1m_mean":           "rain_1m",
        "rain_3m_mean":           "rain_3m",
        "rain_anom_1m_mean":      "rain_anomaly_1m",
        "rain_anom_3m_mean":      "rain_anomaly_3m",
        "rain_match_level":       "rainfall_match_level",
    })

    # Reorder: identity cols first, then phase cols, then ACLED/IDP/rainfall.
    id_cols = ["Country", "location_name_full", "Level 1", "Area",
               "adm1_pcode", "adm2_pcode",
               "From", "To", "Validity period", "Date of analysis",
               "admin_level", "resource_hdx_id"]
    phase_cols = [f"phase_{s}_{t}"
                  for s in ["1", "2", "3", "3plus", "4", "5", "all"]
                  for t in ["number", "percentage"]]
    rest_cols = [c for c in wide.columns if c not in id_cols + phase_cols]
    wide = wide[[c for c in id_cols + phase_cols + rest_cols if c in wide.columns]]

    wide.to_parquet(FINAL_FILE_WIDE, index=False, engine=PARQUET_ENGINE)
    print(f"Saved: {len(wide):,} rows x {len(wide.columns)} cols")
    print(f"File: {FINAL_FILE_WIDE}")


if __name__ == "__main__":
    main()
