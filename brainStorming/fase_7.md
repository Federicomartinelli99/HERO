# FASE 7: A/B Testing e Benchmarking Sperimentale

Tutte le metodologie saranno valutate calcolando metriche di errore di previsione (MAE, RMSE, MAP) su un test set comune:

| Dimensione di Analisi | Modello A (Baseline) | Modello B (Sfidante) | Ipotesi da Verificare |
|---|---|---|---|
| **Preprocessing** | Dataset Raw con NaNs (gestito da XGBoost) | Dataset imputato con `impute_missing_knn_geo_similarity` | L'imputazione spaziale riduce l'errore di forecast rispetto all'omissione o gestione nativa del dato mancante. |
| **Sequenzialità** | Modello Statico Cross-Section (Fase 2) | Modello Temporale Univariato/Multivariato (Fase 4) | L'inclusione di feature dinamiche e lag storici abbatte significativamente i tassi di errore. |
| **Geometria di Rete** | Forecast Locale per singola provincia | Forecast Globale di Cluster (Fase 5) | L'inferenza cross-regionale aggregata su base cluster migliora l'accuratezza nei territori poveri di dati. |

---

## 📊 Grafici e Visualizzazioni per la FASE 7
* **Bar Chart Multiasse degli Errori**: Grafico a barre raggruppate che mette a confronto le metriche MAE e RMSE per i vari modelli (Statico, ARIMA, VAR, Modello Globale con/senza coordinate, TimesFM) per identificare visivamente il modello migliore.
* **Radar Chart delle Performance**: Grafico a radar (spider plot) in cui le diverse dimensioni rappresentano criteri di valutazione qualitativa e quantitativa (es. accuratezza a breve termine, accuratezza a lungo termine, costo computazionale di calcolo, interpretabilità del modello, resilienza ai dati mancanti). Ogni modello è tracciato come un'area colorata coprente.
