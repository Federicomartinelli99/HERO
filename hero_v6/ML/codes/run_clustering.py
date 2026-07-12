import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.cluster.hierarchy import linkage, dendrogram, fcluster
from scipy.spatial.distance import squareform
from scipy.stats import norm
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from statsmodels.tsa.ar_model import AutoReg
import geopandas as gpd
import warnings

# Suppress warnings for clean execution logs
warnings.filterwarnings("ignore")

# Define directories relative to this file
cwd = os.path.dirname(os.path.abspath(__file__)) if "__file__" in locals() else os.getcwd()
ml_dir = os.path.abspath(os.path.join(cwd, ".."))
hero_dir = os.path.abspath(os.path.join(ml_dir, ".."))
data_dir = os.path.join(hero_dir, "data")
merged_parquet = os.path.join(data_dir, "merged", "merged_adm1_wide_con_coordinate.parquet")
results_dir = os.path.join(ml_dir, "results")

os.makedirs(results_dir, exist_ok=True)
os.makedirs(os.path.join(results_dir, "global"), exist_ok=True)

print(f"ML Directory: {ml_dir}")
print(f"Results Directory: {results_dir}")
print(f"Data File: {merged_parquet}")

# --- Helper Functions from TSA for Consistency ---

def z_score_normalize(series):
    s_std = series.std()
    if s_std == 0 or np.isnan(s_std):
        return series - series.mean()
    return (series - series.mean()) / s_std

def dtw_distance(s1, s2, w=None):
    a1, a2 = np.array(s1), np.array(s2)
    n, m = len(a1), len(a2)
    
    dtw_matrix = np.full((n + 1, m + 1), np.inf)
    dtw_matrix[0, 0] = 0.0
    
    if w is None:
        w = max(n, m)
    else:
        w = max(int(w), abs(n - m))
        
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

def compute_similarity_matrix(series_dict, method="dtw", w=None):
    names = list(series_dict.keys())
    n = len(names)
    matrix = np.zeros((n, n))
    
    cleaned_series = {}
    for name in names:
        s = pd.Series(series_dict[name]).interpolate(method="linear").ffill().bfill()
        cleaned_series[name] = z_score_normalize(s)
        
    for i in range(n):
        for j in range(i, n):
            name_i, name_j = names[i], names[j]
            s_i, s_j = cleaned_series[name_i], cleaned_series[name_j]
            
            if i == j:
                dist = 0.0
            else:
                if method == "dtw":
                    dist = dtw_distance(s_i, s_j, w=w)
                elif method == "euclidean":
                    dist = np.sqrt(np.mean((s_i - s_j) ** 2))
                else:
                    raise ValueError(f"Unknown similarity method: {method}")
                    
            matrix[i, j] = dist
            matrix[j, i] = dist
            
    df_matrix = pd.DataFrame(matrix, index=names, columns=names)
    return df_matrix

def calculate_hurst(series):
    y = np.array(series, dtype=float)
    n = len(y)
    if n < 10:
        return 0.5
    lags = range(2, min(20, n // 2))
    try:
        tau = [np.sqrt(np.std(np.subtract(y[lag:], y[:-lag]))) for lag in lags]
        poly = np.polyfit(np.log(lags), np.log(tau), 1)
        return float(poly[0])
    except Exception:
        return 0.5

def calculate_approx_entropy(series, m=2, r=None):
    y = np.array(series, dtype=float)
    n = len(y)
    if n < 10:
        return 0.0
    if r is None:
        r = 0.2 * np.std(y)
        if r == 0:
            r = 1e-5
            
    def _maxdist(x_i, x_j):
        return np.max(np.abs(x_i - x_j))

    def _phi(m_val):
        x = np.array([y[i : i + m_val] for i in range(n - m_val + 1)])
        c = []
        for i in range(len(x)):
            count = 0
            for j in range(len(x)):
                if _maxdist(x[i], x[j]) <= r:
                    count += 1
            c.append(count / len(x))
        return np.sum(np.log(c)) / len(x)
        
    try:
        return float(abs(_phi(m) - _phi(m + 1)))
    except Exception:
        return 0.0

def extract_structural_features(series):
    clean_s = pd.Series(series).interpolate(method="linear").ffill().bfill()
    norm_s = z_score_normalize(clean_s)
    
    mean_val = float(clean_s.mean())
    var_val = float(clean_s.var())
    skew_val = float(clean_s.skew())
    kurt_val = float(clean_s.kurtosis())
    
    hurst = calculate_hurst(clean_s)
    apen = calculate_approx_entropy(clean_s)
    
    ar_params = [0.0, 0.0, 0.0]
    try:
        ar_model = AutoReg(norm_s, lags=3).fit()
        for idx in range(1, min(len(ar_model.params), 4)):
            ar_params[idx - 1] = float(ar_model.params.iloc[idx])
    except Exception:
        pass
        
    return {
        "stat_mean": mean_val,
        "stat_var": var_val,
        "stat_skew": skew_val,
        "stat_kurt": kurt_val,
        "hurst_exponent": hurst,
        "approx_entropy": apen,
        "ar1_coeff": ar_params[0],
        "ar2_coeff": ar_params[1],
        "ar3_coeff": ar_params[2]
    }

# --- Step 1: Load and Preprocess Data ---

print("\n--- Step 1: Loading & Aligning Data ---")
df = pd.read_parquet(merged_parquet)
print(f"Initial raw rows: {len(df):,}")

# Group by Country and adm1_pcode to resolve name and coordinate duplicates per region
regions_data = {}
metadata_rows = []

grouped = df.groupby(["Country", "adm1_pcode"])
for (country, pcode), group in grouped:
    # Resolve region name (first non-null Level 1)
    names = group["Level 1"].dropna()
    r_name = names.iloc[0] if not names.empty else "Unknown Region"
    
    # Resolve coordinates (mean of non-null)
    lats = group["latitude"].dropna()
    lons = group["longitude"].dropna()
    lat = lats.mean() if not lats.empty else np.nan
    lon = lons.mean() if not lons.empty else np.nan
    
    # Extract and expand time series using all validity periods
    expanded = []
    for _, row in group.iterrows():
        m_range = pd.date_range(start=row["From"], end=row["To"], freq="MS")
        for m in m_range:
            expanded.append({"date": m, "pct": row["phase_3plus_percentage"]})
            
    if expanded:
        # Group by date and take mean to aggregate overlapping assessments (current/projections)
        df_ipc = pd.DataFrame(expanded).groupby("date")["pct"].mean().to_frame()
        # Reindex to regular monthly grid from min to max date
        full_range = pd.date_range(start=df_ipc.index.min(), end=df_ipc.index.max(), freq="MS")
        df_ipc = df_ipc.reindex(full_range)
        # Interpolate and ffill/bfill gaps
        df_ipc = df_ipc.interpolate(method="linear").ffill().bfill()
        
        # Check if the series meets the minimum length constraint (>= 24 months) and has no NaNs
        if len(df_ipc) >= 24 and not df_ipc["pct"].isna().any():
            regions_data[f"{country}_{pcode}"] = df_ipc["pct"]
            metadata_rows.append({
                "country": country,
                "adm1_pcode": pcode,
                "region_name": r_name,
                "latitude": lat,
                "longitude": lon,
                "key": f"{country}_{pcode}",
                "series_length": len(df_ipc)
            })

df_meta = pd.DataFrame(metadata_rows)

# Impute any missing coordinates using country means
for idx, row in df_meta.iterrows():
    if pd.isna(row["latitude"]) or pd.isna(row["longitude"]):
        c_code = row["country"]
        c_mean_lat = df_meta[(df_meta["country"] == c_code) & (~df_meta["latitude"].isna())]["latitude"].mean()
        c_mean_lon = df_meta[(df_meta["country"] == c_code) & (~df_meta["longitude"].isna())]["longitude"].mean()
        
        # Fallback if the whole country is NaN
        if pd.isna(c_mean_lat):
            c_mean_lat = 0.0
            c_mean_lon = 0.0
            
        df_meta.at[idx, "latitude"] = c_mean_lat
        df_meta.at[idx, "longitude"] = c_mean_lon
        print(f"Imputed missing coordinates for {row['adm1_pcode']} using {c_code} mean: Lat={c_mean_lat:.4f}, Lon={c_mean_lon:.4f}")

print(f"Regions with valid time series (>= 24 months): {len(df_meta)}")

# --- Step 2: Structural Feature Extraction ---

print("\n--- Step 2: Feature Extraction ---")
features_list = []
for idx, row in df_meta.iterrows():
    key = row["key"]
    series = regions_data[key]
    feats = extract_structural_features(series)
    feats.update({
        "country": row["country"],
        "adm1_pcode": row["adm1_pcode"],
        "region_name": row["region_name"],
        "latitude": row["latitude"],
        "longitude": row["longitude"]
    })
    features_list.append(feats)

df_features = pd.DataFrame(features_list)
feature_cols = ["stat_mean", "stat_var", "stat_skew", "stat_kurt", "hurst_exponent", "approx_entropy", "ar1_coeff", "ar2_coeff", "ar3_coeff"]

print("Extracted structural features example:")
print(df_features[["country", "adm1_pcode", "region_name"] + feature_cols[:3]].head())

# --- Step 3: Define Clustering Pipeline Function ---

def run_clustering_flow(df_feat, series_dict, out_prefix, n_clusters=4, is_global=False):
    """
    Runs the clustering analysis:
    - Feature-based hierarchical clustering (with and without coordinates)
    - Feature-based K-Means (with and without coordinates)
    - Shape-based (DTW) hierarchical clustering (only if not global)
    - Saves plots and returns silhouette scores and label dataframes
    """
    # 1. Feature Extraction Matrices
    feats_only = df_feat[feature_cols].copy().fillna(0.0)
    coords_only = df_feat[["latitude", "longitude"]].copy().fillna(0.0)
    
    # Scale features
    scaler_feats = StandardScaler()
    X_feats_scaled = scaler_feats.fit_transform(feats_only)
    
    scaler_coords = StandardScaler()
    X_coords_scaled = scaler_coords.fit_transform(coords_only)
    
    # Combined scaled representation
    X_combined_scaled = np.hstack([X_feats_scaled, X_coords_scaled])
    
    results = {}
    
    # --- A. FEATURE-BASED CLUSTERING WITHOUT COORDINATES ---
    Z_feat_no_coords = linkage(X_feats_scaled, method='ward')
    labels_hier_no_coords = fcluster(Z_feat_no_coords, t=n_clusters, criterion='maxclust')
    
    kmeans_no_coords = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels_km_no_coords = kmeans_no_coords.fit_predict(X_feats_scaled)
    
    sil_hier_no_coords = silhouette_score(X_feats_scaled, labels_hier_no_coords) if len(np.unique(labels_hier_no_coords)) > 1 else -1
    sil_km_no_coords = silhouette_score(X_feats_scaled, labels_km_no_coords) if len(np.unique(labels_km_no_coords)) > 1 else -1
    
    # PCA for visualization (baseline)
    pca = PCA(n_components=2)
    X_pca_no_coords = pca.fit_transform(X_feats_scaled)
    
    # --- B. FEATURE-BASED CLUSTERING WITH COORDINATES ---
    Z_feat_with_coords = linkage(X_combined_scaled, method='ward')
    labels_hier_with_coords = fcluster(Z_feat_with_coords, t=n_clusters, criterion='maxclust')
    
    kmeans_with_coords = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels_km_with_coords = kmeans_with_coords.fit_predict(X_combined_scaled)
    
    sil_hier_with_coords = silhouette_score(X_combined_scaled, labels_hier_with_coords) if len(np.unique(labels_hier_with_coords)) > 1 else -1
    sil_km_with_coords = silhouette_score(X_combined_scaled, labels_km_with_coords) if len(np.unique(labels_km_with_coords)) > 1 else -1
    
    # PCA for visualization (combined)
    X_pca_with_coords = pca.fit_transform(X_combined_scaled)
    
    # --- C. SHAPE-BASED CLUSTERING (DTW) ---
    shape_labels_series = None
    if not is_global:
        try:
            dtw_matrix = compute_similarity_matrix(series_dict, method="dtw", w=12)
            condensed_dist = squareform(dtw_matrix, checks=False)
            Z_shape = linkage(condensed_dist, method='average')
            labels_hier_shape = fcluster(Z_shape, t=n_clusters, criterion='maxclust')
            
            # Map shape labels to region names safely
            shape_labels_series = pd.Series(labels_hier_shape, index=dtw_matrix.index)
            
            # Save DTW Heatmap
            plt.figure(figsize=(10, 8))
            sns.heatmap(dtw_matrix, annot=False, cmap="viridis")
            plt.title(f"Pairwise DTW Distance Heatmap (Shape)")
            plt.tight_layout()
            plt.savefig(out_prefix + "_dtw_heatmap.png", dpi=150)
            plt.close()
            
            # Save Shape Dendrogram
            plt.figure(figsize=(12, 6))
            dendrogram(Z_shape, labels=df_feat["region_name"].values, leaf_rotation=90, leaf_font_size=8)
            plt.title("Hierarchical Clustering Dendrogram (DTW Shape-Based)")
            plt.ylabel("Warping Distance")
            plt.tight_layout()
            plt.savefig(out_prefix + "_dendrogram_shape.png", dpi=150)
            plt.close()
        except Exception as e:
            print(f"Error computing DTW clustering: {e}")
            
    # --- D. VISUALIZATION PLOTS ---
    # 1. Feature Dendrograms
    plt.figure(figsize=(12, 6))
    dendrogram(Z_feat_no_coords, labels=df_feat["region_name"].values, leaf_rotation=90, leaf_font_size=8)
    plt.title("Hierarchical Clustering Dendrogram (Features - NO Coordinates)")
    plt.ylabel("Ward Linkage Distance")
    plt.tight_layout()
    plt.savefig(out_prefix + "_dendrogram_features_no_coords.png", dpi=150)
    plt.close()
    
    plt.figure(figsize=(12, 6))
    dendrogram(Z_feat_with_coords, labels=df_feat["region_name"].values, leaf_rotation=90, leaf_font_size=8)
    plt.title("Hierarchical Clustering Dendrogram (Features - WITH Coordinates)")
    plt.ylabel("Ward Linkage Distance")
    plt.tight_layout()
    plt.savefig(out_prefix + "_dendrogram_features_with_coords.png", dpi=150)
    plt.close()
    
    # 2. PCA Scatter Plots
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    sns.scatterplot(x=X_pca_no_coords[:, 0], y=X_pca_no_coords[:, 1], hue=labels_km_no_coords, palette="tab10", s=100, ax=axes[0])
    axes[0].set_title("K-Means Clustering on PCA (NO Coordinates)")
    axes[0].set_xlabel("PC 1")
    axes[0].set_ylabel("PC 2")
    axes[0].legend(title="Cluster")
    
    # Annotate region names if small dataset
    if len(df_feat) <= 35:
        for i, txt in enumerate(df_feat["region_name"]):
            axes[0].annotate(txt, (X_pca_no_coords[i, 0] + 0.05, X_pca_no_coords[i, 1] + 0.05), fontsize=7, alpha=0.8)
            
    sns.scatterplot(x=X_pca_with_coords[:, 0], y=X_pca_with_coords[:, 1], hue=labels_km_with_coords, palette="tab10", s=100, ax=axes[1])
    axes[1].set_title("K-Means Clustering on PCA (WITH Coordinates)")
    axes[1].set_xlabel("PC 1")
    axes[1].set_ylabel("PC 2")
    axes[1].legend(title="Cluster")
    
    if len(df_feat) <= 35:
        for i, txt in enumerate(df_feat["region_name"]):
            axes[1].annotate(txt, (X_pca_with_coords[i, 0] + 0.05, X_pca_with_coords[i, 1] + 0.05), fontsize=7, alpha=0.8)
            
    plt.tight_layout()
    plt.savefig(out_prefix + "_pca_comparison.png", dpi=150)
    plt.close()
    
    # Collect labels in a DataFrame
    df_labels = pd.DataFrame({
        "country": df_feat["country"],
        "adm1_pcode": df_feat["adm1_pcode"],
        "region_name": df_feat["region_name"],
        "hierarchical_features_no_coords": labels_hier_no_coords,
        "hierarchical_features_with_coords": labels_hier_with_coords,
        "kmeans_features_no_coords": labels_km_no_coords,
        "kmeans_features_with_coords": labels_km_with_coords
    })
    if shape_labels_series is not None:
        # Safely map shape clusters by adm1_pcode to ensure perfect length/index alignment
        df_labels["hierarchical_shape_dtw"] = df_labels["adm1_pcode"].map(shape_labels_series)
        
    results = {
        "labels_df": df_labels,
        "metrics": {
            "sil_hier_no_coords": sil_hier_no_coords,
            "sil_km_no_coords": sil_km_no_coords,
            "sil_hier_with_coords": sil_hier_with_coords,
            "sil_km_with_coords": sil_km_with_coords
        }
    }
    return results

# --- Step 4: Country-Level Clustering ---

print("\n--- Step 4: Running Country-Level Analysis ---")
metrics_records = []

# Find countries with at least 4 valid regions
country_counts = df_meta["country"].value_counts()
eligible_countries = country_counts[country_counts >= 4].index.tolist()
print(f"Eligible countries (>=4 regions): {eligible_countries}")

for c_code in eligible_countries:
    print(f"\nProcessing Country: {c_code}")
    c_df_feat = df_features[df_features["country"] == c_code].reset_index(drop=True)
    c_series_dict = {row["adm1_pcode"]: regions_data[row["key"]] for _, row in df_meta[df_meta["country"] == c_code].iterrows()}
    
    c_results_dir = os.path.join(results_dir, c_code)
    os.makedirs(c_results_dir, exist_ok=True)
    
    out_prefix = os.path.join(c_results_dir, f"{c_code}_clustering")
    # n_clusters must be <= n_samples - 1 to allow silhouette score calculation (with minimum of 2)
    n_cl = max(2, min(4, len(c_df_feat) - 1))
    
    flow_results = run_clustering_flow(c_df_feat, c_series_dict, out_prefix, n_clusters=n_cl, is_global=False)
    
    # Save CSV
    flow_results["labels_df"].to_csv(out_prefix + "_labels.csv", index=False)
    
    # Save metrics
    mets = flow_results["metrics"]
    mets["country"] = c_code
    mets["num_regions"] = len(c_df_feat)
    metrics_records.append(mets)
    print(f"Country {c_code} completed. Silhouette K-Means (No Coords): {mets['sil_km_no_coords']:.3f} | (With Coords): {mets['sil_km_with_coords']:.3f}")
    
    # Attempt Choropleth Maps
    geojson_path = os.path.join(data_dir, "boundaries", c_code.lower(), f"{c_code.lower()}_admin1.geojson")
    if os.path.exists(geojson_path):
        try:
            gdf = gpd.read_file(geojson_path)
            # Find matching column for adm1_pcode (usually adm1_pcode, case insensitive)
            pcode_col = None
            for col in gdf.columns:
                if col.lower() == 'adm1_pcode':
                    pcode_col = col
                    break
            if pcode_col is not None:
                gdf_merged = gdf.merge(flow_results["labels_df"], left_on=pcode_col, right_on="adm1_pcode", how="left")
                
                # Plot side-by-side maps for K-Means with and without coords
                fig, axes = plt.subplots(1, 2, figsize=(18, 9))
                gdf_merged.plot(column="kmeans_features_no_coords", cmap="tab10", legend=True, categorical=True,
                                ax=axes[0], missing_kwds={"color": "lightgrey"})
                axes[0].set_title(f"{c_code} - K-Means (NO Coordinates)")
                axes[0].axis("off")
                
                gdf_merged.plot(column="kmeans_features_with_coords", cmap="tab10", legend=True, categorical=True,
                                ax=axes[1], missing_kwds={"color": "lightgrey"})
                axes[1].set_title(f"{c_code} - K-Means (WITH Coordinates)")
                axes[1].axis("off")
                
                plt.tight_layout()
                plt.savefig(out_prefix + "_choropleth_comparison.png", dpi=150)
                plt.close()
                print(f"Saved choropleth map comparison for {c_code}")
        except Exception as e:
            print(f"Choropleth mapping failed for {c_code}: {e}")

# --- Step 5: Global Region-Level Clustering ---

print("\n--- Step 5: Running Global Region-Level Clustering ---")
global_out_prefix = os.path.join(results_dir, "global", "global_regions")

# Run global clustering on features (K=5)
global_results = run_clustering_flow(df_features, None, global_out_prefix, n_clusters=5, is_global=True)
global_results["labels_df"].to_csv(global_out_prefix + "_labels.csv", index=False)

mets_global = global_results["metrics"]
print(f"Global Region Clustering completed.")
print(f"Silhouette Hierarchical (No Coords): {mets_global['sil_hier_no_coords']:.3f} | (With Coords): {mets_global['sil_hier_with_coords']:.3f}")
print(f"Silhouette K-Means      (No Coords): {mets_global['sil_km_no_coords']:.3f} | (With Coords): {mets_global['sil_km_with_coords']:.3f}")

# Plot Global Map
print("Attempting to plot Global Map...")
try:
    world_url = 'https://raw.githubusercontent.com/datasets/geo-boundaries-world-110m/master/countries.geojson'
    world = gpd.read_file(world_url)
    world = world[world["continent"] != "Antarctica"]
    
    # Load all boundaries for countries with valid regions
    gdfs = []
    for c in df_features["country"].unique():
        path = os.path.join(data_dir, "boundaries", c.lower(), f"{c.lower()}_admin1.geojson")
        if os.path.exists(path):
            try:
                gdf_c = gpd.read_file(path)
                pcode_col = None
                for col in gdf_c.columns:
                    if col.lower() == 'adm1_pcode':
                        pcode_col = col
                        break
                if pcode_col is not None:
                    gdf_c = gdf_c[[pcode_col, "geometry"]]
                    gdf_c = gdf_c.rename(columns={pcode_col: "adm1_pcode"})
                    gdfs.append(gdf_c)
            except Exception as e:
                pass
                
    if gdfs:
        all_regions_gdf = pd.concat(gdfs, ignore_index=True)
        all_regions_gdf = all_regions_gdf.merge(global_results["labels_df"], on="adm1_pcode", how="left")
        
        # 1. Global map for No Coords
        fig, ax = plt.subplots(figsize=(18, 10))
        world.plot(ax=ax, color="#f2f2f2", edgecolor="#d9d9d9")
        all_regions_gdf.dropna(subset=["kmeans_features_no_coords"]).plot(
            column="kmeans_features_no_coords", cmap="tab10", legend=True, categorical=True,
            ax=ax, legend_kwds={"bbox_to_anchor": (1.05, 1), "loc": "upper left"}
        )
        ax.set_title("Global Admin1 Region Clusters (PCA + K-Means - NO Coordinates)", fontsize=16)
        ax.set_xlim([-120, 150])
        ax.set_ylim([-40, 60])
        plt.tight_layout()
        plt.savefig(global_out_prefix + "_map_no_coords.png", dpi=150)
        plt.close()
        
        # 2. Global map for With Coords
        fig, ax = plt.subplots(figsize=(18, 10))
        world.plot(ax=ax, color="#f2f2f2", edgecolor="#d9d9d9")
        all_regions_gdf.dropna(subset=["kmeans_features_with_coords"]).plot(
            column="kmeans_features_with_coords", cmap="tab10", legend=True, categorical=True,
            ax=ax, legend_kwds={"bbox_to_anchor": (1.05, 1), "loc": "upper left"}
        )
        ax.set_title("Global Admin1 Region Clusters (PCA + K-Means - WITH Coordinates)", fontsize=16)
        ax.set_xlim([-120, 150])
        ax.set_ylim([-40, 60])
        plt.tight_layout()
        plt.savefig(global_out_prefix + "_map_with_coords.png", dpi=150)
        plt.close()
        print("Global maps plotted successfully.")
except Exception as e:
    print(f"Global region choropleth map plotting failed: {e}")

# --- Step 6: Global National-Level Clustering ---

print("\n--- Step 6: Running Global National-Level Clustering ---")
global_nat_prefix = os.path.join(results_dir, "global", "global_national")

# Aggregate regional time series and coordinates to national level
national_series = {}
national_meta = []

for c_code, group in df_meta.groupby("country"):
    valid_dfs = []
    for _, row in group.iterrows():
        valid_dfs.append(regions_data[row["key"]])
    
    # Align to a common monthly range for this country's regions
    common_idx = valid_dfs[0].index
    for s in valid_dfs[1:]:
        common_idx = common_idx.intersection(s.index)
        
    if len(common_idx) >= 24:
        aligned_series = [s.reindex(common_idx) for s in valid_dfs]
        nat_series = pd.concat(aligned_series, axis=1).mean(axis=1)
        national_series[c_code] = nat_series
        
        # Mean coordinates for the country
        c_feats = df_features[df_features["country"] == c_code]
        mean_lat = c_feats["latitude"].mean()
        mean_lon = c_feats["longitude"].mean()
        
        # Calculate features on the aggregated national series
        feats = extract_structural_features(nat_series)
        feats.update({
            "country": c_code,
            "adm1_pcode": c_code,
            "region_name": c_code,
            "latitude": mean_lat,
            "longitude": mean_lon
        })
        national_meta.append(feats)

df_nat_features = pd.DataFrame(national_meta)
print(f"Countries with aggregated national time series (>= 24 months): {len(df_nat_features)}")

if len(df_nat_features) >= 4:
    nat_results = run_clustering_flow(df_nat_features, national_series, global_nat_prefix, n_clusters=4, is_global=False)
    nat_results["labels_df"].to_csv(global_nat_prefix + "_labels.csv", index=False)
    
    # Save national map
    try:
        world_url = 'https://raw.githubusercontent.com/datasets/geo-boundaries-world-110m/master/countries.geojson'
        world = gpd.read_file(world_url)
        world = world[world["continent"] != "Antarctica"]
        
        # Merge world geometry with national cluster labels
        world_merged = world.merge(nat_results["labels_df"], left_on="iso_a3", right_on="country", how="left")
        
        fig, ax = plt.subplots(figsize=(18, 10))
        world_merged.plot(color="#f2f2f2", edgecolor="#d9d9d9", ax=ax)
        world_merged.dropna(subset=["kmeans_features_with_coords"]).plot(
            column="kmeans_features_with_coords", cmap="tab10", legend=True, categorical=True,
            ax=ax, legend_kwds={"bbox_to_anchor": (1.05, 1), "loc": "upper left"}
        )
        ax.set_title("Global National-Level Clusters (PCA + K-Means - WITH Coordinates)", fontsize=16)
        ax.set_xlim([-120, 150])
        ax.set_ylim([-40, 60])
        plt.tight_layout()
        plt.savefig(global_nat_prefix + "_map_with_coords.png", dpi=150)
        plt.close()
        print("Global national maps plotted successfully.")
    except Exception as e:
        print(f"Global national map plotting failed: {e}")

# Save comparative metrics summary
df_metrics = pd.DataFrame(metrics_records)
df_metrics.to_csv(os.path.join(results_dir, "country_level_clustering_silhouette_scores.csv"), index=False)
print("\nSaved comparative silhouette scores summary CSV.")
print("\n--- Pipeline Completed Successfully! ---")
