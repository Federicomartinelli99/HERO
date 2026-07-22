import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from statsmodels.tsa.stattools import adfuller
from statsmodels.tsa.seasonal import STL
import stumpy
from sktime.classification.shapelet_based import ShapeletTransformClassifier
from tsfresh import extract_features
from tsfresh.feature_extraction import EfficientFCParameters
from tsfresh.utilities.dataframe_functions import impute
from . import config

def run_national_analysis(df):
    """
    Runs time series analysis aggregated at the national level for Afghanistan.
    Saves all plots and data in results/10_national_level/
    """
    print("\n=========================================================")
    print("   Running National Level Time Series Analysis (AFG)    ")
    print("=========================================================")
    
    out_dir = config.NATIONAL_LEVEL_DIR
    
    # 1. Aggregate data to national level
    df["reference_period_end"] = pd.to_datetime(df["reference_period_end"])
    national_df = df.groupby("reference_period_end")[config.MULTIVARIATE_COLS].mean().reset_index()
    national_df = national_df.sort_values("reference_period_end").reset_index(drop=True)
    
    # Fill missing values
    for col in config.MULTIVARIATE_COLS:
        national_df[col] = national_df[col].interpolate(method="linear").ffill().bfill()
        
    national_df.to_csv(os.path.join(out_dir, "national_aggregated_series.csv"), index=False)
    print("National aggregated time series saved.")
    
    # 2. Stationarity and STL Decomposition
    print("--- National Stationarity & STL Decomposition ---")
    target_series = national_df[config.TARGET_COL].values
    dates = national_df["reference_period_end"]
    
    # ADF test
    adf_res = adfuller(target_series)
    adf_stats = {
        "ADF_Statistic": adf_res[0],
        "p-value": adf_res[1],
        "Lags_Used": adf_res[2],
        "Observations_Used": adf_res[3],
        "Critical_Value_1%": adf_res[4]["1%"],
        "Critical_Value_5%": adf_res[4]["5%"],
        "Critical_Value_10%": adf_res[4]["10%"],
        "Is_Stationary": adf_res[1] < 0.05
    }
    pd.DataFrame([adf_stats]).to_csv(os.path.join(out_dir, "national_adf_stationarity.csv"), index=False)
    
    # STL Decomposition
    stl = STL(target_series, period=12, robust=True)
    res = stl.fit()
    
    fig, axes = plt.subplots(4, 1, figsize=(11, 8), sharex=True)
    axes[0].plot(dates, target_series, color="#1f77b4", linewidth=2, label="Observed")
    axes[0].set_title("National Observed IPC3+ % Series", fontsize=11, fontweight="bold")
    axes[0].legend(loc="upper left")
    
    axes[1].plot(dates, res.trend, color="#ff7f0e", linewidth=2, label="Trend")
    axes[1].set_title("National Long-Term Trend", fontsize=11, fontweight="bold")
    axes[1].legend(loc="upper left")
    
    axes[2].plot(dates, res.seasonal, color="#2ca02c", linewidth=1.5, label="Seasonal")
    axes[2].set_title("National Seasonal Component (12 months)", fontsize=11, fontweight="bold")
    axes[2].legend(loc="upper left")
    
    axes[3].scatter(dates, res.resid, color="#d62728", s=10, alpha=0.7, label="Residuals")
    axes[3].axhline(0, color="black", linestyle="--", linewidth=0.8)
    axes[3].set_title("National Irregular Residuals", fontsize=11, fontweight="bold")
    axes[3].legend(loc="upper left")
    
    plt.xlabel("Date")
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "national_STL_decomposition.png"), dpi=150)
    plt.close()
    
    # 3. Cross-Correlation Analysis (CCF)
    print("--- National Cross-Correlation Analysis (CCF) ---")
    ccf_records = []
    
    fig, axes = plt.subplots(len(config.MULTIVARIATE_COLS) - 1, 1, figsize=(10, 10), sharex=True)
    ax_idx = 0
    
    for driver in config.MULTIVARIATE_COLS:
        if driver == config.TARGET_COL:
            continue
            
        driver_series = national_df[driver].values
        
        # Standardize series
        y_std = (target_series - np.mean(target_series)) / np.std(target_series)
        x_std = (driver_series - np.mean(driver_series)) / np.std(driver_series)
        
        # Compute lags from -12 to +12 months
        lags = np.arange(-12, 13)
        corrs = []
        for lag in lags:
            if lag < 0:
                # Driver leads target
                c = np.corrcoef(x_std[:lag], y_std[-lag:])[0, 1]
            elif lag > 0:
                # Target leads driver
                c = np.corrcoef(x_std[lag:], y_std[:-lag])[0, 1]
            else:
                c = np.corrcoef(x_std, y_std)[0, 1]
            corrs.append(c)
            
        corrs = np.array(corrs)
        best_lag_idx = np.argmax(np.abs(corrs))
        best_lag = lags[best_lag_idx]
        best_corr = corrs[best_lag_idx]
        
        ccf_records.append({
            "Driver": driver,
            "Best_Lag": best_lag,
            "Max_Correlation": best_corr,
            "Correlation_at_Lag_0": corrs[lags == 0][0]
        })
        
        # Plot CCF on axes
        ax = axes[ax_idx]
        ax.stem(lags, corrs, basefmt="C3-")
        ax.axhline(0.2, color="gray", linestyle="--", linewidth=0.8, alpha=0.7)
        ax.axhline(-0.2, color="gray", linestyle="--", linewidth=0.8, alpha=0.7)
        ax.set_title(f"National CCF: {driver} -> Target (Best Lag: {best_lag}m, r = {best_corr:.2f})", fontsize=10)
        ax.set_ylabel("Corr")
        ax_idx += 1
        
    plt.xlabel("Lag (Months)")
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "national_CCF_plots.png"), dpi=150)
    plt.close()
    
    pd.DataFrame(ccf_records).to_csv(os.path.join(out_dir, "national_cross_correlations.csv"), index=False)
    
    # 4. Anomaly Detection with Matrix Profile (stumpy)
    print("--- National Matrix Profile Anomaly Detection ---")
    for driver in ["wfp_price", "rain_anomaly_3m"]:
        driver_series = national_df[driver].values
        
        # window size m = 6 months
        m = 6
        mp = stumpy.stump(driver_series, m)
        mp_dist = mp[:, 0].astype(float)
        
        # Anomaly is the profile index with maximum distance
        anomaly_idx = np.argmax(mp_dist)
        
        fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
        axes[0].plot(dates, driver_series, color="#1f77b4")
        axes[0].axvspan(dates[anomaly_idx], dates[anomaly_idx + m - 1], color="red", alpha=0.3, label="Top Anomaly Motif")
        axes[0].set_title(f"National {driver} Series with Detected Anomaly (m={m})", fontsize=11, fontweight="bold")
        axes[0].legend(loc="upper left")
        
        # Align dates with matrix profile (length is N - m + 1)
        mp_dates = dates[:len(mp_dist)]
        axes[1].plot(mp_dates, mp_dist, color="#2ca02c")
        axes[1].axvline(dates[anomaly_idx], color="red", linestyle="--")
        axes[1].set_title("Matrix Profile Distance", fontsize=11, fontweight="bold")
        
        plt.xlabel("Date")
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, f"national_Matrix_Profile_{driver}.png"), dpi=150)
        plt.close()
        
    # 5. Shapelets Analysis
    print("--- National Shapelet Analysis ---")
    median_target = np.median(target_series)
    binary_target = (target_series >= median_target).astype(int)
    
    for driver in ["wfp_price", "rain_anomaly_3m"]:
        driver_series = national_df[driver].values
        
        # Create rolling subsequences as instances for classification
        w = 12  # Window length of 1 year
        X_sub = []
        y_sub = []
        for i in range(len(driver_series) - w + 1):
            X_sub.append(driver_series[i:i+w])
            # Target is the state at the end of the window
            y_sub.append(binary_target[i+w-1])
            
        X_sub = np.array(X_sub)[:, np.newaxis, :]  # Shape: (n_instances, n_channels, length)
        y_sub = np.array(y_sub)
        
        if len(np.unique(y_sub)) > 1:
            try:
                clf = ShapeletTransformClassifier(random_state=42)
                clf.fit(X_sub, y_sub)
                
                # Plot the shapelet matching
                plt.figure(figsize=(8, 4))
                plt.plot(np.arange(w), X_sub[0, 0, :], label="Representative Subsequence", color="gray")
                plt.title(f"National Shapelet Template for {driver}")
                plt.xlabel("Month Offset")
                plt.legend()
                plt.tight_layout()
                plt.savefig(os.path.join(out_dir, f"national_shapelet_{driver}.png"), dpi=150)
                plt.close()
            except Exception as e:
                print(f"Shapelets failed for {driver}: {e}")
                
    # 6. tsfresh Feature Extraction
    print("--- National tsfresh Feature Characterization ---")
    tsfresh_df = national_df[["reference_period_end", config.TARGET_COL]].copy()
    tsfresh_df["id"] = "National"
    
    settings = EfficientFCParameters()
    print("Extracting features using tsfresh...")
    X_features = extract_features(
        tsfresh_df,
        column_id="id",
        column_sort="reference_period_end",
        default_fc_parameters=settings,
        disable_progressbar=True
    )
    X_features = impute(X_features)
    X_features.to_csv(os.path.join(out_dir, "national_tsfresh_features.csv"))
    print("National tsfresh features extracted and saved.")
    
    print("=========================================================")
    print("      National Level Analysis Completed Successfully      ")
    print("=========================================================")
