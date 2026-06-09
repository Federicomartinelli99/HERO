import os
import sys
import time
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from pathlib import Path

def main():
    start_time = time.time()
    
    # Setup paths relative to this script
    script_dir = Path(__file__).resolve().parent
    csv_path = script_dir / "join_wpdx_with_ipc_wide.csv"
    parquet_path = script_dir / "join_wpdx_with_ipc_wide.parquet"
    
    # Walk up to find HERO workspace directory
    workspace_dir = script_dir
    while workspace_dir.name != "HERO" and workspace_dir.parent != workspace_dir:
        workspace_dir = workspace_dir.parent
    boundaries_dir = workspace_dir / "hero_v5" / "data" / "boundaries"
    
    print("==========================================================")
    # Emojiless print for windows console compatibility
    print("  INIZIO ASSOCIAZIONE SPAZIALE ADM PCODES (WPDX)")
    print("==========================================================")
    print(f"File CSV di input: {csv_path}")
    print(f"File Parquet di output: {parquet_path}")
    print(f"Cartella confini GeoJSON/SHP: {boundaries_dir}")
    print("----------------------------------------------------------")
    
    if not csv_path.exists():
        print(f"ERRORE: Il file CSV non esiste in {csv_path}")
        sys.exit(1)
        
    print("Caricamento dataset CSV...")
    # Read CSV without specifying dtypes first to avoid cast errors
    df = pd.read_csv(csv_path, low_memory=False)
    total_rows = len(df)
    print(f"Dataset caricato con successo. Righe totali: {total_rows:,}")
    
    # Pulizia e conversione coordinate in formato numerico (gestione virgola come separatore decimale)
    print("Pulizia e validazione coordinate geografiche (lat_deg, lon_deg)...")
    df['lat_clean'] = df['lat_deg'].astype(str).str.replace(',', '.', regex=False)
    df['lat_clean'] = pd.to_numeric(df['lat_clean'], errors='coerce')
    df['lon_clean'] = df['lon_deg'].astype(str).str.replace(',', '.', regex=False)
    df['lon_clean'] = pd.to_numeric(df['lon_clean'], errors='coerce')
    
    # Inizializza le colonne manuali
    df['adm1_pcode_manual'] = None
    df['adm2_pcode_manual'] = None
    
    unique_countries = df['country_id'].dropna().unique()
    print(f"Paesi unici trovati nel CSV: {list(unique_countries)}")
    
    # Helper per trovare dinamicamente i file spaziali di una nazione
    def find_spatial_files(country_id):
        iso3 = str(country_id).strip().lower()
        country_dir = boundaries_dir / iso3
        
        # Gestione case-insensitive se il nome cartella differisce
        if not country_dir.exists():
            for p in boundaries_dir.iterdir():
                if p.is_dir() and p.name.lower() == iso3:
                    country_dir = p
                    break
            else:
                return None, None
                
        admin2_file = None
        admin1_file = None
        
        # Scansione ricorsiva per supportare shapefile o geojson in sottocartelle
        for root, dirs, files in os.walk(country_dir):
            for f in files:
                f_lower = f.lower()
                if f_lower.endswith('.shp') or f_lower.endswith('.geojson'):
                    if 'admin2' in f_lower or 'adm2' in f_lower:
                        admin2_file = Path(root) / f
                    elif 'admin1' in f_lower or 'adm1' in f_lower:
                        admin1_file = Path(root) / f
                        
        return admin1_file, admin2_file

    # Helper per cercare le colonne pcode in modo case-insensitive
    def find_pcode_col(columns, level):
        target = f"adm{level}_pcode"
        # 1. Ricerca corrispondenza esatta case-insensitive
        for c in columns:
            if c.lower() == target:
                return c
        # 2. Ricerca parziale robusta
        for c in columns:
            c_lower = c.lower()
            if f"adm{level}" in c_lower and "pcode" in c_lower:
                return c
            if f"adm{level}" in c_lower and "pc" in c_lower:
                return c
        return None

    # Esegui spatial join per ciascun paese
    for country in unique_countries:
        df_country = df[df['country_id'] == country]
        country_rows = len(df_country)
        print(f"\nElaborazione paese: {country} ({country_rows:,} righe)...")
        
        # Trova i file spaziali
        admin1_path, admin2_path = find_spatial_files(country)
        
        if not admin2_path and not admin1_path:
            print(f"  --> ATTENZIONE: Nessun file di confine (SHP/GeoJSON) trovato per {country}. Skip.")
            continue
            
        # Filtra solo le righe con coordinate geografiche valide
        valid_mask = df_country['lat_clean'].notna() & df_country['lon_clean'].notna()
        df_valid = df_country[valid_mask].copy()
        valid_rows = len(df_valid)
        
        if valid_rows == 0:
            print(f"  --> Nessuna riga con coordinate geografiche valide per {country}.")
            continue
            
        # Crea GeoDataFrame per i punti del paese
        geometry = [Point(xy) for xy in zip(df_valid['lon_clean'], df_valid['lat_clean'])]
        points_gdf = gpd.GeoDataFrame(df_valid, geometry=geometry, crs="EPSG:4326")
        points_gdf = points_gdf.drop(columns=['adm1_pcode_manual', 'adm2_pcode_manual'], errors='ignore')
        
        # Caso A: Trovato file Admin2 (contiene sia Admin1 che Admin2)
        if admin2_path:
            print(f"  --> Caricamento confini Admin2: {admin2_path.name}")
            try:
                boundary_gdf = gpd.read_file(admin2_path)
                boundary_gdf = boundary_gdf.to_crs("EPSG:4326")
                
                # Cerca le colonne pcode corrette nel file spaziale
                p1_col = find_pcode_col(boundary_gdf.columns, 1)
                p2_col = find_pcode_col(boundary_gdf.columns, 2)
                
                if p2_col:
                    cols_to_keep = [p2_col, 'geometry']
                    rename_dict = {p2_col: 'adm2_pcode_manual'}
                    
                    if p1_col:
                        cols_to_keep.append(p1_col)
                        rename_dict[p1_col] = 'adm1_pcode_manual'
                    else:
                        print("  --> WARNING: Colonna Admin1 PCode non trovata nel file Admin2.")
                        
                    # Pulisci boundary dataframe
                    boundary_gdf = boundary_gdf[cols_to_keep].copy()
                    boundary_gdf = boundary_gdf.rename(columns=rename_dict)
                    
                    # Esegui Spatial Join
                    joined = gpd.sjoin(points_gdf, boundary_gdf, how="left", predicate="within")
                    
                    # Salva nel dataframe principale
                    df.loc[df_valid.index, 'adm2_pcode_manual'] = joined['adm2_pcode_manual']
                    if 'adm1_pcode_manual' in joined.columns:
                        df.loc[df_valid.index, 'adm1_pcode_manual'] = joined['adm1_pcode_manual']
                        
                    matched_a2 = joined['adm2_pcode_manual'].notna().sum()
                    matched_a1 = joined['adm1_pcode_manual'].notna().sum() if 'adm1_pcode_manual' in joined.columns else 0
                    print(f"  --> Successo: Accoppiati ADM1={matched_a1}/{valid_rows} ({matched_a1/valid_rows*100:.2f}%), ADM2={matched_a2}/{valid_rows} ({matched_a2/valid_rows*100:.2f}%)")
                else:
                    print(f"  --> ERRORE: Colonna PCode Admin2 non trovata in {admin2_path.name}")
            except Exception as e:
                print(f"  --> ERRORE durante il caricamento o join del file Admin2: {e}")
                
        # Caso B: Trovato solo file Admin1
        elif admin1_path:
            print(f"  --> Caricamento confini Admin1: {admin1_path.name}")
            try:
                boundary_gdf = gpd.read_file(admin1_path)
                boundary_gdf = boundary_gdf.to_crs("EPSG:4326")
                
                p1_col = find_pcode_col(boundary_gdf.columns, 1)
                
                if p1_col:
                    boundary_gdf = boundary_gdf[[p1_col, 'geometry']].copy()
                    boundary_gdf = boundary_gdf.rename(columns={p1_col: 'adm1_pcode_manual'})
                    
                    # Esegui Spatial Join
                    joined = gpd.sjoin(points_gdf, boundary_gdf, how="left", predicate="within")
                    
                    # Salva nel dataframe principale
                    df.loc[df_valid.index, 'adm1_pcode_manual'] = joined['adm1_pcode_manual']
                    
                    matched_a1 = joined['adm1_pcode_manual'].notna().sum()
                    print(f"  --> Successo: Accoppiati ADM1={matched_a1}/{valid_rows} ({matched_a1/valid_rows*100:.2f}%), ADM2=Non disponibile")
                else:
                    print(f"  --> ERRORE: Colonna PCode Admin1 non trovata in {admin1_path.name}")
            except Exception as e:
                print(f"  --> ERRORE durante il caricamento o join del file Admin1: {e}")

    # Rimuovi le colonne temporanee di pulizia coordinate
    df = df.drop(columns=['lat_clean', 'lon_clean'])
    
    # Salvataggio in formato Parquet
    print("\n----------------------------------------------------------")
    print(f"Salvataggio del dataset merged in formato Parquet...")
    try:
        df.to_parquet(parquet_path, index=False)
        print("Salvataggio completato con successo!")
    except Exception as e:
        print(f"ERRORE durante il salvataggio del Parquet: {e}")
        sys.exit(1)
        
    # Calcolo statistiche finali
    total_matched_adm1 = df['adm1_pcode_manual'].notna().sum()
    total_matched_adm2 = df['adm2_pcode_manual'].notna().sum()
    
    print("\n==========================================================")
    print("  STATISTICHE FINALI DI ASSOCIAZIONE")
    print("==========================================================")
    print(f"Righe Totali Processate: {total_rows:,}")
    print(f"Match ADM1 Manuali: {total_matched_adm1:,} ({total_matched_adm1/total_rows*100:.2f}%)")
    print(f"Match ADM2 Manuali: {total_matched_adm2:,} ({total_matched_adm2/total_rows*100:.2f}%)")
    
    # Mostra statistiche per paese
    print("\nDettaglio Match Rate per Paese:")
    for country in unique_countries:
        df_c = df[df['country_id'] == country]
        c_rows = len(df_c)
        c_a1 = df_c['adm1_pcode_manual'].notna().sum()
        c_a2 = df_c['adm2_pcode_manual'].notna().sum()
        print(f"  - {country}: Righe={c_rows:,} | ADM1 Match={c_a1:,} ({c_a1/c_rows*100:.1f}%) | ADM2 Match={c_a2:,} ({c_a2/c_rows*100:.1f}%)")
        
    duration = time.time() - start_time
    print(f"\nTempo di esecuzione totale: {duration:.2f} secondi ({duration/60:.2f} minuti)")
    print("==========================================================")

if __name__ == "__main__":
    main()
