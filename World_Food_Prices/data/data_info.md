# Documentazione Struttura Dati: WFP Global Real-Time Food Prices

Questo documento descrive in dettaglio l'architettura dei dati forniti dal **World Food Programme (WFP)** tramite l'hub HDX, specificamente per il dataset *Global Real-Time Food Prices*.

L'analisi si basa su due componenti principali: il file di metadati globale e i file CSV annuali (es. `global_food_2026.csv`), i quali presentano una struttura **Wide (denormalizzata)** altamente ricca di feature.

---

## 1. Il File dei Metadati (`metadata-global-real-time-food-prices.csv`)

A differenza dei classici dataset tabellari, il file dei metadati ha una struttura **Verticale (Chiave-Valore)**. Serve come "mappa" per scaricare e comprendere l'intero database.

| Field (ID Campo) | Label (Etichetta Descrittiva) | Value (Valore/Dato Reale) |
| :--- | :--- | :--- |
| `id` | Dataset ID | `82efaf85-d581-4fa8...` |
| `title` | Title of Dataset | `Global - Real Time Food Prices` |
| `dataset_source` | Source | `World Bank` |
| ... | ... | ... |
| `resource_X_name`| Resource Name | `Real Time Food Prices 2026` |
| `resource_X_url` | URL | `https://.../global_food_2026.csv` |

**Nota Architetturale:** Ogni "Risorsa" (ovvero un singolo anno di dati, come il 2026) occupa un blocco ripetuto di circa 13 righe. È da questo file che lo script `wfp_to_parquet.py` estrae dinamicamente i link per il download massivo.

---

## 2. Lo Schema del Dataset Annuale (Formato "Wide")

Il file `global_food_2026.csv` contiene i dati veri e propri. Invece di avere una riga per ogni singolo prezzo registrato (formato *Long*), il WFP ha strutturato i dati in formato **Wide**. 

Ogni riga rappresenta **lo stato completo di un singolo mercato in un dato mese**, e i prezzi di tutti gli alimenti sono spalmati su centinaia di colonne.

Possiamo dividere le colonne in **4 Macro-Aree Logiche**:

### 🌍 Area A: Identificazione Geografica e Spaziale
| Colonna | Descrizione | Livello di Granularità |
| :--- | :--- | :--- |
| `ISO3` | Codice univoco del paese (es. `YEM`, `AFG`). | Nazionale (Level 0) |
| `country` | Nome del paese in chiaro. | Nazionale (Level 0) |
| `adm1_name` | Regione, Stato o Governatorato. | Regionale (Level 1) |
| `adm2_name` | Distretto o Provincia. | Distrettuale (Level 2) |
| `mkt_name` | Nome dello specifico mercato fisico monitorato. | Locale (Level 3) |
| `lat` / `lon` | Coordinate spaziali esatte del mercato. | Geospaziale |
| `geo_id` | Identificativo geografico univoco del database. | Sistema |

### 📅 Area B: Dati Temporali
| Colonna | Descrizione |
| :--- | :--- |
| `year` | Anno di rilevazione (es. 2026). |
| `month` | Mese di rilevazione (1 = Gen, 12 = Dic). |
| `DATES` | Timestamp combinato (spesso in formato testuale o epoch). |

### 📊 Area C: Metadati di Qualità e Copertura
Queste colonne indicano quanto ci si può fidare del dato per quel mese specifico (utilissime per filtrare i dati prima del Machine Learning).
* `currency`: Valuta locale utilizzata per le transazioni.
* `components`: Numero di voci che compongono l'indice di quel mercato.
* `data_coverage`: Percentuale di dati storici reali vs dati stimati (imputati).
* `index_confidence_score`: Score di affidabilità statistica del dato mensile.
* `spatially_interpolated`: Flag (True/False) che indica se il dato è reale o derivato da mercati vicini.

### 🌾 Area D: Le Commodities e le Feature Derivate (Il Core)
Per *ogni* singolo prodotto monitorato (es. `apples`, `wheat`, `rice`, `meat_beef`), il dataset genera **6 colonne distinte**.

Prendiamo come esempio il **Grano (Wheat)**. Nel dataset troverai:
1. `wheat`: Il prezzo medio standard.
2. `o_wheat`: Prezzo di apertura (Open) nel mese.
3. `h_wheat`: Prezzo massimo (High) registrato nel mese.
4. `l_wheat`: Prezzo minimo (Low) registrato nel mese.
5. `c_wheat`: Prezzo di chiusura (Close) a fine mese.
6. `inflation_wheat`: Tasso di inflazione specifico per il grano.
7. `trust_wheat`: Livello di confidenza del dato per il grano.

### 📈 Area E: Indici Aggregati (Food Basket Index)
Alla fine delle centinaia di colonne dedicate ai singoli beni, si trovano le colonne più importanti in assoluto per il merging con i dati IPC (insicurezza alimentare):
* `food_price_index`: L'Indice del Paniere Alimentare complessivo per quel mercato.
* `inflation_food_price_index`: **Il tasso di inflazione alimentare generale**.

---

## 3. Schema Relazionale e Gerarchico (Diagramma)

Ecco come i dati sono relazionati logicamente all'interno di una singola riga del CSV.

```text
[ RIGHE DEL DATASET: 1 Riga = 1 Mercato in 1 Mese Specifico ]
   │
   ├── 📍 DOVE? (Gerarchia Spaziale)
   │    ├── Nazione: ISO3 (es. AFG)
   │    └── Regione: adm1_name (es. Badakhshan)
   │         └── Mercato: mkt_name (es. Argo Market) + Lat/Lon
   │
   ├── 🕒 QUANDO? (Coordinate Temporali)
   │    ├── year: 2026
   │    └── month: 1
   │
   ├── ⚖️ AFFIDABILITÀ? (Quality Control)
   │    ├── data_coverage: 0.85
   │    └── index_confidence_score: 9.2
   │
   ├── 🍎 MATERIE PRIME (Centinaia di colonne indipendenti)
   │    ├── Colonna 'wheat' (Prezzo Medio: 1.16)
   │    ├── Colonna 'h_wheat' (Picco Max: 1.25)
   │    ├── Colonna 'rice' (Prezzo Medio: 1.93)
   │    └── ... [Altre decine di beni]
   │
   └── 🎯 INDICI MACROECONOMICI (Target per Machine Learning)
        ├── food_price_index: 145.2
        └── inflation_food_price_index: 12.5%