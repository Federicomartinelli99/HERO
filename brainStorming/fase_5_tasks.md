# Checklist di Sviluppo - FASE 5: Inferenza Cross-Regionale (Global Forecasting)

Questo documento contiene i dettagli implementativi e la checklist per la **Fase 5**. L'obiettivo è addestrare modelli globali robusti aggregando i dati delle province dello stesso cluster e valutarne il trasferimento spaziale.

---

## 📋 Task List

### `[ ]` Task 5.1: Addestramento del Global Cluster Model
* **Descrizione**: Sviluppare e addestrare un singolo modello di ML potente concatenando le serie storiche delle province all'interno dello stesso cluster funzionale.
* **Sotto-task**:
  * `[ ]` Recuperare le etichette di clustering spaziotemporale calcolate nella Fase 3 (DTW + tsfresh).
  * `[ ]` Per ogni cluster identificato, concatenare longitudinalmente le serie storiche (panel data) di tutte le province del cluster.
  * `[ ]` Creare le feature autoregressive ritardate (lag da 1 a 6 mesi per ciascun driver).
  * `[ ]` Addestrare un modello di **XGBoost / LightGBM Regressor** o una rete neurale ricorrente (**LSTM/GRU**) globale per il cluster specifico.
  * `[ ]` Misurare le performance predittive complessive del modello globale.

---

### `[ ]` Task 5.2: Test di Domain Adaptation & Spatial Transfer Learning
* **Descrizione**: Valutare le capacità di generalizzazione spaziale del modello globale su aree escluse o prive di dati storici.
* **Sotto-task**:
  * `[ ]` All'interno di un cluster, escludere un intero paese (es. lo Yemen) dal set di addestramento.
  * `[ ]` Addestrare il modello globale unicamente sui dati delle province dei restanti paesi del cluster (es. Somalia ed Etiopia).
  * `[ ]` Effettuare previsioni *Zero-Shot* sulle province del paese escluso (Yemen).
  * `[ ]` Effettuare previsioni applicando un *fine-tuning* leggero (ri-addestramento parziale del modello globale solo sulle prime 3 osservazioni del paese test).
  * `[ ]` Calcolare le metriche di errore e confrontare le due modalità (Zero-Shot vs Fine-Tuning) per quantificare la stabilità del trasferimento di conoscenza spaziale.

---

### `[ ]` Task 5.3: Spiegabilità Temporale con SHAP (XAI)
* **Descrizione**: Applicare SHAP per identificare quali descrittori globali di serie storica guidano la predizione del modello globale.
* **Sotto-task**:
  * `[ ]` Creare la matrice delle feature strutturali (output di `tsfresh` selezionato) per le serie storiche del cluster.
  * `[ ]` Configurare `shap.TreeExplainer` sull'istanza del modello XGBoost globale addestrato.
  * `[ ]` Calcolare gli SHAP values per ciascuna provincia e data.
  * `[ ]` Generare e salvare il **Beeswarm Plot SHAP** specifico per le feature strutturali temporali (es. Hurst exponent, Fourier coefficients, ApEn).
  * `[ ]` Analizzare l'impatto delle componenti di trend e stagionalità rispetto alla varianza a breve termine dei prezzi e dei conflitti.
  * `[ ]` Salvare i risultati in `ML/results/global_forecasting/`.
