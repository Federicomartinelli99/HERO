# Report Metodologico e Analisi Dettagliata: Benchmark Afghanistan (AFG)

Il presente documento fornisce una descrizione approfondita, teorica e applicativa, di tutte le analisi sulle serie temporali (esclusi forecasting e nowcasting) implementate per il paese benchmark **Afghanistan (AFG)**, in aderenza alle specifiche delle **Fasi 3 e 6** della roadmap del Progetto **HERO (Hunger Early-warning & Risk Optimizer)**.

Il codice sorgente e i relativi output sono archiviati nella directory `C:\Dev\Progetti\HERO\hero_v6\TS\TSindividual\`.

---

## 1. STRUTTURA DEL PROGETTO E RIORGANIZZAZIONE GERARCHICA

Per massimizzare l'esplorabilità, la manutenibilità e la modularità del codice e dei risultati, l'intera struttura è stata riorganizzata gerarchicamente:

```
TSindividual/
├── codes/
│   ├── config.py                   # Parametri globali, colonne e percorsi di output
│   ├── data_utils.py               # Loader dei dati unificati, mercati WFP e confini
│   ├── time_series_exploration.py  # Funzioni core per la Fase 3 (Stationarity, STL, CCF, etc.)
│   ├── frontier_techniques.py      # Funzioni core per la Fase 6 (Spatial network, Moran, LISA, DBSCAN)
│   ├── national_analysis.py        # Analisi aggregata a livello dell'intero paese
│   ├── run_individual_analysis.py  # Orchestratore principale che esegue l'intera pipeline
│   └── Analysis_AFG.ipynb          # Jupyter Notebook interattivo per l'esplorazione dei risultati
├── results/
│   ├── 01_stationarity_stl/        # Risultati ADF test e decomposizione STL provinciale
│   ├── 02_cross_correlation/       # Cross-correlazioni (CCF) tra target e driver con lag
│   ├── 03_matrix_profile/          # Discords e anomalie temporali via Stumpy
│   ├── 04_shapelets/               # Subsequenze e shapelets predittive sktime
│   ├── 05_catch22/                 # Estrazione feature strutturali tramite tsfresh e correlazioni
│   ├── 06_clustering_dtw_ncd/      # Clustering temporale con DTW, NCD e dendrogrammi
│   ├── 07_market_network/          # Analisi dei mercati WFP, grafo statico e HTML interattivo
│   ├── 08_spatial_autocorrelation/ # Moran's I globale e LISA cluster maps locali
│   ├── 09_dbscan_outliers/         # Rilevamento outlier spaziotemporali via DBSCAN
│   └── 10_national_level/          # Analisi temporale aggregata a livello nazionale
└── docs/
    └── report_benchmark_AFG.md     # Questo report metodologico dettagliato
```

---

## 2. PREPARAZIONE DEL DATASET E SCOPE DELL'ANALISI

L'obiettivo dell'analisi è studiare l'evoluzione spaziotemporale della sicurezza alimentare, espressa dal target `phase_3plus_percentage` (percentuale di popolazione in fase IPC 3 o superiore, che denota crisi o emergenza alimentare), in relazione a driver esogeni socio-economici, di conflitto e climatici.

### I Dati Utilizzati:
1. **Dataset Unificato Provinciale**: `merged_adm1_wide_norm_f_imputed.parquet`, contenente 926 osservazioni per l'Afghanistan suddivise tra le sue 34 province, coprendo un intervallo temporale che va da **luglio 2017 a ottobre 2025**. I driver esogeni includono:
   - **Precipitazioni**: Anomalie cumulate a 3 mesi (`rain_anomaly_3m`) e precipitazioni mensili (`rain_3m`).
   - **Conflitto**: Eventi di violenza politica normalizzati per 100.000 abitanti (`acled_political_violence_events_per_100k_population`).
   - **Spostamenti Interni**: Popolazione di sfollati interni rapportata alla popolazione totale provinciale (`idp_population_over_adm1_population`).
   - **Vigore Vegetativo**: Indice NDVI aggregato per area (`ndvi_vim`).
2. **Dati Alimentari ad Alta Frequenza**: `wfp_with_pcodes.parquet`, contenente 9.512 record mensili storici per **41 mercati alimentari distribuiti in Afghanistan**, dal 2007 al 2025.
3. **Geometrie Confini Geografici**: Confini amministrativi di livello 1 (province) caricati dal file GeoJSON `afg_admin1.geojson`.

---

## 3. METODOLOGIA E DETTAGLI DELLE ANALISI (FASE 3 - PROVINCIALE)

### 3.1 Analisi di Stazionarietà e Decomposizione STL (Task 3.1)
I modelli di analisi temporale classica e molti algoritmi di machine learning richiedono serie storiche stazionarie (ossia con media, varianza e struttura di autocorrelazione costanti nel tempo) per evitare regressioni spurie.

1. **Test di Stazionarietà (ADF)**:
   Per ciascuna delle 34 province, la serie del target `phase_3plus_percentage` e dei driver è stata sottoposta al test **Augmented Dickey-Fuller (ADF)**. L'ipotesi nulla ($H_0$) assume la presenza di una radice unitaria (non-stazionarietà).
   - Se il p-value risultante è $\ge 0.05$, la serie è considerata non-stazionaria.
   - Viene applicata una differenziazione temporale automatica di primo ordine ($d=1$): $y'_t = y_t - y_{t-1}$.
   - Se anche la serie differenziata fallisce il test, si applica una differenziazione di secondo ordine ($d=2$).
   - I risultati dettagliati (p-value originari, finali e ordine di differenziazione) sono esportati nel file [adf_stationarity_results.csv](file:///C:/Dev/Progetti/HERO/hero_v6/TS/TSindividual/results/01_stationarity_stl/adf_stationarity_results.csv).
2. **Decomposizione STL**:
   Ogni serie provinciale del target è stata decomposta tramite **STL (Seasonal-Trend Decomposition using LOESS)** con una stagionalità impostata a 12 mesi per catturare i cicli annuali agricoli. La scomposizione estrae tre componenti additive:
   $$Y_t = T_t + S_t + R_t$$
   dove $T_t$ è il trend di lungo termine, $S_t$ è la componente stagionale e $R_t$ rappresenta il residuo (rumore o shock).
   - I plot a 4 pannelli sono stati generati e salvati per le 4 province di benchmark nella cartella [01_stationarity_stl/](file:///C:/Dev/Progetti/HERO/hero_v6/TS/TSindividual/results/01_stationarity_stl/).
   - I correlogrammi ACF (Autocorrelation Function) e PACF (Partial Autocorrelation Function) prima e dopo il processo di differenziazione sono stati salvati per verificare visivamente l'avvenuta rimozione dei trend.

### 3.2 Analisi di Cross-Correlazione con Lag (Task 3.2)
Per comprendere come le variabili esogene influenzino l'insorgere delle crisi alimentari, è stata calcolata la funzione di cross-correlazione (CCF) tra ciascun driver e il target per lag temporali compresi tra **$-12$ mesi e $+12$ mesi**.
- Un lag positivo $k > 0$ indica che il valore del driver al tempo $t$ correla con il target al tempo $t+k$ (il driver anticipa il target: segnale di early-warning).
- La tabella riassuntiva è salvata in [02c_Cross_Correlation_with_Target.csv](file:///C:/Dev/Progetti/HERO/hero_v6/TS/TSindividual/results/02_cross_correlation/02c_Cross_Correlation_with_Target.csv). I grafici individuali mostrano la dinamica anticipatoria (es. le anomalie delle piogge precedono di 3-4 mesi il picco di crisi, mentre l'inflazione dei mercati ha un effetto anticipatore di 1-2 mesi).

### 3.3 Rilevamento di Anomalie via Matrix Profile (Task 3.3)
Utilizzando la libreria **`stumpy`**, è stato calcolato il Matrix Profile sulle serie storiche dei driver principali (`wfp_price` e `rain_anomaly_3m`) per le province rappresentative, impostando una finestra temporale di $m=12$ mesi (finestra annuale classica).
- **Matrix Profile**: Rappresenta la distanza euclidea tra ogni sottosequenza della serie e il suo vicino più prossimo (escludendo se stessa).
- **Discords (Anomalie)**: I picchi massimi nel Matrix Profile indicano sottosequenze che non hanno riscontri simili nella storia della serie, corrispondenti a shock strutturali.
- I risultati grafici sono salvati in [03_matrix_profile/](file:///C:/Dev/Progetti/HERO/hero_v6/TS/TSindividual/results/03_matrix_profile/).

### 3.4 Estrazione di Shapelets Predittive (Task 3.4)
Le shapelets sono sottosequenze temporali brevi e altamente discriminanti che precedono storicamente variazioni repentine del target.
- Abbiamo implementato una routine per identificare i punti di "surge" (impennata dell'insicurezza alimentare, definita come un aumento di `phase_3plus_percentage` $> 5\%$ in un intervallo di 3 mesi).
- È stata estratta una shapelet di lunghezza $L=6$ mesi sui driver nei mesi precedenti a questo surge.
- Facendo scorrere questa shapelet sulla serie storica dei driver, è stata calcolata la distanza euclidea z-normalizzata (Distance Profile) per visualizzare l'allineamento temporale del "pattern precursore". I plot di allineamento sono salvati in [04_shapelets/](file:///C:/Dev/Progetti/HERO/hero_v6/TS/TSindividual/results/04_shapelets/).

### 3.5 Feature Extraction Strutturale via tsfresh (Task 3.5)
La libreria **`tsfresh`** (con la configurazione `EfficientFCParameters` per estrarre in modo rapido ma esaustivo centinaia di caratteristiche) è stata adottata al posto della libreria Catch22 per caratterizzare le serie temporali provinciali del target `phase_3plus_percentage`.
- Sono stati estratti **777 descrittori strutturali** (comprendenti coefficienti FFT, autocorrelazioni a diversi lag, stime di entropia, asimmetrie distributive, trend lineari interni, etc.) per ciascuna provincia.
- Le feature sono state imputate per rimuovere eventuali valori non definiti (NaN).
- È stata calcolata la correlazione di ciascuna caratteristica con il livello medio storico provinciale di IPC3+ per individuare quali proprietà dinamiche sono maggiormente associate alla vulnerabilità cronica.
- I risultati sono salvati in [tsfresh_feature_correlations.csv](file:///C:/Dev/Progetti/HERO/hero_v6/TS/TSindividual/results/05_catch22/tsfresh_feature_correlations.csv) e visualizzati nel grafico [tsfresh_top_correlations.png](file:///C:/Dev/Progetti/HERO/hero_v6/TS/TSindividual/results/05_catch22/tsfresh_top_correlations.png).

### 3.6 Distanze Temporali e Clustering Dinamico (Task 3.6)
Per raggruppare le province in "archetipi di vulnerabilità dinamica" (ossia province che reagiscono in modo simile nel tempo agli shock), sono state calcolate le matrici di distanza inter-provinciale:
1. **Dynamic Time Warping (DTW)**: Calcola la distanza z-normalizzata allineando in modo flessibile l'asse temporale tramite una finestra di Sakoe-Chiba ($w=4$ mesi) per gestire risposte ritardate agli stessi shock.
2. **Normalized Compression Distance (NCD)**: Misura la dissimilarità basata sulla comprimibilità incrociata delle sequenze di dati (utilizzando gzip).
- Sulla matrice di distanza DTW è stato applicato il clustering gerarchico con algoritmo di legame Ward, suddividendo il paese in **3 cluster principali**.
- **Visualizzazioni Prodotte**:
  - **Dendrogramma**: Mostra la gerarchia di aggregazione delle province ([global_regions_dendrogram_shape.png](file:///C:/Dev/Progetti/HERO/hero_v6/TS/TSindividual/results/06_clustering_dtw_ncd/global_regions_dendrogram_shape.png)).
  - **Proiezione PCA**: Disperde bidimensionalmente i cluster temporali delle province ([global_regions_pca_scatter.png](file:///C:/Dev/Progetti/HERO/hero_v6/TS/TSindividual/results/06_clustering_dtw_ncd/global_regions_pca_scatter.png)).
  - **Mappa Geografica dei Cluster**: Mostra la contiguità spaziale dei profili dinamici estratti ([global_regions_map.png](file:///C:/Dev/Progetti/HERO/hero_v6/TS/TSindividual/results/06_clustering_dtw_ncd/global_regions_map.png)).

---

## 4. METODOLOGIA E DETTAGLI DELLE ANALISI (FASE 6 - FRONTIER TECHNIQUES)

### 4.1 Network Analysis dei Mercati Alimentari (Task 6.1)
L'analisi di rete studia la trasmissione spaziale e temporale degli shock dei prezzi alimentari tra i 41 mercati dell'Afghanistan.

1. **Costruzione della Rete**:
   - Abbiamo estratto le serie storiche mensili dei prezzi per ciascun mercato.
   - È stata calcolata la matrice di correlazione di Pearson tra tutte le coppie di mercati.
   - Per evidenziare solo i canali di integrazione commerciale più forti e stabili ed evitare un sovraffollamento visivo della rete, abbiamo impostato una **soglia di correlazione $r > 0.90$** (innalzata rispetto alla baseline originaria di $0.7$).
2. **Mappa Rete Statica (PNG)**:
   - Invece di utilizzare layout astratti (es. layout a molla spring), abbiamo impostato la posizione spaziale dei nodi della rete (`pos`) utilizzando le **coordinate geografiche reali (longitudine e latitudine)** dei mercati storici.
   - La rete è stata disegnata in sovrapposizione alla mappa delle province afghane (colorate con toni pastello per evidenziare le regioni amministrative).
   - I nodi sono stati etichettati con il nome del mercato e racchiusi in box semi-trasparenti bianchi per la massima leggibilità.
   - Lo spessore e il colore degli archi indicano la forza del collegamento commerciale ($r \ge 0.95$ evidenziati in arancione spesso; $0.90 \le r < 0.95$ in grigio sottile).
   - La dimensione dei nodi è proporzionale alla loro **Betweenness Centrality**.
   - I risultati di centralità (Degree e Betweenness) sono salvati in [wfp_market_centralities.csv](file:///C:/Dev/Progetti/HERO/hero_v6/TS/TSindividual/results/07_market_network/wfp_market_centralities.csv) e la mappa finale in [market_network_graph.png](file:///C:/Dev/Progetti/HERO/hero_v6/TS/TSindividual/results/07_market_network/market_network_graph.png).
3. **Mappa Rete Interattiva (HTML)**:
   - Per analizzare come cambia la topologia della rete e come si trasmettono i prezzi al variare di $r$, è stato creato un tool interattivo HTML standalone: [interactive_network.html](file:///C:/Dev/Progetti/HERO/hero_v6/TS/TSindividual/results/07_market_network/interactive_network.html).
   - Sviluppato utilizzando **Leaflet.js** con base map scura CartoDB Positron per un look premium e moderno.
   - Integra i vettori GeoJSON semplificati dell'Afghanistan per mostrare i confini delle province colorati dinamicamente.
   - Contiene uno **slider interattivo** che permette di variare la soglia $r$ da $0.70$ (integrazione nazionale ad ampio raggio) a $0.98$ (mercati ad accoppiamento quasi perfetto).
   - Calcola in tempo reale le statistiche della rete (Numero di collegamenti attivi, Grado medio della rete) e ridimensiona i nodi e i collegamenti in base al valore impostato sul pannello laterale (glassmorphism design).

### 4.2 Autocorrelazione Spaziale - Moran's I & LISA (Task 6.2)
Questa analisi verifica in modo formale e quantitativo la presenza di contagio geografico e dipendenza spaziale nelle crisi alimentari dell'Afghanistan.

1. **Matrice dei Pesi Spaziali ($W$)**:
   Utilizzando `libpysal`, è stata generata una matrice di contiguità spaziale di tipo **Queen** basata sui confini geometrici delle province. La matrice è stata normalizzata per riga (row-standardized).
2. **Moran's I Globale**:
   Misura l'autocorrelazione spaziale globale.
   - Il valore calcolato per l'Afghanistan è pari a **$0.318$** con uno **Z-score di $3.19$** e un **p-value = $0.0014$**.
   - Essendo il p-value ampiamente inferiore alla soglia critica di $0.05$, si rifiuta l'ipotesi nulla di casualità spaziale. Questo dimostra rigorosamente che l'insicurezza alimentare in Afghanistan è un fenomeno a forte impronta geografica.
   - Il grafico di regressione è salvato in [moran_scatterplot.png](file:///C:/Dev/Progetti/HERO/hero_v6/TS/TSindividual/results/08_spatial_autocorrelation/moran_scatterplot.png).
3. **Local Moran's I (LISA)**:
   Gli indicatori locali di associazione spaziale (LISA) identificano singoli agglomerati locali significativi ($p < 0.05$):
   - **High-High (Hot Spot)**: Rilevati nel quadrante sud-ovest (es. Kandahar, Hilmand).
   - **Low-Low (Cold Spot)**: Rilevate in alcune aree settentrionali (es. Balkh).
   - La mappa LISA è salvata in [lisa_cluster_map.png](file:///C:/Dev/Progetti/HERO/hero_v6/TS/TSindividual/results/08_spatial_autocorrelation/lisa_cluster_map.png).

### 4.3 Outlier Rilevamento via DBSCAN (Task 6.4)
Per individuare aree di anomalia congiunta spaziale e temporale (es. province geograficamente vicine che mostrano andamenti strutturali delle serie temporali completamente differenti):
- Abbiamo combinato le coordinate geografiche (latitudine e longitudine dei centroidi delle province) con le feature strutturali `tsfresh` estratte in precedenza.
- Le feature sono state normalizzate e fornite in input all'algoritmo **DBSCAN** (`eps=2.5`, `min_samples=3`).
- I punti classificati come rumore ($label = -1$) sono stati identificati come outlier spaziotemporali.
- Queste province (esportate in [dbscan_spatial_outliers.csv](file:///C:/Dev/Progetti/HERO/hero_v6/TS/TSindividual/results/09_dbscan_outliers/dbscan_spatial_outliers.csv)) rappresentano anomalie locali non spiegabili dalla sola vicinanza geografica. La mappa è disponibile in [dbscan_spatial_outliers.png](file:///C:/Dev/Progetti/HERO/hero_v6/TS/TSindividual/results/09_dbscan_outliers/dbscan_spatial_outliers.png).

---

## 5. ANALISI DI LIVELLO NAZIONALE (AGGREGATA - TASK 7.0)

Per comprendere le macro-dinamiche dell'intero paese e separare i trend locali dai movimenti sistemici nazionali, è stata creata una routine di analisi a livello aggregato nazionale:

1. **Aggregazione**: Group-by mensile e calcolo dei valori medi nazionali di target e driver. I risultati della serie aggregata sono archiviati in [national_aggregated_series.csv](file:///C:/Dev/Progetti/HERO/hero_v6/TS/TSindividual/results/10_national_level/national_aggregated_series.csv).
2. **Decomposizione STL e Stazionarietà**:
   - Il test ADF indica se la serie nazionale è stazionaria. Risultati salvati in [national_adf_stationarity.csv](file:///C:/Dev/Progetti/HERO/hero_v6/TS/TSindividual/results/10_national_level/national_adf_stationarity.csv).
   - Decomposizione STL a 12 mesi per visualizzare il trend nazionale dell'insediamento di insicurezza e i cicli stagionali a livello di paese ([national_STL_decomposition.png](file:///C:/Dev/Progetti/HERO/hero_v6/TS/TSindividual/results/10_national_level/national_STL_decomposition.png)).
3. **Cross-Correlazioni Nazionali (CCF)**:
   - Calcolo delle funzioni di cross-correlazione tra i driver aggregati e il target per lag compresi tra $-12$ e $+12$ mesi.
   - Salvato in [national_cross_correlations.csv](file:///C:/Dev/Progetti/HERO/hero_v6/TS/TSindividual/results/10_national_level/national_cross_correlations.csv) e graficato in [national_CCF_plots.png](file:///C:/Dev/Progetti/HERO/hero_v6/TS/TSindividual/results/10_national_level/national_CCF_plots.png).
4. **Matrix Profile Nazionale**:
   - Applicazione di Stumpy a livello paese per evidenziare le anomalie storiche aggregate (motivi di shock nazionali). I plot sono archiviati in [national_Matrix_Profile_wfp_price.png](file:///C:/Dev/Progetti/HERO/hero_v6/TS/TSindividual/results/10_national_level/national_Matrix_Profile_wfp_price.png) e [national_Matrix_Profile_rain_anomaly_3m.png](file:///C:/Dev/Progetti/HERO/hero_v6/TS/TSindividual/results/10_national_level/national_Matrix_Profile_rain_anomaly_3m.png).
5. **Shapelets Nazionali**:
   - Identificazione di pattern precursori nazionali di surge dell'insicurezza alimentare ([national_shapelet_wfp_price.png](file:///C:/Dev/Progetti/HERO/hero_v6/TS/TSindividual/results/10_national_level/national_shapelet_wfp_price.png) e [national_shapelet_rain_anomaly_3m.png](file:///C:/Dev/Progetti/HERO/hero_v6/TS/TSindividual/results/10_national_level/national_shapelet_rain_anomaly_3m.png)).
6. **Feature tsfresh Nazionali**:
   - Caratterizzazione della forma e della struttura della dinamica nazionale tramite tsfresh, salvata in [national_tsfresh_features.csv](file:///C:/Dev/Progetti/HERO/hero_v6/TS/TSindividual/results/10_national_level/national_tsfresh_features.csv).

---

## 6. CONCLUSIONI E IMPLICAZIONI PER IL MODELLO HERO

L'analisi del benchmark Afghanistan fornisce preziose indicazioni per lo sviluppo futuro della modellazione predittiva:
1. **L'importanza dello Spazio**: L'elevata autocorrelazione spaziale (Moran's I = 0.318) indica che i modelli di forecast temporale non dovrebbero essere puramente locali, ma dovrebbero integrare feature spaziali (lag spaziali o coordinate lat/lon) per migliorare l'accuratezza predittiva.
2. **Integrazione dei Mercati**: La forte integrazione della rete dei mercati (prezzi WFP altamente correlati nationwide) suggerisce che gli indicatori di prezzo nazionali o di hub principali (es. Kabul) possono servire come proxy validi ed efficaci anche per province isolate prive di rilevazioni dirette dei prezzi.
3. **Caratteristiche Strutturali**: Le caratteristiche estratte tramite tsfresh catturano proprietà fondamentali delle serie temporali (come tendenze a lungo termine, entropie ed asimmetrie) che consentono a DBSCAN di separare in maniera chiara le province stabili da quelle soggette a shock improvvisi.
4. **Analisi Nazionale vs. Provinciale**: L'analisi di livello nazionale consente di eliminare il rumore locale e isolare la dinamica strutturale dell'insicurezza alimentare in Afghanistan, mostrando un accoppiamento molto più chiaro e coerente con le grandi anomalie delle piogge e degli shock inflazionistici dei mercati.
