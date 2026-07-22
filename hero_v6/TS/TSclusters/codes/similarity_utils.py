import numpy as np
import pandas as pd
import gzip
import pycatch22
from scipy.spatial.distance import squareform
from scipy.cluster.hierarchy import linkage, fcluster
from numba import njit

def z_score_normalize(series):
    """
    Standardizes series to mean=0 and std=1.
    If standard deviation is zero or NaN, returns a series of zeros.
    """
    arr = np.array(series, dtype=float)
    s_std = np.std(arr)
    if s_std == 0 or np.isnan(s_std):
        return arr - np.mean(arr)
    return (arr - np.mean(arr)) / s_std

@njit
def dtw_distance_numba(a1, a2, w):
    """
    Numba-optimized Dynamic Time Warping (DTW) distance with Sakoe-Chiba constraint.
    """
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
    """
    Computes Dynamic Time Warping (DTW) distance using Numba compilation.
    """
    a1 = np.array(s1, dtype=np.float64)
    a2 = np.array(s2, dtype=np.float64)
    n, m = len(a1), len(a2)
    
    if w is None:
        w_val = max(n, m)
    else:
        w_val = max(int(w), abs(n - m))
        
    return dtw_distance_numba(a1, a2, w_val)

def compute_ncd(s1, s2):
    """
    Computes the Normalized Compression Distance (NCD) using gzip.
    The float series are converted to bytes.
    """
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

def compute_distance_matrix(series_dict, method="dtw", w=None):
    """
    Computes pairwise distance matrix between multiple series.
    Keys in series_dict are identifiers (e.g. adm1_pcodes).
    """
    names = list(series_dict.keys())
    n = len(names)
    matrix = np.zeros((n, n))
    
    cleaned_series = {}
    for name in names:
        s = pd.Series(series_dict[name]).interpolate(method="linear").ffill().bfill().values
        if method in ["dtw", "euclidean"]:
            cleaned_series[name] = z_score_normalize(s)
        else:
            cleaned_series[name] = s
            
    for i in range(n):
        for j in range(i, n):
            if i == j:
                dist = 0.0
            else:
                name_i, name_j = names[i], names[j]
                s_i, s_j = cleaned_series[name_i], cleaned_series[name_j]
                
                if method == "dtw":
                    dist = dtw_distance(s_i, s_j, w=w)
                elif method == "ncd":
                    dist = compute_ncd(s_i, s_j)
                elif method == "euclidean":
                    dist = np.sqrt(np.mean((s_i - s_j) ** 2))
                else:
                    raise ValueError(f"Unknown distance method: {method}")
            
            matrix[i, j] = dist
            matrix[j, i] = dist
            
    return pd.DataFrame(matrix, index=names, columns=names)

def compute_multivariate_distance_matrix(series_dicts, method="dtw", w=None):
    """
    Computes pairwise average shape distance matrix across multiple variables.
    series_dicts is a list of dictionaries, one for each variable's time series.
    """
    names = list(series_dicts[0].keys())
    n = len(names)
    
    # Sum distance matrices for each variable
    sum_matrix = np.zeros((n, n))
    for s_dict in series_dicts:
        df_dist = compute_distance_matrix(s_dict, method=method, w=w)
        sum_matrix += df_dist.values
        
    avg_matrix = sum_matrix / len(series_dicts)
    return pd.DataFrame(avg_matrix, index=names, columns=names)

def get_combined_multivariate_distance_matrix(series_dicts, df_meta, method="dtw", w=None, index_col="key"):
    """
    Computes combined distance matrix: Standardized(Shape) + Standardized(Geo).
    """
    # 1. Compute shape distance matrix (average over variables)
    df_shape = compute_multivariate_distance_matrix(series_dicts, method=method, w=w)
    D_shape = df_shape.values
    
    # 2. Compute geographical distance matrix
    names = list(df_shape.index)
    n = len(names)
    D_geo = np.zeros((n, n))
    
    # Map name to coordinate metadata
    meta_map = df_meta.set_index(index_col)

    
    for i in range(n):
        for j in range(i, n):
            name_i, name_j = names[i], names[j]
            lat_i = meta_map.loc[name_i, "latitude"]
            lon_i = meta_map.loc[name_i, "longitude"]
            lat_j = meta_map.loc[name_j, "latitude"]
            lon_j = meta_map.loc[name_j, "longitude"]
            
            # If multiple rows have the same index (e.g. during country aggregation)
            if isinstance(lat_i, pd.Series):
                lat_i = lat_i.mean()
                lon_i = lon_i.mean()
            if isinstance(lat_j, pd.Series):
                lat_j = lat_j.mean()
                lon_j = lon_j.mean()
                
            dist_geo = np.sqrt((lat_i - lat_j)**2 + (lon_i - lon_j)**2)
            D_geo[i, j] = dist_geo
            D_geo[j, i] = dist_geo
            
    # 3. Standardize distance matrices to make them comparable
    std_shape = np.std(D_shape) if np.std(D_shape) > 0 else 1.0
    std_geo = np.std(D_geo) if np.std(D_geo) > 0 else 1.0
    
    D_shape_scaled = D_shape / std_shape
    D_geo_scaled = D_geo / std_geo
    
    D_combined = D_shape_scaled + D_geo_scaled
    return pd.DataFrame(D_combined, index=names, columns=names)

def extract_catch22_features(values):
    """
    Extracts catch22 features from a 1D array of values.
    Returns a dictionary of feature names and values.
    """
    arr = np.array(values, dtype=float)
    arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
    
    try:
        res = pycatch22.catch22_all(list(arr))
        return dict(zip(res['names'], res['values']))
    except Exception as e:
        return {}

def find_cluster_medoid(series_dict, labels, cluster_id, distance_matrix):
    """
    Finds the medoid of a cluster (the series that minimizes the average distance
    to all other series in the cluster).
    Returns the key of the medoid.
    """
    cluster_keys = [k for k, lbl in labels.items() if lbl == cluster_id]
    if not cluster_keys:
        return None
    if len(cluster_keys) == 1:
        return cluster_keys[0]
        
    sub_matrix = distance_matrix.loc[cluster_keys, cluster_keys]
    sum_distances = sub_matrix.sum(axis=1)
    medoid_key = sum_distances.idxmin()
    return medoid_key
