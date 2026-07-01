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
  - GDELT:    media-conflict signals (CAMEO), at both admin levels. Per-period sum of events +
              mentions and mentions-weighted mean tone, pre-aggregated into the 4 CAMEO
              QuadClasses. ADM1 joined on admin1_code, ADM2 joined on admin2_code.
  - NDVI:     dekadal vegetation index (WFP), native at both admin levels. Per-period,
              n_pixels-weighted mean of vim (greenness) and viq (% of normal); exact-duplicate
              rows dropped first. Native admin level filter, like rainfall.

Usage:
    python merge.py
"""

import os
import pandas as pd

from config import (
    COUNTRIES, FINAL_DIR, FINAL_FILE_ADM1, FINAL_FILE_ADM2,
    raw_file, PARQUET_ENGINE, MAX_IDP_STALENESS_DAYS, WFP_WITH_PCODES,
    GDELT_FILE_ADM1, GDELT_FILE_ADM2, NDVI_FILE,
)


# ── helpers ──────────────────────────────────────────────────────────────────

def load(theme_key):
    """Load the single global parquet for a theme (all countries)."""
    path = raw_file(theme_key)
    return pd.read_parquet(path, engine=PARQUET_ENGINE) if os.path.exists(path) else pd.DataFrame()


def to_dt(series):
    return pd.to_datetime(series, utc=True).dt.tz_localize(None)


# GDELT QuadClass index → output quad name. The raw files ship pre-aggregated into
# these 4 categories (columns n_events_qc{i}, total_mentions_qc{i}, avg_tone_qc{i}).
GDELT_QC_NAMES = {
    1: "verbal_coop",
    2: "material_coop",
    3: "verbal_conflict",
    4: "material_conflict",
}


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


# ── GDELT aggregation ───────────────────────────────────────────────────────────

def aggregate_gdelt(gdelt, join_key_col, pcode_col, ipc_periods):
    """
    Aggregate monthly GDELT rows to IPC reference periods.

    Input schema: iso3, {pcode_col}, year, month,
                  n_events_qc{1-4}, total_mentions_qc{1-4}, avg_tone_qc{1-4}.
    pcode_col:    "adm1_pcode" or "adm2_pcode"
    join_key_col: "admin1_code" or "admin2_code"

    Per (join_key, ipc_start, ipc_end) and per QuadClass i:
        gdelt_q_events   = sum(n_events_qci)        over months in period
        gdelt_q_mentions = sum(total_mentions_qci)  likewise
        gdelt_q_tone     = mentions-weighted mean of avg_tone_qci
                           = sum(avg_tone * mentions) / sum(mentions), NaN if no mentions
                           (absence of events != neutral tone, so tone is never imputed to 0).

    Returns DataFrame with [join_key_col, ipc_start, ipc_end, gdelt_<quad>_<metric> x 12].
    """
    out_cols = [f"gdelt_{q}_{m}" for q in GDELT_QC_NAMES.values() for m in ("events", "mentions", "tone")]
    empty_base = ipc_periods[[join_key_col, "ipc_start", "ipc_end"]].drop_duplicates().copy()

    if gdelt.empty:
        return empty_base

    gdelt = gdelt.copy()
    gdelt["gdelt_date"] = pd.to_datetime(
        dict(year=gdelt["year"], month=gdelt["month"], day=1)
    )
    gdelt[join_key_col] = gdelt[pcode_col].astype(str)

    # Pre-compute per-row tone numerator (mentions-weighted) for each QuadClass.
    qc_cols = []
    for i in GDELT_QC_NAMES:
        gdelt[f"_tonenum_qc{i}"] = gdelt[f"avg_tone_qc{i}"].fillna(0) * gdelt[f"total_mentions_qc{i}"].fillna(0)
        qc_cols += [f"n_events_qc{i}", f"total_mentions_qc{i}", f"_tonenum_qc{i}"]

    merged = ipc_periods.merge(gdelt[[join_key_col, "gdelt_date"] + qc_cols],
                               on=join_key_col, how="left")
    in_period = (merged["gdelt_date"] >= merged["ipc_start"]) & \
                (merged["gdelt_date"] <= merged["ipc_end"])
    merged = merged[in_period]

    if merged.empty:
        return empty_base

    summed = merged.groupby([join_key_col, "ipc_start", "ipc_end"], as_index=False)[qc_cols].sum()

    for i, quad in GDELT_QC_NAMES.items():
        summed[f"gdelt_{quad}_events"]   = summed[f"n_events_qc{i}"]
        summed[f"gdelt_{quad}_mentions"] = summed[f"total_mentions_qc{i}"]
        mentions = summed[f"total_mentions_qc{i}"]
        summed[f"gdelt_{quad}_tone"] = (summed[f"_tonenum_qc{i}"] / mentions).where(mentions > 0)

    return summed[[join_key_col, "ipc_start", "ipc_end"] + out_cols]


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


# ── NDVI aggregation ────────────────────────────────────────────────────────────

def aggregate_ndvi(ndvi, join_key_col, level, ipc_periods):
    """
    Aggregate dekadal NDVI rows to IPC reference periods, at one admin level.

    `level` selects the native NDVI adm_level (1 or 2). `join_key_col` is the IPC-side key
    to emit ("admin1_code" or "admin2_code"); NDVI's join key is its PCODE column.

    Per (join_key_col, ipc_start, ipc_end), an n_pixels-weighted mean over every in-period
    (sub-polygon, dekad) observation:
        ndvi_vim = sum(vim * n_pixels) / sum(n_pixels)   # greenness
        ndvi_viq = sum(viq * n_pixels) / sum(n_pixels)   # vegetation condition, % of normal

    Weighting by n_pixels collapses the (rare) PCODE collisions — pcodes that map to >1 adm_id
    sub-polygon — by polygon size. Exact-duplicate rows (an upstream concat artifact) are
    dropped first so duplicated dekads are not double-counted.
    """
    empty_base = ipc_periods[[join_key_col, "ipc_start", "ipc_end"]].drop_duplicates().copy()

    if ndvi.empty:
        return empty_base

    ndvi = ndvi[ndvi["adm_level"].astype(str) == str(level)].drop_duplicates()
    if ndvi.empty:
        return empty_base

    ndvi = ndvi.copy()
    ndvi["ndvi_date"]  = to_dt(ndvi["date"])
    ndvi[join_key_col] = ndvi["PCODE"].astype(str)

    merged = ipc_periods.merge(
        ndvi[[join_key_col, "ndvi_date", "vim", "viq", "n_pixels"]],
        on=join_key_col, how="left",
    )
    in_period = (merged["ndvi_date"] >= merged["ipc_start"]) & \
                (merged["ndvi_date"] <= merged["ipc_end"])
    merged = merged[in_period]

    if merged.empty:
        return empty_base

    w = merged["n_pixels"]
    merged["_vim_w"] = merged["vim"] * w
    merged["_viq_w"] = merged["viq"] * w
    grouped = merged.groupby([join_key_col, "ipc_start", "ipc_end"], as_index=False).agg(
        _vim_w=("_vim_w", "sum"), _viq_w=("_viq_w", "sum"), _w=("n_pixels", "sum"),
    )
    grouped["ndvi_vim"] = grouped["_vim_w"] / grouped["_w"]
    grouped["ndvi_viq"] = grouped["_viq_w"] / grouped["_w"]

    return grouped[[join_key_col, "ipc_start", "ipc_end", "ndvi_vim", "ndvi_viq"]]


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
                  gdelt_adm1_all, gdelt_adm2_all, ndvi_all,
                  join_key_col, admin_level):
    """
    Pure-level country merge. Filters IPC to rows where IPC's `admin_level` == `admin_level`
    arg, then joins ACLED / IDP / rainfall / WFP / GDELT / NDVI using `join_key_col` only
    ("admin1_code" or "admin2_code"). No fallback, no *_match_level flags.

    GDELT is joined at both admin levels using the matching GDELT file (adm1 or adm2).
    NDVI is native at both levels (like rainfall) and is joined in both passes.
    """
    ipc        = slice_country(ipc_all,       iso3)
    acled      = slice_country(acled_all,     iso3)
    idp        = slice_country(idp_all,       iso3)
    rain       = slice_country(rain_all,      iso3, col="ISO3")
    wfp        = slice_country(wfp_all,       iso3, col="ISO3")
    gdelt_adm1 = slice_country(gdelt_adm1_all, iso3, col="iso3")
    gdelt_adm2 = slice_country(gdelt_adm2_all, iso3, col="iso3")
    ndvi       = slice_country(ndvi_all,      iso3, col="country_iso3")

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
    ndvi_agg  = aggregate_ndvi(ndvi, join_key_col, admin_level, periods)

    result = ipc.merge(acled_agg, on=[join_key_col, "ipc_start", "ipc_end"], how="left")
    result = result.merge(idp_agg,  on=[join_key_col, "ipc_end"], how="left")
    result = result.merge(rain_agg, on=[join_key_col, "ipc_start", "ipc_end"], how="left")
    result = result.merge(wfp_agg,  on=[join_key_col, "ipc_start", "ipc_end"], how="left")
    result = result.merge(ndvi_agg, on=[join_key_col, "ipc_start", "ipc_end"], how="left")

    # GDELT: join at both admin levels using the matching file and pcode column.
    gdelt_src  = gdelt_adm1 if admin_level == 1 else gdelt_adm2
    pcode_col  = "adm1_pcode" if admin_level == 1 else "adm2_pcode"
    gdelt_agg  = aggregate_gdelt(gdelt_src, join_key_col, pcode_col, periods)
    result = result.merge(gdelt_agg, on=[join_key_col, "ipc_start", "ipc_end"], how="left")

    # QA: raw coverage per theme.
    n = len(result)
    acl_cov   = result["acled_total_events"].notna().sum() / n if "acled_total_events" in result.columns else 0
    idp_cov   = result["idp_population"].notna().sum() / n     if "idp_population"      in result.columns else 0
    rain_cov  = result["rain_1m_sum"].notna().sum() / n        if "rain_1m_sum"         in result.columns else 0
    wfp_cov   = result["wfp_price"].notna().sum() / n          if "wfp_price"           in result.columns else 0
    ndvi_cov  = result["ndvi_vim"].notna().sum() / n           if "ndvi_vim"            in result.columns else 0
    gdelt_cov = result["gdelt_material_conflict_events"].notna().sum() / n if "gdelt_material_conflict_events" in result.columns else 0
    print(f"  {iso3} adm{admin_level}: {n:>6,} rows | "
          f"ACLED {acl_cov:>4.0%} | IDP {idp_cov:>4.0%} | "
          f"RAIN {rain_cov:>4.0%} | WFP {wfp_cov:>4.0%} | NDVI {ndvi_cov:>4.0%} | GDELT {gdelt_cov:>4.0%}")

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

    gdelt_adm1_all = (
        pd.read_parquet(GDELT_FILE_ADM1, engine=PARQUET_ENGINE)
        if os.path.exists(GDELT_FILE_ADM1) else pd.DataFrame()
    )
    if gdelt_adm1_all.empty:
        print(f"[warn] GDELT ADM1 source not found at {GDELT_FILE_ADM1} — gdelt_* columns will be empty for adm1.")
    gdelt_adm2_all = (
        pd.read_parquet(GDELT_FILE_ADM2, engine=PARQUET_ENGINE)
        if os.path.exists(GDELT_FILE_ADM2) else pd.DataFrame()
    )
    if gdelt_adm2_all.empty:
        print(f"[warn] GDELT ADM2 source not found at {GDELT_FILE_ADM2} — gdelt_* columns will be empty for adm2.")

    ndvi_all = (
        pd.read_parquet(NDVI_FILE, engine=PARQUET_ENGINE)
        if os.path.exists(NDVI_FILE) else pd.DataFrame()
    )
    if ndvi_all.empty:
        print(f"[warn] NDVI source not found at {NDVI_FILE} — ndvi_* columns will be empty.")

    print(f"Loaded raw: ipc={len(ipc_all):,} acled={len(acled_all):,} "
          f"idp={len(idp_all):,} rain={len(rain_all):,} wfp={len(wfp_all):,} "
          f"gdelt_adm1={len(gdelt_adm1_all):,} gdelt_adm2={len(gdelt_adm2_all):,} ndvi={len(ndvi_all):,}")

    for admin_level, join_key_col, out_path in [
        (1, "admin1_code", FINAL_FILE_ADM1),
        (2, "admin2_code", FINAL_FILE_ADM2),
    ]:
        print(f"\n-- Pass admin_level={admin_level}, key={join_key_col} -> {out_path}")
        frames = []
        for iso3 in COUNTRIES:
            df = merge_country(iso3, ipc_all, acled_all, idp_all, rain_all, wfp_all,
                               gdelt_adm1_all, gdelt_adm2_all, ndvi_all,
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
        ndvi_cov = final["ndvi_vim"].notna().sum() / n           if "ndvi_vim"            in final.columns else 0
        print(f"  Saved {n:,} rows -> {out_path}")
        gdelt_cov = final["gdelt_material_conflict_events"].notna().sum() / n if "gdelt_material_conflict_events" in final.columns else 0
        print(f"  Coverage (row-weighted): ACLED {acl_cov:.0%} | IDP {idp_cov:.0%} | "
              f"RAIN {rain_cov:.0%} | WFP {wfp_cov:.0%} | NDVI {ndvi_cov:.0%} | GDELT {gdelt_cov:.0%}")


if __name__ == "__main__":
    main()
