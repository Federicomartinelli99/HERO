import os
import sys
import glob
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score, adjusted_rand_score, normalized_mutual_info_score, davies_bouldin_score
from sklearn.manifold import TSNE
from scipy.cluster.hierarchy import linkage, fcluster, dendrogram
from scipy.spatial.distance import squareform
from matplotlib.colors import ListedColormap
import geopandas as gpd
import warnings
import umap

# Suppress warnings
warnings.filterwarnings("ignore")

# Add current folder to path for config and similarity_utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import config
import similarity_utils

# Consistent color palette for cluster labels (0: Blue, 1: Orange, 2: Green, 3: Red, etc.)
CLUSTER_COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f"]

def load_and_prepare_data():
    """
    Loads Parquet data and groups by Country and adm1_pcode.
    Resolves duplicates by taking the mean per date.
    Returns:
        df_meta: DataFrame with region metadata (coordinates, population, etc.)
        regions_ts: Dictionary mapping region key to its target time series (Series)
        regions_multivariate_ts: Dictionary mapping region key to its multivariate DataFrame
    """
    print(f"\n--- Loading Dataset from: {config.DATASET_PATH} ---")
    if not os.path.exists(config.DATASET_PATH):
        raise FileNotFoundError(f"Parquet file not found at {config.DATASET_PATH}")
        
    df = pd.read_parquet(config.DATASET_PATH)
    print(f"Total raw rows: {len(df):,}")
    
    # Identify unique regions
    grouped = df.groupby(["Country", "adm1_pcode"])
    regions_ts = {}
    regions_multivariate_ts = {}
    metadata_rows = []
    
    # Features to extract
    all_cols = [config.TARGET_COL] + config.MULTIVARIATE_COLS
    all_cols = list(dict.fromkeys(all_cols))
    
    for (country, pcode), group in grouped:
        # Resolve names and metadata
        names = group["Level 1"].dropna()
        r_name = names.iloc[0] if not names.empty else "Unknown Region"
        
        # Coordinates and population
        lat = group["latitude"].dropna().mean() if not group["latitude"].dropna().empty else np.nan
        lon = group["longitude"].dropna().mean() if not group["longitude"].dropna().empty else np.nan
        pop = group["adm1_population"].dropna().mean() if not group["adm1_population"].dropna().empty else np.nan
        
        # Mode of step 1 cluster_assegnato
        step1_clust = group["cluster_assegnato"].mode().iloc[0] if not group["cluster_assegnato"].dropna().empty else -1
        
        # Group by From date to resolve duplicates, take mean, sort chronologically
        grouped_time = group.groupby("From")[all_cols].mean().sort_index()
        
        # Minimum sequence length check (e.g. >= 5 points)
        if len(grouped_time) >= 5:
            key = f"{country}_{pcode}"
            regions_ts[key] = grouped_time[config.TARGET_COL]
            regions_multivariate_ts[key] = grouped_time[config.MULTIVARIATE_COLS]
            
            metadata_rows.append({
                "key": key,
                "country": country,
                "adm1_pcode": pcode,
                "region_name": r_name,
                "latitude": lat,
                "longitude": lon,
                "adm1_population": pop,
                "step1_cluster": step1_clust,
                "series_length": len(grouped_time)
            })
            
    df_meta = pd.DataFrame(metadata_rows)
    print(f"Loaded {len(df_meta)} valid regions (with series length >= 5)")
    
    # Impute missing coordinates using country means if any
    for idx, row in df_meta.iterrows():
        if pd.isna(row["latitude"]) or pd.isna(row["longitude"]):
            c_code = row["country"]
            c_mean_lat = df_meta[(df_meta["country"] == c_code) & (~df_meta["latitude"].isna())]["latitude"].mean()
            c_mean_lon = df_meta[(df_meta["country"] == c_code) & (~df_meta["longitude"].isna())]["longitude"].mean()
            
            df_meta.at[idx, "latitude"] = c_mean_lat if not pd.isna(c_mean_lat) else 0.0
            df_meta.at[idx, "longitude"] = c_mean_lon if not pd.isna(c_mean_lon) else 0.0
            
        if pd.isna(row["adm1_population"]):
            df_meta.at[idx, "adm1_population"] = 100_000.0
            
    return df_meta, regions_ts, regions_multivariate_ts

def load_geography_boundaries(df_meta):
    """
    Compiles geojson boundary files for each country in df_meta.
    Returns:
        global_gdf: GeoDataFrame containing adm1_pcode and geometry.
    """
    boundary_dirs = glob.glob(os.path.join(config.DATA_DIR, "boundaries", "*"))
    gdfs = []
    
    for d in boundary_dirs:
        c_code_lower = os.path.basename(d).lower()
        geojson_path = os.path.join(d, f"{c_code_lower}_admin1.geojson")
        if not os.path.exists(geojson_path):
            geojson_path = os.path.join(d, f"{c_code_lower}_admin1_em.geojson")
            
        if os.path.exists(geojson_path):
            try:
                gdf = gpd.read_file(geojson_path)
                if "adm1_pcode" in gdf.columns:
                    gdfs.append(gdf[["adm1_pcode", "geometry"]])
            except Exception as e:
                print(f"Error loading boundary for {c_code_lower}: {e}")
                
    if gdfs:
        global_gdf = gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True))
        global_gdf["adm1_pcode"] = global_gdf["adm1_pcode"].astype(str)
        return global_gdf
    return None

def load_world_boundaries():
    """
    Loads global simplified country boundaries for map background.
    """
    try:
        world_url = 'https://raw.githubusercontent.com/datasets/geo-boundaries-world-110m/master/countries.geojson'
        world = gpd.read_file(world_url)
        world = world[world["continent"] != "Antarctica"]
        return world
    except Exception as e:
        print(f"Warning: Could not load global world map boundaries: {e}")
        return None

def select_k_consensus(k_range, sse_list, silhouette_list, db_list):
    """
    Selects the best k in k_range using rank consensus of Silhouette, Davies-Bouldin, and Elbow distance.
    """
    if len(k_range) == 0:
        return 2
    if len(k_range) == 1:
        return k_range[0]
        
    s_ranks = pd.Series(silhouette_list, index=k_range).rank(ascending=False)
    db_ranks = pd.Series(db_list, index=k_range).rank(ascending=True)
    
    x1, y1 = k_range[0], sse_list[0]
    x2, y2 = k_range[-1], sse_list[-1]
    
    elbow_dists = []
    for k, sse in zip(k_range, sse_list):
        numerator = abs((y2 - y1) * k - (x2 - x1) * sse + x2 * y1 - y2 * x1)
        denominator = ((y2 - y1)**2 + (x2 - x1)**2)**0.5
        elbow_dists.append(numerator / denominator if denominator > 0 else 0)
        
    sse_ranks = pd.Series(elbow_dists, index=k_range).rank(ascending=False)
    
    avg_ranks = (s_ranks + db_ranks + sse_ranks) / 3
    best_k = avg_ranks.idxmin()
    return int(best_k)

def plot_clustering_evaluation_metrics(X, out_prefix, max_k=8):
    """
    Evaluates SSE, BSS/TSS, Silhouette Score, and Davies-Bouldin Index for k in [2, max_k].
    Saves a 4-panel plot.
    Returns:
        k_small: the consensus-chosen k in [2, 3]
        k_large: the consensus-chosen k in [4, max_k] (if max_k >= 4, else None)
    """
    os.makedirs(os.path.dirname(out_prefix), exist_ok=True)
    k_range = list(range(2, min(max_k + 1, len(X))))
    if len(k_range) < 1:
        return 2, None
        
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    TSS = np.sum((X_scaled - np.mean(X_scaled, axis=0)) ** 2)
    
    sse_list = []
    bss_tss_list = []
    silhouette_list = []
    db_list = []
    
    for k in k_range:
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(X_scaled)
        
        sse = km.inertia_
        sse_list.append(sse)
        
        bss = TSS - sse
        bss_tss = bss / TSS
        bss_tss_list.append(bss_tss)
        
        sil = silhouette_score(X_scaled, labels)
        silhouette_list.append(sil)
        
        db = davies_bouldin_score(X_scaled, labels)
        db_list.append(db)
        
    fig, axes = plt.subplots(1, 4, figsize=(22, 5))
    axes[0].plot(k_range, sse_list, marker='o', linewidth=2, color='tab:blue')
    axes[0].set_title("Elbow Method: SSE vs. k", fontsize=12)
    axes[0].set_xlabel("Number of clusters (k)", fontsize=10)
    axes[0].set_ylabel("Sum of Squared Errors (SSE)", fontsize=10)
    
    axes[1].plot(k_range, bss_tss_list, marker='s', linewidth=2, color='tab:orange')
    axes[1].set_title("Variance Explained: BSS/TSS vs. k", fontsize=12)
    axes[1].set_xlabel("Number of clusters (k)", fontsize=10)
    axes[1].set_ylabel("BSS / TSS Ratio", fontsize=10)
    
    axes[2].plot(k_range, silhouette_list, marker='^', linewidth=2, color='tab:green')
    axes[2].set_title("Silhouette Score vs. k", fontsize=12)
    axes[2].set_xlabel("Number of clusters (k)", fontsize=10)
    axes[2].set_ylabel("Silhouette Score", fontsize=10)
    
    axes[3].plot(k_range, db_list, marker='d', linewidth=2, color='tab:red')
    axes[3].set_title("Davies-Bouldin vs. k (Lower is Better)", fontsize=12)
    axes[3].set_xlabel("Number of clusters (k)", fontsize=10)
    axes[3].set_ylabel("Davies-Bouldin Index", fontsize=10)
    
    plt.tight_layout()
    plt.savefig(f"{out_prefix}_evaluation_metrics.png", dpi=150)
    plt.close()
    
    k_range_small = [k for k in k_range if k in [2, 3]]
    if k_range_small:
        sse_small = [sse_list[k_range.index(k)] for k in k_range_small]
        sil_small = [silhouette_list[k_range.index(k)] for k in k_range_small]
        db_small = [db_list[k_range.index(k)] for k in k_range_small]
        k_small = select_k_consensus(k_range_small, sse_small, sil_small, db_small)
    else:
        k_small = 2
        
    k_range_large = [k for k in k_range if k >= 4]
    if k_range_large:
        sse_large = [sse_list[k_range.index(k)] for k in k_range_large]
        sil_large = [silhouette_list[k_range.index(k)] for k in k_range_large]
        db_large = [db_list[k_range.index(k)] for k in k_range_large]
        k_large = select_k_consensus(k_range_large, sse_large, sil_large, db_large)
    else:
        k_large = None
        
    print(f"Consensus evaluation completed for {out_prefix}:")
    print(f"  -> Selected k_small: {k_small}")
    print(f"  -> Selected k_large: {k_large}")
    
    return k_small, k_large

def run_clustering_and_evaluate(X, names, out_prefix, k_values=None):
    """
    Helper function that runs K-Means and Ward Hierarchical clustering on a scaled feature matrix.
    Computes silhouette and Davies-Bouldin scores.
    """
    if k_values is None:
        k_values = config.K_VALUES
        
    results = []
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    for k in k_values:
        if k >= len(X):
            continue
            
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        km_labels = km.fit_predict(X_scaled)
        km_sil = silhouette_score(X_scaled, km_labels) if len(np.unique(km_labels)) > 1 else -1.0
        km_db = davies_bouldin_score(X_scaled, km_labels) if len(np.unique(km_labels)) > 1 else 999.0
        
        Z = linkage(X_scaled, method='ward')
        hier_labels = fcluster(Z, t=k, criterion='maxclust') - 1
        hier_sil = silhouette_score(X_scaled, hier_labels) if len(np.unique(hier_labels)) > 1 else -1.0
        hier_db = davies_bouldin_score(X_scaled, hier_labels) if len(np.unique(hier_labels)) > 1 else 999.0
        
        results.append({
            "k": k,
            "kmeans_silhouette": km_sil,
            "kmeans_db": km_db,
            "kmeans_labels": km_labels,
            "hierarchical_silhouette": hier_sil,
            "hierarchical_db": hier_db,
            "hierarchical_labels": hier_labels,
            "linkage_matrix": Z
        })
        
    return X_scaled, results

def plot_medoids(series_dict, labels, distance_matrix, out_path, title):
    """
    Finds and plots the medoids of the shape clusters using consistent colors.
    """
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    unique_labels = np.unique(list(labels.values()))
    unique_labels = unique_labels[unique_labels != -1]
    
    plt.figure(figsize=(10, 6))
    for cid in unique_labels:
        medoid_key = similarity_utils.find_cluster_medoid(series_dict, labels, cid, distance_matrix)
        if medoid_key:
            s = series_dict[medoid_key]
            color = CLUSTER_COLORS[cid % len(CLUSTER_COLORS)]
            plt.plot(range(len(s)), s.values, label=f"Cluster {cid} Medoid ({medoid_key})", marker='o', linewidth=2, color=color)
            
    plt.title(title, fontsize=14)
    plt.xlabel("Observations (Chronological Index)", fontsize=12)
    plt.ylabel("Value", fontsize=12)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()

def plot_pca_comparison(X_scaled, labels, title, out_path, names=None):
    """
    Plots a 2D PCA representation of the clustering results using consistent colors.
    """
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    pca = PCA(n_components=2)
    X_pca = pca.fit_transform(X_scaled)
    
    max_lbl = int(np.max(labels))
    palette = {i: CLUSTER_COLORS[i % len(CLUSTER_COLORS)] for i in range(max_lbl + 1)}
    
    plt.figure(figsize=(8, 6))
    sns.scatterplot(x=X_pca[:, 0], y=X_pca[:, 1], hue=labels, palette=palette, s=100, legend="full")
    plt.title(title, fontsize=14)
    plt.xlabel("PC 1", fontsize=12)
    plt.ylabel("PC 2", fontsize=12)
    
    if names is not None and len(names) <= 30:
        for i, name in enumerate(names):
            plt.annotate(name, (X_pca[i, 0] + 0.05, X_pca[i, 1] + 0.05), fontsize=7, alpha=0.8)
            
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()

def plot_tsne_comparison(X_scaled, labels, title, out_path, perplexity=30):
    """
    Computes and plots 2D t-SNE projection using consistent colors.
    """
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    perp = min(perplexity, len(X_scaled) - 1)
    if perp < 2:
        return
        
    tsne = TSNE(n_components=2, perplexity=perp, random_state=42)
    X_tsne = tsne.fit_transform(X_scaled)
    
    max_lbl = int(np.max(labels))
    palette = {i: CLUSTER_COLORS[i % len(CLUSTER_COLORS)] for i in range(max_lbl + 1)}
    
    plt.figure(figsize=(8, 6))
    sns.scatterplot(x=X_tsne[:, 0], y=X_tsne[:, 1], hue=labels, palette=palette, s=100, legend="full")
    plt.title(title, fontsize=14)
    plt.xlabel("t-SNE Component 1", fontsize=12)
    plt.ylabel("t-SNE Component 2", fontsize=12)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()

def plot_umap_comparison(X_scaled, labels, title, out_path, n_neighbors=15):
    """
    Computes and plots 2D UMAP projection using consistent colors.
    """
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    neighbors = min(n_neighbors, len(X_scaled) - 1)
    if neighbors < 2:
        return
        
    reducer = umap.UMAP(n_neighbors=neighbors, min_dist=0.1, random_state=42)
    X_umap = reducer.fit_transform(X_scaled)
    
    max_lbl = int(np.max(labels))
    palette = {i: CLUSTER_COLORS[i % len(CLUSTER_COLORS)] for i in range(max_lbl + 1)}
    
    plt.figure(figsize=(8, 6))
    sns.scatterplot(x=X_umap[:, 0], y=X_umap[:, 1], hue=labels, palette=palette, s=100, legend="full")
    plt.title(title, fontsize=14)
    plt.xlabel("UMAP Component 1", fontsize=12)
    plt.ylabel("UMAP Component 2", fontsize=12)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()

def plot_geographic_map(boundaries_gdf, labels_df, id_col, label_col, title, out_path, world_gdf=None):
    """
    Plots a choropleth map of the clusters.
    """
    if boundaries_gdf is None or boundaries_gdf.empty:
        return
        
    merged = boundaries_gdf.merge(labels_df, left_on=id_col, right_on=id_col, how="inner")
    if merged.empty:
        return
        
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig, ax = plt.subplots(figsize=(15, 10))
    
    if world_gdf is not None:
        world_gdf.plot(color="#f4f4f4", edgecolor="#dcdcdc", linewidth=0.5, ax=ax)
    else:
        boundaries_gdf.plot(color="#f2f2f2", edgecolor="#d9d9d9", ax=ax)
    
    unique_labels = np.sort(np.unique(merged[label_col].values))
    max_lbl = int(np.max(unique_labels))
    cmap_colors = [CLUSTER_COLORS[i % len(CLUSTER_COLORS)] for i in range(max_lbl + 1)]
    cmap = ListedColormap(cmap_colors)
    
    merged.plot(
        column=label_col,
        cmap=cmap,
        legend=True,
        categorical=True,
        edgecolor="#ffffff",
        linewidth=0.2 if world_gdf is not None else 0.5,
        ax=ax,
        legend_kwds={"title": "Cluster", "bbox_to_anchor": (1.05, 1), "loc": "upper left"}
    )
    
    if world_gdf is not None:
        ax.set_xlim([-120, 150])
        ax.set_ylim([-40, 65])
        
    ax.set_title(title, fontsize=16)
    ax.set_axis_off()
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()

def evaluate_ari_nmi(labels, df_meta, target_ts, out_dir):
    """
    Evaluates ARI and NMI against Step 1 cluster_assegnato and binned average IPC level.
    Generates crosstab heatmaps and saves them directly under out_dir.
    """
    os.makedirs(out_dir, exist_ok=True)
    step1_labels = df_meta["step1_cluster"].values
    
    if not (step1_labels == -1).all():
        ari_step1 = adjusted_rand_score(step1_labels, labels)
        nmi_step1 = normalized_mutual_info_score(step1_labels, labels)
        
        crosstab_step1 = pd.crosstab(labels, step1_labels)
        plt.figure(figsize=(8, 6))
        sns.heatmap(crosstab_step1, annot=True, fmt="d", cmap="YlGnBu", cbar=True)
        plt.title(f"Crosstab: Step 3 Clusters vs. Step 1 Clusters\n(ARI={ari_step1:.4f}, NMI={nmi_step1:.4f})")
        plt.xlabel("Step 1 Cluster")
        plt.ylabel("Step 3 Cluster")
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, "crosstab_step1.png"), dpi=150)
        plt.close()
    else:
        ari_step1, nmi_step1 = np.nan, np.nan
        
    mean_ipc = np.array([target_ts[row["key"]].mean() for _, row in df_meta.iterrows()])
    
    try:
        ipc_bins = pd.qcut(mean_ipc, q=min(3, len(np.unique(mean_ipc))), labels=False, duplicates='drop')
    except Exception:
        ipc_bins = pd.cut(mean_ipc, bins=3, labels=False)
        
    ari_ipc = adjusted_rand_score(ipc_bins, labels)
    nmi_ipc = normalized_mutual_info_score(ipc_bins, labels)
    
    crosstab_ipc = pd.crosstab(labels, ipc_bins)
    plt.figure(figsize=(8, 6))
    sns.heatmap(crosstab_ipc, annot=True, fmt="d", cmap="YlGnBu", cbar=True)
    plt.title(f"Crosstab: Step 3 Clusters vs. Average Target IPC Bins\n(ARI={ari_ipc:.4f}, NMI={nmi_ipc:.4f})")
    plt.xlabel("Target IPC Bin (0:Low, 1:Med, 2:High)")
    plt.ylabel("Step 3 Cluster")
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "crosstab_ipc.png"), dpi=150)
    plt.close()
    
    print(f"\n--- Validation Metrics for {os.path.basename(out_dir)} ---")
    print(f"Adjusted Rand Index (ARI) with Step 1 clusters: {ari_step1:.4f}")
    print(f"Normalized Mutual Information (NMI) with Step 1 clusters: {nmi_step1:.4f}")
    print(f"ARI with average target IPC bins: {ari_ipc:.4f}")
    print(f"NMI with average target IPC bins: {nmi_ipc:.4f}")
    
    df_eval = pd.DataFrame([{
        "ari_step1_cluster": ari_step1,
        "nmi_step1_cluster": nmi_step1,
        "ari_target_ipc_bins": ari_ipc,
        "nmi_target_ipc_bins": nmi_ipc
    }])
    df_eval.to_csv(os.path.join(out_dir, "ari_nmi_evaluation.csv"), index=False)

def compare_clustering_strategies(k_dir, df_labels, df_meta, regions_ts, X_scaled):
    """
    Computes comparative metrics (Silhouette, Davies-Bouldin, ARI/NMI with Step 1 and IPC bins)
    for each clustering strategy present in df_labels.
    Also computes pairwise similarities between strategies and plots a heatmap.
    Saves results inside k_dir.
    """
    label_cols = [col for col in df_labels.columns if col.endswith("_cluster")]
    if len(label_cols) < 2:
        return
        
    comparison_rows = []
    
    # Target IPC Bins
    mean_ipc = np.array([regions_ts[row["key"]].mean() for _, row in df_meta.iterrows()])
    try:
        ipc_bins = pd.qcut(mean_ipc, q=min(3, len(np.unique(mean_ipc))), labels=False, duplicates='drop')
    except Exception:
        ipc_bins = pd.cut(mean_ipc, bins=3, labels=False)
        
    step1_labels = df_meta["step1_cluster"].values
    
    for col in label_cols:
        strat_name = col.replace("_cluster", "")
        labels = df_labels[col].values
        
        if len(np.unique(labels)) > 1:
            sil = silhouette_score(X_scaled, labels)
            db = davies_bouldin_score(X_scaled, labels)
        else:
            sil, db = -1.0, 999.0
            
        if not (step1_labels == -1).all():
            ari_step1 = adjusted_rand_score(step1_labels, labels)
            nmi_step1 = normalized_mutual_info_score(step1_labels, labels)
        else:
            ari_step1, nmi_step1 = np.nan, np.nan
            
        ari_ipc = adjusted_rand_score(ipc_bins, labels)
        nmi_ipc = normalized_mutual_info_score(ipc_bins, labels)
        
        comparison_rows.append({
            "strategy": strat_name,
            "silhouette_score": sil,
            "davies_bouldin_index": db,
            "ari_step1": ari_step1,
            "nmi_step1": nmi_step1,
            "ari_ipc_bins": ari_ipc,
            "nmi_ipc_bins": nmi_ipc
        })
        
    df_compare = pd.DataFrame(comparison_rows)
    df_compare.to_csv(os.path.join(k_dir, "strategy_comparison.csv"), index=False)
    
    n_strats = len(label_cols)
    ari_matrix = np.zeros((n_strats, n_strats))
    nmi_matrix = np.zeros((n_strats, n_strats))
    
    strat_names = [col.replace("_cluster", "") for col in label_cols]
    
    for i in range(n_strats):
        for j in range(n_strats):
            ari_matrix[i, j] = adjusted_rand_score(df_labels[label_cols[i]], df_labels[label_cols[j]])
            nmi_matrix[i, j] = normalized_mutual_info_score(df_labels[label_cols[i]], df_labels[label_cols[j]])
            
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    sns.heatmap(ari_matrix, annot=True, fmt=".3f", xticklabels=strat_names, yticklabels=strat_names, cmap="Greens", cbar=True, ax=axes[0])
    axes[0].set_title("Pairwise Adjusted Rand Index (ARI)", fontsize=12)
    
    sns.heatmap(nmi_matrix, annot=True, fmt=".3f", xticklabels=strat_names, yticklabels=strat_names, cmap="YlOrRd", cbar=True, ax=axes[1])
    axes[1].set_title("Pairwise Normalized Mutual Information (NMI)", fontsize=12)
    
    plt.tight_layout()
    plt.savefig(os.path.join(k_dir, "strategy_similarity_heatmap.png"), dpi=150)
    plt.close()

def run_country_level_clustering(df_meta, regions_ts, boundaries_gdf):
    """
    Runs shape-based and feature-based clustering within each country.
    Restricted to AFG, BEN, BGD as target countries.
    """
    print("\n--- Running Country-Level Analysis ---")
    target_countries = ["AFG", "BEN", "BGD"]
    
    for c_code in target_countries:
        if c_code not in df_meta["country"].values:
            continue
            
        print(f"\nProcessing Country: {c_code}")
        c_meta = df_meta[df_meta["country"] == c_code].reset_index(drop=True)
        c_series = {row["adm1_pcode"]: regions_ts[row["key"]] for _, row in c_meta.iterrows()}
        
        c_out_dir = os.path.join(config.OUTPUT_DIR, c_code)
        os.makedirs(c_out_dir, exist_ok=True)
        
        out_prefix = os.path.join(c_out_dir, f"{c_code}_univariate")
        
        features_list = []
        for pcode, s in c_series.items():
            feats = similarity_utils.extract_catch22_features(s.values)
            feats["adm1_pcode"] = pcode
            features_list.append(feats)
            
        df_feats = pd.DataFrame(features_list).set_index("adm1_pcode").fillna(0.0)
        
        k_small, k_large = plot_clustering_evaluation_metrics(df_feats.values, out_prefix, max_k=min(8, len(c_series) - 1))
        
        active_ks_folders = []
        active_ks_folders.append((k_small, f"k_{k_small}"))
        if k_large is not None:
            active_ks_folders.append((k_large, f"k_{k_large}"))
            
        ph1_vals = c_meta["step1_cluster"].dropna().unique()
        ph1_vals = ph1_vals[ph1_vals != -1]
        k_ph1 = len(ph1_vals)
        
        covered_ks = [item[0] for item in active_ks_folders]
        if k_ph1 >= 2 and k_ph1 < len(c_series) and k_ph1 not in covered_ks:
            active_ks_folders.append((k_ph1, f"k_{k_ph1}_ph1"))
            
        all_k_values = [item[0] for item in active_ks_folders]
        X_scaled, feat_results = run_clustering_and_evaluate(df_feats.values, df_feats.index.tolist(), None, k_values=all_k_values)
        
        dtw_matrix = similarity_utils.compute_distance_matrix(c_series, method="dtw", w=12)
        condensed_dtw = squareform(dtw_matrix, checks=False)
        Z_dtw = linkage(condensed_dtw, method='average')
        
        ncd_matrix = similarity_utils.compute_distance_matrix(c_series, method="ncd")
        condensed_ncd = squareform(ncd_matrix, checks=False)
        Z_ncd = linkage(condensed_ncd, method='average')
        
        plt.figure(figsize=(8, 6))
        sns.heatmap(dtw_matrix, annot=False, cmap="viridis")
        plt.title(f"{c_code} Pairwise DTW Distance Heatmap")
        plt.tight_layout()
        plt.savefig(os.path.join(c_out_dir, f"{c_code}_dtw_heatmap.png"), dpi=150)
        plt.close()
        
        plt.figure(figsize=(10, 5))
        dendrogram(Z_dtw, labels=c_meta["region_name"].values, leaf_rotation=90, leaf_font_size=8)
        plt.title(f"DTW Hierarchical Dendrogram for {c_code}")
        plt.ylabel("Warping Distance")
        plt.tight_layout()
        plt.savefig(os.path.join(c_out_dir, f"{c_code}_dendrogram_dtw.png"), dpi=150)
        plt.close()
        
        for k, folder_name in active_ks_folders:
            k_dir = os.path.join(c_out_dir, folder_name)
            os.makedirs(k_dir, exist_ok=True)
            
            res_feat = next(r for r in feat_results if r["k"] == k)
            feat_labels = res_feat["kmeans_labels"]
            
            lbls_dtw = fcluster(Z_dtw, t=k, criterion='maxclust') - 1
            lbls_ncd = fcluster(Z_ncd, t=k, criterion='maxclust') - 1
            
            df_labels = pd.DataFrame({
                "adm1_pcode": c_meta["adm1_pcode"],
                "region_name": c_meta["region_name"],
                "catch22_kmeans_cluster": feat_labels,
                "dtw_hierarchical_cluster": lbls_dtw,
                "ncd_hierarchical_cluster": lbls_ncd
            })
            df_labels.to_csv(os.path.join(k_dir, "labels.csv"), index=False)
            
            c_meta_eval = c_meta.copy()
            c_meta_eval["key"] = c_meta_eval["country"] + "_" + c_meta_eval["adm1_pcode"]
            
            compare_clustering_strategies(k_dir, df_labels, c_meta_eval, regions_ts, X_scaled)
            
            strategies = [
                {"name": "catch22_kmeans", "labels": feat_labels, "dist_matrix": dtw_matrix},
                {"name": "dtw_hierarchical", "labels": lbls_dtw, "dist_matrix": dtw_matrix},
                {"name": "ncd_hierarchical", "labels": lbls_ncd, "dist_matrix": ncd_matrix}
            ]
            
            for strat in strategies:
                strat_name = strat["name"]
                strat_labels = strat["labels"]
                
                strat_dir = os.path.join(k_dir, strat_name)
                os.makedirs(strat_dir, exist_ok=True)
                
                plot_pca_comparison(
                    X_scaled, 
                    strat_labels, 
                    f"{c_code} Region ({strat_name}, k={k}) - PCA", 
                    os.path.join(strat_dir, "pca.png"),
                    names=df_feats.index.tolist()
                )
                plot_tsne_comparison(
                    X_scaled,
                    strat_labels,
                    f"{c_code} Region ({strat_name}, k={k}) - t-SNE",
                    os.path.join(strat_dir, "tsne.png"),
                    perplexity=10
                )
                plot_umap_comparison(
                    X_scaled,
                    strat_labels,
                    f"{c_code} Region ({strat_name}, k={k}) - UMAP",
                    os.path.join(strat_dir, "umap.png"),
                    n_neighbors=5
                )
                
                labels_dict = dict(zip(c_meta["adm1_pcode"].tolist(), strat_labels))
                plot_medoids(
                    c_series, 
                    labels_dict, 
                    strat["dist_matrix"], 
                    os.path.join(strat_dir, "medoids.png"),
                    f"{c_code} Medoids ({strat_name}, k={k})"
                )
                
                if boundaries_gdf is not None:
                    c_boundaries = boundaries_gdf[boundaries_gdf["adm1_pcode"].isin(c_meta["adm1_pcode"])]
                    plot_geographic_map(
                        c_boundaries, 
                        df_labels, 
                        "adm1_pcode", 
                        f"{strat_name}_cluster", 
                        f"{c_code} Regional Map ({strat_name}, k={k})", 
                        os.path.join(strat_dir, "map.png")
                    )
                    
                evaluate_ari_nmi(strat_labels, c_meta_eval, regions_ts, strat_dir)
                
    print("\nCountry-level analysis completed successfully!")

def run_global_univariate_clustering(df_meta, regions_ts, boundaries_gdf, world_gdf):
    """
    Runs global clustering on all regional target series using catch22 and NCD.
    """
    print("\n--- Running Global Univariate Analysis ---")
    global_out_dir = os.path.join(config.OUTPUT_DIR, "global_univariate")
    os.makedirs(global_out_dir, exist_ok=True)
    
    out_prefix = os.path.join(global_out_dir, "global_univariate")
    
    features_list = []
    for _, row in df_meta.iterrows():
        key = row["key"]
        s = regions_ts[key]
        feats = similarity_utils.extract_catch22_features(s.values)
        feats["key"] = key
        features_list.append(feats)
        
    df_feats = pd.DataFrame(features_list).set_index("key").fillna(0.0)
    
    k_small, k_large = plot_clustering_evaluation_metrics(df_feats.values, out_prefix)
    
    active_ks_folders = []
    active_ks_folders.append((k_small, f"k_{k_small}"))
    if k_large is not None:
        active_ks_folders.append((k_large, f"k_{k_large}"))
        
    ph1_vals = df_meta["step1_cluster"].dropna().unique()
    ph1_vals = ph1_vals[ph1_vals != -1]
    k_ph1 = len(ph1_vals)
    
    covered_ks = [item[0] for item in active_ks_folders]
    if k_ph1 >= 2 and k_ph1 < len(df_meta) and k_ph1 not in covered_ks:
        active_ks_folders.append((k_ph1, f"k_{k_ph1}_ph1"))
        
    all_k_values = [item[0] for item in active_ks_folders]
    X_scaled, feat_results = run_clustering_and_evaluate(df_feats.values, df_feats.index.tolist(), None, k_values=all_k_values)
    
    print("Computing global pairwise DTW matrix...")
    dtw_matrix = similarity_utils.compute_distance_matrix(regions_ts, method="dtw", w=12)
    condensed_dtw = squareform(dtw_matrix, checks=False)
    Z_dtw = linkage(condensed_dtw, method='average')
    
    print("Computing global pairwise NCD matrix...")
    ncd_matrix = similarity_utils.compute_distance_matrix(regions_ts, method="ncd")
    condensed_ncd = squareform(ncd_matrix, checks=False)
    Z_ncd = linkage(condensed_ncd, method='average')
    
    for k, folder_name in active_ks_folders:
        k_dir = os.path.join(global_out_dir, folder_name)
        os.makedirs(k_dir, exist_ok=True)
        
        res_feat = next(r for r in feat_results if r["k"] == k)
        feat_labels = res_feat["kmeans_labels"]
        
        lbls_dtw = fcluster(Z_dtw, t=k, criterion='maxclust') - 1
        lbls_ncd = fcluster(Z_ncd, t=k, criterion='maxclust') - 1
        
        df_labels = pd.DataFrame({
            "key": df_meta["key"],
            "country": df_meta["country"],
            "adm1_pcode": df_meta["adm1_pcode"],
            "region_name": df_meta["region_name"],
            "catch22_kmeans_cluster": feat_labels,
            "dtw_hierarchical_cluster": lbls_dtw,
            "ncd_hierarchical_cluster": lbls_ncd
        })
        df_labels.to_csv(os.path.join(k_dir, "labels.csv"), index=False)
        
        compare_clustering_strategies(k_dir, df_labels, df_meta, regions_ts, X_scaled)
        
        strategies = [
            {"name": "catch22_kmeans", "labels": feat_labels, "dist_matrix": dtw_matrix},
            {"name": "dtw_hierarchical", "labels": lbls_dtw, "dist_matrix": dtw_matrix},
            {"name": "ncd_hierarchical", "labels": lbls_ncd, "dist_matrix": ncd_matrix}
        ]
        
        for strat in strategies:
            strat_name = strat["name"]
            strat_labels = strat["labels"]
            
            strat_dir = os.path.join(k_dir, strat_name)
            os.makedirs(strat_dir, exist_ok=True)
            
            plot_pca_comparison(
                X_scaled, 
                strat_labels, 
                f"Global Region Clusters ({strat_name}, k={k}) - PCA", 
                os.path.join(strat_dir, "pca.png")
            )
            plot_tsne_comparison(
                X_scaled,
                strat_labels,
                f"Global Region Clusters ({strat_name}, k={k}) - t-SNE",
                os.path.join(strat_dir, "tsne.png")
            )
            plot_umap_comparison(
                X_scaled,
                strat_labels,
                f"Global Region Clusters ({strat_name}, k={k}) - UMAP",
                os.path.join(strat_dir, "umap.png")
            )
            
            labels_dict = dict(zip(df_meta["key"].tolist(), strat_labels))
            plot_medoids(
                regions_ts, 
                labels_dict, 
                strat["dist_matrix"], 
                os.path.join(strat_dir, "medoids.png"),
                f"Global Medoids ({strat_name}, k={k})"
            )
            
            if boundaries_gdf is not None:
                plot_geographic_map(
                    boundaries_gdf, 
                    df_labels, 
                    "adm1_pcode", 
                    f"{strat_name}_cluster", 
                    f"Global Regional Map ({strat_name}, k={k})", 
                    os.path.join(strat_dir, "map.png"),
                    world_gdf=world_gdf
                )
                
            evaluate_ari_nmi(strat_labels, df_meta, regions_ts, strat_dir)

def run_global_multivariate_clustering(df_meta, regions_multivariate_ts, boundaries_gdf, world_gdf):
    """
    Extracts catch22 features, DTW, and NCD for multivariate indicators and geography.
    """
    print("\n--- Running Global Multivariate Analysis (with Geography) ---")
    m_out_dir = os.path.join(config.OUTPUT_DIR, "global_multivariate")
    os.makedirs(m_out_dir, exist_ok=True)
    
    out_prefix = os.path.join(m_out_dir, "global_multivariate")
    
    concatenated_features = []
    coords_list = []
    
    for _, row in df_meta.iterrows():
        key = row["key"]
        df_mv = regions_multivariate_ts[key]
        
        region_features = {"key": key}
        for col in config.MULTIVARIATE_COLS:
            s_val = df_mv[col].values
            col_feats = similarity_utils.extract_catch22_features(s_val)
            for f_name, f_val in col_feats.items():
                region_features[f"{col}_{f_name}"] = f_val
                
        concatenated_features.append(region_features)
        coords_list.append([row["latitude"], row["longitude"]])
        
    df_mv_feats = pd.DataFrame(concatenated_features).set_index("key").fillna(0.0)
    X_feats = df_mv_feats.values
    X_coords = np.array(coords_list)
    
    # Scale combined features for kmeans
    scaler_feats = StandardScaler()
    X_feats_scaled = scaler_feats.fit_transform(X_feats)
    
    scaler_coords = StandardScaler()
    X_coords_scaled = scaler_coords.fit_transform(X_coords)
    
    X_combined_scaled = np.hstack([X_feats_scaled, X_coords_scaled])
    scaler_combined = StandardScaler()
    X_combined_scaled = scaler_combined.fit_transform(X_combined_scaled)
    
    k_small, k_large = plot_clustering_evaluation_metrics(X_combined_scaled, out_prefix)
    
    active_ks_folders = []
    active_ks_folders.append((k_small, f"k_{k_small}"))
    if k_large is not None:
        active_ks_folders.append((k_large, f"k_{k_large}"))
        
    ph1_vals = df_meta["step1_cluster"].dropna().unique()
    ph1_vals = ph1_vals[ph1_vals != -1]
    k_ph1 = len(ph1_vals)
    
    covered_ks = [item[0] for item in active_ks_folders]
    if k_ph1 >= 2 and k_ph1 < len(df_meta) and k_ph1 not in covered_ks:
        active_ks_folders.append((k_ph1, f"k_{k_ph1}_ph1"))
        
    all_k_values = [item[0] for item in active_ks_folders]
    _, mv_results = run_clustering_and_evaluate(X_combined_scaled, df_mv_feats.index.tolist(), None, k_values=all_k_values)
    
    # Build list of series dicts to calculate shape distance matrices
    series_dicts = []
    for col in config.MULTIVARIATE_COLS:
        series_dicts.append({key: regions_multivariate_ts[key][col] for key in df_meta["key"]})
        
    print("Computing global pairwise Multivariate DTW matrix...")
    dtw_matrix = similarity_utils.get_combined_multivariate_distance_matrix(series_dicts, df_meta, method="dtw", w=12)
    condensed_dtw = squareform(dtw_matrix, checks=False)
    Z_dtw = linkage(condensed_dtw, method='average')
    
    print("Computing global pairwise Multivariate NCD matrix...")
    ncd_matrix = similarity_utils.get_combined_multivariate_distance_matrix(series_dicts, df_meta, method="ncd")
    condensed_ncd = squareform(ncd_matrix, checks=False)
    Z_ncd = linkage(condensed_ncd, method='average')
    
    for k, folder_name in active_ks_folders:
        k_dir = os.path.join(m_out_dir, folder_name)
        os.makedirs(k_dir, exist_ok=True)
        
        res_feat = next(r for r in mv_results if r["k"] == k)
        feat_labels = res_feat["kmeans_labels"]
        
        lbls_dtw = fcluster(Z_dtw, t=k, criterion='maxclust') - 1
        lbls_ncd = fcluster(Z_ncd, t=k, criterion='maxclust') - 1
        
        df_labels = pd.DataFrame({
            "key": df_meta["key"],
            "country": df_meta["country"],
            "adm1_pcode": df_meta["adm1_pcode"],
            "region_name": df_meta["region_name"],
            "multivariate_kmeans_cluster": feat_labels,
            "multivariate_dtw_hierarchical_cluster": lbls_dtw,
            "multivariate_ncd_hierarchical_cluster": lbls_ncd
        })
        df_labels.to_csv(os.path.join(k_dir, "labels.csv"), index=False)
        
        target_series_dict = {row["key"]: regions_multivariate_ts[row["key"]][config.TARGET_COL] for _, row in df_meta.iterrows()}
        compare_clustering_strategies(k_dir, df_labels, df_meta, target_series_dict, X_combined_scaled)

        
        strategies = [
            {"name": "multivariate_kmeans", "labels": feat_labels, "dist_matrix": dtw_matrix},
            {"name": "multivariate_dtw_hierarchical", "labels": lbls_dtw, "dist_matrix": dtw_matrix},
            {"name": "multivariate_ncd_hierarchical", "labels": lbls_ncd, "dist_matrix": ncd_matrix}
        ]
        
        for strat in strategies:
            strat_name = strat["name"]
            strat_labels = strat["labels"]
            
            strat_dir = os.path.join(k_dir, strat_name)
            os.makedirs(strat_dir, exist_ok=True)
            
            plot_pca_comparison(
                X_combined_scaled, 
                strat_labels, 
                f"Global Region Multivariate ({strat_name}, k={k}) - PCA", 
                os.path.join(strat_dir, "pca.png")
            )
            plot_tsne_comparison(
                X_combined_scaled,
                strat_labels,
                f"Global Region Multivariate ({strat_name}, k={k}) - t-SNE",
                os.path.join(strat_dir, "tsne.png")
            )
            plot_umap_comparison(
                X_combined_scaled,
                strat_labels,
                f"Global Region Multivariate ({strat_name}, k={k}) - UMAP",
                os.path.join(strat_dir, "umap.png")
            )
            
            # Plot medoids for target IPC
            labels_dict = dict(zip(df_meta["key"].tolist(), strat_labels))
            plot_medoids(
                {row["key"]: regions_multivariate_ts[row["key"]][config.TARGET_COL] for _, row in df_meta.iterrows()}, 
                labels_dict, 
                strat["dist_matrix"], 
                os.path.join(strat_dir, "medoids.png"),
                f"Global Multivariate Medoids ({strat_name}, k={k})"
            )
            
            if boundaries_gdf is not None:
                plot_geographic_map(
                    boundaries_gdf, 
                    df_labels, 
                    "adm1_pcode", 
                    f"{strat_name}_cluster", 
                    f"Global Multivariate Map ({strat_name}, k={k})", 
                    os.path.join(strat_dir, "map.png"),
                    world_gdf=world_gdf
                )
                
            evaluate_ari_nmi(strat_labels, df_meta, {row["key"]: regions_multivariate_ts[row["key"]][config.TARGET_COL] for _, row in df_meta.iterrows()}, strat_dir)

def run_national_univariate_clustering(df_meta, regions_ts, world_gdf):
    """
    Aggregates regional series to country-level averages using population-weighting,
    then clusters countries.
    """
    print("\n--- Running National-Level Univariate Clustering ---")
    nat_out_dir = os.path.join(config.OUTPUT_DIR, "national_univariate")
    os.makedirs(nat_out_dir, exist_ok=True)
    
    out_prefix = os.path.join(nat_out_dir, "national_univariate")
    
    national_series = {}
    
    for c_code, group in df_meta.groupby("country"):
        total_pop = group["adm1_population"].sum()
        if total_pop <= 0 or pd.isna(total_pop):
            total_pop = 1.0
            
        group["weight"] = group["adm1_population"] / total_pop
        
        series_list = []
        weights = []
        for _, row in group.iterrows():
            series_list.append(regions_ts[row["key"]])
            weights.append(row["weight"])
            
        df_concat = pd.concat(series_list, axis=1)
        weighted_avg = df_concat.multiply(weights, axis=1).sum(axis=1)
        
        national_series[c_code] = weighted_avg
        
    print(f"Aggregated national series for {len(national_series)} countries")
    
    nat_features_list = []
    for c_code, s in national_series.items():
        feats = similarity_utils.extract_catch22_features(s.values)
        feats["country"] = c_code
        nat_features_list.append(feats)
        
    df_nat_feats = pd.DataFrame(nat_features_list).set_index("country").fillna(0.0)
    
    max_k = min(8, len(df_nat_feats) - 1)
    
    if max_k >= 2:
        k_small, k_large = plot_clustering_evaluation_metrics(df_nat_feats.values, out_prefix, max_k=max_k)
        
        active_ks_folders = []
        active_ks_folders.append((k_small, f"k_{k_small}"))
        if k_large is not None and k_large <= max_k:
            active_ks_folders.append((k_large, f"k_{k_large}"))
            
        ph1_vals = df_meta["step1_cluster"].dropna().unique()
        ph1_vals = ph1_vals[ph1_vals != -1]
        k_ph1 = len(ph1_vals)
        
        covered_ks = [item[0] for item in active_ks_folders]
        if k_ph1 >= 2 and k_ph1 <= max_k and k_ph1 not in covered_ks:
            active_ks_folders.append((k_ph1, f"k_{k_ph1}_ph1"))
            
        all_k_values = [item[0] for item in active_ks_folders]
        X_scaled, nat_results = run_clustering_and_evaluate(df_nat_feats.values, df_nat_feats.index.tolist(), None, k_values=all_k_values)
        
        dtw_matrix = similarity_utils.compute_distance_matrix(national_series, method="dtw", w=12)
        condensed_dtw = squareform(dtw_matrix, checks=False)
        Z_dtw = linkage(condensed_dtw, method='average')
        
        ncd_matrix = similarity_utils.compute_distance_matrix(national_series, method="ncd")
        condensed_ncd = squareform(ncd_matrix, checks=False)
        Z_ncd = linkage(condensed_ncd, method='average')
        
        for k, folder_name in active_ks_folders:
            k_dir = os.path.join(nat_out_dir, folder_name)
            os.makedirs(k_dir, exist_ok=True)
            
            res_feat = next(r for r in nat_results if r["k"] == k)
            feat_labels = res_feat["kmeans_labels"]
            
            lbls_dtw = fcluster(Z_dtw, t=k, criterion='maxclust') - 1
            lbls_ncd = fcluster(Z_ncd, t=k, criterion='maxclust') - 1
            
            df_labels = pd.DataFrame({
                "country": df_nat_feats.index,
                "catch22_kmeans_cluster": feat_labels,
                "dtw_hierarchical_cluster": lbls_dtw,
                "ncd_hierarchical_cluster": lbls_ncd
            })
            df_labels.to_csv(os.path.join(k_dir, "labels.csv"), index=False)
            
            df_meta_eval = df_meta.copy()
            df_meta_eval["key"] = df_meta_eval["country"]
            df_nat_series_eval = {c_code: s for c_code, s in national_series.items()}
            
            compare_clustering_strategies(k_dir, df_labels, df_meta_eval.drop_duplicates(subset=["key"]), df_nat_series_eval, X_scaled)
            
            strategies = [
                {"name": "catch22_kmeans", "labels": feat_labels, "dist_matrix": dtw_matrix},
                {"name": "dtw_hierarchical", "labels": lbls_dtw, "dist_matrix": dtw_matrix},
                {"name": "ncd_hierarchical", "labels": lbls_ncd, "dist_matrix": ncd_matrix}
            ]
            
            for strat in strategies:
                strat_name = strat["name"]
                strat_labels = strat["labels"]
                
                strat_dir = os.path.join(k_dir, strat_name)
                os.makedirs(strat_dir, exist_ok=True)
                
                plot_pca_comparison(
                    X_scaled, 
                    strat_labels, 
                    f"National Country Clusters ({strat_name}, k={k}) - PCA", 
                    os.path.join(strat_dir, "pca.png"),
                    names=df_nat_feats.index.tolist()
                )
                plot_tsne_comparison(
                    X_scaled,
                    strat_labels,
                    f"National Country Clusters ({strat_name}, k={k}) - t-SNE",
                    os.path.join(strat_dir, "tsne.png"),
                    perplexity=10
                )
                plot_umap_comparison(
                    X_scaled,
                    strat_labels,
                    f"National Country Clusters ({strat_name}, k={k}) - UMAP",
                    os.path.join(strat_dir, "umap.png"),
                    n_neighbors=10
                )
                
                labels_dict = dict(zip(df_nat_feats.index.tolist(), strat_labels))
                plot_medoids(
                    national_series, 
                    labels_dict, 
                    strat["dist_matrix"], 
                    os.path.join(strat_dir, "medoids.png"),
                    f"National Medoids ({strat_name}, k={k})"
                )
                
                if world_gdf is not None:
                    try:
                        world = world_gdf.copy()
                        world["iso_a3"] = world["iso_a3"].astype(str).str.upper()
                        df_labels["country"] = df_labels["country"].astype(str).str.upper()
                        
                        world_merged = world.merge(df_labels, left_on="iso_a3", right_on="country", how="left")
                        
                        fig, ax = plt.subplots(figsize=(18, 10))
                        world.plot(color="#f4f4f4", edgecolor="#dcdcdc", linewidth=0.5, ax=ax)
                        
                        unique_labels = np.sort(np.unique(strat_labels))
                        max_lbl = int(np.max(unique_labels))
                        cmap_colors = [CLUSTER_COLORS[i % len(CLUSTER_COLORS)] for i in range(max_lbl + 1)]
                        cmap = ListedColormap(cmap_colors)
                        
                        world_merged.dropna(subset=[f"{strat_name}_cluster"]).plot(
                            column=f"{strat_name}_cluster", 
                            cmap=cmap, 
                            legend=True, 
                            categorical=True,
                            ax=ax, 
                            legend_kwds={"title": "Cluster", "bbox_to_anchor": (1.05, 1), "loc": "upper left"}
                        )
                        ax.set_title(f"Global Country Map ({strat_name}, k={k})", fontsize=16)
                        ax.set_xlim([-120, 150])
                        ax.set_ylim([-40, 60])
                        ax.set_axis_off()
                        plt.tight_layout()
                        plt.savefig(os.path.join(strat_dir, "map.png"), dpi=150)
                        plt.close()
                    except Exception as e:
                        print(f"Error plotting national map for {strat_name}: {e}")
                        
                evaluate_ari_nmi(strat_labels, df_meta_eval.drop_duplicates(subset=["key"]), df_nat_series_eval, strat_dir)
    else:
        print("Not enough countries to run clustering.")

def run_national_multivariate_clustering(df_meta, regions_multivariate_ts, world_gdf):
    """
    Aggregates regional multivariate series to country-level averages using population weighting,
    then clusters countries using combined features + country coordinates.
    """
    print("\n--- Running National-Level Multivariate Clustering ---")
    nat_mv_out_dir = os.path.join(config.OUTPUT_DIR, "national_multivariate")
    os.makedirs(nat_mv_out_dir, exist_ok=True)
    
    out_prefix = os.path.join(nat_mv_out_dir, "national_multivariate")
    
    national_mv_series = {}
    country_coords = {}
    
    for c_code, group in df_meta.groupby("country"):
        total_pop = group["adm1_population"].sum()
        if total_pop <= 0 or pd.isna(total_pop):
            total_pop = 1.0
            
        group["weight"] = group["adm1_population"] / total_pop
        
        lat_avg = group["latitude"].mean()
        lon_avg = group["longitude"].mean()
        country_coords[c_code] = [lat_avg, lon_avg]
        
        c_cols_series = {}
        for col in config.MULTIVARIATE_COLS:
            series_list = []
            weights = []
            for _, row in group.iterrows():
                key = row["key"]
                series_list.append(regions_multivariate_ts[key][col])
                weights.append(row["weight"])
                
            df_concat = pd.concat(series_list, axis=1)
            weighted_avg = df_concat.multiply(weights, axis=1).sum(axis=1)
            c_cols_series[col] = weighted_avg
            
        national_mv_series[c_code] = c_cols_series
        
    print(f"Aggregated national multivariate series for {len(national_mv_series)} countries")
    
    concatenated_features = []
    coords_list = []
    countries_list = list(national_mv_series.keys())
    
    for c_code in countries_list:
        c_features = {"country": c_code}
        for col in config.MULTIVARIATE_COLS:
            s_val = national_mv_series[c_code][col].values
            col_feats = similarity_utils.extract_catch22_features(s_val)
            for f_name, f_val in col_feats.items():
                c_features[f"{col}_{f_name}"] = f_val
                
        concatenated_features.append(c_features)
        coords_list.append(country_coords[c_code])
        
    df_mv_feats = pd.DataFrame(concatenated_features).set_index("country").fillna(0.0)
    X_feats = df_mv_feats.values
    X_coords = np.array(coords_list)
    
    scaler_feats = StandardScaler()
    X_feats_scaled = scaler_feats.fit_transform(X_feats)
    
    scaler_coords = StandardScaler()
    X_coords_scaled = scaler_coords.fit_transform(X_coords)
    
    X_combined_scaled = np.hstack([X_feats_scaled, X_coords_scaled])
    
    scaler_combined = StandardScaler()
    X_combined_scaled = scaler_combined.fit_transform(X_combined_scaled)
    
    max_k = min(8, len(df_mv_feats) - 1)
    
    if max_k >= 2:
        k_small, k_large = plot_clustering_evaluation_metrics(X_combined_scaled, out_prefix, max_k=max_k)
        
        active_ks_folders = []
        active_ks_folders.append((k_small, f"k_{k_small}"))
        if k_large is not None and k_large <= max_k:
            active_ks_folders.append((k_large, f"k_{k_large}"))
            
        ph1_vals = df_meta["step1_cluster"].dropna().unique()
        ph1_vals = ph1_vals[ph1_vals != -1]
        k_ph1 = len(ph1_vals)
        
        covered_ks = [item[0] for item in active_ks_folders]
        if k_ph1 >= 2 and k_ph1 <= max_k and k_ph1 not in covered_ks:
            active_ks_folders.append((k_ph1, f"k_{k_ph1}_ph1"))
            
        all_k_values = [item[0] for item in active_ks_folders]
        _, mv_results = run_clustering_and_evaluate(X_combined_scaled, df_mv_feats.index.tolist(), None, k_values=all_k_values)
        
        # Build series dicts
        series_dicts = []
        for col in config.MULTIVARIATE_COLS:
            series_dicts.append({c_code: national_mv_series[c_code][col] for c_code in countries_list})
            
        # Shape distance matrices
        dtw_matrix = similarity_utils.get_combined_multivariate_distance_matrix(series_dicts, df_meta.drop_duplicates(subset=["country"]), method="dtw", w=12, index_col="country")
        condensed_dtw = squareform(dtw_matrix, checks=False)
        Z_dtw = linkage(condensed_dtw, method='average')
        
        ncd_matrix = similarity_utils.get_combined_multivariate_distance_matrix(series_dicts, df_meta.drop_duplicates(subset=["country"]), method="ncd", index_col="country")
        condensed_ncd = squareform(ncd_matrix, checks=False)
        Z_ncd = linkage(condensed_ncd, method='average')

        
        for k, folder_name in active_ks_folders:
            k_dir = os.path.join(nat_mv_out_dir, folder_name)
            os.makedirs(k_dir, exist_ok=True)
            
            res_feat = next(r for r in mv_results if r["k"] == k)
            feat_labels = res_feat["kmeans_labels"]
            
            lbls_dtw = fcluster(Z_dtw, t=k, criterion='maxclust') - 1
            lbls_ncd = fcluster(Z_ncd, t=k, criterion='maxclust') - 1
            
            df_labels = pd.DataFrame({
                "country": df_mv_feats.index,
                "multivariate_kmeans_cluster": feat_labels,
                "multivariate_dtw_hierarchical_cluster": lbls_dtw,
                "multivariate_ncd_hierarchical_cluster": lbls_ncd
            })
            df_labels.to_csv(os.path.join(k_dir, "labels.csv"), index=False)
            
            df_meta_eval = df_meta.copy()
            df_meta_eval["key"] = df_meta_eval["country"]
            df_nat_series_eval = {c_code: s[config.TARGET_COL] for c_code, s in national_mv_series.items()}
            
            compare_clustering_strategies(k_dir, df_labels, df_meta_eval.drop_duplicates(subset=["key"]), df_nat_series_eval, X_combined_scaled)
            
            strategies = [
                {"name": "multivariate_kmeans", "labels": feat_labels, "dist_matrix": dtw_matrix},
                {"name": "multivariate_dtw_hierarchical", "labels": lbls_dtw, "dist_matrix": dtw_matrix},
                {"name": "multivariate_ncd_hierarchical", "labels": lbls_ncd, "dist_matrix": ncd_matrix}
            ]
            
            for strat in strategies:
                strat_name = strat["name"]
                strat_labels = strat["labels"]
                
                strat_dir = os.path.join(k_dir, strat_name)
                os.makedirs(strat_dir, exist_ok=True)
                
                plot_pca_comparison(
                    X_combined_scaled, 
                    strat_labels, 
                    f"National Multivariate Country ({strat_name}, k={k}) - PCA", 
                    os.path.join(strat_dir, "pca.png"),
                    names=df_mv_feats.index.tolist()
                )
                plot_tsne_comparison(
                    X_combined_scaled,
                    strat_labels,
                    f"National Multivariate Country ({strat_name}, k={k}) - t-SNE",
                    os.path.join(strat_dir, "tsne.png"),
                    perplexity=10
                )
                plot_umap_comparison(
                    X_combined_scaled,
                    strat_labels,
                    f"National Multivariate Country ({strat_name}, k={k}) - UMAP",
                    os.path.join(strat_dir, "umap.png"),
                    n_neighbors=10
                )
                
                labels_dict = dict(zip(df_mv_feats.index.tolist(), strat_labels))
                plot_medoids(
                    {c_code: s[config.TARGET_COL] for c_code, s in national_mv_series.items()}, 
                    labels_dict, 
                    strat["dist_matrix"], 
                    os.path.join(strat_dir, "medoids.png"),
                    f"National Multivariate Medoids ({strat_name}, k={k})"
                )
                
                if world_gdf is not None:
                    try:
                        world = world_gdf.copy()
                        world["iso_a3"] = world["iso_a3"].astype(str).str.upper()
                        df_labels["country"] = df_labels["country"].astype(str).str.upper()
                        
                        world_merged = world.merge(df_labels, left_on="iso_a3", right_on="country", how="left")
                        
                        fig, ax = plt.subplots(figsize=(18, 10))
                        world.plot(color="#f4f4f4", edgecolor="#dcdcdc", linewidth=0.5, ax=ax)
                        
                        unique_labels = np.sort(np.unique(strat_labels))
                        max_lbl = int(np.max(unique_labels))
                        cmap_colors = [CLUSTER_COLORS[i % len(CLUSTER_COLORS)] for i in range(max_lbl + 1)]
                        cmap = ListedColormap(cmap_colors)
                        
                        world_merged.dropna(subset=[f"{strat_name}_cluster"]).plot(
                            column=f"{strat_name}_cluster", 
                            cmap=cmap, 
                            legend=True, 
                            categorical=True,
                            ax=ax, 
                            legend_kwds={"title": "Cluster", "bbox_to_anchor": (1.05, 1), "loc": "upper left"}
                        )
                        ax.set_title(f"Global Country Multivariate Map ({strat_name}, k={k})", fontsize=16)
                        ax.set_xlim([-120, 150])
                        ax.set_ylim([-40, 60])
                        ax.set_axis_off()
                        plt.tight_layout()
                        plt.savefig(os.path.join(strat_dir, "map.png"), dpi=150)
                        plt.close()
                    except Exception as e:
                        print(f"Error plotting national multivariate map: {e}")
                        
                evaluate_ari_nmi(strat_labels, df_meta_eval.drop_duplicates(subset=["key"]), df_nat_series_eval, strat_dir)
    else:
        print("Not enough countries to run clustering.")

def generate_univariate_vs_multivariate_crosstabs(level):
    """
    Computes and plots contingency crosstabs between Univariate and Multivariate cluster assignments.
    Saves in a dedicated results/crosstabs_uni_vs_multi folder.
    """
    print(f"\n--- Generating Univariate vs Multivariate Crosstabs ({level}) ---")
    if level == "global":
        uni_dir = os.path.join(config.OUTPUT_DIR, "global_univariate")
        mv_dir = os.path.join(config.OUTPUT_DIR, "global_multivariate")
        id_col = "key"
        uni_clust_col = "catch22_kmeans_cluster"
        mv_clust_col = "multivariate_kmeans_cluster"
    elif level == "national":
        uni_dir = os.path.join(config.OUTPUT_DIR, "national_univariate")
        mv_dir = os.path.join(config.OUTPUT_DIR, "national_multivariate")
        id_col = "country"
        uni_clust_col = "catch22_kmeans_cluster"
        mv_clust_col = "multivariate_kmeans_cluster"
    else:
        return
        
    if not os.path.exists(uni_dir) or not os.path.exists(mv_dir):
        print("Required directories do not exist.")
        return
        
    crosstabs_dir = os.path.join(config.OUTPUT_DIR, "crosstabs_uni_vs_multi")
    os.makedirs(crosstabs_dir, exist_ok=True)
        
    k_folders = [d for d in os.listdir(mv_dir) if os.path.isdir(os.path.join(mv_dir, d)) and d.startswith("k_")]
    
    for folder_name in k_folders:
        uni_labels_path = os.path.join(uni_dir, folder_name, "labels.csv")
        mv_labels_path = os.path.join(mv_dir, folder_name, "labels.csv")
        
        if os.path.exists(uni_labels_path) and os.path.exists(mv_labels_path):
            try:
                df_uni = pd.read_csv(uni_labels_path)
                df_mv = pd.read_csv(mv_labels_path)
                
                df_merged = pd.merge(df_uni[[id_col, uni_clust_col]], df_mv[[id_col, mv_clust_col]], on=id_col)
                if df_merged.empty:
                    continue
                    
                ari = adjusted_rand_score(df_merged[uni_clust_col], df_merged[mv_clust_col])
                nmi = normalized_mutual_info_score(df_merged[uni_clust_col], df_merged[mv_clust_col])
                
                print(f"  -> {folder_name}: Univariate vs Multivariate ARI = {ari:.4f}, NMI = {nmi:.4f}")
                
                crosstab_df = pd.crosstab(df_merged[mv_clust_col], df_merged[uni_clust_col])
                
                plt.figure(figsize=(8, 6))
                sns.heatmap(crosstab_df, annot=True, fmt="d", cmap="Blues", cbar=True)
                plt.title(f"{level.capitalize()} {folder_name.upper()}\nUnivariate vs. Multivariate Clusters\n(ARI={ari:.4f}, NMI={nmi:.4f})", fontsize=12)
                plt.xlabel("Univariate Cluster (catch22_kmeans)")
                plt.ylabel("Multivariate Cluster (pycatch22+Geo)")
                plt.tight_layout()
                
                out_path = os.path.join(crosstabs_dir, f"{level}_uni_vs_multi_crosstab_{folder_name}.png")
                plt.savefig(out_path, dpi=150)
                plt.close()
                
            except Exception as e:
                print(f"Error generating crosstab for {folder_name}: {e}")

def generate_global_vs_national_crosstabs():
    """
    Computes and plots contingency crosstabs between Global (regional) and National (country-level) cluster assignments.
    This is evaluated at the region level (mapping country clusters to its regions).
    """
    print("\n--- Generating Global vs National Crosstabs ---")
    
    settings = [
        {
            "name": "univariate",
            "global_dir": os.path.join(config.OUTPUT_DIR, "global_univariate"),
            "national_dir": os.path.join(config.OUTPUT_DIR, "national_univariate"),
            "global_col": "catch22_kmeans_cluster",
            "national_col": "catch22_kmeans_cluster",
            "out_filename": "global_vs_national_univariate_crosstab.png"
        },
        {
            "name": "multivariate",
            "global_dir": os.path.join(config.OUTPUT_DIR, "global_multivariate"),
            "national_dir": os.path.join(config.OUTPUT_DIR, "national_multivariate"),
            "global_col": "multivariate_kmeans_cluster",
            "national_col": "multivariate_kmeans_cluster",
            "out_filename": "global_vs_national_multivariate_crosstab.png"
        }
    ]
    
    for s in settings:
        g_dir = s["global_dir"]
        n_dir = s["national_dir"]
        
        if not os.path.exists(g_dir) or not os.path.exists(n_dir):
            continue
            
        k_folders = [d for d in os.listdir(g_dir) if os.path.isdir(os.path.join(g_dir, d)) and d.startswith("k_")]
        
        for folder_name in k_folders:
            g_labels_path = os.path.join(g_dir, folder_name, "labels.csv")
            n_labels_path = os.path.join(n_dir, folder_name, "labels.csv")
            
            if os.path.exists(g_labels_path) and os.path.exists(n_labels_path):
                try:
                    df_global = pd.read_csv(g_labels_path)
                    df_national = pd.read_csv(n_labels_path)
                    
                    df_global["country"] = df_global["country"].astype(str).str.upper()
                    df_national["country"] = df_national["country"].astype(str).str.upper()
                    
                    df_national = df_national.rename(columns={s["national_col"]: "national_cluster"})
                    
                    df_merged = pd.merge(df_global, df_national[["country", "national_cluster"]], on="country", how="inner")
                    
                    if df_merged.empty:
                        continue
                        
                    ari = adjusted_rand_score(df_merged[s["global_col"]], df_merged["national_cluster"])
                    nmi = normalized_mutual_info_score(df_merged[s["global_col"]], df_merged["national_cluster"])
                    
                    print(f"  -> {s['name']} ({folder_name}): Global vs National ARI = {ari:.4f}, NMI = {nmi:.4f}")
                    
                    crosstab_df = pd.crosstab(df_merged["national_cluster"], df_merged[s["global_col"]])
                    
                    plt.figure(figsize=(8, 6))
                    sns.heatmap(crosstab_df, annot=True, fmt="d", cmap="Purples", cbar=True)
                    plt.title(f"Global vs. National {s['name'].capitalize()} ({folder_name.upper()})\nEvaluated at Regional Level\n(ARI={ari:.4f}, NMI={nmi:.4f})", fontsize=12)
                    plt.xlabel(f"Global Regional Cluster ({s['global_col']})")
                    plt.ylabel("National Country Cluster (mapped to regions)")
                    plt.tight_layout()
                    
                    plt.savefig(os.path.join(g_dir, folder_name, s["out_filename"]), dpi=150)
                    plt.savefig(os.path.join(n_dir, folder_name, s["out_filename"]), dpi=150)
                    plt.close()
                    
                except Exception as e:
                    print(f"Error generating global vs national crosstab for {folder_name}: {e}")

def main():
    print("=================================================================")
    print(" HERO Time Series Clustering Pipeline (Step 3)")
    print("=================================================================")
    
    df_meta, regions_ts, regions_multivariate_ts = load_and_prepare_data()
    
    boundaries_gdf = load_geography_boundaries(df_meta)
    if boundaries_gdf is not None:
        print(f"Loaded {len(boundaries_gdf)} geographical boundaries from boundaries directories.")
    else:
        print("No geographical boundaries loaded.")
        
    world_gdf = load_world_boundaries()
    if world_gdf is not None:
        print("Loaded global world map boundaries for plotting.")
    else:
        print("Global world boundaries not loaded.")
        
    run_country_level_clustering(df_meta, regions_ts, boundaries_gdf)
    run_global_univariate_clustering(df_meta, regions_ts, boundaries_gdf, world_gdf)
    run_global_multivariate_clustering(df_meta, regions_multivariate_ts, boundaries_gdf, world_gdf)
    run_national_univariate_clustering(df_meta, regions_ts, world_gdf)
    run_national_multivariate_clustering(df_meta, regions_multivariate_ts, world_gdf)
    
    generate_univariate_vs_multivariate_crosstabs("global")
    generate_univariate_vs_multivariate_crosstabs("national")
    
    generate_global_vs_national_crosstabs()
    
    print("\n=================================================================")
    print(" Pipeline Execution Completed Successfully!")
    print(f" Outputs saved in: {config.OUTPUT_DIR}")
    print("=================================================================")

if __name__ == "__main__":
    main()
