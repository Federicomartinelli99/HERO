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
  * `[ ]` Validare il modello calcolando la matrice di confusione e il report di classificazione.

---

### `[ ]` Task 4.2: Baseline di Forecast Univariato Indipendente (Risoluzione Nativa)
* **Descrizione**: Creare modelli indipendenti a livello di singola provincia/distretto (ADM1/ADM2) per stabilire la baseline di forecast.
* **Sotto-task**:
  * `[ ]` Configurare un ciclo iterativo su tutte le province/distretti del dataset.
  * `[ ]` Per ogni provincia, isolare la serie storica di `phase_3plus_percentage`.
  * `[ ]` Addestrare modelli univariati:
    * `[ ]` **ARIMA/SARIMAX** (selezionando automaticamente i parametri $p, d, q$ tramite AIC/BIC).
    * `[ ]` **Exponential Smoothing (Holt-Winters)**.
  * `[ ]` Generare le previsioni out-of-sample per un orizzonte temporale $h=3$ e $h=6$ mesi.
  * `[ ]` Salvare gli errori di previsione (MAE, RMSE) per il confronto finale.

---

### `[ ]` Task 4.3: Forecast Multivariato Causale (VAR)
* **Descrizione**: Modellare l'interdipendenza tra target e driver esogeni.
* **Sotto-task**:
  * `[ ]` Assicurarsi che le serie storiche inserite siano stazionarie (Task 3.1).
  * `[ ]` Definire il vettore delle variabili: `[IPC3+, acled_events_100k, wfp_price_index, ndvi_vim]`.
  * `[ ]` Inizializzare ed addestrare il modello **Vector Autoregression (VAR)** selezionando il lag ottimale tramite AIC.
  * `[ ]` Calcolare e tracciare le **Impulse Response Functions (IRF)** per simulare l'effetto a catena di uno shock improvviso dei driver sull'IPC3+.

---

### `[ ]` Task 4.4: Diagnostica Avanzata dei Residui
* **Descrizione**: Validare l'adeguatezza statistica del modello migliore verificando che i residui siano white noise.
* **Sotto-task**:
  * `[ ]` Estrarre i residui del modello predittivo migliore su una provincia test.
  * `[ ]` Calcolare il test di **Ljung-Box** per verificare l'assenza di autocorrelazione residua significativa.
  * `[ ]` Generare e salvare il grafico diagnostico a 4 pannelli (`06_Model_Residuals_Diagnostics.png`):
    * Residui nel tempo.
    * Istogramma + KDE dei residui vs curva normale.
    * Q-Q plot normale.
    * Correlogramma ACF dei residui.

---

### `[ ]` Task 4.5: Meta-Modello di Stacking Ensemble
* **Descrizione**: Sviluppare un modello di stacking che pesi le predizioni dei singoli regressori.
* **Sotto-task**:
  * `[ ]` Raccogliere le predizioni out-of-sample dei modelli univariati (ARIMA, ES), del VAR e del modello globale XGBoost.
  * `[ ]` Addestrare un regressore lineare regolarizzato (**Ridge** o **Lasso**) avente come input le predizioni dei modelli base e come target il valore IPC3+ reale.
  * `[ ]` Vincolare i coefficienti del meta-regressore affinché la loro somma sia pari a 1 (opzionale, per interpretabilità).
  * `[ ]` Salvare i pesi risultanti del meta-modello per illustrare il contributo relativo di ciascun algoritmo base.
  * `[ ]` Salvare i codici e risultati in `ML/results/temporal_modeling/`.
