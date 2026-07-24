# Progetto HERO: Pipeline Integrata di NLP e Semantic Clustering per Report IPC

Questo documento offre una panoramica unificata dell'intera pipeline di Natural Language Processing (NLP) sviluppata per il progetto **HERO (Hunger Early-warning & Risk Optimizer)**. 

## Obiettivo Principale
L'obiettivo della pipeline è analizzare sistematicamente i report ufficiali sull'insicurezza alimentare acuta (IPC Country Analysis) per individuare pattern e raggruppare le crisi in base ai **driver causali** (es. conflitti, siccità, crisi economiche, pandemie), depurando i dati dal bias geografico e temporale. L'elaborazione coinvolge circa 497 documenti originari (periodo 2011-2026).

---

## FASE 1: Data Collection & Web Scraping
La raccolta dei dati è stata automatizzata tramite una pipeline divisa in due script principali:

1.  **Raccolta URL (`fase1_raccolta_url.py`)**: Sfruttando `undetected_chromedriver` per eludere le protezioni anti-bot, lo script naviga su *ipcinfo.org*. Itera su tutti i 45 paesi disponibili e gli anni dal 2011 al 2026, estraendo i link ai report di Acute Food Insecurity.
2.  **Download (`fase2_download.py`)**: I 502 link estratti vengono visitati per scaricare sia i testi grezzi della sezione "Key Results", sia i documenti PDF (distinguendo tra report completi e snapshot). Sono stati implementati meccanismi anti-ban come il riavvio periodico del browser.

**Risultati della Fase 1**: 
*   36 nazioni coperte (con Somalia, Honduras e Sud Sudan in testa).
*   501 testi estratti con successo (tasso di successo del 99.8%).

---

## FASE 2: Anonimizzazione e Ablazione Spaziotemporale
Per raggruppare i testi in base ai fattori di crisi e non alla semplice menzione di un Paese o di un anno, è stata applicata una rigorosa ablazione spaziotemporale. Sono state esplorate due vie:

1.  **Esperimenti LLM (Llama 3 e Qwen)**: Sono stati testati modelli quantizzati locali (`Llama-3.2-3B`, `Llama-3.1-8B`, `Qwen2.5-32B`) con prompt Zero-Shot e Few-Shot. I modelli piccoli hanno mostrato allucinazioni sui dati numerici e scarsa ablazione geografica. Qwen 32B ha fornito un'ablazione eccellente, ma tendeva ad essere "troppo discorsivo", introducendo allucinazioni semantiche sui driver causali non presenti nel testo originale.
2.  **Pipeline NLP NER (La scelta finale)**: Per ovviare ai limiti dei LLM, è stata costruita un'architettura basata su **GLiNER** (`gliner_large-v2`) per il riconoscimento Zero-shot delle entità e **spaCy** per la segmentazione in frasi (Sentencizer). 
    *   *Metodo*: Le entità geografiche sono state rimpiazzate con il tag `[AFFECTED_AREA]` e quelle temporali con `[DATE]`. La sostituzione è avvenuta tramite *Backwards Replacement* per non alterare gli indici testuali.
    *   *Risultati*: Throughput rapido (12.68s/batch) e preservazione assoluta dell'integrità strutturale e fattuale dei testi.

---

## FASE 3: Estrazione Feature e Analisi Statistica (NLP)
Sui testi anonimizzati è stata condotta un'analisi per estrarre le feature semantiche:
*   **Pulizia e POS Tagging**: Rimozione dei tag segnaposto, applicazione di un dizionario di stopwords custom (terminologia IPC burocratica come *phase*, *percent*, *million*) e mantenimento di soli Sostantivi (NOUN) e Aggettivi (ADJ) tramite spaCy.
*   **Risultati Quantitativi**: Estrazione di top Unigrammi (es. *food*, *people*, *insecurity*) e Bigrammi (es. *food insecurity*, *acute food*). L'analisi delle frequenze ha confermato la validità della Legge di Zipf all'interno del sottodominio semantico, con pochi macro-concetti che dominano la narrativa.

---

## FASE 4: Vettorizzazione (Embedding) e Riduzione Dimensionale
Per calcolare la similarità semantica, i testi sono stati trasformati in vettori densi:
*   **Testi Originali vs Anonimizzati**: È stato provato che l'uso dei testi anonimizzati riduce drasticamente il bias geografico.
*   **Confronto Modelli**: Valutazione tra `nomic-ai/nomic-embed-text-v1.5` e `BAAI/bge-m3`. La scelta finale è ricaduta su **BGE-M3**, capace di gestire contesti ampi (fino a 8192 token) e generare vettori a 1024 dimensioni altamente allineati semanticamente.
*   **UMAP**: I vettori sono stati compressi a 5 dimensioni per l'ottimizzazione del clustering e a 2 dimensioni per la rappresentazione grafica (scatter plot).

---

## FASE 5: Clustering Non Supervisionato
Sono stati testati due algoritmi sui vettori 5D:
1.  **K-Means**: Utilizzando metriche come Inerzia, Silhouette Score e Davies-Bouldin Index, è stato individuato un numero ottimale di cluster ($K$ iniziale = 7).
2.  **HDBSCAN**: Questo approccio basato sulla densità ha permesso di identificare i cluster ignorando i documenti ambigui classificati come rumore (outlier).

---

## FASE 6: Topic Modeling e Validazione tramite LLM (Gemini)
L'identificazione e la validazione dei topic dei cluster è il cuore analitico della pipeline:
1.  **C-TF-IDF**: Utilizzato per estrarre le parole chiave causali specifiche per ogni cluster (es. *conflict, refugee* per guerre; *price, season, crop* per shock agricoli).
2.  **Etichettatura tramite Gemini**: Le top-10 parole frequenti di ogni cluster sono state fornite a un modello LLM (Gemini) per generare un'etichetta semantica descrittiva e sintetica.
3.  **LLM-as-a-Judge (Validazione Manifesto)**: Per ogni cluster, sono stati estratti i 5 "Report Manifesto" (i testi più vicini al centroide). Questi testi originali sono stati valutati da Gemini per verificare oggettivamente la coerenza narrativa con l'etichetta semantica assegnata, prevenendo artefatti algoritmici.
4.  **Verifica del Bias Geografico**: È stata calcolata la Tabella di Contingenza e l'Entropia Geografica per ogni cluster. Valori alti di entropia hanno confermato che i cluster aggregano nazioni diverse accomunate dagli stessi problemi (es. siccità), dimostrando il successo della fase di anonimizzazione.
