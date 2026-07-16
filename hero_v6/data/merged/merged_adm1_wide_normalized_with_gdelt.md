# Analisi del Flusso di Lavoro del Notebook

Questo documento descrive i passaggi eseguiti nel notebook fornito per l'elaborazione e la normalizzazione dei dati.

## 1. Caricamento dei Dati
- Importazione della libreria `pandas`.
- Caricamento del dataset principale da formato Parquet: `merged_adm1_wide.parquet` [cite: 1].
- Caricamento dei dati di popolazione da CSV: `../raw/population_admin1.csv` [cite: 1].

## 2. Preparazione e Merge
- Rinominata la colonna `ADM1_PCODE` in `adm1_pcode` nel dataset della popolazione per garantire coerenza nell'unione [cite: 1].
- Eseguito un `inner join` tra il dataset principale e i dati di popolazione utilizzando la chiave `adm1_pcode` [cite: 1].
- Rinominata la colonna fusa `Population` in `adm1_population` [cite: 1].
- Pulizia del dato di popolazione: rimozione del carattere separatore `.` e conversione del tipo di dato nel formato intero nullable di Pandas (`Int64`) per gestire nativamente eventuali valori mancanti (NaN) senza compromettere le prestazioni [cite: 1].

## 3. Calcolo delle Metriche Normalizzate (ACLED e IDP)
Sono stati generati i seguenti indicatori normalizzati:
- **Eventi di violenza politica ACLED**: Calcolati per 100.000 abitanti `(acled_political_violence_events / adm1_population) * 100_000` [cite: 1].
- **Vittime ACLED totali**: Calcolate per 100.000 abitanti `(acled_total_fatalities / adm1_population) * 100_000` [cite: 1].
- **Popolazione IDP (Sfollati Interni)**: Calcolata come frazione (percentuale) della popolazione totale `idp_population / adm1_population` [cite: 1].

## 4. Normalizzazione Massiva delle Variabili GDELT
- Identificazione automatica delle colonne relative a GDELT filtrando quelle che contengono la stringa `"gdelt"` ed escludendo quelle relative al tono (`"tone"`) [cite: 1]. Le variabili identificate includono eventi e menzioni di cooperazione e conflitto (sia verbali che materiali) [cite: 1].
- Iterazione sulle variabili estratte per calcolare le relative metriche per 100.000 abitanti, generando nuove feature con suffisso `_per_100k_population` [cite: 1].

## 5. Esportazione
- Salvataggio del dataset finale arricchito in un nuovo file Parquet denominato `merged_adm1_wide_normalized.parquet` [cite: 1].
