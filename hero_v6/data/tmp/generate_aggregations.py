import os
import pandas as pd
from pathlib import Path

def main():
    # Paths
    base_dir = Path("c:/Dev/Progetti/HERO/hero_v6")
    raw_wfp_path = base_dir / "data" / "raw" / "wfp_with_pcodes.parquet"
    tmp_dir = base_dir / "data" / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Reading raw WFP data from {raw_wfp_path}...")
    df = pd.read_parquet(raw_wfp_path, engine="pyarrow")
    
    # Ensure date is datetime
    df["date"] = pd.to_datetime(df["date"])
    
    # --- ADMIN 1 AGGREGATION ---
    print("Performing Admin1 aggregation...")
    # Filter out unmapped/null pcodes at Admin1
    df_adm1 = df[df["adm1_pcode"].notna() & (df["mapping_method_adm1"] != "unmapped")].copy()
    
    # Group by ISO3, country, adm1_pcode, adm1_name, and the monthly time index
    group_cols_adm1 = ["ISO3", "country", "adm1_pcode", "adm1_name", "year", "month", "date"]
    for col in ["ISO3", "country", "adm1_pcode", "adm1_name"]:
        df_adm1[col] = df_adm1[col].astype(str)
        
    adm1_agg = (
        df_adm1.groupby(group_cols_adm1, as_index=False)
        .agg(
            wfp_price_mean=("price", "mean"),
            wfp_inflation_mean=("inflation", "mean"),
            wfp_market_count=("price", "count")
        )
    )
    
    # Sort for time-series convenience
    adm1_agg = adm1_agg.sort_values(by=["ISO3", "adm1_pcode", "date"]).reset_index(drop=True)
    
    # Save as Parquet and CSV for convenience
    adm1_parquet_path = tmp_dir / "wfp_monthly_adm1_index.parquet"
    adm1_csv_path = tmp_dir / "wfp_monthly_adm1_index.csv"
    
    print(f"Saving Admin1 aggregated data to {adm1_parquet_path} and {adm1_csv_path}...")
    adm1_agg.to_parquet(adm1_parquet_path, index=False)
    adm1_agg.to_csv(adm1_csv_path, index=False)
    
    # --- ADMIN 2 AGGREGATION ---
    print("Performing Admin2 aggregation...")
    # Filter out unmapped/null pcodes at Admin2
    df_adm2 = df[df["adm2_pcode"].notna() & (df["mapping_method_adm2"] != "unmapped")].copy()
    
    group_cols_adm2 = ["ISO3", "country", "adm1_pcode", "adm1_name", "adm2_pcode", "adm2_name", "year", "month", "date"]
    for col in ["ISO3", "country", "adm1_pcode", "adm1_name", "adm2_pcode", "adm2_name"]:
        df_adm2[col] = df_adm2[col].astype(str)
        
    adm2_agg = (
        df_adm2.groupby(group_cols_adm2, as_index=False)
        .agg(
            wfp_price_mean=("price", "mean"),
            wfp_inflation_mean=("inflation", "mean"),
            wfp_market_count=("price", "count")
        )
    )
    
    # Sort for time-series convenience
    adm2_agg = adm2_agg.sort_values(by=["ISO3", "adm1_pcode", "adm2_pcode", "date"]).reset_index(drop=True)
    
    # Save as Parquet and CSV for convenience
    adm2_parquet_path = tmp_dir / "wfp_monthly_adm2_index.parquet"
    adm2_csv_path = tmp_dir / "wfp_monthly_adm2_index.csv"
    
    print(f"Saving Admin2 aggregated data to {adm2_parquet_path} and {adm2_csv_path}...")
    adm2_agg.to_parquet(adm2_parquet_path, index=False)
    adm2_agg.to_csv(adm2_csv_path, index=False)
    
    print("Generating doc.md...")
    doc_content = """# Documentazione Aggregazione Mensile WFP (Indici di Mercato)

Questo documento spiega come sono stati generati i file di aggregazione mensili del World Food Programme (WFP) e i motivi di tale scelta metodologica.

## File Creati
Nella cartella [hero_v6/data/tmp](file:///c:/Dev/Progetti/HERO/hero_v6/data/tmp) sono stati generati quattro file (in formato Parquet e CSV per massima flessibilità):
1. **Admin 1**:
   - Parquet: [wfp_monthly_adm1_index.parquet](file:///c:/Dev/Progetti/HERO/hero_v6/data/tmp/wfp_monthly_adm1_index.parquet)
   - CSV: [wfp_monthly_adm1_index.csv](file:///c:/Dev/Progetti/HERO/hero_v6/data/tmp/wfp_monthly_adm1_index.csv)
2. **Admin 2**:
   - Parquet: [wfp_monthly_adm2_index.parquet](file:///c:/Dev/Progetti/HERO/hero_v6/data/tmp/wfp_monthly_adm2_index.parquet)
   - CSV: [wfp_monthly_adm2_index.csv](file:///c:/Dev/Progetti/HERO/hero_v6/data/tmp/wfp_monthly_adm2_index.csv)

## Metodologia di Creazione
I file sono stati creati a partire dal dataset raw consolidato `data/raw/wfp_with_pcodes.parquet` seguendo questi passaggi:

1. **Filtraggio Geografico**:
   - Per l'aggregazione a livello **Admin 1**, sono stati esclusi i record con `adm1_pcode` nullo o con metodo di mappatura spaziale pari a `"unmapped"`.
   - Per l'aggregazione a livello **Admin 2**, sono stati esclusi i record con `adm2_pcode` nullo o con metodo di mappatura spaziale pari a `"unmapped"`.
2. **Aggregazione Spaziale**:
   - I dati di prezzo (`price`) e inflazione (`inflation`) sono stati raggruppati spazialmente per area amministrativa e per data (`year`, `month`, `date`).
   - È stata calcolata la media semplice dei prezzi e dell'inflazione di tutti i mercati fisici monitorati all'interno della stessa area.
   - È stata tenuta traccia del numero di mercati attivi (`wfp_market_count`) per consentire di verificare la robustezza del dato aggregato.
3. **Mantenimento Frequenza Temporale**:
   - La risoluzione temporale originaria mensile è stata preservata per ciascuna area amministrativa, mantenendo la colonna `date` (fissata al 1° del mese, es. `YYYY-MM-01`).

## Motivazioni e Studi sulle Time Series
- **Preservazione della dinamica temporale**: L'aggregazione a livello quadrimestrale dei dati IPC nasconde fluttuazioni mensili rapide che possono caratterizzare i mercati finanziari ed alimentari. Mantenendo la risoluzione mensile, è possibile applicare modelli ARIMA/SARIMAX, LSTM o Prophet per analizzare trend stagionali o shock di breve termine nei prezzi e nell'inflazione.
- **Confronto con IPC**: Per effettuare confronti diretti con le finestre IPC (`From` -> `To`), l'utente dovrà ridurre la frequenza temporale mensile dei prezzi mediando le osservazioni che cadono all'interno dei periodi di validità IPC (operazione di *downsampling* temporale o allineamento a intervallo).
"""
    
    with open(tmp_dir / "doc.md", "w", encoding="utf-8") as f:
        f.write(doc_content)
    
    print("Done!")

if __name__ == "__main__":
    main()
