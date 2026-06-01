import sys
import logging
import pandas as pd
from pathlib import Path

def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        # Console Handler
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)
    return logger

logger = setup_logger("wfp_consolidate")

def main():
    logger.info("==================================================")
    logger.info("AVVIO CONSOLIDAMENTO DATI RAW WFP (v5)")
    logger.info("==================================================")
    
    workspace_dir = Path(__file__).resolve().parent.parent.parent
    source_dir = workspace_dir / "World_Food_Prices" / "data" / "raw_food_prices"
    target_dir = workspace_dir / "hero_v5" / "data"
    target_dir.mkdir(parents=True, exist_ok=True)
    
    csv_files = sorted(list(source_dir.glob("global_food_*.csv")))
    if not csv_files:
        logger.error(f"Nessun file CSV trovato in {source_dir}")
        return
        
    logger.info(f"Trovati {len(csv_files)} file CSV da consolidare.")
    
    # Colonne richieste
    required_cols = [
        'ISO3', 'country', 'adm1_name', 'adm2_name', 'mkt_name', 
        'lat', 'lon', 'year', 'month', 'c_food_price_index', 'inflation_food_price_index', 'geo_id'
    ]
    
    dfs = []
    for file_path in csv_files:
        logger.info(f"Elaborazione: {file_path.name}...")
        try:
            df = pd.read_csv(file_path, usecols=lambda c: c in required_cols, low_memory=False)
            
            missing = [c for c in required_cols if c not in df.columns]
            if missing:
                for m in missing:
                    df[m] = None
                    
            if 'year' in df.columns and 'month' in df.columns:
                valid_time = df['year'].notna() & df['month'].notna()
                df['date'] = pd.NaT
                df.loc[valid_time, 'date'] = pd.to_datetime(
                    df.loc[valid_time, 'year'].astype(int).astype(str) + '-' + 
                    df.loc[valid_time, 'month'].astype(int).astype(str) + '-01',
                    errors='coerce'
                )
            
            df = df[required_cols + ['date']]
            
            categorical_cols = ['ISO3', 'country', 'adm1_name', 'adm2_name', 'mkt_name']
            for col in categorical_cols:
                if col in df.columns:
                    df[col] = df[col].astype('category')
                    
            dfs.append(df)
            logger.info(f"  -> Righe caricate: {len(df):,}")
        except Exception as e:
            logger.error(f"Errore caricamento {file_path.name}: {e}")
            
    if not dfs:
        logger.error("Nessun dato caricato. Pipeline interrotta.")
        return
        
    logger.info("Concatenazione dataset...")
    df_total = pd.concat(dfs, ignore_index=True)
    df_total = df_total.rename(columns={
        'c_food_price_index': 'price',
        'inflation_food_price_index': 'inflation'
    })
    
    out_parquet = target_dir / "wfp_consolidate.parquet"
    logger.info(f"Salvataggio dataset consolidato in: {out_parquet}")
    df_total.to_parquet(out_parquet, engine='pyarrow', index=False)
    
    size_mb = out_parquet.stat().st_size / (1024 * 1024)
    logger.info("✨ CONSOLIDAMENTO WFP COMPLETATO CON SUCCESSO!")
    logger.info(f"   Shape: {df_total.shape[0]:,} righe x {df_total.shape[1]} colonne")
    logger.info(f"   Dimensione file: {size_mb:.2f} MB")
    logger.info("==================================================")

if __name__ == "__main__":
    main()
