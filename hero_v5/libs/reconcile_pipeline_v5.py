import os
import sys
import time
import re
import logging
import pandas as pd
import numpy as np
import geopandas as gpd
from pathlib import Path

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

logger = setup_logger("reconcile_pipeline_v5")

def normalize_name(name) -> str:
    """Normalizza le stringhe per superare differenze di maiuscole/minuscole e spazi."""
    if pd.isna(name):
        return ""
    name_str = str(name).lower().strip()
    name_str = re.sub(r'[^a-z0-9\s]', '', name_str)
    name_str = re.sub(r'\s+', ' ', name_str)
    return name_str.strip()

def main():
    logger.info("==================================================")
    logger.info("AVVIO RECONCILE PIPELINE HERO v5")
    logger.info("==================================================")
    
    t0 = time.time()
    
    workspace_dir = Path(__file__).resolve().parent.parent.parent
    data_dir = workspace_dir / "hero_v5" / "data"
    boundaries_dir = data_dir / "boundaries"
    
    ipc_path = workspace_dir / "ipc_rain_conflict_idp.parquet"
    wfp_path = data_dir / "wfp_with_pcodes.parquet"
    
    # Verifica esistenza file
    if not ipc_path.exists():
        logger.error(f"Dataset primario non trovato in {ipc_path}")
        return
    if not wfp_path.exists():
        logger.error(f"Dataset WFP con PCODE non trovato in {wfp_path}. Eseguire Step 1 e 2.")
        return
        
    logger.info("Caricamento dataset in corso...")
    df_ipc = pd.read_parquet(ipc_path)
    df_wfp = pd.read_parquet(wfp_path)
    
    logger.info(f"  IPC Base Shape: {df_ipc.shape}")
    logger.info(f"  WFP Shape: {df_wfp.shape}")
    
    # 1. Standardizzazione delle date
    df_ipc = df_ipc.reset_index().rename(columns={"index": "ipc_row_id"})
    df_ipc["date_from"] = pd.to_datetime(df_ipc["From"])
    df_ipc["date_to"] = pd.to_datetime(df_ipc["To"])
    
    # Convertiamo i PCodes in stringhe pulite, gestendo i valori nulli o vuoti
    for col in ["adm1_pcode", "adm2_pcode"]:
        df_ipc[col] = df_ipc[col].fillna("").astype(str).str.strip()
        df_ipc.loc[df_ipc[col] == "nan", col] = ""
        
    # --- Ripristino dei PCodes mancanti usando i file confini ---
    logger.info("Ricostruzione PCodes mancanti usando i confini geografici...")
    adm2_map = {}
    adm1_map = {}
    
    # Set di PCodes presenti nei GeoJSON per tracciamento copertura geografica
    boundary_pcodes_adm1 = set()
    boundary_pcodes_adm2 = set()
    
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
        if len(all_files) == 1:
            return all_files[0]
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

    countries = df_ipc["Country"].dropna().unique()
    for iso3 in countries:
        # Carica confini Admin2
        f_adm2 = find_boundary_file(iso3, 2)
        if f_adm2:
            try:
                gdf = gpd.read_file(f_adm2)
                gdf = standardize_col(gdf, 2, 'pcode')
                gdf = standardize_col(gdf, 2, 'name')
                gdf = standardize_col(gdf, 1, 'pcode')
                gdf = standardize_col(gdf, 1, 'name')
                
                if 'adm2_pcode' in gdf.columns:
                    for _, row in gdf.iterrows():
                        p = row['adm2_pcode']
                        boundary_pcodes_adm2.add(str(p).strip())
                        if 'adm2_name' in gdf.columns:
                            n = row['adm2_name']
                            if p and n and not pd.isna(p) and not pd.isna(n):
                                norm = normalize_name(n)
                                if norm:
                                    adm2_map[(iso3.upper(), norm)] = str(p).strip()
            except Exception:
                pass
                
        # Carica confini Admin1
        f_adm1 = find_boundary_file(iso3, 1)
        if f_adm1:
            try:
                gdf = gpd.read_file(f_adm1)
                gdf = standardize_col(gdf, 1, 'pcode')
                gdf = standardize_col(gdf, 1, 'name')
                
                if 'adm1_pcode' in gdf.columns:
                    for _, row in gdf.iterrows():
                        p = row['adm1_pcode']
                        boundary_pcodes_adm1.add(str(p).strip())
                        if 'adm1_name' in gdf.columns:
                            n = row['adm1_name']
                            if p and n and not pd.isna(p) and not pd.isna(n):
                                norm = normalize_name(n)
                                if norm:
                                    adm1_map[(iso3.upper(), norm)] = str(p).strip()
            except Exception:
                pass

    logger.info(f"Dizionari lookup confini creati: Admin2={len(adm2_map)}, Admin1={len(adm1_map)}")
    
    # Eseguiamo il ripristino per righe con PCODE vuoti
    rescued_adm2 = 0
    rescued_adm1 = 0
    
    for idx, row in df_ipc.iterrows():
        country = row["Country"]
        adm2_p = row["adm2_pcode"]
        adm1_p = row["adm1_pcode"]
        area = row["Area"]
        level1 = row["Level 1"]
        
        # Ripristino Admin 2
        if adm2_p == "" and area and not pd.isna(area):
            norm = normalize_name(area)
            norm = spelling_overrides_adm2.get((country, norm), norm)
            match = adm2_map.get((country, norm))
            if match:
                df_ipc.at[idx, "adm2_pcode"] = match
                rescued_adm2 += 1
                
        # Ripristino Admin 1
        if adm1_p == "" and level1 and not pd.isna(level1):
            norm = normalize_name(level1)
            norm = spelling_overrides_adm1.get((country, norm), norm)
            match = adm1_map.get((country, norm))
            if match:
                df_ipc.at[idx, "adm1_pcode"] = match
                rescued_adm1 += 1
                
    logger.info(f"PCodes ripristinati dai confini: Admin2={rescued_adm2}, Admin1={rescued_adm1}")
    
    # Calcoliamo se la riga rappresenta un vero Admin2 (distretto reale)
    df_ipc["is_true_admin2"] = (
        (df_ipc["adm2_pcode"] != "") & 
        (df_ipc["adm1_pcode"] != "") & 
        (df_ipc["adm2_pcode"] != df_ipc["adm1_pcode"])
    )
    
    logger.info(f"  Righe contrassegnate come veri Admin2: {df_ipc['is_true_admin2'].sum()}/{len(df_ipc)}")
    
    # Preparazione chiavi stringa per WFP merge
    df_ipc["norm_adm1"] = df_ipc["Level 1"].apply(normalize_name)
    df_wfp["norm_adm1"] = df_wfp["adm1_name"].apply(normalize_name)
    
    df_wfp["date"] = pd.to_datetime(df_wfp["date"], errors="coerce")
    
    # 2. Aggregazione spaziale dei dati WFP
    logger.info("Pre-aggregazione WFP per livelli di fallback...")
    
    wfp_levels = {
        "admin2": (
            df_wfp[df_wfp["adm2_pcode"].notna() & (df_wfp["adm2_pcode"] != "")]
            .groupby(["ISO3", "adm2_pcode", "date"], observed=True)
            .agg(
                price=("price", "mean"),
                inflation=("inflation", "mean"),
                mapping_method=("mapping_method_adm2", lambda x: "elastic_buffer" if "elastic_buffer" in x.values else "strict_pip")
            )
            .reset_index()
        ),
        "admin1_code": (
            df_wfp[df_wfp["adm1_pcode"].notna() & (df_wfp["adm1_pcode"] != "")]
            .groupby(["ISO3", "adm1_pcode", "date"], observed=True)
            .agg(
                price=("price", "mean"),
                inflation=("inflation", "mean"),
                mapping_method=("mapping_method_adm1", lambda x: "elastic_buffer" if "elastic_buffer" in x.values else "strict_pip")
            )
            .reset_index()
        ),
        "admin1_name": (
            df_wfp[df_wfp["norm_adm1"] != ""]
            .groupby(["ISO3", "norm_adm1", "date"], observed=True)
            .agg(
                price=("price", "mean"),
                inflation=("inflation", "mean"),
                mapping_method=("mapping_method_adm1", lambda x: "elastic_buffer" if "elastic_buffer" in x.values else "strict_pip")
            )
            .reset_index()
        ),
        "country": (
            df_wfp.groupby(["ISO3", "date"], observed=True)
            .agg(
                price=("price", "mean"),
                inflation=("inflation", "mean"),
                mapping_method=("ISO3", lambda x: "national_fallback")
            )
            .reset_index()
        )
    }
    
    # Allineamento gerarchico
    logger.info("Avvio allineamento gerarchico WFP...")
    wfp_chunks = []
    wfp_matched_ids = set()
    
    level_specs = [
        ("Admin2", "admin2", ["Country", "adm2_pcode"], ["ISO3", "adm2_pcode"], "is_true_admin2"),
        ("Admin1_Code", "admin1_code", ["Country", "adm1_pcode"], ["ISO3", "adm1_pcode"], None),
        ("Admin1_Name", "admin1_name", ["Country", "norm_adm1"], ["ISO3", "norm_adm1"], None),
        ("National", "country", ["Country"], ["ISO3"], None),
    ]
    
    for label, key, left_keys, right_keys, filter_col in level_specs:
        remaining = df_ipc[~df_ipc["ipc_row_id"].isin(wfp_matched_ids)]
        if remaining.empty:
            break
            
        if filter_col and filter_col in remaining.columns:
            remaining = remaining[remaining[filter_col]]
            
        if label == "Admin1_Name":
            remaining = remaining[remaining["norm_adm1"] != ""]
            
        if remaining.empty:
            continue
            
        cols_needed = list(set(["ipc_row_id", "date_from", "date_to"] + left_keys))
        cols_needed = [c for c in cols_needed if c in remaining.columns]
        
        m = pd.merge(
            remaining[cols_needed],
            wfp_levels[key],
            left_on=left_keys,
            right_on=right_keys
        )
        
        m = m[(m["date"] >= m["date_from"]) & (m["date"] <= m["date_to"])]
        if m.empty:
            continue
            
        agg = (
            m.groupby("ipc_row_id")
            .agg(
                WFP_avg_price=("price", "mean"),
                WFP_avg_inflation=("inflation", "mean"),
                wfp_obs_count=("price", "size"),
                wfp_spatial_mapping_method=("mapping_method", lambda x: "elastic_buffer" if "elastic_buffer" in x.values else ("national_fallback" if "national_fallback" in x.values else "strict_pip"))
            )
            .reset_index()
        )
        agg["wfp_match_level"] = label
        wfp_chunks.append(agg)
        wfp_matched_ids.update(agg["ipc_row_id"])
        logger.info(f"  WFP {label} Match: {len(agg)} righe")
        
    if wfp_chunks:
        wfp_final = pd.concat(wfp_chunks, ignore_index=True)
    else:
        wfp_final = pd.DataFrame(
            columns=["ipc_row_id", "WFP_avg_price", "WFP_avg_inflation", "wfp_match_level", "wfp_obs_count", "wfp_spatial_mapping_method"]
        )
        
    # Uniamo i dati WFP al dataset primario
    logger.info("Unione dati consolidata WFP con base IPC...")
    df_consolidated = df_ipc.merge(wfp_final, on="ipc_row_id", how="left")
    
    # Riempimento dei valori nulli per i metadati WFP
    df_consolidated["wfp_match_level"] = df_consolidated["wfp_match_level"].fillna("No_Match")
    df_consolidated["wfp_spatial_mapping_method"] = df_consolidated["wfp_spatial_mapping_method"].fillna("unmapped")
    df_consolidated["wfp_obs_count"] = df_consolidated["wfp_obs_count"].fillna(0).astype(int)
    
    # 3. Tracciamento disponibilità (Availability flags)
    logger.info("Generazione flag di disponibilità dei dati...")
    
    # Flag GeoJSON: True se il PCode della riga è effettivamente presente nei confini GeoJSON caricati
    df_consolidated["has_geojson"] = False
    
    # Controlliamo corrispondenze PCode per righe Admin2 e Admin1
    pcode_set_adm1 = set(boundary_pcodes_adm1)
    pcode_set_adm2 = set(boundary_pcodes_adm2)
    
    def check_geojson(row):
        if row["is_true_admin2"]:
            return row["adm2_pcode"] in pcode_set_adm2
        else:
            return row["adm1_pcode"] in pcode_set_adm1
            
    df_consolidated["has_geojson"] = df_consolidated.apply(check_geojson, axis=1)
    
    # Altri flag di copertura basati sui valori non nulli delle colonne corrispondenti
    df_consolidated["has_rainfall"] = df_consolidated["rain_1m"].notna()
    df_consolidated["has_wfp"] = df_consolidated["WFP_avg_price"].notna()
    df_consolidated["has_idp"] = df_consolidated["idp_population"].notna()
    df_consolidated["has_acled_events"] = df_consolidated["acled_total_events"].notna()
    df_consolidated["has_acled_fatalities"] = df_consolidated["acled_total_fatalities"].notna()
    
    # Rimuoviamo colonne temporanee
    cols_to_drop = ["ipc_row_id", "date_from", "date_to", "norm_adm1", "is_true_admin2"]
    df_consolidated = df_consolidated.drop(columns=cols_to_drop, errors="ignore")
    
    # Salvataggio output
    out_parquet = data_dir / "hero_v5_reconciled.parquet"
    logger.info(f"Salvataggio dataset finale unificato in: {out_parquet}")
    df_consolidated.to_parquet(out_parquet, engine='pyarrow', index=False)
    
    elapsed = time.time() - t0
    logger.info("==================================================")
    logger.info(f"[OK] PIPELINE COMPLETATA CON SUCCESSO in {elapsed:.2f}s!")
    logger.info(f"     Shape unificata finale: {df_consolidated.shape}")
    
    # Statistiche di copertura complessiva
    logger.info("--- REPORT COPERTURA GENERALE (Righe totali con dati) ---")
    logger.info(f"    Copertura GeoJSON: {df_consolidated['has_geojson'].mean()*100:.1f}%")
    logger.info(f"    Copertura Pioggia: {df_consolidated['has_rainfall'].mean()*100:.1f}%")
    logger.info(f"    Copertura Prezzi WFP: {df_consolidated['has_wfp'].mean()*100:.1f}%")
    logger.info(f"    Copertura Sfoltati IDP: {df_consolidated['has_idp'].mean()*100:.1f}%")
    logger.info(f"    Copertura Conflitti ACLED (Eventi): {df_consolidated['has_acled_events'].mean()*100:.1f}%")
    logger.info(f"    Copertura Conflitti ACLED (Vittime): {df_consolidated['has_acled_fatalities'].mean()*100:.1f}%")
    logger.info("==================================================")

if __name__ == "__main__":
    main()
