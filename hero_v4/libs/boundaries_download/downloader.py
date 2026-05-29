import sys
import pandas as pd
from pathlib import Path

# Aggiunge il path per caricare la libreria hdx_boundaries_loader
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hdx_boundaries_loader import HDXBoundariesLoader, get_logger

logger = get_logger("downloader", "boundaries_downloader.log")

def main():
    logger.info("==================================================")
    logger.info("AVVIO DOWNLOAD CONFINI HDX COMPLETO (IPC + WFP)")
    logger.info("==================================================")
    
    workspace_dir = Path(__file__).resolve().parent.parent.parent.parent
    ipc_csv_path = workspace_dir / "ipc" / "ipc_global_area_wide_pcoded.csv"
    wfp_parquet_path = workspace_dir / "hero_v4" / "data" / "interim" / "wfp_consolidate.parquet"
    
    countries = set()
    
    # 1. Carica paesi da IPC
    if ipc_csv_path.exists():
        try:
            logger.info(f"Lettura paesi da IPC: {ipc_csv_path.name}")
            df_ipc = pd.read_csv(ipc_csv_path)
            ipc_countries = df_ipc["Country"].dropna().unique().tolist()
            countries.update(ipc_countries)
            logger.info(f"Trovati {len(ipc_countries)} paesi in IPC.")
        except Exception as e:
            logger.error(f"Errore nella lettura del file IPC: {e}")
    else:
        logger.warning(f"File IPC non trovato in: {ipc_csv_path}")
        
    # 2. Carica paesi da WFP
    if wfp_parquet_path.exists():
        try:
            logger.info(f"Lettura paesi da WFP: {wfp_parquet_path.name}")
            df_wfp = pd.read_parquet(wfp_parquet_path, columns=["ISO3"])
            wfp_countries = df_wfp["ISO3"].dropna().unique().tolist()
            countries.update(wfp_countries)
            logger.info(f"Trovati {len(wfp_countries)} paesi in WFP.")
        except Exception as e:
            logger.error(f"Errore nella lettura del file WFP: {e}")
    else:
        logger.warning(f"File WFP non trovato in: {wfp_parquet_path}")
        
    sorted_countries = sorted(list(countries))
    logger.info(f"Totale paesi unici da verificare (Unione IPC + WFP): {len(sorted_countries)}")
    logger.info(f"Lista paesi: {sorted_countries}")
        
    # Inizializza loader
    loader = HDXBoundariesLoader()
    
    # Download sequenziale
    logger.info("Inizio download sequenziale confini da HDX...")
    results = loader.fetch_many(sorted_countries)
    
    # Report finale
    success_count = sum(1 for k, v in results.items() if v is not None)
    logger.info(f"Completato! Scaricati con successo confini per {success_count}/{len(sorted_countries)} paesi.")
    logger.info("I file sono salvati nella cartella: hero_v4/data/boundaries/")
    logger.info("==================================================")

if __name__ == "__main__":
    main()
