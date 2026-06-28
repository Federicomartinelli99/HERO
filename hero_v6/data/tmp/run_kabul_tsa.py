import os
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# TSA models
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tsa.holtwinters import ExponentialSmoothing

# ML models and metrics
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score

# Set plot style
sns.set_theme(style="whitegrid")
plt.rcParams["figure.figsize"] = (12, 6)
plt.rcParams["axes.grid"] = True

def main():
    base_dir = Path("c:/Dev/Progetti/HERO/hero_v6")
    kabul_tsa_dir = base_dir / "TSA" / "Kabul_TSA"
    plots_dir = kabul_tsa_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)
    
    # -------------------------------------------------------------------------
    # 1. LOAD AND PREPROCESS RAW DATASETS FOR KABUL (AF01)
    # -------------------------------------------------------------------------
    print("Loading raw datasets for Kabul...")
    wfp_path = base_dir / "data" / "tmp" / "wfp_monthly_adm1_index.parquet"
    rain_path = base_dir / "data" / "raw" / "rainfall.parquet"
    acled_path = base_dir / "data" / "raw" / "acled.parquet"
    idp_path = base_dir / "data" / "raw" / "idp.parquet"
    merged_path = base_dir / "data" / "merged" / "merged_adm1_wide.parquet"
    
    df_wfp = pd.read_parquet(wfp_path, engine="pyarrow")
    df_rain = pd.read_parquet(rain_path, engine="pyarrow")
    df_acled = pd.read_parquet(acled_path, engine="pyarrow")
    df_idp = pd.read_parquet(idp_path, engine="pyarrow")
    df_merged = pd.read_parquet(merged_path, engine="pyarrow")
    
    # --- Resample/Align each to monthly frequency ---
    
    # A. WFP (natively monthly)
    wfp_k = df_wfp[(df_wfp["ISO3"] == "AFG") & (df_wfp["adm1_pcode"] == "AF01")].copy()
    wfp_k["date"] = pd.to_datetime(wfp_k["date"])
    wfp_k = wfp_k.set_index("date").sort_index()[["wfp_price_mean", "wfp_inflation_mean"]].asfreq("MS")
    # Interpolate WFP if any nulls
    wfp_k = wfp_k.interpolate(method="linear")
    
    # B. Rainfall (natively monthly, parse dates to YYYY-MM-01)
    rain_k = df_rain[df_rain["PCODE"] == "AF01"].copy()
    rain_k["date"] = pd.to_datetime(rain_k["date"]).dt.to_period("M").dt.to_timestamp()
    rain_k = rain_k.groupby("date")[["rain_1m", "rain_3m", "rain_anomaly_1m", "rain_anomaly_3m"]].mean().asfreq("MS")
    
    # C. ACLED (natively event-based summarized, group monthly)
    acled_k = df_acled[df_acled["admin1_code"] == "AF01"].copy()
    acled_k["date"] = pd.to_datetime(acled_k["reference_period_start"]).dt.to_period("M").dt.to_timestamp()
    acled_k = acled_k.groupby("date")[["events", "fatalities"]].sum().rename(
        columns={"events": "acled_events", "fatalities": "acled_fatalities"}
    ).asfreq("MS", fill_value=0)
    
    # D. IDP (assessment round-based, ffill to monthly)
    idp_k = df_idp[df_idp["admin1_code"] == "AF01"].copy()
    idp_k["date"] = pd.to_datetime(idp_k["reference_period_start"]).dt.to_period("M").dt.to_timestamp()
    idp_k = idp_k.groupby("date")[["population"]].mean().rename(
        columns={"population": "idp_population"}
    ).asfreq("MS").ffill().fillna(0)
    
    # E. IPC Phase 3+ (multi-monthly, expand to monthly and ffill)
    ipc_k = df_merged[(df_merged["adm1_pcode"] == "AF01") & (df_merged["Validity period"] == "current")].copy()
    expanded = []
    for _, row in ipc_k.iterrows():
        m_range = pd.date_range(start=row["From"], end=row["To"], freq="MS")
        for m in m_range:
            expanded.append({"date": m, "ipc_phase_3plus_pct": row["phase_3plus_percentage"]})
    df_ipc = pd.DataFrame(expanded).drop_duplicates(subset=["date"]).set_index("date").sort_index().asfreq("MS")
    df_ipc_filled = df_ipc.ffill().bfill()
    
    # Join all to monthly frequency
    joined = wfp_k.join([rain_k, acled_k, idp_k, df_ipc_filled], how="inner")
    print(f"Kabul joined monthly shape: {joined.shape} (from {joined.index.min()} to {joined.index.max()})")
    
    # -------------------------------------------------------------------------
    # 2. STAGE 1: UNIVARIATE FORECASTING OF PREDICTORS (12 Months ahead)
    # -------------------------------------------------------------------------
    predictors = [
        "wfp_price_mean", "wfp_inflation_mean", 
        "rain_1m", "rain_3m", "rain_anomaly_1m", "rain_anomaly_3m", 
        "acled_events", "acled_fatalities", 
        "idp_population"
    ]
    
    forecast_steps = 12
    forecast_index = pd.date_range(start=joined.index[-1] + pd.DateOffset(months=1), periods=forecast_steps, freq="MS")
    forecasted_predictors = pd.DataFrame(index=forecast_index)
    
    print("\nStage 1: Performing univariate forecasting on predictors...")
    for col in predictors:
        ts = joined[col]
        
        # Fit Holt-Winters (highly robust, adapts well to seasonality like rain)
        # Use additive seasonal component for rain and price indices
        try:
            # Handle features that might have zeros (like ACLED)
            if col in ["acled_events", "acled_fatalities", "idp_population"]:
                # Use Holt's Linear Trend or simple Exponential Smoothing if seasonal fails
                model = ExponentialSmoothing(ts, trend="add", seasonal=None)
            else:
                model = ExponentialSmoothing(ts, trend="add", seasonal="add", seasonal_periods=12)
                
            res = model.fit()
            fc = res.forecast(steps=forecast_steps)
            fc.index = forecast_index
        except Exception:
            # Fallback to simple ARIMA(1, 1, 1) or mean if Holt-Winters fails
            try:
                model = SARIMAX(ts, order=(1, 1, 1), enforce_stationarity=False, enforce_invertibility=False)
                res = model.fit(disp=False)
                fc = res.forecast(steps=forecast_steps)
                fc.index = forecast_index
            except Exception:
                fc = pd.Series(ts.mean(), index=forecast_index)
                
        # Bound non-negative features (e.g. events, rainfall, IDP cannot be negative)
        if col in ["rain_1m", "rain_3m", "acled_events", "acled_fatalities", "idp_population", "wfp_price_mean"]:
            fc = fc.clip(lower=0)
            
        forecasted_predictors[col] = fc
        
        # Plot univariate forecast
        plt.figure(figsize=(12, 5))
        plt.plot(ts.loc["2020-01-01":], label="Historical Actual", color="black", linewidth=2)
        plt.plot(fc, label="Forecasted Future (12m)", color="red", linestyle="--", marker='o')
        plt.axvline(x=ts.index[-1], color="gray", linestyle=":")
        plt.title(f"Univariate Forecast: {col} - Kabul", fontsize=12)
        plt.ylabel(col)
        plt.legend(loc="upper left")
        
        fig_name = plots_dir / f"univariate_{col}.png"
        plt.savefig(fig_name, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  Saved forecast plot for {col} to {fig_name.name}")
        
    # -------------------------------------------------------------------------
    # 3. STAGE 2: MULTIVARIATE IPC PREDICTION AND TIMELINE FORECAST
    # -------------------------------------------------------------------------
    print("\nStage 2: Training multivariate Random Forest and projecting future IPC...")
    
    X = joined[predictors]
    y = joined["ipc_phase_3plus_pct"]
    
    # Train Random Forest on historical monthly data
    rf = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
    rf.fit(X, y)
    
    # Predict on historical data to see the fit
    joined["predicted_ipc"] = rf.predict(X)
    
    # Predict on future forecasted predictors
    future_pred = rf.predict(forecasted_predictors[predictors])
    df_future = pd.DataFrame(index=forecast_index)
    df_future["predicted_ipc"] = future_pred
    
    # Plot historical vs. predicted timeline, including the future forecast
    plt.figure(figsize=(14, 6))
    
    # Plot actual historical IPC
    plt.plot(joined.index, joined["ipc_phase_3plus_pct"], label="Actual IPC Phase 3+ %", color="black", marker="o", linewidth=2.5)
    # Plot fitted historical IPC
    plt.plot(joined.index, joined["predicted_ipc"], label="Model Fitted IPC % (Random Forest)", color="blue", linestyle="--", linewidth=1.5)
    # Plot forecasted future IPC
    plt.plot(df_future.index, df_future["predicted_ipc"], label="Projected Future IPC % (12m ahead)", color="red", linestyle="-.", marker="s", linewidth=2)
    
    plt.axvline(x=joined.index[-1], color="gray", linestyle=":", linewidth=2, label="Forecast Horizon Start")
    plt.title("IPC Phase 3+ % Time Series Projection for Kabul (Stage 1 + Stage 2)", fontsize=14)
    plt.xlabel("Date")
    plt.ylabel("% Population in Phase 3+")
    plt.legend(loc="upper left")
    
    forecast_plot_path = plots_dir / "kabul_multivariate_ipc_forecast.png"
    plt.savefig(forecast_plot_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\nSaved final IPC forecast plot to {forecast_plot_path}")
    
    # Write doc.md explaining the whole pipeline
    doc_content = """# Documentazione Analisi Time Series Avanzata: Kabul (AF01)

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
* **IPC**: Espansione del valore di `phase_3plus_percentage` per coprire ciascun mese all'interno dell'intervallo `From` $\\rightarrow$ `To` del rispettivo record di validità `current`, seguito da forward-fill (`ffill()`).

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
"""
    
    with open(kabul_tsa_dir / "doc.md", "w", encoding="utf-8") as f:
        f.write(doc_content)
    print("Saved doc.md explaining the process.")
    
    # -------------------------------------------------------------------------
    # 4. GENERATE JUPYTER NOTEBOOK FOR KABUL TSA
    # -------------------------------------------------------------------------
    cells = []
    
    # Cell 1: Markdown Title
    cells.append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "# Analisi delle Serie Storiche e Pipeline a Due Stadi (Two-Stage Forecasting): Kabul\n",
            "\n",
            "Questo notebook contiene l'analisi dettagliata per la provincia di **Kabul (AF01)**:\n",
            "1. **Allineamento Multigranularità**: Come allineare dati WFP, Rainfall, ACLED, IDP e IPC a una frequenza mensile coerente.\n",
            "2. **Stage 1 (Univariate Forecast)**: Previsione univariata (Holt-Winters / SARIMAX) per ciascuno dei 9 predittori ambientali e socio-economici a 12 mesi nel futuro.\n",
            "3. **Stage 2 (Multivariate Project)**: Addestramento del modello Random Forest Regressor e proiezione dell'indice di insicurezza alimentare **IPC Phase 3+ %** futuro."
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
            "from statsmodels.tsa.statespace.sarimax import SARIMAX\n",
            "from statsmodels.tsa.holtwinters import ExponentialSmoothing\n",
            "from sklearn.ensemble import RandomForestRegressor\n",
            "from sklearn.metrics import mean_absolute_error, r2_score\n",
            "\n",
            "sns.set_theme(style=\"whitegrid\")\n",
            "plt.rcParams[\"figure.figsize\"] = (12, 6)\n",
            "plt.rcParams[\"axes.grid\"] = True\n",
            "os.makedirs(\"plots\", exist_ok=True)"
        ]
    })
    
    # Cell 3: Load raw data & Align
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "source": [
            "base = \"../../data\"\n",
            "wfp = pd.read_parquet(f\"{base}/tmp/wfp_monthly_adm1_index.parquet\", engine=\"pyarrow\")\n",
            "rain = pd.read_parquet(f\"{base}/raw/rainfall.parquet\", engine=\"pyarrow\")\n",
            "acled = pd.read_parquet(f\"{base}/raw/acled.parquet\", engine=\"pyarrow\")\n",
            "idp = pd.read_parquet(f\"{base}/raw/idp.parquet\", engine=\"pyarrow\")\n",
            "merged = pd.read_parquet(f\"{base}/merged/merged_adm1_wide.parquet\", engine=\"pyarrow\")\n",
            "\n",
            "# 1. WFP Kabul\n",
            "wfp_k = wfp[(wfp[\"ISO3\"] == \"AFG\") & (wfp[\"adm1_pcode\"] == \"AF01\")].copy()\n",
            "wfp_k[\"date\"] = pd.to_datetime(wfp_k[\"date\"])\n",
            "wfp_k = wfp_k.set_index(\"date\").sort_index()[[\"wfp_price_mean\", \"wfp_inflation_mean\"]].asfreq(\"MS\")\n",
            "wfp_k = wfp_k.interpolate(method=\"linear\")\n",
            "\n",
            "# 2. Rainfall Kabul\n",
            "rain_k = rain[rain[\"PCODE\"] == \"AF01\"].copy()\n",
            "rain_k[\"date\"] = pd.to_datetime(rain_k[\"date\"]).dt.to_period(\"M\").dt.to_timestamp()\n",
            "rain_k = rain_k.groupby(\"date\")[[\"rain_1m\", \"rain_3m\", \"rain_anomaly_1m\", \"rain_anomaly_3m\"]].mean().asfreq(\"MS\")\n",
            "\n",
            "# 3. ACLED Kabul\n",
            "acled_k = acled[acled[\"admin1_code\"] == \"AF01\"].copy()\n",
            "acled_k[\"date\"] = pd.to_datetime(acled_k[\"reference_period_start\"]).dt.to_period(\"M\").dt.to_timestamp()\n",
            "acled_k = acled_k.groupby(\"date\")[[\"events\", \"fatalities\"]].sum().rename(\n",
            "    columns={\"events\": \"acled_events\", \"fatalities\": \"acled_fatalities\"}\n",
            ").asfreq(\"MS\", fill_value=0)\n",
            "\n",
            "# 4. IDP Kabul\n",
            "idp_k = idp[idp[\"admin1_code\"] == \"AF01\"].copy()\n",
            "idp_k[\"date\"] = pd.to_datetime(idp_k[\"reference_period_start\"]).dt.to_period(\"M\").dt.to_timestamp()\n",
            "idp_k = idp_k.groupby(\"date\")[[\"population\"]].mean().rename(\n",
            "    columns={\"population\": \"idp_population\"}\n",
            ").asfreq(\"MS\").ffill().fillna(0)\n",
            "\n",
            "# 5. IPC Kabul\n",
            "ipc_k = merged[(merged[\"adm1_pcode\"] == \"AF01\") & (merged[\"Validity period\"] == \"current\")].copy()\n",
            "expanded = []\n",
            "for _, row in ipc_k.iterrows():\n",
            "    m_range = pd.date_range(start=row[\"From\"], end=row[\"To\"], freq=\"MS\")\n",
            "    for m in m_range:\n",
            "        expanded.append({\"date\": m, \"ipc_phase_3plus_pct\": row[\"phase_3plus_percentage\"]})\n",
            "df_ipc = pd.DataFrame(expanded).drop_duplicates(subset=[\"date\"]).set_index(\"date\").sort_index().asfreq(\"MS\")\n",
            "df_ipc_filled = df_ipc.ffill().bfill()\n",
            "\n",
            "# Join\n",
            "joined = wfp_k.join([rain_k, acled_k, idp_k, df_ipc_filled], how=\"inner\")\n",
            "print(f\"Joined Shape: {joined.shape}\")\n",
            "print(joined.head(5))"
        ]
    })
    
    # Cell 4: Explain Stage 1
    cells.append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "### Stage 1: Univariate Forecasting dei Predittori\n",
            "Prevediamo in avanti di 12 mesi ciascuna variabile indipendente per poter simulare lo scenario futuro di Kabul."
        ]
    })
    
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "source": [
            "predictors = [\n",
            "    \"wfp_price_mean\", \"wfp_inflation_mean\", \n",
            "    \"rain_1m\", \"rain_3m\", \"rain_anomaly_1m\", \"rain_anomaly_3m\", \n",
            "    \"acled_events\", \"acled_fatalities\", \n",
            "    \"idp_population\"\n",
            "]\n",
            "\n",
            "forecast_steps = 12\n",
            "forecast_index = pd.date_range(start=joined.index[-1] + pd.DateOffset(months=1), periods=forecast_steps, freq=\"MS\")\n",
            "forecasted_predictors = pd.DataFrame(index=forecast_index)\n",
            "\n",
            "for col in predictors:\n",
            "    ts = joined[col]\n",
            "    try:\n",
            "        if col in [\"acled_events\", \"acled_fatalities\", \"idp_population\"]:\n",
            "            model = ExponentialSmoothing(ts, trend=\"add\", seasonal=None)\n",
            "        else:\n",
            "            model = ExponentialSmoothing(ts, trend=\"add\", seasonal=\"add\", seasonal_periods=12)\n",
            "        res = model.fit()\n",
            "        fc = res.forecast(steps=forecast_steps)\n",
            "    except Exception:\n",
            "        model = SARIMAX(ts, order=(1, 1, 1), enforce_stationarity=False, enforce_invertibility=False)\n",
            "        res = model.fit(disp=False)\n",
            "        fc = res.forecast(steps=forecast_steps)\n",
            "        \n",
            "    # Vincolo non-negatività\n",
            "    if col in [\"rain_1m\", \"rain_3m\", \"acled_events\", \"acled_fatalities\", \"idp_population\", \"wfp_price_mean\"]:\n",
            "        fc = fc.clip(lower=0)\n",
            "        \n",
            "    forecasted_predictors[col] = fc\n",
            "    \n",
            "    # Plot\n",
            "    plt.figure(figsize=(12, 4))\n",
            "    plt.plot(ts.loc[\"2020-01-01\":], label=\"Storico Reale\", color=\"black\", linewidth=2)\n",
            "    plt.plot(fc, label=\"Forecast Future (12m)\", color=\"red\", linestyle=\"--\", marker='o')\n",
            "    plt.axvline(x=ts.index[-1], color=\"gray\", linestyle=\":\")\n",
            "    plt.title(f\"Univariate Forecast: {col} - Kabul\")\n",
            "    plt.legend(loc=\"upper left\")\n",
            "    plt.savefig(f\"plots/univariate_{col}.png\", dpi=150, bbox_inches=\"tight\")\n",
            "    plt.show()"
        ]
    })
    
    # Cell 5: Explain Stage 2
    cells.append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "### Stage 2: Proiezione Multivariata dell'IPC\n",
            "Addestriamo il Random Forest Regressor e utilizziamo le feature stimate dallo Stage 1 per proiettare l'andamento futuro dell'insicurezza alimentare a Kabul."
        ]
    })
    
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "source": [
            "X = joined[predictors]\n",
            "y = joined[\"ipc_phase_3plus_pct\"]\n",
            "\n",
            "rf = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)\n",
            "rf.fit(X, y)\n",
            "\n",
            "# Predizioni storiche e future\n",
            "joined[\"predicted_ipc\"] = rf.predict(X)\n",
            "future_pred = rf.predict(forecasted_predictors[predictors])\n",
            "df_future = pd.DataFrame(index=forecast_index)\n",
            "df_future[\"predicted_ipc\"] = future_pred\n",
            "\n",
            "# Plot Finale\n",
            "plt.figure(figsize=(14, 6))\n",
            "plt.plot(joined.index, joined[\"ipc_phase_3plus_pct\"], label=\"Actual IPC Phase 3+ %\", color=\"black\", marker=\"o\", linewidth=2.5)\n",
            "plt.plot(joined.index, joined[\"predicted_ipc\"], label=\"Fitted IPC % (Random Forest)\", color=\"blue\", linestyle=\"--\", linewidth=1.5)\n",
            "plt.plot(df_future.index, df_future[\"predicted_ipc\"], label=\"Projected Future IPC % (12m ahead)\", color=\"red\", linestyle=\"-.\", marker=\"s\", linewidth=2)\n",
            "plt.axvline(x=joined.index[-1], color=\"gray\", linestyle=\":\", linewidth=2, label=\"Inizio Forecast\")\n",
            "plt.title(\"Proiezione dell'Indice IPC Phase 3+ % per Kabul (Two-Stage Forecasting)\", fontsize=14)\n",
            "plt.xlabel(\"Data\")\n",
            "plt.ylabel(\"% Popolazione in Phase 3+\")\n",
            "plt.legend(loc=\"upper left\")\n",
            "plt.savefig(\"plots/kabul_multivariate_ipc_forecast.png\", dpi=150, bbox_inches=\"tight\")\n",
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
    
    output_path = kabul_tsa_dir / "kabul_tsa_analysis.ipynb"
    print(f"Writing notebook to {output_path}...")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(notebook, f, indent=2, ensure_ascii=False)
    print("Notebook created successfully!")

if __name__ == "__main__":
    main()
