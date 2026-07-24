# Piano di Implementazione: Text Anonymization & Spatiotemporal Ablation Pipeline

Questo documento descrive la strategia metodologica e l'architettura software per l'anonimizzazione avanzata e la rimozione di riferimenti spaziali e temporali dai report umanitari sull'insicurezza alimentare. Questa ablazione costituisce una fase preparatoria rigorosa per i task successivi di calcolo della similarità semantica e clustering.

---

## 1. Architettura della Pipeline (Struttura Logica del Codice)

Per garantire modularità ed efficienza operativa, la logica implementata nel notebook viene strutturata nei seguenti moduli concettuali:

```text
Anonymization/
│
├── config.py                 # Mapping globale delle entità (spaziali/temporali) e soglie di confidenza
├── data_loader.py            # Caricamento del dataset (report_originali.csv) e gestione esportazioni
│
├── models/
│   ├── __init__.py
│   ├── ner_model.py          # Caricamento e configurazione di GLiNER (Zero-shot NER)
│   └── nlp_utils.py          # Inizializzazione di spaCy (Sentencizer ottimizzato)
│
├── preprocessing/
│   ├── __init__.py
│   ├── segmentation.py       # Frammentazione dei testi lunghi in array di frasi
│   └── ablation.py           # Predizione entità e Backwards Replacement dei token testuali
│
└── pipeline.py               # Orchestratore principale (process_dataframe_safe)
```

---

## 2. Metodologia: Analisi ed Elaborazione dei Report

Il processo di de-identificazione geografica e temporale copre le seguenti fasi tecniche:

### A. Configurazione Modelli e Accelerazione Hardware
L'architettura impiega la GPU (CUDA) per parallelizzare i carichi di inferenza. Il riconoscimento delle entità è affidato a `gliner_large-v2` per la sua flessibilità Zero-shot. Per la tokenizzazione delle frasi viene utilizzato `en_core_web_sm` di spaCy. Per minimizzare i colli di bottiglia computazionali, i moduli pesanti di spaCy (`ner`, `parser`) vengono disabilitati esplicitamente, mantenendo attivo unicamente il modulo `sentencizer`.

### B. Mappatura Dinamica delle Entità (Tag Mapping)
Per standardizzare il corpus testuale ed evitare *data leakage* geografico o temporale durante le fasi di clustering, si applica una mappatura a dizionario chiusa:
*   **Ablazione Spaziale**: Le etichette *country, region, province, district, city, village, location, landmark* vengono unificate e sostituite dal placeholder `[AFFECTED_AREA]`.
*   **Ablazione Temporale**: Le etichette *year, month, date* vengono schiacciate e sostituite dal placeholder `[DATE]`.

### C. Segmentazione e Sostituzione (Backwards Replacement)
1.  **Sentencizing**: I documenti originali vengono scomposti in frasi singole. Questo garantisce che l'input inviato a GLiNER non superi mai il limite architetturale di contesto massimo consentito (512 token).
2.  **Inferenza NER**: Il modello estrae le coordinate delle entità basandosi su una soglia di confidenza minima fissata a `0.35`.
3.  **Sostituzione Posizionale Inversa**: Le entità individuate vengono ordinate in modo decrescente in base al loro indice di inizio (`start`). La sostituzione testuale con i placeholder avviene procedendo dalla fine della frase verso l'inizio, assicurando che lo scostamento del numero di caratteri non corrompa gli indici delle entità precedenti.

---

## 3. Generalizzazione & Elaborazione Batch

Per scalare il prototipo sull'intero corpus di dati storici:

### A. Integrazione DataFrame
La funzione `process_dataframe_safe` esegue la pipeline su tutta l'infrastruttura pandas. Itera i 497 report originali allocandone il contenuto nella colonna di destinazione `report_anonimo`. Il sistema è costruito per processare in sicurezza i testi, by-passando fluidamente stringhe vuote o formati non validi.

### B. Normalizzazione del Corpus
Il risultato finale è un dataset (`report_anonimizzati.csv`) contenente testi strutturalmente intatti ma privi di riferimenti specifici (es. "Between [DATE] and [DATE] [DATE]..." o "...people in [AFFECTED_AREA]"). Questo isola l'attenzione semantica strettamente sulle metriche di impatto, sulle cause dei conflitti e sulle condizioni di insicurezza alimentare.

---

## 4. Validazione & Metriche di Esecuzione

L'efficienza e la correttezza del processo di ablazione vengono quantificate tramite le seguenti metriche di monitoraggio:
*   **Throughput di Esecuzione**: Misurazione della latenza del processo per batch. Durante l'elaborazione, le code di inferenza raggiungono tempistiche profilate di circa *12.68s/it* per partizione batch, confermando l'efficacia del disarmo dei moduli lenti di spaCy.
*   **Recall dell'Ablazione Spaziotemporale**: Verifica quantitativa per accertare che i riferimenti nativi non sfuggano ai threshold del modello GLiNER finendo nei vettori finali.
*   **Tasso di Integrità Strutturale**: Valutazione post-sostituzione per garantire che l'iniezione dei tag (`[AFFECTED_AREA]`, `[DATE]`) non generi interruzioni sintattiche che possano compromettere i tokenizer a valle.
