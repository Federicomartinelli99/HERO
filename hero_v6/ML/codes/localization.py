"""
localization.py — does localizing the model help?

A single global model is forced to fit very different country regimes. This script tests,
for BOTH rounds (static inference and nowcasting), whether training at a narrower scope
lifts per-country accuracy:

  * global   — one XGBoost on all countries (current behaviour), scored per country.
  * regional — one XGBoost per region (map below), scored on each of its countries.
  * local    — one XGBoost per country (only where enough data), scored on that country.

Validation mirrors each round:
  * static  — GroupKFold by admin-1 area within the scope (unseen areas), out-of-fold.
  * nowcast — rolling-origin expanding backtest within the scope (ORIGINS from nowcast.py),
              trained on all rows before each origin, scored on current (is_projection==0)
              rows in the test window.

Reuses build_xy / make_models / scores (static_inference) and build_panel / make_features /
feature_sets_for / ORIGINS (nowcast). Only XGBoost is run (the best estimator in both rounds).

Run:
    C:/Users/jonas/miniconda3/envs/ewm/python.exe hero_v6/ML/codes/localization.py
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
from sklearn.model_selection import GroupKFold

sys.path.insert(0, str(Path(__file__).resolve().parent))
from static_inference import build_xy, make_models, scores, AREA_KEY
from nowcast import build_panel, make_features, feature_sets_for, ORIGINS, TEST_WINDOW_M, AREA, TARGET

# ----------------------------------------------------------------------------- config
RANDOM_STATE = 42
ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "merged" / "merged_adm1_wide.parquet"
OUTDIR = ROOT / "ML" / "results" / "localization"
OUTDIR.mkdir(parents=True, exist_ok=True)

MIN_EVAL = 5          # min scored rows to report a country's metric
MIN_LOCAL_WINDOWS = 60  # min rows for a per-country (local) model to be attempted
MIN_LOCAL_AREAS = 5     # min admin-1 areas for a within-country area hold-out

# region map over the ISO3 codes present (geographic / agro-climatic grouping)
REGIONS = {
    "Sahel/West Africa": ["MLI", "BFA", "NER", "TCD", "SEN", "MRT", "GMB", "GNB",
                          "NGA", "GHA", "CIV", "LBR", "SLE", "TGO", "BEN", "GIN", "CPV"],
    "Horn/East Africa":  ["SOM", "ETH", "SSD", "KEN", "SDN", "DJI", "UGA", "TZA"],
    "Central Africa":    ["COD", "CAF", "CMR"],
    "Southern Africa":   ["MOZ", "ZMB", "ZWE", "NAM", "MDG", "ZAF"],
    "Latin America/Carib.": ["GTM", "HND", "HTI", "SLV", "ECU"],
    "Asia":              ["AFG", "YEM", "PAK", "BGD", "TLS"],
}
COUNTRY_REGION = {c: r for r, cs in REGIONS.items() for c in cs}


def xgb():
    return make_models()["xgboost"]


# ============================================================ STATIC (GroupKFold by area)
def static_oof(X, y, groups, mask):
    """Out-of-fold XGBoost predictions within `mask`, GroupKFold by area."""
    idx = np.where(mask)[0]
    oof = np.full(len(y), np.nan)
    if len(idx) == 0:
        return oof
    gsub = groups.iloc[idx]
    ng = gsub.nunique()
    if ng < 2:
        return oof
    nsp = min(5, ng)
    gkf = GroupKFold(n_splits=nsp)
    Xs, ys = X.iloc[idx], y.iloc[idx]
    for tr, te in gkf.split(Xs, ys, gsub):
        m = xgb().fit(Xs.iloc[tr], ys.iloc[tr])
        oof[idx[te]] = m.predict(Xs.iloc[te])
    return oof


# ============================================================ NOWCAST (rolling origin)
def nowcast_oof(X, y, panel, cols, train_mask, eval_mask):
    """Expanding rolling-origin XGBoost OOF. train within `train_mask`, score within `eval_mask`."""
    From = panel["From"].values
    oof = np.full(len(y), np.nan)
    for org in ORIGINS:
        c = np.datetime64(pd.Timestamp(org))
        c2 = np.datetime64(pd.Timestamp(org) + pd.DateOffset(months=TEST_WINDOW_M))
        trm = (From < c) & train_mask
        tem = (From >= c) & (From < c2) & eval_mask
        if tem.sum() == 0 or trm.sum() < 50:
            continue
        m = xgb().fit(X.loc[trm, cols], y.loc[trm])
        oof[tem] = m.predict(X.loc[tem, cols])
    return oof


# ============================================================ per-country scoring
def score_countries(y, oof, country, sel=None):
    """R²/MAE per country over rows where oof is finite (optionally intersected with sel)."""
    rows = []
    fin = np.isfinite(oof)
    if sel is not None:
        fin = fin & sel
    for ctry in np.unique(country[fin]):
        cm = fin & (country == ctry)
        if cm.sum() < MIN_EVAL:
            continue
        s = scores(y.values[cm] if hasattr(y, "values") else y[cm], oof[cm])
        rows.append({"Country": ctry, **s, "n": int(cm.sum())})
    return pd.DataFrame(rows).set_index("Country")


# ============================================================ round drivers
def run_static(df):
    print("\n[STATIC] global / regional / local — GroupKFold by area, XGBoost")
    X, y, src = build_xy(df)
    groups = src[AREA_KEY]
    country = src["Country"].values
    n = len(y)

    # global: OOF over all data
    g_oof = static_oof(X, y, groups, np.ones(n, bool))
    g = score_countries(y, g_oof, country).add_suffix("_global")

    # regional
    reg_oof = np.full(n, np.nan)
    for region, members in REGIONS.items():
        mask = np.isin(country, members)
        if mask.sum() == 0:
            continue
        reg_oof_r = static_oof(X, y, groups, mask)
        reg_oof[mask] = reg_oof_r[mask]
        print(f"  regional[{region}]: rows={int(mask.sum())}")
    r = score_countries(y, reg_oof, country).add_suffix("_regional")

    # local: per country where feasible
    loc_oof = np.full(n, np.nan)
    for ctry in np.unique(country):
        mask = country == ctry
        if mask.sum() < MIN_LOCAL_WINDOWS or groups.iloc[np.where(mask)[0]].nunique() < MIN_LOCAL_AREAS:
            continue
        loc_oof_c = static_oof(X, y, groups, mask)
        loc_oof[mask] = loc_oof_c[mask]
    l = score_countries(y, loc_oof, country).add_suffix("_local")

    return combine(g, r, l)


def run_nowcast(df):
    print("\n[NOWCAST] global / regional / local — rolling-origin backtest, XGBoost nowcast set")
    panel = build_panel(df, include_projections=True).reset_index(drop=True)
    X, y = make_features(panel, include_is_proj=True)
    cols = feature_sets_for(X)["nowcast"]
    country = panel["Country"].values
    is_cur = panel["is_projection"].values == 0    # eval only on observed current windows
    n = len(y)

    # global: train on all, eval on current
    g_oof = nowcast_oof(X, y, panel, cols, np.ones(n, bool), is_cur)
    g = score_countries(y, g_oof, country).add_suffix("_global")

    # regional
    reg_oof = np.full(n, np.nan)
    for region, members in REGIONS.items():
        mask = np.isin(country, members)
        if mask.sum() == 0:
            continue
        o = nowcast_oof(X, y, panel, cols, mask, mask & is_cur)
        reg_oof[mask] = o[mask]
        print(f"  regional[{region}]: rows={int(mask.sum())}")
    r = score_countries(y, reg_oof, country).add_suffix("_regional")

    # local
    loc_oof = np.full(n, np.nan)
    for ctry in np.unique(country):
        mask = country == ctry
        if mask.sum() < MIN_LOCAL_WINDOWS:
            continue
        o = nowcast_oof(X, y, panel, cols, mask, mask & is_cur)
        loc_oof[mask] = o[mask]
    l = score_countries(y, loc_oof, country).add_suffix("_local")

    return combine(g, r, l)


def combine(g, r, l):
    """Merge the three scopes into one per-country table with R2/MAE/n columns."""
    out = g.join(r, how="outer").join(l, how="outer")
    keep = [c for c in out.columns if c.startswith(("R2_", "MAE_", "n_"))]
    return out[keep]


# ============================================================ plotting
def plot_compare(static_df, nowcast_df, path):
    fig, axes = plt.subplots(1, 2, figsize=(14, 11))
    for ax, df, title, best in [
        (axes[0], static_df, "Static inference (GroupKFold by area)", ["SDN", "KEN", "NGA"]),
        (axes[1], nowcast_df, "Nowcast (rolling backtest)", ["MLI", "CMR", "SSD", "KEN"]),
    ]:
        # keep countries with a local model (the interesting comparison), sort by global R2
        sub = df[df["R2_local"].notna()].copy()
        sub = sub.sort_values("R2_global")
        countries = sub.index.tolist()
        ypos = np.arange(len(countries))
        h = 0.26
        for k, (scope, color) in enumerate([("global", "#adb5bd"),
                                            ("regional", "#4895ef"),
                                            ("local", "#f3722c")]):
            vals = np.clip(sub[f"R2_{scope}"].values, -1.0, 1.0)
            ax.barh(ypos + (1 - k) * h, vals, height=h, color=color, label=scope, zorder=3)
        ax.axvline(0, color="#333", lw=0.8)
        ax.set_yticks(ypos)
        ax.set_yticklabels(countries, fontsize=8)
        ax.set_xlim(-1.05, 1.0)
        ax.set_xlabel("R²  (clipped at −1)", fontsize=9)
        ax.set_title(title, fontsize=10, fontweight="bold")
        ax.grid(axis="x", lw=0.4, alpha=0.4, zorder=0)
        ax.spines[["top", "right"]].set_visible(False)
        # mark the round's known high-signal countries
        for i, c in enumerate(countries):
            if c in best:
                ax.get_yticklabels()[i].set_fontweight("bold")
        ax.legend(fontsize=8, loc="lower right", frameon=True, framealpha=0.9)
    fig.suptitle("Does localizing the model help? Per-country R² by training scope",
                 fontsize=12, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.98])
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def best_scope(row):
    cand = {s: row.get(f"R2_{s}") for s in ["global", "regional", "local"]}
    cand = {s: v for s, v in cand.items() if pd.notna(v)}
    return max(cand, key=cand.get) if cand else "-"


# ============================================================ main
def main():
    print(f"Loading {DATA}")
    df = pd.read_parquet(DATA)

    static_df = run_static(df)
    static_df.to_csv(OUTDIR / "metrics_static.csv")
    nowcast_df = run_nowcast(df)
    nowcast_df.to_csv(OUTDIR / "metrics_nowcast.csv")

    plot_compare(static_df, nowcast_df, OUTDIR / "scope_comparison.png")

    # summary: recommended scope per country + how often local/regional beats global
    lines = ["# Localization — does localizing the model help?\n",
             "For each country, R² under three training scopes (XGBoost). "
             "Static = GroupKFold by area; Nowcast = rolling-origin backtest.\n"]
    for name, df_r, best in [("Static", static_df, ["SDN", "KEN", "NGA"]),
                             ("Nowcast", nowcast_df, ["MLI", "CMR", "SSD", "KEN"])]:
        df_r = df_r.copy()
        df_r["best_scope"] = df_r.apply(best_scope, axis=1)
        has_local = df_r[df_r["R2_local"].notna()]
        n_reg = int((df_r["R2_regional"] > df_r["R2_global"]).sum())
        n_loc = int((has_local["R2_local"] > has_local["R2_global"]).sum())
        show = (df_r[["R2_global", "R2_regional", "R2_local", "best_scope"]]
                .sort_values("R2_global", ascending=False).round(3))
        lines += [f"\n## {name}\n",
                  f"Regional beats global in **{n_reg}/{len(df_r)}** countries; "
                  f"local beats global in **{n_loc}/{len(has_local)}** (of those with a local model).\n",
                  "```", show.to_string(), "```\n"]
        print(f"\n[{name}] regional>global: {n_reg}/{len(df_r)}  |  "
              f"local>global: {n_loc}/{len(has_local)}")
        print(show.head(15).to_string())
    (OUTDIR / "README.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"\nDone. Artifacts in {OUTDIR}")
    for p in sorted(OUTDIR.iterdir()):
        print("  ", p.name)


if __name__ == "__main__":
    main()
