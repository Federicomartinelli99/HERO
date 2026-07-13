"""
nowcast_viz.py — time-series visualization of nowcast predictions vs actuals.

Produces:
  1. ts_grid.png              — 4×2 country overview
  2. ts_<country>.png         — country mean + driver strip
  3. adm1_<country>.png       — one subplot per admin-1 area

Uses a lightweight viz-only backtest (XGBoost nowcast only) with origins from
2020-07-01 onward, giving full walk-forward OOF coverage across the data range.
The metrics backtest in nowcast.py uses its own ORIGINS and is unchanged.

Run: C:/Users/jonas/miniconda3/envs/ewm/python.exe hero_v6/ML/codes/nowcast_viz.py
"""

import os
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("MKL_THREADING_LAYER", "SEQUENTIAL")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

sys.path.insert(0, str(Path(__file__).resolve().parent))
from static_inference import make_models
from nowcast import build_panel, make_features, feature_sets_for, TARGET, AREA

# --------------------------------------------------------------------------- config
ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "merged" / "merged_adm1_wide.parquet"
OUTDIR = ROOT / "ML" / "results" / "nowcast"
OUTDIR.mkdir(parents=True, exist_ok=True)

# Extended origins for viz — semi-annual from 2020-07, covers full data range.
# Independent of ORIGINS in nowcast.py (which drives the metrics backtest).
VIZ_ORIGINS = [
    "2020-07-01", "2021-01-01", "2021-07-01", "2022-01-01",
    "2022-07-01", "2023-01-01", "2023-07-01", "2024-01-01",
    "2024-07-01", "2025-01-01", "2025-07-01",
]
VIZ_TEST_M = 6
OOF_START  = pd.Timestamp(VIZ_ORIGINS[0])

COUNTRIES = ["SOM", "YEM", "AFG", "ETH", "SSD", "NGA", "MLI", "HTI"]
COUNTRY_NAMES = {
    "SOM": "Somalia", "YEM": "Yemen",   "AFG": "Afghanistan", "ETH": "Ethiopia",
    "SSD": "South Sudan", "NGA": "Nigeria", "MLI": "Mali",    "HTI": "Haiti",
}

DRIVER_DISPLAY = {
    "idp_rate":                                "IDP rate",
    "rain_1m_sum":                             "Rainfall 1m (mm)",
    "acled_political_violence_events_per100k": "Armed conflict (per 100k)",
    "wfp_price":                               "WFP food price index",
}

COLORS = {"actual": "#1a1a2e", "nowcast": "#0077b6"}
DRIVER_COLORS = ["#2d6a4f", "#e63946", "#6a4c93", "#f4a261"]

LEGEND_HANDLES = [
    plt.Line2D([], [], color=COLORS["actual"],  lw=2.0, marker="o", ms=3.5, label="Actual"),
    plt.Line2D([], [], color=COLORS["nowcast"], lw=1.8,              label="Nowcast XGB (walk-forward)"),
    plt.Line2D([], [], color="#aaaaaa",         lw=1.0, ls="--",     label=f"OOF start ({OOF_START.strftime('%Y-%m')})"),
]


# --------------------------------------------------------------------------- backtest
def run_viz_backtest(X, y, panel, cols):
    """Lightweight expanding-window backtest: XGBoost nowcast only."""
    From = panel["From"].values
    n    = len(y)
    oof  = np.full(n, np.nan)
    for org in VIZ_ORIGINS:
        c  = np.datetime64(pd.Timestamp(org))
        c2 = np.datetime64(pd.Timestamp(org) + pd.DateOffset(months=VIZ_TEST_M))
        trm = From < c
        tem = (From >= c) & (From < c2)
        if tem.sum() == 0 or trm.sum() < 50:
            continue
        mdl = make_models()["xgboost"]
        mdl.fit(X.loc[trm, cols], y.loc[trm])
        oof[tem] = mdl.predict(X.loc[tem, cols])
        print(f"    origin {org}: train={trm.sum()}, test={tem.sum()}, OOF so far={np.isfinite(oof).sum()}")
    return oof


# --------------------------------------------------------------------------- aggregation
def area_name_map(df):
    """adm1_pcode → Level 1 name (falls back to pcode if NaN)."""
    mp = (df[["adm1_pcode", "Level 1"]]
            .drop_duplicates("adm1_pcode")
            .set_index("adm1_pcode")["Level 1"]
            .fillna(""))
    return mp.to_dict()


def country_ts(panel, iso3):
    """Country-mean time series (current windows only). Returns (df, n_areas)."""
    mask = (panel["Country"] == iso3) & (panel["is_projection"] == 0)
    if mask.sum() == 0:
        return None, 0
    sub = panel[mask]
    n_areas = sub[AREA].nunique()
    agg = {"actual": (TARGET, "mean"), "predicted_oof": ("predicted_oof", "mean")}
    for col in DRIVER_DISPLAY:
        if col in sub.columns:
            agg[col] = (col, "mean")
    ts = sub.groupby("From").agg(**agg).reset_index().sort_values("From")
    return ts, n_areas


def area_ts(panel, iso3, pcode):
    """Single-area time series (current windows only)."""
    mask = (panel["Country"] == iso3) & (panel[AREA] == pcode) & (panel["is_projection"] == 0)
    sub = panel[mask].sort_values("From")
    return sub[["From", TARGET, "predicted_oof"]].rename(columns={TARGET: "actual"})


# --------------------------------------------------------------------------- plot helpers
def _fmt_ax(ax, xmin=None, xmax=None, ylim=None):
    if xmin is not None:
        ax.set_xlim(xmin, xmax)
    if ylim is not None:
        ax.set_ylim(*ylim)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.tick_params(labelsize=8)
    ax.grid(axis="y", lw=0.4, alpha=0.4)
    ax.spines[["top", "right"]].set_visible(False)


def _draw(ax, ts, oof_start, lw_actual=2.0, ms=3.5, lw_nowcast=1.8):
    ax.axvline(oof_start, color="#aaaaaa", lw=0.9, ls="--", zorder=1)
    oof_m = ts["predicted_oof"].notna()
    if oof_m.any():
        ax.plot(ts.loc[oof_m, "From"], ts.loc[oof_m, "predicted_oof"],
                color=COLORS["nowcast"], lw=lw_nowcast, zorder=3)
    ax.plot(ts["From"], ts["actual"],
            color=COLORS["actual"], lw=lw_actual, marker="o", ms=ms, zorder=4)


# --------------------------------------------------------------------------- main
def main():
    print(f"Loading {DATA}")
    df = pd.read_parquet(DATA)
    names = area_name_map(df)

    panel = build_panel(df, include_projections=True)
    X, y  = make_features(panel, include_is_proj=True)
    panel = panel.reset_index(drop=True)
    cols  = feature_sets_for(X)["nowcast"]
    print(f"  panel_all: {len(panel)} windows, {panel[AREA].nunique()} areas")

    # ---- extended walk-forward backtest (XGB only)
    print(f"  Running viz backtest ({len(VIZ_ORIGINS)} origins, 2020-07 to 2026)...")
    oof_preds = run_viz_backtest(X, y, panel, cols)
    print(f"  Total OOF windows: {int(np.isfinite(oof_preds).sum())}")

    panel["predicted_oof"] = oof_preds
    for col in DRIVER_DISPLAY:
        if col in X.columns:
            panel[col] = X[col].values

    # ---- filter to countries present in data
    found = [c for c in COUNTRIES
             if (panel["Country"] == c).any()]
    print(f"  Plotting: {[COUNTRY_NAMES.get(c, c) for c in found]}")

    # ================================================================= COUNTRY GRID
    ncols_g, nrows_g = 2, (len(found) + 1) // 2
    fig, axes = plt.subplots(nrows_g, ncols_g, figsize=(13, nrows_g * 3.2))
    axes = np.array(axes).reshape(-1)

    for i, iso3 in enumerate(found):
        ts, n_areas = country_ts(panel, iso3)
        dname = COUNTRY_NAMES.get(iso3, iso3)
        ax = axes[i]
        xmin = ts["From"].min()
        xmax = ts["From"].max() + pd.DateOffset(months=3)
        ax.set_xlim(xmin, xmax)
        _draw(ax, ts, OOF_START)
        ymax = max(80, float(ts["actual"].max()) * 1.15)
        _fmt_ax(ax, ylim=(0, ymax))
        ax.set_title(f"{dname}  ({n_areas} areas)", fontsize=9, fontweight="bold", pad=4)

    for j in range(len(found), len(axes)):
        axes[j].set_visible(False)

    fig.legend(handles=LEGEND_HANDLES, loc="lower right", ncol=1, fontsize=8,
               frameon=True, framealpha=0.9, bbox_to_anchor=(0.98, 0.01))
    fig.suptitle("IPC Phase 3+ nowcast vs actual — country mean (admin-1)", fontsize=11, y=1.01)
    fig.tight_layout(rect=[0, 0.02, 1, 1])
    fig.savefig(OUTDIR / "ts_grid.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\nSaved: ts_grid.png")

    # ============================================================= PER-COUNTRY DETAIL
    avail_drivers = [c for c in DRIVER_DISPLAY if c in panel.columns]

    for iso3 in found:
        ts, n_areas = country_ts(panel, iso3)
        dname = COUNTRY_NAMES.get(iso3, iso3)
        n_drv = sum(1 for c in avail_drivers if ts[c].notna().any())
        hr    = [3, 1.5] if n_drv else [1]
        fig, axes_d = plt.subplots(len(hr), 1, figsize=(10, 7 if n_drv else 4),
                                    gridspec_kw={"height_ratios": hr}, sharex=True)
        if len(hr) == 1:
            axes_d = [axes_d]
        ax_ipc = axes_d[0]
        ax_drv = axes_d[1] if len(axes_d) > 1 else None

        xmin = ts["From"].min()
        xmax = ts["From"].max() + pd.DateOffset(months=3)
        for ax in axes_d:
            ax.set_xlim(xmin, xmax)

        _draw(ax_ipc, ts, OOF_START)
        _fmt_ax(ax_ipc, ylim=(0, max(80, float(ts["actual"].max()) * 1.15)))
        ax_ipc.set_ylabel("Phase 3+ population (%)", fontsize=9)
        ax_ipc.set_title(f"{dname} — IPC Phase 3+ nowcast  ({n_areas} admin-1 areas)",
                         fontsize=10, fontweight="bold", pad=6)
        ax_ipc.legend(handles=LEGEND_HANDLES, fontsize=8, loc="upper left",
                      frameon=True, framealpha=0.9)

        if ax_drv is not None:
            ax_drv.axvline(OOF_START, color="#aaaaaa", lw=0.9, ls="--", zorder=1)
            plotted = []
            for j, col in enumerate(avail_drivers):
                if col not in ts.columns or ts[col].notna().sum() < 2:
                    continue
                norm = normalize_01(ts[col].ffill().bfill())
                ax_drv.plot(ts["From"], norm, color=DRIVER_COLORS[j], lw=1.5, alpha=0.85,
                            label=DRIVER_DISPLAY[col])
                plotted.append(col)
            ax_drv.set_ylim(-0.05, 1.05)
            ax_drv.set_ylabel("Driver (norm. 0–1)", fontsize=8)
            ax_drv.tick_params(labelsize=8)
            ax_drv.grid(axis="y", lw=0.4, alpha=0.4)
            ax_drv.spines[["top", "right"]].set_visible(False)
            ax_drv.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
            ax_drv.xaxis.set_major_locator(mdates.YearLocator())
            if plotted:
                ax_drv.legend(fontsize=7.5, loc="upper left", ncol=len(plotted),
                              frameon=True, framealpha=0.9)
            ax_drv.set_xlabel("Assessment window start", fontsize=9)

        fig.tight_layout()
        fig.savefig(OUTDIR / f"ts_{dname.lower().replace(' ', '_')}.png",
                    dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"Saved: ts_{dname.lower().replace(' ', '_')}.png")

    # ============================================================= ADM1 GRIDS
    for iso3 in found:
        dname  = COUNTRY_NAMES.get(iso3, iso3)
        mask   = (panel["Country"] == iso3) & (panel["is_projection"] == 0)
        areas  = sorted(panel.loc[mask, AREA].unique())
        n      = len(areas)
        ncols  = min(5, n)
        nrows  = (n + ncols - 1) // ncols

        fig, axes = plt.subplots(nrows, ncols,
                                  figsize=(ncols * 2.8, nrows * 2.4),
                                  sharex=False, sharey=False)
        axes = np.array(axes).reshape(-1)

        # shared x range for this country
        sub_all = panel[mask]
        xmin_c  = sub_all["From"].min()
        xmax_c  = sub_all["From"].max() + pd.DateOffset(months=3)

        for i, pcode in enumerate(areas):
            ax  = axes[i]
            ts  = area_ts(panel, iso3, pcode)
            lbl = names.get(pcode, "") or pcode

            ax.set_xlim(xmin_c, xmax_c)
            _draw(ax, ts, OOF_START, lw_actual=1.4, ms=2.5, lw_nowcast=1.4)

            ymax = max(80, float(ts["actual"].max()) * 1.15) if ts["actual"].notna().any() else 80
            _fmt_ax(ax, ylim=(0, ymax))
            ax.set_title(lbl, fontsize=7, pad=3)
            ax.tick_params(labelsize=6)
            ax.xaxis.set_major_locator(mdates.YearLocator(2))  # every 2 years

        for j in range(n, len(axes)):
            axes[j].set_visible(False)

        fig.suptitle(f"{dname} — admin-1 nowcast vs actual", fontsize=10, fontweight="bold")
        fig.legend(handles=LEGEND_HANDLES, loc="lower right", ncol=1, fontsize=7,
                   frameon=True, framealpha=0.9, bbox_to_anchor=(0.99, 0.01))
        fig.tight_layout(rect=[0, 0.03, 1, 0.97])
        out = OUTDIR / f"adm1_{dname.lower().replace(' ', '_')}.png"
        fig.savefig(out, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"Saved: {out.name}")

    print(f"\nDone. All figures in {OUTDIR}")


def normalize_01(s):
    lo, hi = s.min(), s.max()
    return s * 0.0 if hi - lo < 1e-9 else (s - lo) / (hi - lo)


if __name__ == "__main__":
    main()
