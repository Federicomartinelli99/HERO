import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

def calculate_matrix_profile(series, m=12):
    """
    Computes the Matrix Profile and Matrix Profile Index for a 1D time series.
    Uses Z-normalized Euclidean distance and an exclusion zone of length m to prevent trivial self-matches.
    """
    a = np.array(series, dtype=float)
    n = len(a)
    n_sub = n - m + 1
    
    if n_sub <= 0:
        raise ValueError("Series is too short for the chosen subsequence length m.")
        
    # Extract and Z-normalize all subsequences
    subs = []
    for i in range(n_sub):
        sub = a[i : i + m]
        sub_mean = sub.mean()
        sub_std = sub.std()
        if sub_std == 0:
            sub_norm = sub - sub_mean
        else:
            sub_norm = (sub - sub_mean) / sub_std
        subs.append(sub_norm)
        
    mp = np.full(n_sub, np.inf)
    mp_idx = np.full(n_sub, -1, dtype=int)
    
    exclusion_zone = m # standard exclusion zone size
    
    for i in range(n_sub):
        for j in range(n_sub):
            # Skip indices within the exclusion zone (trivial matches)
            if abs(i - j) < exclusion_zone:
                continue
                
            dist = np.sqrt(np.mean((subs[i] - subs[j]) ** 2))
            if dist < mp[i]:
                mp[i] = dist
                mp_idx[i] = j
                
    # Find motifs: local minima in the matrix profile
    # The absolute top motif pair is the pair (i, mp_idx[i]) with the minimum distance
    top_motif_idx1 = np.argmin(mp)
    top_motif_idx2 = mp_idx[top_motif_idx1]
    
    # Find discords: absolute maximum value in the matrix profile
    top_discord_idx = np.argmax(mp)
    
    return mp, mp_idx, (top_motif_idx1, top_motif_idx2), top_discord_idx

def plot_matrix_profile(series, m, title, save_path):
    """
    Generates and saves a 2-panel plot:
    - Upper: Original time series with the top motif pair and top discord highlighted.
    - Lower: The Matrix Profile line chart.
    """
    a = np.array(series, dtype=float)
    
    try:
        mp, mp_idx, motif_pair, discord_idx = calculate_matrix_profile(series, m)
    except Exception as e:
        print(f"Matrix Profile calculation failed: {e}")
        # Create dummy plot on failure
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.text(0.5, 0.5, f"Matrix Profile failed: {e}", ha='center')
        plt.savefig(save_path, dpi=120)
        plt.close()
        return
        
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=False)
    
    # 1. Original Time Series Plot
    axes[0].plot(series.index, a, color="black", label="Time Series", linewidth=1.5)
    
    # Highlight top motif pair (in blue and orange)
    m1_idx = motif_pair[0]
    m2_idx = motif_pair[1]
    
    motif1_dates = series.index[m1_idx : m1_idx + m]
    motif1_vals = a[m1_idx : m1_idx + m]
    motif2_dates = series.index[m2_idx : m2_idx + m]
    motif2_vals = a[m2_idx : m2_idx + m]
    
    axes[0].plot(motif1_dates, motif1_vals, color="blue", linewidth=2.5, label=f"Motif Pair (Start: {series.index[m1_idx].strftime('%Y-%m')})")
    axes[0].plot(motif2_dates, motif2_vals, color="orange", linewidth=2.5, label=f"Motif Pair (Start: {series.index[m2_idx].strftime('%Y-%m')})")
    
    # Highlight top discord (in red)
    discord_dates = series.index[discord_idx : discord_idx + m]
    discord_vals = a[discord_idx : discord_idx + m]
    axes[0].plot(discord_dates, discord_vals, color="red", linewidth=2.5, label=f"Anomaly/Discord (Start: {series.index[discord_idx].strftime('%Y-%m')})")
    
    axes[0].set_title(f"Time Series Motifs & Anomalies (Matrix Profile): {title}", fontsize=14)
    axes[0].set_ylabel("IPC Value (%)", fontsize=10)
    axes[0].legend(loc="upper left", fontsize=8)
    axes[0].grid(True)
    
    # 2. Matrix Profile Plot
    # The matrix profile is shorter by m-1 points. Let's align its index with subsequence start dates
    mp_dates = series.index[:len(mp)]
    axes[1].plot(mp_dates, mp, color="purple", label="Matrix Profile", linewidth=1.5)
    axes[1].axhline(y=mp[discord_idx], color="red", linestyle=":", alpha=0.7, label="Max Distance (Discord)")
    axes[1].axhline(y=mp[motif_pair[0]], color="blue", linestyle=":", alpha=0.7, label="Min Distance (Motif)")
    
    axes[1].set_ylabel("Distance", fontsize=10)
    axes[1].set_xlabel("Date (Subsequence Start)", fontsize=10)
    axes[1].legend(loc="upper left", fontsize=8)
    axes[1].grid(True)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=120, bbox_inches="tight")
    plt.close()
