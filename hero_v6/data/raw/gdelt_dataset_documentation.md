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

| Root code | Etichetta | QuadClass 

| 01 | Make Public Statement | Verbal Cooperation 
| 02 | Appeal | Verbal Cooperation 
| 03 | Express Intent to Cooperate 
| 04 | Consult | Verbal Cooperation 
| 05 | Engage in Diplomatic Cooperation | Verbal Cooperation 
| 06 | Engage in Material Cooperation | Material Cooperation 
| 07 | Provide Aid | Material Cooperation 
| 08 | Yield | Verbal Conflict 
| 09 | Investigate | Verbal Conflict 
| 10 | Demand | Verbal Conflict 
| 11 | Disapprove | Verbal Conflict 
| 12 | Reject | Verbal Conflict 
| 13 | Threaten | Verbal Conflict 
| 14 | Protest | Verbal Conflict
| 15 | Exhibit Force Posture | Verbal Conflict 
| 16 | Reduce Relations | Verbal Conflict 
| 17 | Coerce | Material Conflict
| 18 | Assault | Material Conflict
| 19 | Fight | Material Conflict 
| 20 | Use Unconventional Mass Violence | Material Conflict 

---

## Valori mancanti

I valori `NaN` nelle colonne `avg_tone_{rc}` e `n_events_{rc}` indicano che in quella regione/mese non è stato registrato nessun evento di quella categoria — assenza di segnale, non dato mancante in senso stretto. Le colonne più sparse sono quelle dei root code rari (es. `avg_tone_20`: 73.023 NaN su 80.576 righe, pari al 90.6%), in quanto la violenza di massa non è un evento frequente.

Le colonne `n_events_{rc}` e `total_mentions_{rc}` sono trattate come 0 in assenza di eventi. Le colonne `avg_tone_{rc}` invece non vanno imputate a zero (il tono neutro è 0, ma l'assenza di eventi non equivale a tono neutro).

---

## Note metodologiche

**Geocodifica GDELT**: le coordinate lat/long degli eventi GDELT sono estratte automaticamente dal testo degli articoli tramite il gazetteer GNS (National Geospatial-Intelligence Agency). La precisione è variabile: alcuni eventi hanno coordinate al centroide della città menzionata, altri al centroide del paese. Questo introduce un errore di geocodifica che si manifesta come eventi non assegnati a nessuna regione ADM1 dopo lo spatial join (rate medio <1% per la maggior parte dei paesi, ma >60% per paesi insulari come Cabo Verde).

**Unità di misura del tono**: `AvgTone` in GDELT è calcolato dal sistema LIWC (Linguistic Inquiry and Word Count) applicato al testo dell'articolo. Riflette il sentiment linguistico della copertura, non una valutazione oggettiva della gravità degli eventi. Due articoli sullo stesso fatto possono avere toni molto diversi.

**Doppio conteggio**: GDELT applica deduplicazione degli eventi, ma un fatto reale può generare più `GLOBALEVENTID` se codificato diversamente da articoli diversi. Il conteggio `n_events` misura quindi "attività di estrazione GDELT", non "fatti reali distinti" in senso stretto.

---

## Pipeline di produzione

1. **Query BigQuery** — estrazione eventi disaggregati (lat/long, EventRootCode, NumMentions, AvgTone) dalla tabella `gdelt-bq.gdeltv2.events_partitioned`, filtrata per i 48 codici FIPS dei paesi IPC e per il periodo 2017–2026
2. **Spatial join** — assegnazione del pcode ADM1 HDX a ogni evento tramite `gpd.sjoin(..., predicate="within")` con gli shapefile ufficiali OCHA/COD-AB, algoritmo di recovery per il recupero
di punti vicini ai confini (entro un raggio di 20 km)
3. **Aggregazione** — calcolo di `n_events`, `total_mentions`, `avg_tone` (media pesata per NumMentions) per ogni cella `adm1_pcode × year × month × EventRootCode`
4. **Pivot wide** — trasformazione da formato long (una riga per root code) a formato wide (una riga per cella spazio-temporale, 60 colonne numeriche)
5. **Salvataggio** — formato Parquet (`df_gdelt_pivot.parquet`)
