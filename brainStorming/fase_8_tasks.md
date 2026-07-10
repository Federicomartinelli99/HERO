# Checklist di Sviluppo - FASE 8: Visualizzazione Interattiva (Data Visual Analytics)

Questo documento contiene i dettagli implementativi e la checklist per la **Fase 8**. L'obiettivo è realizzare la dashboard web interattiva per l'esplorazione cartografica, temporale, stagionale e di scenario (What-If) basata su Folium, Altair e ApexCharts.

---

## 📋 Task List

### `[ ]` Task 8.1: Cartografia Digitale Geospaziale (Folium)
* **Descrizione**: Realizzare la mappa choropleth interattiva con controllo temporale e marker degli shock.
* **Sotto-task**:
  * `[ ]` Caricare i dati geografici provinciali/distrettuali (GeoJSON) ed allinearli al dataset IPC.
  * `[ ]` Inizializzare la mappa Folium centrata sull'area di studio.
  * `[ ]` Creare la choropleth map colorata secondo il target `phase_3plus_percentage`.
  * `[ ]` Implementare il plugin `TimeSliderChoropleth` per consentire lo scorrimento temporale mese per mese.
  * `[ ]` Aggiungere marker sui centroidi delle province colpite da anomalie significative (Z-score del Matrix Profile > 2.0).

---

### `[ ]` Task 8.2: Tabella Macro-Confronto (ApexCharts Heatmap Matrix)
* **Descrizione**: Configurare la matrice globale per il monitoraggio.
* **Sotto-task**:
  * `[ ]` Preparare il dataset aggregato (Paese/Provincia vs Date).
  * `[ ]` Configurare ApexCharts in Javascript (`app.js`) per caricare la heatmap.
  * `[ ]` Implementare il callback `dataPointSelection` per fare in modo che, al clic su una cella (es. una provincia in una determinata data), il resto della dashboard mostri i dettagli di quella provincia.

---

### `[ ]` Task 8.3: Trend Cartesiani e Toggles del Layout (Linear vs Circular)
* **Descrizione**: Sviluppare i grafici di trend e il toggle di coordinate.
* **Sotto-task**:
  * `[ ]` Implementare i trend cartesiani per IPC, ACLED, IDP, Rainfall (dual axis), WFP, NDVI (dual axis) e GDELT.
  * `[ ]` Sviluppare l'interruttore logico `chart-layout-toggle-group`.
  * `[ ]` Configurare la conversione dinamica: se impostato su "circular/radar", distruggere i grafici cartesiani e rigenerare i grafici a radar (polari) che riassumono la stagionalità o i descrittori strutturali della provincia.

---

### `[ ]` Task 8.4: Profili Stagionali con Radar Sincronizzati
* **Descrizione**: Implementare i 12 grafici a radar con evidenziazione coordinata del trimestre.
* **Sotto-task**:
  * `[ ]` Raggruppare i dati storici per trimestre (Q1, Q2, Q3, Q4) e per anno per tutti i 12 indicatori seasonal.
  * `[ ]` Generare i 12 grafici a radar ApexCharts con colorazione a gradienti.
  * `[ ]` Sviluppare la funzione Javascript `highlightMarkerInAllSeasonalCharts(qIndex)` per intercettare l'hover sul trimestre $q$ di uno qualsiasi dei radar ed applicare la classe di highlight sullo stesso trimestre in tutti gli altri 11 grafici.
  * `[ ]` Sviluppare `clearHighlightInAllSeasonalCharts()` al mouseout.

---

### `[ ]` Task 8.5: Simulatore di Scenario ("What-If" Analysis)
* **Descrizione**: Realizzare l'interfaccia di simulazione causale.
* **Sotto-task**:
  * `[ ]` Creare gli slider HTML per controllare le variazioni percentuali fittizie dei driver (NDVI, ACLED, prezzi WFP).
  * `[ ]` Inserire il pulsante "Simula Shock".
  * `[ ]` Sviluppare la logica in `app.js` che, al clic, moltiplica l'input per i coefficienti del modello VAR appresi per tracciare la risposta impulsiva simulata dell'IPC3+ per i successivi 6 mesi.
  * `[ ]` Rappresentare graficamente la traiettoria simulata (linea tratteggiata rossa) sovrapposta alla proiezione di base (linea blu).
  * `[ ]` Salvare i file in `UI/` ed eseguire i test locali.
