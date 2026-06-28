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
from sklearn.model_selection import train_test_split
from sklearn.impute import SimpleImputer
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# Set plot style
sns.set_theme(style="whitegrid")
plt.rcParams["figure.figsize"] = (12, 6)
plt.rcParams["axes.grid"] = True

def main():
    base_dir = Path("c:/Dev/Progetti/HERO/hero_v6")
    tsa_dir = base_dir / "TSA"
    plots_dir = tsa_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)
    
    wfp_data_path = base_dir / "data" / "tmp" / "wfp_monthly_adm1_index.parquet"
    merged_data_path = base_dir / "data" / "merged" / "merged_adm1_wide.parquet"
    
    print("Loading datasets...")
    df_wfp = pd.read_parquet(wfp_data_path, engine="pyarrow")
    df_wfp['date'] = pd.to_datetime(df_wfp['date'])
    
    df_merged = pd.read_parquet(merged_data_path, engine="pyarrow")
    
    # -------------------------------------------------------------------------
    # 1. UNIVARIATE ANALYSIS ON 3 SELECTED COUNTRIES
    # -------------------------------------------------------------------------
    ts_configs = [
        {"ISO3": "AFG", "pcode": "AF01", "name": "Kabul"},
        {"ISO3": "SOM", "pcode": "SO11", "name": "Awdal"},
        {"ISO3": "KEN", "pcode": "KE023", "name": "Rift Valley"}
    ]
    
    # Try importing Prophet
    try:
        from prophet import Prophet
        import logging
        logging.getLogger('prophet').setLevel(logging.WARNING)
        prophet_installed = True
        print("Prophet is installed.")
    except ImportError:
        prophet_installed = False
        print("Prophet is not installed.")
        
    for config in ts_configs:
        iso = config["ISO3"]
        pcode = config["pcode"]
        name = config["name"]
        
        print(f"Processing Univariate TSA for {iso} - {name} ({pcode})...")
        series_df = df_wfp[(df_wfp["ISO3"] == iso) & (df_wfp["adm1_pcode"] == pcode)].copy()
        series_df = series_df.set_index("date").sort_index()
        series_df = series_df.asfreq("MS")
        
        if series_df["wfp_price_mean"].isna().any():
            series_df["wfp_price_mean"] = series_df["wfp_price_mean"].interpolate(method="linear")
            
        ts = series_df["wfp_price_mean"]
        train = ts.iloc[:-12]
        test = ts.iloc[-12:]
        forecast_steps = 24
        forecast_index = pd.date_range(start=test.index[0], periods=forecast_steps, freq="MS")
        
        # SARIMAX
        try:
            sarimax_model = SARIMAX(train, order=(1, 1, 1), seasonal_order=(1, 1, 1, 12),
                                    enforce_stationarity=False, enforce_invertibility=False)
            sarimax_res = sarimax_model.fit(disp=False)
            sarimax_forecast_obj = sarimax_res.get_forecast(steps=forecast_steps)
            sarimax_forecast = sarimax_forecast_obj.predicted_mean
            sarimax_forecast.index = forecast_index
            sarimax_ci = sarimax_forecast_obj.conf_int(alpha=0.05)
            sarimax_ci.index = forecast_index
        except Exception:
            sarimax_forecast = pd.Series(np.nan, index=forecast_index)
            sarimax_ci = pd.DataFrame(np.nan, index=forecast_index, columns=["lower wfp_price_mean", "upper wfp_price_mean"])
            
        # Holt-Winters
        try:
            hw_model = ExponentialSmoothing(train, trend="add", seasonal="add", seasonal_periods=12)
            hw_res = hw_model.fit()
            hw_forecast = hw_res.forecast(steps=forecast_steps)
            hw_forecast.index = forecast_index
        except Exception:
            hw_forecast = pd.Series(np.nan, index=forecast_index)
            
        # Prophet
        prophet_forecast = pd.Series(np.nan, index=forecast_index)
        if prophet_installed:
            try:
                prophet_train = train.reset_index().rename(columns={"date": "ds", "wfp_price_mean": "y"})
                m = Prophet(yearly_seasonality=True, weekly_seasonality=False, daily_seasonality=False)
                m.fit(prophet_train)
                future = m.make_future_dataframe(periods=forecast_steps, freq="MS")
                forecast_prophet_df = m.predict(future)
                prophet_forecast = forecast_prophet_df.set_index("ds").loc[test.index[0]:, "yhat"].iloc[:forecast_steps]
                prophet_forecast.index = forecast_index
            except Exception:
                pass
                
        # Plot
        plt.figure(figsize=(14, 6))
        plt.plot(ts.loc["2020-01-01":], label="Real Data", color="black", linewidth=2.5)
        if not sarimax_forecast.isna().all():
            plt.plot(sarimax_forecast, label="SARIMAX Forecast", color="#1f77b4", linestyle="--")
            plt.fill_between(sarimax_ci.index, sarimax_ci.iloc[:, 0], sarimax_ci.iloc[:, 1], color="#1f77b4", alpha=0.1)
        if not hw_forecast.isna().all():
            plt.plot(hw_forecast, label="Holt-Winters Forecast", color="green", linestyle="-.")
        if prophet_installed and not prophet_forecast.isna().all():
            plt.plot(prophet_forecast, label="Prophet Forecast", color="orange", linestyle=":")
            
        plt.axvline(x=test.index[0], color="red", linestyle=":", label="Test Start")
        plt.title(f"Univariate Forecast - WFP Price Index in {iso} ({name})", fontsize=14)
        plt.xlabel("Date")
        plt.ylabel("WFP Price Index")
        plt.legend(loc="upper left")
        
        plot_name = plots_dir / f"univariate_{iso.lower()}_{pcode.lower()}.png"
        plt.savefig(plot_name, dpi=150, bbox_inches="tight")
        plt.close()
        
    # -------------------------------------------------------------------------
    # 2. MULTIVARIATE ANALYSIS ON JOINED DATASET (AFG, SOM, KEN) - CURRENT VALIDITY
    # -------------------------------------------------------------------------
    print("\nProcessing Multivariate Machine Learning for IPC prediction (Current Validity period only)...")
    
    # Filter merged dataset for our 3 countries and 'current' validity period to avoid overlapping predictions
    target_countries = ["AFG", "SOM", "KEN"]
    df_ml = df_merged[
        df_merged["Country"].isin(target_countries) & 
        (df_merged["Validity period"] == "current")
    ].copy()
    
    target_col = "phase_3plus_percentage"
    feature_cols = [
        "acled_total_events", "acled_total_fatalities", 
        "idp_population", 
        "rain_1m", "rain_3m", "rain_anomaly_1m", "rain_anomaly_3m", 
        "wfp_price", "wfp_inflation"
    ]
    
    # Drop rows with null target
    df_ml = df_ml.dropna(subset=[target_col])
    
    X = df_ml[feature_cols].copy()
    y = df_ml[target_col]
    
    # Impute missing values
    X["acled_total_events"] = X["acled_total_events"].fillna(0)
    X["acled_total_fatalities"] = X["acled_total_fatalities"].fillna(0)
    X["idp_population"] = X["idp_population"].fillna(0)
    
    imputer = SimpleImputer(strategy="median")
    X_imputed = imputer.fit_transform(X)
    X_imputed_df = pd.DataFrame(X_imputed, columns=feature_cols)
    
    # Train-test split
    X_train, X_test, y_train, y_test = train_test_split(X_imputed_df, y, test_size=0.2, random_state=42)
    
    # Fit Random Forest
    rf = RandomForestRegressor(n_estimators=150, random_state=42, n_jobs=-1)
    rf.fit(X_train, y_train)
    y_pred_rf = rf.predict(X_test)
    
    # R2 scores
    rf_r2 = r2_score(y_test, y_pred_rf)
    print(f"Random Forest test R^2: {rf_r2:.3f}")
    
    # Predict on the ENTIRE df_ml dataset to obtain a continuous predicted timeline
    df_ml_imputed = imputer.transform(X.fillna({
        "acled_total_events": 0, "acled_total_fatalities": 0, "idp_population": 0
    }))
    df_ml["predicted_phase_3plus_percentage"] = rf.predict(df_ml_imputed)
    
    # Plot and save timeline prediction for the 3 target provinces
    fig, axes = plt.subplots(3, 1, figsize=(14, 15), sharex=False)
    
    for idx, config in enumerate(ts_configs):
        iso = config["ISO3"]
        pcode = config["pcode"]
        name = config["name"]
        ax = axes[idx]
        
        # Filter for this province
        prov_df = df_ml[df_ml["adm1_pcode"] == pcode].sort_values("From").copy()
        
        if len(prov_df) > 0:
            ax.plot(prov_df["From"], prov_df[target_col], marker='o', label="Actual IPC Phase 3+ %", color="black", linewidth=2.5)
            ax.plot(prov_df["From"], prov_df["predicted_phase_3plus_percentage"], marker='s', label="Predicted (Random Forest)", color="red", linestyle="--", linewidth=2)
            ax.set_title(f"IPC Phase 3+ % Timeline: Actual vs Predicted - {iso} ({name})", fontsize=12)
            ax.set_ylabel("Population %")
            ax.legend(loc="upper left")
        else:
            ax.text(0.5, 0.5, f"No data for {name} ({pcode})", transform=ax.transAxes, ha='center')
            
    plt.xlabel("Date / Time of Analysis")
    plt.tight_layout()
    
    timeline_plot_path = plots_dir / "multivariate_timeline_predictions.png"
    plt.savefig(timeline_plot_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved timeline predictions plot to {timeline_plot_path}")
    
    # Save standard plots as well
    # Feature Importance
    plt.figure(figsize=(10, 6))
    importances = rf.feature_importances_
    indices = np.argsort(importances)[::-1]
    sorted_features = [feature_cols[i] for i in indices]
    sorted_importances = importances[indices]
    sns.barplot(x=sorted_importances, y=sorted_features, palette="viridis")
    plt.title("Feature Importance - Random Forest (IPC Phase 3+ %)")
    plt.xlabel("Importance Score")
    
    fi_plot_path = plots_dir / "multivariate_feature_importance.png"
    plt.savefig(fi_plot_path, dpi=150, bbox_inches="tight")
    plt.close()
    
    # Predictions vs Actual
    plt.figure(figsize=(8, 8))
    plt.scatter(y_test, y_pred_rf, alpha=0.5, color="#1f77b4")
    plt.plot([y_test.min(), y_test.max()], [y_test.min(), y_test.max()], "r--", lw=2)
    plt.title(f"IPC Prediction - Random Forest (R^2: {rf_r2:.2f})")
    plt.xlabel("Actual Phase 3+ %")
    plt.ylabel("Predicted Phase 3+ %")
    
    pred_plot_path = plots_dir / "multivariate_predictions_vs_actual.png"
    plt.savefig(pred_plot_path, dpi=150, bbox_inches="tight")
    plt.close()
    
    print("Done generating plots.")

if __name__ == "__main__":
    main()
