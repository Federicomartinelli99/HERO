import sys
import pandas as pd
from pathlib import Path

# Aggiunge il path per importare utils
sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils import setup_logger

logger = setup_logger("01_consolidate_wfp", "01_consolidate_wfp.log")

def main():
    logger.info("==================================================")
    logger.info("AVVIO STEP 1: CONSOLIDAMENTO DATI RAW WFP")
    logger.info("==================================================")
    
    workspace_dir = Path(__file__).resolve().parent.parent.parent.parent
    source_dir = workspace_dir / "World_Food_Prices" / "data" / "raw_food_prices"
    target_dir = workspace_dir / "hero_v4" / "data" / "interim"
    target_dir.mkdir(parents=True, exist_ok=True)
    
    csv_files = sorted(list(source_dir.glob("global_food_*.csv")))
    if not csv_files:
        logger.error(f"Nessun file CSV trovato in {source_dir}")
        return
        
    logger.info(f"Trovati {len(csv_files)} file CSV da consolidare in {source_dir.name}.")
    
    # Colonne da caricare per risparmiare memoria ed evitare overflow
    required_cols = [
        'ISO3', 'country', 'adm1_name', 'adm2_name', 'mkt_name', 
        'lat', 'lon', 'year', 'month', 'c_food_price_index', 'inflation_food_price_index', 'geo_id'
    ]
    
    dfs = []
    for file_path in csv_files:
        logger.info(f"Elaborazione file: {file_path.name}...")
        try:
            # Leggiamo solo le colonne richieste
            df = pd.read_csv(file_path, usecols=lambda c: c in required_cols, low_memory=False)
            
            # Controllo colonne mancanti
            missing = [c for c in required_cols if c not in df.columns]
            if missing:
                logger.warning(f"Colonne mancanti in {file_path.name}: {missing}. Verranno riempite con valori nulli.")
                for m in missing:
                    df[m] = None
                    
            # Costruzione colonna 'date'
            if 'year' in df.columns and 'month' in df.columns:
                valid_time = df['year'].notna() & df['month'].notna()
                df['date'] = pd.NaT
                df.loc[valid_time, 'date'] = pd.to_datetime(
                    df.loc[valid_time, 'year'].astype(int).astype(str) + '-' + 
                    df.loc[valid_time, 'month'].astype(int).astype(str) + '-01',
                    errors='coerce'
                )
            
            # Allinea l'ordine delle colonne
            df = df[required_cols + ['date']]
            
            # Cast dei tipi per risparmiare memoria RAM
            categorical_cols = ['ISO3', 'country', 'adm1_name', 'adm2_name', 'mkt_name']
            for col in categorical_cols:
                if col in df.columns:
                    df[col] = df[col].astype('category')
                    
            dfs.append(df)
            logger.info(f"  -> Righe caricate con successo: {len(df):,}")
        except Exception as e:
            logger.error(f"Errore durante l'elaborazione di {file_path.name}: {e}")
            
    if not dfs:
        logger.error("Nessun dato è stato caricato. Interruzione pipeline.")
        return
        
    logger.info("Concatenazione di tutti i dataset caricati...")
    df_total = pd.concat(dfs, ignore_index=True)
    
    # Rinomina colonne indici per consistenza con le pipeline standard
    df_total = df_total.rename(columns={
        'c_food_price_index': 'price',
        'inflation_food_price_index': 'inflation'
    })
    
    # Salvataggio nei file Parquet di output
    out_parquet = target_dir / "wfp_consolidate.parquet"
    out_parquet_alt = target_dir / "wpf_consolidate.parquet"
    
    logger.info(f"Salvataggio dataset consolidato in: {out_parquet}")
    df_total.to_parquet(out_parquet, engine='pyarrow', index=False)
    df_total.to_parquet(out_parquet_alt, engine='pyarrow', index=False)
    
    size_mb = out_parquet.stat().st_size / (1024 * 1024)
    logger.info(f"✨ STEP 1 COMPLETATO CON SUCCESSO!")
    logger.info(f"   Shape finale: {df_total.shape[0]:,} righe × {df_total.shape[1]} colonne")
    logger.info(f"   Dimensione file: {size_mb:.2f} MB")
    logger.info("==================================================")

if __name__ == "__main__":
    main()
