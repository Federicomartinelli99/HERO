# Dataset Merge: IPC Phase Analysis vs. ACLED Violent Events
**Progetto HERO – Hunger Early-warning & Risk Optimizer**

---

## Descrizione

Questo notebook esegue il consolidamento, l'aggregazione spaziale e il merge "Left Join" tra i dati sulle classificazioni IPC (fasi di insicurezza alimentare) e il registro ACLED degli eventi violenti e delle fatalità, filtrati per i paesi target del progetto HERO.

Il risultato finale costituisce un dataset combinato utile ad addestrare modelli di intelligenza artificiale per l'analisi del rischio, permettendo di correlare la severità dei conflitti a livello locale (eventi e fatalità) con l'incidenza delle crisi alimentari misurate dalla popolazione classificata in fase IPC 3 o superiore.

---

## Fonte e accesso

Il dataset unificato viene costruito a partire dai seguenti file in input:

- **Dati IPC (Denominatori Demografici)**: `ipc_global_area_long_pcoded.csv`. (File sorgente contenente le previsioni di fase IPC, le popolazioni totali e le assegnazioni dei codici ADM1).
- **Dati ACLED (Segnali di Violenza)**:
    - `violent_events_1.csv`
    - `violent_events_2.csv`
    - `violent_events_3.csv`
    (File partizionati contenenti il volume degli incidenti violenti, le vittime, localizzati a livello temporale e spaziale).

---

## Granularità

- **Dati IPC Base**: Livello Amministrativo (Area), proiezioni temporali variabili (`From`, `To`).
- **Dati ACLED (Violenza)**: Originariamente a livello di evento puntuale, vengono aggregati a livello `ADM1` per anno e mese.
- **Dataset Finale Unito**: Livello ADM1 per finestra temporale specifica (mese/anno).

---

## Copertura geografica

- **Paesi**: 48 paesi stabiliti come baseline del progetto HERO. Il notebook esclude proattivamente (drop) i record di nazioni presenti in ACLED ma non previste dal monitoraggio IPC.
- **Livello geografico**: ADM1. L'unificazione si basa esplicitamente sulla convergenza tra le chiavi `adm1_pcode` fornite da IPC e quelle generate per ACLED tramite mappatura testuale e standardizzazione dei prefissi.

---

## Copertura temporale

- **Periodo Filtrato**: Gennaio 2017 – Presente. Il notebook rimuove i record di violenza antecedenti al 2017 per allinearsi all'availability dei dati IPC.
- **Formato Temporale Standardizzato**: Per consentire il merge, la combinazione originale di `Month` (stringa testuale "April") e `Year` (intero) nel dataset ACLED viene unita e formattata nel formato `Mmm-YY` (es. `Apr-19`) per fare matching esatto con la colonna `Date of analysis` del dataset IPC.

---

## Struttura del dataset

**Dataset Finale (`df_unito`)**: 56.414 righe × 15 colonne.
Rappresenta l'integrazione delle metriche di insicurezza alimentare con le intensità di conflitto armato.

**Colonne identificative / di Join**:
| Colonna | Tipo | Descrizione |
|---|---|---|
| `Country` | str | Codice ISO 3166-1 alpha-3 del paese. |
| `Date of analysis` | str | Finestra temporale di analisi formattata come `Mmm-YY` (es. Apr-19). |
| `adm1_pcode` | str | Codice univoco della regione livello 1 standardizzato. |

**Altre Colonne Identificative**:
`Level 1`, `Area`, `Validity period`, `From`, `To`, `Phase`.

**Colonne Numeriche di Output**:
| Colonna | Descrizione |
|---|---|
| `Number` | Numero assoluto di persone assegnate a quella specifica fase IPC. |
| `Total country population` | Popolazione complessiva della nazione di riferimento (da cui si ricava la magnitudine della crisi in termini percentuali). |
| `Percentage` | Rapporto ricalcolato (Number / Total country population * 100) per quantificare correttamente l'incidenza della crisi sul totale. |
| `Events` | Conteggio aggregato degli incidenti violenti registrati nella regione ADM1 durante il mese di riferimento. |
| `Fatalities` | Numero aggregato di morti registrati durante gli eventi violenti. |
| `violence_ratio` | Metrica di magnitudine calcolata come (Fatalities / Events). Il valore viene corretto a 0 nei casi in cui Events sia pari a 0 per evitare errori "inf". |

---

## Valori mancanti e Gestione Orfani

Il notebook documenta l'analisi delle righe non mappate ("Orfani") generatesi durante l'operazione di merge. Essendo un *Left Join* (`m:1`) sui dati IPC, tutti i dati di insicurezza alimentare vengono preservati, ma laddove non ci sono dati di violenza corrispondenti (o a causa di fallimento del matching sulle chiavi), le metriche ACLED producono valori Nulli (`NaN`).

* **Valori `NaN` nelle colonne ACLED (`Events`, `Fatalities`, `violence_ratio`)**: Segnalano 22.981 righe non associate.
* **Analisi di Copertura**: Il codice espone le percentuali di valori nulli di queste colonne per paese. Molti paesi registrano il 100% di "NaN" nelle colonne ACLED (es. PAK, GIN, MDG, BGD, AGO), suggerendo un problema sistemico di allineamento delle chiavi geografiche o un'assenza effettiva di record ACLED formattati correttamente per quelle aree nel periodo specificato.
* **Valori `NaN` in `Percentage`**: Segnalano 57 record in cui la divisione per la popolazione non è andata a buon fine.

---

## Statistiche di processing

### Tassi di successo del matching geografico

Prima dell'operazione di `Left Join`, il notebook implementa logiche per aumentare il tasso di accoppiamento (hit rate) tra i P-code dei due database.

| Strategia di Mapping | Azione |
|---|---|
| **Conversione Prefissi Regex** | I prefissi `TD` sostituiti in `TCD`; `NER` sostituiti in `NE` tramite regex pattern matching. |
| **Mappature Unificate Dirette** | Dizionario di override esplicito per le anomalie Nigeriane/Camerunensi (es. `NG00` → `NG001`, `CM00` → `CM001`). |

### Anomalie Irrisolte
Nonostante le correzioni, l'analisi degli insiemi (`set`) rivela discrepanze. Esiste un subset geografico di codici P-code ACLED (come `BDI017`, `TCD18`, `ET14`, ecc.) orfani, cioè assenti nel tracciato IPC Master e che pertanto vengono scartati durante l'unione tabellare.

---

## Note metodologiche

**Calcolo Percentuali IPC**: Nel notebook viene adottata una "Best Practice" importante: ricalcolare la metrica `Percentage` a valle del raggruppamento IPC. Il ricalcolo analitico `(Number / Total country population) * 100` impedisce derive numeriche causate dal fare la media di percentuali preesistenti su popolazioni eterogenee.

**Creazione e Mapping di 'Macro_Region'**: Il notebook costruisce una categorizzazione continentale arbitraria (`Macro_Region`) per generare visualizzazioni macro. I paesi vengono raggruppati in `Asia & Pacific`, `Latin America & Caribbean`, `Middle East & North Africa`, e `Sub-Saharan Africa` tramite mappatura dizionario, con fill fallback su "Other".

**Cluster Analysis (Lethality Indexing)**: I dati ACLED aggregati a livello nazionale vengono usati per calcolare cluster di rischio K-Means (`n_clusters=4`), creando quadranti di pericolosità. Questo approccio indicizza il rischio sistemico, tuttavia è fondamentale notare la presenza della fase di **standardizzazione** tramite `StandardScaler`, cruciale affinché 'Events' (volume) e 'Fatalities' (gravità) concorrano equamente al calcolo delle distanze euclidee, prevenendo distorsioni di scala.

**Risoluzione delle Data (Date of analysis)**: Per consentire la join, la stringa testuale del mese in ACLED (es. "April") è passata a formato corto (es. "Apr") via dizionario, quindi concatenata all'anno troncato a due cifre ("-19"). Un *assertion block* impedisce corruzioni bloccando lo script qualora si presentino typo nei nomi dei mesi originali.

---

## Pipeline di produzione

1. **Load Base**: Caricamento in RAM dei chunk ACLED (`violent_events_1, 2, 3`) e del master IPC.
2. **ACLED Filtering & Standardization**: Concatenazione dei chunk violenza, dropping dei paesi fuori focus IPC tramite mappatura inversa e applicazione del floor temporale (Anno >= 2017).
3. **Calcolo Metriche Intermedie**: Aggregazione ACLED a livello di mese/anno e ADM1, seguita dal calcolo di indicatori derivati (es. `violence_ratio`).
4. **Armonizzazione Geografica (P-codes)**: Patching via Regular Expressions per convertire i p-code non convenzionali (es. TD -> TCD) nei codici ufficiali utilizzati da IPC.
5. **Generazione Chiave Temporale (Join Key)**: Formattazione sintetica `Date of analysis` (es. `Apr-19`) dai campi grezzi ACLED.
6. **Pre-processing IPC**: Raggruppamento per fase e validità temporale del database IPC.
7. **Consolidamento Relazionale**: `Left Join` con validazione forzata `m:1` tra IPC (master) e ACLED (lookup). Le chiavi di join impiegate sono: `['Country', 'Date of analysis', 'adm1_pcode']`.
8. **Data Quality Audit**: Calcolo finale per nazione dell'incidenza dei valori mancanti (`null%`) generati durante il Join.
