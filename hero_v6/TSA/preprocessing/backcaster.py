import pandas as pd
import numpy as np
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tsa.holtwinters import ExponentialSmoothing

def backcast_impute_series(series, clip_non_negative=True, seasonal_periods=12):
    """
    Imputes missing values at the start of a series by forecasting backward in time.
    """
    # Create a copy to avoid side-effects
    ts = series.copy()
    
    # Check if there are missing values to impute
    if not ts.isna().any():
        return ts
        
    # Find the index of the first non-null observation
    first_valid_idx = ts.first_valid_index()
    if first_valid_idx is None:
        # Whole series is NaN, cannot backcast
        return ts.fillna(0.0)
        
    first_valid_loc = ts.index.get_loc(first_valid_idx)
    
    # If the first valid value is at index 0, there is no historical prefix to backcast
    if first_valid_loc == 0:
        # Just interpolate internal gaps
        return ts.interpolate(method="linear").ffill().bfill()
        
    # Extract the valid suffix (available history)
    suffix = ts.iloc[first_valid_loc:]
    
    # Check if suffix has enough points to fit a model (need at least 2 * seasonal_periods for HW)
    suffix_clean = suffix.interpolate(method="linear").ffill().bfill()
    
    # Reverse the suffix
    reversed_suffix = suffix_clean.iloc[::-1]
    
    # Define how many steps backward we need to forecast
    steps_backward = first_valid_loc
    
    # Try fitting a model to forecast backward
    forecasted_vals = None
    
    # Try Holt-Winters first if we have enough data, otherwise fallback to SARIMAX or SES
    if len(reversed_suffix) >= max(10, 2 * seasonal_periods):
        try:
            model = ExponentialSmoothing(reversed_suffix, trend="add", seasonal="add", seasonal_periods=seasonal_periods)
            res = model.fit()
            forecasted_vals = res.forecast(steps=steps_backward)
        except Exception:
            pass
            
    if forecasted_vals is None:
        # Fallback 1: Simple Exponential Smoothing
        try:
            model = ExponentialSmoothing(reversed_suffix, trend="add", seasonal=None)
            res = model.fit()
            forecasted_vals = res.forecast(steps=steps_backward)
        except Exception:
            pass
            
    if forecasted_vals is None:
        # Fallback 2: SARIMAX(1, 1, 1)
        try:
            model = SARIMAX(reversed_suffix, order=(1, 1, 1), enforce_stationarity=False, enforce_invertibility=False)
            res = model.fit(disp=False)
            forecasted_vals = res.forecast(steps=steps_backward)
        except Exception:
            pass
            
    if forecasted_vals is None:
        # Fallback 3: Linear backfill
        forecasted_vals = pd.Series(suffix_clean.iloc[0], index=ts.index[:first_valid_loc])
        
    # Align the forecasted values with the missing prefix index
    forecasted_vals.index = ts.index[:first_valid_loc]
    
    # Reverse the forecasted values so they match the original chronological order
    # (since forecasting forward on reversed series projects further into the past, 
    # the first forecast is t-1, second is t-2, etc. We must align them correctly)
    forecasted_chronological = forecasted_vals.sort_index()
    
    # Fill in the missing prefix
    ts.iloc[:first_valid_loc] = forecasted_chronological
    
    # Clip to non-negative if requested
    if clip_non_negative:
        ts = ts.clip(lower=0)
        
    # Linearly interpolate any remaining internal NaNs and ffill
    ts = ts.interpolate(method="linear").ffill().bfill()
    
    return ts

def backcast_impute_dataframe(df, clip_columns=None):
    """
    Applies backcasting imputation to all columns in a DataFrame.
    """
    if clip_columns is None:
        clip_columns = [
            "wfp_price_mean", "rain_1m", "rain_3m", 
            "acled_events", "acled_fatalities", "idp_population"
        ]
        
    imputed_df = df.copy()
    for col in df.columns:
        clip = any(c in col for c in clip_columns)
        imputed_df[col] = backcast_impute_series(df[col], clip_non_negative=clip)
    return imputed_df
