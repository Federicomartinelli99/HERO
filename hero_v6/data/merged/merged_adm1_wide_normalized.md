# Relazione Tecnica e Documentazione del Notebook di Analisi Dati

## 1. Sintesi Esecutiva
Il notebook analizza, pulisce e normalizza indicatori socio-politici e demografici a livello regionale (**Admin 1**). Il workflow unisce dati sui conflitti e sugli sfollati interni (IDP) con dati demografici per calcolare metriche relative (per 100.000 abitanti o percentuali). L'obiettivo finale è la standardizzazione dei driver di vulnerabilità per consentire confronti geografici coerenti.

---

## 2. Architettura della Pipeline dei Dati

La pipeline si articola in quattro macro-fasi sequenziali:
1. **Ingestione Dati:** Caricamento di un file in formato Parquet (`merged_adm1_wide.parquet`) contenente metriche storiche e conflittuali (GDELT, ACLED) e di un file CSV (`population_admin1.csv`) contenente i dati demografici di riferimento.
2. **Allineamento e Fusione (Merging):** Ridenominazione delle chiavi di giunzione per garantire la coerenza dei metadati (`ADM1_PCODE` $ightarrow$ `adm1_pcode`) ed esecuzione di un `inner merge`.
3. **Data Cleaning e Conversione di Tipo:** Trattamento della colonna demografica per rimuovere anomalie di formattazione stringa e successivo casting a tipo intero.
4. **Ingegneria delle Feature (Normalizzazione):** Calcolo di nuovi indicatori pesati sulla popolazione per eliminare la distorsione causata dalla dimensione demografica delle diverse aree regionali.
5. **Esportazione:** Salvataggio dei dati trasformati in un nuovo file Parquet.

---

## 3. Analisi Dettagliata delle Fasi Logiche

### Fase 1: Caricamento dei Dataset
* **Codice sorgente:**
  ```python
  import pandas as pd
  merged_adm1_wide = pd.read_parquet("merged_adm1_wide.parquet")
  population_admin1 = pd.read_csv('../raw/population_admin1.csv', sep=',', na_values=[''], quotechar='"')
  ```
* **Dettaglio:** Il dataset principale è composto da 10.024 righe e 62 colonne, indicando una struttura informativa complessa (wide format) che include serie temporali o proiezioni (`Validity period`, `Date of analysis`). Il dataset della popolazione contiene 769 record mappati per codice regionale.

### Fase 2: Ridenominazione e Giunzione
* **Codice sorgente:**
  ```python
  population_admin1 = population_admin1.rename(columns={'ADM1_PCODE': 'adm1_pcode'})
  merged_adm1_wide = pd.merge(merged_adm1_wide, population_admin1[["adm1_pcode","Population"]], on='adm1_pcode', how="inner")
  ```
* **Dettaglio:** L'adozione di una giunzione di tipo `inner` riduce il dataset principale da 10.024 a 8.872 righe. Questo implica che il 11.5% dei record originari è stato rimosso a causa della mancanza di un codice di corrispondenza (`adm1_pcode`) nel dataset demografico.

### Fase 3: Pulizia della Feature Demografica
* **Codice sorgente:**
  ```python
  merged_adm1_wide = merged_adm1_wide.rename(columns={'Population':'adm1_population'})
  merged_adm1_wide["adm1_population"] = merged_adm1_wide["adm1_population"].str.replace(".", "", regex=False)
  merged_adm1_wide["adm1_population"] = merged_adm1_wide["adm1_population"].astype("int")
  ```
* **Dettaglio:** La feature `Population` è stata inizialmente letta come stringa (object) a causa della presenza di separatori di migliaia o decimali. Il codice esegue la rimozione del punto. 

### Fase 4: Calcolo degli Indicatori Normalizzati
Il notebook implementa le seguenti formule matematiche per la creazione delle nuove feature:

1. **Eventi di Violenza Politica ACLED per 100k abitanti:**
   $$	ext{acled\_political\_violence\_events\_per\_100k} = rac{	ext{acled\_political\_violence\_events}}{	ext{adm1\_population}} 	imes 100.000$$

2. **Fatalità Totali ACLED per 100k abitanti:**
   $$	ext{acled\_total\_fatalities\_per\_100k} = rac{	ext{acled\_total\_fatalities}}{	ext{adm1\_population}} 	imes 100.000$$

3. **Incidenza della Popolazione Sfolla (IDP Ratio):**
   $$	ext{idp\_population\_over\_adm1\_population} = rac{	ext{idp\_population}}{	ext{adm1\_population}}$$

4. **Rapporto Sfollati su Fasi di Vulnerabilità Alimentare:**
   $$	ext{idp\_population\_over\_phase\_all\_number} = rac{	ext{idp\_population}}{	ext{phase\_all\_number}}$$

### Fase 5: Serializzazione
* **Codice sorgente:**
  ```python
  merged_adm1_wide.to_parquet("merged_adm1_wide_normalized.parquet")
  ```

---

## 4. Analisi Critica dei Difetti e Vulnerabilità del Codice

L'analisi del notebook evidenzia anomalie severe che compromettono l'integrità del dato e l'affidabilità scientifica dell'output:

### A. Il Bug della Scala Demografica (Critico)
* **Evidenza dall'output della cella 6:** La popolazione per il record 0 viene stampata come `5995339.056`.
* **Meccanismo del bug:** L'istruzione `str.replace(".", "", regex=False)` trasforma la stringa `"5995339.056"` in `"5995339056"`. Successivamente, il casting ad intero memorizza una popolazione di **5,9 miliardi** di abitanti per una singola regione dell'Afghanistan (Kabul), moltiplicando il valore reale per 1.000.
* **Impatto:** Tutte le metriche calcolate successivamente risultano sottostimate di un fattore 1.000. Gli eventi per 100k abitanti risultano infinitesimali (`0.001718`) anziché riflettere il valore reale (`1.718`).

### B. Esecuzione Fuori Concorrenza e Asincrona (Logico)
* **Meccanismo del bug:** La cella di esportazione `to_parquet` ha come `execution_count: 14`, mentre il calcolo della colonna `idp_population_over_phase_all_number` ha come `execution_count: 13`. Tuttavia, guardando l'ordine lineare del notebook, la cella di export si trova *sopra* la cella di calcolo della metrica.
* **Impatto:** Se il notebook viene eseguito in modalità lineare ed automatizzata dall'alto verso il basso (es. tramite papermill o riesecuzione del kernel), l'esportazione avverrà *prima* della creazione dell'ultima colonna, generando un file Parquet privo della feature `idp_population_over_phase_all_number`.

### C. Mancanza di Gestione dei Valori Nulli (NaN)
* **Evidenza:** Gli output mostrano la presenza diffusa di valori `NaN` nelle colonne calcolate (es. record 8867-8871).
* **Impatto:** La divisione per zero o l'operazione su valori mancanti nelle colonne ACLED o IPC (`phase_all_number`) non viene intercettata, propagando i record nulli senza una strategia di imputazione o di mascheramento.
