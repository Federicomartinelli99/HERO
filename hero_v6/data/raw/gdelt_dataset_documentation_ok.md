# Dataset GDELT – Media-Based Conflict & Instability Signals
**Progetto HERO – Hunger Early-warning & Risk Optimizer**

---

## Descrizione

Il dataset GDELT (Global Database of Events, Language, and Tone) è un sistema di monitoraggio mediatico globale che estrae automaticamente eventi da articoli di notizie in tutto il mondo, aggiornato quotidianamente. Ogni evento è codificato secondo la tassonomia **CAMEO** (Conflict and Mediation Event Observations), che classifica le azioni tra attori geopolitici in 20 categorie root code.

Nel contesto del progetto HERO, questo dataset fornisce **segnali media-based in quasi tempo reale** sui fenomeni di instabilità (conflitto, proteste, risposta umanitaria) che tipicamente precedono o accompagnano le crisi alimentari, complementando le fonti strutturate (IPC, ACLED, IOM DTM) che per natura sono prodotte con ritardo rispetto agli eventi sul campo.

---

## Fonte e accesso

- **Fonte**: GDELT Project ([gdeltproject.org](https://www.gdeltproject.org))
- **Tabella BigQuery**: `gdelt-bq.gdeltv2.events_partitioned`
- **Accesso**: Google BigQuery (dataset pubblico, quota gratuita 1 TB/mese)
- **Documentazione CAMEO**: [gdeltproject.org/data/documentation/CAMEO.Manual.1.1b3.pdf](http://gdeltproject.org/data/documentation/CAMEO.Manual.1.1b3.pdf)

---

## Granularità

Ogni riga del dataset finale rappresenta una **cella spazio-temporale**: la combinazione univoca di paese × regione ADM1 × anno × mese. Per ogni cella sono disponibili 60 variabili numeriche (3 metriche × 20 root code CAMEO).

---

## Copertura geografica

- **Paesi**: 48 (lista IPC)
- **Livello geografico**: ADM1 (regioni/province), con pcode HDX/COD
- **Regioni ADM1 uniche**: 770
- **Assegnazione geografica**: spatial join tra le coordinate lat/long degli eventi GDELT e gli shapefile ADM1 ufficiali OCHA/HDX. Gli eventi con coordinate fuori dai poligoni (es. paesi insulari come Cabo Verde) vengono scartati.

I 48 paesi coperti sono: AFG, AGO, BDI, BEN, BFA, BGD, CAF, CIV, CMR, COD, CPV, DJI, ECU, ETH, GHA, GIN, GMB, GNB, GTM, HND, HTI, KEN, LBR, LSO, MDG, MLI, MOZ, MRT, NAM, NER, NGA, PAK, SDN, SEN, SLE, SLV, SOM, SSD, SWZ, TCD, TGO, TLS, TZA, UGA, YEM, ZAF, ZMB, ZWE.

---

## Copertura temporale

- **Periodo**: gennaio 2017 – giugno 2026
- **Risoluzione temporale**: mensile
- **Fonte temporale**: GDELT 2.0 (`events_partitioned`, disponibile dal 2015)

---

## Struttura del dataset

**Dimensioni**: 80.576 righe × 64 colonne

**Colonne identificative** (4):

| Colonna | Tipo | Descrizione |
|---|---|---|
| `iso3` | str | Codice ISO 3166-1 alpha-3 del paese |
| `adm1_pcode` | str | Pcode HDX/COD della regione ADM1 |
| `year` | Int64 | Anno dell'osservazione |
| `month` | Int64 | Mese dell'osservazione (1–12) |

**Colonne numeriche** (60): 3 metriche × 20 root code CAMEO, nel formato `{metrica}_{rootcode}` (es. `n_events_01`, `avg_tone_14`, `total_mentions_19`).

---

## Variabili per root code

Per ciascuno dei 20 root code CAMEO sono disponibili tre metriche:

**`n_events_{rc}`** — Numero di eventi distinti registrati da GDELT in quella regione/mese per quella categoria di azione. Misura il *volume* di attività riportata.

**`total_mentions_{rc}`** — Somma delle menzioni di tutti gli eventi (campo `NumMentions` di GDELT). Un evento riportato da 50 testate diverse genera 50 menzioni. Misura la *salienza mediatica* — concettualmente diversa dal volume: un singolo evento molto riportato può avere più menzioni di decine di eventi ignorati.

**`avg_tone_{rc}`** — Tono medio della copertura mediatica, calcolato come **media pesata per NumMentions** del campo `AvgTone` di GDELT. Valori negativi indicano copertura negativa/allarmistica, valori positivi copertura positiva. Range tipico: da circa –10 a +10 (estremi teorici –100/+100). La formula applicata è:

$$\text{avg\_tone} = \frac{\sum_i \text{AvgTone}_i \times \text{NumMentions}_i}{\sum_i \text{NumMentions}_i}$$

La ponderazione per NumMentions è scelta consapevolmente: eventi con maggiore copertura mediatica influenzano il tono aggregato proporzionalmente alla loro rilevanza percepita dai media.

---

## I 20 root code CAMEO

| Root code | Etichetta | QuadClass |
|---|---|---|
| 01 | Make Public Statement | Verbal Cooperation |
| 02 | Appeal | Verbal Cooperation |
| 03 | Express Intent to Cooperate | Verbal Cooperation |
| 04 | Consult | Verbal Cooperation |
| 05 | Engage in Diplomatic Cooperation | Verbal Cooperation |
| 06 | Engage in Material Cooperation | Material Cooperation |
| 07 | Provide Aid | Material Cooperation |
| 08 | Yield | Verbal Conflict |
| 09 | Investigate | Verbal Conflict |
| 10 | Demand | Verbal Conflict |
| 11 | Disapprove | Verbal Conflict |
| 12 | Reject | Verbal Conflict |
| 13 | Threaten | Verbal Conflict |
| 14 | Protest | Verbal Conflict |
| 15 | Exhibit Force Posture | Verbal Conflict |
| 16 | Reduce Relations | Verbal Conflict |
| 17 | Coerce | Material Conflict |
| 18 | Assault | Material Conflict |
| 19 | Fight | Material Conflict |
| 20 | Use Unconventional Mass Violence | Material Conflict |

---

## Valori mancanti

I valori `NaN` nelle colonne `avg_tone_{rc}` e `n_events_{rc}` indicano che in quella regione/mese non è stato registrato nessun evento di quella categoria — assenza di segnale, non dato mancante in senso stretto. Le colonne più sparse sono quelle dei root code rari (es. `avg_tone_20`: 73.023 NaN su 80.576 righe, pari al 90.6%), in quanto la violenza di massa non è un evento frequente.

Le colonne `n_events_{rc}` e `total_mentions_{rc}` sono trattate come 0 in assenza di eventi (imputazione a zero è metodologicamente corretta per conteggi). Le colonne `avg_tone_{rc}` invece non vanno imputate a zero (il tono neutro è 0, ma l'assenza di eventi non equivale a tono neutro).

---

## Statistiche di processing

### Riepilogo globale

| Metrica | Valore |
|---|---|
| Eventi totali scaricati da BigQuery | 65.775.707 |
| Eventi fuori dai poligoni ADM1 (within) | 1.036.325 (1,58%) |
| Recuperati con fallback Nearest Neighbor (≤20 km) | 766.870 (74,0% dei fuori) |
| Orfani definitivi (distanza >20 km, scartati) | 269.455 (0,41%) |
| Righe aggregate nel dataset finale (long) | 958.070 |
| Righe nel dataset finale (wide, dopo pivot) | 80.576 |

Il tasso di orfani definitivi è molto basso (0,41% del totale), con due eccezioni significative legate alla geografia: **Cabo Verde** (CPV, 71,8% orfani) e **Djibouti** (DJI, 67,0% orfani). In entrambi i casi il problema è strutturale — Cabo Verde è un arcipelago con molte coordinate in mare (molti eventi orfani sono assegnati a coordinate di quello che sembra il centroide delle coordinate del paese che risulta in mezzo all'oceano), e Djibouti ha una discrepanza tra il sistema di geocodifica GDELT e i poligoni HDX disponibili — e non è risolvibile con il fallback a 20 km.

### Dettaglio per paese

| ISO3 | Eventi scaricati | Fuori within | Recuperati | Orfani | % orfani | Righe aggregate |
|---|---|---|---|---|---|---|
| AFG | 4.602.418 | 7.451 | 5.009 | 2.442 | 0,1% | 55.253 |
| AGO | 478.593 | 11.339 | 11.299 | 40 | 0,0% | 20.494 |
| BDI | 227.949 | 18 | 0 | 18 | 0,0% | 13.863 |
| BEN | 265.394 | 201 | 96 | 105 | 0,0% | 7.602 |
| BFA | 403.188 | 32 | 32 | 0 | 0,0% | 16.782 |
| BGD | 3.680.932 | 16.429 | 16.285 | 144 | 0,0% | 17.383 |
| CAF | 175.512 | 280 | 280 | 0 | 0,0% | 12.261 |
| CIV | 339.596 | 41 | 41 | 0 | 0,0% | 17.335 |
| CMR | 546.392 | 11.472 | 10.986 | 486 | 0,1% | 16.684 |
| COD | 343.217 | 580 | 579 | 1 | 0,0% | 27.289 |
| CPV | 51.035 | 38.123 | 1.504 | 36.619 | **71,8%** | 2.767 |
| DJI | 313.459 | 215.694 | 5.739 | 209.955 | **67,0%** | 4.767 |
| ECU | 1.040.493 | 1.627 | 1.560 | 67 | 0,0% | 25.991 |
| ETH | 1.239.228 | 1.359 | 1.351 | 8 | 0,0% | 19.515 |
| GHA | 2.803.122 | 5.516 | 5.466 | 50 | 0,0% | 29.316 |
| GIN | 431.320 | 999 | 751 | 248 | 0,1% | 11.100 |
| GMB | 375.442 | 37.495 | 37.495 | 0 | 0,0% | 10.650 |
| GNB | 59.848 | 74 | 74 | 0 | 0,0% | 2.756 |
| GTM | 767.610 | 2.987 | 2.969 | 18 | 0,0% | 24.142 |
| HND | 756.030 | 19.233 | 19.011 | 222 | 0,0% | 19.992 |
| HTI | 844.401 | 5.583 | 5.063 | 520 | 0,1% | 13.568 |
| KEN | 2.794.186 | 27.437 | 27.314 | 123 | 0,0% | 80.754 |
| LBR | 605.658 | 6.663 | 6.530 | 133 | 0,0% | 21.486 |
| LSO | 172.586 | 44 | 44 | 0 | 0,0% | 11.012 |
| MDG | 207.249 | 984 | 608 | 376 | 0,2% | 17.134 |
| MLI | 1.161.832 | 190 | 50 | 140 | 0,0% | 28.302 |
| MOZ | 382.122 | 2.168 | 1.596 | 572 | 0,1% | 15.936 |
| MRT | 249.344 | 111.596 | 111.576 | 20 | 0,0% | 10.336 |
| NAM | 390.523 | 9.117 | 3.898 | 5.219 | 1,3% | 20.653 |
| NER | 601.922 | 1.898 | 928 | 970 | 0,2% | 13.512 |
| NGA | 12.706.771 | 89.430 | 89.299 | 131 | 0,0% | 79.843 |
| PAK | 9.071.144 | 60.856 | 60.833 | 23 | 0,0% | 15.531 |
| SDN | 2.088.978 | 1.008 | 971 | 37 | 0,0% | 30.244 |
| SEN | 614.135 | 286.219 | 286.217 | 2 | 0,0% | 17.231 |
| SLE | 253.119 | 1.226 | 1.205 | 21 | 0,0% | 8.015 |
| SLV | 579.936 | 639 | 639 | 0 | 0,0% | 14.823 |
| SOM | 1.130.656 | 911 | 911 | 0 | 0,0% | 26.220 |
| SSD | 423.493 | 1.672 | 1.672 | 0 | 0,0% | 16.445 |
| SWZ | 74.573 | 357 | 327 | 30 | 0,0% | 5.497 |
| TCD | 421.419 | 458 | 364 | 94 | 0,0% | 11.383 |
| TGO | 173.726 | 231 | 226 | 5 | 0,0% | 6.044 |
| TLS | 95.506 | 174 | 89 | 85 | 0,1% | 4.846 |
| TZA | 652.347 | 24.348 | 15.694 | 8.654 | 1,3% | 33.558 |
| UGA | 1.213.925 | 9.325 | 9.325 | 0 | 0,0% | 8.717 |
| YEM | 1.950.653 | 1.810 | 1.810 | 0 | 0,0% | 34.215 |
| ZAF | 5.867.769 | 12.072 | 10.789 | 1.283 | 0,0% | 19.700 |
| ZMB | 482.338 | 4.938 | 4.934 | 4 | 0,0% | 16.425 |
| ZWE | 1.664.618 | 4.021 | 3.431 | 590 | 0,0% | 20.698 |

## Note metodologiche

**Geocodifica GDELT**: le coordinate lat/long degli eventi GDELT sono estratte automaticamente dal testo degli articoli tramite il gazetteer GNS (National Geospatial-Intelligence Agency). La precisione è variabile: alcuni eventi hanno coordinate al centroide della città menzionata, altri al centroide del paese. Questo introduce un errore di geocodifica che si manifesta come eventi non assegnati a nessuna regione ADM1 dopo lo spatial join primario (`within`). Il fallback Nearest Neighbor entro 20 km recupera la maggior parte di questi casi (specialmente eventi con coordinate leggermente fuori confine per imprecisione numerica o paesi con geometrie complesse). Gli eventi non recuperabili nemmeno con il fallback (distanza > 20 km dai confini, tipici di paesi insulari come Cabo Verde) vengono scartati.

**Unità di misura del tono**: `AvgTone` in GDELT è calcolato dal sistema LIWC (Linguistic Inquiry and Word Count) applicato al testo dell'articolo. Riflette il sentiment linguistico della copertura, non una valutazione oggettiva della gravità degli eventi. Due articoli sullo stesso fatto possono avere toni molto diversi.

**Doppio conteggio**: GDELT applica deduplicazione degli eventi, ma un fatto reale può generare più `GLOBALEVENTID` se codificato diversamente da articoli diversi. Il conteggio `n_events` misura quindi "attività di estrazione GDELT", non "fatti reali distinti" in senso stretto.

**Confronto con ACLED**: GDELT misura la *percezione mediatica* del conflitto, ACLED misura gli *eventi reali verificati*. Le due fonti sono complementari: GDELT è più tempestivo (aggiornamento giornaliero) ma meno preciso; ACLED è più affidabile ma con latenza di alcune settimane.

---

## Pipeline di produzione

1. **Query BigQuery** — estrazione eventi disaggregati (lat/long, EventRootCode, NumMentions, AvgTone) dalla tabella `gdelt-bq.gdeltv2.events_partitioned`, filtrata per i 48 codici FIPS dei paesi IPC e per il periodo 2017–2026
2. **Spatial join** — assegnazione del pcode ADM1 HDX a ogni evento tramite `gpd.sjoin(..., predicate="within")` con gli shapefile ufficiali OCHA/COD-AB
3. **Fallback Nearest Neighbor (entro 20 km)** — gli eventi con coordinate fuori dai poligoni ADM1 (es. punti in prossimità dei confini o con leggera imprecisione di geocodifica) vengono recuperati tramite un secondo join al vicino più prossimo con raggio massimo di 20.000 metri. Il join avviene in proiezione metrica (EPSG:3857) per garantire la correttezza del calcolo delle distanze in metri. Gli eventi ancora non assegnati dopo questo step (distanza > 20 km) vengono scartati.
4. **Aggregazione** — calcolo di `n_events`, `total_mentions`, `avg_tone` (media pesata per NumMentions) per ogni cella `adm1_pcode × year × month × EventRootCode`
5. **Pivot wide** — trasformazione da formato long (una riga per root code) a formato wide (una riga per cella spazio-temporale, 60 colonne numeriche)
6. **Salvataggio** — formato Parquet (`df_gdelt_pivot.parquet`)
