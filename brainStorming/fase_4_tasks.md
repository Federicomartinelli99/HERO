# Checklist di Sviluppo - FASE 4: Modellazione Temporale (Forecasting)

Questo documento contiene i dettagli implementativi e la checklist per la **Fase 4**. L'obiettivo è predire le traiettorie dell'IPC e il forecast quantitativo futuro sfruttando la componente autoregressiva e multivariata.

---

## 📋 Task List

### `[ ]` Task 4.1: Classificazione delle Traiettorie con Weak Supervision
* **Descrizione**: Categorizzare le serie storiche provinciali in traiettorie di rischio alimentare calcolando il delta dell'IPC.
* **Sotto-task**:
  * `[ ]` Definire la finestra temporale di valutazione (es. 12 mesi).
  * `[ ]` Calcolare il delta percentuale dell'IPC3+ ($\Delta = \text{IPC3\%}_{t+12} - \text{IPC3\%}_{t}$).
  * `[ ]` Assegnare le etichette di classe in base a regole fisse:
    * `[ ]` **Classe A (Escalation)**: $\Delta \ge +15\%$
    * `[ ]` **Classe B (Stabilità)**: $-5\% \le \Delta \le +5\%$
    * `[ ]` **Classe C (Recupero)**: $\Delta \le -15\%$
  * `[ ]` Addestrare un classificatore supervisionato (Random Forest / XGBoost) sulle feature storiche dei driver per prevedere l'appartenenza a queste classi.
  * `[ ]` Validare il modello calcolando la matrice di confusione in `ML/results/temporal_modeling/confusion_matrices/`.

---

### `[ ]` Task 4.2: Baseline di Forecast Univariato Indipendente (Risoluzione Nativa)
* **Descrizione**: Creare modelli indipendenti a livello di singola provincia/distretto (ADM1/ADM2) per stabilire la baseline di forecast.
* **Sotto-task**:
  * `[ ]` Configurare un ciclo iterativo su tutte le province/distretti del dataset.
  * `[ ]` Per ogni provincia, isolare la serie storica di `phase_3plus_percentage`.
  * `[ ]` Addestrare modelli univariati:
    * `[ ]` **Exponential Smoothing (Holt-Winters)**.
    * `[ ]` **SARIMAX**: implementare una ricerca a griglia automatica per stimare i parametri autoregressivi, di stagionalità e media mobile ($p, d, q, P, D, Q, s$) minimizzando sia l'**AIC** (Akaike Information Criterion) sia il **BIC** (Bayesian Information Criterion).
  * `[ ]` Generare le previsioni out-of-sample per un orizzonte temporale $h=3$ e $h=6$ mesi.
  * `[ ]` Salvare gli errori di previsione (MAE, RMSE) per il confronto finale ed esportare il grafico di confronto multimodello (`ML/results/temporal_modeling/05_MultiModel_Forecast_Comparison.png`).

---

### `[ ]` Task 4.3: Forecast Multivariato Causale (VAR)
* **Descrizione**: Modellare l'interdipendenza tra target e driver esogeni.
* **Sotto-task**:
  * `[ ]` Assicurarsi che le serie storiche inserite siano stazionarie (Task 3.1).
  * `[ ]` Definire il vettore delle variabili: `[IPC3+, acled_events_100k, wfp_price_index, ndvi_vim]`.
  * `[ ]` Inizializzare ed addestrare il modello **Vector Autoregression (VAR)** selezionando il lag ottimale tramite AIC.
  * `[ ]` Calcolare e tracciare le **Impulse Response Functions (IRF)** per simulare l'effetto a catena di uno shock improvviso dei driver sull'IPC3+. Salvare i plot in `ML/results/temporal_modeling/var_irf/`.

---

### `[ ]` Task 4.4: Diagnostica Avanzata e Distribuzione dei Residui
* **Descrizione**: Validare l'adeguatezza statistica del modello migliore verificando che i residui siano white noise e analizzandone la distribuzione.
* **Sotto-task**:
  * `[ ]` Estrarre i residui del modello predittivo migliore su una provincia test.
  * `[ ]` Analizzare la **distribuzione probabilistica dei residui**: verificare che abbiano media pari a zero, varianza costante (assenza di eteroschedasticità) e studiare l'istogramma/KDE per confermarne la simmetria normale.
  * `[ ]` Calcolare il test di **Ljung-Box** per verificare l'assenza di autocorrelazione residua significativa.
  * `[ ]` Generare e salvare il grafico diagnostico a 4 pannelli (`ML/results/temporal_modeling/06_Model_Residuals_Diagnostics.png`):
    * Residui nel tempo.
    * Istogramma + KDE dei residui vs curva normale per la distribuzione.
    * Q-Q plot normale.
    * Correlogramma ACF dei residui.

---

### `[ ]` Task 4.5: Meta-Modello di Stacking Ensemble
* **Descrizione**: Sviluppare un modello di stacking che pesi le predizioni dei singoli regressori.
* **Sotto-task**:
  * `[ ]` Raccogliere le predizioni out-of-sample dei modelli univariati (ARIMA, ES), del VAR e del modello globale XGBoost.
  * `[ ]` Addestrare un regressore lineare regolarizzato (**Ridge** o **Lasso**) avente come input le predizioni dei modelli base e come target il valore IPC3+ reale.
  * `[ ]` Salvare i pesi risultanti del meta-modello in `ML/results/temporal_modeling/stacking_weights/` per illustrare il contributo relativo di ciascun algoritmo base.
