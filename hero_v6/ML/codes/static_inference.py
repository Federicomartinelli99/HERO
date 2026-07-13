"""
Static inference on IPC Phase 3+ (Tasks 2.2 & 2.3) for hero_v6.

Predicts `phase_3plus_percentage` at admin-1 level from the exogenous food-security
drivers in `merged_adm1_wide.parquet` (conflict, displacement, rainfall, food prices,
GDELT media signals), using ONLY models that handle missing values natively --
DecisionTree, RandomForest, XGBoost, LightGBM. No imputation this round; NaN is kept
intact. (KNN + imputation are a later round.)

Feature logic mirrors the leakage-free `build_xy` in notebooks/phase3plus_model.ipynb.
Validation uses a geographic hold-out split (unseen adm1 areas) plus GroupKFold CV.
Explainability via impurity (Gini) importance and SHAP (TreeExplainer on XGBoost).

Run:
    C:/Users/jonas/miniconda3/envs/ewm/python.exe hero_v6/ML/codes/static_inference.py
"""

import os
# OpenMP/MKL guards — must be set BEFORE numpy is imported. XGBoost/LightGBM bundle their own
# OpenMP runtime; without these, numpy-MKL LAPACK calls (e.g. matplotlib tight_layout ->
# numpy.linalg.inv) crash the process with Windows fatal exception 0xc06d007f.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("MKL_THREADING_LAYER", "SEQUENTIAL")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sklearn.model_selection import GroupShuffleSplit, GroupKFold, train_test_split
from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor
from lightgbm import LGBMRegressor
import shap

# ----------------------------------------------------------------------------- config
RANDOM_STATE = 42
N_SPLITS = 5
TEST_SIZE = 0.2
SHAP_SAMPLE = 3000
TARGET = "phase_3plus_percentage"
AREA_KEY = "adm1_pcode"

ROOT = Path(__file__).resolve().parents[2]          # .../hero_v6
DATA = ROOT / "data" / "merged" / "merged_adm1_wide.parquet"
OUTDIR = ROOT / "ML" / "results" / "static_inference"
OUTDIR.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------------- feature sets
ACLED = [
    "acled_political_violence_events", "acled_civilian_targeting_events",
    "acled_demonstration_events", "acled_political_violence_fatalities",
    "acled_civilian_targeting_fatalities", "acled_demonstration_fatalities",
    "acled_total_events", "acled_total_fatalities",
]
RAIN = ["rain_1m_sum", "rain_1m", "rain_3m", "rain_anomaly_1m", "rain_anomaly_3m"]
WFP = ["wfp_price", "wfp_inflation"]   # wfp_obs_count excluded (data-density, not a driver)
NDVI = ["ndvi_vim", "ndvi_viq"]        # vegetation health / drought (crop & pasture condition)
GDELT = [
    "gdelt_verbal_coop_events", "gdelt_verbal_coop_mentions", "gdelt_verbal_coop_tone",
    "gdelt_material_coop_events", "gdelt_material_coop_mentions", "gdelt_material_coop_tone",
    "gdelt_verbal_conflict_events", "gdelt_verbal_conflict_mentions", "gdelt_verbal_conflict_tone",
    "gdelt_material_conflict_events", "gdelt_material_conflict_mentions", "gdelt_material_conflict_tone",
]


def build_xy(df):
    """Return (X, y, src) with 30 strictly-exogenous driver features. Counts -> per-100k.

    NaN is left intact (native-NaN models handle it). All phase_* columns are excluded
    (leakage guard); phase_all_number is used only as the population denominator.
    """
    df = df[df[TARGET].notna()].copy()
    frm = pd.to_datetime(df["From"])
    pop = df["phase_all_number"].replace(0, np.nan)     # denominator only, never a feature

    X = pd.DataFrame(index=df.index)
    for c in ACLED:
        X[c + "_per100k"] = df[c] / pop * 1e5           # conflict intensity
    X["idp_rate"] = df["idp_population"] / pop           # displacement intensity
    for c in RAIN + WFP + GDELT + NDVI:
        X[c] = df[c]
    X["Country"] = df["Country"].astype("category").cat.codes  # ordinal codes (no NaN)
    X["year"] = frm.dt.year
    X["month"] = frm.dt.month

    leak = [c for c in X.columns if "phase_" in c]
    assert not leak, f"LEAKAGE: phase_* features present: {leak}"

    src = pd.DataFrame({"Country": df["Country"].values, AREA_KEY: df[AREA_KEY].astype(str).values})
    y = df[TARGET].astype(float)
    return X.reset_index(drop=True), y.reset_index(drop=True), src.reset_index(drop=True)


def make_models():
    """Fresh estimators (all handle NaN natively). New instances every call for clean folds."""
    return {
        "decision_tree": DecisionTreeRegressor(random_state=RANDOM_STATE, min_samples_leaf=20),
        "random_forest": RandomForestRegressor(
            n_estimators=400, min_samples_leaf=5, n_jobs=-1, random_state=RANDOM_STATE),
        "xgboost": XGBRegressor(
            tree_method="hist", n_estimators=400, learning_rate=0.05, max_depth=6,
            subsample=0.8, colsample_bytree=0.8, random_state=RANDOM_STATE, n_jobs=-1),
        "lightgbm": LGBMRegressor(
            n_estimators=400, learning_rate=0.03, num_leaves=31, subsample=0.8,
            colsample_bytree=0.8, min_child_samples=40, random_state=RANDOM_STATE,
            n_jobs=1, verbose=-1),
    }


def scores(y_true, y_pred):
    return {
        "MAE": mean_absolute_error(y_true, y_pred),
        "RMSE": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "R2": r2_score(y_true, y_pred),
    }


def country_mean_baseline(country_tr, y_tr, country_te):
    """Per-country mean fit on the training fold only (honest baseline)."""
    cmean = y_tr.groupby(country_tr).mean()
    return country_te.map(cmean).fillna(y_tr.mean()).values


def group_of(feat):
    if feat.startswith("acled"):
        return "conflict"
    if feat.startswith("idp"):
        return "displacement"
    if feat.startswith("rain") or feat.startswith("ndvi"):
        return "climate"
    if feat.startswith("wfp"):
        return "prices"
    if feat.startswith("gdelt"):
        return "media(GDELT)"
    return "context"


def main():
    print(f"Loading {DATA}")
    df = pd.read_parquet(DATA)
    X, y, src = build_xy(df)
    groups = src[AREA_KEY]
    country = src["Country"]
    print(f"  rows={len(X)}  features={X.shape[1]}  areas={groups.nunique()}  "
          f"target mean={y.mean():.1f}%")
    print(f"  features: {list(X.columns)}")

    # ---------------------------------------------------- Task 2.2a: geographic hold-out
    print("\n[Task 2.2] Geographic hold-out split (unseen adm1 areas)")
    gss = GroupShuffleSplit(n_splits=1, test_size=TEST_SIZE, random_state=RANDOM_STATE)
    tr, te = next(gss.split(X, y, groups))
    print(f"  train={len(tr)}  test={len(te)}  "
          f"(train areas={groups.iloc[tr].nunique()}, test areas={groups.iloc[te].nunique()})")

    geo_rows, geo_pred = {}, {}
    geo_rows["baseline_country_mean"] = scores(
        y.iloc[te], country_mean_baseline(country.iloc[tr], y.iloc[tr], country.iloc[te]))
    for name, model in make_models().items():
        model.fit(X.iloc[tr], y.iloc[tr])
        pred = model.predict(X.iloc[te])
        geo_rows[name] = scores(y.iloc[te], pred)
        geo_pred[name] = pred
        print(f"  {name:16s} MAE={geo_rows[name]['MAE']:.3f}  "
              f"RMSE={geo_rows[name]['RMSE']:.3f}  R2={geo_rows[name]['R2']:.3f}")

    metrics_geo = pd.DataFrame(geo_rows).T[["MAE", "RMSE", "R2"]].sort_values("R2", ascending=False)
    metrics_geo.to_csv(OUTDIR / "metrics_geographic_split.csv")

    # ---------------------------------------------------------- random hold-out (comparison)
    print("\n[Comparison] Random hold-out split (rows shuffled, same 80/20 size)")
    tr_r, te_r = train_test_split(range(len(X)), test_size=TEST_SIZE, random_state=RANDOM_STATE)
    rnd_rows = {}
    rnd_rows["baseline_country_mean"] = scores(
        y.iloc[te_r], country_mean_baseline(country.iloc[tr_r], y.iloc[tr_r], country.iloc[te_r]))
    for name, model in make_models().items():
        model.fit(X.iloc[tr_r], y.iloc[tr_r])
        pred = model.predict(X.iloc[te_r])
        rnd_rows[name] = scores(y.iloc[te_r], pred)
        print(f"  {name:16s} MAE={rnd_rows[name]['MAE']:.3f}  "
              f"RMSE={rnd_rows[name]['RMSE']:.3f}  R2={rnd_rows[name]['R2']:.3f}")
    metrics_rnd = pd.DataFrame(rnd_rows).T[["MAE", "RMSE", "R2"]].sort_values("R2", ascending=False)
    metrics_rnd.to_csv(OUTDIR / "metrics_random_split.csv")

    # ------------------------------------------------------- Task 2.2b: GroupKFold CV
    print("\n[Task 2.2] GroupKFold CV (5-fold by area) — out-of-fold")
    gkf = GroupKFold(n_splits=N_SPLITS)
    oof = {n: np.full(len(y), np.nan) for n in ["baseline_country_mean", *make_models()]}
    for tr_i, te_i in gkf.split(X, y, groups):
        oof["baseline_country_mean"][te_i] = country_mean_baseline(
            country.iloc[tr_i], y.iloc[tr_i], country.iloc[te_i])
        for name, model in make_models().items():
            model.fit(X.iloc[tr_i], y.iloc[tr_i])
            oof[name][te_i] = model.predict(X.iloc[te_i])
    metrics_cv = (pd.DataFrame({n: scores(y, p) for n, p in oof.items()}).T[["MAE", "RMSE", "R2"]]
                  .sort_values("R2", ascending=False))
    metrics_cv.to_csv(OUTDIR / "metrics_groupkfold_cv.csv")
    print(metrics_cv.round(3).to_string())

    # ------------------------------------------- Country-ablation: drivers only (no Country)
    print("\n[Ablation] GroupKFold CV WITHOUT Country — drivers only")
    X_nc = X.drop(columns=["Country"])
    oof_nc = {n: np.full(len(y), np.nan) for n in make_models()}
    for tr_i, te_i in gkf.split(X_nc, y, groups):
        for name, model in make_models().items():
            model.fit(X_nc.iloc[tr_i], y.iloc[tr_i])
            oof_nc[name][te_i] = model.predict(X_nc.iloc[te_i])
    metrics_nc = (pd.DataFrame({n: scores(y, p) for n, p in oof_nc.items()}).T[["MAE", "RMSE", "R2"]]
                  .sort_values("R2", ascending=False))
    metrics_nc.to_csv(OUTDIR / "metrics_no_country_cv.csv")
    print(metrics_nc.round(3).to_string())
    # side-by-side delta
    delta = (metrics_cv.loc[metrics_nc.index, "R2"] - metrics_nc["R2"]).rename("R2_drop_without_country")
    print("\nR² drop when Country is removed (GroupKFold CV):")
    print(delta.round(3).to_string())

    # ------------------------------------------ per-country breakdown (geographic hold-out)
    print("\n[Per-country] Geographic hold-out — all models")
    country_te = country.iloc[te].values
    y_te       = y.iloc[te].values
    pc_rows = []
    for ctry in np.unique(country_te):
        cmask = country_te == ctry
        if cmask.sum() < 3:
            continue
        # country-mean baseline (honest: fit on train only)
        s_b = scores(y_te[cmask],
                     country_mean_baseline(country.iloc[tr], y.iloc[tr],
                                           pd.Series([ctry] * int(cmask.sum()))))
        pc_rows.append({"Country": ctry, "model": "baseline_country_mean", **s_b, "n": int(cmask.sum())})
        for name, pred in geo_pred.items():
            s = scores(y_te[cmask], pred[cmask])
            pc_rows.append({"Country": ctry, "model": name, **s, "n": int(cmask.sum())})
    country_geo = pd.DataFrame(pc_rows)
    country_geo.to_csv(OUTDIR / "metrics_per_country.csv", index=False)

    # print pivot sorted by XGBoost R²
    pivot_r2_geo  = country_geo.pivot_table(index="Country", columns="model", values="R2")
    pivot_mae_geo = country_geo.pivot_table(index="Country", columns="model", values="MAE")
    xgb_order_geo = pivot_r2_geo.get("xgboost", pivot_r2_geo.iloc[:, 0]).sort_values(ascending=False)
    print("\nR² per country (geographic hold-out):")
    print(pivot_r2_geo.loc[xgb_order_geo.index].round(3).to_string())
    print("\nMAE per country (geographic hold-out):")
    print(pivot_mae_geo.loc[xgb_order_geo.index].round(2).to_string())

    # ------------------------------------------------------- predicted vs actual plots
    for name, pred in geo_pred.items():
        fig, ax = plt.subplots(figsize=(5, 5))
        ax.scatter(y.iloc[te], pred, s=8, alpha=0.25)
        ax.plot([0, 100], [0, 100], "r--", lw=1)
        ax.set_xlim(0, 100); ax.set_ylim(0, 100)
        ax.set_xlabel("actual phase_3plus_%"); ax.set_ylabel("predicted phase_3plus_%")
        ax.set_title(f"{name}  (geo hold-out, R2={geo_rows[name]['R2']:.3f})")
        fig.tight_layout(); fig.savefig(OUTDIR / f"pred_vs_actual_{name}.png", dpi=120)
        plt.close(fig)

    # -------------------------------------------- Task 2.3a: impurity (Gini) importance
    print("\n[Task 2.3] Impurity (Gini) importance + SHAP")
    dt = DecisionTreeRegressor(random_state=RANDOM_STATE, min_samples_leaf=20).fit(X, y)
    rf = RandomForestRegressor(n_estimators=400, min_samples_leaf=5, n_jobs=-1,
                               random_state=RANDOM_STATE).fit(X, y)
    gini_dt = pd.Series(dt.feature_importances_, index=X.columns).sort_values(ascending=False)
    gini_rf = pd.Series(rf.feature_importances_, index=X.columns).sort_values(ascending=False)
    gini_dt.to_csv(OUTDIR / "gini_importance_dt.csv", header=["importance"])
    gini_rf.to_csv(OUTDIR / "gini_importance_rf.csv", header=["importance"])

    top = gini_rf.head(15)[::-1]
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.barh(top.index, top.values, color="#4C72B0")
    ax.set_title("RandomForest impurity importance (top 15)")
    ax.set_xlabel("importance")
    fig.tight_layout(); fig.savefig(OUTDIR / "impurity_importance_bar.png", dpi=120)
    plt.close(fig)

    # ------------------------------------------------------------- Task 2.3b: SHAP (XGB)
    xgb = XGBRegressor(tree_method="hist", n_estimators=400, learning_rate=0.05, max_depth=6,
                       subsample=0.8, colsample_bytree=0.8, random_state=RANDOM_STATE,
                       n_jobs=-1).fit(X, y)
    Xs = X.sample(min(SHAP_SAMPLE, len(X)), random_state=RANDOM_STATE)
    sv = shap.TreeExplainer(xgb).shap_values(Xs)

    plt.figure()
    shap.summary_plot(sv, Xs, show=False, max_display=15)
    plt.tight_layout(); plt.savefig(OUTDIR / "shap_beeswarm_with_country.png", dpi=120, bbox_inches="tight")
    plt.close()

    plt.figure()
    shap.summary_plot(sv, Xs, plot_type="bar", show=False, max_display=15)
    plt.tight_layout(); plt.savefig(OUTDIR / "shap_bar.png", dpi=120, bbox_inches="tight")
    plt.close()

    shap_imp = pd.Series(np.abs(sv).mean(0), index=Xs.columns).sort_values(ascending=False)
    shap_imp.to_csv(OUTDIR / "shap_importance_with_country.csv", header=["mean_abs_shap"])

    # ----------------------------------------- SHAP without Country (ablation comparison)
    print("\n[Task 2.3] SHAP without Country feature")
    xgb_nc = XGBRegressor(tree_method="hist", n_estimators=400, learning_rate=0.05, max_depth=6,
                          subsample=0.8, colsample_bytree=0.8, random_state=RANDOM_STATE,
                          n_jobs=-1).fit(X_nc, y)
    Xs_nc = X_nc.sample(min(SHAP_SAMPLE, len(X_nc)), random_state=RANDOM_STATE)
    sv_nc = shap.TreeExplainer(xgb_nc).shap_values(Xs_nc)

    plt.figure()
    shap.summary_plot(sv_nc, Xs_nc, show=False, max_display=15)
    plt.tight_layout()
    plt.savefig(OUTDIR / "shap_beeswarm_no_country.png", dpi=120, bbox_inches="tight")
    plt.close()

    shap_imp_nc = pd.Series(np.abs(sv_nc).mean(0), index=Xs_nc.columns).sort_values(ascending=False)
    shap_imp_nc.to_csv(OUTDIR / "shap_importance_no_country.csv", header=["mean_abs_shap"])

    # ------------------------------------------------------------------ findings summary
    ranks = {f: i + 1 for i, f in enumerate(shap_imp.index)}
    gdelt_ranks = sorted(((ranks[f], f) for f in GDELT))
    lines = [
        "# Static inference on IPC Phase 3+ — findings\n",
        f"Dataset: `merged_adm1_wide.parquet` | rows={len(X)} | features={X.shape[1]} "
        f"| areas={groups.nunique()} | target mean={y.mean():.1f}%\n",
        "Models handle missing values natively (no imputation). Validation avoids spatial "
        "leakage (test areas unseen). `wfp_obs_count` excluded (data-density proxy).\n",
        "\n## Model leaderboard — geographic hold-out (unseen adm1 areas)\n",
        "```", metrics_geo.round(3).to_string(), "```\n",
        "\n## Model leaderboard — random hold-out (rows shuffled, same 80/20 size)\n",
        "```", metrics_rnd.round(3).to_string(), "```\n",
        "\nR² gap (random − geographic) — how much spatial autocorrelation inflates scores:\n",
        "```",
        "\n".join(
            f"  {n:24s} {metrics_rnd.loc[n,'R2']:.3f} − {metrics_geo.loc[n,'R2']:.3f} = "
            f"+{metrics_rnd.loc[n,'R2'] - metrics_geo.loc[n,'R2']:+.3f}"
            for n in metrics_geo.index if n in metrics_rnd.index
        ),
        "```\n",
        "\n## Model leaderboard — GroupKFold CV (5-fold by area, out-of-fold)\n",
        "```", metrics_cv.round(3).to_string(), "```\n",
        "\n## Country ablation — GroupKFold CV WITHOUT Country feature\n",
        "```", metrics_nc.round(3).to_string(), "```\n",
        "\nR² drop when Country is removed:\n",
        "```", delta.round(3).to_string(), "```\n",
        "\n## Top drivers — mean(|SHAP|), XGBoost (with Country)\n",
        "```", shap_imp.head(15).round(3).to_string(), "```\n",
        f"\nBest-ranked GDELT media feature: **{gdelt_ranks[0][1]}** at rank "
        f"{gdelt_ranks[0][0]} of {len(shap_imp)}. "
        f"GDELT feature ranks: {[r for r, _ in gdelt_ranks]}.\n",
        "\nDriver group of each top-15 SHAP feature:\n",
        "```",
        "\n".join(f"  {f:42s} {group_of(f)}" for f in shap_imp.head(15).index),
        "```\n",
        "\n## Per-country R2 — geographic hold-out (sorted by XGBoost)\n",
        "```",
        pivot_r2_geo.loc[xgb_order_geo.index][["xgboost", "random_forest", "lightgbm", "baseline_country_mean"]]
                    .round(3).to_string(),
        "```\n",
        "\n## Per-country MAE — geographic hold-out (sorted by XGBoost)\n",
        "```",
        pivot_mae_geo.loc[xgb_order_geo.index][["xgboost", "random_forest", "lightgbm", "baseline_country_mean"]]
                     .round(2).to_string(),
        "```\n",
    ]
    (OUTDIR / "README.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"\nDone. Artifacts written to {OUTDIR}")
    for p in sorted(OUTDIR.iterdir()):
        print("  ", p.name)


if __name__ == "__main__":
    main()
