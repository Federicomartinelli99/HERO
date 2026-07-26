# 🛡️ Manuale Utente e Guida Operativa Esaustiva alla Suite HERO v6 UI
**Humanitarian & Environmental Risk Outlook (Version 6.0) — Complete Analytical Ecosystem & Dashboard**

---

## 1. Introduzione e Filosofia del Sistema

La **User Interface (UI) di HERO v6** è un ecosistema analitico e interattivo ad altissima risoluzione, concepito per il monitoraggio multidimensionale delle crisi umanitarie, della sicurezza alimentare, dei conflitti armati, dell'inflazione microeconomica e delle anomalie climatiche in oltre **53 paesi ad alta vulnerabilità** (con focus analitico approfondito su 20 paesi pilota per i modelli avanzati di serie storiche).

L'interfaccia adotta un'estetica moderna basata sul **Glassmorphism**, con una **Dark Mode nativa** ottimizzata per le sale operative e per la visualizzazione di dati geospaziali ad alta densità. Ogni componente è reattivo, con micro-animazioni di transizione e un'architettura completamente **locale e offline**, eseguibile senza container tramite un server HTTP Python (`run_ui.bat` sulla porta `8080`).

---

## 2. Architettura Navigazionale: Le 8 Viste Principali

Il menu laterale sinistro (*Sidebar*) costituisce il pilastro di navigazione della suite e permette di alternare istantaneamente **8 Viste Operative Principali** (Top-Level Views), ciascuna dedicata a una specifica dimensione di analisi:

```
+----------------------------------------------------------------------------------------------------+
| 1. PANORAMICA GLOBALE (`global`)                | Panoramica mondiale, mappa SVG e ranking rischio |
| 2. DETTAGLIO PAESE (`country`)                  | Suite verticale con 11 sotto-sezioni analitiche  |
| 3. CONFRONTO PAESI (`compare`)                  | Comparazione dinamica multi-paese su serie/radar |
| 4. ESPLORAZIONE SPAZIO-TEMPORALE (`spatiotemp`) | Mappe dinamiche globali su indicatori tematici   |
| 5. TSA GLOBALE (`tsa-global`)                   | Clustering cross-country tra 20 paesi pilota     |
| 6. CLUSTERING & PATTERN (`clustering`)          | Confronto strategie di cluster sub-nazionali       |
| 7. ESPLORATORE TOPOLOGICO (`tsgraph`)           | Analisi topologica, reti di correlazione e grafi |
| 8. CLUSTERING EVOLUTION (`clustering-evolution`)| Alluvial/transizioni temporali (TF-IDF vs Densi) |
+----------------------------------------------------------------------------------------------------+
```

---

## 3. Analisi Dettagliata delle 8 Viste Principali e delle Sotto-Sezioni

### 🌍 3.1. Vista 1: Panoramica Globale (`Panoramica Globale`)
La schermata di comando iniziale offre una radiografia geopolitica istantanea delle emergenze mondiali:
- **Mappa Mondiale Interattiva (SVGMap)**: Visualizza il globo a colori tematizzati in base all'intensità del rischio alimentare e di conflitto. Cliccando su qualsiasi nazione, si apre il **Geographic Audit Modal** (un pannello riassuntivo che verifica in tempo reale la disponibilità e completezza dei dati provinciali e dei mercati prima di accedere al dettaglio).
- **Ranking e Matrice di Rischio dei 53+ Paesi**: Tabella ordinabile che classifica le nazioni monitorate secondo indici compositi di gravità umanitaria, letalità dei conflitti ACLED e anomalie di siccità CHIRPS/NDVI.
- **Toggle Radar Globale**: Un interruttore rapido (`btn-toggle-global-radar-mode`) che consente di alternare la vista della mappa mondiale con profili stagionali radar comparati, evidenziando i mesi critici (*lean season*) in scala globale.

---

### 🏛️ 3.2. Vista 2: Dettaglio Paese (`Dettaglio Paese`) & Le 11 Sotto-Sezioni
Selezionando una nazione, la UI schiera un banner superiore con il nome del paese, il codice ISO-3 (es. **AFG**, **SDN**, **YEM**) e il pulsante maestro di esportazione unificata. Nel menu laterale compaiono **11 sotto-schede specialistiche**:

#### 🗺️ 3.2.1. Mappa & Regioni (`map`)
- Visualizzazione geospaziale vettoriale delle sotto-regioni (province, governatorati, dipartimenti).
- Consente di cliccare sulle singole province per filtrare istantaneamente tutte le serie storiche del paese alla specifica area selezionata.

#### 📈 3.2.2. Grafici e Trend (`charts`)
- Plancia degli indicatori aggregati di stabilità socio-economica e sicurezza alimentare.
- **Switch Dinamico Lineare/Istogramma vs Radar**: Consente di visualizzare i trend sia come serie storiche cronologiche (2017-2026), sia come grafici Radar stagionali a 12 mesi per identificare pattern ciclici e anomalie stagionali ricorrenti.

#### 🏪 3.2.3. Mercati Alimentari WFP ad Alta Granularità (`markets`)
Il modulo analitico più avanzato per l'esplorazione della micro-economia alimentare e dell'inflazione dei beni di prima necessità (rilevamenti *World Food Programme*). È strutturato in tre livelli logici integrati:
1. **Analisi Aggregata Nazionale (In Alto - Griglia 3:1)**:
   - A sinistra (3 frazioni), una serie temporale a lungo periodo che traccia l'Indice Prezzi Alimentari Nazionale e il Tasso di Inflazione (asse Y opposto).
   - A destra (1 frazione), il Profilo Stagionale Radar a 12 mesi, fondamentale per anticipare i picchi di prezzo dell'anno.
   - **Tasto di Esportazione Dedicato**: Permette di scaricare al volo i due grafici HTML interattivi di sintesi nazionale.
2. **Mappa Regionale e Lista Censimento (Al Centro)**:
   - Mappa interattiva ad alta risoluzione del paese che riporta come pallini di calore tutti i singoli mercati censiti (supermercati urbani, fiere rurali, centri di distribuzione).
   - A destra, la lista ordinata e filtrabile dei mercati. Il clic su un punto della mappa o su un nome della lista attiva il focus sul singolo mercato.
3. **Dettaglio Singolo Mercato (In Basso)**:
   - Compare dinamicamente sotto la mappa al momento della selezione. Mostra due grafici interattivi affiancati con i listini originali e il tasso di inflazione specifico di quel singolo punto vendita.

#### 📰 3.2.4. Media & News GDELT (`gdelt`)
Analisi del flusso di notizie mondiali dal *Global Database of Events, Language, and Tone*:
- **Selettore / Toggle Dinamico**: Interruttore per passare in tempo reale tra due modalità di intelligence:
  1. *Salienza Mediatica (Menzioni vs Volume Eventi Reali)*: Evidenzia le discrepanze tra l'attenzione della stampa internazionale e l'effettiva quantità di eventi armati sul terreno (rileva le "guerre dimenticate").
  2. *Instabilità & Tono (Linegraph Sentiment)*: Confronta l'andamento del tono emotivo degli articoli (da positivo/cooperativo a fortemente negativo/ostile) con l'escalation militare.
- **Salvataggio Sdoppiato Automatico**: Qualsiasi sia la vista attiva, al momento del salvataggio la piattaforma esporta automaticamente **entrambe le visualizzazioni come due file HTML interattivi distinti**.

#### 🌾 3.2.5. Sicurezza Alimentare IPC / CH (`ipc`)
Monitoraggio delle classificazioni ufficiali *Integrated Food Security Phase Classification* o *Cadre Harmonisé*:
- Traccia la percentuale e il numero assoluto di abitanti nelle **Fasi 3 (Crisi)**, **Fase 4 (Emergenza)** e **Fase 5 (Catastrofe/Carestia)**.
- Fornisce indicatori di allerta per proiettare il fabbisogno di assistenza umanitaria d'emergenza.

#### ⚔️ 3.2.6. Conflitti ed Eventi di Sicurezza ACLED (`acled`)
Integrazione geolocalizzata dell' *Armed Conflict Location & Event Data Project*:
- Traccia scontri armati, violenze contro i civili, proteste, tumulti e attacchi con esplosivi/remoti.
- Valuta la letalità degli incidenti e la pericolosità delle direttrici logistiche di soccorso.

#### 🚶‍♂️ 3.2.7. Sfollati Interni e Rifugiati IDP (`idp`)
- Monitoraggio demografico dei flussi di sfollati interni (*Internally Displaced Persons*), rifugiati transfrontalieri e ritorni.
- Mappa le aree di pressione democratica su centri urbani e campi di accoglienza improvvisati.

#### 🌧️ 3.2.8. Precipitazioni Satellitari CHIRPS (`rainfall`)
- Misurazione delle precipitazioni cumulative mensili tramite telerilevamento satellitare CHIRPS.
- Evidenzia siccità agrometeorologiche o piogge estreme causa di inondazioni (*flash floods*).

#### 🌿 3.2.9. Indice Vegetativo e Pascoli NDVI (`ndvi`)
- Il *Normalized Difference Vegetation Index* valuta lo stato di salute e la resa fotosintetica delle colture e dei pascoli.
- Costituisce l'allarme preventivo per il fallimento dei raccolti prima della stagione di raccolta.

#### 📐 3.2.10. Mappa Spazio-Temporale Sotto-Regionale (`spatiotemporal`)
- Genera matrici di calore che combinano lo spazio (province sull'asse Y) e il tempo (mesi/anni sull'asse X).
- Permette di individuare a colpo d'occhio in quali specifiche province del paese è iniziata e si è propagata una crisi climatica o di conflitto nel corso dei mesi.

#### 🔬 3.2.11. Diagnostica TSA e Modellazione Predittiva (`tsa`)
La sala macchine di analisi statistica avanzata (*Time Series Analysis & Predictive Modeling*) per la regione o provincia selezionata:
- **Decomposizione STL**: Separazione automatica della serie temporale in componente di Trend, Stagionalità e Residui.
- **Autocorrelazione (ACF / PACF) & Cross-Correlazione**: Calcolo del ritardo temporale (*lag*) con cui le precipitazioni o i conflitti impattano la sicurezza alimentare IPC.
- **Rilevamento Anomalie (Matrix Profile)**: Identificazione algoritmica di discontinuità strutturali e shock imprevisti nei dati storici.
- **Confronto Multi-Modello di Machine Learning**: Valutazione e comparazione delle previsioni generate da modelli statistici e predittivi, con tabelle delle metriche di errore (**MAE, RMSE, R²**) e analisi dei residui post-modellazione.

---

### ⚖️ 3.3. Vista 3: Confronto Paesi (`Confronto Paesi`)
Schermata dedicata alla comparazione inter-statale diretta per l'intelligence comparata:
- **Selettore Aggiunta Paese**: Menu a discesa che consente di aggiungere dinamicamente 2, 3 o più paesi alla plancia di confronto (con chip interattive dotate di tasto "x" per la rimozione rapida).
- **Confronto Temporale Lineare**: Sovrappone nello stesso grafico le curve di instabilità o di inflazione delle nazioni selezionate.
- **Confronto Profili Stagionali Radar**: Sovrappone i grafici radar a 12 mesi per confrontare in quale momento dell'anno scatta la crisi climatica o alimentare in paesi limitrofi.

---

### 🌐 3.4. Vista 4: Esplorazione Spazio-Temporale Globale (`Esplorazione Spazio-Temporale`)
Consente di mappare macro-tendenze a livello continentale e mondiale:
- **Selettore Tema/Indicatore Globale**: Permette di scegliere la metrica da analizzare (es. Indice IPC globale, anomalie NDVI o tasso acled di conflitto).
- **Selettore Livello di Aggregazione**: Permette di scegliere se aggregare la mappa per nazioni intere o per macro-ecoregioni transfrontaliere.

---

### 🧩 3.5. Vista 5: TSA Globale - Clustering Cross-Country (`TSA Globale`)
Sezione di ricerca avanzata che raggruppa matematicamente i **20 paesi pilota** di HERO in cluster di vulnerabilità sulla base dell'andamento storico delle loro serie IPC dal 2017 al 2026:
- **Tre Strategie di Clustering Separate**:
  1. *Feature-Based*: Clusterizzazione basata su estrazione di feature statistiche (Catch22).
  2. *Shape-Based (DTW)*: Utilizzo della distanza *Dynamic Time Warping* per raggruppare paesi che condividono la stessa "forma" delle ondate di crisi, indipendentemente dallo spostamento temporale.
  3. *Compression-Based (NCD)*: Raggruppamento basato sulla *Normalized Compression Distance* (teoria dell'informazione e Kolmogorov complexity).
- **Mappe Mondiali Univariate e Multivariate**: Mappe a colori che mostrano la spartizione dei continenti nei vari cluster identificati.
- **Confronto Strategie & Valutazione**: Grafici a barre interattivi con gli indici di validità del clustering: **Silhouette Index** (coesione interna) e **Davies-Bouldin Index** (separazione tra cluster).
- **Scatter Plot PCA**: Visualizzazione nello spazio a 2 dimensioni delle componenti principali (PCA) per osservare la distribuzione e sovrapposizione geometrica delle nazioni nei cluster.
- **Profili Storici di Traiettoria (2017-2026)**: Linegraph che traccia la traiettoria media di rischio anno per anno dei singoli cluster globali.

---

### 🔬 3.6. Vista 6: Clustering & Pattern Sub-Nazionali (`Clustering & Pattern`)
Porta le metodologie della TSA Globale all'interno dei confini di un singolo paese selezionato:
- Confronta direttamente su due colonne la **Strategia Univariata (DTW)** e la **Strategia Multivariata (Feature-based)** per le province di quella nazione.
- Mostra due mappe di calore affiancate del paese per evidenziare quali province appartengono alla stessa tipologia statistica di crisi e condividono vulnerabilità strutturali identiche.

---

### 🕸️ 3.7. Vista 7: Esploratore Topologico (`Esploratore Topologico`)
Un modulo integrato di **Topological Data Analysis (TDA) e Teoria dei Grafi**, caricato in una vista dedicata ad alte prestazioni:
- Visualizza la rete complessa (*Graph Network*) delle correlazioni spaziali e temporali tra le variabili ambientali e sociali.
- I nodi rappresentano variabili o regioni, mentre gli archi (*edges*) pesati evidenziano relazioni di causalità e forti correlazioni di shock transfrontaliero.

---

### 🌊 3.8. Vista 8: Clustering Evolution (`Clustering Evolution`)
Sezione dedicata allo studio della dinamica temporale dei cluster e delle transizioni di stato del rischio negli anni:
- Traccia come una provincia o una nazione si sposta da un cluster di "Stabilità" a un cluster di "Crisi Cronica" attraverso finestre temporali scorrevoli (diagrammi Alluvionali / di flusso).
- **Switch Modelli di Embedding**: Integrato nell'intestazione della vista, un interruttore interattivo permette di calcolare le transizioni di cluster utilizzando due diversi paradigmi statistici:
  - **TF-IDF**: Ponderazione statistica basata su frequenza termica delle anomalie.
  - **Embedding Densi**: Rappresentazione vettoriale profonda (Dense Embeddings) generata da modelli di reti neurali o autoencoder.

---

## 4. Modali Interattivi e Strumenti di Esportazione Avanzata

### 🔍 4.1. Modali di Diagnostica e Audit In-App
1. **Geographic Audit Modal (`country-audit-modal`)**:
   - Scatta cliccando su un paese nella mappa globale. Mostra una mappa a sinistra e una tabella di completezza a destra, indicando la percentuale esatta di province con dati CHIRPS, ACLED o WFP attivi prima di lanciare l'analisi.
2. **Period Detail Modal (`period-detail-modal`)**:
   - Cliccando su un punto specifico delle serie storiche o su un mese del radar stagionale, si apre questo pannello che fornisce un'analisi statistica approfondita (media, deviazione standard, estremi) per il trimestre o periodo selezionato (es. *Dettagli Periodo: 2021-Q3*).

---

### 📥 4.2. Esportazione Interattiva HTML e Sicurezza JSON
Ogni singolo grafico ApexCharts incorpora un tasto di download per salvare un file `.html` interattivo e autoconnesso, consultabile offline mantenendo zoom, hover e tooltips.
- **Sicurezza Antiriferimento Circolare**: La funzione `window.exportInteractiveChart` applica una sterilizzazione in background che rimuove automaticamente riferimenti circolari e nodi DOM di ApexCharts, garantendo esecuzioni sicure senza crash.

---

### 📦 4.3. Esportazione Unificata in Singola Cartella Zip via JSZip
Nel banner superiore della vista paese è presente il pulsante maestro:

**`[ 🗜️ Salva Tutti HTML del Paese (CODICE) ]`**

1. **Feedback Animato**: Il pulsante si disabilita temporaneamente e mostra una rotella di caricamento animata (*"Creazione Cartella Zip Unica (AFG)..."*).
2. **Elaborazione On-Demand in Background**: Il sistema raggruppa tutti i dati della nazione. Anche se ci si trova nel tab *Trend* o *ACLED*, il codice calcola e inizializza silenziosamente in background i grafici dei Mercati WFP (Nazionale TS e Radar) e gli archivi di tutte le altre sezioni.
3. **Raggruppamento in Cartella Unica**: Tramite la libreria **JSZip**, l'interfaccia compila **in meno di 1 secondo** un singolo archivio compresso:
   👉 **`Suite_Esportazione_Completa_<CODICE>.zip`**
4. **Struttura Interna**: All'interno del file scaricato, una cartella principale (`Esportazione_Completa_HERO_<CODICE>`) raggruppa in modo ordinato tutto il materiale analitico:
   ```
   Suite_Esportazione_Completa_AFG.zip
   └── Esportazione_Completa_HERO_AFG/
       ├── Grafici_HTML_AFG.zip                   # Archivio Master TSA generale
       ├── Grafici_charts_AFG.zip                 # Dati Trend e Proiezioni
       ├── Grafici_ipc_AFG.zip                    # Dati Fasi Insicurezza Alimentare
       ├── Grafici_acled_AFG.zip                  # Storico Incidenti e Conflitti
       ├── Grafici_idp_AFG.zip                    # Movimenti Flussi Sfollati
       ├── Grafici_rainfall_AFG.zip               # Serie Satellitari Precipitazioni
       ├── Grafici_ndvi_AFG.zip                   # Serie Satellitari Vegetazione NDVI
       ├── Grafici_gdelt_AFG.zip                  # Matrice Copertura Mediatica
       ├── chart-market-national-ts_AFG.html      # Grafico HTML Interattivo Indice WFP
       └── chart-market-national-radar_AFG.html   # Grafico HTML Interattivo Radar WFP
   ```
5. **Fallback Sicuro**: In assenza di JSZip, il sistema passa automaticamente al download sequenziale di backup.

---

## 5. Troubleshooting e Buone Pratiche Operative

| Sintomo / Problema | Causa Probabile | Soluzione e Ripristino |
| :--- | :--- | :--- |
| **I nuovi pulsanti o layout non compaiono dopo un aggiornamento del codice** | Il browser ha mantenuto in memoria la versione precedente del file JavaScript (`app.js`) o del foglio di stile (`style.css`). | Effettuare una ricarica approfondita (*Hard Refresh*) premendo **`CTRL + F5`** (o `CTRL + SHIFT + R`). La UI di HERO v6 adotta comunque un sistema di versionamento dinamico (es. `app.js?v=7`) nell'HTML per forzare lo svuotamento della cache ad ogni nuova release. |
| **Errore nella connessione o pagina non trovata su `localhost:8080`** | Il server HTTP locale Python è stato terminato o non è mai stato avviato. | Aprire una finestra di terminale in `C:\Dev\Progetti\HERO\hero_v6\` ed eseguire nuovamente il comando `run_ui.bat`. Assicurarsi di non chiudere la finestra del prompt durante l'utilizzo della UI. |
| **I grafici GDELT o WFP mostrano la scritta *"Nessun dato disponibile"*** | Per quel parametro specifico o periodo di tempo non sono presenti rilevazioni nei file di input (es. paesi senza censimento mercati WFP attivo). | È il comportamento corretto e atteso per i paesi in cui le agenzie delle Nazioni Unite (WFP/FAO) o i sensori non pubblicano bollettini di censo rionale. Si consiglia di fare riferimento ai trend nazionali di macro-sezione. |
| **Rallentamento durante la navigazione della Mappa Mercati WFP** | Il paese selezionato possiede un numero elevatissimo di punti vendita e di serie storiche censite contemporaneamente. | Il rendering dei pallini vettoriali SVG su mappe geografiche complesse richiede alcune frazioni di secondo per il calcolo delle coordinate spaziali. Attendere il completamento del caricamento della lista a destra. |

---
*Manuale e Guida di Sistema generati per la Piattaforma HERO v6 — Advanced Agentic Coding & Analytics System.*
