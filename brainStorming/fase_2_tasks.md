# Checklist di Sviluppo - FASE 2: Approccio Statico (Cross-Sectional)

Questo documento contiene i dettagli implementativi e la checklist per la **Fase 2**. L'obiettivo è stabilire una baseline predittiva e descrittiva analizzando i dati in logica "cross-section" (senza memoria temporale).

---

## 📋 Task List

### `[ ]` Task 2.1: Clustering Statico dei Paesi (EDA Descrittiva)
* **Descrizione**: Raggruppare i paesi in base alla magnitudo media dei loro driver di crisi storici.
* **Sotto-task**:
  * `[ ]` Aggregare il dataset calcolando la media storica di tutti i driver normalizzati (ACLED, IDP, Rainfall, NDVI, WFP) per ciascun paese.
  * `[ ]` Standardizzare la matrice risultante.
  * `[ ]` Applicare **Hierarchical Clustering** (legame Ward) per generare il dendrogramma dei paesi.
  * `[ ]` Applicare **K-Means** (e determinare il numero ottimale di cluster con il metodo del gomito / Silhouette Score).
  * `[ ]` Generare una heatmap ordinata secondo i cluster ottenuti (paesi sulle righe, driver sulle colonne) per visualizzare i pattern di crisi (es. paesi guidati da conflitto vs paesi guidati da siccità).

---

### `[ ]` Task 2.2: Inferenza Statica su IPC3+ (Classificazione e Regressione)
* **Descrizione**: Addestrare modelli supervisionati per stimare il target `phase_3plus_percentage` usando solo i valori istantanei correnti dei driver.
* **Sotto-task**:
  * `[ ]` Suddividere i dati in Train e Test set in modo stratificato o geografico (per evitare data leakage spaziale).
  * `[ ]` Configurare e addestrare i seguenti modelli:
    * `[ ]` K-Nearest Neighbors (KNN Regressor)
    * `[ ]` Decision Tree Regressor
    * `[ ]` Random Forest Regressor
    * `[ ]` XGBoost / LightGBM Regressor
  * `[ ]` Includere `latitude` e `longitude` standardizzate nel set di feature e valutarne l'effetto sulle performance.
  * `[ ]` Calcolare le metriche di accuratezza (MAE, RMSE, $R^2$) sul test set.

---

### `[ ]` Task 2.3: Spiegabilità Statica dei Driver (Explainability)
* **Descrizione**: Estrarre il contributo delle variabili alla stima dell'IPC usando SHAP e Feature Importance classica.
* **Sotto-task**:
  * `[ ]` Estrarre l'importanza intrinseca delle feature per i modelli ad albero (Gini Importance).
  * `[ ]` Configurare `shap.TreeExplainer` per il modello XGBoost/Random Forest addestrato.
  * `[ ]` Generare e salvare lo **SHAP Summary Plot (Beeswarm)** per quantificare l'impatto positivo/negativo di ciascun driver sul target.
  * `[ ]` Analizzare visivamente la forza predittiva delle coordinate lat/lon rispetto alle variabili fisiche e socio-economiche.
  * `[ ]` Salvare i risultati in `ML/results/static_inference/`.
