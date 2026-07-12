# Piano di Implementazione: Time Series Analysis (TSA) Pipeline

Questo documento descrive la strategia metodologica e l'architettura software per l'analisi avanzata delle serie storiche, partendo dal caso studio di **Kabul (AF01)** per poi generalizzare ad altre province e nazioni del dataset HERO.

---

## 1. Architettura della Pipeline (Struttura del Codice)

Per garantire pulizia, modularità e manutenibilità, organizzeremo il codice all'interno della cartella `TSA` in modo strutturato:

```
TSA/
│
├── config.py                 # Parametri globali (split train/test, orizzonti temporali, pcode target)
├── data_loader.py            # Caricamento e allineamento dati (resampling mensile uniforme MS)
├── monitor.py                # Calcolo del Reliability Index per ciascuna serie storica e provincia
│
├── preprocessing/
│   ├── __init__.py
│   ├── stationarity.py       # Test di Dickey-Fuller (ADF), decomposizione STL, differenziazione/log
│   └── imputation.py         # Imputazione di base (linear interp, ffill) e Backcasting
│
├── models/
│   ├── __init__.py
│   ├── baselines.py          # Naive, Average, Drift models
│   ├── statistical.py        # ARIMA, SARIMAX, Holt-Winters
│   ├── ml_regressors.py      # Random Forest, XGBoost, Ridge
│   └── prophet_model.py      # Integrazione modulare con Meta Prophet
│
├── similarity/
│   ├── __init__.py
│   ├── distances.py          # Calcolo delle distanze: Euclidean, MAE, DTW (Sakoe-Chiba)
│   └── representation.py     # Approssimazione delle forme: PAA (Piecewise Aggregate) e SAX
│
└── pipeline.py               # Orchestratore principale (Stage 1 & Stage 2)
```

---

## 2. Metodologia: Analisi Esaustiva su Kabul

L'analisi su Kabul fungerà da prototipo e coprirà le seguenti fasi:

### A. Monitoraggio Dati Mancanti & Reliability Index (Attendibilità)
Per quantificare la qualità e la completezza delle serie storiche prima del modellamento, definiamo un **Reliability Index ($S_{rel}$)** compreso tra 0 e 100 per ciascuna variabile $v$ e provincia:

$$S_{rel}(v) = 100 \times \left(1 - w_1 \cdot r_{missing} - w_2 \cdot \frac{g_{max}}{N} - w_3 \cdot r_{recent}\right)$$

Dove:
* $r_{missing}$: Percentuale totale di dati mancanti nella serie originaria.
* $g_{max}$: Lunghezza del segmento consecutivo vuoto più lungo (i gap lunghi sono difficili da imputare).
* $r_{recent}$: Percentuale di dati mancanti negli ultimi $K$ mesi (cruciale per il forecasting).
* $N$: Lunghezza totale della serie.
* $w_1, w_2, w_3$: Pesi configurabili (es. $w_1=0.4, w_2=0.4, w_3=0.2$).

Questo indice ci permetterà di escludere o penalizzare variabili/regioni con dati troppo frammentati.

### B. Stazionarietà e Analisi dei Pattern (Slides 01 & 03)
1. **Decomposizione STL**: Isoleremo Trend, Stagionalità e Residui (Rumore) per comprendere la struttura fondamentale di ogni feature di Kabul.
2. **ADF Test (Dickey-Fuller)**: Verificheremo formalmente la stazionarietà della serie. Se non stazionaria, applicheremo differenziazioni successive ($d=1, 2$) o trasformazioni logaritmiche per stabilizzare la varianza.
3. **Analisi ACF/PACF**: Definiremo i correlogrammi per individuare i parametri autoregressivi ($p$) e a media mobile ($q$) per i modelli SARIMAX.
4. **Motif Discovery (Matrix Profile)**: Calcoleremo il Matrix Profile sulle serie storiche principali (es. prezzi alimentari WFP e anomalie meteorologiche) per individuare pattern ripetitivi (motifs) di lunghezza $m$ e anomalie temporali (discords).

### C. Imputazione tramite Backcasting ("Forecasting into the Past")
Per gestire dati storici mancanti (es. round sporadici di IDP o mercati WFP non rilevati nei primi anni):
1. **Definizione**: Dato il vettore temporale $Y = [y_1, y_2, \dots, y_T]$, invertiamo l'ordine cronologico delle osservazioni: $Y_{rev} = [y_T, y_{T-1}, \dots, y_1]$.
2. **Addestramento**: Addestriamo un modello autoregressivo (es. SARIMA o Exponential Smoothing) sul suffisso stabile e continuo di $Y_{rev}$.
3. **Imputazione**: Generiamo previsioni in avanti nel tempo invertito (corrispondenti a stime nel passato) per riempire i vuoti storici all'inizio della serie.
4. **Validazione Scientifica**: Valuteremo l'efficacia del backcasting mascherando artificialmente porzioni note di dati storici reali e misurando l'errore di ricostruzione (MAE/RMSE).

---

## 3. Generalizzazione & Confronto Regionale (Slides 02 & 04)

Una volta consolidata la pipeline su Kabul, estenderemo l'analisi alle altre province/regioni (es. *Awdal* in Somalia, *Rift Valley* in Kenya) implementando:

### A. Allineamento Spaziale e Distanze Elastiche
Per confrontare l'andamento temporale di diverse regioni che possono evolvere a velocità differenti o presentare sfasamenti temporali:
1. **Dynamic Time Warping (DTW)**: Calcoleremo le distanze "elastiche" tra coppie di serie storiche, limitando la ricerca del percorso ottimo con bande di vincolo globali (**Sakoe-Chiba Band** o **Itakura Parallelogram**) per velocizzare i calcoli ed evitare allineamenti patologici.
2. **Rappresentazione SAX (Symbolic Aggregate Approximation)**: Convertiremo le serie storiche numeriche in stringhe simboliche (es. `baabccbc`) basate su segmenti PAA mediati. Questo riduce la dimensionalità e consente il confronto tramite algoritmi di string matching o compressione (CDM - Compression-based Dissimilarity Measure).

### B. Clustering e Classificazione delle Regioni
1. **Clustering (K-Means/Hierarchical)**: Raggrupperemo le regioni basandoci sia su vettori di feature globali (es. media, varianza, pendenza del trend estratte con approccio stile *TSfresh*) sia direttamente sulle matrici di distanza DTW. L'obiettivo è identificare "archetipi" di vulnerabilità all'insicurezza alimentare.
2. **Subsequence Classification (Shapelets)**: Identificheremo sottosequenze temporali discriminanti (shapelets) associate a transizioni rapide verso crisi alimentari (IPC Phase 3+).

---

## 4. Validazione & Metriche di Confronto (Slides 05)

Ogni modello di previsione (baselines, Holt-Winters, SARIMAX, Random Forest, Prophet) sarà valutato e controfrontato quantitativamente sul Test Set (ultimi 12 mesi) utilizzando:
* **MAE** (Mean Absolute Error): Errore assoluto medio.
* **RMSE** (Root Mean Squared Error): Penalizza maggiormente gli errori più grandi.
* **MAPE** (Mean Absolute Percentage Error): Utile per confrontare serie storiche con scale diverse (es. popolazioni IDP vs prezzi locali).
* **R²** (Coefficiente di Determinazione): Proporzione di varianza spiegata dal modello.
