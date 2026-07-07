import os
import pandas as pd
import numpy as np
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.stats.diagnostic import acorr_ljungbox
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from preprocessing.causality import fit_var_forecast

# Optional Prophet import
try:
    from prophet import Prophet
    import logging
    logging.getLogger('prophet').setLevel(logging.WARNING)
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False

def run_ljung_box_test(residuals):
    """
    Runs the Ljung-Box test for white noise.
    Returns the p-value at the first robust lag.
    """
    clean_res = pd.Series(residuals).dropna()
    if len(clean_res) < 5:
        return 1.0 # default to white noise if series is too short
    try:
        # standard lag selection: min(10, N/2 - 1)
        lag_val = min(10, len(clean_res) // 2 - 1)
        if lag_val < 1:
            lag_val = 1
        lb_res = acorr_ljungbox(clean_res, lags=[lag_val], return_df=True)
        return float(lb_res["lb_pvalue"].iloc[0])
    except Exception:
        return 0.0

def train_and_compare_forecasting_models(df_imputed, predictors, target_col, forecast_steps=12, use_prophet=True, save_dir=None):
    """
    Trains and compares multiple univariate/multivariate forecasting strategies:
    1. Holt-Winters (Exponential Smoothing)
    2. SARIMAX (automatically optimized using AIC/BIC grid evaluation)
    3. Prophet (if available)
    4. VAR (Vector AutoRegressive)
    
    Splits history into train (all but last 12 months) and test (last 12 months).
    Calculates MAE, RMSE, and Ljung-Box p-values on residuals.
    Returns forecasts, fit metrics, residuals, and the best model.
    """
    ts_all = df_imputed[target_col].copy()
    
    # Train-test split (test = last 12 months)
    test_len = 12
    ts_train = ts_all.iloc[:-test_len]
    ts_test = ts_all.iloc[-test_len:]
    
    forecast_index = ts_test.index
    
    model_predictions = {}
    model_residuals = {}
    metrics_rows = []
    
    # 1. Holt-Winters
    try:
        hw_model = ExponentialSmoothing(ts_train, trend="add", seasonal="add", seasonal_periods=12)
        hw_res = hw_model.fit()
        hw_fc = hw_res.forecast(steps=test_len)
        hw_resid = ts_train - hw_res.fittedvalues
        
        hw_mae = mean_absolute_error(ts_test, hw_fc)
        hw_rmse = np.sqrt(mean_squared_error(ts_test, hw_fc))
        hw_r2 = r2_score(ts_test, np.clip(hw_fc, 0.0, 100.0))
        hw_lb_pval = run_ljung_box_test(hw_resid)
        
        model_predictions["Holt-Winters"] = hw_fc
        model_residuals["Holt-Winters"] = hw_resid
        metrics_rows.append({
            "Model": "Holt-Winters", "MAE": hw_mae, "RMSE": hw_rmse, "R2": hw_r2, "Ljung-Box p-val": hw_lb_pval
        })
    except Exception as e:
        print(f"Holt-Winters comparison failed: {e}")
        
    # 2. SARIMAX
    try:
        # Define candidate orders
        candidates = [
            {"order": (1, 0, 1), "seasonal": (0, 0, 0, 0)},
            {"order": (1, 1, 1), "seasonal": (0, 0, 0, 0)},
            {"order": (1, 1, 1), "seasonal": (1, 0, 0, 12)},
            {"order": (1, 1, 1), "seasonal": (1, 1, 1, 12)},
            {"order": (2, 1, 1), "seasonal": (1, 1, 1, 12)},
            {"order": (1, 1, 2), "seasonal": (1, 1, 1, 12)},
        ]
        
        eval_results = []
        best_sarima_res = None
        best_aic = float("inf")
        best_order = (1, 1, 1)
        best_seasonal = (1, 1, 1, 12)
        
        for cand in candidates:
            try:
                model_c = SARIMAX(
                    ts_train, 
                    order=cand["order"], 
                    seasonal_order=cand["seasonal"], 
                    enforce_stationarity=False, 
                    enforce_invertibility=False
                )
                res_c = model_c.fit(disp=False)
                aic_val = float(res_c.aic)
                bic_val = float(res_c.bic)
                
                label_str = f"ARIMA{cand['order']}x{cand['seasonal']}"
                eval_results.append({
                    "label": label_str,
                    "order": str(cand["order"]),
                    "seasonal": str(cand["seasonal"]),
                    "aic": aic_val,
                    "bic": bic_val
                })
                
                if aic_val < best_aic:
                    best_aic = aic_val
                    best_sarima_res = res_c
                    best_order = cand["order"]
                    best_seasonal = cand["seasonal"]
            except Exception as ex_c:
                pass
                
        # Save AIC/BIC evaluation
        if eval_results and save_dir:
            df_eval = pd.DataFrame(eval_results)
            df_eval.to_csv(os.path.join(save_dir, "05b_SARIMAX_AIC_BIC_Evaluation.csv"), index=False)
            
            # Plot
            try:
                import matplotlib.pyplot as plt
                fig, ax = plt.subplots(figsize=(10, 6))
                x_idx = np.arange(len(df_eval))
                width = 0.35
                ax.bar(x_idx - width/2, df_eval["aic"], width, label='AIC', color='#1f77b4')
                ax.bar(x_idx + width/2, df_eval["bic"], width, label='BIC', color='#ff7f0e')
                ax.set_title("SARIMAX Parameter Evaluation (AIC vs BIC)", fontsize=12)
                ax.set_xticks(x_idx)
                ax.set_xticklabels(df_eval["label"], rotation=30, ha="right", fontsize=8)
                ax.set_ylabel("Value")
                ax.legend()
                ax.grid(True, linestyle=":", alpha=0.6)
                plt.tight_layout()
                plt.savefig(os.path.join(save_dir, "05b_SARIMAX_AIC_BIC_Evaluation.png"), dpi=120)
                plt.close()
            except Exception as ex_plot:
                print(f"Error plotting SARIMAX AIC/BIC comparison: {ex_plot}")
                
        # Fit optimal model on train set
        if best_sarima_res is None:
            sarima_model = SARIMAX(ts_train, order=(1, 1, 1), seasonal_order=(1, 1, 1, 12), enforce_stationarity=False, enforce_invertibility=False)
            best_sarima_res = sarima_model.fit(disp=False)
            best_order = (1, 1, 1)
            best_seasonal = (1, 1, 1, 12)
            
        sarima_fc = best_sarima_res.forecast(steps=test_len)
        sarima_resid = ts_train - best_sarima_res.fittedvalues
        
        sarima_mae = mean_absolute_error(ts_test, sarima_fc)
        sarima_rmse = np.sqrt(mean_squared_error(ts_test, sarima_fc))
        sarima_r2 = r2_score(ts_test, np.clip(sarima_fc, 0.0, 100.0))
        sarima_lb_pval = run_ljung_box_test(sarima_resid)
        
        model_predictions["SARIMAX"] = sarima_fc
        model_residuals["SARIMAX"] = sarima_resid
        metrics_rows.append({
            "Model": f"SARIMAX {best_order}x{best_seasonal}", 
            "MAE": sarima_mae, 
            "RMSE": sarima_rmse, 
            "R2": sarima_r2, 
            "Ljung-Box p-val": sarima_lb_pval
        })
        print(f"SARIMAX optimal parameters: order={best_order}, seasonal={best_seasonal} (AIC={best_aic:.2f})")
    except Exception as e:
        print(f"SARIMAX comparison failed: {e}")

    # 3. Prophet
    if PROPHET_AVAILABLE and use_prophet:
        try:
            prophet_train = ts_train.reset_index().rename(columns={"date": "ds", target_col: "y"})
            m = Prophet(yearly_seasonality=True, weekly_seasonality=False, daily_seasonality=False)
            m.fit(prophet_train)
            future = m.make_future_dataframe(periods=test_len, freq="MS")
            forecast_prophet_df = m.predict(future)
            
            prophet_fc = forecast_prophet_df.set_index("ds").loc[ts_test.index, "yhat"]
            # Residuals on train
            fitted = forecast_prophet_df.set_index("ds").loc[ts_train.index, "yhat"]
            prophet_resid = ts_train - fitted
            
            prophet_mae = mean_absolute_error(ts_test, prophet_fc)
            prophet_rmse = np.sqrt(mean_squared_error(ts_test, prophet_fc))
            prophet_r2 = r2_score(ts_test, np.clip(prophet_fc, 0.0, 100.0))
            prophet_lb_pval = run_ljung_box_test(prophet_resid)
            
            model_predictions["Prophet"] = prophet_fc
            model_residuals["Prophet"] = prophet_resid
            metrics_rows.append({
                "Model": "Prophet", "MAE": prophet_mae, "RMSE": prophet_rmse, "R2": prophet_r2, "Ljung-Box p-val": prophet_lb_pval
            })
        except Exception as e:
            print(f"Prophet comparison failed: {e}")
            
    # 4. VAR (Vector AutoRegressive)
    try:
        # Fit VAR on train set for all predictors + target
        var_cols = [target_col] + [p for p in predictors if p in df_imputed.columns]
        df_train_var = df_imputed[var_cols].iloc[:-test_len]
        
        var_fc_series, var_lb_pval, var_resid = fit_var_forecast(
            df_imputed.iloc[:-test_len], 
            columns=var_cols, 
            target_col=target_col, 
            steps=test_len, 
            maxlags=3
        )
        
        var_mae = mean_absolute_error(ts_test, var_fc_series)
        var_rmse = np.sqrt(mean_squared_error(ts_test, var_fc_series))
        var_r2 = r2_score(ts_test, np.clip(var_fc_series, 0.0, 100.0))
        
        model_predictions["VAR"] = var_fc_series
        model_residuals["VAR"] = var_resid
        metrics_rows.append({
            "Model": "VAR", "MAE": var_mae, "RMSE": var_rmse, "R2": var_r2, "Ljung-Box p-val": var_lb_pval
        })
    except Exception as e:
        print(f"VAR comparison failed: {e}")
        
    df_metrics = pd.DataFrame(metrics_rows)
    
    # Clip all forecasts to be between 0 and 100%
    for key in model_predictions:
        model_predictions[key] = np.clip(model_predictions[key], 0.0, 100.0)
        
    # Choose best model (lowest MAE)
    best_model_name = "SARIMAX"
    if not df_metrics.empty:
        best_idx = df_metrics["MAE"].idxmin()
        best_model_name = df_metrics.loc[best_idx, "Model"]
        
    return model_predictions, df_metrics, model_residuals, best_model_name

# Maintain stage 1/stage 2 functions for compatibility
def forecast_univariate_variable(series, steps=12, variable_name=None):
    """
    Fits Exponential Smoothing or SARIMAX and forecasts future values.
    """
    ts = series.copy()
    forecast_index = pd.date_range(start=ts.index[-1] + pd.DateOffset(months=1), periods=steps, freq="MS")
    is_irregular = False
    if variable_name:
        is_irregular = any(keyword in variable_name.lower() for keyword in ["acled", "conflict", "event", "fatalities", "idp", "population"])
        
    forecast = None
    try:
        if is_irregular:
            model = ExponentialSmoothing(ts, trend="add", seasonal=None)
        else:
            model = ExponentialSmoothing(ts, trend="add", seasonal="add", seasonal_periods=12)
        res = model.fit()
        forecast = res.forecast(steps=steps)
    except Exception:
        pass
        
    if forecast is None:
        try:
            if is_irregular:
                model = SARIMAX(ts, order=(1, 1, 1), enforce_stationarity=False, enforce_invertibility=False)
            else:
                model = SARIMAX(ts, order=(1, 1, 1), seasonal_order=(1, 1, 1, 12), enforce_stationarity=False, enforce_invertibility=False)
            res = model.fit(disp=False)
            forecast = res.forecast(steps=steps)
        except Exception:
            pass
            
    if forecast is None:
        forecast = pd.Series(ts.mean(), index=forecast_index)
        
    if variable_name:
        non_negative_cols = ["wfp_price", "price", "rain", "acled", "conflict", "fatalities", "idp", "population"]
        if any(keyword in variable_name.lower() for keyword in non_negative_cols):
            forecast = forecast.clip(lower=0)
            
    forecast.index = forecast_index
    return forecast

def train_and_project_ipc(joined_df, forecasted_predictors_df, predictors):
    """
    Stage 2: Trains a Random Forest Regressor and a Ridge Regressor on historical aligned data.
    Then, projects the future IPC Phase 3+ % using the forecasted predictors.
    """
    X = joined_df[predictors].copy().ffill().bfill().fillna(0.0)
    y = joined_df["ipc_phase_3plus_pct"]
    
    rf_model = RandomForestRegressor(n_estimators=150, random_state=42, n_jobs=-1)
    rf_model.fit(X, y)
    
    ridge_model = Ridge()
    ridge_model.fit(X, y)
    
    y_pred_rf = rf_model.predict(X)
    y_pred_ridge = ridge_model.predict(X)
    
    X_future = forecasted_predictors_df[predictors].ffill().bfill().fillna(0.0)
    future_pred_rf = rf_model.predict(X_future)
    future_pred_ridge = ridge_model.predict(X_future)
    
    y_pred_rf = np.clip(y_pred_rf, 0.0, 100.0)
    y_pred_ridge = np.clip(y_pred_ridge, 0.0, 100.0)
    future_pred_rf = np.clip(future_pred_rf, 0.0, 100.0)
    future_pred_ridge = np.clip(future_pred_ridge, 0.0, 100.0)
    
    metrics = {
        "rf": {
            "MAE": mean_absolute_error(y, y_pred_rf),
            "RMSE": np.sqrt(mean_squared_error(y, y_pred_rf)),
            "R2": r2_score(y, y_pred_rf)
        },
        "ridge": {
            "MAE": mean_absolute_error(y, y_pred_ridge),
            "RMSE": np.sqrt(mean_squared_error(y, y_pred_ridge)),
            "R2": r2_score(y, y_pred_ridge)
        }
    }
    
    feature_importances = dict(zip(predictors, rf_model.feature_importances_))
    
    df_fitted = pd.DataFrame({
        "ipc_actual": y,
        "rf_fitted": y_pred_rf,
        "ridge_fitted": y_pred_ridge
    }, index=joined_df.index)
    
    df_projected = pd.DataFrame({
        "rf_projected": future_pred_rf,
        "ridge_projected": future_pred_ridge
    }, index=forecasted_predictors_df.index)
    
    return df_fitted, df_projected, metrics, feature_importances
