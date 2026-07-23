# Esperimenti di Anonimizzazione su Report IPC: Confronto tra Modelli LLM

## 1. Obiettivo
Il presente lavoro si pone l'obiettivo di **anonimizzare un dataset di report IPC (Integrated Food Security Phase Classification)**, rimuovendo ogni riferimento spaziale (paesi, regioni, città) e temporale (anni, mesi, date esatte), preservando al contempo l'integrità dei dati numerici e le metriche tecniche (fasi IPC, percentuali, deficit nutrizionali). 
L'anonimizzazione è un prerequisito fondamentale per eseguire un successivo clustering semantico basato *esclusivamente* sui **driver causali delle crisi alimentari** (es. clima, inflazione, conflitti), depurati dal bias geografico.

## 2. Metodologia

### 2.1 Il Dataset
Il processo è stato testato su un campione del dataset originale, composto da **35 report**. È importante notare che alcuni di questi report sono "duplicati" in termini di contenuto testuale, poiché un singolo documento originale copre l'analisi per più nazioni limitrofe (es. Honduras, Guatemala ed El Salvador). Nel dataset finale, questo stesso testo viene attributo separatamente a ciascun paese per il periodo analizzato.

### 2.2 I Modelli LLM Utilizzati
L'esperimento ha valutato l'efficacia di diversi modelli linguistici quantizzati caricati in locale tramite `llama_cpp`:
*   **Llama-3.2-3B-Instruct**
*   **Meta-Llama-3.1-8B-Instruct**
*   **Qwen2.5-32B-Instruct**

Per le versioni 8B e 32B sono state testate diverse precisioni di quantizzazione (4-bit, 6-bit, 8-bit).

### 2.3 Progettazione dei Prompt
L'approccio ha previsto l'esplorazione di due strategie di prompting:
1.  **Zero-Shot Prompting**: Il modello riceve solo regole esplicite (rimuovere nomi geografici e date, preservare metriche, formattare in 4 sezioni fisse).
2.  **In-Context Learning (Few-Shot Prompting)**: Il prompt di sistema viene alleggerito dalle regole discorsive e istruito principalmente tramite **due esempi concreti** (coppie Input/Output) che mostrano chiaramente come trasformare il testo grezzo nella struttura anonimizzata desiderata.

Tutti gli output dovevano seguire rigorosamente una struttura a paragrafi marcati:
*   `[SHOCKS AND DRIVERS]:`
*   `[CURRENT FOOD SECURITY DATA]:`
*   `[PROJECTED FOOD SECURITY DATA]:`
*   `[HUMANITARIAN IMPACTS]:`

L'output di ogni modello è stato salvato in una colonna dedicata all'interno del DataFrame Pandas (es. `Llama_3_1_8B_anonimo`, `Llama_3_1_8B_anonimo_promtp_in_context`, `Qwen_2_5_32B_Q6_K_anonimo`).

## 3. Verifica e Valutazione dei Risultati

La qualità dell'anonimizzazione è stata ispezionata confrontando l'output generato con il testo originale (`testo_originale`). I parametri di validazione sono stati:
*   **Completezza dei Driver**: Tutti i fattori di crisi presenti nell'originale dovevano figurare nel riassunto.
*   **Assenza di Allucinazioni**: Il modello non doveva introdurre cause, shock o numeri inesistenti.
*   **Ablazione Spaziotemporale**: Nessun nome proprio di luogo o data precisa doveva sopravvivere nell'output.

### 3.1 Risultati dell'Esperimento

Dai test effettuati sono emersi comportamenti molto differenti tra le architetture:

*   **Modelli "Piccoli" (Llama 3B e Llama 8B)**:
    *   Sia in modalità *Zero-Shot* che *In-Context*, i modelli hanno palesato **difficoltà nella completa anonimizzazione**. Spesso il nome di alcune regioni o municipalità specifiche non veniva rimosso. 
    *   La versione a 8B ha mostrato lievi miglioramenti rispetto al 3B nella rimozione dei toponimi, ma entrambi i modelli hanno manifestato una tendenza a generare allucinazioni sui dati (alterando leggermente i numeri o le percentuali).
*   **Modello "Grande" (Qwen 32B)**:
    *   Il modello da 32B ha dimostrato **un'eccellente capacità di ablazione**. L'anonimizzazione spaziale e temporale è risultata di gran lunga superiore, sostituendo con successo i nomi propri con descrittori contestuali generici (es. "le aree colpite").
    *   **Criticità (Allucinazioni Semantiche)**: Sebbene l'anonimizzazione fosse ottima, il modello tendeva a essere "troppo discorsivo", introducendo talvolta allucinazioni sotto forma di **driver causali non esplicitati nel testo di origine**, rendendolo inadatto per la successiva fase di embedding semantico fedele ai dati.
