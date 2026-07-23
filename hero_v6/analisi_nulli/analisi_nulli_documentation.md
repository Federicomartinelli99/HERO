# Report di Analisi Diagnostica: Spazio, Tempo e Struttura dei Dati Mancanti

---

## 1. Obiettivi
Effettuare un'analisi spazio-temporale dei valori nulli presenti nei dataset di riferimento (ACLED, NDVI, CHIRPS, IDP, IPC, WFP) per determinare l'esatta natura della *missingness* (MCAR, MAR, MNAR). L'indagine mappa le correlazioni strutturali, temporali e geografiche per separare i fallimenti stocastici da quelli sistemici, logistici o ambientali.

---

## 2. Metodologia
L'architettura diagnostica implementata nello script `analisi_nulli` converte l'assenza del dato in informazione vettoriale disaccoppiando l'esplorazione topologica dall'inferenza statistica[cite: 3].

### 2.1. Shadow Matrix
I pattern di missingness vengono isolati generando una matrice booleana derivata dal dataframe originale[cite: 3]. La trasformazione applicata è:
$$S_{i,j} = \begin{cases} 1 & \text{se } X_{i,j} \text{ è NaN} \\ 0 & \text{altrimenti} \end{cases}$$
Questo converte i valori nulli in variabili binarie, abilitando il calcolo diretto delle correlazioni[cite: 3].

### 2.2. Regressione Logistica Multivariata
La dipendenza dell'assenza di una metrica dall'intero spazio informativo (test MCAR vs MAR/MNAR) viene misurata tramite un classificatore a Regressione Logistica[cite: 3]. Il modello calcola la probabilità che il target sia mancante ($S_{target} = 1$) dati i regressori osservati[cite: 3]:
$$P(S_{target}=1 | X) = \frac{1}{1 + e^{-(\beta_0 + \beta_1 X_1 + \dots + \beta_n X_n)}}$$
Le performance vengono misurate con la metrica ROC AUC[cite: 3]. Un valore $\text{AUC} > 0.6$ sancisce la prevedibilità strutturale dell'assenza, rigettando matematicamente l'ipotesi di casualità pura (MCAR)[cite: 3].

### 2.3. Welch's T-Test (Verifica Univariata)
Il test di Welch valuta la significatività statistica della differenza tra le medie di una singola feature $X$ partizionata in base all'assenza/presenza del target[cite: 3]:
$$t = \frac{\bar{X}_1 - \bar{X}_2}{\sqrt{\frac{s_1^2}{N_1} + \frac{s_2^2}{N_2}}}$$
Questa formulazione è matematicamente robusta in presenza di varianze ($s_1^2 \neq s_2^2$) e numerosità campionarie eterogenee ($N_1 \neq N_2$)[cite: 3]. Un p-value $< 0.05$ certifica la dipendenza univariata (MAR)[cite: 3].

### 2.4. Aggregazioni Topologiche
La *Shadow Matrix* viene esplorata su tre dimensioni[cite: 3]:
*   **Strutturale:** Calcolo dei coefficienti di correlazione di Pearson tra i vettori binari[cite: 3].
*   **Temporale:** Raggruppamento per `year_month` con calcolo delle medie mensili, renderizzate dinamicamente tramite `ipywidgets`[cite: 3].
*   **Geografica:** Raggruppamento per nazione (`Country`) con calcolo dell'intensità del deficit[cite: 3].

---

## 3. Risultati e Diagnosi
I risultati confutano totalmente l'ipotesi MCAR. L'infrastruttura dei dati è affetta da missingness deterministica (MAR/MNAR).

### 3.1. Inferenza Statistica: Collasso dell'MCAR
Il modello predittivo e i T-Test evidenziano dipendenze estreme:
*   **WFP Price:** $\text{AUC} = 0.859$. I blackout del mercato sono deterministicamente prevedibili. I test univariati mostrano scostamenti massivi (IPC: $p < 3.31e-262$; CHIRPS: $p < 1.55e-38$; NDVI: $p < 4.18e-58$).
*   **GDELT:** $\text{AUC} = 0.763$. Il fallimento dell'estrazione altera significativamente la distribuzione di ACLED ($p < 7.83e-42$) e IPC ($p < 7.12e-71$).
*   **IDP:** $\text{AUC} = 0.725$. L'impossibilità di tracciare sfollati è correlata ad anomalie satellitari (CHIRPS: $p < 3.77e-20$) e di insicurezza alimentare (IPC: $p = 0.0$).
*   **ACLED:** $\text{AUC} = 0.615$. Assenza non stocastica con distorsioni sistemiche nei valori WFP, IDP e NDVI misurati.

### 3.2. Topologia Strutturale (Heatmap Correlazioni)
L'infrastruttura collassa in blocchi funzionali isolati:
*   **Sensori Ambientali:** Correlazione di **0.92** tra `missing_NDVI` e `missing_CHIRPS`. Il fallimento del monitoraggio ottico vegetazionale è accompagnato dal blackout della misurazione pluviometrica.
*   **Sensori Socio-Politici:** Correlazioni critiche tra ACLED e WFP (**0.65**) e tra ACLED e IDP (**0.60**). Quando viene perso il tracciamento dei conflitti armati, cadono contemporaneamente i reportistica dei mercati e degli sfollati interni.

### 3.3. Dinamiche Temporali (Time Series)
I vettori ombra nel tempo certificano origini differenti per la missingness:
*   **Pattern Ambientale Ciclico (MAR):** NDVI e CHIRPS mostrano blackout periodici e sovrapposti (tassi di missingness generalmente $< 0.4$), imputabili a barriere ottiche/meteorologiche costanti nel tempo.
*   **Collasso Istituzionale Sincrono (MNAR/MAR):** Le serie di ACLED, WFP e IDP registrano crolli infrastrutturali improvvisi, prolungati e simultanei (picchi a 1.0). L'assenza di regolarità esclude il disturbo naturale e indica falle catastrofiche nella supply chain dei dati istituzionali.

### 3.4. Frammentazione Geografica
La distribuzione spaziale rivela falle non gestibili tramite semplice imputazione:
*   **Isolamento ACLED:** Un tasso di fallimento sistemico pari a 1.0 oblitera 17 nazioni su 18. Il dato sopravvive solo in CAF (Repubblica Centrafricana) e parzialmente in KEN. Questa è un'assenza puramente **MNAR** dettata da barriere geopolitiche.
*   **Blackout IDP:** Dinamica analoga per gli sfollati interni, assenti deterministicamente in ampi cluster del dataset (es. SLV, GTM, ZWE).
