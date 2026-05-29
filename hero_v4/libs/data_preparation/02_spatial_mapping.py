import os
import sys
import pandas as pd
import numpy as np
import geopandas as gpd
from pathlib import Path
from tqdm import tqdm

# Imposta limite massimo per dimensione GeoJSON a illimitato per fiona/gdal
os.environ["OGR_GEOJSON_MAX_OBJ_SIZE"] = "0"

# Aggiunge il path per importare utils
sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils import setup_logger

logger = setup_logger("02_spatial_mapping", "02_spatial_mapping.log")

def find_boundary_file(iso3: str, level: int, boundaries_dir: Path, fallback_dir: Path = None) -> Path | None:
    """Trova il file GeoJSON o Shapefile per un dato paese e livello amministrativo (1 o 2) usando regex."""
    import re
    for b_dir in [boundaries_dir, fallback_dir]:
        if b_dir is None:
            continue
        country_dir = b_dir / iso3.lower()
        if not country_dir.exists():
            continue
        
        # Raccoglie tutti i file .geojson e .shp ricorsivamente
        all_files = list(country_dir.rglob("*.geojson")) + list(country_dir.rglob("*.shp"))
        
        # Filtra i file usando una regex per il livello amministrativo
        # E.g., _adm1_, _admin1_, _adm1.geojson, adm1.shp
        regex_pattern = rf"[._-]adm(in)?{level}([._-]|$)"
        
        matching_files = []
        for f in all_files:
            if re.search(regex_pattern, f.name.lower()):
                matching_files.append(f)
                
        # Priorità ai file .geojson rispetto ai .shp
        geojson_files = [f for f in matching_files if f.suffix.lower() == ".geojson"]
        shp_files = [f for f in matching_files if f.suffix.lower() == ".shp"]
        
        if geojson_files:
            return geojson_files[0]
        if shp_files:
            return shp_files[0]
            
        # Fallback se non trova file corrispondenti alla regex:
        # Se c'è solo un file .geojson o .shp, restituiscilo comunque
        if len(all_files) == 1:
            return all_files[0]
            
    return None

def standardize_pcode_column(gdf: gpd.GeoDataFrame, level: int) -> gpd.GeoDataFrame:
    """Identifica la colonna pcode nel GeoDataFrame e la standardizza in 'admX_pcode'."""
    standard_name = f"adm{level}_pcode"
    if standard_name in gdf.columns:
        return gdf
        
    # Ricerca euristica del nome della colonna
    for col in gdf.columns:
        col_lower = str(col).lower()
        if (f"adm{level}" in col_lower or f"admin{level}" in col_lower) and "pco" in col_lower:
            logger.info(f"    Rinominata colonna '{col}' -> '{standard_name}'")
            return gdf.rename(columns={col: standard_name})
            
    # Se non trova corrispondenza esatta, cerca qualsiasi cosa con pcode
    for col in gdf.columns:
        col_lower = str(col).lower()
        if "pcode" in col_lower and str(level) in col_lower:
            logger.info(f"    Rinominata colonna '{col}' -> '{standard_name}'")
            return gdf.rename(columns={col: standard_name})
            
    return gdf

def main():
    logger.info("==================================================")
    logger.info("AVVIO STEP 2: POINT-IN-POLYGON (PIP) SPATIAL MAPPING")
    logger.info("==================================================")
    
    workspace_dir = Path(__file__).resolve().parent.parent.parent.parent
    data_dir = workspace_dir / "hero_v4" / "data" / "interim"
    wfp_parquet_path = data_dir / "wfp_consolidate.parquet"
    boundaries_dir = workspace_dir / "hero_v4" / "data" / "boundaries"
    fallback_boundaries_dir = workspace_dir / "rainfall" / "data" / "raw_boundaries0"
    
    if not wfp_parquet_path.exists():
        logger.error(f"File consolidato WFP non trovato in {wfp_parquet_path}. Eseguire lo Step 1 prima.")
        return
        
    logger.info(f"Caricamento dati WFP consolidati da {wfp_parquet_path.name}...")
    df_wfp = pd.read_parquet(wfp_parquet_path)
    
    # 1. Estrazione dei mercati unici con coordinate valide
    logger.info("Estrazione dei mercati unici con coordinate geografiche valide...")
    colonne_geo = ['ISO3', 'mkt_name', 'lat', 'lon']
    df_mercati = df_wfp[colonne_geo].drop_duplicates().dropna(subset=['lat', 'lon']).copy()
    
    if df_mercati.empty:
        logger.error("Nessun mercato con coordinate lat/lon valide trovato nel dataset.")
        return
        
    logger.info(f"Trovati {len(df_mercati):,} mercati unici da mappare spazialmente.")
    
    # Creazione del GeoDataFrame dei mercati
    gdf_mercati = gpd.GeoDataFrame(
        df_mercati,
        geometry=gpd.points_from_xy(df_mercati.lon, df_mercati.lat),
        crs="EPSG:4326"
    )
    
    # Inizializza colonne PCODE e metodi di mapping
    gdf_mercati['adm1_pcode'] = np.nan
    gdf_mercati['adm2_pcode'] = np.nan
    gdf_mercati['mapping_method_adm1'] = 'unmapped'
    gdf_mercati['mapping_method_adm2'] = 'unmapped'
    
    paesi_unici = gdf_mercati['ISO3'].unique()
    logger.info(f"Paesi presenti nei mercati unici WFP: {list(paesi_unici)}")
    
    # 2. Point-in-Polygon (PIP) con fallback elastico per ciascun paese
    mapped_adm2_total = 0
    mapped_adm1_total = 0
    
    for iso3 in tqdm(paesi_unici, desc="Elaborazione Point-in-Polygon per paese"):
        iso3_str = str(iso3).lower()
        mask_paese = gdf_mercati['ISO3'] == iso3
        gdf_mercati_paese = gdf_mercati[mask_paese]
        
        if gdf_mercati_paese.empty:
            continue
            
        logger.info(f"Processing country [{iso3.upper()}] ({len(gdf_mercati_paese)} mercati)...")
        indices_paese = gdf_mercati_paese.index
        
        # --- Mappatura Livello 2 (Distretti) ---
        file_adm2 = find_boundary_file(iso3_str, 2, boundaries_dir, fallback_boundaries_dir)
        if file_adm2:
            try:
                logger.info(f"  Caricamento confini Admin2 da: {file_adm2.name}")
                gdf_adm2 = gpd.read_file(file_adm2)
                if gdf_adm2.crs != "EPSG:4326":
                    gdf_adm2 = gdf_adm2.to_crs("EPSG:4326")
                
                gdf_adm2 = standardize_pcode_column(gdf_adm2, 2)
                
                if 'adm2_pcode' in gdf_adm2.columns:
                    # Rimuoviamo colonne PCODE pre-esistenti a sinistra per evitare suffissi duplicati
                    left_df = gdf_mercati_paese.drop(columns=['adm1_pcode', 'adm2_pcode'], errors='ignore')
                    
                    # 1. Strict PIP
                    joined_pip = gpd.sjoin(
                        left_df, 
                        gdf_adm2[['adm2_pcode', 'geometry']], 
                        how="left", 
                        predicate="intersects"
                    )
                    
                    # Salva strict PIP
                    gdf_mercati.loc[indices_paese, 'adm2_pcode'] = joined_pip['adm2_pcode']
                    pip_mask = joined_pip['adm2_pcode'].notna()
                    gdf_mercati.loc[joined_pip[pip_mask].index, 'mapping_method_adm2'] = 'strict_pip'
                    
                    # 2. Fallback elastico per quelli rimasti unmapped
                    unmapped_pip_indices = joined_pip[~pip_mask].index
                    if len(unmapped_pip_indices) > 0 and len(gdf_adm2) > 0:
                        gdf_unmapped = left_df.loc[unmapped_pip_indices]
                        
                        import warnings
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore", category=UserWarning)
                            joined_nearest = gpd.sjoin_nearest(
                                gdf_unmapped,
                                gdf_adm2[['adm2_pcode', 'geometry']],
                                how="left",
                                max_distance=0.05,
                                distance_col="dist"
                            )
                        
                        # Rimuoviamo duplicati in caso lo stesso punto sia alla stessa distanza da più poligoni
                        joined_nearest = joined_nearest.reset_index().drop_duplicates(subset='index').set_index('index')
                        
                        nearest_mask = joined_nearest['adm2_pcode'].notna()
                        if nearest_mask.any():
                            matched_nearest = joined_nearest[nearest_mask]
                            gdf_mercati.loc[matched_nearest.index, 'adm2_pcode'] = matched_nearest['adm2_pcode']
                            gdf_mercati.loc[matched_nearest.index, 'mapping_method_adm2'] = 'elastic_buffer'
                            logger.info(f"  -> Distretti (Admin2) mappati via buffer elastico (<=0.05 deg): {len(matched_nearest)} mercati")
                    
                    # Qualsiasi rimasto nullo lo marchiamo come 'unmapped'
                    final_unmapped_adm2 = gdf_mercati.loc[indices_paese, 'adm2_pcode'].isna()
                    gdf_mercati.loc[gdf_mercati[mask_paese & final_unmapped_adm2].index, 'mapping_method_adm2'] = 'unmapped'
                    
                    mapped_adm2 = gdf_mercati.loc[indices_paese, 'adm2_pcode'].notna().sum()
                    mapped_adm2_total += mapped_adm2
                    logger.info(f"  -> Totale Distretti (Admin2) mappati per {iso3.upper()}: {mapped_adm2}/{len(gdf_mercati_paese)}")
                else:
                    logger.warning(f"  [!] Colonna 'adm2_pcode' non trovata o non standardizzata in {file_adm2.name}")
            except Exception as e:
                logger.error(f"  Errore mappatura Admin2 per {iso3.upper()}: {e}")
        else:
            logger.info(f"  Nessun file confini Admin2 trovato per {iso3.upper()}.")
            
        # --- Mappatura Livello 1 (Province) ---
        file_adm1 = find_boundary_file(iso3_str, 1, boundaries_dir, fallback_boundaries_dir)
        if file_adm1:
            try:
                logger.info(f"  Caricamento confini Admin1 da: {file_adm1.name}")
                gdf_adm1 = gpd.read_file(file_adm1)
                if gdf_adm1.crs != "EPSG:4326":
                    gdf_adm1 = gdf_adm1.to_crs("EPSG:4326")
                    
                gdf_adm1 = standardize_pcode_column(gdf_adm1, 1)
                
                if 'adm1_pcode' in gdf_adm1.columns:
                    # Rimuoviamo colonne PCODE pre-esistenti a sinistra per evitare suffissi duplicati
                    left_df = gdf_mercati_paese.drop(columns=['adm1_pcode', 'adm2_pcode'], errors='ignore')
                    
                    # 1. Strict PIP
                    joined_pip = gpd.sjoin(
                        left_df, 
                        gdf_adm1[['adm1_pcode', 'geometry']], 
                        how="left", 
                        predicate="intersects"
                    )
                    
                    # Salva strict PIP
                    gdf_mercati.loc[indices_paese, 'adm1_pcode'] = joined_pip['adm1_pcode']
                    pip_mask = joined_pip['adm1_pcode'].notna()
                    gdf_mercati.loc[joined_pip[pip_mask].index, 'mapping_method_adm1'] = 'strict_pip'
                    
                    # 2. Fallback elastico
                    unmapped_pip_indices = joined_pip[~pip_mask].index
                    if len(unmapped_pip_indices) > 0 and len(gdf_adm1) > 0:
                        gdf_unmapped = left_df.loc[unmapped_pip_indices]
                        
                        import warnings
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore", category=UserWarning)
                            joined_nearest = gpd.sjoin_nearest(
                                gdf_unmapped,
                                gdf_adm1[['adm1_pcode', 'geometry']],
                                how="left",
                                max_distance=0.05,
                                distance_col="dist"
                            )
                            
                        joined_nearest = joined_nearest.reset_index().drop_duplicates(subset='index').set_index('index')
                        
                        nearest_mask = joined_nearest['adm1_pcode'].notna()
                        if nearest_mask.any():
                            matched_nearest = joined_nearest[nearest_mask]
                            gdf_mercati.loc[matched_nearest.index, 'adm1_pcode'] = matched_nearest['adm1_pcode']
                            gdf_mercati.loc[matched_nearest.index, 'mapping_method_adm1'] = 'elastic_buffer'
                            logger.info(f"  -> Province (Admin1) mappate via buffer elastico (<=0.05 deg): {len(matched_nearest)} mercati")
                            
                    final_unmapped_adm1 = gdf_mercati.loc[indices_paese, 'adm1_pcode'].isna()
                    gdf_mercati.loc[gdf_mercati[mask_paese & final_unmapped_adm1].index, 'mapping_method_adm1'] = 'unmapped'
                    
                    mapped_adm1 = gdf_mercati.loc[indices_paese, 'adm1_pcode'].notna().sum()
                    mapped_adm1_total += mapped_adm1
                    logger.info(f"  -> Totale Province (Admin1) mappate per {iso3.upper()}: {mapped_adm1}/{len(gdf_mercati_paese)}")
                else:
                    logger.warning(f"  [!] Colonna 'adm1_pcode' non trovata o non standardizzata in {file_adm1.name}")
            except Exception as e:
                logger.error(f"  Errore mappatura Admin1 per {iso3.upper()}: {e}")
        else:
            logger.info(f"  Nessun file confini Admin1 trovato per {iso3.upper()}.")
            
    # 3. Riversa i PCODE calcolati sul dataset storico consolidato WFP
    logger.info("Unione dei PCODE calcolati con il dataset WFP storico consolidato...")
    
    # Rimuoviamo la colonna geometry prima del merge di pandas
    tabella_mappatura = pd.DataFrame(gdf_mercati.drop(columns='geometry'))
    
    df_wfp_arricchito = pd.merge(
        df_wfp,
        tabella_mappatura,
        on=['ISO3', 'mkt_name', 'lat', 'lon'],
        how='left'
    )
    
    out_parquet = data_dir / "wfp_with_pcodes.parquet"
    logger.info(f"Salvataggio del dataset WFP con PCODE in {out_parquet}...")
    df_wfp_arricchito.to_parquet(out_parquet, engine='pyarrow', index=False)
    
    logger.info("✨ STEP 2 COMPLETATO CON SUCCESSO!")
    logger.info(f"   Totale mercati mappati Admin2: {mapped_adm2_total}/{len(df_mercati)}")
    logger.info(f"   Totale mercati mappati Admin1: {mapped_adm1_total}/{len(df_mercati)}")
    logger.info(f"   Shape finale WFP con PCODE: {df_wfp_arricchito.shape[0]:,} righe × {df_wfp_arricchito.shape[1]} colonne")
    logger.info("==================================================")

if __name__ == "__main__":
    main()
