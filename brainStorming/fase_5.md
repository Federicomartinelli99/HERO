# FASE 5: Inferenza Cross-Regionale (Global Forecasting)

* **Metodologia**: Invece di addestrare modelli locali singoli per province con dati storici scarsi o frammentati, si sfrutta l'apprendimento globale basato sul clustering.
* **Pipeline**:
  1. Si applica il clustering spaziotemporale (DTW + tsfresh + coordinate standardizzate) per raggruppare le regioni in "archetipi di vulnerabilità".
  2. Per ciascun cluster, si concatenano le serie storiche di tutte le province appartenenti ad esso.
  3. Si addestra un unico modello di Machine Learning globale (XGBoost globale o rete neurale ricorrente LSTM/GRU) su tutti i dati del cluster.
  4. Il modello globale generalizza il comportamento del cluster e può fare inferenza accurata anche su province che possiedono pochissimi dati storici (trasferimento di conoscenza spaziale).

---

## Task 5.2 - Domain Adaptation & Trasferimento Spaziale (Transfer Learning)
* **Logica (DMML)**: Testare la capacità del modello globale di generalizzare su territori privi di dati storici storicamente continui (es. a causa di embargo, conflitti intensi o interruzioni delle agenzie umanitarie).
* **Metodologia**: Addestrare il modello globale su un sottoinsieme di paesi del cluster (es. Afghanistan e Somalia) e testarlo direttamente (Zero-Shot) o con fine-tuning leggero su paesi esclusi del medesimo cluster (es. Yemen), misurando la stabilità del trasferimento spaziale.

---

## Task 5.3 - SHAP per Feature Temporali Strutturali (XAI Avanzata)
* **Logica (DMML)**: Portare l'interpretabilità dei modelli ad un livello superiore. Invece di spiegare la previsione usando solo i valori puntuali correnti dei driver, si applicano gli additivi SHAP sull'output del modello globale addestrato sulle feature di `tsfresh`.
* **Obiettivo**: Dimostrare quali pattern dinamici complessi (es. l'autocorrelazione a 3 mesi dei prezzi o la volatilità climatica dell'NDVI) abbiano guidato la predizione di crisi della provincia.

---

## 📊 Grafici e Visualizzazioni per la FASE 5
* **Confronto Lineare Actual vs Predict (Global Model)**: Grafici a linee multi-provincia in cui si sovrappongono i dati reali (linea nera) e le predizioni del modello globale (linea rossa tratteggiata) su un set di province "test" escluse dall'addestramento.
* **Scatter Plot dei Residui Globali**: Grafico a dispersione che mostra l'errore residuo del modello globale in funzione del tempo o della magnitudo del target, per verificare l'assenza di eteroschedasticità all'interno del cluster.
* **Beeswarm Plot SHAP delle Feature Temporali (`tsfresh` descriptors)**: Visualizzazione SHAP che classifica l'impatto dei descrittori di serie storica (Hurst exponent, Fourier coefficients, ApEn, ecc.) sulle predizioni di carestia del modello globale.
