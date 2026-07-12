import os
import warnings
# Silence statsmodels, pandas and geopandas warnings to clean output
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)

import matplotlib
matplotlib.use('Agg') # Headless plotting to prevent blocking popups
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
from tqdm import tqdm
import scipy.stats as stats
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
from statsmodels.tsa.stattools import acf, pacf

# Clustering & Dimensionality Reduction imports
from scipy.cluster.hierarchy import linkage, dendrogram, fcluster
from scipy.spatial.distance import squareform
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
import geopandas as gpd

import config
from data_loader import load_country_pcodes, load_and_align_region, load_and_align_national
from monitor import generate_country_reliability_report
from preprocessing.backcaster import backcast_impute_dataframe
from preprocessing.stationarity import check_stationarity_and_difference, run_stl_decomposition, plot_stl_decomposition, plot_acf_pacf
from preprocessing.matrix_profile import calculate_matrix_profile, plot_matrix_profile
from preprocessing.causality import run_granger_causality
from models.forecasting import train_and_compare_forecasting_models, train_and_project_ipc, forecast_univariate_variable
from similarity import compute_similarity_matrix, sax_transform, extract_structural_features, z_score_normalize

def plot_residuals_diagnostics(residuals, model_name, save_path):
    """
    Plots a 4-panel diagnostic chart for model residuals:
    1. Standardized residuals over time
    2. Histogram + KDE
    3. Normal Q-Q plot
    4. PACF plot (partial correlogram) of residuals
    """
    res = pd.Series(residuals).dropna()
    if len(res) < 5:
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.text(0.5, 0.5, "Too few residuals for diagnostics", ha='center')
        plt.savefig(save_path, dpi=100)
        plt.close()
        return
        
    std_res = (res - res.mean()) / (res.std() + 1e-9)
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    
    # 1. Residuals plot
    axes[0, 0].plot(res.index, std_res, color="black", linewidth=1.0)
    axes[0, 0].axhline(y=0, color="gray", linestyle="--")
    axes[0, 0].set_title("Standardized Residuals")
    axes[0, 0].grid(True)
    
    # 2. Histogram + KDE
    sns.histplot(std_res, kde=True, ax=axes[0, 1], color="blue", stat="density")
    x_axis = np.linspace(-4, 4, 100)
    axes[0, 1].plot(x_axis, stats.norm.pdf(x_axis, 0, 1), color="red", linestyle="--", label="Normal")
    axes[0, 1].set_title("Residuals Histogram & KDE")
    axes[0, 1].legend(loc="upper right", fontsize=8)
    axes[0, 1].grid(True)
    
    # 3. Normal Q-Q
    stats.probplot(std_res, dist="norm", plot=axes[1, 0])
    axes[1, 0].get_lines()[0].set_markerfacecolor('blue')
    axes[1, 0].get_lines()[0].set_markeredgecolor('blue')
    axes[1, 0].get_lines()[1].set_color('red')
    axes[1, 0].set_title("Normal Q-Q Plot")
    axes[1, 0].grid(True)
    
    # 4. PACF of residuals
    lag_val = min(15, len(std_res) // 2 - 1)
    if lag_val < 1:
        lag_val = 1
    plot_pacf(std_res, ax=axes[1, 1], lags=lag_val, title="Residuals Partial Autocorrelation (PACF)")
    axes[1, 1].grid(True)
    
    plt.suptitle(f"Diagnostics of Residuals: {model_name}", fontsize=14, y=0.98)
    plt.tight_layout()
    plt.savefig(save_path, dpi=120, bbox_inches="tight")
    plt.close()

def run_autocorrelation_comparison(df, target_col, predictors, region_dir, title):
    """
    Computes ACF and PACF for all available variables in the region dataset,
    compares them, computes Cross-Correlation Function (CCF) of predictors with the target IPC,
    and saves the plots and data.
    """
    import pandas as pd
    import numpy as np
    import matplotlib.pyplot as plt
    from statsmodels.tsa.stattools import acf, pacf

    # Keep only variables that exist in df and have no missing values
    variables = [target_col] + [p for p in predictors if p in df.columns]
    
    # 1. Compare Autocorrelations
    acf_data = []
    pacf_data = []
    
    lag_limit = min(12, len(df) // 2 - 1)
    if lag_limit < 2:
        lag_limit = 2
        
    for var in variables:
        try:
            series = df[var]
            # Z-normalize to make them scale-free
            series_norm = (series - series.mean()) / (series.std() + 1e-9)
            
            acf_vals = acf(series_norm, nlags=lag_limit, fft=True)
            pacf_vals = pacf(series_norm, nlags=lag_limit)
            
            for lag in range(len(acf_vals)):
                acf_data.append({"lag": lag, "variable": var, "acf": acf_vals[lag]})
                pacf_data.append({"lag": lag, "variable": var, "pacf": pacf_vals[lag]})
        except Exception as e:
            print(f"Error computing ACF/PACF for variable {var}: {e}")
            
    df_acf = pd.DataFrame(acf_data)
    df_pacf = pd.DataFrame(pacf_data)
    
    # Save CSV data
    df_acf_pivot = df_acf.pivot(index="lag", columns="variable", values="acf")
    df_pacf_pivot = df_pacf.pivot(index="lag", columns="variable", values="pacf")
    
    df_acf_pivot.to_csv(os.path.join(region_dir, "02b_Compare_Series_Autocorrelation_ACF.csv"))
    df_pacf_pivot.to_csv(os.path.join(region_dir, "02b_Compare_Series_Autocorrelation_PACF.csv"))
    
    # Plot Compare ACF and PACF
    try:
        fig, axes = plt.subplots(1, 2, figsize=(15, 6))
        for var in variables:
            var_acf = df_acf[df_acf["variable"] == var]
            var_pacf = df_pacf[df_pacf["variable"] == var]
            
            # Plot ACF
            axes[0].plot(var_acf["lag"], var_acf["acf"], marker="o", label=var)
            # Plot PACF
            axes[1].plot(var_pacf["lag"], var_pacf["pacf"], marker="o", label=var)
            
        axes[0].axhline(y=0, color="gray", linestyle="--", alpha=0.5)
        axes[0].axhline(y=1.96/np.sqrt(len(df)), color="gray", linestyle=":", alpha=0.5)
        axes[0].axhline(y=-1.96/np.sqrt(len(df)), color="gray", linestyle=":", alpha=0.5)
        axes[0].set_title("Autocorrelation Function (ACF) Comparison")
        axes[0].set_xlabel("Lag (Months)")
        axes[0].set_ylabel("Correlation")
        axes[0].grid(True)
        axes[0].legend(fontsize=8)
        
        axes[1].axhline(y=0, color="gray", linestyle="--", alpha=0.5)
        axes[1].axhline(y=1.96/np.sqrt(len(df)), color="gray", linestyle=":", alpha=0.5)
        axes[1].axhline(y=-1.96/np.sqrt(len(df)), color="gray", linestyle=":", alpha=0.5)
        axes[1].set_title("Partial Autocorrelation Function (PACF) Comparison")
        axes[1].set_xlabel("Lag (Months)")
        axes[1].set_ylabel("Partial Correlation")
        axes[1].grid(True)
        axes[1].legend(fontsize=8)
        
        plt.suptitle(f"Time Series Autocorrelation Comparison: {title}", fontsize=14)
        plt.tight_layout()
        plt.savefig(os.path.join(region_dir, "02b_Compare_Series_Autocorrelation.png"), dpi=120)
        plt.close()
    except Exception as e:
        print(f"Error plotting autocorrelation comparison: {e}")
        
    # 2. Compare Cross-Correlations with Target (CCF)
    ccf_data = []
    target_series = df[target_col]
    target_norm = (target_series - target_series.mean()) / (target_series.std() + 1e-9)
    
    pred_vars = [p for p in predictors if p in df.columns]
    for var in pred_vars:
        try:
            pred_series = df[var]
            pred_norm = (pred_series - pred_series.mean()) / (pred_series.std() + 1e-9)
            
            for lag in range(-12, 13):
                if lag < 0:
                    corr = target_norm.iloc[-lag:].corr(pred_norm.shift(lag).dropna())
                else:
                    corr = target_norm.corr(pred_norm.shift(lag))
                if pd.isna(corr):
                    corr = 0.0
                ccf_data.append({"lag": lag, "variable": var, "ccf": corr})
        except Exception as e:
            print(f"Error computing CCF for {var}: {e}")
            
    if ccf_data:
        df_ccf = pd.DataFrame(ccf_data)
        df_ccf_pivot = df_ccf.pivot(index="lag", columns="variable", values="ccf")
        df_ccf_pivot.to_csv(os.path.join(region_dir, "02c_Cross_Correlation_with_Target.csv"))
        
        # Plot CCF
        try:
            plt.figure(figsize=(12, 6))
            for var in pred_vars:
                var_ccf = df_ccf[df_ccf["variable"] == var]
                plt.plot(var_ccf["lag"], var_ccf["ccf"], marker="o", label=f"CCF({var}, Target)")
                
            plt.axhline(y=0, color="gray", linestyle="--", alpha=0.5)
            plt.axvline(x=0, color="red", linestyle=":", alpha=0.5)
            plt.axhline(y=1.96/np.sqrt(len(df)), color="gray", linestyle=":", alpha=0.5)
            plt.axhline(y=-1.96/np.sqrt(len(df)), color="gray", linestyle=":", alpha=0.5)
            
            plt.title(f"Cross-Correlation Function (CCF) with Target IPC: {title}")
            plt.xlabel("Lag (Months) [Negative: Predictor leads Target | Positive: Predictor lags Target]")
            plt.ylabel("Correlation Coefficient")
            plt.grid(True)
            plt.legend(fontsize=8)
            plt.tight_layout()
            plt.savefig(os.path.join(region_dir, "02c_Cross_Correlation_with_Target.png"), dpi=120)
            plt.close()
        except Exception as e:
            print(f"Error plotting CCF: {e}")

def run_diagnostic_and_forecast_flow(df_imputed, target_col, predictors, region_dir, title, country_code, data_dir, pcode, use_prophet=True):
    """
    Helper function to run the full diagnostic suite (STL, ADF, PACF, Matrix Profile, Granger,
    Multi-model forecasting and residual diagnostics) for a specific dataset (region or national).
    """
    target_series = df_imputed[target_col]
    
    # --- 1. Stationarity & Autocorrelation (PACF) ---
    stat_res = check_stationarity_and_difference(target_series, max_diff=2)
    plot_acf_pacf(
        stat_res["stationary_series"], 
        title=f"{title} (d={stat_res['d']})", 
        save_path=os.path.join(region_dir, "02_Autocorrelation_ACF_PACF.png")
    )
    try:
        lag_limit = min(24, len(stat_res["stationary_series"]) // 2 - 1)
        if lag_limit < 2:
            lag_limit = 2
        acf_vals = acf(stat_res["stationary_series"], nlags=lag_limit)
        pacf_vals = pacf(stat_res["stationary_series"], nlags=lag_limit)
        pd.DataFrame({
            "lag": range(len(acf_vals)),
            "acf": acf_vals,
            "pacf": pacf_vals
        }).to_csv(os.path.join(region_dir, "02_Autocorrelation_ACF_PACF.csv"), index=False)
    except Exception as e:
        print(f"Error saving ACF/PACF CSV: {e}")
        
    # Run autocorrelation comparison across all variables (target & predictors)
    run_autocorrelation_comparison(df_imputed, target_col, predictors, region_dir, title)
        
    # --- 2. STL Decomposition ---
    obs, trend, seasonal, resid = run_stl_decomposition(target_series, period=12)
    plot_stl_decomposition(
        obs, trend, seasonal, resid, 
        title=title, 
        save_path=os.path.join(region_dir, "01_Statistical_Decomposition_STL.png")
    )
    pd.DataFrame({
        "observed": obs,
        "trend": trend,
        "seasonal": seasonal,
        "residual": resid
    }, index=obs.index).to_csv(os.path.join(region_dir, "01_Statistical_Decomposition_STL.csv"))
    
    # --- 3. Granger Causality ---
    df_granger = run_granger_causality(df_imputed, target_col=target_col, predictor_cols=predictors, maxlag=6)
    if not df_granger.empty:
        df_granger.to_csv(os.path.join(region_dir, "03_Multivariate_Granger_Causality.csv"))
        
    # --- 4. Matrix Profile (Anomalies & Motifs) ---
    plot_matrix_profile(
        target_series, 
        m=12, 
        title=title, 
        save_path=os.path.join(region_dir, "04_Matrix_Profile_Anomalies_Discords.png")
    )
    try:
        mp, mp_idx, motif_pair, discord_idx = calculate_matrix_profile(target_series, m=12)
        pd.DataFrame({
            "value": target_series,
            "matrix_profile": pd.Series(mp, index=target_series.index[:len(mp)]),
            "matrix_profile_index": pd.Series(mp_idx, index=target_series.index[:len(mp)])
        }).to_csv(os.path.join(region_dir, "04_Matrix_Profile_Anomalies_Discords.csv"))
    except Exception as e:
        print(f"Error saving Matrix Profile CSV: {e}")
        
    # --- 5. Multi-Model Forecast Comparison & Residuals Diagnostics ---
    forecasts, df_comp_metrics, residuals_dict, best_model = train_and_compare_forecasting_models(
        df_imputed, 
        predictors, 
        target_col=target_col,
        use_prophet=use_prophet,
        save_dir=region_dir
    )
    
    # Save residual diagnostics and CSV (using PACF)
    if best_model in residuals_dict:
        best_resids = residuals_dict[best_model]
        plot_residuals_diagnostics(
            best_resids, 
            model_name=best_model, 
            save_path=os.path.join(region_dir, "06_Model_Residuals_Diagnostics.png")
        )
        std_resids = (best_resids - best_resids.mean()) / (best_resids.std() + 1e-9)
        pd.DataFrame({
            "raw_residuals": best_resids,
            "standardized_residuals": std_resids
        }, index=best_resids.index).to_csv(os.path.join(region_dir, "06_Model_Residuals_Diagnostics.csv"))
        
    # Generate Multi-Model plot
    ts_train = target_series.iloc[:-12]
    ts_test = target_series.iloc[-12:]
    
    fig = plt.figure(figsize=(14, 7))
    ax_main = fig.add_subplot(111)
    
    ax_main.plot(ts_train.index, ts_train, label="Historical Actual (Train)", color="black", linewidth=2.5)
    ax_main.plot(ts_test.index, ts_test, label="Historical Actual (Test)", color="black", linestyle="none", marker="o", markersize=6)
    
    colors = {"Holt-Winters": "green", "SARIMAX": "#1f77b4", "Prophet": "orange", "VAR": "purple"}
    styles = {"Holt-Winters": "-.", "SARIMAX": "--", "Prophet": ":", "VAR": "-"}
    
    for m_name, fc_series in forecasts.items():
        col_c = colors.get(m_name, "blue")
        st_s = styles.get(m_name, "-")
        ax_main.plot(fc_series.index, fc_series, label=f"{m_name} Forecast", color=col_c, linestyle=st_s, linewidth=1.8)
        
    if not df_comp_metrics[df_comp_metrics["Model"] == best_model].empty:
        best_rmse = df_comp_metrics[df_comp_metrics["Model"] == best_model]["RMSE"].values[0]
        best_fc = forecasts[best_model]
        ax_main.fill_between(
            best_fc.index, 
            np.clip(best_fc - 1.96 * best_rmse, 0, 100), 
            np.clip(best_fc + 1.96 * best_rmse, 0, 100), 
            color="blue", alpha=0.1, label=f"{best_model} 95% Conf. Int."
        )
        
    ax_main.axvline(x=ts_train.index[-1], color="red", linestyle=":", linewidth=2, label="Forecast/Validation Split")
    ax_main.set_title(f"Multi-Model Forecast Comparison: {title} ({country_code})", fontsize=14)
    ax_main.set_ylabel("% Population in Phase 3+", fontsize=12)
    ax_main.grid(True)
    
    # Embed Table
    table_text = "Model        | Test MAE | Test RMSE | Test R2 | White Noise?\n"
    table_text += "-" * 62 + "\n"
    for _, r in df_comp_metrics.iterrows():
        wn = "Sì" if r["Ljung-Box p-val"] > 0.05 else "No"
        r2_val = f"{r['R2']:.2f}" if 'R2' in r else "N/A"
        table_text += f"{r['Model']:<12} | {r['MAE']:>7.2f}% | {r['RMSE']:>8.2f}% | {r2_val:>7} | {wn} (p={r['Ljung-Box p-val']:.2f})\n"
        
    ax_main.text(
        0.02, 0.05, table_text, 
        transform=ax_main.transAxes, 
        fontsize=8, 
        family='monospace', 
        bbox=dict(facecolor='white', alpha=0.9, edgecolor='gray')
    )
    ax_main.legend(loc="upper right", fontsize=8)
    
    comp_plot_path = os.path.join(region_dir, "05_MultiModel_Forecast_Comparison.png")
    plt.savefig(comp_plot_path, dpi=120, bbox_inches="tight")
    plt.close()
    
    # Save raw Multi-Model Comparison data to CSV
    df_fc_csv = pd.DataFrame({"actual": target_series})
    df_fc_csv["actual_train"] = ts_train
    df_fc_csv["actual_test"] = ts_test
    for m_name, fc_series in forecasts.items():
        df_fc_csv[f"forecast_{m_name.lower().replace(' ', '_')}"] = fc_series
    df_fc_csv.to_csv(os.path.join(region_dir, "05_MultiModel_Forecast_Comparison.csv"))
    
    # --- 6. Standard Future Projection (12m ahead) ---
    forecast_index = pd.date_range(start=df_imputed.index[-1] + pd.DateOffset(months=1), periods=config.FORECAST_STEPS, freq="MS")
    df_forecasted_predictors = pd.DataFrame(index=forecast_index)
    
    for pred in predictors:
        df_forecasted_predictors[pred] = forecast_univariate_variable(df_imputed[pred], steps=config.FORECAST_STEPS, variable_name=pred)
        
    df_forecasted_predictors.to_csv(os.path.join(data_dir, f"{pcode.lower()}_forecasted_predictors.csv"))
    
    df_fitted, df_projected, rf_metrics, _ = train_and_project_ipc(df_imputed, df_forecasted_predictors, predictors)
    
    df_fitted.to_csv(os.path.join(data_dir, f"{pcode.lower()}_fitted_ipc.csv"))
    df_projected.to_csv(os.path.join(data_dir, f"{pcode.lower()}_projected_ipc.csv"))
    
    return rf_metrics, resid

def process_country_pipeline(country_code):
    """
    Orchestrates the TSA pipeline for a country:
    1. Computes reliability report for regions.
    2. Runs optimized diagnostics (ADF, STL, ACF/PACF, Matrix Profile, Forecasts)
       ONLY on the target IPC variable for all regions (optimized: no Prophet at regional level).
    3. Performs Z-normalized shape-based and feature-based clustering on target IPC.
    4. Builds and plots the Temporal Anomaly Heatmap of target IPC residuals.
    5. Aggregates all data to a National level and runs the complete advanced TSA diagnostics/models.
    
    Returns:
       - country_region_features (list of features dicts)
       - country_national_feature (dict of national features)
       - country_national_series (Series of national target IPC)
    """
    print(f"\n==================================================")
    print(f"PROCESSING COUNTRY: {country_code}")
    print(f"==================================================")
    
    country_results_dir = os.path.join(config.RESULTS_DIR, country_code)
    diag_base_dir = os.path.join(country_results_dir, "diagnostics")
    data_dir = os.path.join(country_results_dir, "data")
    clustering_dir = os.path.join(country_results_dir, "clustering")
    
    os.makedirs(diag_base_dir, exist_ok=True)
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(clustering_dir, exist_ok=True)
    
    # --- Step 1: Reliability Report ---
    try:
        rel_report = generate_country_reliability_report(country_code)
        report_csv = os.path.join(country_results_dir, f"{country_code}_reliability_report.csv")
        rel_report.to_csv(report_csv, index=False)
    except Exception as e:
        print(f"Failed to generate reliability report for {country_code}: {e}")
        
    # --- Step 2: Processing Regions ---
    regions = load_country_pcodes(country_code)
    metrics_rows = []
    ipc_series_dict = {}
    structural_features_list = []
    residuals_dict = {}
    
    target_col = "ipc_phase_3plus_pct"
    
    # Process regions
    for pcode, name in tqdm(regions, desc=f"Regions of {country_code}"):
        clean_name = name.replace(" ", "_").replace("/", "_").replace("-", "_")
        region_diag_dir = os.path.join(diag_base_dir, f"{country_code}_{clean_name}_{pcode}")
        
        try:
            df_aligned = load_and_align_region(country_code, pcode)
            if len(df_aligned) < 24:
                continue
                
            os.makedirs(region_diag_dir, exist_ok=True)
            df_aligned.to_csv(os.path.join(data_dir, f"{pcode.lower()}_aligned.csv"))
            
            df_imputed = backcast_impute_dataframe(df_aligned)
            df_imputed.to_csv(os.path.join(data_dir, f"{pcode.lower()}_imputed.csv"))
            
            target_series = df_imputed[target_col]
            ipc_series_dict[name] = target_series
            
            # Structural features
            feat = extract_structural_features(target_series)
            feat["adm1_pcode"] = pcode
            feat["region_name"] = name
            feat["country"] = country_code
            structural_features_list.append(feat)
            
            # Region diagnostics (use_prophet=False for speed)
            rf_metrics, resid = run_diagnostic_and_forecast_flow(
                df_imputed, 
                target_col=target_col, 
                predictors=config.PREDICTORS, 
                region_dir=region_diag_dir, 
                title=f"{name} - Target IPC", 
                country_code=country_code,
                data_dir=data_dir,
                pcode=pcode,
                use_prophet=False
            )
            
            residuals_dict[name] = z_score_normalize(resid)
            
            metrics_rows.append({
                "adm1_pcode": pcode,
                "region_name": name,
                "rf_mae": round(rf_metrics["rf"]["MAE"], 3),
                "rf_rmse": round(rf_metrics["rf"]["RMSE"], 3),
                "rf_r2": round(rf_metrics["rf"]["R2"], 3),
                "ridge_mae": round(rf_metrics["ridge"]["MAE"], 3),
                "ridge_rmse": round(rf_metrics["ridge"]["RMSE"], 3),
                "ridge_r2": round(rf_metrics["ridge"]["R2"], 3)
            })
        except Exception as e:
            pass
            
    # Save overall metrics report
    if metrics_rows:
        df_metrics = pd.DataFrame(metrics_rows)
        metrics_csv = os.path.join(country_results_dir, f"{country_code}_forecasting_metrics.csv")
        df_metrics.to_csv(metrics_csv, index=False)
        
    # Save structural features report
    if structural_features_list:
        df_feat = pd.DataFrame(structural_features_list)
        cols = ["country", "adm1_pcode", "region_name"] + [c for c in df_feat.columns if c not in ["country", "adm1_pcode", "region_name"]]
        df_feat = df_feat[cols]
        feat_csv = os.path.join(country_results_dir, f"{country_code}_structural_features.csv")
        df_feat.to_csv(feat_csv, index=False)
        
    # --- Step 3: Similarity Matching & Clustering (DTW/Euclidean/SAX) ---
    if len(ipc_series_dict) >= 2:
        try:
            # DTW similarity (Z-Normalized)
            dtw_matrix = compute_similarity_matrix(ipc_series_dict, method="dtw", w=12)
            dtw_matrix.to_csv(os.path.join(clustering_dir, "DTW_Distance_Matrix.csv"))
            
            eucl_matrix = compute_similarity_matrix(ipc_series_dict, method="euclidean")
            eucl_matrix.to_csv(os.path.join(clustering_dir, "Euclidean_Distance_Matrix.csv"))
            
            # Plot Heatmap with viridis
            plt.figure(figsize=(12, 10))
            sns.heatmap(dtw_matrix, annot=False, cmap="viridis", cbar_kws={'label': 'DTW Distance (Z-Normalized)'})
            plt.title(f"Pairwise DTW Distance Heatmap (IPC Shape): {country_code}")
            plt.tight_layout()
            heatmap_path = os.path.join(country_results_dir, f"{country_code}_dtw_heatmap.png")
            plt.savefig(heatmap_path, dpi=150, bbox_inches="tight")
            plt.close()
            
            # SAX mapping
            sax_rows = []
            for r_name, series in ipc_series_dict.items():
                sax_str = sax_transform(series, w_segments=10, a_size=4)
                sax_rows.append({"region_name": r_name, "sax_representation": sax_str})
            df_sax = pd.DataFrame(sax_rows)
            
            # 3.1. Shape-Based Hierarchical
            condensed_dist = squareform(dtw_matrix, checks=False)
            Z_linkage_shape = linkage(condensed_dist, method='average')
            labels_hier_shape = fcluster(Z_linkage_shape, t=min(4, len(ipc_series_dict)), criterion='maxclust')
            
            plt.figure(figsize=(12, 6))
            dendrogram(Z_linkage_shape, labels=dtw_matrix.index, leaf_rotation=90, leaf_font_size=8)
            plt.title(f"Hierarchical Clustering Dendrogram (DTW Shape-Based) - {country_code}")
            plt.ylabel("Warping Distance")
            plt.tight_layout()
            dendrogram_shape_path = os.path.join(clustering_dir, "Hierarchical_Dendrogram_Shape.png")
            plt.savefig(dendrogram_shape_path, dpi=150)
            plt.close()
            
            # 3.2. Feature-Based Hierarchical
            feats = df_feat.drop(columns=["country", "adm1_pcode", "region_name"]).ffill().bfill().fillna(0.0)
            X_scaled = StandardScaler().fit_transform(feats)
            Z_linkage_feat = linkage(X_scaled, method='ward')
            labels_hier_feat = fcluster(Z_linkage_feat, t=min(4, len(ipc_series_dict)), criterion='maxclust')
            
            plt.figure(figsize=(12, 6))
            dendrogram(Z_linkage_feat, labels=df_feat["region_name"].values, leaf_rotation=90, leaf_font_size=8)
            plt.title(f"Hierarchical Clustering Dendrogram (Feature-Based) - {country_code}")
            plt.ylabel("Linkage Distance (Ward)")
            plt.tight_layout()
            dendrogram_feat_path = os.path.join(clustering_dir, "Hierarchical_Dendrogram_Features.png")
            plt.savefig(dendrogram_feat_path, dpi=150)
            plt.close()
            
            # 3.3. Feature-Based K-Means
            pca = PCA(n_components=2)
            X_pca = pca.fit_transform(X_scaled)
            kmeans = KMeans(n_clusters=min(4, len(ipc_series_dict)), random_state=42, n_init=10)
            labels_km = kmeans.fit_predict(X_pca)
            
            plt.figure(figsize=(10, 8))
            sns.scatterplot(x=X_pca[:, 0], y=X_pca[:, 1], hue=labels_km, palette="tab10", style=labels_km, s=100)
            for idx, r_name in enumerate(df_feat["region_name"]):
                plt.annotate(r_name, (X_pca[idx, 0] + 0.05, X_pca[idx, 1] + 0.05), fontsize=8, alpha=0.8)
            plt.title(f"Feature-Based PCA Scatter Plot (K-Means Clustering) - {country_code}")
            plt.xlabel("Principal Component 1")
            plt.ylabel("Principal Component 2")
            plt.legend(title="Cluster")
            plt.tight_layout()
            pca_scatter_path = os.path.join(clustering_dir, "Feature_Based_PCA_Scatter.png")
            plt.savefig(pca_scatter_path, dpi=150)
            plt.close()
            
            # 3.4. Choropleth Map with GeoPandas
            geojson_path = os.path.join(config.DATA_DIR, "boundaries", country_code.lower(), f"{country_code.lower()}_admin1.geojson")
            if os.path.exists(geojson_path):
                try:
                    gdf = gpd.read_file(geojson_path)
                    df_clusters = pd.DataFrame({
                        "adm1_pcode": df_feat["adm1_pcode"],
                        "region_name": df_feat["region_name"],
                        "hierarchical_shape_cluster": labels_hier_shape,
                        "hierarchical_feature_cluster": labels_hier_feat,
                        "kmeans_feature_cluster": labels_km
                    })
                    gdf_merged = gdf.merge(df_clusters, on="adm1_pcode", how="left")
                    
                    fig, axes = plt.subplots(1, 2, figsize=(20, 10))
                    gdf_merged.plot(column="hierarchical_shape_cluster", cmap="tab10", legend=True, categorical=True, 
                                    ax=axes[0], missing_kwds={"color": "lightgrey"})
                    axes[0].set_title("Shape-Based Clusters (DTW + Hierarchical)", fontsize=14)
                    axes[0].axis("off")
                    
                    gdf_merged.plot(column="hierarchical_feature_cluster", cmap="tab10", legend=True, categorical=True, 
                                    ax=axes[1], missing_kwds={"color": "lightgrey"})
                    axes[1].set_title("Feature-Based Clusters (Ward + Hierarchical)", fontsize=14)
                    axes[1].axis("off")
                    
                    plt.tight_layout()
                    map_plot_path = os.path.join(clustering_dir, "Cluster_Map_Admin1.png")
                    plt.savefig(map_plot_path, dpi=150, bbox_inches="tight")
                    plt.close()
                except Exception as e:
                    pass
                    
            # 3.5. Save Labels
            df_clusters_csv = pd.DataFrame({
                "adm1_pcode": df_feat["adm1_pcode"],
                "region_name": df_feat["region_name"],
                "hierarchical_shape_cluster": labels_hier_shape,
                "hierarchical_feature_cluster": labels_hier_feat,
                "kmeans_feature_cluster": labels_km,
                "sax_representation": df_sax["sax_representation"]
            })
            labels_csv_path = os.path.join(clustering_dir, f"{country_code}_clustering_labels.csv")
            df_clusters_csv.to_csv(labels_csv_path, index=False)
        except Exception as e:
            pass
            
    # --- Step 4: Temporal Anomaly Heatmap (Shock Sistemici) ---
    if len(residuals_dict) >= 2:
        try:
            df_anomalies = pd.DataFrame(residuals_dict)
            df_anomalies_T = df_anomalies.T
            
            anom_csv = os.path.join(country_results_dir, f"{country_code}_temporal_anomalies.csv")
            df_anomalies_T.to_csv(anom_csv)
            
            plt.figure(figsize=(16, 10))
            sns.heatmap(df_anomalies_T, cmap="coolwarm", center=0, cbar_kws={'label': 'IPC Residuals (Z-Normalized)'})
            
            ax = plt.gca()
            xticks = range(0, len(df_anomalies.index), 6)
            ax.set_xticks([x + 0.5 for x in xticks])
            ax.set_xticklabels([df_anomalies.index[x].strftime('%Y-%m') for x in xticks], rotation=45, ha='right', fontsize=8)
            ax.set_yticklabels(df_anomalies_T.index, fontsize=8)
            
            plt.title(f"Temporal Anomaly Map (Shock IPC): {country_code}")
            plt.xlabel("Date")
            plt.ylabel("Region")
            plt.tight_layout()
            
            heatmap_anom_path = os.path.join(country_results_dir, f"{country_code}_temporal_anomalies.png")
            plt.savefig(heatmap_anom_path, dpi=150, bbox_inches="tight")
            plt.close()
        except Exception as e:
            pass
            
    # --- Step 5: National Aggregated Dataset Analysis ---
    national_feature = None
    national_series = None
    try:
        national_diag_dir = os.path.join(country_results_dir, "national")
        os.makedirs(national_diag_dir, exist_ok=True)
        
        df_aligned_nat = load_and_align_national(country_code)
        df_aligned_nat.to_csv(os.path.join(national_diag_dir, "national_aligned.csv"))
        
        df_imputed_nat = backcast_impute_dataframe(df_aligned_nat)
        df_imputed_nat.to_csv(os.path.join(national_diag_dir, "national_imputed.csv"))
        
        national_series = df_imputed_nat[target_col]
        national_feature = extract_structural_features(national_series)
        national_feature["country"] = country_code
        
        # National diagnostics (use_prophet=True is fully active here!)
        run_diagnostic_and_forecast_flow(
            df_imputed_nat, 
            target_col=target_col, 
            predictors=config.PREDICTORS, 
            region_dir=national_diag_dir, 
            title=f"National Aggregated - {country_code}", 
            country_code=country_code,
            data_dir=national_diag_dir,
            pcode="national",
            use_prophet=True
        )
    except Exception as e:
        print(f"Error running national aggregated pipeline for {country_code}: {e}")
        
    return structural_features_list, national_feature, national_series

def run_global_cross_country_analysis(global_region_features, global_national_features, global_national_series):
    """
    Computes global cross-region feature clustering and cross-country national shape/feature clustering.
    Saves results to results/global/.
    """
    global_dir = os.path.join(config.RESULTS_DIR, "global")
    os.makedirs(global_dir, exist_ok=True)
    print(f"\n==================================================")
    print(f"RUNNING GLOBAL CROSS-COUNTRY CLUSTERING ANALYSIS")
    print(f"==================================================")
    
    # 1. Global Region-Level Feature Clustering
    if len(global_region_features) >= 4:
        print("\n--- 1. Global Region Feature-Based Clustering ---")
        df_reg = pd.DataFrame(global_region_features)
        df_reg.to_csv(os.path.join(global_dir, "global_regions_raw_features.csv"), index=False)
        
        feats = df_reg.drop(columns=["country", "adm1_pcode", "region_name"]).ffill().bfill().fillna(0.0)
        X_scaled = StandardScaler().fit_transform(feats)
        
        # A. Dendrogram
        Z_reg = linkage(X_scaled, method='ward')
        labels_hier_reg = fcluster(Z_reg, t=5, criterion='maxclust')
        
        plt.figure(figsize=(16, 8))
        dendrogram(Z_reg, labels=(df_reg["country"] + "_" + df_reg["region_name"]).values, leaf_rotation=90, leaf_font_size=6)
        plt.title("Global Hierarchical Clustering Dendrogram (Feature-Based - All Regions)")
        plt.ylabel("Ward Distance")
        plt.tight_layout()
        plt.savefig(os.path.join(global_dir, "global_regions_dendrogram.png"), dpi=150)
        plt.close()
        
        # B. PCA + K-Means
        pca = PCA(n_components=2)
        X_pca = pca.fit_transform(X_scaled)
        kmeans = KMeans(n_clusters=5, random_state=42, n_init=10)
        labels_km_reg = kmeans.fit_predict(X_pca)
        
        plt.figure(figsize=(12, 10))
        sns.scatterplot(x=X_pca[:, 0], y=X_pca[:, 1], hue=labels_km_reg, palette="tab10", style=df_reg["country"], s=80)
        plt.title("Global Feature-Based PCA Scatter Plot (All Admin Regions)")
        plt.xlabel("Principal Component 1")
        plt.ylabel("Principal Component 2")
        plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left', title="Cluster / Country")
        plt.tight_layout()
        plt.savefig(os.path.join(global_dir, "global_regions_pca_scatter.png"), dpi=150)
        plt.close()
        
        # Save CSV
        df_reg_labels = pd.DataFrame({
            "country": df_reg["country"],
            "adm1_pcode": df_reg["adm1_pcode"],
            "region_name": df_reg["region_name"],
            "hierarchical_region_cluster": labels_hier_reg,
            "kmeans_region_cluster": labels_km_reg
        })
        df_reg_labels.to_csv(os.path.join(global_dir, "global_regions_clustering_labels.csv"), index=False)
        print("Saved global regions clustering outputs.")
        
        # C. Plot Global World Map of Regional Clusters
        print("\n--- 1.1. Plotting Global Regions World Map ---")
        try:
            # Load world map background
            world_url = 'https://raw.githubusercontent.com/datasets/geo-boundaries-world-110m/master/countries.geojson'
            world = gpd.read_file(world_url)
            world = world[world["continent"] != "Antarctica"]
            
            # Load all available regional boundaries
            gdfs = []
            for c in df_reg["country"].unique():
                path = os.path.join(config.DATA_DIR, "boundaries", c.lower(), f"{c.lower()}_admin1.geojson")
                if os.path.exists(path):
                    try:
                        gdf_c = gpd.read_file(path)
                        pcode_col = None
                        for col in gdf_c.columns:
                            if col.lower() == 'adm1_pcode':
                                pcode_col = col
                                break
                        if pcode_col:
                            gdf_c = gdf_c[[pcode_col, "geometry"]].rename(columns={pcode_col: "adm1_pcode"})
                            gdf_c["country"] = c
                            gdfs.append(gdf_c)
                    except Exception:
                        pass
            
            if gdfs:
                gdf_all_regions = pd.concat(gdfs, ignore_index=True)
                gdf_regions_merged = gdf_all_regions.merge(df_reg_labels, on="adm1_pcode", how="left")
                
                fig, axes = plt.subplots(1, 2, figsize=(24, 10))
                
                # Panel 1: Hierarchical Regional Clusters
                world.plot(ax=axes[0], color="#e5e5e5", edgecolor="#ffffff", linewidth=0.4)
                gdf_regions_merged.dropna(subset=["hierarchical_region_cluster"]).plot(
                    column="hierarchical_region_cluster", cmap="tab10", legend=True, categorical=True,
                    ax=axes[0], edgecolor="none"
                )
                axes[0].set_title("Global Admin1 Region Clusters (Ward + Hierarchical)", fontsize=14)
                axes[0].axis("off")
                
                # Panel 2: KMeans Regional Clusters
                world.plot(ax=axes[1], color="#e5e5e5", edgecolor="#ffffff", linewidth=0.4)
                gdf_regions_merged.dropna(subset=["kmeans_region_cluster"]).plot(
                    column="kmeans_region_cluster", cmap="tab10", legend=True, categorical=True,
                    ax=axes[1], edgecolor="none"
                )
                axes[1].set_title("Global Admin1 Region Clusters (PCA + K-Means)", fontsize=14)
                axes[1].axis("off")
                
                plt.tight_layout()
                reg_map_path = os.path.join(global_dir, "global_regions_map.png")
                plt.savefig(reg_map_path, dpi=150, bbox_inches="tight")
                plt.close()
                print(f"Saved Global Regions Map to {reg_map_path}")
            else:
                print("No regional boundary files found. Skipping regional world map.")
        except Exception as e:
            print(f"Error drawing regional world map: {e}")

    # 2. Global National-Level Shape & Feature Clustering
    if len(global_national_features) >= 2:
        print("\n--- 2. Global National Feature-Based Clustering ---")
        df_nat = pd.DataFrame(global_national_features)
        df_nat.to_csv(os.path.join(global_dir, "global_national_raw_features.csv"), index=False)
        
        feats_nat = df_nat.drop(columns=["country"]).ffill().bfill().fillna(0.0)
        X_scaled_nat = StandardScaler().fit_transform(feats_nat)
        
        # A. Feature Dendrogram
        Z_nat = linkage(X_scaled_nat, method='ward')
        labels_hier_nat = fcluster(Z_nat, t=min(4, len(df_nat)), criterion='maxclust')
        
        plt.figure(figsize=(10, 6))
        dendrogram(Z_nat, labels=df_nat["country"].values, leaf_rotation=45, leaf_font_size=10)
        plt.title("Global National Hierarchical Clustering Dendrogram (Feature-Based)")
        plt.ylabel("Ward Distance")
        plt.tight_layout()
        plt.savefig(os.path.join(global_dir, "global_national_dendrogram_features.png"), dpi=150)
        plt.close()
        
        # B. PCA + K-Means
        pca_nat = PCA(n_components=2)
        X_pca_nat = pca_nat.fit_transform(X_scaled_nat)
        kmeans_nat = KMeans(n_clusters=min(4, len(df_nat)), random_state=42, n_init=10)
        labels_km_nat = kmeans_nat.fit_predict(X_pca_nat)
        
        plt.figure(figsize=(10, 8))
        sns.scatterplot(x=X_pca_nat[:, 0], y=X_pca_nat[:, 1], hue=labels_km_nat, palette="tab10", s=150)
        for idx, country_c in enumerate(df_nat["country"]):
            plt.annotate(country_c, (X_pca_nat[idx, 0] + 0.05, X_pca_nat[idx, 1] + 0.05), fontsize=10, weight='bold')
        plt.title("Global National Feature-Based PCA Scatter Plot (All Countries)")
        plt.xlabel("Principal Component 1")
        plt.ylabel("Principal Component 2")
        plt.legend(title="Cluster")
        plt.tight_layout()
        plt.savefig(os.path.join(global_dir, "global_national_pca_scatter.png"), dpi=150)
        plt.close()
        
        # C. Global National Shape Similarity (DTW on Common Dates)
        print("\n--- 3. Global National Shape-Based Clustering (DTW) ---")
        labels_shape_nat = [np.nan] * len(df_nat)
        try:
            countries_list = list(global_national_series.keys())
            common_idx = global_national_series[countries_list[0]].index
            for c in countries_list[1:]:
                common_idx = common_idx.intersection(global_national_series[c].index)
                
            if len(common_idx) >= 12:
                # Reindex series
                sliced_series = {c: global_national_series[c].reindex(common_idx) for c in countries_list}
                dtw_matrix = compute_similarity_matrix(sliced_series, method="dtw", w=12)
                dtw_matrix.to_csv(os.path.join(global_dir, "global_national_dtw_distance_matrix.csv"))
                
                # Plot Heatmap
                plt.figure(figsize=(12, 10))
                sns.heatmap(dtw_matrix, annot=False, cmap="viridis", cbar_kws={'label': 'DTW Distance (Z-Normalized)'})
                plt.title("Pairwise DTW Distance Heatmap (National aggregated IPC Shape Similarity)", fontsize=12)
                plt.tight_layout()
                plt.savefig(os.path.join(global_dir, "global_national_dtw_heatmap.png"), dpi=150)
                plt.close()
                
                # Plot Shape Dendrogram
                condensed_dist = squareform(dtw_matrix, checks=False)
                Z_shape_nat = linkage(condensed_dist, method='average')
                labels_shape_nat_arr = fcluster(Z_shape_nat, t=min(4, len(countries_list)), criterion='maxclust')
                
                # Map back to df_nat order
                shape_label_dict = dict(zip(countries_list, labels_shape_nat_arr))
                labels_shape_nat = [shape_label_dict.get(c, np.nan) for c in df_nat["country"]]
                
                plt.figure(figsize=(10, 6))
                dendrogram(Z_shape_nat, labels=dtw_matrix.index, leaf_rotation=45, leaf_font_size=10)
                plt.title("Global National Hierarchical Clustering Dendrogram (Shape-Based DTW)")
                plt.ylabel("Warping Distance")
                plt.tight_layout()
                plt.savefig(os.path.join(global_dir, "global_national_dendrogram_shape.png"), dpi=150)
                plt.close()
            else:
                print("Too short common date intersection for DTW. Skipping national DTW clustering.")
        except Exception as e:
            print(f"Error during national DTW clustering: {e}")
            
        # C2. Global National Compression-Based Similarity (NCD)
        print("\n--- 3.5. Global National Compression-Based Clustering (NCD) ---")
        labels_compression_nat = [np.nan] * len(df_nat)
        try:
            import zlib
            countries_list = list(global_national_series.keys())
            
            # We want to use Z-normalized series values
            # To ensure consistent length, let's find the intersection of all dates first
            common_idx = global_national_series[countries_list[0]].index
            for c in countries_list[1:]:
                common_idx = common_idx.intersection(global_national_series[c].index)
                
            if len(common_idx) >= 12:
                # Pairwise NCD matrix
                ncd_matrix = pd.DataFrame(index=countries_list, columns=countries_list, dtype=float)
                for c1 in countries_list:
                    for c2 in countries_list:
                        if c1 == c2:
                            ncd_matrix.loc[c1, c2] = 0.0
                        else:
                            s1 = global_national_series[c1].reindex(common_idx)
                            s2 = global_national_series[c2].reindex(common_idx)
                            
                            # Z-normalize
                            s1_norm = (s1 - s1.mean()) / (s1.std() + 1e-9)
                            s2_norm = (s2 - s2.mean()) / (s2.std() + 1e-9)
                            
                            # Convert to float32 bytes
                            b1 = s1_norm.values.astype(np.float32).tobytes()
                            b2 = s2_norm.values.astype(np.float32).tobytes()
                            
                            c1_size = len(zlib.compress(b1))
                            c2_size = len(zlib.compress(b2))
                            c12_size = len(zlib.compress(b1 + b2))
                            
                            ncd = (c12_size - min(c1_size, c2_size)) / max(c1_size, c2_size)
                            ncd_matrix.loc[c1, c2] = ncd
                
                ncd_matrix.to_csv(os.path.join(global_dir, "global_national_ncd_distance_matrix.csv"))
                
                # Plot NCD Heatmap
                plt.figure(figsize=(12, 10))
                sns.heatmap(ncd_matrix, annot=False, cmap="viridis", cbar_kws={'label': 'NCD Distance (Compression-Based)'})
                plt.title("Pairwise NCD Distance Heatmap (National aggregated IPC)", fontsize=12)
                plt.tight_layout()
                plt.savefig(os.path.join(global_dir, "global_national_ncd_heatmap.png"), dpi=150)
                plt.close()
                
                # Plot NCD Dendrogram
                condensed_ncd = squareform(ncd_matrix, checks=False)
                Z_ncd_nat = linkage(condensed_ncd, method='average')
                labels_ncd_nat_arr = fcluster(Z_ncd_nat, t=min(4, len(countries_list)), criterion='maxclust')
                
                ncd_label_dict = dict(zip(countries_list, labels_ncd_nat_arr))
                labels_compression_nat = [ncd_label_dict.get(c, np.nan) for c in df_nat["country"]]
                
                plt.figure(figsize=(10, 6))
                dendrogram(Z_ncd_nat, labels=ncd_matrix.index, leaf_rotation=45, leaf_font_size=10)
                plt.title("Global National Hierarchical Clustering Dendrogram (Compression-Based NCD)")
                plt.ylabel("NCD Distance")
                plt.tight_layout()
                plt.savefig(os.path.join(global_dir, "global_national_dendrogram_compression.png"), dpi=150)
                plt.close()
            else:
                print("Too short common date intersection for NCD. Skipping national NCD clustering.")
        except Exception as e:
            print(f"Error during national NCD clustering: {e}")
            
        # Save CSV national labels
        df_nat_labels = pd.DataFrame({
            "country": df_nat["country"],
            "hierarchical_feature_cluster": labels_hier_nat,
            "kmeans_feature_cluster": labels_km_nat,
            "hierarchical_shape_cluster": labels_shape_nat,
            "hierarchical_compression_cluster": labels_compression_nat
        })
        df_nat_labels.to_csv(os.path.join(global_dir, "global_national_clustering_labels.csv"), index=False)
        print("Saved global national clustering outputs.")
        
        # D. Plot Global World Map of National Clusters
        print("\n--- 4. Plotting Global National World Map ---")
        try:
            world_url = 'https://raw.githubusercontent.com/datasets/geo-boundaries-world-110m/master/countries.geojson'
            world = gpd.read_file(world_url)
            world = world[world["continent"] != "Antarctica"]
            
            world_merged = world.merge(df_nat_labels, left_on="iso_a3", right_on="country", how="left")
            
            fig, axes = plt.subplots(1, 2, figsize=(24, 10))
            
            # Panel 1: Hierarchical Feature Clusters
            world.plot(ax=axes[0], color="#e5e5e5", edgecolor="#ffffff", linewidth=0.4)
            world_merged.dropna(subset=["hierarchical_feature_cluster"]).plot(
                column="hierarchical_feature_cluster", cmap="tab10", legend=True, categorical=True,
                ax=axes[0], edgecolor="#ffffff", linewidth=0.6
            )
            axes[0].set_title("Global National Clusters (Ward + Hierarchical)", fontsize=14)
            axes[0].axis("off")
            
            # Panel 2: KMeans Feature Clusters
            world.plot(ax=axes[1], color="#e5e5e5", edgecolor="#ffffff", linewidth=0.4)
            world_merged.dropna(subset=["kmeans_feature_cluster"]).plot(
                column="kmeans_feature_cluster", cmap="tab10", legend=True, categorical=True,
                ax=axes[1], edgecolor="#ffffff", linewidth=0.6
            )
            axes[1].set_title("Global National Clusters (PCA + K-Means)", fontsize=14)
            axes[1].axis("off")
            
            plt.tight_layout()
            nat_map_path = os.path.join(global_dir, "global_national_map.png")
            plt.savefig(nat_map_path, dpi=150, bbox_inches="tight")
            plt.close()
            print(f"Saved Global National Map to {nat_map_path}")
        except Exception as e:
            print(f"Error drawing national world map: {e}")

if __name__ == "__main__":
    global_region_features = []
    global_national_features = []
    global_national_series = {}
    
    # Process target countries
    for code in config.TARGET_COUNTRIES:
        try:
            r_feats, n_feat, n_series = process_country_pipeline(code)
            if r_feats:
                global_region_features.extend(r_feats)
            if n_feat is not None:
                global_national_features.append(n_feat)
            if n_series is not None:
                global_national_series[code] = n_series
        except Exception as e:
            print(f"Failed completely to run pipeline for country {code}: {e}")
            
    # Run global cross-country and cross-region analysis
    try:
        run_global_cross_country_analysis(global_region_features, global_national_features, global_national_series)
    except Exception as e:
        print(f"Failed to run global cross-country analysis: {e}")
        import traceback
        traceback.print_exc()
        
    print("\nAll tasks completed successfully!")
