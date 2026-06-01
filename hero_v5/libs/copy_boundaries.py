import shutil
import pandas as pd
from pathlib import Path

def main():
    print("==================================================")
    print("AVVIO COPIA CONFINI PER HERO v5")
    print("==================================================")
    
    workspace_dir = Path(__file__).resolve().parent.parent.parent
    src_boundaries = workspace_dir / "hero_v4" / "data" / "boundaries"
    dest_boundaries = workspace_dir / "hero_v5" / "data" / "boundaries"
    dest_boundaries.mkdir(parents=True, exist_ok=True)
    
    parquet_path = workspace_dir / "ipc_rain_conflict_idp.parquet"
    if not parquet_path.exists():
        print(f"File {parquet_path} non trovato!")
        return
        
    print(f"Lettura paesi da {parquet_path.name}...")
    df = pd.read_parquet(parquet_path)
    countries = df["Country"].dropna().unique()
    print(f"Paesi nel dataset: {len(countries)} ({sorted(list(countries))})")
    
    copied_count = 0
    missing_count = 0
    
    for country in sorted(countries):
        country_lower = country.lower()
        src_folder = src_boundaries / country_lower
        dest_folder = dest_boundaries / country_lower
        
        if src_folder.exists() and src_folder.is_dir():
            if dest_folder.exists():
                shutil.rmtree(dest_folder)
            shutil.copytree(src_folder, dest_folder)
            print(f"  [OK] Copiati confini per {country.upper()}")
            copied_count += 1
        else:
            print(f"  [WARNING] Confini non trovati per {country.upper()} in {src_boundaries}")
            missing_count += 1
            
    print("==================================================")
    print(f"COPIA COMPLETATA! Copiati: {copied_count}, Mancanti: {missing_count}")
    print("==================================================")

if __name__ == "__main__":
    main()
