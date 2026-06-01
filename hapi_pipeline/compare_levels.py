"""
compare_levels.py — Per-country match coverage: pure admin2 vs admin2 + admin1 fallback.

Derives the numbers from the real merge pipeline (merge.merge_country), so it always
reflects the current config (including the IDP staleness cap, MAX_IDP_STALENESS_DAYS).

Match level columns produced by merge_country:
  *_match_level == 2  -> matched at admin2 (district)
  *_match_level == 1  -> filled from admin1 (province)
  *_match_level is NA  -> no match

  admin2 coverage   = share of rows with level == 2
  fallback coverage = share of rows with level in {1, 2}

Covers ACLED, IDP, and rainfall. Writes compare_levels.csv and prints the row-weighted
overall coverage.

Usage:
    python compare_levels.py
"""

import pandas as pd
import merge as M
from config import COUNTRIES, MAX_IDP_STALENESS_DAYS


def main():
    ipc_all, acled_all, idp_all = M.load("ipc"), M.load("acled"), M.load("idp")
    rain_all = M.load("rainfall")

    rows = []
    for iso3 in COUNTRIES:
        df = M.merge_country(iso3, ipc_all, acled_all, idp_all, rain_all)
        if df.empty:
            continue
        n = len(df)
        al = df["acled_match_level"]
        il = df["idp_match_level"]
        rl = df["rain_match_level"]
        rows.append(dict(
            iso3=iso3,
            ipc_rows=n,
            acled_admin2=round(100 * (al == 2).sum() / n, 1),
            acled_fallback=round(100 * al.notna().sum() / n, 1),
            idp_admin2=round(100 * (il == 2).sum() / n, 1),
            idp_fallback=round(100 * il.notna().sum() / n, 1),
            rain_admin2=round(100 * (rl == 2).sum() / n, 1),
            rain_fallback=round(100 * rl.notna().sum() / n, 1),
        ))

    df = pd.DataFrame(rows)
    df.to_csv("compare_levels.csv", index=False)

    def wavg(col):
        return round((df[col] * df["ipc_rows"]).sum() / df["ipc_rows"].sum(), 1)

    print(f"IDP staleness cap: {MAX_IDP_STALENESS_DAYS} days   |   countries: {len(df)}\n")
    print("Row-weighted coverage across all IPC rows:")
    print(f"  ACLED: pure admin2 {wavg('acled_admin2')}%  ->  with admin1 fallback {wavg('acled_fallback')}%")
    print(f"  IDP  : pure admin2 {wavg('idp_admin2')}%  ->  with admin1 fallback {wavg('idp_fallback')}%")
    print(f"  RAIN : pure admin2 {wavg('rain_admin2')}%  ->  with admin1 fallback {wavg('rain_fallback')}%")
    print("\nSaved -> compare_levels.csv")


if __name__ == "__main__":
    main()
