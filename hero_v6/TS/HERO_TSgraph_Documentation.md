# HERO - TSgraph (Time Series Graph Analysis)
**Documentazione di Progetto e Riepilogo Funzionalità**

Questo documento riassume nel dettaglio l'architettura, le implementazioni e le logiche sviluppate per il modulo **TSgraph** all'interno del progetto HERO. Il modulo è composto da una pipeline di data processing in Python e da una Dashboard analitica interattiva basata su tecnologie web.

---

## 1. Pipeline di Data Processing (Backend in Python)
Tutta l'elaborazione dei dati grezzi e l'estrazione delle reti complesse avviene tramite script Python situati in `TSgraph/codes`.

### `01-dataExport.py`
Questo script è il motore computazionale che trasforma le serie storiche dei prezzi in Reti Spaziali (Spatial Networks). Le operazioni principali includono:
- **Ingestion & Pulizia:** Caricamento dei dati spaziali e temporali dal dataset globale WFP (formato `.parquet`). Pulizia dei missing values, raggruppamento per mercato e allineamento temporale (resampling mensile).
- **Log-Returns:** Trasformazione dei prezzi base in rendimenti logaritmici (`log-diff`) per garantire la stazionarietà delle serie storiche, passaggio fondamentale per l'analisi statistica.
- **Calcolo Metriche Pairwise:** Tra ogni coppia di mercati (nodi) vengono calcolate tre diverse metriche di dipendenza/connessione su vari *time-lags* (ritardi temporali da 0 a 3 mesi):
  1. **Pearson Correlation:** Per catturare le dipendenze lineari istantanee o ritardate.
  2. **Mutual Information (MI):** Per catturare la dipendenza non lineare non direzionata tramite entropia di Shannon.
  3. **Symbolic Transfer Entropy (STE):** Una formulazione avanzata dell'entropia di trasferimento. I valori di prezzo vengono convertiti in "simboli" prima di calcolare le probabilità congiunte, misurando il flusso di informazione **direzionato** in modo altamente robusto al rumore.
- **Esportazione JSON Dinamica:** Generazione di file JSON per ogni paese elaborato, contenenti i dati dei nodi (serie temporali, coordinate) e degli archi (metriche, p-values calcolati tramite permutazioni, distanze geodetiche). Il sistema esporta autonomamente tutti i paesi presenti nel dataset, aggiornando un file `countries_list.json` per mantenere sincronizzata la dashboard.

---

## 2. Dashboard Analitica e UI (Frontend Web)
L'interfaccia, situata in `TSgraph/UI/`, è costruita con HTML, Vanilla JS, CSS (Design System Glassmorphism), Leaflet (mappe spaziali) e Plotly.js (grafici statistici).

### Esplorazione Spaziale e Filtraggio
- **Gestione Dinamica delle Soglie:** Gli utenti possono sfoltire il grafo in tempo reale basandosi su:
  - **Soglia Fissa (Fixed):** Es. mostrare solo archi con $Pearson \ge 0.92$.
  - **Soglia Topologica (Top %):** Mantenere solo la percentuale dei link più forti per preservare la densità e la forma strutturale.
- **Filtri di Significatività e Lag:** Possibilità di scartare automaticamente i collegamenti con p-value $> 0.05$ e di switchare fluidamente tra gli impatti ritardati (Lag 0, 1, 2, 3) esplorando i tre modelli statistici.

### Analisi Topologica e Benchmark Models (In-Browser)
Il motore Javascript genera istantaneamente grafi artificiali con lo *stesso identico numero di nodi e archi* della rete empirica attualmente filtrata:
- **Erdős-Rényi (ER):** Benchmark casuale.
- **Watts-Strogatz (WS):** Per valutare la natura "Small-World".
- **Barabási-Albert (BA):** Per testare la presenza di Scale-Free networks.
- I valori topologici tra i grafi empirici e artificiali (Average Degree, Clustering Coefficient e Shortest Path Length) vengono ricalcolati live in una tabella comparativa.

### Metriche Globali e Hub
Vengono calcolate live e mostrate nel pannello "Topology Info":
- Numero di componenti e nodi isolati, percentuale del Giant Component e l'Assortativity Coefficient (r).
- Identificazione dei mercati centrali basata su **Degree Centrality** (Top Hubs) e **Closeness Centrality** (BFS-based Shortest Paths).

---

## 3. Highlighting Bi-Direzionale e Analisi Grafica
Il lato destro della UI ospita 3 grafici Plotly con fitting analitico, progettati per avere una sinergia totale e bidirezionale con la mappa interattiva Leaflet:

1. **Distance Decay:** Scatter plot (Distanza Fisica vs Peso della connessione) con Fitting Esponenziale automatico ($W \sim e^{-\lambda d}$).
2. **Degree Distribution:** Bar Chart (Grado $k$ vs Numero di mercati) scalabile lin/log con Fitting Power-Law ($P(k) \sim k^{-\alpha}$).
3. **Assortativity Analysis (Toggle):** 
   - Grafico $k$ vs $K_{nn}$ con fitting Power-Law.
   - Scatter plot simmetrico $k_1$ vs $k_2$ con bisettrice $y=x$ per valutare visivamente l'omofilia della rete.

**Cross-Highlighting Magico:**
- **Dal Grafico alla Mappa:** Cliccando un segmento dello Scatter plot o una barra dell'istogramma in Plotly, Javascript seleziona fisicamente gli archi spaziali o i nodi corrispondenti, colorandoli d'oro e ingrandendoli all'interno della mappa geografica.
- **Dalla Mappa al Grafico:** Viceversa, cliccando i nodi geografici (o i loro nomi testuali nel pannello Hubs) o le polilinee di interconnessione in Leaflet, viene scatenato un evento che inietta uno speciale layer Plotly sui grafici, posizionando un marker visivo (❌) che aiuta l'utente a capire istantaneamente se il link selezionato spazialmente corrisponda a un "outlier" statistico.
