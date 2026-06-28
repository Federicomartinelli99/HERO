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
            "# Time Series Analysis (TSA): Afghanistan (Admin1)\n",
            "\n",
            "Questo notebook analizza l'andamento temporale dell'indice dei prezzi alimentari WFP (`wfp_price_mean`) a livello provinciale (Admin1) in Afghanistan.\n",
            "\n",
            "In questa versione estesa:\n",
            "1. Analizziamo le proprietà statistiche della serie storica (stazionarietà, trend, stagionalità).\n",
            "2. Addestriamo un modello classico **SARIMAX**.\n",
            "3. Addestriamo un modello **Holt-Winters Exponential Smoothing**.\n",
            "4. Integriamo e addestriamo **Prophet** (di Meta).\n",
            "5. Effettuiamo un **confronto prestazionale** (MAE, RMSE) sul test set di 12 mesi per capire qual è il modello migliore.\n",
            "6. Discutiamo altre tecniche avanzate (modelli multivariati VAR, regressione ML con lag)."
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
            "from statsmodels.tsa.holtwinters import ExponentialSmoothing\n",
            "\n",
            "# Valutazione Metriche\n",
            "from sklearn.metrics import mean_absolute_error, mean_squared_error\n",
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
            "Selezioniamo come esempio la provincia di **Kabul** e impostiamo la data come indice temporale."
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
            "# Frequenza mensile start-of-month ('MS')\n",
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
            "### 1. Visualizzazione della Serie Storica"
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
            "### 2. Analisi di Stazionarietà (Augmented Dickey-Fuller Test)"
        ]
    })
    
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "def check_stationarity(timeseries, window=12):\n",
            "    rolmean = timeseries.rolling(window=window).mean()\n",
            "    rolstd = timeseries.rolling(window=window).std()\n",
            "\n",
            "    plt.figure(figsize=(14, 5))\n",
            "    plt.plot(timeseries, color='#1f77b4', label='Originale', alpha=0.5)\n",
            "    plt.plot(rolmean, color='red', label=f'Media Mobile ({window}m)')\n",
            "    plt.plot(rolstd, color='black', label=f'Dev. Std. Mobile ({window}m)')\n",
            "    plt.legend(loc='best')\n",
            "    plt.title('Statistiche Mobili: Media e Deviazione Standard', fontsize=14)\n",
            "    plt.show()\n",
            "\n",
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
            "        print(\"\\n--> La serie NON è stazionaria (p-value >= 0.05). È necessario il differenziamento.\")\n",
            "\n",
            "check_stationarity(ts)"
        ]
    })
    
    # Cell 7: Differencing
    cells.append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "Se la serie non è stazionaria, applichiamo un differenziamento del primo ordine ($d=1$)."
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
            "### 3. Decomposizione della Serie Storica"
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
            "fig.set_size_inches(14, 8)\n",
            "plt.show()"
        ]
    })
    
    # Cell 9: ACF/PACF
    cells.append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "### 4. ACF e PACF sulla serie differenziata"
        ]
    })
    
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "fig, axes = plt.subplots(1, 2, figsize=(16, 4))\n",
            "plot_acf(ts_diff, lags=36, ax=axes[0], title='Autocorrelazione (ACF)')\n",
            "plot_pacf(ts_diff, lags=36, ax=axes[1], title='Autocorrelazione Parziale (PACF)')\n",
            "plt.show()"
        ]
    })
    
    # Cell 10: Train-Test Split
    cells.append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "### 5. Definizione del Dataset di Train e Test\n",
            "Teniamo da parte gli ultimi **12 mesi** come Test Set per la validazione quantitativa dei modelli. I successivi 12 mesi saranno di puro forecast."
        ]
    })
    
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "train = ts.iloc[:-12]\n",
            "test = ts.iloc[-12:]\n",
            "forecast_steps = 24\n",
            "\n",
            "print(f\"Train set: da {train.index.min()} a {train.index.max()} (N={len(train)})\")\n",
            "print(f\"Test set: da {test.index.min()} a {test.index.max()} (N={len(test)})\")"
        ]
    })
    
    # Cell 11: SARIMAX Model
    cells.append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "### Modello 1: SARIMAX\n",
            "Calibriamo un modello stagionale autoregressivo integrato a media mobile: **SARIMAX(1, 1, 1)x(1, 1, 1, 12)**."
        ]
    })
    
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "sarimax_model = SARIMAX(\n",
            "    train,\n",
            "    order=(1, 1, 1),\n",
            "    seasonal_order=(1, 1, 1, 12),\n",
            "    enforce_stationarity=False,\n",
            "    enforce_invertibility=False\n",
            ")\n",
            "sarimax_results = sarimax_model.fit(disp=False)\n",
            "print(sarimax_results.summary())\n",
            "\n",
            "# Forecast SARIMAX\n",
            "sarimax_forecast_obj = sarimax_results.get_forecast(steps=forecast_steps)\n",
            "forecast_index = pd.date_range(start=test.index[0], periods=forecast_steps, freq='MS')\n",
            "\n",
            "sarimax_forecast = sarimax_forecast_obj.predicted_mean\n",
            "sarimax_forecast.index = forecast_index\n",
            "sarimax_ci = sarimax_forecast_obj.conf_int(alpha=0.05)\n",
            "sarimax_ci.index = forecast_index"
        ]
    })
    
    # Cell 12: Holt-Winters Exponential Smoothing
    cells.append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "### Modello 2: Holt-Winters (Exponential Smoothing)\n",
            "Il metodo Holt-Winters gestisce esplicitamente il trend lineare e la componente stagionale (configurato con stagionalità additiva a 12 mesi)."
        ]
    })
    
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "hw_model = ExponentialSmoothing(\n",
            "    train,\n",
            "    trend='add',\n",
            "    seasonal='add',\n",
            "    seasonal_periods=12\n",
            ")\n",
            "hw_results = hw_model.fit()\n",
            "print(hw_results.summary())\n",
            "\n",
            "# Forecast Holt-Winters\n",
            "hw_forecast = hw_results.forecast(steps=forecast_steps)\n",
            "hw_forecast.index = forecast_index"
        ]
    })
    
    # Cell 13: Prophet Model
    cells.append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "### Modello 3: Meta Prophet\n",
            "Prophet è un modello additivo di curve di crescita che si adatta particolarmente bene a trend non lineari con effetti stagionali annuali e festività.\n",
            "\n",
            "> **Nota**: Se Prophet non è installato, esegui nel terminale:\n",
            "> `pip install prophet`"
        ]
    })
    
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "try:\n",
            "    from prophet import Prophet\n",
            "    import logging\n",
            "    logging.getLogger('prophet').setLevel(logging.WARNING)\n",
            "    \n",
            "    # Prophet richiede colonne ds (date) e y (valore)\n",
            "    prophet_train = train.reset_index().rename(columns={'date': 'ds', 'wfp_price_mean': 'y'})\n",
            "    \n",
            "    m = Prophet(\n",
            "        yearly_seasonality=True,\n",
            "        weekly_seasonality=False,\n",
            "        daily_seasonality=False\n",
            "    )\n",
            "    m.fit(prophet_train)\n",
            "    \n",
            "    # Costruzione dataframe futuro (12 mesi test + 12 mesi forecast = 24 mesi totali)\n",
            "    future = m.make_future_dataframe(periods=forecast_steps, freq='MS')\n",
            "    forecast_prophet_df = m.predict(future)\n",
            "    \n",
            "    # Estrazione previsioni\n",
            "    prophet_forecast = forecast_prophet_df.set_index('ds').loc[test.index[0]:, 'yhat']\n",
            "    prophet_forecast = prophet_forecast.iloc[:forecast_steps]\n",
            "    prophet_forecast.index = forecast_index\n",
            "    \n",
            "    prophet_installed = True\n",
            "    print(\"Modello Prophet addestrato con successo!\")\n",
            "except ImportError:\n",
            "    print(\"[WARN] Prophet non è installato. Esegui 'pip install prophet' per abilitare questa cella.\")\n",
            "    prophet_installed = False\n",
            "    prophet_forecast = pd.Series(np.nan, index=forecast_index)"
        ]
    })
    
    # Cell 14: Model Comparison
    cells.append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "### 6. Confronto delle Performance ed Errore di Validazione\n",
            "Calcoliamo le metriche **MAE** (Mean Absolute Error) e **RMSE** (Root Mean Squared Error) confrontando le previsioni dei modelli sul Test set (gli ultimi 12 mesi della serie storica reale)."
        ]
    })
    
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "# Estraiamo i primi 12 mesi di previsione (corrispondenti al Test set)\n",
            "sarimax_test_pred = sarimax_forecast.iloc[:12]\n",
            "hw_test_pred = hw_forecast.iloc[:12]\n",
            "\n",
            "# Calcolo metriche per SARIMAX\n",
            "sarimax_mae = mean_absolute_error(test, sarimax_test_pred)\n",
            "sarimax_rmse = np.sqrt(mean_squared_error(test, sarimax_test_pred))\n",
            "\n",
            "# Calcolo metriche per Holt-Winters\n",
            "hw_mae = mean_absolute_error(test, hw_test_pred)\n",
            "hw_rmse = np.sqrt(mean_squared_error(test, hw_test_pred))\n",
            "\n",
            "# Calcolo metriche per Prophet (se installato)\n",
            "if prophet_installed:\n",
            "    prophet_test_pred = prophet_forecast.iloc[:12]\n",
            "    prophet_mae = mean_absolute_error(test, prophet_test_pred)\n",
            "    prophet_rmse = np.sqrt(mean_squared_error(test, prophet_test_pred))\n",
            "else:\n",
            "    prophet_mae, prophet_rmse = np.nan, np.nan\n",
            "\n",
            "# Tabella di confronto\n",
            "metrics_df = pd.DataFrame({\n",
            "    'Modello': ['SARIMAX', 'Holt-Winters', 'Meta Prophet'],\n",
            "    'MAE': [sarimax_mae, hw_mae, prophet_mae],\n",
            "    'RMSE': [sarimax_rmse, hw_rmse, prophet_rmse]\n",
            "})\n",
            "print(metrics_df.to_string(index=False))"
        ]
    })
    
    # Cell 15: Combined Plot
    cells.append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "#### Grafico di Confronto delle Previsioni\n",
            "Visualizziamo l'andamento dei vari modelli a confronto con i dati reali."
        ]
    })
    
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "plt.figure(figsize=(14, 7))\n",
            "plt.plot(ts.loc['2021-01-01':], label='Dato Reale (Storico + Test)', color='black', linewidth=2.5)\n",
            "plt.plot(sarimax_forecast, label=f'SARIMAX (MAE: {sarimax_mae:.3f})', color='#1f77b4', linestyle='--')\n",
            "plt.plot(hw_forecast, label=f'Holt-Winters (MAE: {hw_mae:.3f})', color='green', linestyle='-.')\n",
            "\n",
            "if prophet_installed:\n",
            "    plt.plot(prophet_forecast, label=f'Prophet (MAE: {prophet_mae:.3f})', color='orange', linestyle=':')\n",
            "\n",
            "plt.fill_between(\n",
            "    sarimax_ci.index,\n",
            "    sarimax_ci.iloc[:, 0],\n",
            "    sarimax_ci.iloc[:, 1],\n",
            "    color='#1f77b4',\n",
            "    alpha=0.1,\n",
            "    label='SARIMAX Conf. Int. 95%'\n",
            ")\n",
            "\n",
            "plt.axvline(x=test.index[0], color='red', linestyle=':', linewidth=1.5, label='Inizio Test Set / Forecast')\n",
            "plt.title(f\"Confronto Previsioni Modelli TSA - Prezzi Alimentari {provincia}\", fontsize=14)\n",
            "plt.xlabel(\"Data\", fontsize=12)\n",
            "plt.ylabel(\"Indice Prezzi WFP\", fontsize=12)\n",
            "plt.legend(loc='upper left')\n",
            "plt.show()"
        ]
    })
    
    # Cell 16: Other Techniques Discussion
    cells.append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "### 7. Altre Tecniche Interessanti per lo Studio di Market Indices\n",
            "\n",
            "Oltre ad ARIMA/SARIMAX, Holt-Winters e Prophet, in ambito finanziario e umanitario si possono implementare altre metodologie di rilievo:\n",
            "\n",
            "#### A. Modelli Multivariati: VAR / VARMAX\n",
            "- **Descrizione**: I modelli Vector Autoregression (VAR) estendono l'ARIMA a scenari multivariati in cui le variabili si influenzano a vicenda simultaneamente.\n",
            "- **Applicazione nel progetto**: Possiamo modellare contemporaneamente `wfp_price_mean` e `wfp_inflation_mean` insieme ad altre serie temporali (come le anomalie delle piogge `rain_anomaly_1m` o gli eventi di conflitto di ACLED) per studiare la causalità (es. *Granger Causality*) e stimare le funzioni di risposta agli impulsi (come uno shock di siccità influenza i prezzi nei mesi successivi).\n",
            "- **Libreria**: `statsmodels.tsa.vector_ar.var_model.VAR`.\n",
            "\n",
            "#### B. Approccio Machine Learning con Feature Lagged\n",
            "- **Descrizione**: Consiste nel riformulare la serie storica come un problema di apprendimento supervisionato. Si creano colonne di feature basate sui valori passati (*lag features* es. $y_{t-1}, y_{t-2}$) e statistiche mobili (*rolling features* es. media mobile a 3 e 6 mesi).\n",
            "- **Modelli**: Si possono usare modelli di regressione robusti come **Random Forest**, **Gradient Boosting (XGBoost/LightGBM)** o **Ridge/Lasso Regression**.\n",
            "- **Vantaggi**: Gestiscono molto bene relazioni non-lineari complesse e l'inclusione di feature esterne statiche o dinamiche.\n",
            "\n",
            "#### C. Modelli Deep Learning (LSTM / GRU)\n",
            "- **Descrizione**: Reti neurali ricorrenti (RNN) specializzate in sequenze temporali. Le celle **LSTM (Long Short-Term Memory)** catturano dipendenze a lungo termine e pattern temporali complessi.\n",
            "- **Applicazione**: Utili soprattutto in presenza di dataset molto grandi e ricchi di osservazioni ad alta frequenza (giornaliera/settimanale), sebbene possano soffrire di overfitting su serie mensili brevi."
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
