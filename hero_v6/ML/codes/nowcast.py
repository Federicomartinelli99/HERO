"""
Nowcasting IPC Phase 3+ at admin-1 (autoregressive panel) for hero_v6.

Estimates an area's *current* phase_3plus_percentage from its last known IPC value
(lag) plus the latest exogenous drivers, validated over time (rolling-origin backtest).
The bar to beat is a persistence baseline (carry the last assessment forward), which is
strong because IPC is highly persistent — so the real question is whether the drivers add
skill on top of persistence (i.e. predict the *change* since the last assessment).

Two panels are compared:
  - panel_cur : current-validity windows only (exclude projections)
  - panel_all : current + projection windows (include projections), preference-deduped,
                carrying an `is_projection` flag
Metrics are reported separately for observed ('current') and projection eval windows.

Driver feature engineering, model set and scoring are reused from static_inference.py.

Run:
    C:/Users/jonas/miniconda3/envs/ewm/python.exe hero_v6/ML/codes/nowcast.py
"""

import os
# MKL/OpenMP guards — MUST be set before numpy is imported (and before importing
# static_inference, which imports numpy). Otherwise matplotlib crashes (0xc06d007f).
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
import shap

# reuse driver engineering / models / scoring from the sibling script
sys.path.insert(0, str(Path(__file__).resolve().parent))
from static_inference import build_xy, make_models, scores  # noqa: E402

# ----------------------------------------------------------------------------- config
RANDOM_STATE = 42
SHAP_SAMPLE = 3000
TARGET = "phase_3plus_percentage"
AREA = "adm1_pcode"

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "merged" / "merged_adm1_wide.parquet"
OUTDIR = ROOT / "ML" / "results" / "nowcast"
OUTDIR.mkdir(parents=True, exist_ok=True)

ORIGINS = ["2023-07-01", "2024-01-01", "2024-07-01", "2025-01-01", "2025-07-01"]  # rolling backtest
TEST_WINDOW_M = 6
HOLDOUT_CUT = "2024-01-01"
VP_RANK = {"current": 0, "first projection": 1, "second projection": 2}
AR_FEATS = ["lag1_phase3plus", "lag2_phase3plus", "recent_trend", "months_since_last"]


# ------------------------------------------------------------------------- panel + features
def build_panel(df, include_projections):
    """One row per (area, window `From`), autoregressive features added per area.

    Windows are deduped with preference current > first > second projection (this dedup is a
    no-op for current-only, and is exactly what makes projections tractable — see plan).
    """
    d = df[df[TARGET].notna()].copy()
    if not include_projections:
        d = d[d["Validity period"] == "current"].copy()
    d["From"] = pd.to_datetime(d["From"])
    d["Date of analysis"] = pd.to_datetime(d["Date of analysis"], errors="coerce")
    d["vp_rank"] = d["Validity period"].map(VP_RANK).fillna(9)
    d = d.sort_values([AREA, "From", "vp_rank", "Date of analysis"])
    d = d.drop_duplicates([AREA, "From"], keep="first")           # authoritative value per window
    d = d.sort_values([AREA, "From"]).reset_index(drop=True)

    g = d.groupby(AREA, sort=False)
    d["lag1_phase3plus"] = g[TARGET].shift(1)
    d["lag2_phase3plus"] = g[TARGET].shift(2)
    d["recent_trend"] = d["lag1_phase3plus"] - d["lag2_phase3plus"]
    d["months_since_last"] = (d["From"] - g["From"].shift(1)).dt.days / 30.44
    d["is_projection"] = (d["Validity period"] != "current").astype(int)
    return d


NON_DELTA = ["Country", "year", "month"]  # categorical/time cols we don't difference


def make_features(panel, include_is_proj):
    """Driver features (build_xy) + AR features + driver deltas, aligned to `panel`."""
    X, y, _ = build_xy(panel)                       # driver cols, same row order as panel
    X = X.reset_index(drop=True)
    ar = panel[AR_FEATS].reset_index(drop=True)
    X = pd.concat([X, ar], axis=1)
    if include_is_proj:
        X["is_projection"] = panel["is_projection"].reset_index(drop=True)

    # driver deltas: change in each continuous driver since the area's previous window
    cont = [c for c in X.columns if c not in AR_FEATS + ["is_projection"] + NON_DELTA]
    tmp = X[cont].copy()
    tmp[AREA] = panel[AREA].values                  # panel is sorted by (area, From)
    deltas = tmp.groupby(AREA, sort=False).diff()   # current - previous, NaN at first obs
    deltas.columns = ["d_" + c for c in cont]
    X = pd.concat([X, deltas], axis=1)
    return X, y.reset_index(drop=True)


def feature_sets_for(X):
    delta = [c for c in X.columns if c.startswith("d_")]
    core = [c for c in X.columns if c not in delta]                       # drivers + AR + is_proj
    static = [c for c in core if c not in AR_FEATS + ["is_projection"]]   # drivers only
    ar_only = [c for c in core if c in AR_FEATS + ["is_projection"]]      # lag/trend/gap only
    return {"ar_only": ar_only, "static": static, "nowcast": core, "nowcast_delta": list(X.columns)}


# --------------------------------------------------------------------------- prediction core
def split_predict(X, y, panel, trm, tem):
    """Fit persistence + every (feature_set, model) on `trm`, predict on `tem`.

    Returns dict[(fs, model)] -> array of length n, NaN outside the test mask.
    """
    n = len(y)
    lag1 = panel["lag1_phase3plus"].values
    pred = {("persistence", ""): np.full(n, np.nan)}
    pred[("persistence", "")][tem] = pd.Series(lag1[tem]).fillna(y.values[trm].mean()).values
    for fs, cols in feature_sets_for(X).items():
        for mname, mdl in make_models().items():          # fresh estimators
            mdl.fit(X.loc[trm, cols], y.loc[trm])
            arr = np.full(n, np.nan)
            arr[tem] = mdl.predict(X.loc[tem, cols])
            pred[(fs, mname)] = arr
    return pred


def run_backtest(X, y, panel):
    """Expanding-window rolling-origin backtest. Returns merged OOF preds + tested mask."""
    From = panel["From"].values
    n = len(y)
    tested = np.zeros(n, bool)
    merged = None
    for org in ORIGINS:
        c = np.datetime64(pd.Timestamp(org))
        c2 = np.datetime64(pd.Timestamp(org) + pd.DateOffset(months=TEST_WINDOW_M))
        trm = From < c
        tem = (From >= c) & (From < c2)
        if tem.sum() == 0 or trm.sum() == 0:
            continue
        tested |= tem
        fold = split_predict(X, y, panel, trm, tem)
        if merged is None:
            merged = {k: v.copy() for k, v in fold.items()}
        else:
            for k, v in fold.items():
                m = ~np.isnan(v)
                merged[k][m] = v[m]
    return merged, tested


def score_by_country(y, pred, sel, panel):
    """Score every (feature_set, model) broken down by country, on the selection mask.

    Returns a DataFrame with columns: Country, feature_set, model, MAE, RMSE, R2, n.
    Only countries with >= 5 evaluated windows are included.
    """
    countries = panel["Country"].values
    rows = []
    for ctry in np.unique(countries[sel]):
        cmask = sel & (countries == ctry)
        if cmask.sum() < 5:
            continue
        yv = y.values[cmask]
        for (fs, m), arr in pred.items():
            if fs == "persistence":
                continue
            s = scores(yv, arr[cmask])
            rows.append({"Country": ctry, "feature_set": fs, "model": m, **s, "n": int(cmask.sum())})
        # persistence baseline per country
        s_p = scores(yv, pred[("persistence", "")][cmask])
        rows.append({"Country": ctry, "feature_set": "-", "model": "persistence", **s_p, "n": int(cmask.sum())})
    return pd.DataFrame(rows)


def score_cell(y, pred, sel, cell_name):
    """Score every series on the selection mask; skill = MAE improvement over persistence."""
    yv = y.values[sel]
    base = scores(yv, pred[("persistence", "")][sel])
    base_mae = base["MAE"]
    rows = [{"cell": cell_name, "feature_set": "-", "model": "persistence",
             **base, "skill_vs_persist": 0.0, "n": int(sel.sum())}]
    for (fs, m), arr in pred.items():
        if fs == "persistence":
            continue
        s = scores(yv, arr[sel])
        s["skill_vs_persist"] = (base_mae - s["MAE"]) / base_mae
        rows.append({"cell": cell_name, "feature_set": fs, "model": m, **s, "n": int(sel.sum())})
    return pd.DataFrame(rows)


def pivot_print(df, title):
    print(f"\n{title}")
    p = df.pivot_table(index=["feature_set", "model"], columns="cell",
                       values="R2", sort=False)
    print(p.round(3).to_string())


# ---------------------------------------------------------------------------------- main
def main():
    print(f"Loading {DATA}")
    df = pd.read_parquet(DATA)
    panel_cur = build_panel(df, include_projections=False)
    panel_all = build_panel(df, include_projections=True)
    Xc, yc = make_features(panel_cur, include_is_proj=False)
    Xa, ya = make_features(panel_all, include_is_proj=True)
    print(f"  panel_cur: {len(Xc)} windows, lag1 avail {panel_cur['lag1_phase3plus'].notna().mean():.1%}")
    print(f"  panel_all: {len(Xa)} windows, lag1 avail {panel_all['lag1_phase3plus'].notna().mean():.1%}, "
          f"projection windows {int(panel_all['is_projection'].sum())}")

    # ---------------------------------------------------------- rolling backtest, 3 cells
    print("\n[Backtest] rolling-origin, expanding window")
    pred_cur, tested_cur = run_backtest(Xc, yc, panel_cur)
    pred_all, tested_all = run_backtest(Xa, ya, panel_all)
    is_proj_all = panel_all["is_projection"].values.astype(bool)

    parts = [
        score_cell(yc, pred_cur, tested_cur, "train_cur|eval_current"),
        score_cell(ya, pred_all, tested_all & ~is_proj_all, "train_all|eval_current"),
        score_cell(ya, pred_all, tested_all & is_proj_all, "train_all|eval_projection"),
    ]
    metrics_bt = pd.concat(parts, ignore_index=True)
    metrics_bt.to_csv(OUTDIR / "metrics_backtest.csv", index=False)
    pivot_print(metrics_bt, "Backtest R² by cell (rows = feature_set × model):")

    # skill-vs-persistence focus table (primary cell)
    skill = (metrics_bt[metrics_bt["cell"] == "train_all|eval_current"]
             [["feature_set", "model", "MAE", "R2", "skill_vs_persist"]]
             .sort_values("skill_vs_persist", ascending=False))
    skill.to_csv(OUTDIR / "skill_vs_persistence.csv", index=False)
    print("\nSkill vs persistence (train_all | eval_current):")
    print(skill.round(3).to_string(index=False))

    # cumulative decomposition: persistence -> AR-only -> +driver levels -> +driver deltas
    prim = metrics_bt[metrics_bt["cell"] == "train_all|eval_current"]

    def get(fs, m, col):
        r = prim[(prim.feature_set == fs) & (prim.model == m)]
        return float(r.iloc[0][col]) if len(r) else np.nan

    contrib_rows = []
    for m in ["xgboost", "random_forest", "lightgbm", "decision_tree"]:
        ar, nc, nd = get("ar_only", m, "MAE"), get("nowcast", m, "MAE"), get("nowcast_delta", m, "MAE")
        contrib_rows.append({
            "model": m,
            "ar_only_MAE": ar, "nowcast_MAE": nc, "nowcast_delta_MAE": nd,
            "levels_gain_pct": (ar - nc) / ar,          # driver levels on top of AR
            "deltas_gain_pct": (nc - nd) / nc,          # driver deltas on top of levels
            "all_drivers_gain_pct": (ar - nd) / ar,     # levels + deltas vs AR-only
            "ar_only_R2": get("ar_only", m, "R2"),
            "nowcast_R2": get("nowcast", m, "R2"),
            "nowcast_delta_R2": get("nowcast_delta", m, "R2")})
    driver_contrib = pd.DataFrame(contrib_rows)
    driver_contrib.to_csv(OUTDIR / "driver_contribution.csv", index=False)
    print("\nDecomposition (train_all | eval_current): AR-only -> +levels -> +deltas")
    print(driver_contrib.round(3).to_string(index=False))

    # ------------------------------------------------- per-country breakdown (primary cell)
    print("\n[Per-country] train_all | eval_current — nowcast feature set")
    primary_mask = tested_all & ~is_proj_all
    country_metrics = score_by_country(ya, pred_all, primary_mask, panel_all)
    country_metrics.to_csv(OUTDIR / "metrics_per_country.csv", index=False)

    # print pivot: countries × models for the nowcast feature set, sorted by XGB R²
    nc_rows = country_metrics[country_metrics["feature_set"].isin(["nowcast", "-"])]
    pivot_r2 = nc_rows.pivot_table(index="Country", columns="model", values="R2")
    pivot_mae = nc_rows.pivot_table(index="Country", columns="model", values="MAE")
    xgb_order = pivot_r2.get("xgboost", pivot_r2.iloc[:, 0]).sort_values(ascending=False)
    print("\nR² per country (nowcast feature set + persistence baseline):")
    print(pivot_r2.loc[xgb_order.index].round(3).to_string())
    print("\nMAE per country (nowcast feature set + persistence baseline):")
    print(pivot_mae.loc[xgb_order.index].round(2).to_string())

    # ----------------------------------------------------------- headline single holdout
    print(f"\n[Holdout] train From < {HOLDOUT_CUT}, test From >= {HOLDOUT_CUT}")
    cut = np.datetime64(pd.Timestamp(HOLDOUT_CUT))
    fc, fa = panel_cur["From"].values, panel_all["From"].values
    ho_cur = split_predict(Xc, yc, panel_cur, fc < cut, fc >= cut)
    ho_all = split_predict(Xa, ya, panel_all, fa < cut, fa >= cut)
    te_cur = fc >= cut
    te_all_c = (fa >= cut) & ~is_proj_all
    te_all_p = (fa >= cut) & is_proj_all
    ho = pd.concat([
        score_cell(yc, ho_cur, te_cur, "train_cur|eval_current"),
        score_cell(ya, ho_all, te_all_c, "train_all|eval_current"),
        score_cell(ya, ho_all, te_all_p, "train_all|eval_projection"),
    ], ignore_index=True)
    ho.to_csv(OUTDIR / "metrics_headline_holdout.csv", index=False)
    pivot_print(ho, "Holdout R² by cell:")

    # ----------------------------------------------------- plots (holdout, panel_all, current eval)
    lag1_a = panel_all["lag1_phase3plus"].values
    for mname in ["decision_tree", "random_forest", "xgboost", "lightgbm"]:
        arr = ho_all[("nowcast", mname)]
        sel = te_all_c & ~np.isnan(arr)
        r2 = scores(ya.values[sel], arr[sel])["R2"]
        fig, ax = plt.subplots(figsize=(5, 5))
        ax.scatter(ya.values[sel], arr[sel], s=8, alpha=0.25)
        ax.plot([0, 100], [0, 100], "r--", lw=1)
        ax.set_xlim(0, 100); ax.set_ylim(0, 100)
        ax.set_xlabel("actual phase_3plus_%"); ax.set_ylabel("nowcast phase_3plus_%")
        ax.set_title(f"nowcast {mname}  (holdout eval_current, R2={r2:.3f})")
        fig.tight_layout(); fig.savefig(OUTDIR / f"pred_vs_actual_{mname}.png", dpi=120)
        plt.close(fig)

    # change scatter: predicted vs actual change since last assessment (XGBoost nowcast_delta)
    arr = ho_all[("nowcast_delta", "xgboost")]
    sel = te_all_c & ~np.isnan(arr) & ~np.isnan(lag1_a)
    dact = ya.values[sel] - lag1_a[sel]
    dpred = arr[sel] - lag1_a[sel]
    corr = np.corrcoef(dact, dpred)[0, 1]
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.scatter(dact, dpred, s=8, alpha=0.25)
    lim = max(20, np.nanpercentile(np.abs(dact), 99))
    ax.plot([-lim, lim], [-lim, lim], "r--", lw=1)
    ax.axhline(0, color="grey", lw=0.5); ax.axvline(0, color="grey", lw=0.5)
    ax.set_xlim(-lim, lim); ax.set_ylim(-lim, lim)
    ax.set_xlabel("actual change since last (pp)"); ax.set_ylabel("predicted change (pp)")
    ax.set_title(f"nowcast XGBoost — change captured (r={corr:.2f})")
    fig.tight_layout(); fig.savefig(OUTDIR / "change_scatter.png", dpi=120)
    plt.close(fig)

    # ------------------------------------------------------------------------- SHAP (nowcast_delta XGB)
    print("\n[SHAP] nowcast_delta XGBoost on panel_all")
    nowc_cols = feature_sets_for(Xa)["nowcast_delta"]
    xgb = make_models()["xgboost"].fit(Xa[nowc_cols], ya)
    Xs = Xa[nowc_cols].sample(min(SHAP_SAMPLE, len(Xa)), random_state=RANDOM_STATE)
    sv = shap.TreeExplainer(xgb).shap_values(Xs)
    plt.figure()
    shap.summary_plot(sv, Xs, show=False, max_display=15)
    plt.tight_layout(); plt.savefig(OUTDIR / "shap_beeswarm.png", dpi=120, bbox_inches="tight")
    plt.close()
    shap_imp = pd.Series(np.abs(sv).mean(0), index=Xs.columns).sort_values(ascending=False)
    shap_imp.to_csv(OUTDIR / "shap_importance.csv", header=["mean_abs_shap"])

    # ------------------------------------------------------------------------- findings
    def cell_tbl(dfm, cell):
        t = dfm[dfm["cell"] == cell][["feature_set", "model", "MAE", "RMSE", "R2", "skill_vs_persist"]]
        return t.sort_values("R2", ascending=False).round(3).to_string(index=False)

    lines = [
        "# Nowcasting IPC Phase 3+ — findings\n",
        f"panel_cur: {len(Xc)} windows | panel_all: {len(Xa)} windows "
        f"({int(panel_all['is_projection'].sum())} projection). Temporal validation.\n",
        "Persistence = carry last known IPC forward. Skill = MAE improvement over persistence.\n",
        "\n## Rolling backtest — train_all | eval_current (PRIMARY)\n",
        "```", cell_tbl(metrics_bt, "train_all|eval_current"), "```\n",
        "\n## Driver contribution — (AR + drivers) vs (AR only)\n",
        "How much the exogenous drivers add on top of the autoregressive terms (lag1/lag2/trend/gap).\n",
        "```", driver_contrib.round(3).to_string(index=False), "```\n",
        "\n## Rolling backtest — train_cur | eval_current (exclude projections)\n",
        "```", cell_tbl(metrics_bt, "train_cur|eval_current"), "```\n",
        "\n## Rolling backtest — train_all | eval_projection (reproducing IPC projections)\n",
        "```", cell_tbl(metrics_bt, "train_all|eval_projection"), "```\n",
        "\n## Headline holdout — train_all | eval_current\n",
        "```", cell_tbl(ho, "train_all|eval_current"), "```\n",
        "\n## Top nowcast drivers — mean(|SHAP|), XGBoost (panel_all)\n",
        "```", shap_imp.head(15).round(3).to_string(), "```\n",
        f"\nChange-direction correlation (predicted vs actual change since last assessment): r = {corr:.2f}.\n",
        "\n## Per-country R2 — nowcast XGBoost vs persistence (train_all | eval_current)\n",
        "```",
        pivot_r2.loc[xgb_order.index][["xgboost", "random_forest", "lightgbm", "persistence"]]
                .round(3).to_string(),
        "```\n",
        "\n## Per-country MAE — nowcast XGBoost vs persistence (train_all | eval_current)\n",
        "```",
        pivot_mae.loc[xgb_order.index][["xgboost", "random_forest", "lightgbm", "persistence"]]
                 .round(2).to_string(),
        "```\n",
    ]
    (OUTDIR / "README.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"\nDone. Artifacts written to {OUTDIR}")
    for p in sorted(OUTDIR.iterdir()):
        print("  ", p.name)


if __name__ == "__main__":
    main()
