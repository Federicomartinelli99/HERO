import os
import pandas as pd
from pathlib import Path
from libs.logger_config import get_logger

logger = get_logger("wfp_to_parquet")

def convert_csv_to_parquet():
    base_dir = Path(__file__).resolve().parent.parent
    source_dir = base_dir / "data" / "raw_food_prices"
    target_dir = base_dir / "data" / "parquet_file"
    target_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Ricerca CSV in: {source_dir}")
    csv_files = sorted(list(source_dir.glob("global_food_*.csv")))
    
    if not csv_files:
        logger.error("Nessun CSV trovato!")
        return
        
    dfs = []
    categorical_cols = ['ISO3', 'country', 'adm1_name', 'adm2_name', 'mkt_name', 'currency']
    
    for file_path in csv_files:
        logger.info(f"Elaborazione: {file_path.name}")
        try:
            df = pd.read_csv(file_path, low_memory=False)
        except Exception as e:
            logger.error(f"Errore lettura {file_path.name}: {e}")
            continue
        
        if 'year' in df.columns and 'month' in df.columns:
            valid_time = df['year'].notna() & df['month'].notna()
            df['date'] = pd.NaT
            df.loc[valid_time, 'date'] = pd.to_datetime(
                df.loc[valid_time, 'year'].astype(int).astype(str) + '-' + 
                df.loc[valid_time, 'month'].astype(int).astype(str) + '-01',
                errors='coerce'
            )
        
        for col in categorical_cols:
            if col in df.columns: df[col] = df[col].astype('category')
                
        dfs.append(df)
        
    logger.info(f"Concatenazione di {len(dfs)} file in corso...")
    df_total = pd.concat(dfs, ignore_index=True)
    
    output_file = target_dir / "wfp_consolidated.parquet"
    logger.info("Salvataggio Parquet... (richiede qualche secondo)")
    
    df_total.to_parquet(output_file, engine='pyarrow', index=False)
    file_size = output_file.stat().st_size / (1024 * 1024)
    logger.info(f"✨ Completato! File generato: {output_file.name} ({file_size:.2f} MB)")

if __name__ == "__main__":
    convert_csv_to_parquet()
