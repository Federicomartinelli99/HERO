# FASE 1: Preprocessing, Armonizzazione e Gestione del Dato Mancante

Il dataset unificato unisce fonti altamente eterogenee (IPC, ACLED, WFP, GDELT, NDVI, Rainfall). La sfida principale risiede nella presenza di missing values e nelle differenti scale delle variabili.

---

## 1. Normalizzazione e Armonizzazione Geografica (KDD Workflow)
* **Standardizzazione dei Driver**: Per evitare sbilanciamenti causati dalla dimensione demografica dei territori, le variabili di conflitto (ACLED - eventi e vittime) e di migrazione interna (IDP - sfollati) verranno normalizzate per **100.000 abitanti** (calcolate sulla popolazione totale dell'area).
* **Conversione IDP**: La popolazione IDP sarà espressa anche come percentuale sulla popolazione totale dell'area per rappresentare la densità dello shock.
* **Tipi di Dati**: Ottimizzazione del consumo di memoria (conversione in `float32` per le percentuali, `category` per i codici geografici).

---

## 2. Gestione dei Dati Mancanti (KNN Imputation vs Baseline)
* **Algoritmo `impute_missing_knn_geo_similarity`**:
  * Sfrutta l'algoritmo KNN Imputer (`sklearn.impute.KNNImputer`) inserendo le coordinate spaziali (`latitude` e `longitude` standardizzate) direttamente nel calcolo delle distanze.
  * **Razionale**: Le aree geograficamente contigue tendono a condividere profili climatici e dinamiche economiche simili. Includere le coordinate guida la ricerca dei "vicini" più simili, migliorando l'accuratezza dei valori imputati.
  * **Sicurezze**: Gestione automatica delle colonne interamente nulle a livello di singolo gruppo (evitando crash del codice) e riduzione dinamica del numero di vicini (`n_neighbors`) in caso di campioni insufficienti.
* **Confronto Sperimentale**: Il dataset imputato spazialmente verrà confrontato con un dataset grezzo (dove i modelli come XGBoost gestiranno i valori mancanti in autonomia) per valutare se l'imputazione spaziale migliora l'inferenza finale o introduce rumore.

---

## 📊 Grafici e Visualizzazioni per la FASE 1
* **Missingness Heatmap (Prima vs Dopo)**: Mappa di calore bidimensionale (regioni vs feature) che mostra graficamente in nero i dati mancanti prima del preprocessing e in bianco il dataset completamente popolato dopo il KNN spaziale.
* **Density plots di Controllo (Originale vs Imputato)**: Grafici a curve di densità sovrapposte (KDE Plot) per ciascun driver (es. piogge, inflazione). Consente di verificare visivamente che la distribuzione probabilistica del dato imputato con KNN non presenti distorsioni o shift sistematici rispetto alla distribuzione dei dati reali osservati.
* **Mappa Spaziale delle Imputazioni**: Mappa geografica con marker colorati per evidenziare le regioni in cui è stato necessario ricorrere all'imputazione (e l'intensità/percentuale dei dati ricostruiti).
