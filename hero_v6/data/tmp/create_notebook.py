import json
import os
from pathlib import Path

def main():
    base_dir = Path("c:/Dev/Progetti/HERO/hero_v6")
    tsa_dir = base_dir / "TSA"
    tsa_dir.mkdir(parents=True, exist_ok=True)
    
    cells = []
    
    # Cell 1: Markdown Title
    cells.append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "# Time Series Analysis (TSA) & ARIMA: Afghanistan (Admin1)\n",
            "\n",
            "Questo notebook analizza l'andamento temporale dell'indice dei prezzi alimentari WFP (`wfp_price_mean`) a livello provinciale (Admin1) in Afghanistan.\n",
            "L'obiettivo è esplorare la serie storica, valutarne la stazionarietà e provare ad addestrare un modello **ARIMA/SARIMAX** per la previsione dei prezzi."
        ]
    })
    
    # Cell 2: Imports
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "import os\n",
            "import numpy as np\n",
            "import pandas as pd\n",
            "import matplotlib.pyplot as plt\n",
            "import seaborn as sns\n",
            "\n",
            "# Statistiche e Time Series\n",
            "from statsmodels.tsa.stattools import adfuller\n",
            "from statsmodels.tsa.seasonal import seasonal_decompose\n",
            "from statsmodels.graphics.tsaplots import plot_acf, plot_pacf\n",
            "from statsmodels.tsa.arima.model import ARIMA\n",
            "from statsmodels.tsa.statespace.sarimax import SARIMAX\n",
            "\n",
            "# Setup plot\n",
            "sns.set_theme(style=\"whitegrid\")\n",
            "plt.rcParams[\"figure.figsize\"] = (12, 6)\n",
            "plt.rcParams[\"axes.grid\"] = True"
        ]
    })
    
    # Cell 3: Load Data
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "# Percorso del dataset aggregato\n",
            "data_path = \"../data/tmp/wfp_monthly_adm1_index.parquet\"\n",
            "\n",
            "if not os.path.exists(data_path):\n",
            "    raise FileNotFoundError(f\"File non trovato a: {data_path}. Eseguire prima generate_aggregations.py.\")\n",
            "\n",
            "df = pd.read_parquet(data_path, engine=\"pyarrow\")\n",
            "df['date'] = pd.to_datetime(df['date'])\n",
            "\n",
            "# Filtro per l'Afghanistan\n",
            "df_afg = df[df['ISO3'] == 'AFG'].copy()\n",
            "print(f\"Numero totale di righe per AFG: {len(df_afg)}\")\n",
            "print(f\"Province disponibili in AFG: {df_afg['adm1_name'].nunique()}\")"
        ]
    })
    
    # Cell 4: Select Province
    cells.append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "### Selezione della Provincia\n",
            "Selezioniamo come esempio la provincia di **Kabul** (o un'altra a scelta) e impostiamo la data come indice della serie storica."
        ]
    })
    
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "provincia = 'Kabul'\n",
            "df_prov = df_afg[df_afg['adm1_name'] == provincia].copy()\n",
            "\n",
            "# Impostiamo la data come indice e ordiniamo temporalmente\n",
            "df_prov = df_prov.set_index('date').sort_index()\n",
            "\n",
            "# Assicuriamoci che la frequenza dell'indice sia impostata a Mensile ('MS' per inizio mese o 'ME' per fine mese)\n",
            "# I nostri dati hanno date tipo YYYY-MM-01, quindi usiamo 'MS' (Month Start)\n",
            "df_prov = df_prov.asfreq('MS')\n",
            "\n",
            "print(f\"Serie storica per {provincia} - Da: {df_prov.index.min()} A: {df_prov.index.max()}\")\n",
            "print(f\"Valori nulli in wfp_price_mean: {df_prov['wfp_price_mean'].isna().sum()}\")\n",
            "\n",
            "# Gestione di eventuali valori nulli tramite interpolazione lineare\n",
            "if df_prov['wfp_price_mean'].isna().any():\n",
            "    print(\"Trovati valori nulli, applicazione dell'interpolazione lineare...\")\n",
            "    df_prov['wfp_price_mean'] = df_prov['wfp_price_mean'].interpolate(method='linear')\n",
            "\n",
            "ts = df_prov['wfp_price_mean']"
        ]
    })
    
    # Cell 5: Plot time series
    cells.append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "### 1. Visualizzazione Grafica della Serie Storica"
        ]
    })
    
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "plt.figure(figsize=(14, 6))\n",
            "plt.plot(ts, label=f\"WFP Price Mean - {provincia}\", color='#1f77b4', linewidth=2)\n",
            "plt.title(f\"Indice dei prezzi alimentari medi - Provincia di {provincia} (AFG)\", fontsize=14)\n",
            "plt.xlabel(\"Anno\", fontsize=12)\n",
            "plt.ylabel(\"Prezzo Medio (Indice WFP)\", fontsize=12)\n",
            "plt.legend(loc=\"upper left\")\n",
            "plt.show()"
        ]
    })
    
    # Cell 6: Stationarity Test
    cells.append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "### 2. Analisi di Stazionarietà (Augmented Dickey-Fuller Test)\n",
            "I modelli ARIMA richiedono una serie storica stazionaria (media, varianza e autocovarianza costanti nel tempo).\n",
            "Visualizziamo la media/deviazione standard mobile (rolling stats) ed eseguiamo il test ADF."
        ]
    })
    
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "def check_stationarity(timeseries, window=12):\n",
            "    # Rolling statistics\n",
            "    rolmean = timeseries.rolling(window=window).mean()\n",
            "    rolstd = timeseries.rolling(window=window).std()\n",
            "\n",
            "    # Plot\n",
            "    plt.figure(figsize=(14, 6))\n",
            "    plt.plot(timeseries, color='#1f77b4', label='Originale', alpha=0.5)\n",
            "    plt.plot(rolmean, color='red', label=f'Media Mobile ({window}m)')\n",
            "    plt.plot(rolstd, color='black', label=f'Dev. Std. Mobile ({window}m)')\n",
            "    plt.legend(loc='best')\n",
            "    plt.title('Statistiche Mobili: Media e Deviazione Standard', fontsize=14)\n",
            "    plt.show()\n",
            "\n",
            "    # ADF Test\n",
            "    print('Risultati dell\\'Augmented Dickey-Fuller Test:')\n",
            "    dftest = adfuller(timeseries, autolag='AIC')\n",
            "    dfoutput = pd.Series(dftest[0:4], index=['Test Statistic', 'p-value', '#Lags Used', 'Number of Observations Used'])\n",
            "    for key, value in dftest[4].items():\n",
            "        dfoutput[f'Critical Value ({key})'] = value\n",
            "    print(dfoutput)\n",
            "    \n",
            "    if dfoutput['p-value'] < 0.05:\n",
            "        print(\"\\n--> La serie è STAZIONARIA (p-value < 0.05)\")\n",
            "    else:\n",
            "        print(\"\\n--> La serie NON è stazionaria (p-value >= 0.05). Sarà necessario applicare il differenziamento.\")\n",
            "\n",
            "check_stationarity(ts)"
        ]
    })
    
    # Cell 7: Differencing
    cells.append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "#### Differenziamento per rendere la serie stazionaria\n",
            "Se il p-value del test ADF è superiore a 0.05, applichiamo un differenziamento del primo ordine ($d=1$) e rivalutiamo."
        ]
    })
    
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "ts_diff = ts.diff().dropna()\n",
            "check_stationarity(ts_diff)"
        ]
    })
    
    # Cell 8: Decomposition
    cells.append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "### 3. Decomposizione della Serie Storica\n",
            "Decomponiamo la serie in Trend, Stagionalità e Componente Residua per osservare la struttura sottostante."
        ]
    })
    
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "decomposition = seasonal_decompose(ts, model='additive', period=12)\n",
            "fig = decomposition.plot()\n",
            "fig.set_size_inches(14, 10)\n",
            "plt.show()"
        ]
    })
    
    # Cell 9: ACF/PACF
    cells.append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "### 4. Grafici ACF (Autocorrelation) e PACF (Partial Autocorrelation)\n",
            "Questi grafici aiutano ad identificarne i parametri autoregressivi ($p$) e a media mobile ($q$) del modello ARIMA sulla serie differenziata."
        ]
    })
    
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "fig, axes = plt.subplots(1, 2, figsize=(16, 5))\n",
            "plot_acf(ts_diff, lags=40, ax=axes[0], title='Autocorrelazione (ACF)')\n",
            "plot_pacf(ts_diff, lags=40, ax=axes[1], title='Autocorrelazione Parziale (PACF)')\n",
            "plt.show()"
        ]
    })
    
    # Cell 10: Model Fitting Intro
    cells.append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "### 5. Modellazione ARIMA e SARIMAX\n",
            "Dividiamo la serie storica in:\n",
            "- **Train Set**: dati storici fino a 12 mesi fa.\n",
            "- **Test Set**: gli ultimi 12 mesi della serie.\n",
            "\n",
            "Dopodiché proveremo a calibrare:\n",
            "1. Un modello **ARIMA(p, d, q)** classico (es. `ARIMA(1, 1, 1)`).\n",
            "2. Un modello **SARIMAX(p, d, q)x(P, D, Q, s)** per catturare la stagionalità annuale (`s=12`)."
        ]
    })
    
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "# Dividiamo in Train (fino a 12 mesi fa) e Test (ultimi 12 mesi)\n",
            "train = ts.iloc[:-12]\n",
            "test = ts.iloc[-12:]\n",
            "\n",
            "print(f\"Train size: {len(train)} (da {train.index.min()} a {train.index.max()})\")\n",
            "print(f\"Test size: {len(test)} (da {test.index.min()} a {test.index.max()})\")"
        ]
    })
    
    # Cell 11: ARIMA fit
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "print(\"--- Adattamento modello ARIMA(1, 1, 1) ---\")\n",
            "arima_model = ARIMA(train, order=(1, 1, 1))\n",
            "arima_results = arima_model.fit()\n",
            "print(arima_results.summary())"
        ]
    })
    
    # Cell 12: SARIMAX fit
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "print(\"--- Adattamento modello SARIMAX(1, 1, 1)x(1, 1, 1, 12) ---\")\n",
            "sarimax_model = SARIMAX(train, order=(1, 1, 1), seasonal_order=(1, 1, 1, 12), enforce_stationarity=False, enforce_invertibility=False)\n",
            "sarimax_results = sarimax_model.fit(disp=False)\n",
            "print(sarimax_results.summary())"
        ]
    })
    
    # Cell 13: Model Diagnostics
    cells.append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "### 6. Diagnostica del Modello\n",
            "Controlliamo i residui per verificare se assomigliano a rumore bianco (assenza di autocorrelazione residua e distribuzione normale)."
        ]
    })
    
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "sarimax_results.plot_diagnostics(figsize=(14, 10))\n",
            "plt.show()"
        ]
    })
    
    # Cell 14: Forecast
    cells.append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "### 7. Previsione (Forecasting)\n",
            "Effettuiamo la previsione sugli ultimi 12 mesi (Test set) e proiettiamoci nel futuro (ulteriori 12 mesi), mostrando l'intervallo di confidenza al 95%."
        ]
    })
    
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "# Previsione sul periodo del Test set + 12 mesi futuri (totale 24 mesi)\n",
            "forecast_steps = 24\n",
            "forecast_res = sarimax_results.get_forecast(steps=forecast_steps)\n",
            "forecast_index = pd.date_range(start=test.index[0], periods=forecast_steps, freq='MS')\n",
            "\n",
            "forecast_mean = forecast_res.predicted_mean\n",
            "forecast_mean.index = forecast_index\n",
            "\n",
            "confidence_intervals = forecast_res.conf_int(alpha=0.05)\n",
            "confidence_intervals.index = forecast_index\n",
            "\n",
            "# Plot dei risultati\n",
            "plt.figure(figsize=(14, 6))\n",
            "plt.plot(ts.loc['2020-01-01':], label='Prezzi Storici (Reali)', color='#1f77b4', linewidth=2)\n",
            "plt.plot(forecast_mean, label='Previsione SARIMAX', color='red', linestyle='--', linewidth=2)\n",
            "plt.fill_between(\n",
            "    confidence_intervals.index,\n",
            "    confidence_intervals.iloc[:, 0],\n",
            "    confidence_intervals.iloc[:, 1],\n",
            "    color='pink',\n",
            "    alpha=0.3,\n",
            "    label='Intervallo di confidenza al 95%'\n",
            ")\n",
            "plt.axvline(x=test.index[0], color='gray', linestyle=':', label='Inizio Previsione')\n",
            "plt.title(f\"Forecasting Prezzi Alimentari WFP - {provincia}\", fontsize=14)\n",
            "plt.xlabel(\"Data\", fontsize=12)\n",
            "plt.ylabel(\"Indice Prezzi\", fontsize=12)\n",
            "plt.legend(loc='upper left')\n",
            "plt.show()"
        ]
    })
    
    # Construct notebook dict
    notebook = {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
            },
            "language_info": {
                "codemirror_mode": {
                    "name": "ipython",
                    "version": 3
                },
                "file_extension": ".py",
                "mimetype": "text/x-python",
                "name": "python",
                "nbconvert_exporter": "python",
                "pygments_lexer": "ipython3",
                "version": "3.11.0"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 2
    }
    
    output_path = tsa_dir / "arima_analysis_afg.ipynb"
    print(f"Writing notebook to {output_path}...")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(notebook, f, indent=2, ensure_ascii=False)
    print("Notebook created successfully!")

if __name__ == "__main__":
    main()
