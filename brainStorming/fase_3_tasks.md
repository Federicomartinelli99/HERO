# Checklist di Sviluppo - FASE 3: Analisi Sequenziale ed Esplorazione Time Series

Questo documento contiene i dettagli implementativi e la checklist per la **Fase 3**. L'obiettivo è analizzare le serie storiche dei driver per estrarne la stazionarietà, le anomalie e le feature dinamiche.

---

## 📋 Task List

### `[ ]` Task 3.1: Stazionarizzazione Automatica e Decomposizione STL
* **Descrizione**: Verificare e correggere la non-stazionarietà delle serie storiche prima della modellazione.
* **Sotto-task**:
  * `[ ]` Implementare il test **Augmented Dickey-Fuller (ADF)** per la serie target (`phase_3plus_percentage`) e i driver esogeni a livello di provincia.
  * `[ ]` Sviluppare una routine di differenziazione automatica: applicare la differenza prima ($d=1$) o seconda ($d=2$) se il p-value del test ADF è $\ge 0.05$.
  * `[ ]` Applicare la decomposizione **STL (Seasonal-Trend Decomposition using LOESS)** per isolare trend, stagionalità e residui per ciascuna provincia.
  * `[ ]` Plottare e salvare i correlogrammi ACF/PACF prima e dopo la stazionarizzazione.

---

### `[ ]` Task 3.2: Analisi di Cross-Correlazione con Lag (CCF)
* **Descrizione**: Calcolare i lag temporali ottimali dei driver esogeni rispetto al target IPC.
* **Sotto-task**:
  * `[ ]` Implementare il calcolo della cross-correlazione per lag compresi tra $-12$ e $+12$ mesi.
  * `[ ]` Identificare per ciascuna provincia e driver il lag che presenta il valore assoluto di correlazione massimo.
  * `[ ]` Salvare i risultati in un file CSV ed esportare i grafici CCF (`02c_Cross_Correlation_with_Target.png`).

---

### `[ ]` Task 3.3: Anomaly Detection con Matrix Profile (Motifs & Discords)
* **Descrizione**: Cercare pattern ripetitivi (Motifs) e shock isolati (Discords) nelle serie esogene.
* **Sotto-task**:
  * `[ ]` Installare/importare librerie per il calcolo del Matrix Profile (es. `stumpy` o implementazione custom z-normalizzata).
  * `[ ]` Configurare una finestra temporale di $m = 12$ mesi.
  * `[ ]` Calcolare il Matrix Profile sui prezzi WFP e anomalie CHIRPS, individuando i Discords principali (shock di prezzo o climatici).
  * `[ ]` Tracciare i residui dell'anomalia rispetto alla soglia $Z > 2.0$.

---

### `[ ]` Task 3.4: Estrazione delle Shapelets Predittive
* **Descrizione**: Estrarre sottosequenze temporali discriminanti che precedono picchi di IPC3+.
* **Sotto-task**:
  * `[ ]` Definire finestre temporali di input (es. 6 mesi di dati storici dei driver) associate a un picco dell'IPC3+ nei successivi 3 mesi.
  * `[ ]` Estrarre le Shapelets candidate usando algoritmi di shapelet discovery (es. `sktime.classification.shapelet_based.ShapeletTransformClassifier` o algoritmi basati sulla distanza minima).
  * `[ ]` Plottare l'allineamento delle shapelets estrattive sulle serie storiche reali per illustrare il precursore visivo della crisi.

---

### `[ ]` Task 3.5: Feature Extraction Strutturale via `tsfresh`
* **Descrizione**: Calcolare descrittori statici globali per sintetizzare le dinamiche delle serie storiche.
* **Sotto-task**:
  * `[ ]` Configurare `tsfresh` per estrarre feature dalle serie storiche mensili provinciali.
  * `[ ]` Generare descrittori (media, varianza, Hurst exponent, entropia approssimata, coefficienti autoregressivi AR).
  * `[ ]` Applicare la feature selection integrata di `tsfresh` per filtrare solo le feature significativamente correlate al target IPC3+.

---

### `[ ]` Task 3.6: Distanze Temporali e Clustering Dinamico (DTW & NCD)
* **Descrizione**: Calcolare le matrici di dissimilarità dinamica e raggruppare le province in base alla forma o comprimibilità delle loro serie storiche.
* **Sotto-task**:
  * `[ ]` Sviluppare il calcolo della distanza **DTW (Dynamic Time Warping)** z-normalizzata tra le serie storiche provinciali.
  * `[ ]` Sviluppare il calcolo della distanza di compressione **NCD (Normalized Compression Distance)** concatenando e comprimendo (es. con gzip) i vettori delle serie storiche.
  * `[ ]` Eseguire il clustering gerarchico sulle matrici di distanza risultanti e generare i relativi dendrogrammi.
  * `[ ]` Salvare tutti i risultati in `ML/results/time_series_exploration/`.
