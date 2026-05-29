import sys
import time
import re
import pandas as pd
import numpy as np
import geopandas as gpd
from pathlib import Path
from typing import Dict, Set, List


# Aggiunge il path per importare utils
sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils import setup_logger, normalize_name

logger = setup_logger("03_reconcile_pipeline", "03_reconcile_pipeline.log")

def main():
    logger.info("==================================================")
    logger.info("AVVIO STEP 3: RECONCILE PIPELINE & FALLBACK MERGE")
    logger.info("==================================================")
    
    t0 = time.time()
    
    workspace_dir = Path(__file__).resolve().parent.parent.parent.parent
    interim_dir = workspace_dir / "hero_v4" / "data" / "interim"
    reconciled_dir = workspace_dir / "hero_v4" / "data" / "reconciled"
    
    ipc_path = workspace_dir / "ipc" / "ipc_global_area_wide_pcoded.csv"
    wfp_path = interim_dir / "wfp_with_pcodes.parquet"
    rain_path = workspace_dir / "rainfall" / "data" / "clean_rainfall" / "rainfall_monthly.parquet"
    
    # Verifiche di esistenza dei file
    for p, label in [(ipc_path, "IPC"), (wfp_path, "WFP"), (rain_path, "Rainfall")]:
        if not p.exists():
            logger.error(f"File {label} non trovato in: {p}")
            return
            
    # 1. Caricamento dati
    logger.info("Caricamento dataset in corso...")
    df_ipc = pd.read_csv(ipc_path)
    df_wfp = pd.read_parquet(wfp_path)
    df_rain = pd.read_parquet(rain_path)
    
    logger.info(f"  IPC Shape: {df_ipc.shape}")
    logger.info(f"  WFP Shape: {df_wfp.shape}")
    logger.info(f"  Rain Shape: {df_rain.shape}")
    
    # 2. Preparazione chiavi e date IPC
    df_ipc = df_ipc.reset_index().rename(columns={"index": "ipc_row_id"})
    df_ipc["date_from"] = pd.to_datetime(df_ipc["From"], format="%d/%m/%Y", errors="coerce")
    df_ipc["date_to"] = pd.to_datetime(df_ipc["To"], format="%d/%m/%Y", errors="coerce")
    
    # --- PCODE Reconstruction from boundaries ---
    logger.info("Avvio ricostruzione PCODE da file confini (shapefile/geojson)...")
    
    # Dizionari di lookup: (Country_ISO3, normalized_name) -> PCODE
    adm2_map = {}
    adm1_map = {}
    
    # Overrides manuali per risolvere differenze di spelling note
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
    
    def find_boundary_file(iso3: str, level: int, b_dir: Path) -> Path | None:
        if not b_dir.exists():
            return None
        country_dir = b_dir / iso3.lower()
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
        for col in gdf.columns:
            col_lower = str(col).lower()
            if col_type == 'pcode' and "pcode" in col_lower and str(level) in col_lower:
                return gdf.rename(columns={col: target})
            if col_type == 'name' and "name" in col_lower and str(level) in col_lower:
                return gdf.rename(columns={col: target})
        return gdf

    countries = df_ipc["Country"].dropna().unique()
    boundaries_dir = workspace_dir / "hero_v4" / "data" / "boundaries"
    fallback_dir = workspace_dir / "rainfall" / "data" / "raw_boundaries0"
    if not fallback_dir.exists():
        fallback_dir = workspace_dir / "rainfall" / "data" / "raw_boundaries"
        
    for iso3 in countries:
        # Tenta di leggere da boundaries_dir, poi fallback
        for b_dir in [boundaries_dir, fallback_dir]:
            f_adm2 = find_boundary_file(iso3, 2, b_dir)
            if f_adm2:
                try:
                    gdf = gpd.read_file(f_adm2)
                    gdf = standardize_col(gdf, 2, 'pcode')
                    gdf = standardize_col(gdf, 2, 'name')
                    gdf = standardize_col(gdf, 1, 'pcode')
                    gdf = standardize_col(gdf, 1, 'name')
                    
                    if 'adm2_pcode' in gdf.columns and 'adm2_name' in gdf.columns:
                        for _, row in gdf.iterrows():
                            p = row['adm2_pcode']
                            n = row['adm2_name']
                            if p and n and not pd.isna(p) and not pd.isna(n):
                                norm = normalize_name(str(n))
                                if norm:
                                    adm2_map[(iso3.upper(), norm)] = p
                                    
                    if 'adm1_pcode' in gdf.columns and 'adm1_name' in gdf.columns:
                        for _, row in gdf.iterrows():
                            p = row['adm1_pcode']
                            n = row['adm1_name']
                            if p and n and not pd.isna(p) and not pd.isna(n):
                                norm = normalize_name(str(n))
                                if norm:
                                    adm1_map[(iso3.upper(), norm)] = p
                    break
                except Exception as e:
                    pass
                    
        for b_dir in [boundaries_dir, fallback_dir]:
            f_adm1 = find_boundary_file(iso3, 1, b_dir)
            if f_adm1:
                try:
                    gdf = gpd.read_file(f_adm1)
                    gdf = standardize_col(gdf, 1, 'pcode')
                    gdf = standardize_col(gdf, 1, 'name')
                    
                    if 'adm1_pcode' in gdf.columns and 'adm1_name' in gdf.columns:
                        for _, row in gdf.iterrows():
                            p = row['adm1_pcode']
                            n = row['adm1_name']
                            if p and n and not pd.isna(p) and not pd.isna(n):
                                norm = normalize_name(str(n))
                                if norm:
                                    adm1_map[(iso3.upper(), norm)] = p
                    break
                except Exception as e:
                    pass
                    
    logger.info(f"Lookup completati. Elementi Admin2: {len(adm2_map)}, Admin1: {len(adm1_map)}")
    
    # Esecuzione del ripristino in df_ipc
    rescued_adm2 = 0
    rescued_adm1 = 0
    rescued_adm2_by_country = {}
    rescued_adm1_by_country = {}
    
    for idx, row in df_ipc.iterrows():
        country = row["Country"]
        adm2_p = row["adm2_pcode"]
        adm1_p = row["adm1_pcode"]
        area = row["Area"]
        level1 = row["Level 1"]
        
        # Ripristino Admin 2
        if pd.isna(adm2_p) and not pd.isna(area):
            norm = normalize_name(str(area))
            norm = spelling_overrides_adm2.get((country, norm), norm)
            match = adm2_map.get((country, norm))
            if match:
                df_ipc.at[idx, "adm2_pcode"] = match
                rescued_adm2 += 1
                rescued_adm2_by_country[country] = rescued_adm2_by_country.get(country, 0) + 1
                
        # Ripristino Admin 1
        if pd.isna(adm1_p) and not pd.isna(level1):
            norm = normalize_name(str(level1))
            norm = spelling_overrides_adm1.get((country, norm), norm)
            match = adm1_map.get((country, norm))
            if match:
                df_ipc.at[idx, "adm1_pcode"] = match
                rescued_adm1 += 1
                rescued_adm1_by_country[country] = rescued_adm1_by_country.get(country, 0) + 1
                
    logger.info(f"PCODE Ripristinati: Admin2={rescued_adm2} {dict(sorted(rescued_adm2_by_country.items()))}")
    logger.info(f"PCODE Ripristinati: Admin1={rescued_adm1} {dict(sorted(rescued_adm1_by_country.items()))}")
    
    # P2 Fix: Rilevamento vero Admin 2 vs Admin 1
    # Se adm2_pcode == adm1_pcode o adm2_pcode è nullo, non è un vero codice Admin2
    df_ipc["is_true_admin2"] = (
        df_ipc["adm2_pcode"].notna() & 
        df_ipc["adm1_pcode"].notna() & 
        (df_ipc["adm2_pcode"] != df_ipc["adm1_pcode"])
    )

    
    logger.info(f"  IPC True Admin2 count: {df_ipc['is_true_admin2'].sum()}/{len(df_ipc)} "
                f"({df_ipc['is_true_admin2'].mean()*100:.1f}%)")
    
    # Normalizzazione nomi geografici per superare differenze di spelling
    df_ipc["norm_adm1"] = df_ipc["Level 1"].apply(normalize_name)
    df_wfp["norm_adm1"] = df_wfp["adm1_name"].apply(normalize_name)
    
    df_wfp["date"] = pd.to_datetime(df_wfp["date"], errors="coerce")
    df_rain["date"] = pd.to_datetime(df_rain["date"], errors="coerce")
    
    # ────────────────────────────────────────────────────────────────────────
    # ALLINEAMENTO SPATIAL FALLBACK WFP
    # ────────────────────────────────────────────────────────────────────────
    logger.info("Pre-aggregazione dei dati WFP per livello spaziale...")
    
    wfp_levels = {
        "admin2": (
            df_wfp.dropna(subset=["adm2_pcode"])
            .groupby(["ISO3", "adm2_pcode", "date"], observed=True)
            .agg(
                price=("price", "mean"),
                inflation=("inflation", "mean"),
                mapping_method=("mapping_method_adm2", lambda x: "elastic_buffer" if "elastic_buffer" in x.values else "strict_pip")
            )
            .reset_index()
        ),
        "admin1_code": (
            df_wfp.dropna(subset=["adm1_pcode"])
            .groupby(["ISO3", "adm1_pcode", "date"], observed=True)
            .agg(
                price=("price", "mean"),
                inflation=("inflation", "mean"),
                mapping_method=("mapping_method_adm1", lambda x: "elastic_buffer" if "elastic_buffer" in x.values else "strict_pip")
            )
            .reset_index()
        ),
        "admin1_name": (
            # P1 Fix: Filtra norm_adm1 != "" per evitare cross-join spuri su stringhe vuote
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
    
    for k, v in wfp_levels.items():
        logger.info(f"  WFP pre-agg {k}: {v.shape}")
        
    logger.info("Avvio allineamento gerarchico WFP...")
    wfp_chunks = []
    wfp_matched_ids = set()
    
    level_specs = [
        # (label, wfp_key, left_keys, right_keys, filter_col)
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
            
        # P1 Fix: Escludi norm_adm1 vuoti a livello di nome per evitare cross-join spuri
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
        
        # Filtro temporale
        m = m[(m["date"] >= m["date_from"]) & (m["date"] <= m["date_to"])]
        
        if m.empty:
            logger.info(f"  WFP {label}: 0 righe matchate.")
            continue
            
        # Aggregazione temporale (Fase 2)
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
        logger.info(f"  WFP {label}: {len(agg)} righe matchate.")
        
    if wfp_chunks:
        wfp_final = pd.concat(wfp_chunks, ignore_index=True)
    else:
        wfp_final = pd.DataFrame(
            columns=["ipc_row_id", "WFP_avg_price", "WFP_avg_inflation", "wfp_match_level", "wfp_obs_count", "wfp_spatial_mapping_method"]
        )
        
    # ────────────────────────────────────────────────────────────────────────
    # ALLINEAMENTO SPATIAL FALLBACK RAINFALL
    # ────────────────────────────────────────────────────────────────────────
    logger.info("Allineamento gerarchico Rainfall (P3)...")
    
    # Separazione per adm_level per evitare doppi conteggi
    rain_adm2 = df_rain[df_rain["adm_level"] == 2][["ISO3", "PCODE", "date", "r1h", "rfq"]]
    rain_adm1 = df_rain[df_rain["adm_level"] == 1][["ISO3", "PCODE", "date", "r1h", "rfq"]]
    rain_national = (
        df_rain.groupby(["ISO3", "date"], observed=True)[["r1h", "rfq"]]
        .mean()
        .reset_index()
    )
    
    logger.info(f"  Rainfall separato: Admin2={len(rain_adm2)} righe, Admin1={len(rain_adm1)} righe")
    
    rain_chunks = []
    rain_matched_ids = set()
    
    # -- Livello 1: Admin 2 (solo su righe IPC con vero Admin2)
    ipc_true_adm2 = df_ipc[df_ipc["is_true_admin2"]]
    if not ipc_true_adm2.empty and not rain_adm2.empty:
        m = pd.merge(
            ipc_true_adm2[["ipc_row_id", "Country", "adm2_pcode", "date_from", "date_to"]],
            rain_adm2,
            left_on=["Country", "adm2_pcode"],
            right_on=["ISO3", "PCODE"]
        )
        m = m[(m["date"] >= m["date_from"]) & (m["date"] <= m["date_to"])]
        if not m.empty:
            agg = (
                m.groupby("ipc_row_id")
                .agg(
                    Rain_avg_r1h=("r1h", "mean"),
                    Rain_avg_rfq=("rfq", "mean"),
                    rain_obs_count=("r1h", "size"),
                )
                .reset_index()
            )
            agg["rain_match_level"] = "Admin2"
            rain_chunks.append(agg)
            rain_matched_ids.update(agg["ipc_row_id"])
            logger.info(f"  Rainfall Admin2: {len(agg)} righe matchate.")
            
    # -- Livello 2: Admin 1 Code
    remaining = df_ipc[~df_ipc["ipc_row_id"].isin(rain_matched_ids)]
    if not remaining.empty and not rain_adm1.empty:
        m = pd.merge(
            remaining[["ipc_row_id", "Country", "adm1_pcode", "date_from", "date_to"]],
            rain_adm1,
            left_on=["Country", "adm1_pcode"],
            right_on=["ISO3", "PCODE"]
        )
        m = m[(m["date"] >= m["date_from"]) & (m["date"] <= m["date_to"])]
        if not m.empty:
            agg = (
                m.groupby("ipc_row_id")
                .agg(
                    Rain_avg_r1h=("r1h", "mean"),
                    Rain_avg_rfq=("rfq", "mean"),
                    rain_obs_count=("r1h", "size"),
                )
                .reset_index()
            )
            agg["rain_match_level"] = "Admin1"
            rain_chunks.append(agg)
            rain_matched_ids.update(agg["ipc_row_id"])
            logger.info(f"  Rainfall Admin1: {len(agg)} righe matchate.")
            
    # -- Livello 3: National
    remaining = df_ipc[~df_ipc["ipc_row_id"].isin(rain_matched_ids)]
    if not remaining.empty:
        m = pd.merge(
            remaining[["ipc_row_id", "Country", "date_from", "date_to"]],
            rain_national,
            left_on=["Country"],
            right_on=["ISO3"]
        )
        m = m[(m["date"] >= m["date_from"]) & (m["date"] <= m["date_to"])]
        if not m.empty:
            agg = (
                m.groupby("ipc_row_id")
                .agg(
                    Rain_avg_r1h=("r1h", "mean"),
                    Rain_avg_rfq=("rfq", "mean"),
                    rain_obs_count=("r1h", "size"),
                )
                .reset_index()
            )
            agg["rain_match_level"] = "National"
            rain_chunks.append(agg)
            logger.info(f"  Rainfall National: {len(agg)} righe matchate.")
            
    if rain_chunks:
        rain_final = pd.concat(rain_chunks, ignore_index=True)
    else:
        rain_final = pd.DataFrame(
            columns=["ipc_row_id", "Rain_avg_r1h", "Rain_avg_rfq", "rain_match_level", "rain_obs_count"]
        )
        
    # ────────────────────────────────────────────────────────────────────────
    # MERGE FINALE E SALVATAGGIO
    # ────────────────────────────────────────────────────────────────────────
    logger.info("Unione finale dei dati IPC con WFP e Rainfall allineati...")
    df_consolidated = df_ipc.merge(wfp_final, on="ipc_row_id", how="left")
    df_consolidated = df_consolidated.merge(rain_final, on="ipc_row_id", how="left")
    
    # Riempimento dei valori nulli per i livelli di match, mapping e osservazioni
    df_consolidated["wfp_match_level"] = df_consolidated["wfp_match_level"].fillna("No_Match")
    df_consolidated["wfp_spatial_mapping_method"] = df_consolidated["wfp_spatial_mapping_method"].fillna("unmapped")
    df_consolidated["rain_match_level"] = df_consolidated["rain_match_level"].fillna("No_Match")
    df_consolidated["wfp_obs_count"] = df_consolidated["wfp_obs_count"].fillna(0).astype(int)
    df_consolidated["rain_obs_count"] = df_consolidated["rain_obs_count"].fillna(0).astype(int)
    
    # Rimuoviamo colonne temporanee
    cols_to_drop = ["ipc_row_id", "date_from", "date_to", "norm_adm1", "is_true_admin2"]
    df_consolidated = df_consolidated.drop(columns=cols_to_drop, errors="ignore")
    
    out_csv = reconciled_dir / "ipc_wfp_reconciled.csv"
    out_csv_alt = reconciled_dir / "ipc_reconciled_wide.csv"
    
    logger.info(f"Salvataggio in CSV: {out_csv}...")
    df_consolidated.to_csv(out_csv, index=False)
    df_consolidated.to_csv(out_csv_alt, index=False)
    
    elapsed = time.time() - t0
    logger.info(f"✨ STEP 3 COMPLETATO CON SUCCESSO in {elapsed:.2f}s!")
    logger.info(f"   Shape finale consolidata: {df_consolidated.shape}")
    
    # Mostra report di copertura
    wfp_cov = (df_consolidated["wfp_match_level"] != "No_Match").mean() * 100
    rain_cov = (df_consolidated["rain_match_level"] != "No_Match").mean() * 100
    both_cov = ((df_consolidated["wfp_match_level"] != "No_Match") & (df_consolidated["rain_match_level"] != "No_Match")).mean() * 100
    
    logger.info(f"   Copertura WFP: {wfp_cov:.1f}%")
    logger.info(f"   Copertura Rainfall: {rain_cov:.1f}%")
    logger.info(f"   Copertura Entrambi: {both_cov:.1f}%")
    
    logger.info(f"   WFP Match Levels: {df_consolidated['wfp_match_level'].value_counts().to_dict()}")
    logger.info(f"   Rain Match Levels: {df_consolidated['rain_match_level'].value_counts().to_dict()}")
    logger.info("==================================================")

if __name__ == "__main__":
    main()
