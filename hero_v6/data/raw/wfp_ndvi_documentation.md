# Dataset WFP NDVI – Indice di Vegetazione
**Progetto HERO – Hunger Early-warning & Risk Optimizer**

---

## Descrizione

Il dataset consolida i dati subnazionali dell'NDVI (Normalized Difference Vegetation Index) estratti dal database del World Food Programme (WFP) tramite l'API HDX. Fornisce serie storiche sull'indice di vegetazione, fungendo da proxy critico per misurare densità e salute della biomassa, anomalie climatiche, siccità e stress agricolo che impattano la sicurezza alimentare.

All'interno del progetto HERO, questo dataset integra i segnali media-based e le stime demografiche, fornendo indicatori ambientali quantificabili per alimentare i modelli predittivi e di early-warning sulle crisi alimentari.

---

## Fonte e accesso

- **Fonte**: HDX (Humanitarian Data Exchange) / World Food Programme (WFP)
- **Dataset Query**: `ndvi` (fq: `organization:wfp`)
- **Accesso**: API Python HDX (`hdx-python-api`)
- **Documentazione**: N/A

---

## Granularità

Ogni riga del dataset finale rappresenta un'osservazione spaziotemporale. La granularità è subnazionale (solitamente equivalente a ADM1 o ADM2 a seconda del paese e della disponibilità del WFP) misurata a intervalli temporali continui.

---

## Copertura geografica

- **Paesi**: 52 (Specificati nel target set del codice, divergendo dai 48 dei metadati precedenti)
- **Livello geografico**: Subnazionale (Subnat)
- **Assegnazione geografica**: Aggregazione diretta in base all'ISO3 estratto dai metadati HDX (`get_location_iso3s()`), arricchita programmaticamente con la colonna `country_iso3`.

I 52 paesi coperti dal codice sono: AFG, AGO, BDI, BEN, BFA, BGD, CAF, CIV, CMR, COD, CPV, DJI, DOM, ECU, ETH, GHA, GIN, GMB, GNB, GTM, HND, HTI, KEN, LBN, LBR, LSO, MDG, MLI, MOZ, MRT, MWI, NAM, NER, NGA, PAK, PSE, SDN, SEN, SLE, SLV, SOM, SSD, SWZ, TCD, TGO, TLS, TZA, UGA, YEM, ZAF, ZMB, ZWE.

---

## Copertura temporale

- **Periodo**: 1 Gennaio 2017 – Giugno 2026 (Il minimo storico del dataset originale è 2002-07-01, troncato in fase di elaborazione).
- **Risoluzione temporale**: Serie storica (decadale/mensile in base allo standard WFP).
- **Fonte temporale**: Colonna `date` dei file HDX scaricati.

---

## Struttura del dataset

**Dimensioni**: 7.225.344 righe generate in estrazione (gonfiate da duplicazioni), prima del filtraggio finale.

**Colonne identificative** (visibili dal codice):

| Colonna | Tipo | Descrizione |
|---|---|---|
| `country_iso3` | str | Codice ISO 3166-1 alpha-3 del paese. |
| `hdx_dataset_name` | str | Nome del dataset originario su HDX. |
| `date` | str | Data dell'osservazione satellitare. |

---

## Statistiche di processing

### Riepilogo globale

| Metrica | Valore |
|---|---|
| Righe concatenate inizialmente | 7.225.344 |
| Formato di persistenza primario | `.parquet` |
| Filtro temporale applicato | `>= '2017-01-01'` |

---

## Note metodologiche

**Deduplicazione Mancante (Grave Anomalia)**: Il parsing dei dataset HDX scarica indiscriminatamente tutte le risorse CSV (sia i file `*-ndvi-subnat-full.csv` che `*-ndvi-subnat-5ytd.csv`). Il file `full` include già i dati degli ultimi 5 anni. La concatenazione di entrambi genera una duplicazione massiccia dei record recenti, alterando in modo errato il peso dei dati temporali se inseriti in modelli statistici, a meno che non si applichi un `drop_duplicates()` non presente nel codice.

**Incongruenza della Baseline Paesi**: L'elenco `TARGET_COUNTRIES` nel notebook include 52 codici ISO3, introducendo `DOM`, `MWI`, e `PSE`. Questo rompe l'integrità strutturale rispetto al core base del progetto HERO descritto in precedenza (48 paesi). 

---

## Pipeline di produzione

1. **Inizializzazione Configurazione** — Modifica dell'istanza `Configuration` di HDX con gestione sicura delle eccezioni e user agent dedicato (`NDVI_WFP_Consolidator`).
2. **Ricerca Dati** — Query all'API HDX per i dataset WFP relativi all'NDVI.
3. **Controllo Intersezioni** — Filtro dei dataset basato sull'intersezione tra le geolocalizzazioni HDX (ISO3) e l'insieme custom `TARGET_COUNTRIES`.
4. **Download e Integrazione** — Scaricamento iterativo dei CSV su directory temporanea (gestita via `tempfile`), iniezione delle coordinate descrittive (`country_iso3`, `hdx_dataset_name`) e accodamento in RAM.
5. **Primo I/O (Inefficiente)** — Salvataggio grezzo su disco in `wfp_ndvi_consolidated.csv`.
6. **Filtraggio Temporale** — Ricaricamento in RAM dell'output, identificazione del floor temporale, e rimozione forzata dei record antecedenti al 2017.
7. **Esportazione** — Salvataggio parallelo nel formato colonnare Parquet (`wfp_ndvi.parquet`) e CSV standard.
