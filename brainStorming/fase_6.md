# FASE 6: Tecniche di Frontiera (Integrazione TSMDA & DMML)

---

## 1. Network Analysis Classica (NetworkX) e Autocorrelazione Spaziale
* **Rete di Integrazione dei Mercati (WFP)**:
  * **Concetto**: Rappresentare il sistema di scambio e distribuzione alimentare come una rete in cui i nodi sono i mercati fisici (o le province) e gli archi rappresentano la correlazione temporale dei prezzi dei beni alimentari di base.
  * **Granularità Temporale**: Al fine di studiare l'integrazione e la propagazione degli shock con massima fedeltà e catturare i tempi di reazione (lags) rapidi dei mercati, **l'analisi di rete viene eseguita mantenendo la risoluzione temporale nativa non aggregata dei prezzi WFP** (es. frequenza settimanale o giornaliera originale), senza forzarli alla risoluzione mensile del target IPC.
  * **Applicazione**: Utilizzo della libreria `NetworkX` per calcolare metriche di centralità (*Degree Centrality*, *Betweenness Centrality*). Questo consente di individuare empiricamente i mercati "hub" o di transito precisi che, se colpiti da uno shock sui prezzi, propagano l'inflazione alle aree adiacenti.
* **Autocorrelazione Spaziale (Moran's I & LISA)**:
  * **Concetto**: Verificare quantitativamente se la gravità dell'insicurezza alimentare di una provincia sia influenzata dalla vicinanza geografica con province colpite da crisi (effetto contagio).
  * **Applicazione**: Calcolo dell'indice di Moran globale (*Moran's I*) per validare la presenza di autocorrelazione spaziale dell'IPC3+, e della mappa LISA (*Local Indicators of Spatial Association*) per identificare cluster spaziali di insicurezza (aree High-High o Low-Low).

---

## 2. Zero-Shot Forecasting con Foundation Models (TimesFM)
* **Concetto**: Applicazione del modello pre-addestrato di Google `TimesFM` per effettuare previsioni zero-shot sulle serie temporali IPC di territori privi di storico sufficiente.
* **Obiettivo**: Valutare se modelli generalisti pre-addestrati superano i modelli statistici tradizionali in contesti fragili.

---

## 3. Spatial Outlier Detection via DBSCAN
* **Metodologia**: Applicazione di DBSCAN sul dataset spaziotemporale delle feature strutturali.
* **Applicazione**: Identificare province atipiche (outliers/rumore per DBSCAN) che, pur trovandosi all'interno di una determinata area geografica colpita da crisi, mostrano dinamiche di resistenza o andamenti discordanti. Questo permette di isolare fattori di resilienza locale.

---

## 4. Clustering basato su Compressione NCD (Normalized Compression Distance)
* **Logica**: Clustering temporale alternativo al DTW basato sulla comprimibilità incrociata delle sequenze di dati.
* **Applicazione**: Generare raggruppamenti di nazioni/regioni indipendentemente dalla scala o dal rumore geometrico.

---

## 📊 Grafici e Visualizzazioni per la FASE 6
* **Grafo di Integrazione dei Mercati (NetworkX)**: Rappresentazione visiva della rete dei mercati alimentari. I nodi hanno dimensioni proporzionali alla loro centralità (*Betweenness Centrality*) e gli archi hanno uno spessore proporzionale alla correlazione temporale dei prezzi, evidenziando le rotte principali di contagio economico.
* **Moran Scatterplot & Mappa LISA**: Grafico a dispersione che mostra la relazione tra il valore IPC3+ di una provincia e la media spaziale delle province confinanti. La mappa LISA colora le province evidenziando i cluster significativi (es. rosso per High-High, blu per Low-Low) e gli outlier spaziali.
* **TimesFM Zero-Shot Comparison Plot**: Grafico a linee che confronta la predizione a 6-12 mesi di TimesFM (senza addestramento locale) contro il reale andamento storico e contro la baseline locale ARIMA, per evidenziare visivamente la qualità del modello foundation.
* **DBSCAN Outlier Map/Scatter**: Grafico a dispersione PCA in cui i punti del rumore (outliers spaziali identificati da DBSCAN) sono colorati in rosso vivo su uno sfondo di cluster colorati in toni pastello, evidenziando geograficamente le anomalie di resilienza.
* **Heatmap delle Distanze di Compressione NCD**: Matrice simmetrica delle distanze basate sulla compressione delle stringhe/dati per visualizzare la dissimilarità globale.
