import pandas as pd
import numpy as np
from statsmodels.tsa.stattools import adfuller
from statsmodels.tsa.seasonal import STL
import matplotlib.pyplot as plt
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf

def check_stationarity_and_difference(series, max_diff=2):
    """
    Runs ADF test. If not stationary (p-value > 0.05), differences the series
    up to max_diff times and repeats the test.
    Returns a dict with the final stationary series, number of differences d, and final adf results.
    """
    clean_series = series.interpolate(method="linear").ffill().bfill()
    d = 0
    curr_series = clean_series.copy()
    
    # Run initial ADF test
    adf_result = run_adf_test(curr_series)
    
    while adf_result["p_value"] > 0.05 and d < max_diff:
        d += 1
        curr_series = curr_series.diff().dropna()
        adf_result = run_adf_test(curr_series)
        
    return {
        "stationary_series": curr_series,
        "d": d,
        "adf_stat": adf_result["adf_statistic"],
        "p_value": adf_result["p_value"],
        "is_stationary": adf_result["is_stationary"]
    }

def run_adf_test(series):
    """
    Runs a single Augmented Dickey-Fuller test.
    """
    if len(series) < 6:
        return {"adf_statistic": 0.0, "p_value": 1.0, "is_stationary": False}
    try:
        res = adfuller(series)
        return {
            "adf_statistic": res[0],
            "p_value": res[1],
            "is_stationary": res[1] < 0.05
        }
    except Exception:
        return {"adf_statistic": np.nan, "p_value": 1.0, "is_stationary": False}

def run_stl_decomposition(series, period=12):
    """
    Performs STL decomposition on a z-score normalized series.
    Returns STL components.
    """
    clean_series = series.interpolate(method="linear").ffill().bfill()
    # STL requires seasonal periods to be odd and >= 7 for robust fit, default is 7.
    # period must be >= 4
    if len(clean_series) < 2 * period:
        # Fallback if series is too short
        period = 2
        
    try:
        stl = STL(clean_series, period=period, robust=True)
        res = stl.fit()
        return res.observed, res.trend, res.seasonal, res.resid
    except Exception as e:
        # Fallback to simple rolling means if STL fails
        print(f"STL decomposition failed: {e}. Falling back to rolling components.")
        trend = clean_series.rolling(window=period, center=True).mean().ffill().bfill()
        resid = clean_series - trend
        seasonal = pd.Series(0.0, index=clean_series.index)
        return clean_series, trend, seasonal, resid

def plot_stl_decomposition(observed, trend, seasonal, resid, title, save_path):
    """
    Generates and saves the 4-panel STL decomposition plot.
    """
    fig, axes = plt.subplots(4, 1, figsize=(12, 10), sharex=True)
    
    axes[0].plot(observed, color="black", linewidth=1.5)
    axes[0].set_title(f"STL Decomposition: {title}", fontsize=14)
    axes[0].set_ylabel("Observed", fontsize=10)
    axes[0].grid(True)
    
    axes[1].plot(trend, color="blue", linewidth=1.5)
    axes[1].set_ylabel("Trend", fontsize=10)
    axes[1].grid(True)
    
    axes[2].plot(seasonal, color="green", linewidth=1.5)
    axes[2].set_ylabel("Seasonal", fontsize=10)
    axes[2].grid(True)
    
    axes[3].plot(resid, color="red", linestyle="none", marker="o", alpha=0.6)
    axes[3].axhline(y=0, color="black", linestyle="--")
    axes[3].set_ylabel("Residual", fontsize=10)
    axes[3].grid(True)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=120, bbox_inches="tight")
    plt.close()

def plot_acf_pacf(series, title, save_path, lags=24):
    """
    Generates and saves the ACF and PACF plots on a stationary series.
    """
    clean_series = series.interpolate(method="linear").ffill().bfill()
    # Limit lags to half the series length
    lags = min(lags, len(clean_series) // 2 - 1)
    if lags < 2:
        lags = 2
        
    fig, axes = plt.subplots(2, 1, figsize=(12, 8))
    
    try:
        plot_acf(clean_series, ax=axes[0], lags=lags, title=f"Autocorrelation (ACF) - {title}")
        axes[0].grid(True)
    except Exception as e:
        axes[0].text(0.5, 0.5, f"ACF Plot failed: {e}", ha='center')
        
    try:
        plot_pacf(clean_series, ax=axes[1], lags=lags, title=f"Partial Autocorrelation (PACF) - {title}")
        axes[1].grid(True)
    except Exception as e:
        axes[1].text(0.5, 0.5, f"PACF Plot failed: {e}", ha='center')
        
    plt.tight_layout()
    plt.savefig(save_path, dpi=120, bbox_inches="tight")
    plt.close()
