"""
Time-series visualization of the nowcast for one dataset: country-mean actual vs walk-forward
out-of-sample nowcast, plus per-admin-1 grids for a set of crisis countries.

Uses a lightweight viz-only backtest (XGBoost, nowcast feature set) with extra early origins so the
walk-forward curve covers the full history — independent of the metrics backtest in nowcast.py.

Run:  python nowcast_viz.py imputed        (or: unimputed)
"""

import sys
import config  # first — MKL guards
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

import features as F
from config import (TARGET, AREA_COL, COUNTRY_COL, LEVEL, HEADLINE_MODEL, TEST_WINDOW_MONTHS,
                    DATASETS, make_models, results_dir)

AREA_NAME_COL = "Level 1" if LEVEL == "adm1" else "Area"   # human-readable area label per level

# Extended, semi-annual origins from 2020-07 so the walk-forward curve spans the data range.
VIZ_ORIGINS = ["2020-07-01", "2021-01-01", "2021-07-01", "2022-01-01", "2022-07-01",
               "2023-01-01", "2023-07-01", "2024-01-01", "2024-07-01", "2025-01-01", "2025-07-01"]
VIZ_MIN_TRAIN = 50            # smaller than the metrics floor — viz wants coverage, not a headline metric
OOF_START = pd.Timestamp(VIZ_ORIGINS[0])

CRISIS_COUNTRIES = {"SOM": "Somalia", "YEM": "Yemen", "AFG": "Afghanistan", "ETH": "Ethiopia",
                    "SSD": "South Sudan", "NGA": "Nigeria", "MLI": "Mali", "HTI": "Haiti"}
DRIVER_STRIP = {
    "idp_population_over_adm1_population":                 "IDP rate",
    "rain_3m":                                            "Rainfall 3m (mm)",
    "acled_political_violence_events_per_100k_population": "Armed conflict (per 100k)",
    "wfp_price":                                          "WFP food price index",
}
ACTUAL_COLOR, NOWCAST_COLOR = "#1a1a2e", "#0077b6"
DRIVER_COLORS = ["#2d6a4f", "#e63946", "#6a4c93", "#f4a261"]
LEGEND = [
    plt.Line2D([], [], color=ACTUAL_COLOR, lw=2.0, marker="o", ms=3.5, label="Actual"),
    plt.Line2D([], [], color=NOWCAST_COLOR, lw=1.8, label="Nowcast XGB (walk-forward)"),
    plt.Line2D([], [], color="#aaaaaa", lw=1.0, ls="--", label=f"OOF start ({OOF_START:%Y-%m})"),
]


def walk_forward_predictions(features, target, panel, cols):
    """XGBoost-only expanding backtest over the extended viz origins; returns OOF predictions."""
    when = panel["From"].values
    oof = np.full(len(target), np.nan)
    for origin in VIZ_ORIGINS:
        start = np.datetime64(pd.Timestamp(origin))
        end = np.datetime64(pd.Timestamp(origin) + pd.DateOffset(months=TEST_WINDOW_MONTHS))
        train = when < start
        test = (when >= start) & (when < end)
        if test.sum() == 0 or train.sum() < VIZ_MIN_TRAIN:
            continue
        model = make_models()[HEADLINE_MODEL]
        model.fit(features.loc[train, cols], target.loc[train])
        oof[test] = model.predict(features.loc[test, cols])
    return oof


def country_series(panel, iso3):
    """Country-mean actual + nowcast (+ drivers) over current windows. Returns (df, n_areas)."""
    sub = panel[(panel[COUNTRY_COL] == iso3) & (panel["is_projection"] == 0)]
    if sub.empty:
        return None, 0
    agg = {"actual": (TARGET, "mean"), "nowcast": ("nowcast", "mean")}
    for col in DRIVER_STRIP:
        if col in sub.columns:
            agg[col] = (col, "mean")
    series = sub.groupby("From").agg(**agg).reset_index().sort_values("From")
    return series, sub[AREA_COL].nunique()


def format_axis(ax, ylim=None):
    if ylim:
        ax.set_ylim(*ylim)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.tick_params(labelsize=8)
    ax.grid(axis="y", lw=0.4, alpha=0.4)
    ax.spines[["top", "right"]].set_visible(False)


def draw_series(ax, series, lw_actual=2.0, ms=3.5, lw_nowcast=1.8):
    ax.axvline(OOF_START, color="#aaaaaa", lw=0.9, ls="--", zorder=1)
    has_nowcast = series["nowcast"].notna()
    if has_nowcast.any():
        ax.plot(series.loc[has_nowcast, "From"], series.loc[has_nowcast, "nowcast"],
                color=NOWCAST_COLOR, lw=lw_nowcast, zorder=3)
    ax.plot(series["From"], series["actual"], color=ACTUAL_COLOR, lw=lw_actual,
            marker="o", ms=ms, zorder=4)


def normalize_01(s):
    lo, hi = s.min(), s.max()
    return s * 0.0 if hi - lo < 1e-9 else (s - lo) / (hi - lo)


def plot_country_grid(panel, found, outdir):
    rows = (len(found) + 1) // 2
    fig, axes = plt.subplots(rows, 2, figsize=(13, rows * 3.2))
    axes = np.array(axes).reshape(-1)
    for i, iso3 in enumerate(found):
        series, n_areas = country_series(panel, iso3)
        ax = axes[i]
        ax.set_xlim(series["From"].min(), series["From"].max() + pd.DateOffset(months=3))
        draw_series(ax, series)
        format_axis(ax, ylim=(0, max(80, float(series["actual"].max()) * 1.15)))
        ax.set_title(f"{CRISIS_COUNTRIES[iso3]}  ({n_areas} areas)", fontsize=9, fontweight="bold")
    for j in range(len(found), len(axes)):
        axes[j].set_visible(False)
    fig.legend(handles=LEGEND, loc="lower right", ncol=1, fontsize=8, frameon=True,
               framealpha=0.9, bbox_to_anchor=(0.98, 0.01))
    fig.suptitle("IPC Phase 3+ nowcast vs actual — country mean (admin-1)", fontsize=11, y=1.01)
    fig.tight_layout(rect=[0, 0.02, 1, 1])
    fig.savefig(outdir / "ts_grid.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("Saved: ts_grid.png")


def plot_area_grid(panel, area_names, iso3, outdir):
    name = CRISIS_COUNTRIES[iso3]
    sub = panel[(panel[COUNTRY_COL] == iso3) & (panel["is_projection"] == 0)]
    areas = sorted(sub[AREA_COL].unique())
    ncols = min(5, len(areas))
    nrows = (len(areas) + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(ncols * 2.8, nrows * 2.4))
    axes = np.array(axes).reshape(-1)
    xmin, xmax = sub["From"].min(), sub["From"].max() + pd.DateOffset(months=3)
    for i, area in enumerate(areas):
        ax = axes[i]
        one = sub[sub[AREA_COL] == area].sort_values("From")
        series = one[["From", TARGET, "nowcast"]].rename(columns={TARGET: "actual"})
        ax.set_xlim(xmin, xmax)
        draw_series(ax, series, lw_actual=1.4, ms=2.5, lw_nowcast=1.4)
        ymax = max(80, float(series["actual"].max()) * 1.15) if series["actual"].notna().any() else 80
        format_axis(ax, ylim=(0, ymax))
        ax.set_title(area_names.get(area, area), fontsize=7)
        ax.tick_params(labelsize=6)
        ax.xaxis.set_major_locator(mdates.YearLocator(2))
    for j in range(len(areas), len(axes)):
        axes[j].set_visible(False)
    fig.suptitle(f"{name} — admin-1 nowcast vs actual", fontsize=10, fontweight="bold")
    fig.legend(handles=LEGEND, loc="lower right", ncol=1, fontsize=7, frameon=True,
               framealpha=0.9, bbox_to_anchor=(0.99, 0.01))
    fig.tight_layout(rect=[0, 0.03, 1, 0.97])
    fig.savefig(outdir / f"adm1_{name.lower().replace(' ', '_')}.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: adm1_{name.lower().replace(' ', '_')}.png")


def main(dataset: str):
    outdir = results_dir("nowcast", dataset)
    print(f"[nowcast_viz / {dataset}] loading {DATASETS[dataset].name}")
    df = F.load_dataset(dataset)
    area_names = (df[[AREA_COL, AREA_NAME_COL]].drop_duplicates(AREA_COL)
                  .set_index(AREA_COL)[AREA_NAME_COL].fillna("").to_dict())

    panel = F.build_panel(df, include_projections=True)
    features, target = F.make_features(panel)
    cols = F.feature_sets(features)["nowcast"]
    panel = panel.reset_index(drop=True)
    panel["nowcast"] = walk_forward_predictions(features, target, panel, cols)
    for col in DRIVER_STRIP:
        if col in features.columns:
            panel[col] = features[col].values

    found = [iso3 for iso3 in CRISIS_COUNTRIES if (panel[COUNTRY_COL] == iso3).any()]
    print(f"  plotting: {[CRISIS_COUNTRIES[c] for c in found]}")
    plot_country_grid(panel, found, outdir)
    for iso3 in found:
        plot_area_grid(panel, area_names, iso3, outdir)
    print(f"Done -> {outdir}")


if __name__ == "__main__":
    dataset = sys.argv[1] if len(sys.argv) > 1 else "imputed"
    assert dataset in DATASETS, f"dataset must be one of {list(DATASETS)}"
    main(dataset)
