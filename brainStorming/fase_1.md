# FASE 1: Preprocessing, Armonizzazione e Gestione del Dato Mancante

Il dataset unificato unisce fonti altamente eterogenee (IPC, ACLED, WFP, GDELT, NDVI, Rainfall). La sfida principale risiede nella presenza di missing values e nelle differenti scale delle variabili.

---

## 1. Normalizzazione e Armonizzazione Geografica e Temporale (KDD Workflow)
* **Standardizzazione dei Driver**: Per evitare sbilanciamenti causati dalla dimensione demografica dei territori, le variabili di conflitto (ACLED - eventi e vittime) e di migrazione interna (IDP - sfollati) verranno normalizzate per **100.000 abitanti** (calcolate sulla popolazione totale dell'area).
* **Conversione IDP**: La popolazione IDP sarà espressa anche come percentuale sulla popolazione totale dell'area per rappresentare la densità dello shock.
* **Tipi di Dati**: Ottimizzazione del consumo di memoria (conversione in `float32` per le percentuali, `category` per i codici geografici).
* **Preservazione della Risoluzione Temporale Nativa**: 
  * Il riallineamento temporale su griglia mensile uniforme (`MS`) è vincolante **solo** per le analisi e i modelli predittivi che richiedono il join diretto con la spina dorsale del target IPC.
  * Per tutti gli studi di tipo autonomo o indipendente (ad esempio l'analisi di rete dei mercati alimentari o l'anomaly detection sui prezzi e precipitazioni), **si deve mantenere la risoluzione temporale nativa non aggregata** (es. settimanale o giornaliera dei prezzi WFP, o pentadica/decalica per dati climatici) al fine di non disperdere la ricchezza informativa e catturare con massima precisione i lag temporali a breve termine e la propagazione rapida degli shock.

---

## 2. Gestione dei Dati Mancanti e Ricostruzione delle Serie Storiche
La ricostruzione dei dati mancanti, in particolare per la serie storica dell'IPC, adotta due logiche complementari:

### A. Ricostruzione delle Serie Storiche IPC su Base Nazionale (Country-Bounded Reconstruction)
* **Logica**: Per colmare buchi temporali o ricostruire intere serie storiche dell'IPC in province povere di dati, si utilizzano le serie temporali delle altre province appartenenti allo **stesso paese**. Gli shock macroeconomici, le risposte politiche e i cicli stagionali sono fortemente coesi all'interno dei confini nazionali.
* **Metodologia**: La ricostruzione opera separando i dati per nazione (`groupby('Country')`). Se una provincia A presenta valori IPC mancanti in determinati mesi, questi vengono ricostruiti come combinazione lineare o spaziale pesata (tramite distanza geometrica o correlazione storica delle serie) delle serie delle altre province del medesimo paese che possiedono dati completi in quegli stessi mesi. Questo garantisce la coerenza macro-regionale dei dati stimati.

### B. Algoritmo `impute_missing_knn_geo_similarity`
* **Logica**: Sfrutta l'algoritmo KNN Imputer (`sklearn.impute.KNNImputer`) inserendo le coordinate spaziali (`latitude` e `longitude` standardizzate) direttamente nel calcolo delle distanze.
* **Razionale**: Le aree geograficamente contigue tendono a condividere profili climatici e dinamiche economiche simili. Includere le coordinate guida la ricerca dei "vicini" più simili, migliorando l'accuratezza dei valori imputati.
* **Sicurezze**: Gestione automatica delle colonne interamente nulle a livello di singolo gruppo (evitando crash del codice) e riduzione dinamica del numero di vicini (`n_neighbors`) in caso di campioni insufficienti.

---

## 📊 Grafici e Visualizzazioni per la FASE 1
* **Missingness Heatmap (Prima vs Dopo)**: Mappa di calore bidimensionale (regioni vs feature) che mostra graficamente in nero i dati mancanti prima del preprocessing e in bianco il dataset completamente popolato dopo il KNN spaziale.
* **Density plots di Controllo (Originale vs Imputato)**: Grafici a curve di densità sovrapposte (KDE Plot) per ciascun driver (es. piogge, inflazione). Consente di verificare visivamente che la distribuzione probabilistica del dato imputato con KNN non presenti distorsioni o shift sistematici rispetto alla distribuzione dei dati reali osservati.
* **Mappa Spaziale delle Imputazioni**: Mappa geografica con marker colorati per evidenziare le regioni in cui è stato necessario ricorrere all'imputazione (e l'intensità/percentuale dei dati ricostruiti).

---
### C.Definzione algoritmo per la gestione dei dati mancanti

Usare diverse metriche per la scelta dell'agoritmo giusto.

