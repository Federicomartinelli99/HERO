# Documentazione Aggregazione Mensile WFP (Indici di Mercato)

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
