# Dataset Population ADM1 – Base Demografica
**Progetto HERO – Hunger Early-warning & Risk Optimizer**

---

## Descrizione

Il dataset *Population ADM1* fornisce le stime della popolazione totale disaggregata a livello amministrativo 1 (regioni/province) per i 48 paesi di interesse del progetto HERO. 

Nel contesto del progetto HERO, questo dataset funge da denominatore demografico fondamentale. È essenziale per calcolare i tassi di incidenza e normalizzare i segnali provenienti da altre fonti (es. GDELT, ACLED, dati IPC), permettendo di trasformare conteggi assoluti in metriche relative pesate per la popolazione residente in ciascuna macro-area.

---

## Fonte e accesso

Il dataset è una consolidazione di diverse fonti secondarie, necessaria per coprire lacune nei repository primari.

- **Fonte Primaria**: OCHA / HDX (Humanitarian Data Exchange) - Dataset `cod_population_admin1.csv` (Baseline UNFPA e uffici statistici nazionali).
- **Fonti Secondarie per integrazione (Fallback)**:
    - *Afghanistan (AFG)*: Dataset `AFG_ADM1.csv`.
    - *Libano (LBN)*: Dataset `lebanon.csv` (Dati LRP 2026).
    - *Yemen (YEM)*: Dataset `yemen.csv`.
    - *Gambia (GMB)*: Dataset `GMB_ADM1.csv`.
    - *Guinea-Bissau (GNB)*: Dati estratti da reportistica e inseriti tramite mapping hardcoded.
- **Accesso**: File CSV locale unificato (`population_admin1.csv`).

---

## Granularità

Ogni riga del dataset finale rappresenta una **cella spaziale**: la combinazione univoca di paese (ISO3) e regione (ADM1_PCODE). Per ogni cella è disponibile il totale aggregato della popolazione residente.

---

## Copertura geografica

- **Paesi**: 48 (lista estratta dinamicamente dal master dataset IPC `ipc_global_area_long_pcoded.csv`).
- **Livello geografico**: ADM1 (Province/Regioni), identificati tramite Pcode HDX/COD.
- **Regioni uniche**: ~769 (stimato in base all'aggregazione finale).
- **Assegnazione geografica**: Mapping directo sui codici Pcode. Per il Libano, i nomi testuali delle governatorati sono stati mappati manualmente sui codici standard ISO/Pcode (es. `Akkar` → `LB-AK`).

I 48 paesi coperti sono estratti dalle analisi IPC e includono: AFG, AGO, BDI, BEN, BFA, BGD, CAF, CIV, CMR, COD, CPV, DJI, ECU, ETH, GHA, GIN, GMB, GNB, GTM, HND, HTI, KEN, LBR, LSO, MDG, MLI, MOZ, MRT, NAM, NER, NGA, PAK, SDN, SEN, SLE, SLV, SOM, SSD, SWZ, TCD, TGO, TLS, TZA, UGA, YEM, ZAF, ZMB, ZWE.

---

## Copertura temporale

- **Periodo**: Cross-sectional (variabile in base al paese, prevalentemente stime 2021-2024 per HDX, proiezioni 2026 per Libano).
- **Risoluzione temporale**: Statica (ultima stima disponibile).
- **Fonte temporale**: Mista (dipende dalla fonte di origine della specifica riga).

---

## Struttura del dataset

**Dimensioni**: ~769 righe × 3 colonne (formato long).

**Colonne identificative** (2):

| Colonna | Tipo | Descrizione |
|---|---|---|
| `ISO3` | str | Codice ISO 3166-1 alpha-3 del paese. |
| `ADM1_PCODE` | str | Codice identificativo univoco HDX/COD della regione ADM1. |

**Colonne numeriche** (1):

| Colonna | Descrizione |
|---|---|
| `Population` | Popolazione totale residente nell'unità ADM1. Aggregata eliminando le stratificazioni per genere ed età. |

---

## Valori mancanti

I valori mancanti (`NaN`) non sono previsti nel dataset finale. Il processo di costruzione del dataset è progettato esplicitamente per identificare i paesi mancanti nel file `cod_population_admin1.csv` e importarli da fonti specifiche per garantire una copertura totale.

---

## Statistiche di processing

### Riepilogo globale

| Metrica | Valore |
|---|---|
| Righe estratte da fonte primaria (HDX) | 730 (dopo filtraggio per `Gender=="all"` e `Age_range=="all"`) |
| Paesi mancanti identificati | 5 (AFG, GMB, GNB, LBN, YEM) |
| Aggiunte AFG (Province) | 34 |
| Aggiunte LBN (Governatorati) | 8 |
| Aggiunte YEM (Governatorati) | Aggregato da ADM2 |
| Aggiunte GMB (Aree Amministrative) | 8 |
| Aggiunte GNB (Regioni) | 9 |

L'identificazione dei paesi mancanti è stata effettuata confrontando la lista dei paesi (ISO3) presente nel master file IPC con quelli presenti nel database globale HDX della popolazione.

---

## Note metodologiche

**Dati Libano (LBN)**: I dati del Libano derivano da un file di pianificazione (LRP 2026) in cui la popolazione è indicata como "TOTAL LEBANESE". I nomi delle regioni sono stati normalizzati tramite un dizionario hardcoded (es. "Mount Lebanon" in "LB-JL").

**Dati Yemen (YEM)**: Il file originale dello Yemen presentava la popolazione a livello ADM2 (distretti) con la popolazione formattata come stringa con separatore delle migliaia (es. "17.138.738"). Durante il preprocessing, i punti sono stati rimossi per la conversione in interi, e i dati sono stati raggruppati tramite `groupby` e sommati per ottenere i totali a livello ADM1.

**Dati Guinea-Bissau (GNB)**: In assenza di file CSV strutturati, i dati demografici per i 9 settori/regioni (es. Bissau, Gabú, Bafatá) sono stati hardcodati direttamente nello script di data engineering associandoli ai rispettivi ADM1_PCODE.

**Popolazione Totale**: La granularità originale del file HDX comprendeva stratificazioni per età e genere. Il subset per HERO è stato isolato filtrando esplicitamente le righe in cui `Gender == 'all'` e `Age_range == 'all'`, scartando i dettagli demografici non necessari per le aggregazioni base.

---

## Pipeline di produzione

1. **Identificazione Target** — Estrazione della lista dei paesi unici (ISO3) dal file `ipc_global_area_long_pcoded.csv`.
2. **Filtraggio Base HDX** — Caricamento di `cod_population_admin1.csv`, filtraggio per la popolazione totale complessiva e mantenimento delle sole colonne `ISO3`, `ADM1_PCODE` e `Population`.
3. **Analisi dei Gap** — Confronto tra i paesi IPC e i paesi nel dataframe HDX per isolare gli ISO3 mancanti.
4. **Integrazione AFG** — Caricamento di `AFG_ADM1.csv`, standardizzazione delle colonne e concatenazione al dataframe master.
5. **Integrazione LBN** — Caricamento di `lebanon.csv` (saltando le righe di intestazione sporche), mapping testuale-a-PCODE tramite dizionario, standardizzazione colonne e concatenazione.
6. **Integrazione YEM** — Caricamento di `yemen.csv`, pulizia delle stringhe numeriche (rimozione punti), casting a integer, aggregazione somma (`groupby`) al livello ADM1 e concatenazione.
7. **Integrazione GMB** — Caricamento di `GMB_ADM1.csv`, estrazione colonna dei totali, standardizzazione e concatenazione.
8. **Integrazione GNB** — Creazione di un DataFrame da dizionario Python hardcoded con dati puntuali estratti da report, e concatenazione.
9. **Export** — Salvataggio del dataframe unificato in `population_admin1.csv`.