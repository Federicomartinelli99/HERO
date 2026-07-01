# Dataset GDELT – Media-Based Conflict & Instability Signals (ADM2)
**Progetto HERO – Hunger Early-warning & Risk Optimizer**

---

## Descrizione

Il dataset GDELT (Global Database of Events, Language, and Tone) è un sistema di monitoraggio mediatico globale che estrae automaticamente eventi da articoli di notizie in tutto il mondo, aggiornato quotidianamente. Ogni evento è codificato secondo la tassonomia **CAMEO** (Conflict and Mediation Event Observations), che classifica le azioni tra attori geopolitici in 20 categorie root code, raggruppabili in 4 QuadClass.

Nel contesto del progetto HERO, questo dataset fornisce **segnali media-based in quasi tempo reale** sui fenomeni di instabilità (conflitto, proteste, risposta umanitaria) che tipicamente precedono o accompagnano le crisi alimentari, complementando le fonti strutturate (IPC, ACLED, IOM DTM) che per natura sono prodotte con ritardo rispetto agli eventi sul campo.

---

## Fonte e accesso

- **Fonte**: GDELT Project ([gdeltproject.org](https://www.gdeltproject.org))
- **Tabella BigQuery**: `gdelt-bq.gdeltv2.events_partitioned`
- **Accesso**: Google BigQuery (dataset pubblico, quota gratuita 1 TB/mese)
- **Documentazione CAMEO**: [gdeltproject.org/data/documentation/CAMEO.Manual.1.1b3.pdf](http://gdeltproject.org/data/documentation/CAMEO.Manual.1.1b3.pdf)

---

## Granularità

Ogni riga del dataset finale rappresenta una **cella spazio-temporale**: la combinazione univoca di paese × regione ADM1 × distretto ADM2 × anno × mese. Per ogni cella sono disponibili variabili numeriche disaggregate per EventRootCode (20 categorie) e per QuadClass (4 categorie).

---

## Copertura geografica

- **Paesi**: 48 (lista IPC)
- **Livello geografico**: ADM2 (distretti/comuni), con pcode HDX/COD; incluso anche il pcode ADM1 di appartenenza
- **Regioni ADM2 uniche**: 5.769
- **Assegnazione geografica**: spatial join tra le coordinate lat/long degli eventi GDELT e gli shapefile ADM2 ufficiali OCHA/HDX. Gli eventi con coordinate fuori dai poligoni vengono recuperati tramite fallback Nearest Neighbor entro 20 km. Gli eventi non recuperabili vengono scartati.

I 48 paesi coperti sono: AFG, AGO, BDI, BEN, BFA, BGD, CAF, CIV, CMR, COD, CPV, DJI, ECU, ETH, GHA, GIN, GMB, GNB, GTM, HND, HTI, KEN, LBR, LSO, MDG, MLI, MOZ, MRT, NAM, NER, NGA, PAK, SDN, SEN, SLE, SLV, SOM, SSD, SWZ, TCD, TGO, TLS, TZA, UGA, YEM, ZAF, ZMB, ZWE.

---

## Copertura temporale

- **Periodo**: gennaio 2017 – giugno 2026
- **Risoluzione temporale**: mensile
- **Fonte temporale**: GDELT 2.0 (`events_partitioned`, disponibile dal 2015)

---

## Struttura del dataset

**Dimensioni**: 2.695.764 righe × 10 colonne (formato long, prima del pivot)

**Colonne identificative** (6):

| Colonna | Tipo | Descrizione |
|---|---|---|
| `iso3` | str | Codice ISO 3166-1 alpha-3 del paese |
| `adm1_pcode` | str | Pcode HDX/COD della regione ADM1 |
| `adm2_pcode` | str | Pcode HDX/COD del distretto ADM2 |
| `year` | int | Anno dell'osservazione |
| `month` | int | Mese dell'osservazione (1–12) |
| `EventRootCode` | str | Codice root CAMEO dell'azione (01–20) |
| `QuadClass` | int | Raggruppamento macro CAMEO (1–4) |

**Colonne numeriche** (3):

| Colonna | Descrizione |
|---|---|
| `n_events` | Numero di eventi distinti registrati da GDELT |
| `total_mentions` | Somma delle menzioni di tutti gli eventi |
| `avg_tone` | Tono medio della copertura mediatica, pesato per NumMentions |

---

## I 20 root code CAMEO e le 4 QuadClass

| Root code | Etichetta | QuadClass |
|---|---|---|
| 01 | Make Public Statement | 1 – Verbal Cooperation |
| 02 | Appeal | 1 – Verbal Cooperation |
| 03 | Express Intent to Cooperate | 1 – Verbal Cooperation |
| 04 | Consult | 1 – Verbal Cooperation |
| 05 | Engage in Diplomatic Cooperation | 1 – Verbal Cooperation |
| 06 | Engage in Material Cooperation | 2 – Material Cooperation |
| 07 | Provide Aid | 2 – Material Cooperation |
| 08 | Yield | 2 – Material Cooperation |
| 09 | Investigate | 2 – Material Cooperation |
| 10 | Demand | 3 – Verbal Conflict |
| 11 | Disapprove | 3 – Verbal Conflict |
| 12 | Reject | 3 – Verbal Conflict |
| 13 | Threaten | 3 – Verbal Conflict |
| 14 | Protest | 3 – Verbal Conflict |
| 15 | Exhibit Force Posture | 4 – Material Conflict |
| 16 | Reduce Relations | 4 – Material Conflict |
| 17 | Coerce | 4 – Material Conflict |
| 18 | Assault | 4 – Material Conflict |
| 19 | Fight | 4 – Material Conflict |
| 20 | Use Unconventional Mass Violence | 4 – Material Conflict |

Il mapping QuadClass → EventRootCode è stato verificato direttamente dalla tabella BigQuery `gdelt-bq.gdeltv2.events_partitioned`.

---

## Calcolo delle metriche

**`n_events`**: conteggio degli eventi distinti per cella spazio-temporale.

**`total_mentions`**: somma del campo `NumMentions` di GDELT. Un evento riportato da 50 testate diverse genera 50 menzioni. Misura la salienza mediatica — concettualmente diversa dal volume: un singolo evento molto riportato può avere più menzioni di decine di eventi ignorati.

**`avg_tone`**: tono medio della copertura mediatica, calcolato come **media pesata per NumMentions** del campo `AvgTone` di GDELT. Valori negativi indicano copertura negativa/allarmistica, valori positivi copertura positiva. La formula applicata è:

$$\text{avg\_tone} = \frac{\sum_i \text{AvgTone}_i \times \text{NumMentions}_i}{\sum_i \text{NumMentions}_i}$$

La ponderazione per NumMentions è scelta consapevolmente: eventi con maggiore copertura mediatica influenzano il tono aggregato proporzionalmente alla loro rilevanza percepita dai media.

---

## Valori mancanti

I valori `NaN` in `avg_tone` indicano che in quella cella non è stato registrato nessun evento di quella categoria — assenza di segnale, non dato mancante in senso stretto. Le colonne `n_events` e `total_mentions` possono essere imputate a 0 in assenza di eventi (corretto per conteggi). `avg_tone` invece non va imputata a 0 (il tono neutro è 0, ma l'assenza di eventi non equivale a tono neutro).

---

## Statistiche di processing

### Riepilogo globale

| Metrica | Valore |
|---|---|
| Eventi totali scaricati da BigQuery | 65.814.898 |
| Eventi fuori dai poligoni ADM2 (within) | 1.038.338 (1,58%) |
| Recuperati con fallback Nearest Neighbor (≤20 km) | 768.770 (74,0% dei fuori) |
| Orfani definitivi (distanza >20 km, scartati) | 269.568 (0,41%) |
| Righe nel dataset finale (long) | 2.695.764 |

Il tasso di orfani definitivi è molto basso (0,41% del totale), con due eccezioni significative legate alla geografia: **Cabo Verde** (CPV, 71,7% orfani) e **Djibouti** (DJI, 67,0% orfani). In entrambi i casi il problema è strutturale — Cabo Verde è un arcipelago con molte coordinate in mare, e Djibouti ha una discrepanza tra il sistema di geocodifica GDELT e i poligoni HDX disponibili — e non è risolvibile con il fallback a 20 km.

### Dettaglio per paese

| ISO3 | ADM2 | Eventi scaricati | Fuori within | Recuperati | Orfani | % orfani | Righe aggregate |
|---|---|---|---|---|---|---|---|
| AFG | 401 | 4.603.574 | 7.451 | 5.009 | 2.442 | 0,1% | 131.054 |
| AGO | 161 | 478.754 | 11.339 | 11.299 | 40 | 0,0% | 35.528 |
| BDI | 119 | 227.985 | 18 | 0 | 18 | 0,0% | 18.248 |
| BEN | 77 | 265.591 | 201 | 96 | 105 | 0,0% | 9.296 |
| BFA | 47 | 403.665 | 32 | 32 | 0 | 0,0% | 21.474 |
| BGD | 64 | 3.683.389 | 16.429 | 16.285 | 144 | 0,0% | 101.501 |
| CAF | 85 | 175.543 | 280 | 280 | 0 | 0,0% | 14.818 |
| CIV | 108 | 339.705 | 41 | 41 | 0 | 0,0% | 19.738 |
| CMR | 58 | 546.584 | 11.474 | 10.988 | 486 | 0,1% | 41.090 |
| COD | 164 | 343.484 | 580 | 579 | 1 | 0,0% | 42.866 |
| CPV | 32 | 51.058 | 38.140 | 1.504 | 36.636 | **71,7%** | 2.774 |
| DJI | 20 | 313.592 | 215.781 | 5.741 | 210.040 | **67,0%** | 5.361 |
| ECU | 221 | 1.041.374 | 1.633 | 1.566 | 67 | 0,0% | 42.871 |
| ETH | 107 | 1.239.570 | 1.366 | 1.358 | 8 | 0,0% | 42.964 |
| GHA | 260 | 2.804.240 | 5.521 | 5.471 | 50 | 0,0% | 150.250 |
| GIN | 34 | 431.554 | 999 | 751 | 248 | 0,1% | 19.787 |
| GMB | 49 | 375.637 | 37.495 | 37.495 | 0 | 0,0% | 20.137 |
| GNB | 39 | 59.861 | 74 | 74 | 0 | 0,0% | 2.787 |
| GTM | 342 | 767.943 | 2.987 | 2.969 | 18 | 0,0% | 41.740 |
| HND | 298 | 756.286 | 19.238 | 19.016 | 222 | 0,0% | 34.475 |
| HTI | 140 | 846.104 | 5.583 | 5.063 | 520 | 0,1% | 30.702 |
| KEN | 290 | 2.796.263 | 27.473 | 27.350 | 123 | 0,0% | 194.334 |
| LBR | 136 | 606.029 | 6.697 | 6.564 | 133 | 0,0% | 41.211 |
| LSO | 78 | 172.707 | 44 | 44 | 0 | 0,0% | 19.156 |
| MDG | 119 | 207.336 | 984 | 608 | 376 | 0,2% | 24.859 |
| MLI | 160 | 1.162.008 | 190 | 50 | 140 | 0,0% | 54.334 |
| MOZ | 159 | 382.240 | 2.175 | 1.596 | 579 | 0,2% | 35.877 |
| MRT | 63 | 249.515 | 111.682 | 111.662 | 20 | 0,0% | 11.806 |
| NAM | 107 | 390.699 | 9.119 | 3.900 | 5.219 | 1,3% | 41.819 |
| NER | 67 | 602.159 | 1.898 | 928 | 970 | 0,2% | 26.325 |
| NGA | 774 | 12.718.422 | 91.016 | 90.885 | 131 | 0,0% | 498.372 |
| PAK | 160 | 9.075.217 | 60.888 | 60.865 | 23 | 0,0% | 214.871 |
| SDN | 189 | 2.089.975 | 1.008 | 971 | 37 | 0,0% | 56.930 |
| SEN | 46 | 614.415 | 286.308 | 286.306 | 2 | 0,0% | 27.511 |
| SLE | 16 | 253.191 | 1.226 | 1.205 | 21 | 0,0% | 13.330 |
| SLV | 48 | 580.420 | 639 | 639 | 0 | 0,0% | 19.846 |
| SOM | 91 | 1.131.270 | 911 | 911 | 0 | 0,0% | 39.166 |
| SSD | 79 | 423.674 | 1.672 | 1.672 | 0 | 0,0% | 30.326 |
| SWZ | 55 | 74.601 | 357 | 327 | 30 | 0,0% | 9.797 |
| TCD | 70 | 421.588 | 458 | 364 | 94 | 0,0% | 12.607 |
| TGO | 40 | 173.795 | 231 | 226 | 5 | 0,0% | 9.009 |
| TLS | 65 | 95.572 | 174 | 89 | 85 | 0,1% | 5.098 |
| TZA | 170 | 652.613 | 24.352 | 15.694 | 8.658 | 1,3% | 61.397 |
| UGA | 135 | 1.214.783 | 9.331 | 9.331 | 0 | 0,0% | 91.377 |
| YEM | 335 | 1.951.122 | 1.810 | 1.810 | 0 | 0,0% | 93.335 |
| ZAF | 52 | 5.871.924 | 12.074 | 10.791 | 1.283 | 0,0% | 95.180 |
| ZMB | 116 | 482.423 | 4.938 | 4.934 | 4 | 0,0% | 50.547 |
| ZWE | 91 | 1.665.444 | 4.021 | 3.431 | 590 | 0,0% | 87.883 |

---

## Note metodologiche

**Geocodifica GDELT**: le coordinate lat/long degli eventi GDELT sono estratte automaticamente dal testo degli articoli tramite il gazetteer GNS (National Geospatial-Intelligence Agency). La precisione è variabile: alcuni eventi hanno coordinate al centroide della città menzionata, altri al centroide del paese. Questo introduce un errore di geocodifica che si manifesta come eventi non assegnati a nessuna regione ADM2 dopo lo spatial join primario (`within`). Il fallback Nearest Neighbor entro 20 km recupera la maggior parte di questi casi. Gli eventi non recuperabili nemmeno con il fallback (distanza > 20 km dai confini, tipici di paesi insulari come Cabo Verde) vengono scartati.

**Unità di misura del tono**: `AvgTone` in GDELT è calcolato dal sistema LIWC (Linguistic Inquiry and Word Count) applicato al testo dell'articolo. Riflette il sentiment linguistico della copertura, non una valutazione oggettiva della gravità degli eventi. Due articoli sullo stesso fatto possono avere toni molto diversi.

**Doppio conteggio**: GDELT applica deduplicazione degli eventi, ma un fatto reale può generare più `GLOBALEVENTID` se codificato diversamente da articoli diversi. Il conteggio `n_events` misura quindi "attività di estrazione GDELT", non "fatti reali distinti" in senso stretto.

---

## Pipeline di produzione

1. **Query BigQuery** — estrazione eventi disaggregati (lat/long, EventRootCode, QuadClass, NumMentions, AvgTone) dalla tabella `gdelt-bq.gdeltv2.events_partitioned`, filtrata per i 48 codici FIPS dei paesi IPC e per il periodo 2017–2026
2. **Spatial join** — assegnazione del pcode ADM2 HDX a ogni evento tramite `gpd.sjoin(..., predicate="within")` con gli shapefile ufficiali OCHA/COD-AB; viene estratto anche il pcode ADM1 di appartenenza
3. **Fallback Nearest Neighbor (entro 20 km)** — gli eventi con coordinate fuori dai poligoni ADM2 vengono recuperati tramite un secondo join al vicino più prossimo con raggio massimo di 20.000 metri. Il join avviene in proiezione metrica (EPSG:3857) per garantire la correttezza del calcolo delle distanze in metri. Gli eventi ancora non assegnati dopo questo step (distanza > 20 km) vengono scartati.
4. **Aggregazione** — calcolo di `n_events`, `total_mentions`, `avg_tone` (media pesata per NumMentions) per ogni cella `adm1_pcode × adm2_pcode × year × month × EventRootCode × QuadClass`
5. **Salvataggio** — formato Parquet (`gdelt_adm2_final.parquet`)
