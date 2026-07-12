# Checklist di Sviluppo - FASE 6: Tecniche di Frontiera (TSMDA & DMML)

Questo documento contiene i dettagli implementativi e la checklist per la **Fase 6**. L'obiettivo è implementare modelli e analisi avanzate (Network Analysis, TimesFM e DBSCAN) per arricchire il valore scientifico del progetto.

---

## 📋 Task List

### `[ ]` Task 6.1: Network Analysis Classica dei Mercati Alimentari (NetworkX)
* **Descrizione**: Rappresentare il sistema dei prezzi alimentari come una rete e calcolare le metriche di trasmissione degli shock.
* **Sotto-task**:
  * `[ ]` Filtrare i dati dei mercati WFP mantenendo la **risoluzione temporale nativa non aggregata** (es. settimanale o data transazione originale), evitando la contrazione a livello mensile `MS` per preservare i lag rapidi.
  * `[ ]` Calcolare la matrice di correlazione temporale dei prezzi tra tutte le coppie di mercati usando le serie storiche ad alta frequenza.
  * `[ ]` Costruire il grafo: i mercati sono i nodi; inserire un arco tra due nodi solo se il valore di correlazione supera una soglia definita (es. $r > 0.7$).
  * `[ ]` Utilizzare `NetworkX` per calcolare:
    * `[ ]` **Degree Centrality**: identificare i mercati più connessi.
    * `[ ]` **Betweenness Centrality**: identificare i mercati ponte che fungono da corridoi di trasmissione del rincaro dei prezzi.
  * `[ ]` Salvare la struttura del grafo ed esportare il disegno della rete.

---

### `[ ]` Task 6.2: Autocorrelazione Spaziale (Moran's I & LISA)
* **Descrizione**: Misurare formalmente l'effetto di vicinato e contagio geografico della crisi alimentare.
* **Sotto-task**:
  * `[ ]` Caricare i GeoJSON provinciali e allinearli al DataFrame dei dati IPC3+.
  * `[ ]` Calcolare la matrice dei pesi spaziali (contiguità Queen o Rook) usando la libreria `libpysal`.
  * `[ ]` Calcolare l'indice globale di **Moran's I** per testare la significatività dell'autocorrelazione spaziale dell'IPC3+ nel tempo.
  * `[ ]` Calcolare gli indicatori locali di associazione spaziale (**LISA**) per classificare ogni provincia in cluster spaziali significativi (High-High, Low-Low, High-Low, Low-High).
  * `[ ]` Salvare la mappa dei cluster LISA ed il Moran Scatterplot.

---

### `[ ]` Task 6.3: Zero-Shot Forecasting con TimesFM (Google Foundation Model)
* **Descrizione**: Testare il modello pre-addestrato di Google per il forecast out-of-sample senza addestramento locale.
* **Sotto-task**:
  * `[ ]` Installare e configurare l'ambiente di runtime per `TimesFM`.
  * `[ ]` Caricare le serie storiche IPC3+ provinciali e formattarle secondo i requisiti di TimesFM (input length, context length, horizon).
  * `[ ]` Invocare TimesFM in modalità *Zero-Shot* per generare previsioni a 6 mesi.
  * `[ ]` Calcolare gli errori di forecast (MAE, RMSE) sul test set.

---

### `[ ]` Task 6.4: Spatial Outlier Detection via DBSCAN
* **Descrizione**: Isolare anomalie di resilienza geografica identificando province con dinamiche atipiche rispetto al loro vicinato.
* **Sotto-task**:
  * `[ ]` Costruire la matrice delle feature aggregando le coordinate lat/lon standardizzate e i descrittori delle serie storiche (tsfresh).
  * `[ ]` Inizializzare ed applicare **DBSCAN** impostando opportunamente i parametri `eps` e `min_samples`.
  * `[ ]` Identificare i punti classificati come rumore/outliers ($label = -1$).
  * `[ ]` Mappare geograficamente questi outliers per individuare le province che mostrano andamenti discordanti (es. province resilienti pur circondate da siccità o guerra).
  * `[ ]` Salvare i risultati in `ML/results/frontier_techniques/`.
