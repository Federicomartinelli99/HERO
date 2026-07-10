# FASE 3: Feature Engineering ed Esplorazione Time Series (Sequenzialità)

Le osservazioni vengono trattate come sequenze temporali ordinate: $X_i = \langle x_{t1}, x_{t2}, \dots, x_{tm} \rangle$.

---

## Task 3.1 - Anomaly Detection con Matrix Profile (Motifs & Discords)
* **Metodologia**: Calcolo del **Matrix Profile** su una finestra temporale di $m = 12$ mesi (finestra annuale classica) per le serie esogene (prezzi WFP, piogge).
* **Obiettivo**:
  * **Motifs**: Trovare pattern ciclici o ripetitivi di incremento di vulnerabilità.
  * **Discords**: Identificare shock sistemici anomali (anomalie strutturali isolate).
* **Identificazione Shock**: Calcolo del Z-score sui residui e classificazione come shock sistemico per deviazioni superiori a $Z > 2.0$.

---

## Task 3.2 - Uso delle Shapelets (Subsequence-based Classification)
* **Metodologia**: Gli algoritmi estrarranno le "Shapelets", ovvero le sottosequenze temporali brevi e altamente discriminanti all'interno delle serie storiche dei driver.
* **Applicazione in HERO**: Trovare una combinazione specifica (es. un incremento repentino dei prezzi alimentari WFP abbinato a un calo persistente del vigore vegetazionale NDVI per 3 mesi consecutivi) che precede storicamente l'impennata dei livelli di IPC 3+. La distanza geometrica delle nuove serie da questa Shapelet diventa la feature predittiva principale.

---

## Task 3.3 - Feature-Based Clustering (tsfresh) & Dissimilarità
* **tsfresh Feature Extraction**: Generazione automatica di centinaia di feature strutturali (coefficienti di Fourier, trend lineari, picchi, autocorrelazioni) per ciascuna serie temporale.
* **Feature Selection**: Applicazione del modulo di selezione basato su test di ipotesi di `tsfresh` per ridurre la dimensionalità e mantenere solo le feature strutturali correlate al target IPC3+.
* **CBD (Compression-Based Dissimilarity)**: Misura della dissimiliarità tra serie calcolando la comprimibilità delle serie concatenate, per catturare similitudini strutturali anche in presenza di forte rumore di fondo.

---

## Task 3.4 - Clustering Dinamico con DTW (Dynamic Time Warping)
* **Logica**: Allineamento flessibile dell'asse temporale. Se due province reagiscono allo stesso shock climatico o di mercato con 2 mesi di ritardo l'una rispetto all'altra, il DTW ne riconosce la somiglianza deformando il tempo.
* **Applicazione**: Creazione di "Cluster Funzionali" di comportamento dinamico tra regioni.

---

## Task 3.5 - Analisi di Stazionarietà e Differenziazione Automatica (Stazionarizzazione)
* **Logica**: I modelli temporali classici (ARIMA, VAR) richiedono che la serie storica sia stazionaria (media, varianza e struttura di autocorrelazione costanti nel tempo) per evitare regressioni spurie e stime errate.
* **Metodologia**:
  * Applicazione del test **Augmented Dickey-Fuller (ADF)** per testare l'ipotesi nulla di non-stazionarietà.
  * Se il test fallisce (p-value $\ge 0.05$), si applica in automatico la differenziazione temporale di primo ordine ($d=1$) o di secondo ordine ($d=2$).
  * Estrazione della componente stagionale, trend e residua mediante decomposizione **STL (Seasonal-Trend Decomposition using LOESS)**.

---

## Task 3.6 - Analisi di Cross-Correlazione con Lag (CCF)
* **Logica**: Misurare la relazione di lead-lag temporale tra i driver esogeni (es. anomalie delle precipitazioni o prezzi) e la risposta del target (IPC3+).
* **Metodologia**: Calcolo della funzione di cross-correlazione (CCF) per lag compresi tra $-12$ (il driver precede l'IPC di 12 mesi) e $+12$ mesi per individuare indicatori anticipatori.

---

## 📊 Grafici e Visualizzazioni per la FASE 3
* **Decomposizione STL (Observed, Trend, Seasonal, Residuals)**: Plot a 4 pannelli per illustrare visivamente la scomposizione della serie storica IPC.
* **Grafico ACF e PACF Comparativo (`02b_Compare_Series_Autocorrelation.png`)**: Pannello doppio che confronta i correlogrammi prima e dopo il processo di stazionarizzazione (differenziazione) per confermare la rimozione di trend e stagionalità.
* **Cross-Correlation Function Plot (`02c_Cross_Correlation_with_Target.png`)**: Grafico che traccia la correlazione per lag (da -12 a +12). Evidenzia visivamente a quale lag temporale si trova la massima correlazione (early-warning signal).
* **Allineamento Time Series + Matrix Profile**: Grafico a due pannelli sovrapposti. Il pannello superiore mostra la serie storica originale (es. prezzi del cibo) con gli shock evidenziati in rosso; il pannello inferiore mostra la curva del Matrix Profile con i minimi locali (Motifs) e i picchi massimi (Discords/Anomalie) chiaramente marcati.
* **Shapelet Alignment Plot**: Grafico a linee che mostra la serie temporale del driver esogeno con evidenziata in grassetto colorato la sezione in cui si è allineata la Shapelet predittiva, illustrando visivamente il "pattern precursore".
* **Dendrogramma Comparativo (DTW vs tsfresh)**: Due dendrogrammi affiancati (tanglegram) per confrontare visivamente come cambia il raggruppamento delle province se effettuato su base geometrica deformabile (DTW) o su feature strutturali (tsfresh).
* **Heatmap della Matrice di Distanza DTW**: Matrice simmetrica $N \times N$ colorata con scala divergente (viridis/inferno) che mostra la distanza di allineamento temporale tra tutte le coppie di province.
