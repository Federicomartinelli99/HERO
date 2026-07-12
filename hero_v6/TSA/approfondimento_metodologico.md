# Approfondimento Metodologico: Tecniche di Serie Temporali per HERO

Questo documento approfondisce le scelte metodologiche alla base della pipeline di Time Series Analysis (TSA) sviluppata per il progetto HERO, analizzando le opzioni di ottimizzazione computazionale, l'aggregazione a livello nazionale e la visualizzazione spaziale delle anomalie per l'**Afghanistan (Stato Pilota)**.

---

## 1. Analisi dei Colli di Bottiglia Computazionali e Semplificazioni

L'esecuzione della pipeline diagnostica avanzata su tutte le 34 province dell'Afghanistan e le 18 del Sudan richiede diverse risorse. Di seguito analizziamo i componenti più pesanti e proponiamo strategie di semplificazione:

### A. Modellazione con Meta Prophet
* **Perché è pesante**: Prophet utilizza un motore probabilistico scritto in C++ (PyStan). Per ogni fit, esegue un ciclo di ottimizzazione numerica per stimare i parametri del trend flessibile (changepoints) e dei coefficienti di Fourier per la stagionalità. Questo richiede circa $1 \sim 2$ secondi per serie. Moltiplicato per 10 variabili e 34 province, l'overhead diventa notevole.
* **Proposta di Semplificazione**: Disattivare Prophet a livello di singola provincia per le serie esogene dello Stage 1. Utilizzare Prophet **solo per prevedere l'indice IPC Target** (Stage 2) o **limitare il suo utilizzo alla serie storica aggregata nazionale**. I predittori esogeni (prezzi, piogge, IDP) possono essere previsti molto più velocemente tramite Holt-Winters lineare o SARIMAX.

### B. Matrix Profile (Motif & Discord Discovery)
* **Perché è pesante**: Il Matrix Profile calcola la distanza Euclidean z-normalizzata tra tutte le possibili coppie di sottosequenze di lunghezza $m=12$. Anche se ottimizzato in numpy, l'algoritmo brute-force ha una complessità di $O(N^2)$ per serie. Eseguirlo per tutte le 10 variabili in tutte le province (340 serie in totale) introduce un calcolo ridondante.
* **Proposta di Semplificazione**: Calcolare il Matrix Profile **esclusivamente sulla variabile target IPC** (e opzionalmente su WFP Food Prices). Variabili come le precipitazioni (`rain_1m`) hanno una stagionalità quasi deterministica ed estremamente regolare; applicare il Matrix Profile su di esse fornisce scarso valore analitico rispetto a una semplice analisi dei residui STL o a una rolling standard deviation.

---

## 2. Analisi a Livello di Intera Nazione (Aggregato Nazionale)

L'aggregazione delle serie storiche provinciali a livello nazionale consente di ridurre il rumore locale e isolare i macro-trend del paese.

### A. Strategia di Aggregazione dei Dati (Suddivisione per Variabile)
Per creare una serie storica nazionale coerente da Agosto 2017 a Maggio 2025:
1. **Prezzi Alimentari (WFP Prices & Inflation)**: Calcoliamo la media mensile (semplice o ponderata sul numero di mercati attivi per provincia).
2. **Precipitazioni (Rainfall & Anomalies)**: Media spaziale delle precipitazioni mensili sull'intero territorio nazionale.
3. **Conflitti (ACLED Events & Fatalities)**: Somma mensile cumulativa di tutti gli eventi di violenza politica e delle vittime registrate in tutto l'Afghanistan.
4. **Sfollamento (IDP Population)**: Somma mensile cumulativa della popolazione sfollata interna attiva in tutte le province.
5. **Insicurezza Alimentare (IPC Phase 3+ %)**: Media ponderata basata sulla popolazione stimata di ciascuna provincia, per riflettere il reale impatto demografico della crisi alimentare a livello paese.

### B. Vantaggi dell'Analisi Nazionale
* **Segnale più pulito**: I modelli multivariati complessi come **VAR (Vector AutoRegressive)** e **Prophet** beneficiano di dati aggregati poiché gli shock locali (es. uno scontro ACLED in una singola provincia o un mercato WFP temporaneamente chiuso) vengono smorzati, evidenziando le dinamiche macroeconomiche e geopolitiche nazionali.
* **Causalità di Granger Globale**: Permette di testare se, a livello macroscopico, le anomalie meteo a livello paese causino variazioni nei prezzi agricoli nazionali con un determinato ritardo (lag), e se questo a sua volta provochi picchi nell'IPC nazionale.

---

## 3. Mappatura e Allineamento Temporale delle Anomalie (Shock Sistemici)

L'idea di graficare tutte le anomalie di tutte le province in una visualizzazione unificata è eccellente e di alto valore analitico.

### A. Metodologia: "Spazio Temporale delle Anomalie"
Possiamo identificare e confrontare gli shock locali e sistemici costruendo una **Heatmap Temporale degli Shock**:
1. **Estrazione dell'Anomalia**: Per ogni provincia e per ogni variabile (es. IPC, Prezzi, Conflitti), estraiamo la serie storica dei residui STL (che rappresentano la componente non spiegata dal trend o dalla stagionalità regolare) oppure i valori del Matrix Profile.
2. **Standardizzazione**: Normalizziamo i residui tramite Z-score per renderli confrontabili tra province diverse.
3. **Soglia di Shock**: Definiamo un valore critico (es. $Z > 2.0$, ovvero oltre 2 deviazioni standard dal comportamento normale).
4. **Visualizzazione**:
   * **Asse X**: Tempo (mesi, da Agosto 2017 a Maggio 2025).
   * **Asse Y**: Province dell'Afghanistan (34 righe).
   * **Colore (Heatmap)**: Intensità dello shock.
   * **Marker (Scatter)**: Un pallino rosso la cui dimensione è proporzionale all'intensità dell'anomalia.

### B. Interpretazione Analitica: Shock Sistemici vs. Shock Locali
* **Allineamento Verticale (Shock Sistemico)**: Se in un determinato mese (es. Agosto 2021, coincidente con la transizione politica in Afghanistan) osserviamo una linea verticale di anomalie (prezzi alle stelle e picchi di conflitto) che attraversa quasi tutte le 34 province, abbiamo la prova visiva e statistica di uno **shock sistemico nazionale**.
* **Shock Isolati (Shock Locali)**: Anomalie che compaiono solo in 1 o 2 righe (es. un picco isolato nella provincia di Hilmand) indicano shock circoscritti (alluvioni locali, battaglie isolate) che non hanno avuto un effetto di spillover sul resto del paese.

---

## 4. Teoria e Razionale delle Tecniche Utilizzate

### STL Decomposition (Seasonal-Trend using LOESS)
* **Perché**: A differenza dei metodi classici basati su medie mobili (che soffrono in prossimità dei bordi della serie e sono molto sensibili agli outlier), la STL utilizza regressioni locali ponderate (LOESS). Questo permette di stimare in modo robusto il trend anche in presenza di forti shock temporanei e consente alla componente stagionale di variare lentamente nel tempo, simulando il reale cambiamento climatico o i mutamenti strutturali dei mercati.

### Test ADF (Augmented Dickey-Fuller) e Differenziazione
* **Perché**: I modelli statistici lineari come ARIMA/SARIMAX assumono che la serie sia stazionaria (media e varianza costanti nel tempo). L'applicazione di modelli a dati non stazionari genera regressioni spurie. L'automazione della differenziazione ($d=1, 2$) garantisce che la pipeline stazioni la serie in modo adattivo prima di passarla ai correlogrammi e ai previsori.

### Granger Causality & VAR
* **Perché**: Molti modelli assumono relazioni unidirezionali ($X \rightarrow Y$). In contesti fragili, le relazioni sono spesso bidirezionali (i conflitti distruggono i raccolti aumentando i prezzi, ma l'aumento dei prezzi esaspera le tensioni aumentando i conflitti). Il modello VAR tratta tutte le variabili come endogene, consentendo di misurare questi cicli di feedback e quantificare gli effetti di spillover nel tempo.

### DTW (Dynamic Time Warping)
* **Perché**: La distanza euclidea classica confronta i punti esattamente allo stesso istante temporale ($t_i$ con $t_i$). Se una provincia reagisce a uno shock meteo con 2 mesi di ritardo rispetto ad un'altra, la distanza euclidea risulterà enorme. Il DTW trova l'allineamento ottimale "piegando" l'asse temporale, identificando province che mostrano la stessa risposta dinamica ma sfasata nel tempo.
