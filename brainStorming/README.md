# Roadmap di Sviluppo del Progetto HERO: Indice dei Moduli

Questo è il file centrale di coordinamento per la roadmap di sviluppo del progetto **HERO (Hunger Early-warning & Risk Optimizer)**. Il piano è suddiviso in moduli autonomi e interconnessi per facilitare la gestione dei task di Data Mining & Machine Learning (DMML), Time Series Analysis (TSMDA) e Data Visualization (DVVA).

Clicca sui link sottostanti per esplorare la documentazione dettagliata, le specifiche visuali e le checklist implementative di ciascuna fase:

---

## Indice delle Fasi di Sviluppo

### 🛠️ [FASE 1: Preprocessing, Armonizzazione e Gestione del Dato Mancante](fase_1.md)
* **Descrizione**: Standardizzazione demografica dei driver per 100.000 abitanti (ACLED, IDP) e imputazione spaziotemporale KNN guidata dalle coordinate geografiche.
* 📝 **[Checklist Implementativa - Fase 1 Tasks](fase_1_tasks.md)**

### 📈 [FASE 2: Approccio Statico (Cross-Sectional, Senza Sequenzialità)](fase_2.md)
* **Descrizione**: Clustering statico dei paesi (K-Means, DBSCAN, Hierarchical) e modelli predittivi supervisionati per l'IPC3+ (KNN, Decision Trees, SVM, Random Forest, XGBoost) con spiegabilità SHAP.
* 📝 **[Checklist Implementativa - Fase 2 Tasks](fase_2_tasks.md)**

### ⏱️ [FASE 3: Feature Engineering ed Esplorazione Time Series (Sequenzialità)](fase_3.md)
* **Descrizione**: Pattern temporali (Matrix Profile), Shapelets, feature selection `tsfresh`, DTW/NCD clustering, stazionarizzazione (test ADF) e cross-correlazioni (CCF).
* 📝 **[Checklist Implementativa - Fase 3 Tasks](fase_3_tasks.md)**

### 🔮 [FASE 4: Modellazione Temporale (Inferenza e Forecast su TS)](fase_4.md)
* **Descrizione**: Classificazione traiettorie IPC3+ (Weak Supervision), forecast univariato nativo baseline, forecast multivariato VAR, diagnostica residui e Stacking Ensemble.
* 📝 **[Checklist Implementativa - Fase 4 Tasks](fase_4_tasks.md)**

### 🌍 [FASE 5: Inferenza Cross-Regionale (Global Forecasting)](fase_5.md)
* **Descrizione**: Global Cluster Forecasting, Domain Adaptation / Transfer Learning spaziotemporale e spiegabilità temporale SHAP su feature `tsfresh`.
* 📝 **[Checklist Implementativa - Fase 5 Tasks](fase_5_tasks.md)**

### 🛡️ [FASE 6: Tecniche di Frontiera (Integrazione TSMDA & DMML)](fase_6.md)
* **Descrizione**: Network Analysis classica dei mercati (NetworkX), autocorrelazione spaziale (Moran's I & LISA), TimesFM Zero-Shot forecast e DBSCAN Outlier detection.
* 📝 **[Checklist Implementativa - Fase 6 Tasks](fase_6_tasks.md)**

### 🔬 [FASE 7: A/B Testing e Benchmarking Sperimentale](fase_7.md)
* **Descrizione**: Calcolo comparativo delle performance (MAE, RMSE, MAPE) e visualizzazione spider/radar chart del benchmarking.
* 📝 **[Checklist Implementativa - Fase 7 Tasks](fase_7_tasks.md)**

### 🖥️ [FASE 8: Visualizzazione Interattiva (Data Visual Analytics)](fase_8.md)
* **Descrizione**: Dashboard web Folium/GeoPandas, ApexCharts heatmap, trend lineari/radar e il simulatore interattivo di scenario "What-If".
* 📝 **[Checklist Implementativa - Fase 8 Tasks](fase_8_tasks.md)**
