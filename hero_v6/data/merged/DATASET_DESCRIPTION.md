# Descrizione Dettagliata del Dataset HERO v6

Questo documento fornisce una descrizione approfondita dei dataset pronti per l'uso contenuti nella cartella `hero_v6/data/merged/`. Questi dataset costituiscono la base su cui sono stati sviluppati i moduli di **Time Series Analysis (TSA)** e il modulo di **Machine Learning (ML)** per il clustering e la predizione dell'insicurezza alimentare.

---

## 1. Filosofia del Dataset & Struttura Core

La spina dorsale (spine) di tutto il dataset è rappresentata dai dati **IPC (Integrated Food Security Phase Classification)**. 
Tutte le altre fonti informative (conflitti ACLED, sfollati IDP, dati climatici Rainfall/NDVI, prezzi dei mercati WFP e segnali media GDELT) sono state collegate tramite **Left Join** sulla spalla temporale e geografica dell'IPC. Ciò significa che:
* Il set di righe finale corrisponde esattamente a quello delle valutazioni ufficiali IPC.
* Eventuali dati mancanti da fonti secondarie sono rappresentati da valori `NaN` (null), senza causare la perdita o la cancellazione della riga IPC originaria.

### I File di Dati Disponibili in `data/merged/`

1. **`merged_adm1_wide.parquet`**:
   * **Granularità**: Una riga per ciascuna provincia (Admin Level 1) e per ciascun periodo di validità IPC.
   * **Righe**: ~10.024
   * **Uso principale**: Analisi regionali aggregate, clustering globale e integrazione con GDELT (disponibile solo a questo livello).
2. **`merged_adm1_wide_con_coordinate.parquet`**:
   * Uguale a `merged_adm1_wide.parquet` ma con l'aggiunta delle colonne finali `latitude` e `longitude` che indicano le coordinate del centroide geografico di ciascuna provincia.
3. **`merged_adm1_wide_knn.parquet`**:
   * Uguale a `merged_adm1_wide.parquet` ma con l'imputazione dei dati mancanti effettuata tramite l'algoritmo KNN Imputer.
4. **`merged_adm2_wide.parquet`**:
   * **Granularità**: Una riga per ciascun distretto/dipartimento (Admin Level 2) e per ciascun periodo di validità IPC.
   * **Righe**: ~42.957
   * **Uso principale**: Analisi locale ad altissima risoluzione geografica (le variabili GDELT non sono presenti in quanto native del livello Admin 1).

---

## 2. Dettaglio delle Colonne e Variabili

Il dataset in formato "wide" organizza i dati raccogliendo le informazioni in gruppi tematici:

### A. Colonne di Identificazione (Metadata)
Identificano geograficamente e temporalmente la riga del dataset:
* **`Country`**: Codice ISO3 dello Stato (es. `AFG` per l'Afghanistan, `SDN` per il Sudan). Sono presenti 48-52 paesi totali.
* **`location_name_full`**: Nome completo dello Stato.
* **`Level 1`**: Nome della provincia (Admin 1, es. `Kabul`).
* **`Area`**: Nome del distretto (Admin 2, es. `Deh Sabz`, solo nel file `adm2`).
* **`adm1_pcode` / `adm2_pcode`**: Codici geografici standardizzati (P-Codes) rilasciati da OCHA per l'identificazione univoca dei territori.
* **`From` / `To`**: Date di inizio e fine validità del periodo di analisi IPC (tipicamente un intervallo di 3-6 mesi).
* **`Validity period`**: Indica il tipo di analisi:
  * `current`: La valutazione della situazione attuale al momento dell'analisi.
  * `first projection` / `second projection`: Proiezioni future a medio termine elaborate dagli analisti.
* **`Date of analysis`**: Data di rilascio/pubblicazione del report IPC.
* **`admin_level`**: Valore intero (`1` o `2`) indicante il livello amministrativo.

### B. Variabili IPC (Target)
Misurano il livello di insicurezza alimentare della popolazione. Per ciascuna fase sono presenti sia il numero assoluto di persone (`_number`) sia la percentuale sulla popolazione totale del territorio (`_percentage`):
* **Fase 1 (`phase_1_...`)**: *Minima/Nessuna* insicurezza (le famiglie soddisfano i bisogni alimentari essenziali).
* **Fase 2 (`phase_2_...`)**: *Marginale* (le famiglie hanno un consumo alimentare minimamente adeguato).
* **Fase 3 (`phase_3_...`)**: *Crisi* (elevati tassi di malnutrizione acuta o grave esaurimento degli asset).
* **Fase 4 (`phase_4_...`)**: *Emergenza* (tassi di malnutrizione acuta estremamente elevati e mortalità eccessiva).
* **Fase 5 (`phase_5_...`)**: *Carestia/Catastrofe* (indigenza estrema, fame e mortalità critica).
* **Fase 3+ (`phase_3plus_...`)**: La somma delle Fasi 3, 4 e 5. **Questa è la variabile target standard (espressa in percentuale o numero)** utilizzata nei modelli predittivi e nel clustering per monitorare la gravità della crisi.
* **Fase All (`phase_all_...`)**: Popolazione totale analizzata.

### C. Conflitti (ACLED)
Aggregati calcolando la somma degli eventi e delle vittime avvenuti nel territorio nel corso dell'intervallo temporale IPC (`From` - `To`):
* **`acled_political_violence_events` / `_fatalities`**: Scontri armati, esplosioni, attacchi di milizie.
* **`acled_civilian_targeting_events` / `_fatalities`**: Violenze mirate contro civili inermi.
* **`acled_demonstration_events` / `_fatalities`**: Proteste, sommosse e manifestazioni pubbliche.
* **`acled_total_events` / `_fatalities`**: Somma totale di tutti gli eventi di conflitto e relative vittime.

### D. Sfollati Interni (IDP)
Variabili relative alla popolazione di sfollati interni (dati stock):
* **`idp_population`**: Numero stimato di sfollati interni nel territorio (preso dall'ultimo report disponibile prima della data di fine dell'IPC `To`).
* **`idp_staleness_days`**: Indica quanti giorni prima del periodo IPC è stato registrato il dato IDP (se superiore a 400 giorni, il dato viene considerato troppo vecchio e scartato).
* **`idp_assessment_type`**: Metodologia di rilevamento dello sfollamento.

### E. Dati Climatici (Rainfall & NDVI)
Indicatori meteoclimatici e vegetazionali per catturare shock agricoli o siccità:
* **`rain_1m_sum`**: Somma delle precipitazioni accumulate (in mm) nel periodo IPC.
* **`rain_1m` / `rain_3m`**: Media delle precipitazioni mensili a 1 e 3 mesi.
* **`rain_anomaly_1m` / `rain_anomaly_3m`**: Scostamento (anomalia) della pioggia rispetto alla media storica del periodo.
* **`ndvi_vim`**: Indice di vigore vegetazionale medio (greenness) calcolato tramite immagini satellitari e pesato sui pixel agricoli.
* **`ndvi_viq`**: Indice di qualità della vegetazione (anomalia rispetto alla norma, utile per rilevare siccità agricole).

### F. Prezzi dei Mercati Alimentari (WFP)
Calcolati estraendo le medie dei prezzi dei beni alimentari di base monitorati dal World Food Programme nel corso del periodo IPC:
* **`wfp_price`**: Indice del livello medio dei prezzi alimentari.
* **`wfp_inflation`**: Indice dell'inflazione dei prezzi alimentari calcolata su base annua.
* **`wfp_obs_count`**: Numero di mercati/osservazioni fisiche incluse nel calcolo.
* **`wfp_mapping_method`**: Metodo di associazione spaziale (`strict_pip` o `elastic_buffer`).

### G. Segnali Media Nazionali/Internazionali (GDELT - Solo ADM1)
Analisi automatica delle notizie giornalistiche classificate secondo la tassonomia CAMEO e aggregate in 4 categorie (QuadClasses). I conteggi sono sommati sul periodo IPC, mentre il tono è una media pesata sulle menzioni:
* **`gdelt_verbal_coop_events` / `_mentions` / `_tone`**: Cooperazione verbale (dichiarazioni, accordi di principio).
* **`gdelt_material_coop_events` / `_mentions` / `_tone`**: Cooperazione materiale (aiuti economici, supporto militare effettivo).
* **`gdelt_verbal_conflict_events` / `_mentions` / `_tone`**: Conflitto verbale (accuse, minacce, sanzioni verbali).
* **`gdelt_material_conflict_events` / `_mentions` / `_tone`**: Conflitto materiale (scontri, sanzioni economiche, espulsioni diplomatiche).

---

## 3. Utilizzo dei Dati in TSA & ML

La pipeline **TSA (Time Series Analysis)** e gli script in **ML (Machine Learning)** preparano e manipolano questi file Parquet secondo le seguenti metodologie:

1. **Riallineamento Mensile Uniforme**:
   Poiché le valutazioni IPC avvengono solo poche volte l'anno e coprono intervalli di vari mesi, le date `From` e `To` vengono espanse su un asse temporale mensile uniforme (`MS` - Month Start). I mesi sovrapposti vengono aggregati tramite media ed i valori intermedi vengono riempiti tramite interpolazione lineare e trascinamento dei bordi (`ffill`/`bfill`), in modo da generare una serie storica continua ed equispaziata adatta per l'analisi autoregressiva e di similarità shape-based.
2. **Estrazione delle Feature Strutturali**:
   Per ciascuna serie storica consolidata, vengono estratti 9 descrittori statici:
   * **Momenti Statistici**: Media, varianza, skewness (asimmetria) e kurtosis (spessore delle code).
   * **Memoria a Lungo Termine**: Esponente di Hurst ($H$).
   * **Regolarità/Caos**: Entropia Approssimata (ApEn).
   * **Memoria a Breve Termine**: I primi 3 coefficienti autoregressivi AR(1), AR(2) e AR(3) calcolati standardizzando la serie storica.
3. **Analisi Spaziale (Coordinates)**:
   Nei modelli di clustering spazialmente vincolati, le coordinate `latitude` e `longitude` del centroide (ricavate dal file `_con_coordinate.parquet`) vengono standardizzate ed integrate nel vettore delle feature strutturali, forzando la coesione geografica dei cluster risultanti.
