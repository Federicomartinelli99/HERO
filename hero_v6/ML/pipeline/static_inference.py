"""
Static inference — predict IPC Phase 3+ from instantaneous drivers (cross-sectional; no time).

Pipeline for one dataset (imputed | unimputed):
  1. build features (drivers + seasonality, drivers only)
  2. GroupKFold-by-area out-of-fold predictions -> model leaderboard + pred-vs-actual + per-country
  3. explainability: impurity importance + SHAP (XGBoost), aggregated by data source
  4. localization: the same round at five training scopes (global / regional / local / 2 clusters)

Validation is GroupKFold by area only: a random split would leak because IPC is spatially and
temporally autocorrelated (an area recurs across windows; neighbours resemble each other), so
holding out whole areas is the honest test of generalization to unseen areas.

Run:  python static_inference.py imputed        (or: unimputed)
"""

import sys
import config  # first — MKL guards
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.model_selection import GroupKFold

import features as F
from config import (AREA_COL, COUNTRY_COL, CLUSTER_SCOPES, N_SPLITS, SHAP_SAMPLE_SIZE, RANDOM_STATE,
                    HEADLINE_MODEL, REGIONS, MIN_ROWS_FOR_LOCAL_MODEL, MIN_AREAS_FOR_LOCAL_MODEL,
                    MIN_ROWS_TO_REPORT_STATIC as MIN_ROWS_TO_REPORT,
                    DATASETS, make_models, results_dir)

ROUND = "static_inference"


def leaderboard(features, target, groups, country):
    """Out-of-fold GroupKFold predictions for the per-country-mean baseline + every model."""
    oof = {name: F.groupkfold_predictions(features, target, groups, estimator)
           for name, estimator in make_models().items()}
    baseline = np.full(len(target), np.nan)
    for train_idx, test_idx in GroupKFold(N_SPLITS).split(features, target, groups):
        baseline[test_idx] = F.country_mean_baseline(
            country.iloc[train_idx], target.iloc[train_idx], country.iloc[test_idx])
    oof["baseline_country_mean"] = baseline
    table = (pd.DataFrame({name: F.regression_scores(target, pred) for name, pred in oof.items()})
             .T[["MAE", "RMSE", "R2"]].sort_values("R2", ascending=False))
    return oof, table


def per_country_table(target, oof, country) -> pd.DataFrame:
    """Long table of per-country R²/MAE/n for every model (from the out-of-fold predictions)."""
    rows = []
    for name, pred in oof.items():
        scored = F.score_by_country(target, pred, country, min_rows=MIN_ROWS_TO_REPORT)
        for name_country, row in scored.iterrows():
            rows.append({"Country": name_country, "model": name,
                         "R2": row.R2, "MAE": row.MAE, "n": int(row.n)})
    return pd.DataFrame(rows)


def _scope_predictions(features, target, groups, xgb, membership):
    """Pool GroupKFold-by-area OOF predictions from a per-subgroup model.

    For each subgroup (a region, a country, or a cluster) that clears the data floor, fit within that
    subgroup's rows with whole-area hold-out, and place its OOF predictions back. Rows whose subgroup
    is too small stay NaN. `membership` is a per-row label array (region / country / cluster).
    """
    predictions = np.full(len(target), np.nan)
    for value in pd.unique(membership[pd.notna(membership)]):
        mask = membership == value
        enough_rows = mask.sum() >= MIN_ROWS_FOR_LOCAL_MODEL
        enough_areas = groups.iloc[np.where(mask)[0]].nunique() >= MIN_AREAS_FOR_LOCAL_MODEL
        if enough_rows and enough_areas:
            predictions[mask] = F.groupkfold_predictions(features, target, groups, xgb, mask)[mask]
    return predictions


def localization_scopes(features, target, groups, country, global_oof, clusters=None):
    """Per-country + overall metrics under global / regional / local / cluster scopes (XGBoost, GKF).

    global   = the full OOF (all countries).   regional = one model per 6-region group.
    local    = one model per country.          cluster  = one model per data-driven cluster, one scope
    per entry in `clusters` (name -> per-row membership array). Regional has no data floor; local and
    cluster require MIN_ROWS_FOR_LOCAL_MODEL rows and MIN_AREAS_FOR_LOCAL_MODEL areas to fit a
    defensible model. Returns (per_country_scope_df, overall_df).
    """
    xgb = make_models()[HEADLINE_MODEL]
    preds = {"global": np.asarray(global_oof, dtype=float)}

    # regional: no floor (regions are always large enough); reuse the pooling helper is overkill here.
    regional = np.full(len(target), np.nan)
    for members in REGIONS.values():
        mask = np.isin(country, members)
        if mask.any():
            regional[mask] = F.groupkfold_predictions(features, target, groups, xgb, mask)[mask]
    preds["regional"] = regional
    preds["local"] = _scope_predictions(features, target, groups, xgb, country)
    for name, membership in (clusters or {}).items():
        preds[name] = _scope_predictions(features, target, groups, xgb, membership)

    scope_dfs = {s: F.score_by_country(target, p, country, min_rows=MIN_ROWS_TO_REPORT)
                 for s, p in preds.items()}
    return F.combine_scopes(scope_dfs), F.overall_scope_metrics(target, preds, country)


def plot_pred_vs_actual(target, oof, table, outdir):
    """One predicted-vs-actual scatter per model, from the out-of-fold predictions."""
    for name, pred in oof.items():
        if name == "baseline_country_mean":
            continue
        fig, ax = plt.subplots(figsize=(5, 5))
        ax.scatter(target, pred, s=8, alpha=0.25)
        ax.plot([0, 100], [0, 100], "r--", lw=1)
        ax.set_xlim(0, 100); ax.set_ylim(0, 100)
        ax.set_xlabel("actual phase 3+ %"); ax.set_ylabel("predicted phase 3+ %")
        ax.set_title(f"{name}  (GroupKFold OOF, R²={table.loc[name, 'R2']:.3f})")
        fig.tight_layout(); fig.savefig(outdir / f"pred_vs_actual_{name}.png", dpi=120)
        plt.close(fig)


def impurity_importance(features, target, outdir):
    """RandomForest impurity (Gini) importance — a quick complement to SHAP."""
    models = make_models()
    rf = models["random_forest"].fit(features, target)
    importance = pd.Series(rf.feature_importances_, index=features.columns).sort_values(ascending=False)
    importance.to_csv(outdir / "impurity_importance.csv", header=["importance"])
    top = importance.head(15)[::-1]
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.barh(top.index, top.values, color="#4C72B0")
    ax.set_title("RandomForest impurity importance (top 15)")
    ax.set_xlabel("importance")
    fig.tight_layout(); fig.savefig(outdir / "impurity_importance.png", dpi=120)
    plt.close(fig)


def write_readme(dataset, features, target, table, importance, by_source, scope_df, overall, outdir):
    scope_df = scope_df.copy()
    scope_df["best_scope"] = scope_df.apply(F.best_scope, axis=1)
    lines = [
        f"# Static inference — findings ({dataset})\n",
        f"Dataset: `{DATASETS[dataset].name}` | rows={len(features)} | features={features.shape[1]} "
        f"| target mean={target.mean():.1f}% | drivers only (no country, no coordinates)\n",
        "Validation: GroupKFold(5) by area (out-of-fold) — test areas unseen.\n",
        "\n## Model leaderboard (GroupKFold OOF)\n",
        "```", table.round(3).to_string(), "```\n",
        "\n## Top drivers — mean(|SHAP|), XGBoost\n",
        "```", importance.head(15).round(3).to_string(), "```\n",
        "\n## SHAP by data source\n",
        "```", by_source.round(3).to_string(), "```\n",
        "\n## Localization — overall by scope (pooled over each scope's scored rows;"
        " `*_vs_global` = global model on those same rows)\n",
        "```", overall.to_string(), "```\n",
        "\n## Localization — per country (" + F.scope_summary(scope_df) + ")\n",
        "```",
        scope_df[[f"R2_{s}" for s in F.SCOPES if f"R2_{s}" in scope_df.columns] + ["best_scope"]]
        .sort_values("R2_global", ascending=False).round(3).to_string(),
        "```\n",
    ]
    (outdir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main(dataset: str):
    outdir = results_dir(ROUND, dataset)
    print(f"[static_inference / {dataset}] loading {DATASETS[dataset].name}")
    df = F.load_dataset(dataset)
    features, target, meta = F.build_features(df)
    groups, country = meta[AREA_COL], meta[COUNTRY_COL].values
    clusters = {name: meta[name].values for name in CLUSTER_SCOPES if name in meta.columns}
    print(f"  rows={len(features)}  features={features.shape[1]}  areas={groups.nunique()}  "
          f"target mean={target.mean():.1f}%")

    oof, table = leaderboard(features, target, groups, meta[COUNTRY_COL])
    table.to_csv(outdir / "metrics_cv.csv")
    print(table.round(3).to_string())

    plot_pred_vs_actual(target, oof, table, outdir)
    pct = per_country_table(target, oof, country)
    pct.to_csv(outdir / "metrics_per_country.csv", index=False)
    F.plot_skill_vs_baseline(
        pct[pct.model == HEADLINE_MODEL].set_index("Country"),
        pct[pct.model == "baseline_country_mean"].set_index("Country"),
        "Static inference", "country-mean", outdir / "skill_vs_baseline.png")
    impurity_importance(features, target, outdir)

    xgb = make_models()[HEADLINE_MODEL].fit(features, target)
    sample = features.sample(min(SHAP_SAMPLE_SIZE, len(features)), random_state=RANDOM_STATE)
    importance, by_source = F.save_shap(
        xgb, sample, "Static inference — SHAP by data source (XGBoost)", outdir)

    scope_df, overall = localization_scopes(
        features, target, groups, country, oof[HEADLINE_MODEL], clusters)
    scope_df.to_csv(outdir / "metrics_scopes.csv")
    overall.to_csv(outdir / "metrics_scopes_overall.csv")
    F.plot_scopes(scope_df, "Static inference", outdir / "scope_comparison.png")
    print("\nLocalization:", F.scope_summary(scope_df))
    print("Overall by scope:\n" + overall.to_string())

    write_readme(dataset, features, target, table, importance, by_source, scope_df, overall, outdir)
    print(f"Done -> {outdir}")


if __name__ == "__main__":
    dataset = sys.argv[1] if len(sys.argv) > 1 else "imputed"
    assert dataset in DATASETS, f"dataset must be one of {list(DATASETS)}"
    main(dataset)
