import pandas as pd
import numpy as np
from statsmodels.tsa.stattools import grangercausalitytests
from statsmodels.tsa.api import VAR
from statsmodels.stats.diagnostic import acorr_ljungbox

def run_granger_causality(df, target_col, predictor_cols, maxlag=6):
    """
    Performs Granger Causality tests for multiple predictors vs target.
    Returns a DataFrame containing p-values for each lag.
    """
    clean_df = df.interpolate(method="linear").ffill().bfill()
    results_dict = {}
    
    # We require a minimum number of samples (usually 2 * maxlag + 2)
    if len(clean_df) < (2 * maxlag + 2):
        maxlag = max(1, len(clean_df) // 3)
        
    for pred in predictor_cols:
        if pred == target_col or pred not in clean_df.columns:
            continue
            
        p_values = []
        try:
            # Data array: first column is target (y), second is predictor (x)
            data_pair = clean_df[[target_col, pred]].values
            gc_res = grangercausalitytests(data_pair, maxlag=maxlag, verbose=False)
            
            for lag in range(1, maxlag + 1):
                # We use the SSR-based F-test p-value (which is standard)
                p_val = gc_res[lag][0]["ssr_ftest"][1]
                p_values.append(p_val)
                
            results_dict[pred] = p_values
        except Exception as e:
            print(f"Granger Causality failed for predictor {pred}: {e}")
            results_dict[pred] = [np.nan] * maxlag
            
    # Compile into a DataFrame
    if results_dict:
        df_pvals = pd.DataFrame(results_dict, index=[f"lag_{i}" for i in range(1, maxlag + 1)])
        return df_pvals
    else:
        return pd.DataFrame()

def fit_var_forecast(df, columns, target_col, steps=12, maxlags=6):
    """
    Fits a Vector Autoregression (VAR) model on the selected columns,
    selects optimal lag, and forecasts future values.
    Returns the forecast Series and the Ljung-Box p-value of residuals.
    """
    # Filter columns and clean data
    clean_df = df[columns].interpolate(method="linear").ffill().bfill()
    
    # Ensure there is enough data
    if len(clean_df) < (2 * maxlags + 2):
        maxlags = max(1, len(clean_df) // 3)
        
    try:
        model = VAR(clean_df)
        # Select optimal lag order
        order_sel = model.select_order(maxlags=maxlags)
        # Fallback to AIC lag
        p_lag = order_sel.aic if order_sel.aic > 0 else 1
        
        # Fit VAR
        var_res = model.fit(p_lag)
        
        # Forecast
        # VAR forecast takes a 2D array of the last p_lag observations
        forecast_input = clean_df.values[-p_lag:]
        fc = var_res.forecast(y=forecast_input, steps=steps)
        
        # Find index of target column in VAR
        target_idx = list(clean_df.columns).index(target_col)
        fc_target = fc[:, target_idx]
        
        # Check residuals white noise properties on target using Ljung-Box
        residuals = var_res.resid[target_col]
        # Perform Ljung-Box test
        lb_res = acorr_ljungbox(residuals, lags=[min(10, len(residuals)//2-1)], return_df=True)
        lb_pval = lb_res["lb_pvalue"].iloc[0]
        
        # Generate forecast series
        forecast_index = pd.date_range(start=clean_df.index[-1] + pd.DateOffset(months=1), periods=steps, freq="MS")
        fc_series = pd.Series(fc_target, index=forecast_index)
        
        return fc_series, lb_pval, residuals
        
    except Exception as e:
        print(f"VAR model failed: {e}")
        # Fallback to mean forecast and 0.0 p-value
        forecast_index = pd.date_range(start=clean_df.index[-1] + pd.DateOffset(months=1), periods=steps, freq="MS")
        return pd.Series(df[target_col].mean(), index=forecast_index), 0.0, pd.Series(0.0, index=clean_df.index)
