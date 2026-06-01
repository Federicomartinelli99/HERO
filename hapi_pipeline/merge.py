"""
merge.py — Join IPC (anchor) with ACLED and IDP for each country.

Reads one global parquet per theme (data/raw/{theme}.parquet), slices each country in
memory, and joins IPC with ACLED and IDP.

Join strategy: row-level admin2 with admin1 fallback. Each ACLED/IDP value is first
joined onto the IPC spine at admin2 (district). IPC rows that get no admin2 match are
filled from the admin1 (province) aggregate. Provenance is recorded per row:
  acled_match_level / idp_match_level = 2 (district), 1 (province fill), or NA (no match).
A province-filled value is a whole-province total, so the flag must be respected when
analysing magnitudes.

ACLED aggregation: sum events + fatalities by event_type over each IPC reference period,
  pivoted wide as acled_{event_type}_{events|fatalities}.

IDP matching: most recent IDP snapshot with period_start <= IPC period_end, per admin unit.

Output: data/final/hapi_merged_2017.parquet  (IPC is the spine — no IPC rows are dropped)

Usage:
    python merge.py
"""

import os
import pandas as pd

from config import (
    COUNTRIES, FINAL_DIR, FINAL_FILE, raw_file, PARQUET_ENGINE,
    MAX_IDP_STALENESS_DAYS,
)


# ── helpers ──────────────────────────────────────────────────────────────────

def load(theme_key):
    """Load the single global parquet for a theme (all countries)."""
    path = raw_file(theme_key)
    return pd.read_parquet(path, engine=PARQUET_ENGINE) if os.path.exists(path) else pd.DataFrame()


def to_dt(series):
    return pd.to_datetime(series, utc=True).dt.tz_localize(None)


# ── ACLED aggregation ─────────────────────────────────────────────────────────

def aggregate_acled(acled, join_key_col, ipc_periods):
    """
    Aggregate ACLED monthly rows to IPC reference periods.

    Parameters
    ----------
    acled        : DataFrame with [join_key_col, reference_period_start, event_type, events, fatalities]
    join_key_col : "admin1_code" or "admin2_code"
    ipc_periods  : unique IPC (join_key_col, ipc_start, ipc_end) combinations

    Returns
    -------
    DataFrame with [join_key_col, ipc_start, ipc_end, acled_*_events, acled_*_fatalities,
                    acled_total_events, acled_total_fatalities]
    """
    empty_base = ipc_periods[[join_key_col, "ipc_start", "ipc_end"]].drop_duplicates().copy()

    if acled.empty:
        return empty_base

    acled = acled.copy()
    acled["acled_start"] = to_dt(acled["reference_period_start"])
    acled[join_key_col]  = acled[join_key_col].astype(str)

    # Ensure one row per (key, month, event_type) — handles any residual duplicates
    acled = (
        acled.groupby([join_key_col, "acled_start", "event_type"], as_index=False)
             .agg(events=("events", "sum"), fatalities=("fatalities", "sum"))
    )

    # Join on key, then filter to temporal overlap: ACLED month start within IPC period
    merged = ipc_periods.merge(acled, on=join_key_col, how="left")
    in_period = (merged["acled_start"] >= merged["ipc_start"]) & \
                (merged["acled_start"] <= merged["ipc_end"])
    merged = merged[in_period]

    if merged.empty:
        return empty_base

    summed = (
        merged.groupby([join_key_col, "ipc_start", "ipc_end", "event_type"], as_index=False)
              .agg(events=("events", "sum"), fatalities=("fatalities", "sum"))
    )

    # Pivot event_type wide: acled_{event_type}_{events|fatalities}
    pivot = summed.pivot_table(
        index=[join_key_col, "ipc_start", "ipc_end"],
        columns="event_type",
        values=["events", "fatalities"],
        aggfunc="sum",
        fill_value=0,
    )
    pivot.columns = [f"acled_{col[1]}_{col[0]}" for col in pivot.columns]
    pivot = pivot.reset_index()

    e_cols = [c for c in pivot.columns if c.endswith("_events")]
    f_cols = [c for c in pivot.columns if c.endswith("_fatalities")]
    pivot["acled_total_events"]     = pivot[e_cols].sum(axis=1)
    pivot["acled_total_fatalities"] = pivot[f_cols].sum(axis=1)

    return pivot


# ── IDP matching ──────────────────────────────────────────────────────────────

def match_idp(idp, join_key_col, ipc_ends):
    """
    For each (join_key, ipc_end), find the most recent IDP snapshot where
    idp.reference_period_start <= ipc_end.

    Parameters
    ----------
    idp          : DataFrame with [join_key_col, reference_period_start, population,
                                   assessment_type, reporting_round]
    join_key_col : "admin1_code" or "admin2_code"
    ipc_ends     : unique IPC (join_key_col, ipc_end) combinations

    Returns
    -------
    DataFrame with [join_key_col, ipc_end, idp_population, idp_assessment_type, idp_reporting_round]
    """
    if idp.empty:
        return ipc_ends[[join_key_col, "ipc_end"]].drop_duplicates().copy()

    idp = idp.copy()
    idp["idp_start"]   = to_dt(idp["reference_period_start"])
    idp[join_key_col]  = idp[join_key_col].astype(str)

    idp_cols = [join_key_col, "idp_start", "population", "assessment_type", "reporting_round"]
    merged = ipc_ends.merge(idp[idp_cols], on=join_key_col, how="left")
    merged = merged[merged["idp_start"] <= merged["ipc_end"]]

    result = (
        merged.sort_values("idp_start")
              .groupby([join_key_col, "ipc_end"], as_index=False)
              .last()
              .rename(columns={
                  "population":      "idp_population",
                  "assessment_type": "idp_assessment_type",
                  "reporting_round": "idp_reporting_round",
              })
    )

    # Staleness filter: drop matches whose snapshot is too old for the IPC period.
    result["idp_staleness_days"] = (result["ipc_end"] - result["idp_start"]).dt.days
    if MAX_IDP_STALENESS_DAYS is not None:
        result = result[result["idp_staleness_days"] <= MAX_IDP_STALENESS_DAYS]

    return result.drop(columns=["idp_start"], errors="ignore")


# ── rainfall aggregation ───────────────────────────────────────────────────────

def aggregate_rainfall(rain, join_key_col, level, ipc_periods):
    """
    Aggregate monthly rainfall rows to IPC reference periods, at one admin level.

    Parameters
    ----------
    rain         : country slice with [date, adm_level, PCODE, rain_1m, rain_3m,
                                       rain_anomaly_1m, rain_anomaly_3m]
    join_key_col : "admin1_code" or "admin2_code" (the IPC-side key name to emit)
    level        : 1 or 2 — which native rainfall admin level to use (adm_level)
    ipc_periods  : unique IPC (join_key_col, ipc_start, ipc_end) combinations

    Returns
    -------
    DataFrame with [join_key_col, ipc_start, ipc_end, rain_1m_sum, rain_1m_mean,
                    rain_3m_mean, rain_anom_1m_mean, rain_anom_3m_mean]
    Sum only for 1-month precip (a true period total); 3-month is a rolling/overlapping
    window so mean only; anomalies are percentages so mean only.
    """
    empty_base = ipc_periods[[join_key_col, "ipc_start", "ipc_end"]].drop_duplicates().copy()

    if rain.empty:
        return empty_base

    rain = rain[rain["adm_level"].astype(str) == str(level)].copy()
    if rain.empty:
        return empty_base

    rain["rain_date"]   = to_dt(rain["date"])
    rain[join_key_col]  = rain["PCODE"].astype(str)

    merged = ipc_periods.merge(rain, on=join_key_col, how="left")
    in_period = (merged["rain_date"] >= merged["ipc_start"]) & \
                (merged["rain_date"] <= merged["ipc_end"])
    merged = merged[in_period]

    if merged.empty:
        return empty_base

    agg = (
        merged.groupby([join_key_col, "ipc_start", "ipc_end"], as_index=False)
              .agg(
                  rain_1m_sum=("rain_1m", "sum"),
                  rain_1m_mean=("rain_1m", "mean"),
                  rain_3m_mean=("rain_3m", "mean"),
                  rain_anom_1m_mean=("rain_anomaly_1m", "mean"),
                  rain_anom_3m_mean=("rain_anomaly_3m", "mean"),
              )
    )
    return agg


# ── per-country merge ─────────────────────────────────────────────────────────

def slice_country(df, iso3, col="location_code"):
    if df.empty:
        return df
    return df[df[col] == iso3].copy()


def fill_from_admin1(result, agg1, key_cols, value_cols, primary_col, flag_col):
    """
    Row-level fallback: for IPC rows in `result` that have no admin2 match
    (primary_col is null), fill `value_cols` from the admin1-level aggregate `agg1`
    (joined on `key_cols`) and stamp `flag_col` = 1. Rows already matched at admin2
    keep their district values and flag = 2.

    The admin1 value is a whole-province total, so `flag_col` records the provenance
    (2 = admin2/district, 1 = admin1/province, NA = no match).
    """
    if agg1.empty or primary_col not in agg1.columns:
        return result

    merged = result.merge(agg1, on=key_cols, how="left", suffixes=("", "_a1"))
    need = merged[primary_col].isna() & merged[f"{primary_col}_a1"].notna()

    for c in value_cols:
        a1c = f"{c}_a1"
        if a1c in merged.columns:
            merged.loc[need, c] = merged.loc[need, a1c]
    merged.loc[need, flag_col] = 1

    drop = [f"{c}_a1" for c in value_cols if f"{c}_a1" in merged.columns]
    return merged.drop(columns=drop)


def merge_country(iso3, ipc_all, acled_all, idp_all, rain_all):
    ipc   = slice_country(ipc_all,   iso3)
    acled = slice_country(acled_all, iso3)
    idp   = slice_country(idp_all,   iso3)
    rain  = slice_country(rain_all,  iso3, col="ISO3")

    if ipc.empty:
        print(f"  {iso3}: no IPC data — skipped")
        return pd.DataFrame()

    # Parse IPC dates; keep both admin keys as strings for clean joins.
    ipc = ipc.copy()
    ipc["ipc_start"]   = to_dt(ipc["reference_period_start"])
    ipc["ipc_end"]     = to_dt(ipc["reference_period_end"])
    ipc["admin1_code"] = ipc["admin1_code"].astype(str)
    ipc["admin2_code"] = ipc["admin2_code"].astype(str)

    periods_a2 = ipc[["admin2_code", "ipc_start", "ipc_end"]].drop_duplicates()
    periods_a1 = ipc[["admin1_code", "ipc_start", "ipc_end"]].drop_duplicates()

    # Aggregate ACLED and match IDP at BOTH admin levels (from the same raw rows).
    acled_a2 = aggregate_acled(acled, "admin2_code", periods_a2)
    acled_a1 = aggregate_acled(acled, "admin1_code", periods_a1)
    idp_a2   = match_idp(idp, "admin2_code", ipc[["admin2_code", "ipc_end"]].drop_duplicates())
    idp_a1   = match_idp(idp, "admin1_code", ipc[["admin1_code", "ipc_end"]].drop_duplicates())
    rain_a2  = aggregate_rainfall(rain, "admin2_code", 2, periods_a2)
    rain_a1  = aggregate_rainfall(rain, "admin1_code", 1, periods_a1)

    # ── ACLED: join at admin2, then fill gaps from admin1 ─────────────────────
    result = ipc.merge(acled_a2, on=["admin2_code", "ipc_start", "ipc_end"], how="left")
    if "acled_total_events" not in result.columns:
        result["acled_total_events"] = pd.NA
    acled_cols = [c for c in result.columns if c.startswith("acled_")]
    result["acled_match_level"] = pd.NA
    result.loc[result["acled_total_events"].notna(), "acled_match_level"] = 2
    result = fill_from_admin1(result, acled_a1,
                              ["admin1_code", "ipc_start", "ipc_end"],
                              acled_cols, "acled_total_events", "acled_match_level")

    # ── IDP: join at admin2, then fill gaps from admin1 ───────────────────────
    result = result.merge(idp_a2, on=["admin2_code", "ipc_end"], how="left")
    if "idp_population" not in result.columns:
        result["idp_population"] = pd.NA
    idp_cols = [c for c in result.columns if c.startswith("idp_")]
    result["idp_match_level"] = pd.NA
    result.loc[result["idp_population"].notna(), "idp_match_level"] = 2
    result = fill_from_admin1(result, idp_a1,
                              ["admin1_code", "ipc_end"],
                              idp_cols, "idp_population", "idp_match_level")

    # ── Rainfall: join at admin2, then fill gaps from native admin1 ───────────
    result = result.merge(rain_a2, on=["admin2_code", "ipc_start", "ipc_end"], how="left")
    if "rain_1m_sum" not in result.columns:
        result["rain_1m_sum"] = pd.NA
    rain_cols = [c for c in result.columns if c.startswith("rain_")]
    result["rain_match_level"] = pd.NA
    result.loc[result["rain_1m_sum"].notna(), "rain_match_level"] = 2
    result = fill_from_admin1(result, rain_a1,
                              ["admin1_code", "ipc_start", "ipc_end"],
                              rain_cols, "rain_1m_sum", "rain_match_level")

    # QA summary: coverage at pure admin2 vs with admin1 fallback.
    n            = len(result)
    acl_lvl      = result["acled_match_level"]
    idp_lvl      = result["idp_match_level"]
    rain_lvl     = result["rain_match_level"]
    acl_a2       = (acl_lvl == 2).sum() / n          # district-only
    acl_fb       = acl_lvl.notna().sum() / n         # district + province fill
    idp_a2       = (idp_lvl == 2).sum() / n
    idp_fb       = idp_lvl.notna().sum() / n
    rain_a2p     = (rain_lvl == 2).sum() / n
    rain_fb      = rain_lvl.notna().sum() / n
    print(f"  {iso3}: {n:>7,} rows | ACLED {acl_a2:>4.0%}->{acl_fb:>4.0%} "
          f"| IDP {idp_a2:>4.0%}->{idp_fb:>4.0%} | RAIN {rain_a2p:>4.0%}->{rain_fb:>4.0%}")

    return result


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    os.makedirs(FINAL_DIR, exist_ok=True)

    ipc_all   = load("ipc")
    acled_all = load("acled")
    idp_all   = load("idp")
    rain_all  = load("rainfall")
    print(f"Loaded raw: ipc={len(ipc_all):,} acled={len(acled_all):,} "
          f"idp={len(idp_all):,} rain={len(rain_all):,}")
    print(f"Merging {len(COUNTRIES)} countries...\n")

    frames = []
    for iso3 in COUNTRIES:
        df = merge_country(iso3, ipc_all, acled_all, idp_all, rain_all)
        if not df.empty:
            frames.append(df)

    if not frames:
        print("No data to save.")
        return

    final = pd.concat(frames, ignore_index=True)
    final.to_parquet(FINAL_FILE, index=False, engine=PARQUET_ENGINE)

    # Overall coverage: pure admin2 vs with admin1 fallback.
    n = len(final)
    acl_a2 = (final["acled_match_level"] == 2).sum() / n
    acl_fb = final["acled_match_level"].notna().sum() / n
    idp_a2 = (final["idp_match_level"] == 2).sum() / n
    idp_fb = final["idp_match_level"].notna().sum() / n
    rain_a2 = (final["rain_match_level"] == 2).sum() / n
    rain_fb = final["rain_match_level"].notna().sum() / n

    print(f"\n{'-'*60}")
    print(f"Saved {len(final):,} rows -> {FINAL_FILE}")
    print(f"Columns ({len(final.columns)}): {final.columns.tolist()}")
    print(f"\nOverall coverage (row-weighted):")
    print(f"  ACLED: pure admin2 {acl_a2:.0%}  ->  with admin1 fallback {acl_fb:.0%}")
    print(f"  IDP  : pure admin2 {idp_a2:.0%}  ->  with admin1 fallback {idp_fb:.0%}")
    print(f"  RAIN : pure admin2 {rain_a2:.0%}  ->  with admin1 fallback {rain_fb:.0%}")


if __name__ == "__main__":
    main()
