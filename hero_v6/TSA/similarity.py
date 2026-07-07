import numpy as np
import pandas as pd
from scipy.stats import norm
from statsmodels.tsa.ar_model import AutoReg

def z_score_normalize(series):
    """
    Applies z-score normalization to remove offset translation and amplitude scaling.
    """
    s_std = series.std()
    if s_std == 0 or np.isnan(s_std):
        return series - series.mean()
    return (series - series.mean()) / s_std

def dtw_distance(s1, s2, w=None):
    """
    Computes the Dynamic Time Warping (DTW) distance between two series
    with a Sakoe-Chiba band constraint of width w.
    """
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

def paa_transform(series, w_segments):
    """
    Piecewise Aggregate Approximation (PAA):
    Reduces a series of length n to w_segments by averaging values in windows.
    """
    a = np.array(series)
    n = len(a)
    if n == w_segments:
        return a
    
    if n % w_segments == 0:
        return a.reshape(w_segments, -1).mean(axis=1)
        
    paa = np.zeros(w_segments)
    for i in range(n * w_segments):
        idx_series = i // w_segments
        idx_paa = i // n
        paa[idx_paa] += a[idx_series]
    return paa / n

def get_sax_breakpoints(a_size):
    """
    Returns standard Gaussian breakpoints dividing normal distribution into equiprobable regions.
    """
    return norm.ppf(np.linspace(1.0 / a_size, 1.0 - 1.0 / a_size, a_size - 1))

def sax_transform(series, w_segments, a_size=4):
    """
    Symbolic Aggregate Approximation (SAX):
    Normalizes series, applies PAA, and maps to characters.
    """
    norm_series = z_score_normalize(series)
    paa = paa_transform(norm_series, w_segments)
    breakpoints = get_sax_breakpoints(a_size)
    symbols = []
    alphabet = [chr(i) for i in range(ord('a'), ord('a') + a_size)]
    
    for val in paa:
        symbol_idx = np.digitize(val, breakpoints)
        symbols.append(alphabet[symbol_idx])
        
    return "".join(symbols)

def compute_similarity_matrix(series_dict, method="dtw", w=None):
    """
    Computes a pairwise similarity (distance) matrix between multiple series.
    """
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

# --- Advanced Structural Feature Extraction ---

def calculate_hurst(series):
    """
    Computes the Hurst exponent of a series using a simplified R/S analysis.
    """
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
    """
    Computes Approximate Entropy (ApEn) for the time series.
    """
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
    """
    Extracts a vector of structural features:
    - Statistical moments: mean, variance, skewness, kurtosis
    - Temporal: Hurst exponent, Approximate Entropy
    - Autoregressive parameters: AR(1), AR(2), AR(3) coefficients
    """
    clean_s = pd.Series(series).interpolate(method="linear").ffill().bfill()
    norm_s = z_score_normalize(clean_s) # extract features on standardized series for comparability
    
    mean_val = float(clean_s.mean())
    var_val = float(clean_s.var())
    skew_val = float(clean_s.skew())
    kurt_val = float(clean_s.kurtosis())
    
    hurst = calculate_hurst(clean_s)
    apen = calculate_approx_entropy(clean_s)
    
    # Fit AR(3)
    ar_params = [0.0, 0.0, 0.0]
    try:
        ar_model = AutoReg(norm_s, lags=3).fit()
        # AutoReg params: const, L1.y, L2.y, L3.y
        for idx in range(1, min(len(ar_model.params), 4)):
            ar_params[idx - 1] = float(ar_model.params.iloc[idx])
    except Exception:
        pass
        
    features = {
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
    return features
