"""
merge.py — Join IPC (anchor) with ACLED, IDP, rainfall, and WFP food prices.

Produces two outputs, one per admin level, driven by IPC's own `admin_level` column:
  - data/merged/merged_adm1.parquet  — only IPC rows reported at admin1
  - data/merged/merged_adm2.parquet  — only IPC rows reported at admin2

Within each output, every theme is joined at exactly that level. No admin2→admin1
fallback, no *_match_level provenance flags — IPC's admin_level is authoritative per row.

Aggregation rules:
  - ACLED:    sum events + fatalities by event_type over each IPC period (pivot wide).
  - IDP:      most recent snapshot with period_start <= IPC period_end (staleness-capped).
  - Rainfall: per-period sum (1m) + means (1m, 3m, anomalies); native admin level filter.
  - WFP:      per-period mean price + mean inflation + observation count, with worst-case
              mapping_method propagation ('elastic_buffer' if any contributing market used
              it, else 'strict_pip'). WFP ships pre-prepared at
              data/raw/wfp_with_pcodes.parquet (see README.md for provenance).

Usage:
    python merge.py
"""

import os
import pandas as pd

from config import (
    COUNTRIES, FINAL_DIR, FINAL_FILE_ADM1, FINAL_FILE_ADM2,
    raw_file, PARQUET_ENGINE, MAX_IDP_STALENESS_DAYS, WFP_WITH_PCODES,
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

    acled = (
        acled.groupby([join_key_col, "acled_start", "event_type"], as_index=False)
             .agg(events=("events", "sum"), fatalities=("fatalities", "sum"))
    )

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

    Returns DataFrame with [join_key_col, ipc_end, idp_population, idp_assessment_type,
                            idp_reporting_round, idp_staleness_days].
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

    result["idp_staleness_days"] = (result["ipc_end"] - result["idp_start"]).dt.days
    if MAX_IDP_STALENESS_DAYS is not None:
        result = result[result["idp_staleness_days"] <= MAX_IDP_STALENESS_DAYS]

    return result.drop(columns=["idp_start"], errors="ignore")


# ── rainfall aggregation ───────────────────────────────────────────────────────

def aggregate_rainfall(rain, join_key_col, level, ipc_periods):
    """
    Aggregate monthly rainfall rows to IPC reference periods, at one admin level.

    `level` selects the native rainfall adm_level (1 or 2). `join_key_col` is the
    IPC-side key name to emit ("admin1_code" or "admin2_code").

    Returns DataFrame with [join_key_col, ipc_start, ipc_end, rain_1m_sum,
                            rain_1m_mean, rain_3m_mean, rain_anom_1m_mean, rain_anom_3m_mean].
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


# ── WFP aggregation ───────────────────────────────────────────────────────────

def aggregate_wfp(wfp, join_key_col, level, ipc_periods):
    """
    Aggregate WFP monthly market-price rows to IPC reference periods, at one admin level.

    Input schema (from data/raw/wfp_with_pcodes.parquet):
        ISO3, adm1_pcode, adm2_pcode, mkt_name, lat, lon, year, month, date,
        price, inflation, mapping_method_adm1, mapping_method_adm2.

    `level` (1 or 2) selects which WFP pcode column is used as the join key:
        1 -> adm1_pcode + mapping_method_adm1
        2 -> adm2_pcode + mapping_method_adm2

    Per (join_key, ipc_start, ipc_end):
        wfp_price          = mean(price)
        wfp_inflation      = mean(inflation)
        wfp_obs_count      = number of (market, month) rows contributing
        wfp_mapping_method = 'elastic_buffer' if any contributing market used it,
                              else 'strict_pip'   (worst-case propagation)
    """
    empty_base = ipc_periods[[join_key_col, "ipc_start", "ipc_end"]].drop_duplicates().copy()

    if wfp.empty:
        return empty_base

    pcode_col  = f"adm{level}_pcode"
    method_col = f"mapping_method_adm{level}"

    wfp = wfp.copy()
    wfp["wfp_date"]  = to_dt(wfp["date"])
    # Drop rows the PIP step couldn't map at this level — NaN pcode or 'unmapped' method.
    wfp = wfp[wfp[pcode_col].notna() & (wfp[method_col] != "unmapped")]
    if wfp.empty:
        return empty_base

    wfp[join_key_col] = wfp[pcode_col].astype(str)

    merged = ipc_periods.merge(
        wfp[[join_key_col, "wfp_date", "price", "inflation", method_col]],
        on=join_key_col, how="left",
    )
    in_period = (merged["wfp_date"] >= merged["ipc_start"]) & \
                (merged["wfp_date"] <= merged["ipc_end"])
    merged = merged[in_period]

    if merged.empty:
        return empty_base

    def worst_method(s):
        return "elastic_buffer" if (s == "elastic_buffer").any() else "strict_pip"

    agg = (
        merged.groupby([join_key_col, "ipc_start", "ipc_end"], as_index=False)
              .agg(
                  wfp_price=("price", "mean"),
                  wfp_inflation=("inflation", "mean"),
                  wfp_obs_count=("price", "size"),
                  wfp_mapping_method=(method_col, worst_method),
              )
    )
    return agg


# ── per-country merge ─────────────────────────────────────────────────────────

def slice_country(df, iso3, col="location_code"):
    if df.empty:
        return df
    return df[df[col] == iso3].copy()


def merge_country(iso3, ipc_all, acled_all, idp_all, rain_all, wfp_all,
                  join_key_col, admin_level):
    """
    Pure-level country merge. Filters IPC to rows where IPC's `admin_level` == `admin_level`
    arg, then joins ACLED / IDP / rainfall / WFP using `join_key_col` only
    ("admin1_code" or "admin2_code"). No fallback, no *_match_level flags.
    """
    ipc   = slice_country(ipc_all,   iso3)
    acled = slice_country(acled_all, iso3)
    idp   = slice_country(idp_all,   iso3)
    rain  = slice_country(rain_all,  iso3, col="ISO3")
    wfp   = slice_country(wfp_all,   iso3, col="ISO3")

    if ipc.empty:
        return pd.DataFrame()

    # Filter IPC to the requested admin level (column comes in as int or str — coerce).
    ipc = ipc.copy()
    ipc = ipc[ipc["admin_level"].astype(str) == str(admin_level)]
    if ipc.empty:
        return pd.DataFrame()

    ipc["ipc_start"]   = to_dt(ipc["reference_period_start"])
    ipc["ipc_end"]     = to_dt(ipc["reference_period_end"])
    ipc[join_key_col]  = ipc[join_key_col].astype(str)

    periods = ipc[[join_key_col, "ipc_start", "ipc_end"]].drop_duplicates()
    ends    = ipc[[join_key_col, "ipc_end"]].drop_duplicates()

    acled_agg = aggregate_acled(acled, join_key_col, periods)
    idp_agg   = match_idp(idp, join_key_col, ends)
    rain_agg  = aggregate_rainfall(rain, join_key_col, admin_level, periods)
    wfp_agg   = aggregate_wfp(wfp, join_key_col, admin_level, periods)

    result = ipc.merge(acled_agg, on=[join_key_col, "ipc_start", "ipc_end"], how="left")
    result = result.merge(idp_agg,  on=[join_key_col, "ipc_end"], how="left")
    result = result.merge(rain_agg, on=[join_key_col, "ipc_start", "ipc_end"], how="left")
    result = result.merge(wfp_agg,  on=[join_key_col, "ipc_start", "ipc_end"], how="left")

    # QA: raw coverage per theme.
    n = len(result)
    acl_cov  = result["acled_total_events"].notna().sum() / n if "acled_total_events" in result.columns else 0
    idp_cov  = result["idp_population"].notna().sum() / n     if "idp_population"      in result.columns else 0
    rain_cov = result["rain_1m_sum"].notna().sum() / n        if "rain_1m_sum"         in result.columns else 0
    wfp_cov  = result["wfp_price"].notna().sum() / n          if "wfp_price"           in result.columns else 0
    print(f"  {iso3} adm{admin_level}: {n:>6,} rows | "
          f"ACLED {acl_cov:>4.0%} | IDP {idp_cov:>4.0%} | "
          f"RAIN {rain_cov:>4.0%} | WFP {wfp_cov:>4.0%}")

    return result


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    os.makedirs(FINAL_DIR, exist_ok=True)

    ipc_all   = load("ipc")
    acled_all = load("acled")
    idp_all   = load("idp")
    rain_all  = load("rainfall")
    wfp_all   = (
        pd.read_parquet(WFP_WITH_PCODES, engine=PARQUET_ENGINE)
        if os.path.exists(WFP_WITH_PCODES) else pd.DataFrame()
    )
    if wfp_all.empty:
        print(f"[warn] WFP source not found at {WFP_WITH_PCODES} — wfp_* columns will be empty.")
        print(f"       Expected the pre-prepared file at data/raw/wfp_with_pcodes.parquet.")

    print(f"Loaded raw: ipc={len(ipc_all):,} acled={len(acled_all):,} "
          f"idp={len(idp_all):,} rain={len(rain_all):,} wfp={len(wfp_all):,}")

    for admin_level, join_key_col, out_path in [
        (1, "admin1_code", FINAL_FILE_ADM1),
        (2, "admin2_code", FINAL_FILE_ADM2),
    ]:
        print(f"\n-- Pass admin_level={admin_level}, key={join_key_col} -> {out_path}")
        frames = []
        for iso3 in COUNTRIES:
            df = merge_country(iso3, ipc_all, acled_all, idp_all, rain_all, wfp_all,
                               join_key_col, admin_level)
            if not df.empty:
                frames.append(df)

        if not frames:
            print(f"  No data for admin_level={admin_level}. Skipping save.")
            continue

        final = pd.concat(frames, ignore_index=True)
        final.to_parquet(out_path, index=False, engine=PARQUET_ENGINE)

        n = len(final)
        acl_cov  = final["acled_total_events"].notna().sum() / n if "acled_total_events" in final.columns else 0
        idp_cov  = final["idp_population"].notna().sum() / n     if "idp_population"      in final.columns else 0
        rain_cov = final["rain_1m_sum"].notna().sum() / n        if "rain_1m_sum"         in final.columns else 0
        wfp_cov  = final["wfp_price"].notna().sum() / n          if "wfp_price"           in final.columns else 0
        print(f"  Saved {n:,} rows -> {out_path}")
        print(f"  Coverage (row-weighted): ACLED {acl_cov:.0%} | IDP {idp_cov:.0%} | "
              f"RAIN {rain_cov:.0%} | WFP {wfp_cov:.0%}")


if __name__ == "__main__":
    main()
