"""
compare_levels.py — Per-country theme coverage at each admin level.

With the admin1/admin2 split in merge.py, IPC's own `admin_level` decides the level
per row — there's no fallback to compare against anymore. This script reports raw
theme coverage (share of rows with non-null values) for each (country, admin_level,
theme) cell. Derived from the live `merge.merge_country`, so it always reflects
current config (including the IDP staleness cap, MAX_IDP_STALENESS_DAYS).

Themes: ACLED (acled_total_events), IDP (idp_population), rainfall (rain_1m_sum),
        WFP (wfp_price).

Writes compare_levels.csv and prints row-weighted overall coverage per level.

Usage:
    python compare_levels.py
"""

import os
import pandas as pd

import merge as M
from config import COUNTRIES, MAX_IDP_STALENESS_DAYS, WFP_WITH_PCODES, PARQUET_ENGINE


def main():
    ipc_all   = M.load("ipc")
    acled_all = M.load("acled")
    idp_all   = M.load("idp")
    rain_all  = M.load("rainfall")
    wfp_all   = (
        pd.read_parquet(WFP_WITH_PCODES, engine=PARQUET_ENGINE)
        if os.path.exists(WFP_WITH_PCODES) else pd.DataFrame()
    )

    rows = []
    for admin_level, join_key_col in [(1, "admin1_code"), (2, "admin2_code")]:
        for iso3 in COUNTRIES:
            df = M.merge_country(iso3, ipc_all, acled_all, idp_all, rain_all, wfp_all,
                                 join_key_col, admin_level)
            if df.empty:
                continue
            n = len(df)
            def cov(col):
                return round(100 * df[col].notna().sum() / n, 1) if col in df.columns else 0.0
            rows.append(dict(
                iso3=iso3,
                admin_level=admin_level,
                ipc_rows=n,
                acled=cov("acled_total_events"),
                idp=cov("idp_population"),
                rain=cov("rain_1m_sum"),
                wfp=cov("wfp_price"),
            ))

    df = pd.DataFrame(rows)
    df.to_csv("compare_levels.csv", index=False)

    print(f"IDP staleness cap: {MAX_IDP_STALENESS_DAYS} days   |   "
          f"countries seen: {df['iso3'].nunique()}\n")
    for lvl in (1, 2):
        sub = df[df["admin_level"] == lvl]
        if sub.empty:
            print(f"admin{lvl}: no rows.")
            continue
        def wavg(col):
            return round((sub[col] * sub["ipc_rows"]).sum() / sub["ipc_rows"].sum(), 1)
        print(f"admin{lvl} ({sub['ipc_rows'].sum():,} IPC rows across {len(sub)} countries):")
        print(f"  ACLED {wavg('acled')}%  |  IDP {wavg('idp')}%  |  "
              f"RAIN {wavg('rain')}%  |  WFP {wavg('wfp')}%")

    print("\nSaved -> compare_levels.csv")


if __name__ == "__main__":
    main()
