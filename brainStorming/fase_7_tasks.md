# Checklist di Sviluppo - FASE 7: A/B Testing e Benchmarking Sperimentale

Questo documento contiene i dettagli implementativi e la checklist per la **Fase 7**. L'obiettivo è validare scientificamente le scelte metodologiche del progetto confrontando i modelli lungo tre assi di testing.

---

## 📋 Task List

### `[ ]` Task 7.1: Calcolo Comparativo delle Metriche (Il Framework di Test)
* **Descrizione**: Calcolare in modo uniforme gli errori di forecast su un test set comune e non contaminato per tutti i modelli sviluppati.
* **Sotto-task**:
  * `[ ]` Isolare la finestra di test temporale (es. gli ultimi 6 mesi storici disponibili del dataset).
  * `[ ]` Sviluppare una funzione centralizzata per il calcolo di:
    * Mean Absolute Error (MAE):
      $$\text{MAE} = \frac{1}{N}\sum|y_i - \hat{y}_i|$$
    * Root Mean Squared Error (RMSE):
      $$\text{RMSE} = \sqrt{\frac{1}{N}\sum(y_i - \hat{y}_i)^2}$$
    * Mean Absolute Percentage Error (MAPE):
      $$\text{MAPE} = \frac{1}{N}\sum\left|\frac{y_i - \hat{y}_i}{y_i}\right| \times 100$$
  * `[ ]` Popolare la tabella comparativa per i seguenti tre assi di test:
    * `[ ]` **Test A (Preprocessing)**: Dataset Raw (senza imputazione, gestito nativamente da XGBoost) vs Dataset imputato spazialmente con KNN.
    * `[ ]` **Test B (Sequenzialità)**: Modello statico Fase 2 vs Modelli temporali (VAR, ARIMA) vs Modello spazio-temporale (VAR/XGBoost con coordinate).
    * `[ ]` **Test C (Integrazione di Rete)**: Previsione locale (univariata ARIMA/ES) vs Previsione globale di cluster (Fase 5) vs Stacking Ensemble.

---

### `[ ]` Task 7.2: Visualizzazione del Benchmarking
* **Descrizione**: Produrre grafici sintetici per illustrare chiaramente le performance dei modelli.
* **Sotto-task**:
  * `[ ]` Generare e salvare il **Bar Chart Multiasse** per visualizzare MAE e RMSE affiancati per ciascun modello base ed ensemble.
  * `[ ]` Generare e salvare il **Radar Chart** (spider plot) per confrontare i modelli su dimensioni multiple (accuratezza a breve termine, accuratezza a lungo termine, costo computazionale, interpretabilità, stabilità ai dati mancanti).
  * `[ ]` Salvare la tabella riassuntiva finale in formato CSV e Markdown in `ML/results/benchmarking/`.
