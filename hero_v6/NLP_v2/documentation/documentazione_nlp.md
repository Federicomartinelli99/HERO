# Documentazione Analisi NLP: Report sull'Insicurezza Alimentare

Questo documento descrive la pipeline di Natural Language Processing (NLP) implementata nel notebook `NLP.ipynb` per l'estrazione di feature semantiche dai report umanitari precedentemente anonimizzati.

---

## 1. Obiettivo e Caricamento Dati
Il processo prende in input il dataset elaborato nella fase di ablazione spaziotemporale (`report_anonimizzati.csv`).
In fase di caricamento, la pipeline si assicura di ripulire ulteriormente il testo rimuovendo i tag segnaposto generati in precedenza (es. `[AFFECTED_AREA]`, `[DATE]`, `[REDACTED]`), lasciando un corpus testuale puro focalizzato esclusivamente sugli aspetti nutrizionali, economici e umanitari. 

L'elaborazione coinvolge 497 documenti originari. Gli anni di riferimento vengono estratti analizzando le stringhe temporali tramite espressioni regolari (regex).

---

## 2. Definizione Stopwords e Filtraggio POS
Per massimizzare il valore semantico dei token estratti, il vocabolario viene filtrato tramite una combinazione di regole:
*   **Stopwords Custom**: Oltre alle stopword standard della lingua inglese, viene definita una lista di termini legati alla burocrazia dei report o ad alta frequenza non informativa (es. `ipc`, `phase`, `million`, `percent`, `analysis`). Vengono rimossi sia i termini diretti che i loro lemmi (26 in totale).
*   **Part-of-Speech (POS) Tagging**: Attraverso il modello linguistico `en_core_web_sm` di spaCy, i testi vengono analizzati grammaticalmente. Vengono mantenuti **esclusivamente Sostantivi (NOUN) e Aggettivi (ADJ)**, scartando verbi, avverbi, congiunzioni e punteggiatura.

---

## 3. Estrazione Feature: Unigrammi e Bigrammi
L'estrazione quantitativa genera metriche di frequenza su due livelli di N-grammi, calcolando sia statistiche globali che documenti-specifiche:
1.  **Top Unigrammi Globale**: La frequenza assoluta conferma la focalizzazione del dominio. I lemmi più ricorrenti sono `food` (3145 occorrenze), `people` (1817), `population` (1504) e `insecurity` (1173).
2.  **Top Bigrammi Globale**: Analizzando le coppie di token adiacenti, emergono costrutti dominanti come `food insecurity` (1068 occorrenze), `acute food` (658) e `food security` (391).

Il testo così trasformato e lemmatizzato (`preprocessed_text`) viene salvato all'interno del DataFrame in preparazione per successive architetture di vettorizzazione (TF-IDF, T-SVD, UMAP).

---

## 4. Visualizzazione e Analisi Statistica
Le frequenze estratte sono visualizzate tramite grafici a barre orizzontali (Seaborn) e nuvole di parole (WordCloud). 
L'andamento visualizzato per le prime 50 parole evidenzia un comportamento esponenziale negativo a "coda lunga". Questo pattern rileva empiricamente la validità della **Legge di Zipf** anche all'interno del sottodominio semantico filtrato: pochissimi macro-concetti strutturano la narrativa di base del corpus, mentre la vasta maggioranza delle entità compare con frequenze marginali.
