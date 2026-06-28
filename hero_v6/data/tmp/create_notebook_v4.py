import json
import os
from pathlib import Path

def main():
    base_dir = Path("c:/Dev/Progetti/HERO/hero_v6")
    tsa_dir = base_dir / "TSA"
    tsa_dir.mkdir(parents=True, exist_ok=True)
    
    cells = []
    
    # Cell 1: Markdown Introduction
    cells.append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "# Analisi delle Serie Storiche (TSA) e Machine Learning Multivariato per IPC\n",
            "\n",
            "Questo notebook contiene l'implementazione completa delle analisi richieste:\n",
            "1. **Analisi Univariata (Time Series Forecasting)**:\n",
            "   - Applichiamo i modelli **SARIMAX**, **Holt-Winters Exponential Smoothing** e **Meta Prophet** (se installato).\n",
            "   - Analizziamo i 3 paesi con maggior volume di dati a livello Admin1: **Afghanistan (AFG)**, **Somalia (SOM)** e **Kenya (KEN)**.\n",
            "   - Per ciascun paese selezioniamo una provincia specifica ed effettuiamo previsioni sull'indice dei prezzi WFP (`wfp_price_mean`).\n",
            "   - I grafici generati vengono salvati automaticamente nella cartella `plots/`.\n",
            "2. **Analisi Multivariata (IPC Phase 3+ % Prediction)**:\n",
            "   - Utilizziamo il dataset integrato (joined) `merged_adm1_wide.parquet` per i 3 paesi target.\n",
            "   - Filtriamo per `Validity period == 'current'` per ottenere una serie storica pulita senza sovrapposizioni temporali.\n",
            "   - Prepariamo le feature derivanti da conflitti (ACLED), sfollati (IDP), piogge (Rainfall) e mercati (WFP).\n",
            "   - Addestriamo un modello non lineare (**Random Forest Regressor**) ed uno lineare (**Ridge Regression**) per predire la percentuale di popolazione in fase IPC 3 o superiore (`phase_3plus_percentage`).\n",
            "   - Valutiamo le metriche di errore ($R^2$, MAE, RMSE) e analizziamo la feature importance del modello.\n",
            "   - Generiamo un grafico che mostra l'andamento reale dell'IPC vs quello predetto lungo la serie storica temporale per ciascuno dei 3 paesi di test."
        ]
    })
    
    # Cell 2: Imports
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "source": [
            "import os\n",
            "import numpy as np\n",
            "import pandas as pd\n",
            "import matplotlib.pyplot as plt\n",
            "import seaborn as sns\n",
            "\n",
            "# TSA Models\n",
            "from statsmodels.tsa.statespace.sarimax import SARIMAX\n",
            "from statsmodels.tsa.holtwinters import ExponentialSmoothing\n",
            "\n",
            "# ML Models & Metrics\n",
            "from sklearn.model_selection import train_test_split\n",
            "from sklearn.impute import SimpleImputer\n",
            "from sklearn.ensemble import RandomForestRegressor\n",
            "from sklearn.linear_model import Ridge\n",
            "from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score\n",
            "\n",
            "# Setup plot\n",
            "sns.set_theme(style=\"whitegrid\")\n",
            "plt.rcParams[\"figure.figsize\"] = (12, 6)\n",
            "plt.rcParams[\"axes.grid\"] = True\n",
            "\n",
            "# Creazione cartella plots se non esiste\n",
            "os.makedirs(\"plots\", exist_ok=True)"
        ]
    })
    
    # Cell 3: Load Datasets
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "source": [
            "wfp_path = \"../data/tmp/wfp_monthly_adm1_index.parquet\"\n",
            "merged_path = \"../data/merged/merged_adm1_wide.parquet\"\n",
            "\n",
            "df_wfp = pd.read_parquet(wfp_path, engine=\"pyarrow\")\n",
            "df_wfp['date'] = pd.to_datetime(df_wfp['date'])\n",
            "\n",
            "df_merged = pd.read_parquet(merged_path, engine=\"pyarrow\")\n",
            "print(f\"WFP dataset shape: {df_wfp.shape}\")\n",
            "print(f\"Merged dataset shape: {df_merged.shape}\")"
        ]
    })
    
    # Cell 4: TSA Setup
    cells.append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "## 1. Analisi Univariata sulle Singole Serie Storiche\n",
            "Prendiamo come riferimento 3 paesi con più dati a livello Admin1:\n",
            "1. **Afghanistan (AFG)** - Provincia di Kabul (`AF01`)\n",
            "2. **Somalia (SOM)** - Provincia di Awdal (`SO11`)\n",
            "3. **Kenya (KEN)** - Provincia di Rift Valley (`KE023`)"
        ]
    })
    
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "source": [
            "ts_configs = [\n",
            "    {\"ISO3\": \"AFG\", \"pcode\": \"AF01\", \"name\": \"Kabul\"},\n",
            "    {\"ISO3\": \"SOM\", \"pcode\": \"SO11\", \"name\": \"Awdal\"},\n",
            "    {\"ISO3\": \"KEN\", \"pcode\": \"KE023\", \"name\": \"Rift Valley\"}\n",
            "]\n",
            "\n",
            "# Verifica installazione Prophet\n",
            "try:\n",
            "    from prophet import Prophet\n",
            "    import logging\n",
            "    logging.getLogger('prophet').setLevel(logging.WARNING)\n",
            "    prophet_installed = True\n",
            "    print(\"Prophet è installato!\")\n",
            "except ImportError:\n",
            "    prophet_installed = False\n",
            "    print(\"Prophet non è installato. Esegui 'pip install prophet' per abilitarlo.\")"
        ]
    })
    
    # Cell 5: TSA loop
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "source": [
            "for config in ts_configs:\n",
            "    iso = config[\"ISO3\"]\n",
            "    pcode = config[\"pcode\"]\n",
            "    name = config[\"name\"]\n",
            "    \n",
            "    print(f\"\\n{'='*50}\\nElaborazione TSA per {iso} - {name} ({pcode})\\n{'='*50}\")\n",
            "    \n",
            "    # Estrazione e ordinamento serie temporale\n",
            "    series_df = df_wfp[(df_wfp[\"ISO3\"] == iso) & (df_wfp[\"adm1_pcode\"] == pcode)].copy()\n",
            "    series_df = series_df.set_index(\"date\").sort_index()\n",
            "    series_df = series_df.asfreq(\"MS\")\n",
            "    \n",
            "    # Interpolazione lineare se presenti NaN\n",
            "    if series_df[\"wfp_price_mean\"].isna().any():\n",
            "        series_df[\"wfp_price_mean\"] = series_df[\"wfp_price_mean\"].interpolate(method=\"linear\")\n",
            "        \n",
            "    ts = series_df[\"wfp_price_mean\"]\n",
            "    \n",
            "    # Train-test split (ultimi 12 mesi per test)\n",
            "    train = ts.iloc[:-12]\n",
            "    test = ts.iloc[-12:]\n",
            "    forecast_steps = 24\n",
            "    forecast_index = pd.date_range(start=test.index[0], periods=forecast_steps, freq=\"MS\")\n",
            "    \n",
            "    # 1. Modello SARIMAX\n",
            "    print(\"  Adattamento SARIMAX...\")\n",
            "    sarimax_model = SARIMAX(train, order=(1, 1, 1), seasonal_order=(1, 1, 1, 12),\n",
            "                            enforce_stationarity=False, enforce_invertibility=False)\n",
            "    sarimax_res = sarimax_model.fit(disp=False)\n",
            "    sarimax_forecast_obj = sarimax_res.get_forecast(steps=forecast_steps)\n",
            "    sarimax_forecast = sarimax_forecast_obj.predicted_mean\n",
            "    sarimax_forecast.index = forecast_index\n",
            "    sarimax_ci = sarimax_forecast_obj.conf_int(alpha=0.05)\n",
            "    sarimax_ci.index = forecast_index\n",
            "    \n",
            "    # Valutazione SARIMAX\n",
            "    sarimax_mae = mean_absolute_error(test, sarimax_forecast.iloc[:12])\n",
            "    sarimax_rmse = np.sqrt(mean_squared_error(test, sarimax_forecast.iloc[:12]))\n",
            "    \n",
            "    # 2. Modello Holt-Winters\n",
            "    print(\"  Adattamento Holt-Winters...\")\n",
            "    hw_model = ExponentialSmoothing(train, trend=\"add\", seasonal=\"add\", seasonal_periods=12)\n",
            "    hw_res = hw_model.fit()\n",
            "    hw_forecast = hw_res.forecast(steps=forecast_steps)\n",
            "    hw_forecast.index = forecast_index\n",
            "    \n",
            "    # Valutazione Holt-Winters\n",
            "    hw_mae = mean_absolute_error(test, hw_forecast.iloc[:12])\n",
            "    hw_rmse = np.sqrt(mean_squared_error(test, hw_forecast.iloc[:12]))\n",
            "    \n",
            "    # 3. Modello Prophet (se disponibile)\n",
            "    prophet_forecast = pd.Series(np.nan, index=forecast_index)\n",
            "    prophet_mae, prophet_rmse = np.nan, np.nan\n",
            "    if prophet_installed:\n",
            "        print(\"  Adattamento Prophet...\")\n",
            "        prophet_train = train.reset_index().rename(columns={\"date\": \"ds\", \"wfp_price_mean\": \"y\"})\n",
            "        m = Prophet(yearly_seasonality=True, weekly_seasonality=False, daily_seasonality=False)\n",
            "        m.fit(prophet_train)\n",
            "        future = m.make_future_dataframe(periods=forecast_steps, freq=\"MS\")\n",
            "        forecast_prophet_df = m.predict(future)\n",
            "        prophet_forecast = forecast_prophet_df.set_index(\"ds\").loc[test.index[0]:, \"yhat\"].iloc[:forecast_steps]\n",
            "        prophet_forecast.index = forecast_index\n",
            "        \n",
            "        prophet_mae = mean_absolute_error(test, prophet_forecast.iloc[:12])\n",
            "        prophet_rmse = np.sqrt(mean_squared_error(test, prophet_forecast.iloc[:12]))\n",
            "        \n",
            "    # Tabella metriche\n",
            "    metrics_df = pd.DataFrame({\n",
            "        'Modello': ['SARIMAX', 'Holt-Winters', 'Prophet'],\n",
            "        'MAE': [sarimax_mae, hw_mae, prophet_mae],\n",
            "        'RMSE': [sarimax_rmse, hw_rmse, prophet_rmse]\n",
            "    })\n",
            "    print(\"\\nMetriche di performance sul Test Set (12 mesi):\")\n",
            "    print(metrics_df.to_string(index=False))\n",
            "    \n",
            "    # Plot delle Previsioni\n",
            "    plt.figure(figsize=(14, 6))\n",
            "    plt.plot(ts.loc[\"2020-01-01\":], label=\"Dato Reale\", color=\"black\", linewidth=2.5)\n",
            "    plt.plot(sarimax_forecast, label=f\"SARIMAX Forecast (MAE: {sarimax_mae:.3f})\", color=\"#1f77b4\", linestyle=\"--\")\n",
            "    plt.plot(hw_forecast, label=f\"Holt-Winters Forecast (MAE: {hw_mae:.3f})\", color=\"green\", linestyle=\"-.\")\n",
            "    if prophet_installed:\n",
            "        plt.plot(prophet_forecast, label=f\"Prophet Forecast (MAE: {prophet_mae:.3f})\", color=\"orange\", linestyle=\":\")\n",
            "    \n",
            "    plt.fill_between(sarimax_ci.index, sarimax_ci.iloc[:, 0], sarimax_ci.iloc[:, 1], color=\"#1f77b4\", alpha=0.1, label=\"SARIMAX Conf. Int 95%\")\n",
            "    plt.axvline(x=test.index[0], color=\"red\", linestyle=\":\", linewidth=1.5, label=\"Inizio Test / Forecast\")\n",
            "    plt.title(f\"Confronto Modelli Univariati - {iso} ({name})\", fontsize=14)\n",
            "    plt.xlabel(\"Data\", fontsize=12)\n",
            "    plt.ylabel(\"Indice Prezzi WFP\", fontsize=12)\n",
            "    plt.legend(loc=\"upper left\")\n",
            "    \n",
            "    # Salvataggio\n",
            "    fig_name = f\"plots/univariate_{iso.lower()}_{pcode.lower()}.png\"\n",
            "    plt.savefig(fig_name, dpi=150, bbox_inches=\"tight\")\n",
            "    plt.show()\n",
            "    print(f\"Grafico salvato in: {fig_name}\")"
        ]
    })
    
    # Cell 6: Multivariate Section Introduction
    cells.append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "## 2. Analisi Multivariata sul Dataset Integrato (Joined)\n",
            "\n",
            "In questa sezione proviamo ad addestrare modelli di Machine Learning per **predire la percentuale di popolazione in stato di crisi alimentare (IPC Phase 3+)**.\n",
            "\n",
            "Filtriamo per `Validity period == 'current'` per ottenere una serie temporale pulita senza sovrapposizioni temporali e usiamo le seguenti feature:\n",
            "- **Conflitto (ACLED)**: Numero totale di eventi e di vittime.\n",
            "- **Sfollamento (IDP)**: Popolazione sfollata interna.\n",
            "- **Precipitazioni (Rainfall)**: Livello di piogge, anomalia ad 1 mese e a 3 mesi.\n",
            "- **Prezzi Alimentari (WFP)**: Indice dei prezzi medi e inflazione generale dei mercati nell'area."
        ]
    })
    
    # Cell 7: Data Preparation for ML
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "source": [
            "target_countries = [\"AFG\", \"SOM\", \"KEN\"]\n",
            "df_ml = df_merged[\n",
            "    df_merged[\"Country\"].isin(target_countries) & \n",
            "    (df_merged[\"Validity period\"] == \"current\")\n",
            "].copy()\n",
            "\n",
            "# Colonne target e feature\n",
            "target_col = \"phase_3plus_percentage\"\n",
            "feature_cols = [\n",
            "    \"acled_total_events\", \"acled_total_fatalities\", \n",
            "    \"idp_population\", \n",
            "    \"rain_1m\", \"rain_3m\", \"rain_anomaly_1m\", \"rain_anomaly_3m\", \n",
            "    \"wfp_price\", \"wfp_inflation\"\n",
            "]\n",
            "\n",
            "# Rimozione righe con target nullo\n",
            "df_ml = df_ml.dropna(subset=[target_col])\n",
            "\n",
            "X = df_ml[feature_cols].copy()\n",
            "y = df_ml[target_col]\n",
            "\n",
            "# Preprocessing ed Imputazione\n",
            "# Per ACLED e IDP, la mancanza di dati corrisponde a 0\n",
            "X[\"acled_total_events\"] = X[\"acled_total_events\"].fillna(0)\n",
            "X[\"acled_total_fatalities\"] = X[\"acled_total_fatalities\"].fillna(0)\n",
            "X[\"idp_population\"] = X[\"idp_population\"].fillna(0)\n",
            "\n",
            "# Per Rainfall e WFP usiamo un'imputazione mediana per i valori mancanti\n",
            "imputer = SimpleImputer(strategy=\"median\")\n",
            "X_imputed = imputer.fit_transform(X)\n",
            "X_imputed_df = pd.DataFrame(X_imputed, columns=feature_cols)\n",
            "\n",
            "# Suddivisione in Train e Test (80/20)\n",
            "X_train, X_test, y_train, y_test = train_test_split(X_imputed_df, y, test_size=0.2, random_state=42)\n",
            "print(f\"ML Train size: {X_train.shape[0]} righe | Test size: {X_test.shape[0]} righe\")"
        ]
    })
    
    # Cell 8: Model fitting
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "source": [
            "# 1. Random Forest Regressor (Non lineare)\n",
            "rf = RandomForestRegressor(n_estimators=150, random_state=42, n_jobs=-1)\n",
            "rf.fit(X_train, y_train)\n",
            "y_pred_rf = rf.predict(X_test)\n",
            "\n",
            "# 2. Ridge Regression (Lineare)\n",
            "ridge = Ridge()\n",
            "ridge.fit(X_train, y_train)\n",
            "y_pred_ridge = ridge.predict(X_test)\n",
            "\n",
            "# Calcolo delle metriche di valutazione\n",
            "print(\"Confronto Performance dei Modelli per predizione IPC (Phase 3+ %):\")\n",
            "print(f\"  Random Forest - R^2: {r2_score(y_test, y_pred_rf):.3f} | MAE: {mean_absolute_error(y_test, y_pred_rf):.3f}% | RMSE: {np.sqrt(mean_squared_error(y_test, y_pred_rf)):.3f}%\")\n",
            "print(f\"  Ridge Regr.   - R^2: {r2_score(y_test, y_pred_ridge):.3f} | MAE: {mean_absolute_error(y_test, y_pred_ridge):.3f}% | RMSE: {np.sqrt(mean_squared_error(y_test, y_pred_ridge)):.3f}%\")"
        ]
    })
    
    # Cell 9: Plot Feature Importances
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "source": [
            "plt.figure(figsize=(10, 6))\n",
            "importances = rf.feature_importances_\n",
            "indices = np.argsort(importances)[::-1]\n",
            "sorted_features = [feature_cols[i] for i in indices]\n",
            "sorted_importances = importances[indices]\n",
            "\n",
            "sns.barplot(x=sorted_importances, y=sorted_features, palette=\"viridis\", hue=sorted_features, legend=False)\n",
            "plt.title(\"Importanza delle Feature - Random Forest Regressor\", fontsize=14)\n",
            "plt.xlabel(\"Score di Importanza\", fontsize=12)\n",
            "plt.ylabel(\"Feature\", fontsize=12)\n",
            "\n",
            "# Salvataggio\n",
            "fi_name = \"plots/multivariate_feature_importance.png\"\n",
            "plt.savefig(fi_name, dpi=150, bbox_inches=\"tight\")\n",
            "plt.show()\n",
            "print(f\"Grafico salvato in: {fi_name}\")"
        ]
    })
    
    # Cell 10: Plot Predictions
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "source": [
            "plt.figure(figsize=(8, 8))\n",
            "plt.scatter(y_test, y_pred_rf, alpha=0.5, color=\"#1f77b4\", label=\"Predizioni vs Dati Reali\")\n",
            "plt.plot([y_test.min(), y_test.max()], [y_test.min(), y_test.max()], \"r--\", lw=2, label=\"Linea Ideale\")\n",
            "plt.title(f\"Predizione IPC Phase 3+ (Random Forest - R^2: {r2_score(y_test, y_pred_rf):.2f})\", fontsize=14)\n",
            "plt.xlabel(\"Percentuale IPC Reale (Phase 3+ %)\", fontsize=12)\n",
            "plt.ylabel(\"Percentuale IPC Predetta\", fontsize=12)\n",
            "plt.legend()\n",
            "\n",
            "# Salvataggio\n",
            "pred_name = \"plots/multivariate_predictions_vs_actual.png\"\n",
            "plt.savefig(pred_name, dpi=150, bbox_inches=\"tight\")\n",
            "plt.show()\n",
            "print(f\"Grafico salvato in: {pred_name}\")"
        ]
    })
    
    # Cell 11: Plot Timeline Series for predicting IPC
    cells.append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "### 3. Visualizzazione Temporale dell'IPC Reale vs Predetto per le 3 Province di Test\n",
            "\n",
            "Per verificare la bontà dinamica del modello di Machine Learning, calcoliamo le predizioni per l'intero dataset e plottiamo la serie storica dell'IPC reale a confronto con l'IPC predetto per:\n",
            "- **Kabul** (Afghanistan)\n",
            "- **Awdal** (Somalia)\n",
            "- **Rift Valley** (Kenya)"
        ]
    })
    
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "source": [
            "# Applichiamo l'imputazione sul dataset completo di X\n",
            "X_all_imputed = imputer.transform(X.fillna({\n",
            "    \"acled_total_events\": 0, \"acled_total_fatalities\": 0, \"idp_population\": 0\n",
            "}))\n",
            "\n",
            "# Aggiungiamo le predizioni del Random Forest al DataFrame\n",
            "df_ml[\"predicted_phase_3plus_percentage\"] = rf.predict(X_all_imputed)\n",
            "\n",
            "# Plot delle time series per le tre province\n",
            "fig, axes = plt.subplots(3, 1, figsize=(14, 15), sharex=False)\n",
            "\n",
            "for idx, config in enumerate(ts_configs):\n",
            "    iso = config[\"ISO3\"]\n",
            "    pcode = config[\"pcode\"]\n",
            "    name = config[\"name\"]\n",
            "    ax = axes[idx]\n",
            "    \n",
            "    # Filtriamo per la provincia corrente e ordiniamo per data 'From'\n",
            "    prov_df = df_ml[df_ml[\"adm1_pcode\"] == pcode].sort_values(\"From\").copy()\n",
            "    \n",
            "    if len(prov_df) > 0:\n",
            "        ax.plot(prov_df[\"From\"], prov_df[\"phase_3plus_percentage\"], marker='o', label=\"IPC Phase 3+ % Reale\", color=\"black\", linewidth=2.5)\n",
            "        ax.plot(prov_df[\"From\"], prov_df[\"predicted_phase_3plus_percentage\"], marker='s', label=\"Predizione Random Forest\", color=\"red\", linestyle=\"--\", linewidth=2)\n",
            "        ax.set_title(f\"Serie Storica IPC Phase 3+ %: Reale vs Predetto - {iso} ({name})\", fontsize=12)\n",
            "        ax.set_ylabel(\"% Popolazione\")\n",
            "        ax.legend(loc=\"upper left\")\n",
            "    else:\n",
            "        ax.text(0.5, 0.5, f\"Dati non disponibili per {name} ({pcode})\", transform=ax.transAxes, ha='center')\n",
            "\n",
            "plt.xlabel(\"Data di Analisi (Periodo From)\")\n",
            "plt.tight_layout()\n",
            "\n",
            "# Salvataggio\n",
            "timeline_name = \"plots/multivariate_timeline_predictions.png\"\n",
            "plt.savefig(timeline_name, dpi=150, bbox_inches=\"tight\")\n",
            "plt.show()\n",
            "print(f\"Grafico delle serie temporali salvato in: {timeline_name}\")"
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
    
    output_path = tsa_dir / "tsa_and_multivariate_analysis.ipynb"
    print(f"Writing notebook to {output_path}...")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(notebook, f, indent=2, ensure_ascii=False)
    print("Notebook created successfully!")

if __name__ == "__main__":
    main()
