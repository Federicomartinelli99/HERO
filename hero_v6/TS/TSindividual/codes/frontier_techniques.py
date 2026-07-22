import os
import json
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import seaborn as sns
import networkx as nx
import libpysal
import esda
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler
from . import config

def plot_distance_decay(valid_markets_coords, mkt_coords, corr_matrix, ste_dict, output_path):
    """
    Plots the relationship between link strength (Pearson r and STE) and geographical distance (km).
    """
    import numpy as np
    import pandas as pd
    import matplotlib.pyplot as plt
    import seaborn as sns
    from math import radians, sin, cos, sqrt, atan2
    
    # Haversine distance helper
    def haversine(lat1, lon1, lat2, lon2):
        R = 6371.0 # Earth radius in km
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        return R * c

    # Build market coordinates dict
    coords_dict = {row["mkt_name"]: (row["lat"], row["lon"]) for _, row in mkt_coords.iterrows()}
    
    records = []
    for i in range(len(valid_markets_coords)):
        for j in range(i + 1, len(valid_markets_coords)):
            m1 = valid_markets_coords[i]
            m2 = valid_markets_coords[j]
            if m1 not in coords_dict or m2 not in coords_dict:
                continue
            lat1, lon1 = coords_dict[m1]
            lat2, lon2 = coords_dict[m2]
            dist = haversine(lat1, lon1, lat2, lon2)
            
            r_val = corr_matrix.loc[m1, m2]
            ste_val = ste_dict.get(m1, {}).get(m2, 0.0)
            
            records.append({
                "Market1": m1,
                "Market2": m2,
                "Distance_km": dist,
                "Pearson_r": r_val,
                "STE": ste_val
            })
            
    df_decay = pd.DataFrame(records)
    df_decay.to_csv(output_path.replace(".png", ".csv"), index=False)
    
    # Plotting
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    
    # Pearson r vs Distance
    sns.regplot(data=df_decay, x="Distance_km", y="Pearson_r", ax=axes[0],
                scatter_kws={"alpha": 0.5, "color": "#1f77b4"},
                line_kws={"color": "red", "linewidth": 2})
    axes[0].set_title("Pearson Correlation vs. Geographical Distance", fontsize=12, fontweight="bold")
    axes[0].set_xlabel("Distance (km)", fontsize=11)
    axes[0].set_ylabel("Pearson correlation (r)", fontsize=11)
    axes[0].grid(True, linestyle=":", alpha=0.6)
    
    # STE vs Distance
    sns.regplot(data=df_decay, x="Distance_km", y="STE", ax=axes[1],
                scatter_kws={"alpha": 0.5, "color": "#2ca02c"},
                line_kws={"color": "red", "linewidth": 2})
    axes[1].set_title("Symbolic Transfer Entropy (STE) vs. Geographical Distance", fontsize=12, fontweight="bold")
    axes[1].set_xlabel("Distance (km)", fontsize=11)
    axes[1].set_ylabel("STE Value", fontsize=11)
    axes[1].grid(True, linestyle=":", alpha=0.6)
    
    plt.suptitle("Distance Decay of Market Integration (Afghanistan WFP)", fontsize=14, fontweight="bold", y=0.98)
    plt.tight_layout()
    plt.savefig(output_path, dpi=180)
    plt.close()
    print(f"Distance decay plot saved at: {output_path}")

def plot_distance_decay(valid_markets_coords, mkt_coords, corr_matrix, ste_dict, output_path, country_name="Afghanistan"):
    """
    Plots the relationship between link strength (Pearson r and STE) and geographical distance (km).
    """
    import numpy as np
    import pandas as pd
    import matplotlib.pyplot as plt
    import seaborn as sns
    from math import radians, sin, cos, sqrt, atan2
    
    # Haversine distance helper
    def haversine(lat1, lon1, lat2, lon2):
        R = 6371.0 # Earth radius in km
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        return R * c

    # Build market coordinates dict
    coords_dict = {row["mkt_name"]: (row["lat"], row["lon"]) for _, row in mkt_coords.iterrows()}
    
    records = []
    for i in range(len(valid_markets_coords)):
        for j in range(i + 1, len(valid_markets_coords)):
            m1 = valid_markets_coords[i]
            m2 = valid_markets_coords[j]
            if m1 not in coords_dict or m2 not in coords_dict:
                continue
            lat1, lon1 = coords_dict[m1]
            lat2, lon2 = coords_dict[m2]
            dist = haversine(lat1, lon1, lat2, lon2)
            
            r_val = corr_matrix.loc[m1, m2]
            ste_val = ste_dict.get(m1, {}).get(m2, 0.0)
            
            records.append({
                "Market1": m1,
                "Market2": m2,
                "Distance_km": dist,
                "Pearson_r": r_val,
                "STE": ste_val
            })
            
    df_decay = pd.DataFrame(records)
    df_decay.to_csv(output_path.replace(".png", ".csv"), index=False)
    
    if df_decay.empty:
        return df_decay
        
    # Plotting
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    
    # Pearson r vs Distance
    if len(df_decay) > 3:
        try:
            sns.regplot(data=df_decay, x="Distance_km", y="Pearson_r", ax=axes[0],
                        scatter_kws={"alpha": 0.5, "color": "#1f77b4"},
                        line_kws={"color": "red", "linewidth": 2})
        except Exception:
            sns.scatterplot(data=df_decay, x="Distance_km", y="Pearson_r", ax=axes[0], color="#1f77b4")
    else:
        sns.scatterplot(data=df_decay, x="Distance_km", y="Pearson_r", ax=axes[0], color="#1f77b4")
        
    axes[0].set_title(f"Pearson Correlation vs. Distance - {country_name}", fontsize=12, fontweight="bold")
    axes[0].set_xlabel("Distance (km)", fontsize=11)
    axes[0].set_ylabel("Pearson correlation (r)", fontsize=11)
    axes[0].grid(True, linestyle=":", alpha=0.6)
    
    # STE vs Distance
    if len(df_decay) > 3:
        try:
            sns.regplot(data=df_decay, x="Distance_km", y="STE", ax=axes[1],
                        scatter_kws={"alpha": 0.5, "color": "#2ca02c"},
                        line_kws={"color": "red", "linewidth": 2})
        except Exception:
            sns.scatterplot(data=df_decay, x="Distance_km", y="STE", ax=axes[1], color="#2ca02c")
    else:
        sns.scatterplot(data=df_decay, x="Distance_km", y="STE", ax=axes[1], color="#2ca02c")
        
    axes[1].set_title(f"STE vs. Distance - {country_name}", fontsize=12, fontweight="bold")
    axes[1].set_xlabel("Distance (km)", fontsize=11)
    axes[1].set_ylabel("STE Value", fontsize=11)
    axes[1].grid(True, linestyle=":", alpha=0.6)
    
    plt.suptitle(f"Distance Decay of Market Integration ({country_name})", fontsize=14, fontweight="bold", y=0.98)
    plt.tight_layout()
    plt.savefig(output_path, dpi=180)
    plt.close()
    return df_decay

def plot_distance_decay(valid_markets_coords, mkt_coords, corr_matrix, ste_dict, output_path, country_name="Afghanistan"):
    """
    Plots the relationship between link strength (Pearson r and STE) and geographical distance (km).
    """
    import numpy as np
    import pandas as pd
    import matplotlib.pyplot as plt
    import seaborn as sns
    from math import radians, sin, cos, sqrt, atan2
    
    # Haversine distance helper
    def haversine(lat1, lon1, lat2, lon2):
        R = 6371.0 # Earth radius in km
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        return R * c

    # Build market coordinates dict
    coords_dict = {row["mkt_name"]: (row["lat"], row["lon"]) for _, row in mkt_coords.iterrows()}
    
    records = []
    for i in range(len(valid_markets_coords)):
        for j in range(i + 1, len(valid_markets_coords)):
            m1 = valid_markets_coords[i]
            m2 = valid_markets_coords[j]
            if m1 not in coords_dict or m2 not in coords_dict:
                continue
            lat1, lon1 = coords_dict[m1]
            lat2, lon2 = coords_dict[m2]
            dist = haversine(lat1, lon1, lat2, lon2)
            
            r_val = corr_matrix.loc[m1, m2]
            ste_val = ste_dict.get(m1, {}).get(m2, 0.0)
            
            records.append({
                "Market1": m1,
                "Market2": m2,
                "Distance_km": dist,
                "Pearson_r": r_val,
                "STE": ste_val
            })
            
    df_decay = pd.DataFrame(records)
    df_decay.to_csv(output_path.replace(".png", ".csv"), index=False)
    
    if df_decay.empty:
        return df_decay
        
    # Plotting
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    
    # Pearson r vs Distance
    if len(df_decay) > 3:
        try:
            sns.regplot(data=df_decay, x="Distance_km", y="Pearson_r", ax=axes[0],
                        scatter_kws={"alpha": 0.5, "color": "#1f77b4"},
                        line_kws={"color": "red", "linewidth": 2})
        except Exception:
            sns.scatterplot(data=df_decay, x="Distance_km", y="Pearson_r", ax=axes[0], color="#1f77b4")
    else:
        sns.scatterplot(data=df_decay, x="Distance_km", y="Pearson_r", ax=axes[0], color="#1f77b4")
        
    axes[0].set_title(f"Pearson Correlation vs. Distance - {country_name}", fontsize=12, fontweight="bold")
    axes[0].set_xlabel("Distance (km)", fontsize=11)
    axes[0].set_ylabel("Pearson correlation (r)", fontsize=11)
    axes[0].grid(True, linestyle=":", alpha=0.6)
    
    # STE vs Distance
    if len(df_decay) > 3:
        try:
            sns.regplot(data=df_decay, x="Distance_km", y="STE", ax=axes[1],
                        scatter_kws={"alpha": 0.5, "color": "#2ca02c"},
                        line_kws={"color": "red", "linewidth": 2})
        except Exception:
            sns.scatterplot(data=df_decay, x="Distance_km", y="STE", ax=axes[1], color="#2ca02c")
    else:
        sns.scatterplot(data=df_decay, x="Distance_km", y="STE", ax=axes[1], color="#2ca02c")
        
    axes[1].set_title(f"STE vs. Distance - {country_name}", fontsize=12, fontweight="bold")
    axes[1].set_xlabel("Distance (km)", fontsize=11)
    axes[1].set_ylabel("STE Value", fontsize=11)
    axes[1].grid(True, linestyle=":", alpha=0.6)
    
    plt.suptitle(f"Distance Decay of Market Integration ({country_name})", fontsize=14, fontweight="bold", y=0.98)
    plt.tight_layout()
    plt.savefig(output_path, dpi=180)
    plt.close()
    return df_decay

import os
import json
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import seaborn as sns
import networkx as nx
from tqdm import tqdm
from scipy.optimize import curve_fit

import os
import json
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import seaborn as sns
import networkx as nx
from tqdm import tqdm
from scipy.optimize import curve_fit

