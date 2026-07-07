import pandas as pd
import numpy as np
import config
from data_loader import load_country_pcodes, load_and_align_region

def calculate_reliability(series, weights=None):
    """
    Computes the Reliability Index (0 to 100) for a given pandas Series.
    """
    if weights is None:
        weights = config.RELIABILITY_WEIGHTS
        
    n = len(series)
    if n == 0:
        return 0.0
        
    # 1. Total missingness ratio
    n_missing = series.isna().sum()
    r_missing = n_missing / n
    
    # 2. Maximum consecutive gap length
    is_na = series.isna()
    # Cumsum of non-NaN values creates unique group IDs for consecutive NaN sequences
    gap_groups = is_na.groupby((~is_na).cumsum())
    g_max = 0
    for _, group in gap_groups:
        if group.iloc[0]: # If this group represents NaNs
            g_max = max(g_max, len(group))
            
    r_gap = g_max / n
    
    # 3. Recency of missingness (last 12 months)
    recent_period = min(12, n)
    recent_series = series.iloc[-recent_period:]
    r_recent = recent_series.isna().sum() / recent_period if recent_period > 0 else 0.0
    
    # 4. Weighted score
    w_m = weights.get("w_missing", 0.4)
    w_g = weights.get("w_gap", 0.4)
    w_r = weights.get("w_recent", 0.2)
    
    penalty = (w_m * r_missing) + (w_g * r_gap) + (w_r * r_recent)
    score = 100.0 * (1.0 - penalty)
    
    return float(np.clip(score, 0.0, 100.0))

def evaluate_region_reliability(df):
    """
    Evaluates reliability for all target predictors in a region's aligned DataFrame.
    """
    scores = {}
    for col in config.PREDICTORS:
        if col in df.columns:
            scores[col] = calculate_reliability(df[col])
        else:
            scores[col] = 0.0 # Missing column is treated as 0% reliable
    return scores

def generate_country_reliability_report(country_code):
    """
    Loops through all regions of a country, computes their reliability indices,
    and returns a sorted DataFrame summarizing the data quality.
    """
    regions = load_country_pcodes(country_code)
    report_rows = []
    
    for pcode, name in regions:
        try:
            df = load_and_align_region(country_code, pcode)
            scores = evaluate_region_reliability(df)
            avg_score = np.mean(list(scores.values()))
            
            row = {
                "adm1_pcode": pcode,
                "region_name": name,
                "avg_reliability": round(avg_score, 2)
            }
            # Add scores for individual predictors
            for col, val in scores.items():
                row[col] = round(val, 2)
                
            report_rows.append(row)
        except Exception as e:
            print(f"Error checking reliability for {name} ({pcode}): {e}")
            
    df_report = pd.DataFrame(report_rows)
    if not df_report.empty:
        df_report = df_report.sort_values(by="avg_reliability", ascending=False).reset_index(drop=True)
    return df_report
