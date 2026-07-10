# FASE 4: Modellazione Temporale (Inferenza e Forecast su TS)

---

## Task 4.1 - Classificazione delle Traiettorie Temporali (Weak Supervision)
* **Logica**: Invece di stimare un singolo timestamp, l'obiettivo qui è trovare una funzione matematica $f$ che mappa lo spazio delle intere possibili serie temporali nello spazio di una classe finale target $c_i$.
* **Applicazione**: La classe può indicare la "traiettoria di rischio" (es. Classe A: Deterioramento verso l'emergenza; Classe B: Stabilizzazione).

---

## Task 4.2 - Forecast Time Series Indipendente (Univariato)
* **Modelli**: Modelli di base come l'Exponential Smoothing (ES) o gli ARIMA (AutoRegressive Integrated Moving Average), che proiettano la singola time series nel futuro modellando i propri ritardi e gli errori medi residui.

---

## Task 4.3 - Forecast Multivariato su IPC (Modelli Causali e VAR)
* **Logica**: Valutare se includere altre variabili temporali riduca l'errore di forecast (differenza tra valore osservato ed errore calcolato sul test set).
* **Applicazione**: Usare algoritmi che catturano l'interdipendenza sequenziale multivariata (es. Vector Autoregression - VAR) per proiettare l'IPC tenendo in conto simultaneamente ACLED e Prezzi.

---

## Task 4.4 - Diagnostica Avanzata dei Residui dei Modelli
* **Logica**: Validare che i residui del modello di forecast migliore si comportino come "rumore bianco" (assenza di autocorrelazione).
* **Metodologia**: Test di Ljung-Box per la significatività statistica e stima della normalità dei residui.

---

## Task 4.5 - Modellazione Ensemble tramite Stacking (Meta-Learning)
* **Logica (DMML)**: Integrare la precisione di modelli statistici lineari con la flessibilità di modelli non lineari di Machine Learning e Deep Learning per mitigare la varianza dell'errore.
* **Metodologia**: Le predizioni a livello provinciale di modelli univariati (ARIMA, ES), del VAR e del modello globale XGBoost verranno fornite in input a un modello di livello superiore (Meta-Regressore regolarizzato come Ridge o Lasso). Quest'ultimo imparerà i pesi ottimali da attribuire a ciascuna previsione per produrre un forecast consolidato finale.

---

## 📊 Grafici e Visualizzazioni per la FASE 4
* **Matrice di Confusione della Classificazione**: Mappa di calore delle predizioni vs valori reali per le classi di traiettoria (Escalation, Stabilità, Ripresa) per valutare errori sistematici di classificazione.
* **Grafico di Confronto Multi-Modello (`05_MultiModel_Forecast_Comparison.png`)**: Grafico temporale che confronta la serie storica reale (test set) con le proiezioni generate contemporaneamente da Holt-Winters, SARIMAX, Prophet e VAR, includendo una tabella sovrapposta con le metriche di errore calcolate (MAE, RMSE) per identificare visivamente il modello migliore.
* **Line plot di Forecast Univariato**: Grafico temporale per province selezionate che mostra lo storico reale in linea continua nera, il fit del modello in linea tratteggiata blu e la proiezione futura con l'area semitrasparente che rappresenta l'intervallo di confidenza al 95%.
* **Impulse Response Function (IRF) Plot**: Grafici a subplots derivati dal modello VAR. Mostrano come l'IPC3+ reagisca nel corso dei successivi 12 mesi a uno "shock" improvviso (impulso di una deviazione standard) applicato a un driver esogeno (es. un picco improvviso nei conflitti ACLED).
* **Model Residuals Diagnostics (4-Panel Plot - `06_Model_Residuals_Diagnostics.png`)**:
  1. Grafico a linee dei residui nel tempo per valutare l'omoschedasticità.
  2. Istogramma con stima KDE della densità dei residui per verificarne la simmetria normale.
  3. Q-Q Plot normale per valutare lo spessore delle code e la vicinanza alla gaussiana.
  4. Correlogramma ACF dei residui con limiti di confidenza del test di Ljung-Box.
* **Grafico delle Frazioni dei Pesi di Stacking (Radar o Stacked Bar)**: Rappresentazione visiva dei pesi appresi dal meta-modello di stacking, mostrando l'importance relativa di ciascun modello base (VAR, ARIMA, XGBoost) in base al territorio analizzato.
