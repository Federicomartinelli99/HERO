#  HERO: Hunger Early-warning & Risk Optimizer & Overview del Progetto
> **Un'architettura Big Data per la scomposizione analitica delle crisi umanitarie:** Mappare i driver socio-economici e climatici attraverso l'integrazione di flussi informativi globali. 
**HERO (Hunger Event Reconstruction & Oversight)** è un framework analitico basato su Big Data e Machine Learning volto a decostruire, mappare e prevedere le crisi alimentari globali. L'obiettivo core è superare il ritardo temporale dei report ufficiali tradizionali integrando flussi di dati eterogenei in tempo reale (news, conflitti, meteo, macroeconomia) per generare indicatori di *Early-Warning* ad alta tempestività.

---

##  Indice dei Contenuti
1. [Il Problema e la Sfida Globale](#1-il-problema-e-la-sfida-globale)
2. [Research Questions](#2-research-questions)
3. [Target Audience & Stakeholders](#3-target-audience--stakeholders)
4. [Data Architecture & Fonti Dati](#4-data-architecture--fonti-dati)
5. [Analisi della Letteratura (State of the Art)](#5-analisi-della-letteratura-state-of-the-art)
6. [Mappatura delle Competenze (Corsi Coinvolti)](#6-mappatura-delle-competenze-corsi-coinvolti)
7. [Metodi e Pipeline di Data Engineering & ML](#7-metodi-e-pipeline-di-data-engineering--ml)
8. [Risultati Attesi & Data Visualization](#8-risultati-attesi--data-visualization)
9. [Risk Management & Contromisure](#9-risk-management--contromisure)
10. [Roadmap di Progetto](#10-roadmap-di-progetto)

---

## 1. Il Problema e la Sfida Globale
Nel 2015, le Nazioni Unite hanno adottato gli **Obiettivi di Sviluppo Sostenibile (SDGs)**, ponendo il traguardo *Fame Zero entro il 2030*. Tuttavia, lo scenario geopolitico e climatico attuale evidenzia che il mondo non è sulla traiettoria corretta:
* **Emergenze Croniche ed Acute:** Più di *300 milioni di persone* versano oggi in condizioni di insicurezza alimentare acuta (es. crisi recenti e profonde a Gaza e in Sudan).
* **Multidimensionalità del Fenomeno:** La carenza di cibo non è una mera questione di scarsità agricola, bensì il risultato combinato e sinergico di **conflitti armati**, **shock climatici** ed **instabilità economica**.

HERO si propone di documentare la presenza di pattern ricorrenti tra diversi contesti geografici, caratterizzando analiticamente le dinamiche associate alle fasi di escalation rapida (livelli **IPC 3 - Crisi** o superiori).

---

## 2. Research Questions
Il progetto intende fornire risposte quantitative e basate sui dati ai seguenti quesiti:
1.  **Sentiment & Media:** Esiste una correlazione quantificabile tra il sentiment dei media locali/internazionali (GDELT) ed il manifestarsi macroscopico di una crisi alimentare?
2.  **Trigger Identification:** Quali sono i "fattori scatenanti" (*trigger*) con il maggior peso predittivo e come variano in base alle diverse aree geografiche?
3.  **Early-Warning Window:** Con quanto anticipo temporale è possibile prevedere il passaggio di una regione alla fase di "Crisi" o "Emergenza" secondo la scala standard IPC?
4.  **Dinamiche Migratorie:** In che modo i flussi migratori (sia immigrazione che emigrazione) sono legati a doppio filo con l'aggravarsi delle crisi alimentari?
5.  **Climate Change:** In quale misura e con quali pattern specifici il cambiamento climatico ha impattato sull'intensità delle crisi alimentari storiche e correnti?

---

## 3. Target Audience & Stakeholders
La piattaforma e i report generati da HERO sono strutturati per rispondere alle esigenze di:
* **Decision-Maker & Ong Internazionali:** Enti come *World Food Program (WFP)*, *Medici Senza Frontiere (MSF)* ed *Oxfam*, per l'allocazione predittiva e tempestiva delle risorse umanitarie.
* **Agenzie Governative:** Per lo sviluppo di policy di resilienza locale.
* **Divulgazione Scientifico-Tecnica:** Riviste di settore ed editoriali generalisti ad alto impatto (es. *Focus*) per sensibilizzare l'opinione pubblica tramite storytelling guidato dai dati.

---
## 4. Data Architecture & Fonti Dati
La pipeline integra flussi informativi globali attraverso chiavi di join spaziali (`ISO-Country`/Regione) e temporali:

| Fonte | Tipologia di Dato | Frequenza | Ruolo nel Modello / API |
| :--- | :--- | :--- | :--- |
| **IPC (Integrated Food Security Phase Classification)** | Target Variabile | Trimestrale | Ground Truth (API HDX) |
| **ACLED** | Conflitti e disordini civili | Puntuale / Giornaliero | Proxy di instabilità geopolitica (API) |
| **WFP & World Bank** | Prezzi beni prima necessità | Storico / Mensile | Indice di shock economico (API) |
| **GDELT Project** | Web scraping & Global News | Real-time | Sentiment Analysis & Media Volatility |
| **CHIRPS** | Dati satellitari precipitazioni | Giornaliero / Decadale | Monitoraggio siccità e anomalie climatiche |
| **NDVI (Normalized Difference Veg. Index)** | Indice di vigore della vegetazione | Decadale / Mensile | Monitoraggio salute delle colture e shock agricoli |
| **UNHCR & IOM** | Flussi rifugiati e sfollati | Periodico | Dinamiche di mobilità umana |

---

## 5. Analisi della Letteratura
Il posizionamento metodologico di HERO si basa sull'analisi critica dei principali paper scientifici del settore:

1. *“Predicting food crises using news streams”*
   *  **Punti di forza:** Uso innovativo ed pionieristico di dati testuali non strutturati.
   *  **Debolezza:** Elevata difficoltà nel filtrare il "rumore" mediatico irrilevante. HERO interviene introducendo filtri granulari sui codici evento (CAMEO).
2. *“Predicting food-security crises in the Horn of Africa using ML”*
   *  **Punti di forza:** Altissima precisione e accuratezza su scala locale.
   *  **Debolezza:** Scarsa generalizzabilità a contesti non africani. HERO mitiga questo aspetto tramite clustering cross-country.
3. *“Forecasting trends in food security with real-time data”*
   *  **Punti di forza:** Forte focus sulla tempestività e l'early-warning operativo.
   *  **Debolezza:** Tende a trascurare l'impatto dei conflitti armati diretti sul territorio. HERO integra i dati ACLED per coprire questo gap.
4. *“A data-driven approach improves food insecurity crisis prediction”*
   *  **Punti di forza:** Estrema robustezza statistica dei modelli proposti.
   *  **Debolezza:** Dataset statici e non aggiornati in tempo reale. HERO risolve implementando pipeline di ingestion automatizzate.

---

## 6. Mappatura delle Competenze (Corsi Coinvolti)
Il progetto è nativamente multidisciplinare e declina le competenze dei seguenti insegnamenti:
*  **Data Crawling:** Estrazione automatizzata da HDX e orchestrazione dei flussi GDELT.
*  **Text Analytics:** Sentiment analysis e Topic Modeling sulle notizie mondiali per estrarre vettori semantici di crisi.
*  **Time Series Analysis:** Modellazione della stagionalità dei raccolti, trend dei prezzi e anomalie climatiche.
*  **Data Mining & ML/DL:** Sviluppo di modelli descrittivi e predittivi (confronto tra *XGBoost*, *Random Forest* e *Transformers per serie storiche*).
*  **Information Retrieval:** Indicizzazione ed efficientamento delle query sul database di news su larga scala.
*  **Decision Support:** Sintesi analitica e visualizzazione geospaziale interattiva (Dashboard su *QGIS/PowerBI*).

---

## 7. Metodi e Pipeline di Data Engineering & ML
```
*  [Ingestion (API/Scraping)] 
*  [Preprocessing & Harmonization] 
*  [Feature Engineering]
*  [Modeling & Evaluation]
```


## 8. Risultati Attesi & Data Visualization
Il framework restituirà risposte strutturate su:
* Temi mediatici ricorrenti nelle fasi di escalation verso l'IPC 3+.
* Variazioni delle relazioni tra indicatori economici (prezzi) e narrativi (news) al variare dei livelli IPC.
* Pattern spaziali e temporali preannuncianti situazioni di elevato rischio umanitario.

###  Concept della Visualizzazione (Dashboard Interattiva)
L'output finale prevede una **Dashboard Comparativa** contenente la *"Timeline della Crisi"*:
* Sovrapposizione grafica di serie storiche continue (andamento prezzi dei beni e volumi/sentiment delle notizie).
* Aree di sfondo colorate dinamicamente in base ai livelli discreti della scala IPC (*Ground Truth*).
* *Value Proposition:* Visualizzazione immediata della ricorrenza dei pattern e del tempo di anticipo dei trigger rispetto alla validazione ufficiale.

---

## 9. Risk Management & Contromisure

| Rischio Identificato | Impatto | Contromisura Strategica |
| :--- | :--- | :--- |
| **Disomogeneità dei dati IPC** |  Alto | Focalizzare e circoscrivere l'analisi su un sottoinsieme di paesi target aventi serie storiche IPC storicamente complete, consistenti e stabili. |
| **Rumore nei dati GDELT** |  Medio | Applicare filtri stringenti basati su codici evento standardizzati (**CAMEO**) e calcolare medie mobili pesate per abbattere le fluttuazioni giornaliere irrilevanti. |
| **Eterogeneità dei paesi** |  Medio | Raggruppare i paesi target in cluster omogenei (es. per area geografica o livello di dipendenza dalle importazioni alimentari) per rendere i pattern confrontabili. |
