import os
import json
import numpy as np
import pandas as pd
from scipy.stats import pearsonr
from tqdm import tqdm
from sklearn.metrics import mutual_info_score
import config_graph as config

def get_symbols(x, m=3):
    n = len(x)
    if n < m: return np.zeros(0, dtype=int)
    sub_vectors = np.array([x[i : n - m + 1 + i] for i in range(m)])
    ranks = np.argsort(np.argsort(sub_vectors, axis=0), axis=0)
    return ranks[0] * 9 + ranks[1] * 3 + ranks[2]

def compute_ste_pair_opt(sym_x, sym_y, delta=1):
    L = min(len(sym_x), len(sym_y))
    if L <= delta: return 0.0
    y_future, y_past, x_past = sym_y[delta:L], sym_y[:-delta], sym_x[:-delta]
    n_samples = len(y_future)
    if n_samples == 0: return 0.0
    
    joint_3 = y_future * 729 + y_past * 27 + x_past
    counts_3 = np.bincount(joint_3, minlength=19683)
    p_3 = counts_3[counts_3 > 0] / n_samples
    H_all = -np.sum(p_3 * np.log2(p_3 + 1e-12))
    
    joint_yx = y_past * 27 + x_past
    counts_yx = np.bincount(joint_yx, minlength=729)
    p_yx = counts_yx[counts_yx > 0] / n_samples
    H_yx = -np.sum(p_yx * np.log2(p_yx + 1e-12))
    
    joint_yy = y_future * 27 + y_past
    counts_yy = np.bincount(joint_yy, minlength=729)
    p_yy = counts_yy[counts_yy > 0] / n_samples
    H_yy = -np.sum(p_yy * np.log2(p_yy + 1e-12))
    
    counts_y = np.bincount(y_past, minlength=27)
    p_y = counts_y[counts_y > 0] / n_samples
    H_y = -np.sum(p_y * np.log2(p_y + 1e-12))
    
    return max(0.0, float(H_yy - H_y - H_all + H_yx))

def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(np.radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    return 6371 * 2 * np.arcsin(np.sqrt(a)) # km

def compute_pairwise_metrics(s1, s2, lags=[0, 1, 2, 3], n_permutations=100):
    df = pd.concat([s1, s2], axis=1).dropna()
    if len(df) < 15:
        return None
    
    x = df.iloc[:, 0].values
    y = df.iloc[:, 1].values
    
    sym_x_base = get_symbols(x)
    sym_y_base = get_symbols(y)
    
    results = {'Pearson': {}, 'STE': {}, 'MI': {}}
    
    for lag in lags:
        if lag == 0:
            x_lag, y_lag = x, y
            sx_lag, sy_lag = sym_x_base, sym_y_base
        else:
            x_lag, y_lag = x[:-lag], y[lag:]
            sx_lag, sy_lag = sym_x_base[:-lag], sym_y_base[lag:]
            
        if len(x_lag) < 10:
            continue
            
        r, p_val = pearsonr(x_lag, y_lag)
        if not np.isnan(r):
            results['Pearson'][lag] = {'val': float(abs(r)), 'sig': bool(p_val < config.P_VALUE_THRESH)}
            
        if lag > 0:
            ste = compute_ste_pair_opt(sx_lag, sy_lag, delta=1)
            ste_nulls = []
            for _ in range(n_permutations):
                sy_shuff = np.random.permutation(sy_lag)
                ste_nulls.append(compute_ste_pair_opt(sx_lag, sy_shuff, delta=1))
            p_ste = np.mean(np.array(ste_nulls) >= ste)
            results['STE'][lag] = {'val': float(ste), 'sig': bool(p_ste < config.P_VALUE_THRESH)}
        
        mi = mutual_info_score(sx_lag, sy_lag)
        mi_nulls = []
        for _ in range(n_permutations):
            sy_shuff = np.random.permutation(sy_lag)
            mi_nulls.append(mutual_info_score(sx_lag, sy_shuff))
        p_mi = np.mean(np.array(mi_nulls) >= mi)
        results['MI'][lag] = {'val': float(mi), 'sig': bool(p_mi < config.P_VALUE_THRESH)}
        
    return results

def build_networks_json(df_piv, country_name, markets, mkt_coords):
    n = len(markets)
    nodes = []
    edges = []
    
    for m in markets:
        ts = df_piv[m].dropna()
        nodes.append({
            "id": m,
            "lat": mkt_coords[m][0],
            "lon": mkt_coords[m][1],
            "dates": ts.index.astype(str).tolist(),
            "prices": ts.values.tolist()
        })
    
    with tqdm(total=n*(n-1), desc=f"Computing edges for {country_name}") as pbar:
        for i, m1 in enumerate(markets):
            for j, m2 in enumerate(markets):
                if i == j: 
                    continue
                pbar.update(1)
                
                res = compute_pairwise_metrics(df_piv[m1], df_piv[m2], lags=config.LAGS, n_permutations=config.N_PERMUTATIONS)
                if res is None: continue
                
                dist = haversine(mkt_coords[m1][1], mkt_coords[m1][0], mkt_coords[m2][1], mkt_coords[m2][0])
                
                for lag in config.LAGS:
                    metrics_for_lag = {}
                    valid = False
                    for metric in ['Pearson', 'STE', 'MI']:
                        if lag in res[metric] and res[metric][lag]['val'] > 0:
                            metrics_for_lag[metric] = res[metric][lag]
                            valid = True
                            
                    if valid:
                        edges.append({
                            "source": m1,
                            "target": m2,
                            "distance": dist,
                            "lag": lag,
                            "metrics": metrics_for_lag
                        })

    out_folder = os.path.join(config.TS_GRAPH_DIR, "UI", "data")
    os.makedirs(out_folder, exist_ok=True)
    
    out_file = os.path.join(out_folder, f"network_data_{country_name}.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({"nodes": nodes, "edges": edges}, f)

def main():
    print("--- 01: Graph Creation (JSON Export) ---")
    df = pd.read_parquet(config.WFP_PATH)
    df["date"] = pd.to_datetime(df["date"])
    df = df.dropna(subset=['lat', 'lon'])
    
    year_counts = df['date'].dt.year.value_counts().sort_index()
    max_cap = year_counts.max()
    valid_years = year_counts[year_counts >= max_cap * 0.70]
    optimal_start_year = valid_years.index[0]
    
    df = df[df['date'].dt.year >= optimal_start_year]
    
    countries = config.TARGET_COUNTRIES if config.TARGET_COUNTRIES else df["ISO3"].unique().tolist()
    
    global_piv_list = []
    global_markets = []
    global_coords = {}
    processed_countries = []
    
    for country in countries:
        c_df = df[df["ISO3"] == country].copy()
        mkt_counts = c_df.groupby("mkt_name").size().sort_values(ascending=False)
        top_mkts = mkt_counts.head(35).index.tolist()
        c_df = c_df[c_df["mkt_name"].isin(top_mkts)]
        
        if c_df["mkt_name"].nunique() < 2: continue
            
        mkt_piv = c_df.pivot_table(index="date", columns="mkt_name", values="price", aggfunc="mean")
        mkt_piv = mkt_piv.resample("MS").mean()
        
        mkt_piv = np.log(mkt_piv).diff().replace([np.inf, -np.inf], np.nan).dropna(how='all')
        
        mkt_coords_df = c_df.groupby("mkt_name")[["lat", "lon"]].mean().reset_index()
        coords_dict = {row["mkt_name"]: (row["lat"], row["lon"]) for _, row in mkt_coords_df.iterrows()}
        
        print(f"\nBuilding temporal networks (JSON) for {country}")
        build_networks_json(mkt_piv, country, top_mkts, coords_dict)
        processed_countries.append(country)
        
        hubs = mkt_counts.head(config.GLOBAL_HUB_COUNT).index.tolist()
        for h in hubs:
            g_name = f"{country}_{h}"
            global_markets.append(g_name)
            global_coords[g_name] = coords_dict[h]
            if h in mkt_piv.columns:
                piv_col = mkt_piv[h].rename(g_name)
                global_piv_list.append(piv_col)
            
    if global_piv_list:
        print("\nBuilding GLOBAL temporal networks (JSON)...")
        global_piv = pd.concat(global_piv_list, axis=1).resample("MS").mean()
        build_networks_json(global_piv, "GLOBAL", global_markets, global_coords)
        processed_countries.append("GLOBAL")
        
    out_folder = os.path.join(config.TS_GRAPH_DIR, "UI", "data")
    os.makedirs(out_folder, exist_ok=True)
    with open(os.path.join(out_folder, "countries_list.json"), "w", encoding="utf-8") as f:
        json.dump(processed_countries, f)
    
    print("Graph creation (JSON) completed.")

if __name__ == "__main__":
    main()
