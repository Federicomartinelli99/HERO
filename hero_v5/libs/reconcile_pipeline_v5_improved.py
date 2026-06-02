import os
import sys
import time
import re
import logging
import pandas as pd
import numpy as np
import geopandas as gpd
from pathlib import Path

# Setup logging
def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)
    return logger

logger = setup_logger("reconcile_pipeline_v5_improved")

# Config parameters matching hapi_pipeline
COUNTRIES = [
    "AFG", "AGO", "BDI", "BEN", "BFA", "BGD", "CAF", "CIV", "CMR", "COD",
    "CPV", "DJI", "DOM", "ECU", "ETH", "GHA", "GIN", "GMB", "GNB", "GTM",
    "HND", "HTI", "KEN", "LBN", "LBR", "LSO", "MDG", "MLI", "MOZ", "MRT",
    "MWI", "NAM", "NER", "NGA", "PAK", "PSE", "SDN", "SEN", "SLE", "SLV",
    "SOM", "SSD", "SWZ", "TCD", "TGO", "TLS", "TZA", "UGA", "YEM", "ZAF",
    "ZMB", "ZWE",
]
MAX_IDP_STALENESS_DAYS = 400
PARQUET_ENGINE = "pyarrow" # Use pyarrow in this env since it works fine here

def normalize_name(name) -> str:
    if pd.isna(name):
        return ""
    name_str = str(name).lower().strip()
    name_str = re.sub(r'[^a-z0-9\s]', '', name_str)
    name_str = re.sub(r'\s+', ' ', name_str)
    return name_str.strip()

def to_dt(series):
    return pd.to_datetime(series, utc=True).dt.tz_localize(None)

# --- ACLED Aggregation ---
def aggregate_acled(acled, join_key_col, ipc_periods):
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

# --- IDP Matching ---
def match_idp(idp, join_key_col, ipc_ends):
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

# --- Rainfall Aggregation ---
def aggregate_rainfall(rain, join_key_col, level, ipc_periods):
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

def slice_country(df, iso3, col="location_code"):
    if df.empty:
        return df
    return df[df[col] == iso3].copy()

def fill_from_admin1(result, agg1, key_cols, value_cols, primary_col, flag_col):
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
        return pd.DataFrame()

    ipc = ipc.copy()
    ipc["ipc_start"]   = to_dt(ipc["reference_period_start"])
    ipc["ipc_end"]     = to_dt(ipc["reference_period_end"])
    ipc["admin1_code"] = ipc["admin1_code"].astype(str)
    ipc["admin2_code"] = ipc["admin2_code"].astype(str)

    periods_a2 = ipc[["admin2_code", "ipc_start", "ipc_end"]].drop_duplicates()
    periods_a1 = ipc[["admin1_code", "ipc_start", "ipc_end"]].drop_duplicates()

    acled_a2 = aggregate_acled(acled, "admin2_code", periods_a2)
    acled_a1 = aggregate_acled(acled, "admin1_code", periods_a1)
    idp_a2   = match_idp(idp, "admin2_code", ipc[["admin2_code", "ipc_end"]].drop_duplicates())
    idp_a1   = match_idp(idp, "admin1_code", ipc[["admin1_code", "ipc_end"]].drop_duplicates())
    rain_a2  = aggregate_rainfall(rain, "admin2_code", 2, periods_a2)
    rain_a1  = aggregate_rainfall(rain, "admin1_code", 1, periods_a1)

    # ACLED merge
    result = ipc.merge(acled_a2, on=["admin2_code", "ipc_start", "ipc_end"], how="left")
    if "acled_total_events" not in result.columns:
        result["acled_total_events"] = pd.NA
    acled_cols = [c for c in result.columns if c.startswith("acled_")]
    result["acled_match_level"] = pd.NA
    result.loc[result["acled_total_events"].notna(), "acled_match_level"] = 2
    result = fill_from_admin1(result, acled_a1, ["admin1_code", "ipc_start", "ipc_end"], acled_cols, "acled_total_events", "acled_match_level")

    # IDP merge
    result = result.merge(idp_a2, on=["admin2_code", "ipc_end"], how="left")
    if "idp_population" not in result.columns:
        result["idp_population"] = pd.NA
    idp_cols = [c for c in result.columns if c.startswith("idp_")]
    result["idp_match_level"] = pd.NA
    result.loc[result["idp_population"].notna(), "idp_match_level"] = 2
    result = fill_from_admin1(result, idp_a1, ["admin1_code", "ipc_end"], idp_cols, "idp_population", "idp_match_level")

    # Rainfall merge
    result = result.merge(rain_a2, on=["admin2_code", "ipc_start", "ipc_end"], how="left")
    if "rain_1m_sum" not in result.columns:
        result["rain_1m_sum"] = pd.NA
    rain_cols = [c for c in result.columns if c.startswith("rain_")]
    result["rain_match_level"] = pd.NA
    result.loc[result["rain_1m_sum"].notna(), "rain_match_level"] = 2
    result = fill_from_admin1(result, rain_a1, ["admin1_code", "ipc_start", "ipc_end"], rain_cols, "rain_1m_sum", "rain_match_level")

    # Log metrics
    n = len(result)
    acl_lvl = result["acled_match_level"]
    idp_lvl = result["idp_match_level"]
    rain_lvl = result["rain_match_level"]
    acl_a2 = (acl_lvl == 2).sum() / n
    acl_fb = acl_lvl.notna().sum() / n
    idp_a2 = (idp_lvl == 2).sum() / n
    idp_fb = idp_lvl.notna().sum() / n
    rain_a2p = (rain_lvl == 2).sum() / n
    rain_fb = rain_lvl.notna().sum() / n
    logger.info(f"  {iso3}: {n:>6,} rows | ACLED {acl_a2:>4.0%}->{acl_fb:>4.0%} | IDP {idp_a2:>4.0%}->{idp_fb:>4.0%} | RAIN {rain_a2p:>4.0%}->{rain_fb:>4.0%}")

    return result

def main():
    t0 = time.time()
    
    workspace_dir = Path(__file__).resolve().parent.parent.parent
    data_dir = workspace_dir / "hero_v5" / "data"
    boundaries_dir = data_dir / "boundaries"
    raw_dir = data_dir / "raw"
    merged_dir = data_dir / "merged"
    merged_dir.mkdir(parents=True, exist_ok=True)
    
    # Files paths
    ipc_raw_path = raw_dir / "ipc.parquet"
    acled_raw_path = raw_dir / "acled.parquet"
    idp_raw_path = raw_dir / "idp.parquet"
    rain_raw_path = raw_dir / "rainfall.parquet"
    wfp_raw_path = data_dir / "wfp_with_pcodes.parquet"
    
    logger.info("Verifica dell'esistenza dei file raw...")
    for p in [ipc_raw_path, acled_raw_path, idp_raw_path, rain_raw_path, wfp_raw_path]:
        if not p.exists():
            logger.error(f"File non trovato: {p}")
            return
            
    logger.info("Caricamento dei file raw...")
    df_ipc_raw = pd.read_parquet(ipc_raw_path)
    df_acled_raw = pd.read_parquet(acled_raw_path)
    df_idp_raw = pd.read_parquet(idp_raw_path)
    df_rain_raw = pd.read_parquet(rain_raw_path)
    
    # ── STEP 1: PCodes Recovery on ipc.parquet before merging ────────────────
    logger.info("Costruzione mappe dei confini geografici per il ripristino dei PCodes...")
    adm2_map = {}
    adm1_map = {}
    
    spelling_overrides_adm2 = {
        ('YEM', 'dhalee'): 'ad dali',
        ('YEM', 'ad dhalee'): 'ad dali',
        ('YEM', 'azzal'): 'azaal',
        ('YEM', 'aththaorah'): 'ath thawrah',
        ('YEM', 'buraiqeh'): 'al burayqah',
        ('YEM', 'craiter'): 'sirah',
        ('YEM', 'hidaybu'): 'hadibu',
        ('YEM', 'shahan'): 'shahin',
        ('YEM', 'yafaa'): 'yafi',
        ('YEM', 'rudum'): 'radum',
        ('YEM', 'maton'): 'al mutun',
        ('YEM', 'wadea'): 'al wadeah',
        ('YEM', 'hussein'): 'al husayn',
        ('YEM', 'sanhan'): 'sahar',
        ('SOM', 'burao'): 'burco',
        ('SOM', 'baydoa'): 'baydhaba',
        ('SOM', 'oodwweyne'): 'owdweyne',
        ('SOM', 'jamame'): 'jamaame',
        ('SOM', 'dhobley'): 'afmadow',
        ('SLE', 'falaba'): 'fabala',
        ('TCD', 'dodje'): 'djode',
    }
    
    spelling_overrides_adm1 = {
        ('YEM', 'sanaa city'): 'sana a city',
        ('YEM', 'sanaa'): 'sana a',
        ('YEM', 'dhalee'): 'ad dali',
        ('YEM', 'al dhalee'): 'ad dali',
        ('YEM', 'hadramaut'): 'hadramawt',
        ('YEM', 'lhodeidah'): 'al hudaydah',
        ('SOM', 'juba dhexe'): 'middle juba',
        ('SOM', 'juba hoose'): 'lower juba',
        ('SOM', 'shabelle dhexe'): 'middle shabelle',
        ('SOM', 'shabelle hoose'): 'lower shabelle',
    }

    def find_boundary_file(iso3: str, level: int) -> Path | None:
        country_dir = boundaries_dir / iso3.lower()
        if not country_dir.exists():
            return None
        all_files = list(country_dir.rglob("*.geojson")) + list(country_dir.rglob("*.shp"))
        regex_pattern = rf"[._-]adm(in)?{level}([._-]|$)"
        matching_files = [f for f in all_files if re.search(regex_pattern, f.name.lower())]
        geojson_files = [f for f in matching_files if f.suffix.lower() == ".geojson"]
        shp_files = [f for f in matching_files if f.suffix.lower() == ".shp"]
        if geojson_files:
            return geojson_files[0]
        if shp_files:
            return shp_files[0]
        return None

    def standardize_col(gdf, level, col_type):
        target = f"adm{level}_{col_type}"
        if target in gdf.columns:
            return gdf
        for col in gdf.columns:
            col_lower = str(col).lower()
            if (f"adm{level}" in col_lower or f"admin{level}" in col_lower):
                if col_type == 'pcode' and "pco" in col_lower:
                    return gdf.rename(columns={col: target})
                if col_type == 'name' and ("name" in col_lower or "en" in col_lower):
                    return gdf.rename(columns={col: target})
        return gdf

    for iso3 in COUNTRIES:
        f_adm2 = find_boundary_file(iso3, 2)
        if f_adm2:
            try:
                gdf = gpd.read_file(f_adm2)
                gdf = standardize_col(gdf, 2, 'pcode')
                gdf = standardize_col(gdf, 2, 'name')
                if 'adm2_pcode' in gdf.columns and 'adm2_name' in gdf.columns:
                    for _, row in gdf.iterrows():
                        p, n = row['adm2_pcode'], row['adm2_name']
                        if p and n and not pd.isna(p) and not pd.isna(n):
                            norm = normalize_name(n)
                            if norm:
                                adm2_map[(iso3.upper(), norm)] = str(p).strip()
            except Exception:
                pass
                
        f_adm1 = find_boundary_file(iso3, 1)
        if f_adm1:
            try:
                gdf = gpd.read_file(f_adm1)
                gdf = standardize_col(gdf, 1, 'pcode')
                gdf = standardize_col(gdf, 1, 'name')
                if 'adm1_pcode' in gdf.columns and 'adm1_name' in gdf.columns:
                    for _, row in gdf.iterrows():
                        p, n = row['adm1_pcode'], row['adm1_name']
                        if p and n and not pd.isna(p) and not pd.isna(n):
                            norm = normalize_name(n)
                            if norm:
                                adm1_map[(iso3.upper(), norm)] = str(p).strip()
            except Exception:
                pass

    logger.info(f"Dizionari di lookup creati: Admin2={len(adm2_map)}, Admin1={len(adm1_map)}")
    
    # Standardizzazione colonne PCode nel dataframe raw
    df_ipc_raw["admin1_code"] = df_ipc_raw["admin1_code"].fillna("").astype(str).str.strip()
    df_ipc_raw["admin2_code"] = df_ipc_raw["admin2_code"].fillna("").astype(str).str.strip()
    df_ipc_raw.loc[df_ipc_raw["admin1_code"] == "nan", "admin1_code"] = ""
    df_ipc_raw.loc[df_ipc_raw["admin2_code"] == "nan", "admin2_code"] = ""
    
    rescued_adm2 = 0
    rescued_adm1 = 0
    
    for idx, row in df_ipc_raw.iterrows():
        country = row["location_code"]
        adm2_p = row["admin2_code"]
        adm1_p = row["admin1_code"]
        adm2_n = row["admin2_name"]
        adm1_n = row["admin1_name"]
        
        # Recupero Admin 2
        if adm2_p == "" and adm2_n and not pd.isna(adm2_n):
            norm = normalize_name(adm2_n)
            norm = spelling_overrides_adm2.get((country, norm), norm)
            match = adm2_map.get((country, norm))
            if match:
                df_ipc_raw.at[idx, "admin2_code"] = match
                rescued_adm2 += 1
                
        # Recupero Admin 1
        if adm1_p == "" and adm1_n and not pd.isna(adm1_n):
            norm = normalize_name(adm1_n)
            norm = spelling_overrides_adm1.get((country, norm), norm)
            match = adm1_map.get((country, norm))
            if match:
                df_ipc_raw.at[idx, "admin1_code"] = match
                rescued_adm1 += 1
                
    logger.info(f"PCodes ripristinati in ipc.parquet prima del merge: Admin2={rescued_adm2}, Admin1={rescued_adm1}")
    
    # --- STEP 2: Run merge.py logic with the enriched ipc_raw ---
    logger.info(f"Avvio del merge per {len(COUNTRIES)} paesi...")
    frames = []
    for iso3 in COUNTRIES:
        df_c = merge_country(iso3, df_ipc_raw, df_acled_raw, df_idp_raw, df_rain_raw)
        if not df_c.empty:
            frames.append(df_c)
            
    if not frames:
        logger.error("Nessun dato unito generato!")
        return
        
    df_long = pd.concat(frames, ignore_index=True)
    logger.info(f"Merge completato in formato LONG: {len(df_long):,} righe.")
    
    # ── STEP 3: Pivot LONG to WIDE matching widen.py logic ───────────────────
    logger.info("Avvio pivot dei dati uniti da LONG a WIDE...")
    
    # Gestione stringhe PCodes e NaNs per sopravvivere al pivot
    for col in ("admin1_code", "admin2_code"):
        df_long[col] = df_long[col].fillna("").astype(str)
        
    # Pivot solo sulle colonne chiave
    KEY_COLS = [
        "location_code", "admin1_code", "admin2_code", "admin_level",
        "ipc_start", "ipc_end", "ipc_type",
    ]
    
    PHASE_SUFFIX = {
        "1": "1", "2": "2", "3": "3", "3+": "3plus", "4": "4", "5": "5", "all": "all"
    }
    
    pivot = df_long.pivot_table(
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
    logger.info(f"Dimensioni dopo pivot: {len(pivot):,} righe.")
    
    # Estraiamo colonne pass-through (ACLED, IDP, Rainfall, etc.) dalla fase 'all'
    passthrough_cols = [c for c in df_long.columns
                        if c not in ("ipc_phase", "population_in_phase", "population_fraction_in_phase")
                        and c not in KEY_COLS]
                        
    passthrough = (
        df_long[df_long["ipc_phase"] == "all"][KEY_COLS + passthrough_cols]
        .drop_duplicates(subset=KEY_COLS, keep="first")
        .copy()
    )
    
    # Unione pivot + pass-through
    wide = pivot.merge(passthrough, on=KEY_COLS, how="left")
    
    # Percentualizzazione dei frazionari (0-1 -> 0-100)
    for col in [c for c in wide.columns if c.endswith("_percentage")]:
        wide[col] = wide[col] * 100
        
    # Ridenominazione colonne per formato legacy
    wide = wide.rename(columns={
        "location_code":          "Country",
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
    
    # Riordinamento colonne
    id_cols = ["Country", "location_name_full", "Level 1", "Area", "adm1_pcode", "adm2_pcode",
               "From", "To", "Validity period", "Date of analysis", "admin_level", "resource_hdx_id"]
    phase_cols = [f"phase_{s}_{t}"
                  for s in ["1", "2", "3", "3plus", "4", "5", "all"]
                  for t in ["number", "percentage"]]
    rest_cols = [c for c in wide.columns if c not in id_cols + phase_cols]
    wide = wide[[c for c in id_cols + phase_cols + rest_cols if c in wide.columns]]
    
    # Salvataggio ipc_rain_conflict_idp_v5.parquet
    out_wide_parquet = merged_dir / "ipc_rain_conflict_idp_v5.parquet"
    logger.info(f"Salvataggio dataset wide intermedio in: {out_wide_parquet}")
    wide.to_parquet(out_wide_parquet, index=False, engine=PARQUET_ENGINE)
    
    # Copia nel root per consistenza
    root_wide_parquet = workspace_dir / "ipc_rain_conflict_idp_v5.parquet"
    wide.to_parquet(root_wide_parquet, index=False, engine=PARQUET_ENGINE)
    logger.info(f"Copia salvata anche nel root del workspace: {root_wide_parquet}")
    
    # ── STEP 4: Run WFP Price Reconciliation on the new v5 file ──────────────
    logger.info("Avvio del modulo di riconciliazione WFP Prices per v5...")
    df_wfp_src = pd.read_parquet(wfp_raw_path)
    
    # Standardizzazione colonne From/To e PCodes in wide
    wide["ipc_row_id"] = range(len(wide))
    wide["date_from"] = pd.to_datetime(wide["From"])
    wide["date_to"] = pd.to_datetime(wide["To"])
    
    for col in ["adm1_pcode", "adm2_pcode"]:
        wide[col] = wide[col].fillna("").astype(str).str.strip()
        wide.loc[wide[col] == "nan", col] = ""
        
    wide["is_true_admin2"] = (
        (wide["adm2_pcode"] != "") & 
        (wide["adm1_pcode"] != "") & 
        (wide["adm2_pcode"] != wide["adm1_pcode"])
    )
    
    wide["norm_adm1"] = wide["Level 1"].apply(normalize_name)
    df_wfp_src["norm_adm1"] = df_wfp_src["adm1_name"].apply(normalize_name)
    df_wfp_src["date"] = pd.to_datetime(df_wfp_src["date"], errors="coerce")
    
    # Aggregazione WFP fallbacks
    wfp_levels = {
        "admin2": (
            df_wfp_src[df_wfp_src["adm2_pcode"].notna() & (df_wfp_src["adm2_pcode"] != "")]
            .groupby(["ISO3", "adm2_pcode", "date"], observed=True)
            .agg(price=("price", "mean"), inflation=("inflation", "mean"),
                 mapping_method=("mapping_method_adm2", lambda x: "elastic_buffer" if "elastic_buffer" in x.values else "strict_pip"))
            .reset_index()
        ),
        "admin1_code": (
            df_wfp_src[df_wfp_src["adm1_pcode"].notna() & (df_wfp_src["adm1_pcode"] != "")]
            .groupby(["ISO3", "adm1_pcode", "date"], observed=True)
            .agg(price=("price", "mean"), inflation=("inflation", "mean"),
                 mapping_method=("mapping_method_adm1", lambda x: "elastic_buffer" if "elastic_buffer" in x.values else "strict_pip"))
            .reset_index()
        ),
        "admin1_name": (
            df_wfp_src[df_wfp_src["norm_adm1"] != ""]
            .groupby(["ISO3", "norm_adm1", "date"], observed=True)
            .agg(price=("price", "mean"), inflation=("inflation", "mean"),
                 mapping_method=("mapping_method_adm1", lambda x: "elastic_buffer" if "elastic_buffer" in x.values else "strict_pip"))
            .reset_index()
        ),
        "country": (
            df_wfp_src.groupby(["ISO3", "date"], observed=True)
            .agg(price=("price", "mean"), inflation=("inflation", "mean"),
                 mapping_method=("ISO3", lambda x: "national_fallback"))
            .reset_index()
        )
    }
    
    wfp_chunks = []
    wfp_matched_ids = set()
    
    level_specs = [
        ("Admin2", "admin2", ["Country", "adm2_pcode"], ["ISO3", "adm2_pcode"], "is_true_admin2"),
        ("Admin1_Code", "admin1_code", ["Country", "adm1_pcode"], ["ISO3", "adm1_pcode"], None),
        ("Admin1_Name", "admin1_name", ["Country", "norm_adm1"], ["ISO3", "norm_adm1"], None),
        ("National", "country", ["Country"], ["ISO3"], None),
    ]
    
    for label, key, left_keys, right_keys, filter_col in level_specs:
        remaining = wide[~wide["ipc_row_id"].isin(wfp_matched_ids)]
        if remaining.empty:
            break
        if filter_col and filter_col in remaining.columns:
            remaining = remaining[remaining[filter_col]]
        if label == "Admin1_Name":
            remaining = remaining[remaining["norm_adm1"] != ""]
            
        if remaining.empty:
            continue
            
        cols_needed = list(set(["ipc_row_id", "date_from", "date_to"] + left_keys))
        m = pd.merge(remaining[cols_needed], wfp_levels[key], left_on=left_keys, right_on=right_keys)
        m = m[(m["date"] >= m["date_from"]) & (m["date"] <= m["date_to"])]
        if m.empty:
            continue
            
        agg = (
            m.groupby("ipc_row_id")
            .agg(WFP_avg_price=("price", "mean"), WFP_avg_inflation=("inflation", "mean"), wfp_obs_count=("price", "size"),
                 wfp_spatial_mapping_method=("mapping_method", lambda x: "elastic_buffer" if "elastic_buffer" in x.values else ("national_fallback" if "national_fallback" in x.values else "strict_pip")))
            .reset_index()
        )
        agg["wfp_match_level"] = label
        wfp_chunks.append(agg)
        wfp_matched_ids.update(agg["ipc_row_id"])
        
    if wfp_chunks:
        wfp_final = pd.concat(wfp_chunks, ignore_index=True)
    else:
        wfp_final = pd.DataFrame(columns=["ipc_row_id", "WFP_avg_price", "WFP_avg_inflation", "wfp_match_level", "wfp_obs_count", "wfp_spatial_mapping_method"])
        
    df_consolidated = wide.merge(wfp_final, on="ipc_row_id", how="left")
    
    # Metadata WFP defaults
    df_consolidated["wfp_match_level"] = df_consolidated["wfp_match_level"].fillna("No_Match")
    df_consolidated["wfp_spatial_mapping_method"] = df_consolidated["wfp_spatial_mapping_method"].fillna("unmapped")
    df_consolidated["wfp_obs_count"] = df_consolidated["wfp_obs_count"].fillna(0).astype(int)
    
    # Generazione flag di disponibilità dei dati
    logger.info("Generazione flag di disponibilità dei dati...")
    
    pcode_set_adm1 = set(adm1_map.values())
    pcode_set_adm2 = set(adm2_map.values())
    
    def check_geojson(row):
        if row["is_true_admin2"]:
            return row["adm2_pcode"] in pcode_set_adm2
        else:
            return row["adm1_pcode"] in pcode_set_adm1
            
    df_consolidated["has_geojson"] = df_consolidated.apply(check_geojson, axis=1)
    df_consolidated["has_rainfall"] = df_consolidated["rain_1m"].notna()
    df_consolidated["has_wfp"] = df_consolidated["WFP_avg_price"].notna()
    df_consolidated["has_idp"] = df_consolidated["idp_population"].notna()
    df_consolidated["has_acled_events"] = df_consolidated["acled_total_events"].notna()
    df_consolidated["has_acled_fatalities"] = df_consolidated["acled_total_fatalities"].notna()
    
    # Cleanup colonne temporanee
    cols_to_drop = ["ipc_row_id", "date_from", "date_to", "norm_adm1", "is_true_admin2"]
    df_consolidated = df_consolidated.drop(columns=cols_to_drop, errors="ignore")
    
    # Salva il file finale reconciled v5
    out_reconciled = data_dir / "hero_v5_reconciled_v5.parquet"
    logger.info(f"Salvataggio dataset finale reconciled v5 in: {out_reconciled}")
    df_consolidated.to_parquet(out_reconciled, index=False, engine=PARQUET_ENGINE)
    
    elapsed = time.time() - t0
    logger.info("==================================================")
    logger.info(f"[OK] PIPELINE ENRICHED COMPLETATA CON SUCCESSO in {elapsed:.2f}s!")
    logger.info(f"     Shape finale reconciled v5: {df_consolidated.shape}")
    logger.info("==================================================")

if __name__ == "__main__":
    main()
