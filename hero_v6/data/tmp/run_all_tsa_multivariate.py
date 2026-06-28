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
    # Time Series to process:
    # 1. AFG - Kabul (AF01)
    # 2. SOM - Awdal (SO11)
    # 3. KEN - Rift Valley (KE023)
    
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
        print("Prophet is installed and will be included in the comparison.")
    except ImportError:
        prophet_installed = False
        print("Prophet is not installed. Skipping Prophet in the execution (it will be try-excepted in the notebook).")
        
    for config in ts_configs:
        iso = config["ISO3"]
        pcode = config["pcode"]
        name = config["name"]
        
        print(f"\nProcessing Univariate TSA for {iso} - {name} ({pcode})...")
        
        # Filter series
        series_df = df_wfp[(df_wfp["ISO3"] == iso) & (df_wfp["adm1_pcode"] == pcode)].copy()
        series_df = series_df.set_index("date").sort_index()
        series_df = series_df.asfreq("MS")
        
        # Interpolate NaNs if any
        if series_df["wfp_price_mean"].isna().any():
            series_df["wfp_price_mean"] = series_df["wfp_price_mean"].interpolate(method="linear")
            
        ts = series_df["wfp_price_mean"]
        
        # Train-Test Split (last 12 months as test)
        train = ts.iloc[:-12]
        test = ts.iloc[-12:]
        forecast_steps = 24
        forecast_index = pd.date_range(start=test.index[0], periods=forecast_steps, freq="MS")
        
        # Fit SARIMAX
        print("  Fitting SARIMAX...")
        try:
            sarimax_model = SARIMAX(train, order=(1, 1, 1), seasonal_order=(1, 1, 1, 12),
                                    enforce_stationarity=False, enforce_invertibility=False)
            sarimax_res = sarimax_model.fit(disp=False)
            sarimax_forecast_obj = sarimax_res.get_forecast(steps=forecast_steps)
            sarimax_forecast = sarimax_forecast_obj.predicted_mean
            sarimax_forecast.index = forecast_index
            sarimax_ci = sarimax_forecast_obj.conf_int(alpha=0.05)
            sarimax_ci.index = forecast_index
        except Exception as e:
            print(f"  SARIMAX fitting failed: {e}")
            sarimax_forecast = pd.Series(np.nan, index=forecast_index)
            sarimax_ci = pd.DataFrame(np.nan, index=forecast_index, columns=["lower wfp_price_mean", "upper wfp_price_mean"])
            
        # Fit Holt-Winters
        print("  Fitting Holt-Winters...")
        try:
            hw_model = ExponentialSmoothing(train, trend="add", seasonal="add", seasonal_periods=12)
            hw_res = hw_model.fit()
            hw_forecast = hw_res.forecast(steps=forecast_steps)
            hw_forecast.index = forecast_index
        except Exception as e:
            print(f"  Holt-Winters fitting failed: {e}")
            hw_forecast = pd.Series(np.nan, index=forecast_index)
            
        # Fit Prophet
        prophet_forecast = pd.Series(np.nan, index=forecast_index)
        if prophet_installed:
            print("  Fitting Prophet...")
            try:
                prophet_train = train.reset_index().rename(columns={"date": "ds", "wfp_price_mean": "y"})
                m = Prophet(yearly_seasonality=True, weekly_seasonality=False, daily_seasonality=False)
                m.fit(prophet_train)
                future = m.make_future_dataframe(periods=forecast_steps, freq="MS")
                forecast_prophet_df = m.predict(future)
                prophet_forecast = forecast_prophet_df.set_index("ds").loc[test.index[0]:, "yhat"].iloc[:forecast_steps]
                prophet_forecast.index = forecast_index
            except Exception as e:
                print(f"  Prophet fitting failed: {e}")
                
        # Plot and save univariate comparison
        plt.figure(figsize=(14, 6))
        plt.plot(ts.loc["2020-01-01":], label="Real Data (Historical + Test)", color="black", linewidth=2.5)
        
        if not sarimax_forecast.isna().all():
            plt.plot(sarimax_forecast, label="SARIMAX Forecast", color="#1f77b4", linestyle="--", linewidth=1.8)
            plt.fill_between(sarimax_ci.index, sarimax_ci.iloc[:, 0], sarimax_ci.iloc[:, 1], color="#1f77b4", alpha=0.1)
            
        if not hw_forecast.isna().all():
            plt.plot(hw_forecast, label="Holt-Winters Forecast", color="green", linestyle="-.", linewidth=1.8)
            
        if prophet_installed and not prophet_forecast.isna().all():
            plt.plot(prophet_forecast, label="Prophet Forecast", color="orange", linestyle=":", linewidth=2)
            
        plt.axvline(x=test.index[0], color="red", linestyle=":", linewidth=1.5, label="Test Start")
        plt.title(f"Univariate Forecast - WFP Price Index in {iso} ({name})", fontsize=14)
        plt.xlabel("Date", fontsize=12)
        plt.ylabel("WFP Price Index", fontsize=12)
        plt.legend(loc="upper left")
        
        plot_name = plots_dir / f"univariate_{iso.lower()}_{pcode.lower()}.png"
        plt.savefig(plot_name, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  Saved univariate plot to {plot_name}")
        
    # -------------------------------------------------------------------------
    # 2. MULTIVARIATE ANALYSIS ON JOINED DATASET (AFG, SOM, KEN)
    # -------------------------------------------------------------------------
    print("\nProcessing Multivariate Machine Learning for IPC prediction...")
    
    # Filter merged dataset for our 3 countries
    target_countries = ["AFG", "SOM", "KEN"]
    df_ml = df_merged[df_merged["Country"].isin(target_countries)].copy()
    
    # Select target and features
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
    
    # Handle NaNs:
    # 1. ACLED and IDP are filled with 0 (since missing events/displacements means zero occurred)
    X["acled_total_events"] = X["acled_total_events"].fillna(0)
    X["acled_total_fatalities"] = X["acled_total_fatalities"].fillna(0)
    X["idp_population"] = X["idp_population"].fillna(0)
    
    # 2. Rain and WFP are imputed using SimpleImputer (strategy='median')
    imputer = SimpleImputer(strategy="median")
    X_imputed = imputer.fit_transform(X)
    X_imputed_df = pd.DataFrame(X_imputed, columns=feature_cols)
    
    # Train-test split
    X_train, X_test, y_train, y_test = train_test_split(X_imputed_df, y, test_size=0.2, random_state=42)
    
    # Fit Random Forest Regressor
    print("  Fitting Random Forest Regressor...")
    rf = RandomForestRegressor(n_estimators=150, random_state=42, n_jobs=-1)
    rf.fit(X_train, y_train)
    y_pred_rf = rf.predict(X_test)
    
    # Fit Ridge Regressor (linear benchmark)
    print("  Fitting Ridge Regressor...")
    ridge = Ridge()
    ridge.fit(X_train, y_train)
    y_pred_ridge = ridge.predict(X_test)
    
    # Evaluate
    print("\nEvaluation Metrics (Random Forest):")
    rf_mae = mean_absolute_error(y_test, y_pred_rf)
    rf_rmse = np.sqrt(mean_squared_error(y_test, y_pred_rf))
    rf_r2 = r2_score(y_test, y_pred_rf)
    print(f"  MAE: {rf_mae:.3f}% | RMSE: {rf_rmse:.3f}% | R^2: {rf_r2:.3f}")
    
    print("\nEvaluation Metrics (Ridge Regression):")
    ridge_mae = mean_absolute_error(y_test, y_pred_ridge)
    ridge_rmse = np.sqrt(mean_squared_error(y_test, y_pred_ridge))
    ridge_r2 = r2_score(y_test, y_pred_ridge)
    print(f"  MAE: {ridge_mae:.3f}% | RMSE: {ridge_rmse:.3f}% | R^2: {ridge_r2:.3f}")
    
    # Plot Feature Importances
    plt.figure(figsize=(10, 6))
    importances = rf.feature_importances_
    indices = np.argsort(importances)[::-1]
    sorted_features = [feature_cols[i] for i in indices]
    sorted_importances = importances[indices]
    
    sns.barplot(x=sorted_importances, y=sorted_features, palette="viridis")
    plt.title("Feature Importance - Random Forest (IPC Phase 3+ % Prediction)")
    plt.xlabel("Importance Score")
    plt.ylabel("Features")
    
    fi_plot_path = plots_dir / "multivariate_feature_importance.png"
    plt.savefig(fi_plot_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved feature importance plot to {fi_plot_path}")
    
    # Plot Predictions vs Actuals
    plt.figure(figsize=(8, 8))
    plt.scatter(y_test, y_pred_rf, alpha=0.5, color="#1f77b4", label="Predicted vs Actual")
    plt.plot([y_test.min(), y_test.max()], [y_test.min(), y_test.max()], "r--", lw=2, label="Ideal Line (Perfect Prediction)")
    plt.title(f"IPC Prediction - Random Forest (R^2: {rf_r2:.2f})", fontsize=14)
    plt.xlabel("Actual Phase 3+ Percentage", fontsize=12)
    plt.ylabel("Predicted Phase 3+ Percentage", fontsize=12)
    plt.legend()
    
    pred_plot_path = plots_dir / "multivariate_predictions_vs_actual.png"
    plt.savefig(pred_plot_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved predictions vs actuals plot to {pred_plot_path}")
    
    print("\nSuccessfully ran all python code and saved the plots.")

if __name__ == "__main__":
    main()
