import os
import sys
import json
import logging
import re
import pandas as pd
import numpy as np
import geopandas as gpd
from pathlib import Path
import time

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

logger = setup_logger("generate_diagnostics_v5")

def normalize_name(name) -> str:
    if pd.isna(name):
        return ""
    name_str = str(name).lower().strip()
    name_str = re.sub(r'[^a-z0-9\s]', '', name_str)
    name_str = re.sub(r'\s+', ' ', name_str)
    return name_str.strip()

def to_dt(series):
    return pd.to_datetime(series, utc=True).dt.tz_localize(None)

# Helper for IDP matching dual simulation
def compute_idp_matching_levels(df_ipc, df_idp):
    df_idp = df_idp.copy()
    df_idp["match_level"] = "Unmatched"
    df_idp["raw_idx"] = range(len(df_idp))
    df_idp["idp_start"] = to_dt(df_idp["reference_period_start"])
    
    # Standardize string PCODEs
    df_idp["admin1_code"] = df_idp["admin1_code"].fillna("").astype(str).str.strip()
    df_idp["admin2_code"] = df_idp["admin2_code"].fillna("").astype(str).str.strip()
    
    matched_a2_idxs = set()
    matched_a1_idxs = set()
    
    for iso3 in df_ipc["Country"].unique():
        idp_c = df_idp[df_idp["location_code"] == iso3]
        if idp_c.empty:
            continue
            
        ipc_c = df_ipc[df_ipc["Country"] == iso3]
        
        # Match Admin2
        ends_a2 = ipc_c[["adm2_pcode", "ipc_end"]].drop_duplicates().rename(columns={"adm2_pcode": "admin2_code"})
        ends_a2["admin2_code"] = ends_a2["admin2_code"].astype(str).str.strip()
        
        idp_c_a2 = idp_c[idp_c["admin2_code"] != ""].copy()
        
        if not ends_a2.empty and not idp_c_a2.empty:
            merged_a2 = ends_a2.merge(idp_c_a2[["admin2_code", "idp_start", "raw_idx"]], on="admin2_code", how="inner")
            merged_a2 = merged_a2[merged_a2["idp_start"] <= merged_a2["ipc_end"]]
            if not merged_a2.empty:
                result_a2 = (
                    merged_a2.sort_values("idp_start")
                          .groupby(["admin2_code", "ipc_end"], as_index=False)
                          .last()
                )
                result_a2["staleness"] = (result_a2["ipc_end"] - result_a2["idp_start"]).dt.days
                result_a2 = result_a2[result_a2["staleness"] <= 400]
                matched_a2_idxs.update(result_a2["raw_idx"].dropna().astype(int))
                
        # Match Admin1
        ends_a1 = ipc_c[["adm1_pcode", "ipc_end"]].drop_duplicates().rename(columns={"adm1_pcode": "admin1_code"})
        ends_a1["admin1_code"] = ends_a1["admin1_code"].astype(str).str.strip()
        
        idp_c_a1 = idp_c[idp_c["admin1_code"] != ""].copy()
        
        if not ends_a1.empty and not idp_c_a1.empty:
            merged_a1 = ends_a1.merge(idp_c_a1[["admin1_code", "idp_start", "raw_idx"]], on="admin1_code", how="inner")
            merged_a1 = merged_a1[merged_a1["idp_start"] <= merged_a1["ipc_end"]]
            if not merged_a1.empty:
                result_a1 = (
                    merged_a1.sort_values("idp_start")
                          .groupby(["admin1_code", "ipc_end"], as_index=False)
                          .last()
                )
                result_a1["staleness"] = (result_a1["ipc_end"] - result_a1["idp_start"]).dt.days
                result_a1 = result_a1[result_a1["staleness"] <= 400]
                matched_a1_idxs.update(result_a1["raw_idx"].dropna().astype(int))
                
    df_idp.loc[df_idp["raw_idx"].isin(matched_a1_idxs), "match_level"] = "Admin1"
    df_idp.loc[df_idp["raw_idx"].isin(matched_a2_idxs), "match_level"] = "Admin2"
    
    return df_idp

def main():
    t0 = time.time()
    logger.info("==================================================")
    logger.info("AVVIO GENERAZIONE STRUMENTO DIAGNOSTICO ENRICHED v5")
    logger.info("==================================================")
    
    workspace_dir = Path(__file__).resolve().parent.parent.parent
    data_dir = workspace_dir / "hero_v5" / "data"
    boundaries_dir = data_dir / "boundaries"
    plots_dir = workspace_dir / "hero_v5" / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = data_dir / "raw"
    
    reconciled_path = data_dir / "hero_v5_reconciled_v5.parquet"
    wfp_raw_path = raw_dir / "wfp.parquet"
    wfp_pcodes_path = data_dir / "wfp_with_pcodes.parquet"
    rain_path = raw_dir / "rainfall.parquet"
    acled_path = raw_dir / "acled.parquet"
    idp_path = raw_dir / "idp.parquet"
    ipc_base_path = raw_dir / "ipc.parquet"
    
    if not reconciled_path.exists() or not wfp_raw_path.exists() or not rain_path.exists():
        logger.error("File richiesti mancanti per la diagnostica. Esegui la pipeline prima.")
        return
        
    logger.info("Caricamento dati...")
    df_rec = pd.read_parquet(reconciled_path)
    df_wfp_raw = pd.read_parquet(wfp_raw_path)
    df_wfp_pc = pd.read_parquet(wfp_pcodes_path)
    df_rain = pd.read_parquet(rain_path)
    df_acled = pd.read_parquet(acled_path)
    df_idp = pd.read_parquet(idp_path)
    
    # ── ARMONIZZAZIONE E PREPARAZIONE baseline IPC ──
    # Useremo df_rec come spine già allineata
    df_ipc = df_rec.copy()
    df_ipc['date_from'] = pd.to_datetime(df_ipc['From'])
    df_ipc['date_to'] = pd.to_datetime(df_ipc['To'])
    df_ipc['ipc_end'] = df_ipc['date_to']
    
    for col in ["adm1_pcode", "adm2_pcode"]:
        df_ipc[col] = df_ipc[col].fillna("").astype(str).str.strip()
        df_ipc.loc[df_ipc[col] == "nan", col] = ""
        
    df_ipc["is_true_admin2"] = (
        (df_ipc["adm2_pcode"] != "") & 
        (df_ipc["adm1_pcode"] != "") & 
        (df_ipc["adm2_pcode"] != df_ipc["adm1_pcode"])
    )
    
    # Esplosione temporale in mesi per joins rapidi
    df_ipc_months = df_ipc.copy()
    df_ipc_months['month_start'] = df_ipc_months.apply(
        lambda r: pd.date_range(start=r['date_from'], end=r['date_to'], freq='MS'),
        axis=1
    )
    df_ipc_months = df_ipc_months.explode('month_start').dropna(subset=['month_start'])
    df_ipc_months['month_start'] = pd.to_datetime(df_ipc_months['month_start'])
    df_ipc_months['norm_adm1'] = df_ipc_months['Level 1'].apply(normalize_name)
    
    # Dizionari di lookup temporali e spaziali dell'IPC
    ipc_a2_keys = set(zip(df_ipc_months['Country'], df_ipc_months['adm2_pcode'], df_ipc_months['month_start']))
    ipc_a1_keys = set(zip(df_ipc_months['Country'], df_ipc_months['adm1_pcode'], df_ipc_months['month_start']))
    ipc_a1_names = set(zip(df_ipc_months['Country'], df_ipc_months['norm_adm1'], df_ipc_months['month_start']))
    ipc_nat_keys = set(zip(df_ipc_months['Country'], df_ipc_months['month_start']))
    
    # ── 1. DUALE WFP (Accoppiamento WFP -> IPC) ──
    logger.info("Valutazione accoppiamento duale WFP...")
    # Uniamo i PCodes spaziali su raw WFP
    merge_keys = ['ISO3', 'mkt_name', 'lat', 'lon', 'year', 'month']
    df_wfp_m = df_wfp_raw.merge(df_wfp_pc[merge_keys + ['adm1_pcode', 'adm2_pcode']].drop_duplicates(subset=merge_keys), on=merge_keys, how='left')
    df_wfp_m['date'] = pd.to_datetime(df_wfp_m['date'])
    df_wfp_m['norm_adm1'] = df_wfp_m['adm1_name'].apply(normalize_name)
    
    # PCodes standardizzazione
    for col in ["adm1_pcode", "adm2_pcode"]:
        df_wfp_m[col] = df_wfp_m[col].fillna("").astype(str).str.strip()
        df_wfp_m.loc[df_wfp_m[col] == "nan", col] = ""
        
    df_wfp_m['match_level'] = 'Unmatched'
    
    # Match vectorized
    # Convertiamo in liste/sets o facciamo join rapidi
    # Per farlo velocemente e risparmiare memoria:
    wfp_tup_a2 = list(zip(df_wfp_m['ISO3'], df_wfp_m['adm2_pcode'], df_wfp_m['date']))
    wfp_tup_a1 = list(zip(df_wfp_m['ISO3'], df_wfp_m['adm1_pcode'], df_wfp_m['date']))
    wfp_tup_a1_name = list(zip(df_wfp_m['ISO3'], df_wfp_m['norm_adm1'], df_wfp_m['date']))
    wfp_tup_nat = list(zip(df_wfp_m['ISO3'], df_wfp_m['date']))
    
    match_levels_wfp = []
    for i in range(len(df_wfp_m)):
        if wfp_tup_a2[i] in ipc_a2_keys:
            match_levels_wfp.append('Admin2')
        elif wfp_tup_a1[i] in ipc_a1_keys:
            match_levels_wfp.append('Admin1_Code')
        elif wfp_tup_a1_name[i] in ipc_a1_names:
            match_levels_wfp.append('Admin1_Name')
        elif wfp_tup_nat[i] in ipc_nat_keys:
            match_levels_wfp.append('National')
        else:
            match_levels_wfp.append('Unmatched')
            
    df_wfp_m['match_level'] = match_levels_wfp
    
    # ── 2. DUALE RAINFALL (Accoppiamento Rain -> IPC) ──
    logger.info("Valutazione accoppiamento duale Rainfall...")
    df_rain['date'] = pd.to_datetime(df_rain['date'])
    df_rain['month_start'] = df_rain['date'].dt.to_period('M').dt.to_timestamp()
    df_rain['PCODE'] = df_rain['PCODE'].fillna("").astype(str).str.strip()
    df_rain.loc[df_rain['PCODE'] == "nan", 'PCODE'] = ""
    
    rain_tup = list(zip(df_rain['ISO3'], df_rain['PCODE'], df_rain['month_start']))
    rain_levels = df_rain['adm_level'].values
    
    match_levels_rain = []
    for i in range(len(df_rain)):
        tup = rain_tup[i]
        lvl = rain_levels[i]
        if lvl == 2 and tup in ipc_a2_keys:
            match_levels_rain.append('Admin2')
        elif lvl == 1 and tup in ipc_a1_keys:
            match_levels_rain.append('Admin1')
        else:
            match_levels_rain.append('Unmatched')
            
    df_rain['match_level'] = match_levels_rain
    
    # ── 3. DUALE ACLED (Accoppiamento ACLED -> IPC) ──
    logger.info("Valutazione accoppiamento duale ACLED...")
    df_acled['month_start'] = pd.to_datetime(df_acled['reference_period_start']).dt.to_period('M').dt.to_timestamp()
    df_acled['admin1_code'] = df_acled['admin1_code'].fillna("").astype(str).str.strip()
    df_acled['admin2_code'] = df_acled['admin2_code'].fillna("").astype(str).str.strip()
    
    acled_tup_a2 = list(zip(df_acled['location_code'], df_acled['admin2_code'], df_acled['month_start']))
    acled_tup_a1 = list(zip(df_acled['location_code'], df_acled['admin1_code'], df_acled['month_start']))
    
    match_levels_acled = []
    for i in range(len(df_acled)):
        if acled_tup_a2[i] in ipc_a2_keys:
            match_levels_acled.append('Admin2')
        elif acled_tup_a1[i] in ipc_a1_keys:
            match_levels_acled.append('Admin1')
        else:
            match_levels_acled.append('Unmatched')
            
    df_acled['match_level'] = match_levels_acled
    
    # ── 4. DUALE IDP (Accoppiamento IDP -> IPC) ──
    logger.info("Valutazione accoppiamento duale IDP...")
    df_idp_m = compute_idp_matching_levels(df_ipc, df_idp)
    
    # ── 5. CONFINE GEOJSON DUALE ──
    logger.info("Valutazione accoppiamento duale confini GeoJSON...")
    boundary_pcodes_adm1 = set()
    boundary_pcodes_adm2 = set()
    
    def standardize_pcode_col(gdf, level):
        for col in gdf.columns:
            if f"adm{level}" in str(col).lower() and "pco" in str(col).lower():
                return gdf.rename(columns={col: f"adm{level}_pcode"})
        for col in gdf.columns:
            if "pcode" in str(col).lower() and str(level) in str(col).lower():
                return gdf.rename(columns={col: f"adm{level}_pcode"})
        return gdf

    for folder in boundaries_dir.glob("*"):
        if folder.is_dir():
            iso3 = folder.name.upper()
            for f in folder.rglob("*.geojson"):
                if "adm1" in f.name.lower() or "admin1" in f.name.lower():
                    try:
                        gdf = gpd.read_file(f)
                        gdf = standardize_pcode_col(gdf, 1)
                        if "adm1_pcode" in gdf.columns:
                            boundary_pcodes_adm1.update(gdf["adm1_pcode"].dropna().unique())
                    except Exception:
                        pass
                if "adm2" in f.name.lower() or "admin2" in f.name.lower():
                    try:
                        gdf = gpd.read_file(f)
                        gdf = standardize_pcode_col(gdf, 2)
                        if "adm2_pcode" in gdf.columns:
                            boundary_pcodes_adm2.update(gdf["adm2_pcode"].dropna().unique())
                    except Exception:
                        pass
                        
    boundary_pcodes = boundary_pcodes_adm1.union(boundary_pcodes_adm2)
    ipc_pcodes = set(df_ipc['adm1_pcode'].unique()).union(set(df_ipc['adm2_pcode'].unique()))
    
    # ── 6. GENERAZIONE REPORT DI LIVELLO (compare_levels_v5.csv) ──
    logger.info("Generazione report delle coperture di livello (compare_levels_v5.csv)...")
    
    COUNTRIES_LIST = sorted(df_rec['Country'].unique().tolist())
    rows_levels = []
    for iso3 in COUNTRIES_LIST:
        df_c_rec = df_rec[df_rec['Country'] == iso3]
        if df_c_rec.empty:
            continue
            
        n = len(df_c_rec)
        
        # Copertura per livelli (diretta)
        acled_a2_cov = (df_c_rec["acled_match_level"] == 2).sum() / n * 100
        acled_fb_cov = df_c_rec["acled_match_level"].notna().sum() / n * 100
        
        idp_a2_cov = (df_c_rec["idp_match_level"] == 2).sum() / n * 100
        idp_fb_cov = df_c_rec["idp_match_level"].notna().sum() / n * 100
        
        rain_a2_cov = (df_c_rec["rainfall_match_level"] == 2).sum() / n * 100
        rain_fb_cov = df_c_rec["rainfall_match_level"].notna().sum() / n * 100
        
        wfp_a2_cov = (df_c_rec["wfp_match_level"] == "Admin2").sum() / n * 100
        wfp_fb_cov = (df_c_rec["wfp_match_level"] != "No_Match").sum() / n * 100
        
        # Dual match (lost) rates
        acled_c = df_acled[df_acled["location_code"] == iso3]
        acled_dual = (acled_c["match_level"] != "Unmatched").mean() * 100 if not acled_c.empty else 0.0
        
        idp_c = df_idp_m[df_idp_m["location_code"] == iso3]
        idp_dual = (idp_c["match_level"] != "Unmatched").mean() * 100 if not idp_c.empty else 0.0
        
        rain_c = df_rain[df_rain["ISO3"] == iso3]
        rain_dual = (rain_c["match_level"] != "Unmatched").mean() * 100 if not rain_c.empty else 0.0
        
        wfp_c = df_wfp_m[df_wfp_m["ISO3"] == iso3]
        wfp_dual = (wfp_c["match_level"] != "Unmatched").mean() * 100 if not wfp_c.empty else 0.0
        
        rows_levels.append({
            "iso3": iso3,
            "ipc_rows": n,
            "acled_admin2": round(acled_a2_cov, 1),
            "acled_fallback": round(acled_fb_cov, 1),
            "acled_dual_match_pct": round(acled_dual, 1),
            "idp_admin2": round(idp_a2_cov, 1),
            "idp_fallback": round(idp_fb_cov, 1),
            "idp_dual_match_pct": round(idp_dual, 1),
            "rain_admin2": round(rain_a2_cov, 1),
            "rain_fallback": round(rain_fb_cov, 1),
            "rain_dual_match_pct": round(rain_dual, 1),
            "wfp_admin2": round(wfp_a2_cov, 1),
            "wfp_fallback": round(wfp_fb_cov, 1),
            "wfp_dual_match_pct": round(wfp_dual, 1)
        })
        
    df_levels_final = pd.DataFrame(rows_levels)
    out_levels_csv = data_dir / "compare_levels_v5.csv"
    df_levels_final.to_csv(out_levels_csv, index=False)
    logger.info(f"Report comparativo salvato in: {out_levels_csv}")
    
    # ── 7. DIAGNOSTICA SPAZIO-TEMPORALE DETTAGLIATA ──
    logger.info("Raccolta statistiche di copertura e accoppiamento per paese e trimestre...")
    indicators = ['has_geojson', 'has_rainfall', 'has_wfp', 'has_idp', 'has_acled_events', 'has_acled_fatalities']
    df_rec['avail_score'] = df_rec[indicators].sum(axis=1) / len(indicators) * 100
    df_rec['year_quarter'] = pd.to_datetime(df_rec['From']).dt.to_period('Q').astype(str)
    
    country_order = sorted(df_rec['Country'].unique().tolist())
    date_order = sorted(df_rec['year_quarter'].unique().tolist())
    
    heatmap_datasets = {}
    metrics_to_map = {
        'overall': 'avail_score',
        'geojson': 'has_geojson',
        'rainfall': 'has_rainfall',
        'wfp': 'has_wfp',
        'idp': 'has_idp',
        'acled_events': 'has_acled_events',
        'acled_fatalities': 'has_acled_fatalities'
    }
    
    for key, col in metrics_to_map.items():
        pivot_df = df_rec.pivot_table(index='Country', columns='year_quarter', values=col, aggfunc='mean')
        if col != 'avail_score':
            pivot_df = pivot_df * 100
        pivot_df = pivot_df.reindex(index=country_order, columns=date_order)
        z_data = pivot_df.where(pd.notna(pivot_df), None).values.tolist()
        heatmap_datasets[key] = {
            'y': country_order,
            'x': date_order,
            'z': z_data
        }
        
    diagnostics_data = {
        "global": {
            "ipc_rows": len(df_rec),
            "geojson_pct": float(df_rec['has_geojson'].mean() * 100),
            "rainfall_pct": float(df_rec['has_rainfall'].mean() * 100),
            "wfp_pct": float(df_rec['has_wfp'].mean() * 100) if 'has_wfp' in df_rec.columns else 0.0,
            "idp_pct": float(df_rec['has_idp'].mean() * 100),
            "acled_events_pct": float(df_rec['has_acled_events'].mean() * 100),
            "acled_fatalities_pct": float(df_rec['has_acled_fatalities'].mean() * 100),
            
            # WFP Match Breakdown
            "wfp_breakdown": {
                "Admin2": float((df_wfp_m['match_level'] == 'Admin2').mean() * 100),
                "Admin1_Code": float((df_wfp_m['match_level'] == 'Admin1_Code').mean() * 100),
                "Admin1_Name": float((df_wfp_m['match_level'] == 'Admin1_Name').mean() * 100),
                "National": float((df_wfp_m['match_level'] == 'National').mean() * 100),
                "Unmatched": float((df_wfp_m['match_level'] == 'Unmatched').mean() * 100)
            },
            # Rainfall Match Breakdown
            "rain_breakdown": {
                "Admin2": float((df_rain['match_level'] == 'Admin2').mean() * 100),
                "Admin1": float((df_rain['match_level'] == 'Admin1').mean() * 100),
                "Unmatched": float((df_rain['match_level'] == 'Unmatched').mean() * 100)
            },
            # ACLED Breakdown
            "acled_breakdown": {
                "Admin2": float((df_acled['match_level'] == 'Admin2').mean() * 100),
                "Admin1": float((df_acled['match_level'] == 'Admin1').mean() * 100),
                "Unmatched": float((df_acled['match_level'] == 'Unmatched').mean() * 100)
            },
            # IDP Breakdown
            "idp_breakdown": {
                "Admin2": float((df_idp_m['match_level'] == 'Admin2').mean() * 100),
                "Admin1": float((df_idp_m['match_level'] == 'Admin1').mean() * 100),
                "Unmatched": float((df_idp_m['match_level'] == 'Unmatched').mean() * 100)
            },
            # Boundary PCodes Breakdown
            "boundary_breakdown": {
                "Matched": float(len(boundary_pcodes.intersection(ipc_pcodes)) / max(1, len(boundary_pcodes)) * 100),
                "Unmatched": float(len(boundary_pcodes.difference(ipc_pcodes)) / max(1, len(boundary_pcodes)) * 100)
            }
        },
        "countries": {},
        "heatmaps": heatmap_datasets
    }
    
    # ── SPAZIALE: HOTSPOTS DI MISMATCH PER PAESE ──
    for country in sorted(country_order):
        df_c_rec = df_rec[df_rec['Country'] == country]
        df_c_wfp = df_wfp_m[df_wfp_m['ISO3'] == country]
        df_c_rain = df_rain[df_rain['ISO3'] == country]
        df_c_acled = df_acled[df_acled['location_code'] == country]
        df_c_idp = df_idp_m[df_idp_m['location_code'] == country]
        
        # Filtro PCodes del paese
        c_boundary_pcodes = {p for p in boundary_pcodes if str(p).startswith(country)}
        c_ipc_pcodes = set(df_c_rec['adm1_pcode'].unique()).union(set(df_c_rec['adm2_pcode'].unique()))
        
        # Hotspot spaziali: calcoliamo i peggiori distretti (adm2)
        mismatch_by_adm2 = []
        if 'adm2_pcode' in df_c_rec.columns:
            a2_counts = df_c_rec.groupby('adm2_pcode')['avail_score'].mean()
            # Prendiamo anche i nomi dei distretti
            a2_names = df_c_rec.groupby('adm2_pcode')['Area'].first()
            for pcode, score in a2_counts.items():
                if pcode != "":
                    mismatch_by_adm2.append({
                        "pcode": pcode,
                        "name": a2_names.get(pcode, "Sconosciuto"),
                        "score": round(score, 1),
                        "mismatch": round(100 - score, 1)
                    })
        mismatch_by_adm2 = sorted(mismatch_by_adm2, key=lambda x: x["score"])[:15] # Top 15 peggiori
        
        diagnostics_data["countries"][country] = {
            "ipc_rows": len(df_c_rec),
            "geojson_pct": float(df_c_rec['has_geojson'].mean() * 100) if len(df_c_rec) > 0 else 0,
            "rainfall_pct": float(df_c_rec['has_rainfall'].mean() * 100) if len(df_c_rec) > 0 else 0,
            "wfp_pct": float(df_c_rec['has_wfp'].mean() * 100) if len(df_c_rec) > 0 and 'has_wfp' in df_c_rec.columns else 0,
            "idp_pct": float(df_c_rec['has_idp'].mean() * 100) if len(df_c_rec) > 0 else 0,
            "acled_events_pct": float(df_c_rec['has_acled_events'].mean() * 100) if len(df_c_rec) > 0 else 0,
            "acled_fatalities_pct": float(df_c_rec['has_acled_fatalities'].mean() * 100) if len(df_c_rec) > 0 else 0,
            
            "wfp_breakdown": {
                "Admin2": float((df_c_wfp['match_level'] == 'Admin2').mean() * 100) if len(df_c_wfp) > 0 else 0,
                "Admin1_Code": float((df_c_wfp['match_level'] == 'Admin1_Code').mean() * 100) if len(df_c_wfp) > 0 else 0,
                "Admin1_Name": float((df_c_wfp['match_level'] == 'Admin1_Name').mean() * 100) if len(df_c_wfp) > 0 else 0,
                "National": float((df_c_wfp['match_level'] == 'National').mean() * 100) if len(df_c_wfp) > 0 else 0,
                "Unmatched": float((df_c_wfp['match_level'] == 'Unmatched').mean() * 100) if len(df_c_wfp) > 0 else 0
            },
            "rain_breakdown": {
                "Admin2": float((df_c_rain['match_level'] == 'Admin2').mean() * 100) if len(df_c_rain) > 0 else 0,
                "Admin1": float((df_c_rain['match_level'] == 'Admin1').mean() * 100) if len(df_c_rain) > 0 else 0,
                "Unmatched": float((df_c_rain['match_level'] == 'Unmatched').mean() * 100) if len(df_c_rain) > 0 else 0
            },
            "acled_breakdown": {
                "Admin2": float((df_c_acled['match_level'] == 'Admin2').mean() * 100) if len(df_c_acled) > 0 else 0,
                "Admin1": float((df_c_acled['match_level'] == 'Admin1').mean() * 100) if len(df_c_acled) > 0 else 0,
                "Unmatched": float((df_c_acled['match_level'] == 'Unmatched').mean() * 100) if len(df_c_acled) > 0 else 0
            },
            "idp_breakdown": {
                "Admin2": float((df_c_idp['match_level'] == 'Admin2').mean() * 100) if len(df_c_idp) > 0 else 0,
                "Admin1": float((df_c_idp['match_level'] == 'Admin1').mean() * 100) if len(df_c_idp) > 0 else 0,
                "Unmatched": float((df_c_idp['match_level'] == 'Unmatched').mean() * 100) if len(df_c_idp) > 0 else 0
            },
            "boundary_breakdown": {
                "Matched": float(len(c_boundary_pcodes.intersection(c_ipc_pcodes)) / max(1, len(c_boundary_pcodes)) * 100) if len(c_boundary_pcodes) > 0 else 0,
                "Unmatched": float(len(c_boundary_pcodes.difference(c_ipc_pcodes)) / max(1, len(c_boundary_pcodes)) * 100) if len(c_boundary_pcodes) > 0 else 0
            },
            "hotspots": mismatch_by_adm2
        }
        
    # ── 8. DASHBOARD INTERATTIVA HTML GENERAZIONE ──
    logger.info("Scrittura file HTML per la Dashboard interattiva v5...")
    
    html_template = """<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HERO v5 — Esploratore Diagnostica Enriched</title>
    <!-- Tailwind CSS -->
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- Plotly.js -->
    <script src="https://cdn.plot.ly/plotly-2.24.1.min.js"></script>
    <!-- Google Fonts -->
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body {
            font-family: 'Inter', sans-serif;
            background-color: #0b0f19;
            color: #f1f5f9;
        }
        .glass-card {
            background: rgba(17, 24, 39, 0.7);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.05);
        }
        .custom-scroll::-webkit-scrollbar {
            width: 6px;
            height: 6px;
        }
        .custom-scroll::-webkit-scrollbar-track {
            background: #0f172a;
        }
        .custom-scroll::-webkit-scrollbar-thumb {
            background: #334155;
            border-radius: 4px;
        }
    </style>
</head>
<body class="min-h-screen p-4 md:p-6 flex flex-col custom-scroll">

    <!-- Header -->
    <header class="glass-card rounded-3xl p-6 mb-6 shadow-2xl relative overflow-hidden flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div class="absolute -right-16 -top-16 w-64 h-64 bg-indigo-600/20 rounded-full blur-3xl"></div>
        <div>
            <span class="text-[10px] font-bold tracking-wider text-indigo-400 uppercase bg-indigo-500/10 px-3 py-1.5 rounded-full border border-indigo-500/20">DIAGNOSTICA MULTI-SORGENTE ENRICHED v5</span>
            <h1 class="text-3xl font-extrabold tracking-tight text-white mt-2">HERO v5 — Esploratore Armonizzazione Duale</h1>
            <p class="text-slate-400 text-xs mt-1">Coperture dirette dell'IPC e tassi di accoppiamento inverso (dual mismatch/dati persi) per WFP, Rainfall, ACLED, IDP e Confini.</p>
        </div>
        
        <div class="flex items-center gap-3 bg-slate-900/90 border border-slate-800 px-4 py-2.5 rounded-2xl z-10 w-full md:w-auto">
            <span class="text-slate-400 text-xs font-bold uppercase tracking-wider">Paese:</span>
            <select id="country-selector" onchange="onCountryChange()" class="bg-slate-950 border border-slate-700 rounded-xl px-4 py-1.5 text-xs text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 flex-grow md:w-48">
                <option value="global">Tutti i Paesi (Globale)</option>
            </select>
        </div>
    </header>

    <!-- Global Key Indicators -->
    <div class="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
        <div class="glass-card rounded-2xl p-4 shadow-lg border-l-4 border-indigo-500">
            <div class="text-slate-400 text-[10px] font-bold uppercase tracking-wider">Record IPC</div>
            <div class="text-2xl font-black text-white mt-1" id="stat-ipc-rows">0</div>
            <p class="text-slate-500 text-[9px] mt-1">Righe analizzate nel dataset wide</p>
        </div>
        <div class="glass-card rounded-2xl p-4 shadow-lg border-l-4 border-emerald-500">
            <div class="text-slate-400 text-[10px] font-bold uppercase tracking-wider">Copertura Globale</div>
            <div class="text-2xl font-black text-emerald-400 mt-1" id="stat-ipc-cov">0%</div>
            <p class="text-slate-500 text-[9px] mt-1">Media complessiva dei 6 indicatori</p>
        </div>
        <div class="glass-card rounded-2xl p-4 shadow-lg border-l-4 border-amber-500">
            <div class="text-slate-400 text-[10px] font-bold uppercase tracking-wider">Dati Persi WFP (Lost)</div>
            <div class="text-2xl font-black text-amber-400 mt-1" id="stat-wfp-lost">0%</div>
            <p class="text-slate-500 text-[9px] mt-1">Prezzi WFP esclusi dal merge</p>
        </div>
        <div class="glass-card rounded-2xl p-4 shadow-lg border-l-4 border-red-500">
            <div class="text-slate-400 text-[10px] font-bold uppercase tracking-wider">Dati Persi ACLED (Lost)</div>
            <div class="text-2xl font-black text-red-400 mt-1" id="stat-acled-lost">0%</div>
            <p class="text-slate-500 text-[9px] mt-1">Eventi ACLED esclusi dal merge</p>
        </div>
        <div class="glass-card rounded-2xl p-4 shadow-lg border-l-4 border-sky-500">
            <div class="text-slate-400 text-[10px] font-bold uppercase tracking-wider">Dati Persi IDP (Lost)</div>
            <div class="text-2xl font-black text-sky-400 mt-1" id="stat-idp-lost">0%</div>
            <p class="text-slate-500 text-[9px] mt-1">Rilevazioni IDP escluse dal merge</p>
        </div>
    </div>

    <!-- Main Grid -->
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch flex-grow">
        
        <!-- Left: Match Analysis & Hotspots (5 Columns) -->
        <div class="lg:col-span-5 flex flex-col gap-6">
            <!-- Row Coverage Bar Chart -->
            <div class="glass-card rounded-3xl p-5 shadow-xl flex flex-col flex-grow min-h-[300px]">
                <h3 class="text-xs font-bold text-slate-300 tracking-widest uppercase mb-4">Copertura Righe IPC (%)</h3>
                <div id="ipc-coverage-chart" class="w-full flex-grow"></div>
            </div>
            
            <!-- Dual Mismatch Side-by-Side Breakdown -->
            <div class="glass-card rounded-3xl p-5 shadow-xl flex flex-col flex-grow min-h-[300px]">
                <h3 class="text-xs font-bold text-slate-300 tracking-widest uppercase mb-4">Livelli di Accoppiamento Duale (%)</h3>
                <div id="dual-matching-chart" class="w-full flex-grow"></div>
            </div>
            
            <!-- Spatial Hotspots Table -->
            <div class="glass-card rounded-3xl p-5 shadow-xl flex flex-col flex-grow min-h-[250px]">
                <h3 class="text-xs font-bold text-slate-300 tracking-widest uppercase mb-3 text-red-400">Peggiori 10 Hotspot di Mismatch Spaziale (Admin2)</h3>
                <div class="overflow-x-auto w-full custom-scroll flex-grow">
                    <table class="w-full text-left text-xs border-collapse">
                        <thead>
                            <tr class="border-b border-slate-800 text-slate-400">
                                <th class="pb-2 font-semibold">PCode Admin2</th>
                                <th class="pb-2 font-semibold">Nome Area</th>
                                <th class="pb-2 font-semibold text-right">Completeness</th>
                                <th class="pb-2 font-semibold text-right">Dati Mancanti</th>
                            </tr>
                        </thead>
                        <tbody id="hotspot-table-body" class="divide-y divide-slate-800/50">
                            <!-- Injected dynamically -->
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- Right: Matrix (7 Columns) -->
        <div class="lg:col-span-7 flex flex-col glass-card rounded-3xl p-6 shadow-xl">
            <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 mb-6">
                <div>
                    <h2 class="text-lg font-bold text-white">Matrice di Completezza Spazio-Temporale</h2>
                    <p class="text-slate-400 text-xs">Seleziona la metrica per visualizzare i dettagli spazio-temporali.</p>
                </div>
                <div class="w-full sm:w-auto">
                    <select id="heatmap-var-selector" onchange="renderHeatmap()" class="bg-slate-950 border border-slate-700 rounded-xl px-4 py-2 text-xs text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 w-full sm:w-64">
                        <option value="overall">Punteggio Medio Completezza (%)</option>
                        <option value="geojson">Disponibilità Confini GeoJSON (%)</option>
                        <option value="rainfall">Precipitazioni (CHIRPS) (%)</option>
                        <option value="wfp">Prezzi Alimentari (WFP) (%)</option>
                        <option value="idp">Sfoltati (IDP) (%)</option>
                        <option value="acled_events">Conflitti ACLED (Eventi) (%)</option>
                        <option value="acled_fatalities">Conflitti ACLED (Vittime) (%)</option>
                    </select>
                </div>
            </div>
            
            <div id="diagnostics-heatmap" class="w-full flex-grow min-h-[550px] bg-slate-950/20 rounded-2xl overflow-hidden"></div>
        </div>
    </div>

    <!-- Footer -->
    <footer class="mt-8 text-center text-xs text-slate-600">
        HERO Pipeline v5 Diagnostics Tool | Generato con Raccordo Duale Completo
    </footer>

    <!-- Data Injection -->
    <script>
        const DIAG_DATA = __DIAG_DATA__;
    </script>

    <!-- Client Logic -->
    <script>
        window.addEventListener("load", () => {
            populateCountrySelector();
            updateDashboard();
        });

        function populateCountrySelector() {
            const selector = document.getElementById("country-selector");
            const countries = Object.keys(DIAG_DATA.countries).sort();
            countries.forEach(c => {
                const opt = document.createElement("option");
                opt.value = c;
                opt.innerText = c;
                selector.appendChild(opt);
            });
        }

        function onCountryChange() {
            updateDashboard();
        }

        function updateDashboard() {
            const country = document.getElementById("country-selector").value;
            const data = (country === "global") ? DIAG_DATA.global : DIAG_DATA.countries[country];

            // 1. Stats Cards
            document.getElementById("stat-ipc-rows").innerText = data.ipc_rows.toLocaleString();
            
            const overall_pct = (data.geojson_pct + data.rainfall_pct + data.wfp_pct + data.idp_pct + data.acled_events_pct + data.acled_fatalities_pct) / 6;
            document.getElementById("stat-ipc-cov").innerText = overall_pct.toFixed(1) + "%";
            document.getElementById("stat-wfp-lost").innerText = data.wfp_breakdown.Unmatched.toFixed(1) + "%";
            document.getElementById("stat-acled-lost").innerText = data.acled_breakdown.Unmatched.toFixed(1) + "%";
            document.getElementById("stat-idp-lost").innerText = data.idp_breakdown.Unmatched.toFixed(1) + "%";

            // 2. Bar Chart: IPC Row Coverage
            renderIpcCoverageChart(data);

            // 3. Match Levels Side-by-Side
            renderDualMatchingChart(data);

            // 4. Hotspots Table
            renderHotspotsTable(country, data);

            // 5. Heatmap
            renderHeatmap();
        }

        function renderIpcCoverageChart(data) {
            const labels = ['GeoJSON', 'Precipitazioni', 'Prezzi WFP', 'Popolazione IDP', 'Conflitti Eventi', 'Conflitti Vittime'];
            const values = [data.geojson_pct, data.rainfall_pct, data.wfp_pct, data.idp_pct, data.acled_events_pct, data.acled_fatalities_pct];
            const colors = ['#6366f1', '#0ea5e9', '#10b981', '#f59e0b', '#ef4444', '#b91c1c'];

            const trace = {
                x: values,
                y: labels,
                type: 'bar',
                orientation: 'h',
                marker: {
                    color: colors,
                    line: {color: 'rgba(255,255,255,0.05)', width: 0.5}
                },
                text: values.map(v => v.toFixed(1) + "%"),
                textposition: 'inside',
                insidetextanchor: 'end',
                textfont: {color: '#ffffff', size: 9, weight: 'bold'}
            };

            const layout = {
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                margin: {t: 10, b: 30, l: 110, r: 20},
                font: {color: '#94a3b8', size: 9},
                xaxis: {
                    gridcolor: '#1e293b',
                    linecolor: '#334155',
                    range: [0, 105],
                    ticksuffix: '%'
                },
                yaxis: {
                    gridcolor: '#1e293b',
                    linecolor: '#334155',
                    autorange: 'reversed'
                }
            };

            Plotly.newPlot('ipc-coverage-chart', [trace], layout, {responsive: true, displayModeBar: false});
        }

        function renderDualMatchingChart(data) {
            // Confrontiamo le 4 sorgenti: WFP, Rainfall, ACLED, IDP
            const categories = ['Prezzi WFP', 'Pioggia CHIRPS', 'Conflitti ACLED', 'Sfoltati IDP'];
            
            const matchedA2 = [
                data.wfp_breakdown.Admin2,
                data.rain_breakdown.Admin2,
                data.acled_breakdown.Admin2,
                data.idp_breakdown.Admin2
            ];
            
            const matchedA1 = [
                data.wfp_breakdown.Admin1_Code + data.wfp_breakdown.Admin1_Name,
                data.rain_breakdown.Admin1,
                data.acled_breakdown.Admin1,
                data.idp_breakdown.Admin1
            ];
            
            const matchedNat = [
                data.wfp_breakdown.National,
                0,
                0,
                0
            ];
            
            const unmatched = [
                data.wfp_breakdown.Unmatched,
                data.rain_breakdown.Unmatched,
                data.acled_breakdown.Unmatched,
                data.idp_breakdown.Unmatched
            ];

            const traceA2 = {
                x: categories,
                y: matchedA2,
                name: 'Match Admin2 (District)',
                type: 'bar',
                marker: {color: '#10b981'}
            };

            const traceA1 = {
                x: categories,
                y: matchedA1,
                name: 'Match Admin1 (Province)',
                type: 'bar',
                marker: {color: '#6366f1'}
            };

            const traceNat = {
                x: categories,
                y: matchedNat,
                name: 'Match National (Fallback)',
                type: 'bar',
                marker: {color: '#eab308'}
            };

            const traceUnmatched = {
                x: categories,
                y: unmatched,
                name: 'Scollegato (Lost)',
                type: 'bar',
                marker: {color: '#ef4444'}
            };

            const layout = {
                barmode: 'stack',
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                margin: {t: 10, b: 35, l: 35, r: 10},
                font: {color: '#94a3b8', size: 9},
                xaxis: {
                    linecolor: '#334155',
                    gridcolor: 'rgba(0,0,0,0)'
                },
                yaxis: {
                    linecolor: '#334155',
                    gridcolor: '#1e293b',
                    range: [0, 105],
                    ticksuffix: '%'
                },
                legend: {
                    orientation: 'h',
                    y: -0.15,
                    font: {size: 8}
                }
            };

            Plotly.newPlot('dual-matching-chart', [traceA2, traceA1, traceNat, traceUnmatched], layout, {responsive: true, displayModeBar: false});
        }

        function renderHotspotsTable(country, data) {
            const tbody = document.getElementById("hotspot-table-body");
            tbody.innerHTML = "";
            
            if (country === "global" || !data.hotspots || data.hotspots.length === 0) {
                const tr = document.createElement("tr");
                tr.innerHTML = `<td colspan="4" class="py-4 text-center text-slate-500">Seleziona un singolo paese per visualizzare gli hotspot spaziali.</td>`;
                tbody.appendChild(tr);
                return;
            }
            
            data.hotspots.forEach(h => {
                const tr = document.createElement("tr");
                tr.className = "hover:bg-slate-800/30 transition-colors";
                tr.innerHTML = `
                    <td class="py-2.5 font-mono text-slate-300 font-bold">${h.pcode}</td>
                    <td class="py-2.5 text-slate-400 font-medium">${h.name}</td>
                    <td class="py-2.5 text-right font-semibold text-emerald-400">${h.score.toFixed(1)}%</td>
                    <td class="py-2.5 text-right font-semibold text-red-400">${h.mismatch.toFixed(1)}%</td>
                `;
                tbody.appendChild(tr);
            });
        }

        function renderHeatmap() {
            const metric = document.getElementById("heatmap-var-selector").value;
            const hData = DIAG_DATA.heatmaps[metric];
            
            const cleanX = hData.x.map(d => {
                const parts = d.split('-');
                return parts.length >= 2 ? `${parts[0]}-${parts[1]}` : d;
            });

            const data = [{
                z: hData.z,
                x: cleanX,
                y: hData.y,
                type: 'heatmap',
                colorscale: 'Viridis',
                colorbar: {
                    thickness: 10,
                    len: 0.8,
                    tickfont: {color: '#94a3b8', size: 8},
                    title: {text: '%', font: {color: '#94a3b8', size: 8}}
                },
                hoverongaps: false
            }];

            const layout = {
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                margin: {t: 20, b: 50, l: 60, r: 10},
                font: {color: '#94a3b8', size: 9},
                xaxis: {
                    gridcolor: '#111827',
                    linecolor: '#334155',
                    type: 'category',
                    tickangle: -45,
                    tickfont: {size: 8}
                },
                yaxis: {
                    gridcolor: '#111827',
                    linecolor: '#334155',
                    autorange: 'reversed',
                    tickfont: {size: 8}
                }
            };

            Plotly.newPlot('diagnostics-heatmap', data, layout, {responsive: true, displayModeBar: true});
        }
    </script>
</body>
</html>
"""
    
    json_data = json.dumps(diagnostics_data, ensure_ascii=False)
    html_content = html_template.replace("__DIAG_DATA__", json_data)
    
    out_html = plots_dir / "diagnostics_dashboard_v5.html"
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    logger.info(f"Dashboard di Diagnostica v5 salvata con successo in: {out_html}")
    
    elapsed_total = time.time() - t0
    logger.info("==================================================")
    logger.info(f"[OK] DIAGNOSTICA GENERATA CON SUCCESSO IN {elapsed_total:.2f}s!")
    logger.info("==================================================")

if __name__ == "__main__":
    main()
