# Pipeline di Analisi delle Serie Temporali (TSA) Avanzata

Questa directory contiene la pipeline modulare in Python per l'analisi statistica, diagnostica, comparativa e predittiva dell'insicurezza alimentare (**IPC Phase 3+ %**) per le province dell'**Afghanistan (AFG)** e del **Sudan (SDN)**.

---

## 1. Moduli della Pipeline

La pipeline è organizzata in modo modulare:

* **`config.py`**: Definisce i parametri globali (percorsi, predittori, orizzonti di forecast, pesi affidabilità).
* **`data_loader.py`**: Carica e allinea i dati su base mensile uniforme (`MS`) mantenendo i `NaN` originari per la diagnostica.
* **`monitor.py`**: Calcola il **Reliability Index** basato sulla completezza del dato originario.
* **`preprocessing/backcaster.py`**: Algoritmo di backcasting per imputare predittori e target nel passato.
* **`preprocessing/stationarity.py`**: Gestisce il test ADF con differenziazione automatica ($d=1, 2$), l'estrazione di componenti **STL** e i correlogrammi **ACF/PACF**.
* **`preprocessing/matrix_profile.py`**: Implementazione nativa del **Matrix Profile** per identificare pattern ciclici (**Motifs**) ed eventi anomali (**Discords**).
* **`preprocessing/causality.py`**: Esegue i test di **Causalità di Granger** e modella le interazioni endogene tramite **Vector AutoRegressive (VAR)**.
* **`models/forecasting.py`**: Benchmarking predittivo a due stadi che mette a confronto Holt-Winters, SARIMAX, Prophet (se disponibile) e VAR, testando la bianchezza dei residui tramite **Ljung-Box**.
* **`similarity.py`**: Calcola le distanze di forma **DTW** e **SAX**, ed estrae vettori di feature strutturali statiche (momenti statistici, Hurst exponent, entropia approssimata, coefficienti AR).
* **`run_pipeline.py`**: Script orchestratore principale che esegue l'analisi per tutti i territori e genera i grafici di diagnostica dettagliati.

---

## 2. Metodologia Scientifica & Formule

### A. STL (Seasonal-Trend Decomposition using LOESS)
Utilizziamo la decomposizione STL (`statsmodels.tsa.seasonal.STL`) per dividere la serie target $Y_t$ in tre componenti additive:
$$Y_t = T_t + S_t + R_t$$
dove $T_t$ è il trend di lungo periodo, $S_t$ è la stagionalità e $R_t$ sono i residui. Rispetto alla decomposizione classica, la STL è robusta contro gli outlier e le variazioni temporali nella forma stagionale.

### B. Granger Causality
Verifichiamo se i predittori esogeni $X_t$ (es. conflitti ACLED) abbiano una relazione causale ritardata con il target $Y_t$ (IPC) tramite il test di Granger. Il test valuta l'ipotesi nulla:
$$H_0: \beta_1 = \beta_2 = \dots = \beta_p = 0$$
nella regressione lineare:
$$Y_t = c + \sum_{i=1}^p \alpha_i Y_{t-i} + \sum_{i=1}^p \beta_i X_{t-i} + \epsilon_t$$
Se il $p\text{-value}$ associato al test $F$ è $< 0.05$, rifiutiamo $H_0$, indicando che i lag di $X$ forniscono informazioni statisticamente significative per prevedere $Y$ oltre ai lag storici di $Y$ stesso.

### C. Matrix Profile (Motifs & Discords)
Il Matrix Profile ($MP$) è un vettore che memorizza la distanza Euclidean z-normalizzata di ogni sottosequenza di lunghezza $m$ (impostata a 12 mesi) dal suo vicino più prossimo (escludendo se stessa tramite una zona di esclusione di raggio $m$):
$$MP_i = \min_{j, |i-j| \ge m} D(Sub_i, Sub_j)$$
* **Motifs (Pattern Ripetitivi)**: I punti di minimo locale in $MP$ indicano sottosequenze altamente simili che si ripetono nel tempo.
* **Discords (Anomalie)**: I punti di massimo assoluto in $MP$ rappresentano le anomalie storiche (shock eccezionali non spiegati da cicli regolari).

### D. Feature Strutturali (Feature-Based Similarity)
Per confrontare le province strutturalmente, estraiamo un vettore statico a 9 dimensioni per ciascuna serie storica normalizzata:
1. **Media & Varianza**: Livello medio e volatilità globale.
2. **Skewness & Kurtosis**: Asimmetria e spessore delle code della distribuzione.
3. **Hurst Exponent ($H$)**: Misura la memoria a lungo termine. Se $H > 0.5$ la serie è persistente (un trend tende a continuare), se $H < 0.5$ è anti-persistente.
4. **Approximate Entropy (ApEn)**: Quantifica la regolarità e l'imprevedibilità della serie (valori bassi indicano forte ciclicità, valori alti indicano caos/irregolarità).
5. **Coefficienti AR(1), AR(2), AR(3)**: Estratti fittando un modello autoregressivo per catturare la memoria a breve termine.

---

## 3. Struttura degli Output per Provincia

I risultati diagnostici e le time series allineate sono salvati nella cartella `results/{COUNTRY}/` con la seguente tassonomia:

```text
results/AFG/diagnostics/AFG_Kabul_AF01/
├── 01_Statistical_Decomposition_STL.png    # Grafico STL (Observed, Trend, Seasonal, Resid)
├── 02_Autocorrelation_ACF_PACF.png         # Correlogramma ACF e PACF (su serie stazionaria)
├── 03_Multivariate_Granger_Causality.csv   # Tabella p-value di causalità di Granger per lag
├── 04_Matrix_Profile_Anomalies_Discords.png # Visualizzazione dei pattern (Motif) e shock (Discord)
├── 05_MultiModel_Forecast_Comparison.png   # Confronto HW, SARIMAX, Prophet, VAR con tabella metriche
└── 06_Model_Residuals_Diagnostics.png      # 4-panel plot di analisi dei residui del best model

results/AFG/data/
├── af01_aligned.csv                         # Serie storica unita originale (con NaNs)
├── af01_imputed.csv                         # Serie storica imputata tramite backcasting
├── af01_forecasted_predictors.csv           # Previsioni esogene a 12 mesi
├── af01_fitted_ipc.csv                      # Fit storico dei modelli multivariati
└── af01_projected_ipc.csv                   # Proiezioni IPC future a 12 mesi
```

---

## 4. Esecuzione

Attiva l'ambiente conda `env_master_2026` ed esegui:
```powershell
C:\Users\feder\anaconda3\envs\env_master_2026\python.exe run_pipeline.py
```
