# FASE 4: Modellazione Temporale (Inferenza e Forecast su TS)

---

## Task 4.1 - Classificazione delle Traiettorie Temporali (Weak Supervision)
* **Obiettivo**: Mappare l'intera serie temporale di una provincia in una classe di rischio $c_i$.
* **Generazione Label (Rule-Based Labeling)**: Non avendo dataset pre-etichettati per le classi di rischio, calcoleremo il delta ($\Delta$) di `phase_3plus_percentage` su finestre semestrali/annuali:
  * **Classe A: Escalation Critica** ($\Delta \ge +15\%$)
  * **Classe B: Crisis Cronica** (oscillazioni contenute tra $-5\%$ e $+5\%$)
  * **Classe C: Recupero/Miglioramento** ($\Delta \le -15\%$)
* **Modellazione**: Addestramento di classificatori (Random Forest, SVM o Shapelet classifiers) per prevedere in anticipo l'appartenenza a una traiettoria in base alle dinamiche storiche dei driver esogeni.

---

## Task 4.2 - Forecast Univariato Indipendente a Risoluzione Nativa
* **Metodologia**: Abbandono dell'aggregazione nazionale per operare sulla granularità spaziale originaria (livello provinciale ADM1 e distrettuale ADM2).
* **Esecuzione**: Addestramento indipendente di migliaia di modelli univariati veloci (ARIMA, Exponential Smoothing - ES) su ogni singola provincia/distretto.
* **Scopo**: Costruire una **solida baseline univariata** (basata esclusivamente sull'autocorrelazione storica del target) da confrontare con i modelli multivariati e globali.

---

## Task 4.3 - Forecast Multivariato Causale (VAR)
* **Logica**: Utilizzo di modelli autoregressivi vettoriali (VAR) sulle serie rese stazionarie per catturare i feedback loop bidirezionali (es. l'insorgenza di conflitti aumenta i prezzi alimentari locali, e l'inflazione esaspera le tensioni sociali).

---

## Task 4.4 - Diagnostica Avanzata dei Residui dei Modelli
* **Logica**: Validare che i residui del modello di forecast migliore si comportino come "rumore bianco" (assenza di autocorrelazione).
* **Metodologia**: Test di Ljung-Box per la significatività statistica e stima della normalità dei residui.

---

## Task 4.5 - Modellazione Ensemble tramite Stacking (Meta-Learning)
* **Logica (DMML)**: Integrare la precisione di modelli statistici lineari con la flessibilità di modelli non lineari di Machine Learning e Deep Learning per mitigare la varianza dell'errore.
* **Metodologia**: Le predizioni a livello provinciale di modelli univariati (ARIMA, ES), multivariati (VAR) e globali (XGBoost, TimesFM) verranno fornite in input a un modello di livello superiore (Meta-Regressore regolarizzato come Ridge o Lasso). Quest'ultimo imparerà i pesi ottimali da attribuire a ciascuna previsione per produrre un forecast consolidato finale.

---

## 📊 Grafici e Visualizzazioni per la FASE 4
* **Matrice di Confusione della Classificazione**: Mappa di calore delle predizioni vs valori reali per le classi di traiettoria (Escalation, Stabilità, Ripresa) per valutare errori sistematici di classificazione.
* **Line plot di Forecast Univariato**: Grafico temporale per province selezionate che mostra lo storico reale in linea continua nera, il fit del modello in linea tratteggiata blu e la proiezione futura con l'area semitrasparente che rappresenta l'intervallo di confidenza al 95%.
* **Impulse Response Function (IRF) Plot**: Grafici a subplots derivati dal modello VAR. Mostrano come l'IPC3+ reagisca nel corso dei successivi 12 mesi a uno "shock" improvviso (impulso di una deviazione standard) applicato a un driver esogeno (es. un picco improvviso nei conflitti ACLED).
* **Model Residuals Diagnostics (4-Panel Plot - `06_Model_Residuals_Diagnostics.png`)**:
  1. Grafico a linee dei residui nel tempo per valutare l'omoschedasticità.
  2. Istogramma con stima KDE della densità dei residui per verificarne la simmetria normale.
  3. Q-Q Plot normale per valutare lo spessore delle code e la vicinanza alla gaussiana.
  4. Correlogramma ACF dei residui con limiti di confidenza del test di Ljung-Box.
* **Grafico delle Frazioni dei Pesi di Stacking (Radar o Stacked Bar)**: Rappresentazione visiva dei pesi appresi dal meta-modello di stacking, mostrando l'importanza relativa di ciascun modello base (VAR, ARIMA, XGBoost) in base al territorio analizzato.
