# Documentazione Analisi Semantic Clustering: Report IPC (Insicurezza Alimentare)

Questo documento descrive la pipeline di Natural Language Processing (NLP) implementata nel notebook `Clustering.ipynb` per il partizionamento semantico dei report sull'insicurezza alimentare, al fine di individuare pattern non visibili se i dati fossero suddivisi solo per area geografica.

---

## 1. Obiettivo e Caricamento Dati
Il processo prende in input il dataset elaborato nella fase di ablazione spaziotemporale (`report_anonimizzati_ok.csv`). L'obiettivo è sfruttare embedding densi e modelli non supervisionati per raggruppare i report in base a driver causali (es: scarsità di piogge, malattie del bestiame, pandemia, tensioni economiche) e non in base allo stato o all'anno in cui il report è stato redatto.

L'elaborazione coinvolge 497 documenti.

---

## 2. Esperimenti di Embedding
Sono stati eseguiti due distinti esperimenti di embedding, valutando modelli differenti, con l'obiettivo di trovare la migliore separazione semantica tra i report:

### 2.1 Embedding su Testi Originali vs. Testi Anonimizzati
Il primo esperimento ha testato l'impatto dell'anonimizzazione. È stato effettuato un clustering sui **testi originali** (contenenti nomi di paesi, regioni e date esatte) e un altro clustering sui **testi anonimizzati** (in cui le entità geografiche e temporali sono state rimosse e sostituite con tag). I risultati hanno dimostrato chiaramente che l'uso dei testi anonimizzati riduce drasticamente il bias geografico, consentendo ai modelli di raggruppare i documenti in base ai reali fattori di crisi e non alla semplice menzione dello stesso Paese.

### 2.2 Confronto tra Modelli di Embedding (Nomic vs. BGE-M3)
Un secondo esperimento si è concentrato sul confronto tra architetture di embedding. 
*   **Esperimento con `nomic-ai/nomic-embed-text-v1.5`**: Questo modello è stato testato come potenziale soluzione ad alta efficienza per catturare le sfumature semantiche dei report.
*   **Esperimento con `BAAI/bge-m3`**: Questo modello multilingue, capace di gestire contesti fino a 8192 token, è stato valutato parallelamente. La pipeline finale adotta BGE-M3, ritenuto più idoneo a processare documenti lunghi e a mantenere un forte allineamento semantico (es. equiparando "scarsità d'acqua" a "siccità prolungata"). I vettori a **1024 dimensioni** generati da BGE-M3, dopo la rimozione dei tag di pulizia `[AFFECTED_AREA]` e `[DATE]`, sono stati salvati come formato Numpy (`.npy`).

---

## 3. Riduzione Dimensionale (UMAP)
La pipeline sfrutta l'algoritmo **UMAP (Uniform Manifold Approximation and Projection)** per due scopi differenti:
1.  **Clustering (5 Dimensioni)**: Ridurre i vettori da 1024 a 5 dimensioni mitiga la cosiddetta "Maledizione della Dimensionalità" (Curse of Dimensionality), permettendo a modelli come K-Means o HDBSCAN di calcolare distanze più significative tra i punti.
2.  **Visualizzazione (2 Dimensioni)**: Viene addestrato un secondo UMAP per comprimere lo spazio a 2 dimensioni, che verrà usato nelle fasi successive per produrre scatter plot.

La metrica spaziale utilizzata è la *Coseno Similarità*.

---

## 4. Clustering e Valutazione

Vengono testati e valutati due differenti approcci di partizionamento:

### 4.1. K-Means
Viene esplorato un range di cluster $K$ (da 2 a 12). Per identificare il numero ottimale, vengono calcolate tre metriche geometriche:
*   **Inerzia (WCSS)**: Ricerca del punto di "gomito".
*   **Silhouette Score**: Valuta la compattezza e la separazione dei cluster.
*   **Davies-Bouldin Index**: Misura la dispersione intra-cluster rispetto alla distanza inter-cluster.

Sulla base delle metriche, viene stabilito un $K$ ottimale di partenza (nell'esempio: $K=7$).

### 4.2. HDBSCAN
Come approccio basato sulla densità, HDBSCAN raggruppa dinamicamente i report, ignorando quelli che appaiono come rumore (outlier). Questo è particolarmente utile per documenti ambigui o che trattano molteplici driver isolati.
Con i parametri settati, il modello identifica circa **11 cluster** e classifica **171 documenti come rumore (`-1`)**.

---

## 5. Analisi Semantica e Topic Modeling

Per identificare in modo accurato il tema dominante di ciascun cluster, l'analisi semantica è stata strutturata in due fasi interconnesse, supportate da un LLM (Gemini):

### 5.1 Estrazione Feature C-TF-IDF e Identificazione Keyword
Per identificare le parole che caratterizzano maggiormente ogni cluster, viene utilizzato un approccio **Class-based TF-IDF** (ispirato a BERTopic). I documenti di uno stesso cluster vengono concatenati in un "macro-documento". 
Il testo subisce un filtraggio estremo tramite `NLTK`, che rimuove:
*   Stop-words inglesi.
*   Nomi dei Paesi.
*   Terminologia IPC standard (es. `percent`, `phase`, `million`, `people`, `crisis`) che non apporta valore informativo sui *driver* della crisi.

Questo processo isola le vere keyword causali. 

Esempi di driver reali rilevati (su cluster K-Means):
*   **Cluster 4**: *conflict, humanitarian, catastrophe, refugee, access*
*   **Cluster 2**: *price, season, crop, harvest, rainfall*
*   **Cluster 3**: *covid, pandemic, impact, income*

### 5.2 Etichettatura Semantica e Validazione tramite LLM (Gemini)
Per trasformare le liste di parole chiave in etichette semantiche descrittive e verificabili, la pipeline ha integrato un modello LLM (Gemini) come giudice:
1.  **Generazione dell'Etichetta**: Le 10 parole più frequenti (estratte via C-TF-IDF) di ogni cluster sono state fornite a Gemini, con il compito di sintetizzarle in un'**etichetta semantica** chiara e comprensibile (es. "Crisi guidate da guerre", "Shock legati al meteo e all'agricoltura", "Crisi pandemiche").
2.  **Validazione sui "Documenti Manifesto"**: Il sistema ha quindi calcolato la distanza euclidea/coseno dei report dal rispettivo centroide per isolare i **5 Report Manifesto** (i documenti più rappresentativi) di ogni cluster. I testi originali di questi 5 report sono stati poi passati a Gemini per **verificare la coerenza effettiva** con l'etichetta semantica precedentemente generata. Questo approccio garantisce che i topic emersi corrispondano realmente al contenuto narrativo dei report e non siano un artefatto statistico dell'algoritmo di clustering.

---

## 6. Validazione Qualitativa: Tabella di Contingenza ed Entropia
Per accertarsi che i modelli semantici *non abbiano raggruppato i report semplicemente per Paese* (bias geografico), viene calcolata l'entropia della distribuzione dei paesi all'interno di ogni cluster. Un'elevata entropia (es: 2.65, 3.06) conferma che **il cluster è semanticamente eterogeneo a livello geografico**, aggregando report di decine di Nazioni accomunate dallo stesso problema (es. Siccità o Malattie degli Animali).
