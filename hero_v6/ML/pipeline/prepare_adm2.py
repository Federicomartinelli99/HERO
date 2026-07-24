"""
Build the admin-2 modelling dataset from the raw admin-2 merge.

`merged_adm2_wide.parquet` only has raw event *counts* (ACLED, IDP, GDELT), not the rate-normalized
drivers the pipeline expects. This script reproduces the adm1 normalization at adm2 level so the same
drivers-only pipeline can run unchanged (with AREA_COL=adm2_pcode). It writes
`merged_adm2_wide_norm.parquet` next to the raw file.

Normalization mirrors adm1 (`raw / population * 1e5`, and `idp / population`) but adm2 has no total
population column, so we use a **static per-area proxy**: the max `phase_all_number` (assessed
population) seen for each adm2 area. Static per area (like adm1_population) avoids a moving denominator;
it is *assessed*, not total, population — see methodology.md for the caveat. The 6 already-rate/index
drivers (rain, wfp, ndvi) are left as-is. Clusters are NOT added here — `features.load_dataset` joins
them from the parent adm1 at load time.

Run:  python prepare_adm2.py
"""

import config  # first — sets OpenMP/MKL guards before numpy is imported
import numpy as np
import pandas as pd

SRC = config.MERGED_DIR / "merged_adm2_wide.parquet"
OUT = config.MERGED_DIR / "merged_adm2_wide_norm.parquet"

# raw count column -> normalized driver name (exactly the names in config.DRIVERS)
PER_100K = {
    "acled_political_violence_events": "acled_political_violence_events_per_100k_population",
    "acled_total_fatalities":          "acled_total_fatalities_per_100k_population",
    "gdelt_material_coop_events":       "gdelt_material_coop_events_per_100k_population",
    "gdelt_verbal_conflict_events":     "gdelt_verbal_conflict_events_per_100k_population",
}
IDP_RATE = ("idp_population", "idp_population_over_adm1_population")   # per-population rate (name kept)


def main():
    print(f"[prepare_adm2] reading {SRC.name}")
    df = pd.read_parquet(SRC)

    # static per-area population proxy: the largest assessed population ever seen for that adm2 unit
    pop = df.groupby("adm2_pcode")["phase_all_number"].transform("max")
    pop = pop.where(pop > 0)                         # guard: 0/NaN pop -> NaN rate (never divide by 0)

    for raw_col, rate_col in PER_100K.items():
        df[rate_col] = df[raw_col] / pop * 1e5       # NaN raw -> NaN rate (native-NaN preserved)
    idp_raw, idp_rate = IDP_RATE
    df[idp_rate] = df[idp_raw] / pop

    made = list(PER_100K.values()) + [idp_rate]
    df.to_parquet(OUT, index=False)
    print(f"[prepare_adm2] wrote {OUT.name}: {len(df):,} rows, {df['adm2_pcode'].nunique():,} adm2 areas")
    print("  new driver columns (non-null count):")
    for c in made:
        print(f"    {c:52s} {int(df[c].notna().sum()):>7,}")


if __name__ == "__main__":
    main()
