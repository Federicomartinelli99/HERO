import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from scipy.cluster.hierarchy import linkage, fcluster, dendrogram
from scipy.spatial.distance import squareform
from statsmodels.tsa.ar_model import AutoReg


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
        x = np.array([y[i: i + m_val] for i in range(n - m_val + 1)])
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


def run_clustering_flow(df_feat, series_dict, out_prefix, n_clusters=4, is_global=False, feature_cols=None):
    """
    Runs the clustering analysis:
    - Feature-based hierarchical clustering (with and without coordinates)
    - Feature-based K-Means (with and without coordinates)
    - Shape-based (DTW) hierarchical clustering (only if not global)
    - Saves plots and returns silhouette scores and label dataframes
    """
    # FIX 1: Se non passi le colonne dal notebook, usa la lista di default per evitare NameError
    if feature_cols is None:
        feature_cols = ["stat_mean", "stat_var", "stat_skew", "stat_kurt", "hurst_exponent", "approx_entropy",
                        "ar1_coeff", "ar2_coeff", "ar3_coeff"]

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

    sil_hier_no_coords = silhouette_score(X_feats_scaled, labels_hier_no_coords) if len(
        np.unique(labels_hier_no_coords)) > 1 else -1
    sil_km_no_coords = silhouette_score(X_feats_scaled, labels_km_no_coords) if len(
        np.unique(labels_km_no_coords)) > 1 else -1

    # PCA for visualization (baseline)
    pca = PCA(n_components=2)
    X_pca_no_coords = pca.fit_transform(X_feats_scaled)

    # --- B. FEATURE-BASED CLUSTERING WITH COORDINATES ---
    Z_feat_with_coords = linkage(X_combined_scaled, method='ward')
    labels_hier_with_coords = fcluster(Z_feat_with_coords, t=n_clusters, criterion='maxclust')

    kmeans_with_coords = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels_km_with_coords = kmeans_with_coords.fit_predict(X_combined_scaled)

    sil_hier_with_coords = silhouette_score(X_combined_scaled, labels_hier_with_coords) if len(
        np.unique(labels_hier_with_coords)) > 1 else -1
    sil_km_with_coords = silhouette_score(X_combined_scaled, labels_km_with_coords) if len(
        np.unique(labels_km_with_coords)) > 1 else -1

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
    sns.scatterplot(x=X_pca_no_coords[:, 0], y=X_pca_no_coords[:, 1], hue=labels_km_no_coords, palette="tab10", s=100,
                    ax=axes[0])
    axes[0].set_title("K-Means Clustering on PCA (NO Coordinates)")
    axes[0].set_xlabel("PC 1")
    axes[0].set_ylabel("PC 2")
    axes[0].legend(title="Cluster")

    # Annotate region names if small dataset
    if len(df_feat) <= 35:
        for i, txt in enumerate(df_feat["region_name"]):
            axes[0].annotate(txt, (X_pca_no_coords[i, 0] + 0.05, X_pca_no_coords[i, 1] + 0.05), fontsize=7, alpha=0.8)

    sns.scatterplot(x=X_pca_with_coords[:, 0], y=X_pca_with_coords[:, 1], hue=labels_km_with_coords, palette="tab10",
                    s=100, ax=axes[1])
    axes[1].set_title("K-Means Clustering on PCA (WITH Coordinates)")
    axes[1].set_xlabel("PC 1")
    axes[1].set_ylabel("PC 2")
    axes[1].legend(title="Cluster")

    if len(df_feat) <= 35:
        for i, txt in enumerate(df_feat["region_name"]):
            axes[1].annotate(txt, (X_pca_with_coords[i, 0] + 0.05, X_pca_with_coords[i, 1] + 0.05), fontsize=7,
                             alpha=0.8)

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

    # FIX 2: Inizializza la colonna DTW a -1 (valore standard per "Non Calcolato")
    df_labels["hierarchical_shape_dtw"] = -1
    if shape_labels_series is not None:
        df_labels["hierarchical_shape_dtw"] = df_labels["adm1_pcode"].map(shape_labels_series).fillna(-1).astype(int)

    results = {
        "labels_df": df_labels,
        "metrics": {
            "sil_hier_no_coords": float(sil_hier_no_coords),
            "sil_km_no_coords": float(sil_km_no_coords),
            "sil_hier_with_coords": float(sil_hier_with_coords),
            "sil_km_with_coords": float(sil_km_with_coords)
        }
    }
    return results