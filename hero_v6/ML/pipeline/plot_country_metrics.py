"""
Per-country performance dot charts for one dataset — reads the `metrics_per_country.csv` written by
static_inference.py and nowcast.py and draws a horizontal R²/MAE chart for each round.

Run:  python plot_country_metrics.py imputed        (or: unimputed)
"""

import sys
import config  # first — MKL guards
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.lines as mlines

from config import DATASETS, results_dir

MODEL_STYLE = {
    "xgboost":               {"color": "#0077b6", "marker": "o", "label": "XGBoost"},
    "random_forest":         {"color": "#2d9e6b", "marker": "s", "label": "RandomForest"},
    "lightgbm":              {"color": "#e07b39", "marker": "^", "label": "LightGBM"},
    "persistence":           {"color": "#888888", "marker": "D", "label": "Persistence"},
    "baseline_country_mean": {"color": "#888888", "marker": "D", "label": "Country mean"},
}
R2_CLIP = (-1.0, 1.0)   # extreme negatives compress the axis, so clip for display


def dot_chart(ax, pivot, models, sort_col, clip, xlabel):
    order = pivot[sort_col].sort_values(ascending=True).index   # best at the top
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels(order, fontsize=7.5)
    ax.yaxis.set_tick_params(length=0)
    ax.grid(axis="x", lw=0.4, alpha=0.5, zorder=0)
    ax.axvline(0, color="#333333", lw=0.8, zorder=1)
    for i, country in enumerate(order):
        ax.axhline(i, color="#eeeeee", lw=0.6, zorder=0)
        for model in models:
            if model not in pivot.columns or pd.isna(pivot.loc[country, model]):
                continue
            style = MODEL_STYLE[model]
            ax.plot(np.clip(pivot.loc[country, model], *clip), i, color=style["color"],
                    marker=style["marker"], markersize=5, markeredgewidth=0.4,
                    markeredgecolor="white", linestyle="none")
    ax.set_xlim(clip[0] - 0.08, clip[1] + 0.05)
    ax.set_ylim(-0.8, len(order) - 0.2)
    ax.set_xlabel(xlabel, fontsize=9)
    ax.spines[["top", "right", "left"]].set_visible(False)


def draw(metrics_csv, models, title, path):
    df = pd.read_csv(metrics_csv)
    r2 = df.pivot_table(index="Country", columns="model", values="R2")
    mae = df.pivot_table(index="Country", columns="model", values="MAE")
    countries = r2.index[r2["xgboost"].notna()]
    r2, mae = r2.loc[countries], mae.loc[countries]

    fig, (ax_r2, ax_mae) = plt.subplots(1, 2, figsize=(13, max(6, len(countries) * 0.3)), sharey=True)
    dot_chart(ax_r2, r2, models, "xgboost", R2_CLIP, "R²  (clipped at −1)")
    mae_clip = (0, mae["xgboost"].quantile(0.95) * 1.1)
    dot_chart(ax_mae, mae, models, "xgboost", mae_clip, "MAE (pp)")
    ax_mae.set_xlim(*mae_clip)
    ax_r2.set_title("R²", fontsize=9); ax_mae.set_title("MAE (pp)", fontsize=9)
    handles = [mlines.Line2D([], [], color=MODEL_STYLE[m]["color"], marker=MODEL_STYLE[m]["marker"],
                             linestyle="none", markersize=5, label=MODEL_STYLE[m]["label"])
               for m in models]
    fig.legend(handles=handles, loc="lower center", ncol=len(models), fontsize=8,
               frameon=True, framealpha=0.9, bbox_to_anchor=(0.5, -0.01))
    fig.suptitle(title, fontsize=10, fontweight="bold")
    fig.tight_layout(rect=[0, 0.04, 1, 0.97])
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")


def main(dataset: str):
    static_dir = results_dir("static_inference", dataset)
    nowcast_dir = results_dir("nowcast", dataset)

    static_csv = static_dir / "metrics_per_country.csv"
    if static_csv.exists():
        draw(static_csv, ["xgboost", "random_forest", "lightgbm", "baseline_country_mean"],
             f"Static inference — per-country performance ({dataset})",
             static_dir / "per_country_performance.png")

    nowcast_csv = nowcast_dir / "metrics_per_country.csv"
    if nowcast_csv.exists():
        df = pd.read_csv(nowcast_csv)
        keep = df[df["feature_set"].isin(["nowcast", "-"])]
        keep.to_csv(nowcast_dir / "_per_country_nowcast_only.csv", index=False)
        draw(nowcast_dir / "_per_country_nowcast_only.csv",
             ["xgboost", "random_forest", "lightgbm", "persistence"],
             f"Nowcast — per-country performance ({dataset})",
             nowcast_dir / "per_country_performance.png")
        (nowcast_dir / "_per_country_nowcast_only.csv").unlink()


if __name__ == "__main__":
    dataset = sys.argv[1] if len(sys.argv) > 1 else "imputed"
    assert dataset in DATASETS, f"dataset must be one of {list(DATASETS)}"
    main(dataset)
