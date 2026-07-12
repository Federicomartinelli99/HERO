# FASE 8: Visualizzazione Interattiva (Data Visual Analytics)

L'output del progetto include un'applicazione di dashboard web interattiva e visualizzazione geospaziale avanzata che rispecchia l'esatta struttura dei componenti attivi nella UI:

---

## 1. Visualizzazione Geospaziale e Cartografia Digitale (Folium & GeoPandas)
* **Choropleth Map Animata**: Mappa interattiva a livello Admin 1 (provinciale) e Admin 2 (distrettuale) colorata in base alla percentuale `phase_3plus_percentage`, controllata da uno slider temporale per visualizzare l'evoluzione e la propagazione geografica della crisi.
* **Marker geografici di Shock**: Puntatori posizionati sui centroidi delle province in cui il Matrix Profile rileva shock sistemici superati la soglia $Z > 2.0$ (Discord).

---

## 2. Tabella di Macro-Confronto (Heatmap Matrix con ApexCharts)
* **Heatmap dei Paesi e delle Province**: Tabella interattiva a doppia entrata (Paese/Provincia vs Tempo) in ApexCharts che permette il drill-down sul livello di insicurezza alimentare globale ed evidenzia i territori più critici a colpo d'occhio.

---

## 3. Pannello Principale dei Trend Temporali (Cartesiano/Lineare)
Grafici a linee/area cartesiani interattivi con asse temporale continuo (`app.js` references):
* **Fasi IPC (`chart-ipc`)**: Andamento della percentuale della popolazione ripartita per ciascuna delle 5 classi IPC nel tempo.
* **Conflitti ACLED (`chart-acled`)**: Grafico a linee multi-variabile per tracciare contemporaneamente la frequenza degli eventi e il numero delle vittime per tipologia (political violence, civilian targeting, demonstrations).
* **Sfollati IDP (`chart-idp`)**: Curva della popolazione sfollata interna registrata nel tempo.
* **Precipitazioni CHIRPS (`chart-rainfall` - Dual Axis)**: Barre verticali indicanti le piogge accumulate mensili e linea sovrapposta indicante l'anomalia climatica rispetto allo storico.
* **Mercati Alimentari WFP (`chart-wfp`)**: Line plot dei prezzi medi ponderati e dei tassi inflazionistici mensili.
* **Vigore Vegetativo NDVI (`chart-ndvi` - Dual Axis)**: Curva del vigore vegetativo medio (`ndvi_vim`) e della qualità vegetativa (`ndvi_viq`) per monitorare la siccità agricola.
* **Sentiment Media GDELT (`chart-gdelt`)**: Trend delle notizie giornalistiche indicizzate per QuadClass di conflitto/cooperazione verbale e materiale.

---

## 4. Pannello dei Profili Stagionali (12 Radar/Circular Charts Sincronizzati)
* **Radar a 4 Vertici (Trimestrali - Q1, Q2, Q3, Q4)** con colorazione a gradienti. 
* **Interazione e Hover Sincronizzato**: Cliccando o passando il mouse su un determinato quarto (es. Q3) in uno dei 12 indicatori (es. `chart-rainfall-rain-seasonal`), tutti gli altri 11 grafici radar stagionali (IPC, prezzi, NDVI, conflitti, ecc.) evidenziano istantaneamente lo stesso quarto. Questo permette agli analisti di identificare visivamente la latenza stagionale e le relazioni tra anomalie delle piogge e conseguente impennata dell'IPC o dei conflitti nello stesso trimestre o in quelli successivi.

---

## 5. Sotto-View dei Mercati Alimentari Locali (WFP Market Charts)
* **Dettaglio Prezzi ed Inflazione**: Grafici dedicati (`chart-market-price-index` e `chart-market-inflation`) per visualizzare l'andamento dei prezzi dei singoli mercati all'interno della provincia selezionata.

---

## 6. Pannello GDELT Avanzato (Tone & Salience)
* **Analisi dei Media**: Grafici interattivi (`chart-gdelt-tab-tone` e `chart-gdelt-tab-salience`) focalizzati esclusivamente sul sentiment giornalistico complessivo del paese (Tone) e sul volume globale di notizie prodotte (Salience).

---

## 7. Pannello di Confronto Dati Grezzi vs Processati (Diagnostics)
* **Visualizzazione Preprocessing**: Grafico comparativo (`chart-compare`) che mostra la sovrapposizione tra la serie temporale originale contenente i dati grezzi con vuoti e NaN (raw data) e la corrispondente serie ricostruita/imputata spaziotemporalmente, per monitorare la fedeltà del preprocessing.

---

## 8. Pannello di Simulazione e Analisi di Scenario ("What-If" Analysis)
* **Simulazione Causalità Dinamica**: Integrazione di cursori interattivi (slider) associati a ciascun driver (es. simulazione di una riduzione del 30% dell'NDVI o un incremento di eventi ACLED). Cliccando sul pulsante "Simula Shock", l'interfaccia invocherà i coefficienti del modello VAR per tracciare in tempo reale la propagazione temporale teorica dello shock simulato sull'IPC3+ della provincia selezionata per i successivi 6 mesi.

---

## 📊 Grafici e Visualizzazioni per la FASE 8 (Layout Interattivo)
* **Linked Scatter + Line Plot (Altair)**: Cliccando su una provincia nella mappa geospaziale Folium (o in un grafico a dispersione PCA dei cluster), una seconda serie temporale Altair adiacente si aggiorna istantaneamente mostrando la "Crisis Timeline" di quel territorio specifico.
* **Time-Series Horizon Chart**: Grafico a bande di colore sovrapposte (Horizon Chart) per visualizzare simultaneamente l'andamento di decine di province su una singola pagina senza affollamento visivo, facilitando il confronto visivo di trend divergenti.
* **Visualizzatore Interattivo "What-If" (Altair / D3)**: Grafico temporale con due linee: una linea continua che mostra la proiezione di base (baseline forecast) e una linea tratteggiata rossa dinamica che mostra la traiettoria IPC3+ simulata dall'utente manipolando gli slider dei driver di siccità e conflitto.
