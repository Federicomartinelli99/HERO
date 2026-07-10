# Checklist di Sviluppo - FASE 1: Preprocessing e Imputazione Spaziale

Questo documento contiene i dettagli implementativi e la checklist per la **Fase 1**. L'obiettivo è armonizzare le scale demografiche e ricostruire i valori mancanti dei driver usando la prossimità geografica.

---

## 📋 Task List

### `[ ]` Task 1.1: Normalizzazione e Armonizzazione Demografica
* **Descrizione**: Scalare i conteggi crudi dei driver per renderli comparabili tra province di dimensioni demografiche diverse.
* **Sotto-task**:
  * `[ ]` Caricare il dataset `merged_adm1_wide_knn.parquet` o `merged_adm1_wide.parquet`.
  * `[ ]` Calcolare le vittime e gli eventi ACLED ogni 100.000 abitanti:
    $$\text{acled\_events\_100k} = \frac{\text{acled\_events}}{\text{population}} \times 100.000$$
  * `[ ]` Calcolare la popolazione IDP come percentuale sulla popolazione totale:
    $$\text{idp\_percentage} = \frac{\text{idp\_population}}{\text{population}} \times 100$$
  * `[ ]` Gestire la staleness dei dati IDP: impostare a `NaN` le osservazioni IDP più vecchie di 400 giorni (`idp_staleness_days`).

---

### `[ ]` Task 1.2: Imputazione Spaziotemporale KNN (Geo-Similarity)
* **Descrizione**: Sviluppare e applicare la funzione di imputazione spaziale basata su KNN.
* **Firma della Funzione**:
  ```python
  def impute_missing_knn_geo_similarity(df, target_columns, lat_col='latitude', lon_col='longitude', n_neighbors=5):
      """
      Imputa i valori mancanti nelle colonne target usando KNN,
      utilizzando Latitudine e Longitudine come guida geometrica.
      """
  ```
* **Sotto-task**:
  * `[ ]` Verificare la presenza di coordinate: scartare temporaneamente le righe prive di latitudine/longitudine valide (non possono guidare l'imputazione spaziale).
  * `[ ]` Isolare le feature: creare una matrice contenente `[latitude, longitude] + target_columns`.
  * `[ ]` Standardizzare le feature (`StandardScaler`): passaggio obbligatorio prima del KNN per evitare che le scale geografiche dominino quelle dei driver.
  * `[ ]` Inizializzare `KNNImputer(n_neighbors=k, weights='distance')` adattando dinamicamente $k$ se il numero di righe disponibili è inferiore a $n\_neighbors$.
  * `[ ]` Eseguire il fit ed inverse transform, e reinserire i valori imputati nel DataFrame originale.

---

### `[ ]` Task 1.3: Diagnostica e Visualizzazione del Preprocessing
* **Descrizione**: Generare grafici di controllo per validare il comportamento dell'imputazione spaziale.
* **Sotto-task**:
  * `[ ]` Generare e salvare la **Missingness Heatmap** prima e dopo l'imputazione.
  * `[ ]` Tracciare i **KDE Plot** (Kernel Density Estimate) per ciascun driver per confrontare la distribuzione dei dati originali rispetto a quelli imputati (verificando che il KNN non abbia appiattito la varianza o alterato la forma della distribuzione).
  * `[ ]` Salvare tutti i grafici diagnostici nella cartella `ML/results/preprocessing/`.
