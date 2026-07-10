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

---

## 📂 Alberatura di Archiviazione dei Risultati (Risultati & Plot)

Tutti i codici verranno archiviati all'interno della cartella `ML/codes/`, mentre tutti i prodotti analitici (immagini, mappe, CSV intermedi e tabelle) seguiranno una rigida alberatura gerarchica all'interno di **`ML/results/`**:

```text
ML/
├── codes/
│   ├── run_clustering.py
│   └── [altri script di pipeline...]
└── results/
    ├── preprocessing/
    │   ├── missingness_heatmap_before.png
    │   ├── missingness_heatmap_after.png
    │   ├── kde_density_control_[driver].png
    │   └── spatial_imputed_markers_map.png
    ├── static_inference/
    │   ├── country_static_dendrogram.png
    │   ├── country_static_heatmap.png
    │   ├── pca_tsne_static_clusters.png
    │   └── shap_static_beeswarm_plot.png
    ├── time_series_exploration/
    │   ├── 01_Statistical_Decomposition_STL.png
    │   ├── 02b_Compare_Series_Autocorrelation.png
    │   ├── 02c_Cross_Correlation_with_Target.png
    │   ├── 02c_Cross_Correlation_with_Target.csv
    │   ├── 04_Matrix_Profile_Anomalies_Discords.png
    │   ├── shapelet_alignments/
    │   │   └── [plot delle shapelets per provincia...]
    │   ├── heatmaps/
    │   │   └── global_national_dtw_heatmap.png
    │   ├── dendrograms/
    │   │   ├── global_regions_dendrogram_features.png
    │   │   └── global_regions_dendrogram_shape.png
    │   ├── clustering/
    │   │   └── global_regions_pca_scatter.png
    │   └── maps/
    │       ├── global_national_map.png
    │       └── global_regions_map.png
    ├── temporal_modeling/
    │   ├── 05_MultiModel_Forecast_Comparison.png
    │   ├── 06_Model_Residuals_Diagnostics.png
    │   ├── confusion_matrices/
    │   │   └── trajectory_confusion_matrix.png
    │   ├── forecasts/
    │   │   └── [plot dei forecast indipendenti per provincia...]
    │   ├── var_irf/
    │   │   └── var_impulse_response_subplots.png
    │   └── stacking_weights/
    │       └── stacking_weights_distribution.png
    ├── global_forecasting/
    │   ├── global_actual_vs_predict.png
    │   ├── global_residuals_scatterplot.png
    │   └── shap_temporal_beeswarm_plot.png
    ├── frontier_techniques/
    │   ├── market_network_graph.png
    │   ├── moran_scatterplot.png
    │   ├── lisa_cluster_map.png
    │   ├── timesfm_zeroshot_forecast.png
    │   ├── dbscan_spatial_outliers.png
    │   └── ncd_compression_heatmap.png
    └── benchmarking/
        ├── metrics_summary_table.csv
        ├── models_error_comparison_bar.png
        └── models_performance_radar_chart.png
```
