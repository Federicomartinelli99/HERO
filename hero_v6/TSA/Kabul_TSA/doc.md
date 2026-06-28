# Documentazione Analisi Time Series Avanzata: Kabul (AF01)

Questa directory contiene l'analisi avanzata a due stadi per la previsione dell'insicurezza alimentare (IPC Phase 3+ %) nella provincia di **Kabul, Afghanistan**, gestendo l'allineamento di frequenze temporali eterogenee.

## Frequenze Temporali dei Dati Grezzi (Raw)
I dati di input per Kabul provengono da fonti con frequenze e granularità originarie molto diverse:
1. **Prezzi Alimentari (WFP)**: Mensile nativa (uno stato di mercato consolidato per mese).
2. **Precipitazioni (Rainfall)**: Mensile nativa (rilevazioni geospaziali mensili).
3. **Conflitto (ACLED)**: Basato su eventi (giornaliero). Viene aggregato mensilmente sommando il numero totale di eventi e vittime.
4. **Sfollamento (IDP)**: Rilevazioni sporadiche basate su round di assessment (generalmente trimestrali o semestrali).
5. **Insicurezza Alimentare (IPC)**: Multi-mensile (generalmente periodi di validità di 3-6 mesi).

## Allineamento e Resampling
Per effettuare studi di serie storiche coerenti ed evitare perdita di informazione, tutti i termini sono stati allineati a una **frequenza mensile coerente** (Month Start - `MS`):
* **ACLED**: Raggruppamento mensile (`groupby('date').sum()`).
* **Rainfall**: Raggruppamento mensile (`groupby('date').mean()`).
* **IDP**: Raggruppamento mensile con propagazione in avanti per i mesi senza nuove misurazioni (`ffill()`).
* **IPC**: Espansione del valore di `phase_3plus_percentage` per coprire ciascun mese all'interno dell'intervallo `From` $\rightarrow$ `To` del rispettivo record di validità `current`, seguito da forward-fill (`ffill()`).

Il dataset mensile finale così unificato per Kabul comprende **93 mesi consecutivi** (da Agosto 2017 a Maggio 2025).

## Pipeline di Previsione a Due Stadi (Two-Stage Forecasting)
Per fare proiezioni dell'IPC nel futuro (12 mesi in avanti: da Giugno 2025 a Maggio 2026), abbiamo strutturato una pipeline predittiva in due fasi:

### Stadio 1: Previsione Univariata dei Predictor
Ciascuna delle 9 serie storiche dei predittori (prezzi, inflazione, precipitazioni, anomalie meteo, conflitti ed IDP) viene proiettata in avanti di 12 mesi in modo indipendente:
* I modelli utilizzati sono **Holt-Winters Exponential Smoothing** (per catturare stagionalità e trend lineare) e **SARIMAX** come fallback per serie irregolari (es. conflitti).
* I grafici per ciascun predittore sono salvati in `plots/univariate_{col}.png`.

### Stadio 2: Proiezione Multivariata dell'IPC
* Viene addestrato un modello **Random Forest Regressor** per mappare la relazione non lineare tra i 9 predittori mensili e la percentuale IPC.
* Per il futuro (i 12 mesi di forecast), inseriamo le feature *forecastate* dallo Stadio 1 all'interno del modello Random Forest per proiettare la percentuale di IPC Phase 3+ futura.

Il grafico finale che mostra la serie storica reale, il fit del modello e la proiezione futura a 12 mesi è salvato in [kabul_multivariate_ipc_forecast.png](file:///c:/Dev/Progetti/HERO/hero_v6/TSA/Kabul_TSA/plots/kabul_multivariate_ipc_forecast.png).
