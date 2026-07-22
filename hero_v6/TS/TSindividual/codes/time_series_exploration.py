import os
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import seaborn as sns
import gzip
import stumpy
import pycatch22
from scipy.spatial.distance import squareform
from scipy.cluster.hierarchy import linkage, dendrogram, fcluster
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from statsmodels.tsa.stattools import adfuller, ccf
from statsmodels.tsa.seasonal import STL
import statsmodels.graphics.tsaplots as sgt
from numba import njit
from . import config

# --- HELPER FUNCTIONS FOR DTW & NCD ---

def z_score_normalize(series):
    arr = np.array(series, dtype=float)
    s_std = np.std(arr)
    if s_std == 0 or np.isnan(s_std):
        return arr - np.mean(arr)
    return (arr - np.mean(arr)) / s_std

@njit
def dtw_distance_numba(a1, a2, w):
    n, m = len(a1), len(a2)
    dtw_matrix = np.full((n + 1, m + 1), np.inf)
    dtw_matrix[0, 0] = 0.0
    for i in range(1, n + 1):
        start_j = max(1, i - w)
        end_j = min(m + 1, i + w + 1)
        for j in range(start_j, end_j):
            cost = (a1[i - 1] - a2[j - 1]) ** 2
            dtw_matrix[i, j] = cost + min(
                dtw_matrix[i - 1, j],
                dtw_matrix[i, j - 1],
                dtw_matrix[i - 1, j - 1]
            )
    return np.sqrt(dtw_matrix[n, m])

def dtw_distance(s1, s2, w=None):
    a1 = np.array(s1, dtype=np.float64)
    a2 = np.array(s2, dtype=np.float64)
    n, m = len(a1), len(a2)
    if w is None:
        w_val = max(n, m)
    else:
        w_val = max(int(w), abs(n - m))
    return dtw_distance_numba(a1, a2, w_val)

def compute_ncd(s1, s2):
    a1 = np.array(s1, dtype=np.float32)
    a2 = np.array(s2, dtype=np.float32)
    b1 = a1.tobytes()
    b2 = a2.tobytes()
    b12 = b1 + b2
    c1 = len(gzip.compress(b1))
    c2 = len(gzip.compress(b2))
    c12 = len(gzip.compress(b12))
    ncd_val = (c12 - min(c1, c2)) / max(c1, c2)
    return max(0.0, ncd_val)

# --- FASE 3 ANALYSIS FUNCTIONS ---

def run_stationarity_and_stl(df, results_dir=None):
    """
    Task 3.1: Stationarity testing (ADF) + auto-differencing + STL decomposition.
    Plots are generated for representative provinces.
    """
    print("--- Running Stationarity and STL Decomposition ---")
    out_dir = config.STATIONARITY_STL_DIR
    
    provinces = df["Level 1"].unique()
    adf_results = []
    
    for prov in provinces:
        prov_df = df[df["Level 1"] == prov].sort_values("reference_period_end")
        series = prov_df[config.TARGET_COL].values
        
        if len(series) < 15:
            continue
            
        # Test stationarity
        adf_res = adfuller(series)
        p_val = adf_res[1]
        
        d = 0
        diff_series = series.copy()
        if p_val >= 0.05:
            # Try first diff
            diff_series = np.diff(series)
            adf_res_1 = adfuller(diff_series)
            p_val_1 = adf_res_1[1]
            d = 1
            if p_val_1 >= 0.05:
                # Try second diff
                diff_series = np.diff(diff_series)
                adf_res_2 = adfuller(diff_series)
                p_val_2 = adf_res_2[1]
                d = 2
                p_val = p_val_2
            else:
                p_val = p_val_1
        else:
            p_val = p_val
            
        adf_results.append({
            "Province": prov,
            "Original_PValue": adf_res[1],
            "Final_PValue": p_val,
            "Order_d": d
        })
        
        # Run STL on original series
        stl = STL(series, period=12, robust=True)
        res = stl.fit()
        
        # Plot only for representative provinces to avoid clutter
        if prov in config.REPRESENTATIVE_PROVINCES:
            # Plot STL
            fig, axes = plt.subplots(4, 1, figsize=(10, 8), sharex=True)
            dates = prov_df["reference_period_end"].values
            axes[0].plot(dates, series, label="Observed", color="blue")
            axes[0].legend(loc="upper left")
            axes[0].set_title(f"STL Decomposition & Stationarity - {prov}")
            
            axes[1].plot(dates, res.trend, label="Trend", color="orange")
            axes[1].legend(loc="upper left")
            
            axes[2].plot(dates, res.seasonal, label="Seasonal", color="green")
            axes[2].legend(loc="upper left")
            
            axes[3].plot(dates, res.resid, label="Residuals", color="red")
            axes[3].legend(loc="upper left")
            
            plt.tight_layout()
            stl_plot_path = os.path.join(out_dir, f"01_Statistical_Decomposition_STL_{prov}.png")
            plt.savefig(stl_plot_path, dpi=150)
            plt.close()
            
            # Plot ACF / PACF Comparison (Before vs After differencing if d > 0)
            fig, axes = plt.subplots(2, 2, figsize=(12, 6))
            sgt.plot_acf(series, ax=axes[0, 0], lags=12, title=f"ACF Original ({prov})")
            sgt.plot_pacf(series, ax=axes[0, 1], lags=12, title=f"PACF Original ({prov})")
            
            # Differenced series ACF/PACF
            sgt.plot_acf(diff_series, ax=axes[1, 0], lags=12, title=f"ACF Diff d={d} ({prov})")
            sgt.plot_pacf(diff_series, ax=axes[1, 1], lags=12, title=f"PACF Diff d={d} ({prov})")
            
            plt.tight_layout()
            acf_plot_path = os.path.join(out_dir, f"02b_Compare_Series_Autocorrelation_{prov}.png")
            plt.savefig(acf_plot_path, dpi=150)
            plt.close()
            
    # Save ADF table
    df_adf = pd.DataFrame(adf_results)
    df_adf.to_csv(os.path.join(out_dir, "adf_stationarity_results.csv"), index=False)
    print("STL and Stationarity Analysis Completed.")
    return df_adf

def run_cross_correlation(df, results_dir=None):
    """
    Task 3.2: Cross-Correlation with Lag (CCF)
    """
    print("--- Running Cross-Correlation Analysis ---")
    out_dir = config.CROSS_CORRELATION_DIR
    
    provinces = df["Level 1"].unique()
    ccf_records = []
    
    # Representative columns
    drivers = [col for col in config.MULTIVARIATE_COLS if col != config.TARGET_COL]
    
    for prov in provinces:
        prov_df = df[df["Level 1"] == prov].sort_values("reference_period_end")
        target_series = prov_df[config.TARGET_COL].values
        
        if len(target_series) < 15:
            continue
            
        for driver in drivers:
            driver_series = prov_df[driver].values
            
            # Interpolate to avoid NaNs
            target_series_clean = pd.Series(target_series).interpolate().ffill().bfill().values
            driver_series_clean = pd.Series(driver_series).interpolate().ffill().bfill().values
            
            # Normalize for CCF
            y_norm = z_score_normalize(target_series_clean)
            x_norm = z_score_normalize(driver_series_clean)
            
            lags = np.arange(-12, 13)
            ccf_values = []
            
            for lag in lags:
                if lag < 0:
                    val = np.corrcoef(x_norm[-lag:], y_norm[:lag])[0, 1] if len(x_norm[-lag:]) > 5 else 0
                elif lag > 0:
                    val = np.corrcoef(x_norm[:-lag], y_norm[lag:])[0, 1] if len(x_norm[:-lag]) > 5 else 0
                else:
                    val = np.corrcoef(x_norm, y_norm)[0, 1]
                    
                ccf_values.append(val if not np.isnan(val) else 0)
                
            ccf_values = np.array(ccf_values)
            abs_ccf = np.abs(ccf_values)
            opt_idx = np.argmax(abs_ccf)
            opt_lag = lags[opt_idx]
            opt_corr = ccf_values[opt_idx]
            
            ccf_records.append({
                "Province": prov,
                "Driver": driver,
                "Optimal_Lag": opt_lag,
                "Max_Correlation": opt_corr
            })
            
            # Plot CCF for representative provinces
            if prov in config.REPRESENTATIVE_PROVINCES:
                plt.figure(figsize=(8, 4))
                plt.bar(lags, ccf_values, color="teal", alpha=0.7)
                plt.axvline(opt_lag, color="red", linestyle="--", label=f"Max Corr at Lag {opt_lag} ({opt_corr:.2f})")
                plt.title(f"Cross-Correlation: {driver} -> {config.TARGET_COL} ({prov})")
                plt.xlabel("Lag (Months, negative: target leads, positive: driver leads)")
                plt.ylabel("Correlation")
                plt.grid(True, linestyle=":", alpha=0.6)
                plt.legend()
                plt.tight_layout()
                plt.savefig(os.path.join(out_dir, f"02c_CCF_{prov}_{driver}.png"), dpi=150)
                plt.close()
                
    df_ccf = pd.DataFrame(ccf_records)
    df_ccf.to_csv(os.path.join(out_dir, "02c_Cross_Correlation_with_Target.csv"), index=False)
    print("Cross-Correlation Analysis Completed.")
    return df_ccf

def run_matrix_profile(df, results_dir=None):
    """
    Task 3.3: Matrix Profile Anomalies and Discords
    """
    print("--- Running Matrix Profile Anomaly Rilevamento ---")
    out_dir = config.MATRIX_PROFILE_DIR
    
    drivers = ["wfp_price", "rain_anomaly_3m"]
    
    for prov in config.REPRESENTATIVE_PROVINCES:
        prov_df = df[df["Level 1"] == prov].sort_values("reference_period_end")
        dates = prov_df["reference_period_end"].values
        
        if len(dates) < 24:
            continue
            
        for driver in drivers:
            series = prov_df[driver].interpolate().ffill().bfill().values
            if len(np.unique(series)) <= 1:
                continue
                
            m = 12
            mp = stumpy.stump(series, m)
            mp_dist = mp[:, 0].astype(float)
            
            discord_idx = int(np.argmax(mp_dist))
            motif_idx = int(np.argmin(mp_dist))
            
            mp_mean = float(np.mean(mp_dist))
            mp_std = float(np.std(mp_dist)) if np.std(mp_dist) > 0 else 1.0
            mp_z = (mp_dist - mp_mean) / mp_std
            
            shocks_idx = np.where(mp_z > 2.0)[0]
            
            # Plot
            fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
            
            axes[0].plot(dates, series, label=driver, color="darkblue")
            axes[0].axvspan(dates[discord_idx], dates[discord_idx + m - 1], color="red", alpha=0.2, label="Top Discord (Anomaly)")
            axes[0].axvspan(dates[motif_idx], dates[motif_idx + m - 1], color="green", alpha=0.2, label="Top Motif (Pattern)")
            
            for s_idx in shocks_idx:
                axes[0].axvline(dates[s_idx], color="orange", linestyle=":", alpha=0.8)
                
            axes[0].legend(loc="upper left")
            axes[0].set_title(f"Matrix Profile (m={m}) - {driver} in {prov}")
            
            mp_padded = np.zeros(len(dates))
            mp_padded[:len(mp_dist)] = mp_dist
            mp_padded[len(mp_dist):] = np.nan
            
            axes[1].plot(dates, mp_padded, color="purple", label="Matrix Profile Distance")
            axes[1].axhline(mp_mean + 2.0 * mp_std, color="red", linestyle="--", label="Shock Threshold (Z > 2.0)")
            axes[1].legend(loc="upper left")
            
            plt.tight_layout()
            plt.savefig(os.path.join(out_dir, f"04_Matrix_Profile_{prov}_{driver}.png"), dpi=150)
            plt.close()
            
    print("Matrix Profile Analysis Completed.")

def run_shapelets(df, results_dir=None):
    """
    Task 3.4: Shapelet Extraction
    """
    print("--- Running Shapelet Extraction & Alignment ---")
    out_dir = config.SHAPELETS_DIR
    
    drivers = ["wfp_price", "acled_political_violence_events_per_100k_population", "rain_anomaly_3m"]
    
    for prov in config.REPRESENTATIVE_PROVINCES:
        prov_df = df[df["Level 1"] == prov].sort_values("reference_period_end").copy()
        dates = prov_df["reference_period_end"].values
        target = prov_df[config.TARGET_COL].interpolate().ffill().bfill().values
        
        if len(dates) < 24:
            continue
            
        target_diff = np.zeros(len(target))
        target_diff[:-3] = target[3:] - target[:-3]
        
        surge_indices = np.where(target_diff > 5.0)[0]
        if len(surge_indices) == 0:
            surge_indices = np.where(target > np.percentile(target, 85))[0]
            
        if len(surge_indices) == 0:
            continue
            
        best_surge_t = surge_indices[np.argmax(target_diff[surge_indices])]
        
        L = 6
        if best_surge_t < L:
            best_surge_t = max(L, surge_indices[0])
            if best_surge_t >= len(target):
                continue
                
        start_idx = best_surge_t - L
        end_idx = best_surge_t
        
        for driver in drivers:
            driver_series = prov_df[driver].interpolate().ffill().bfill().values
            shapelet = driver_series[start_idx:end_idx]
            shapelet_norm = z_score_normalize(shapelet)
            
            distances = []
            for i in range(len(driver_series) - L + 1):
                subseq = driver_series[i:i+L]
                subseq_norm = z_score_normalize(subseq)
                dist = np.sqrt(np.mean((subseq_norm - shapelet_norm) ** 2))
                distances.append(dist)
                
            distances = np.array(distances)
            
            # Plot
            fig, axes = plt.subplots(3, 1, figsize=(10, 7), sharex=True)
            
            axes[0].plot(dates, target, color="red", label="Target (IPC3+ %)")
            axes[0].axvline(dates[best_surge_t], color="darkred", linestyle="--", label="Surge Start")
            axes[0].legend(loc="upper left")
            axes[0].set_title(f"Shapelet Alignment ({driver}) preceding IPC3+ surge - {prov}")
            
            axes[1].plot(dates, driver_series, color="blue", label=f"Driver ({driver})")
            axes[1].plot(dates[start_idx:end_idx], shapelet, color="orange", linewidth=3, label="Extracted Shapelet")
            axes[1].legend(loc="upper left")
            
            dist_padded = np.zeros(len(dates))
            dist_padded[:len(distances)] = distances
            dist_padded[len(distances):] = np.nan
            
            axes[2].plot(dates, dist_padded, color="purple", label="Shapelet Distance Profile")
            axes[2].legend(loc="upper left")
            
            plt.tight_layout()
            plt.savefig(os.path.join(out_dir, f"shapelet_{prov}_{driver}.png"), dpi=150)
            plt.close()
            
    print("Shapelet Analysis Completed.")

def run_tsfresh_feature_extraction(df, results_dir=None):
    """
    Task 3.5: Structural Feature Extraction via tsfresh
    """
    print("--- Running tsfresh Feature Extraction & Correlation ---")
    out_dir = config.CATCH22_DIR  # Save in Catch22 directory
    
    from tsfresh import extract_features
    from tsfresh.feature_extraction import EfficientFCParameters
    from tsfresh.utilities.dataframe_functions import impute
    
    # Prepare data for tsfresh: needs a long-format DataFrame
    ts_data = df[["Level 1", "reference_period_end", config.TARGET_COL]].copy()
    ts_data["reference_period_end"] = pd.to_datetime(ts_data["reference_period_end"])
    ts_data[config.TARGET_COL] = ts_data[config.TARGET_COL].interpolate().ffill().bfill()
    
    # Filter provinces with at least 15 observations
    counts = ts_data["Level 1"].value_counts()
    valid_provs = counts[counts >= 15].index
    ts_data = ts_data[ts_data["Level 1"].isin(valid_provs)]
    
    # Extract features using Efficient parameters (faster than Comprehensive but rich)
    settings = EfficientFCParameters()
    print("Extracting features using tsfresh...")
    X = extract_features(
        ts_data,
        column_id="Level 1",
        column_sort="reference_period_end",
        default_fc_parameters=settings,
        disable_progressbar=True
    )
    
    # Impute missing values
    X = impute(X)
    
    # Save extracted features
    X.to_csv(os.path.join(out_dir, "tsfresh_extracted_features.csv"))
    
    # Compute mean target per province to correlate with features
    mean_target = ts_data.groupby("Level 1")[config.TARGET_COL].mean()
    
    # Compute correlation with mean target
    corrs = X.corrwith(mean_target).sort_values()
    df_corrs = pd.DataFrame(corrs).reset_index().rename(columns={"index": "Feature", 0: "Correlation"})
    
    # Drop rows where correlation is NaN
    df_corrs = df_corrs.dropna(subset=["Correlation"])
    df_corrs.to_csv(os.path.join(out_dir, "tsfresh_feature_correlations.csv"), index=False)
    
    # Plot top 10 correlations
    if not df_corrs.empty:
        plt.figure(figsize=(12, 6))
        top_corrs = pd.concat([df_corrs.head(5), df_corrs.tail(5)]).sort_values("Correlation")
        sns.barplot(data=top_corrs, x="Correlation", y="Feature", palette="coolwarm")
        plt.title("Top tsfresh Feature Correlations with Mean IPC3+ (AFG)")
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, "tsfresh_top_correlations.png"), dpi=150)
        plt.close()
        
    print("tsfresh Feature Extraction Completed.")
    # Convert index back to Province column for downstream DBSCAN outlier compatibility
    X_out = X.reset_index()
    X_out.rename(columns={X_out.columns[0]: "Province"}, inplace=True)
    return X_out


def run_dynamic_clustering(df, results_dir=None, boundaries_gdf=None):
    """
    Task 3.6: Temporal Distances and Dynamic Clustering (DTW & NCD)
    """
    print("--- Running Dynamic Clustering (DTW & NCD) ---")
    out_dir = config.CLUSTERING_DIR
    
    provinces = df["Level 1"].unique()
    series_dict = {}
    
    for prov in provinces:
        prov_df = df[df["Level 1"] == prov].sort_values("reference_period_end")
        series = prov_df[config.TARGET_COL].values
        if len(series) >= 15:
            series_clean = pd.Series(series).interpolate().ffill().bfill().values
            series_dict[prov] = series_clean
            
    prov_names = list(series_dict.keys())
    n = len(prov_names)
    
    if n < 3:
        print("Not enough provinces for clustering.")
        return
        
    dtw_mat = np.zeros((n, n))
    ncd_mat = np.zeros((n, n))
    
    cleaned_series = {name: z_score_normalize(series_dict[name]) for name in prov_names}
    
    for i in range(n):
        for j in range(i, n):
            if i == j:
                dtw_mat[i, j] = 0.0
                ncd_mat[i, j] = 0.0
            else:
                s1_dtw = cleaned_series[prov_names[i]]
                s2_dtw = cleaned_series[prov_names[j]]
                s1_ncd = series_dict[prov_names[i]]
                s2_ncd = series_dict[prov_names[j]]
                
                dist_dtw = dtw_distance(s1_dtw, s2_dtw, w=4)
                dist_ncd = compute_ncd(s1_ncd, s2_ncd)
                
                dtw_mat[i, j] = dist_dtw
                dtw_mat[j, i] = dist_dtw
                ncd_mat[i, j] = dist_ncd
                ncd_mat[j, i] = dist_ncd
                
    # Save distance matrix heatmaps
    plt.figure(figsize=(10, 8))
    sns.heatmap(pd.DataFrame(dtw_mat, index=prov_names, columns=prov_names), cmap="viridis")
    plt.title("DTW Shape Distance Heatmap (AFG Provinces)")
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "global_national_dtw_heatmap.png"), dpi=150)
    plt.close()
    
    # Run hierarchical clustering on DTW
    condensed_dtw = squareform(dtw_mat)
    Z = linkage(condensed_dtw, method="ward")
    
    # Plot shape-based dendrogram
    plt.figure(figsize=(12, 6))
    dendrogram(Z, labels=prov_names, leaf_rotation=90)
    plt.title("Shape-Based Dendrogram (DTW Ward Linkage) - AFG Provinces")
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "global_regions_dendrogram_shape.png"), dpi=150)
    plt.close()
    
    k_clusters = 3
    labels = fcluster(Z, k_clusters, criterion="maxclust")
    labels_df = pd.DataFrame({
        "Province": prov_names,
        "Cluster": labels
    })
    
    labels_df.to_csv(os.path.join(out_dir, "dtw_clustering_labels.csv"), index=False)
    
    # Plot PCA projection of clustering
    min_len = min(len(s) for s in series_dict.values())
    X_feat = np.array([series_dict[name][:min_len] for name in prov_names])
    X_scaled = StandardScaler().fit_transform(X_feat)
    
    pca = PCA(n_components=2)
    X_pca = pca.fit_transform(X_scaled)
    
    plt.figure(figsize=(8, 6))
    sns.scatterplot(x=X_pca[:, 0], y=X_pca[:, 1], hue=labels, palette="Set1", s=100)
    for idx, name in enumerate(prov_names):
        plt.annotate(name, (X_pca[idx, 0], X_pca[idx, 1]), alpha=0.7, fontsize=8)
    plt.title("PCA Scatter Plot of DTW Time Series Clusters")
    plt.xlabel("PC1")
    plt.ylabel("PC2")
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "global_regions_pca_scatter.png"), dpi=150)
    plt.close()
    
    # Plot Geographical Map of Clusters
    map_gdf = boundaries_gdf.copy()
    map_gdf = map_gdf.merge(labels_df, left_on="adm1_name", right_on="Province", how="left")
    
    fig, ax = plt.subplots(1, 1, figsize=(10, 8))
    map_gdf.plot(column="Cluster", cmap="Set1", categorical=True, legend=True, ax=ax, missing_kwds={"color": "lightgrey"})
    plt.title("AFG Time Series Shape Clusters (DTW k=3)")
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "global_regions_map.png"), dpi=150)
    plt.close()
    
    print("Dynamic Clustering Analysis Completed.")
