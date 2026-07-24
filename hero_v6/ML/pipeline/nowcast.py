"""
Nowcasting — estimate an area's CURRENT IPC Phase 3+ from its last assessment plus latest drivers.

The bar to beat is persistence (carry the last known IPC forward), which is strong because IPC is
highly autoregressive — so the real question is whether the drivers add skill on top of persistence.

Pipeline for one dataset (imputed | unimputed):
  1. build the autoregressive panel (lags + driver changes), current-only and with-projections
  2. rolling-origin (walk-forward) backtest -> leaderboard, skill vs persistence, skill decomposition
  3. pred-vs-actual + change-direction scatter + SHAP (by data source)
  4. localization: global / regional / local / 2 cluster training scopes

Validation is a rolling-origin expanding backtest: for each origin, train on all windows before it
and test the next TEST_WINDOW_MONTHS — never using the future to predict the past.

Run:  python nowcast.py imputed        (or: unimputed)
"""

import sys
import config  # first — MKL guards
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import features as F
from config import (COUNTRY_COL, CLUSTER_SCOPE_NAMES, SHAP_SAMPLE_SIZE, RANDOM_STATE, HEADLINE_MODEL,
                    REGIONS, BACKTEST_ORIGINS, TEST_WINDOW_MONTHS, MIN_ROWS_FOR_LOCAL_MODEL,
                    MIN_ROWS_TO_REPORT_NOWCAST as MIN_ROWS_TO_REPORT,
                    DATASETS, make_models, results_dir)

ROUND = "nowcast"
PRIMARY_CELL = "train_all|eval_current"   # nowcast reality (observed windows), using all training data


# ============================================================ backtest core
def fit_predict_fold(features, target, panel, train_mask, test_mask) -> dict:
    """Fit persistence + every (feature_set, model) on the train fold; predict the test fold.

    Returns {(feature_set, model): array of length n, NaN outside the test fold}.
    """
    n = len(target)
    last_known = panel["lag1"].values
    predictions = {("persistence", ""): np.full(n, np.nan)}
    predictions[("persistence", "")][test_mask] = (
        pd.Series(last_known[test_mask]).fillna(target.values[train_mask].mean()).values)
    for feature_set, cols in F.feature_sets(features).items():
        for name, model in make_models().items():
            model.fit(features.loc[train_mask, cols], target.loc[train_mask])
            fold = np.full(n, np.nan)
            fold[test_mask] = model.predict(features.loc[test_mask, cols])
            predictions[(feature_set, name)] = fold
    return predictions


def rolling_backtest(features, target, panel):
    """Expanding-window rolling-origin backtest; merge each fold's out-of-sample predictions."""
    when = panel["From"].values
    tested = np.zeros(len(target), bool)
    merged = None
    for origin in BACKTEST_ORIGINS:
        start = np.datetime64(pd.Timestamp(origin))
        end = np.datetime64(pd.Timestamp(origin) + pd.DateOffset(months=TEST_WINDOW_MONTHS))
        train_mask = when < start
        test_mask = (when >= start) & (when < end)
        if test_mask.sum() == 0 or train_mask.sum() == 0:
            continue
        tested |= test_mask
        fold = fit_predict_fold(features, target, panel, train_mask, test_mask)
        if merged is None:
            merged = {key: arr.copy() for key, arr in fold.items()}
        else:
            for key, arr in fold.items():
                filled = ~np.isnan(arr)
                merged[key][filled] = arr[filled]
    return merged, tested


def score_cell(target, predictions, selection, cell_name) -> pd.DataFrame:
    """Score every series on `selection`; skill = MAE improvement over persistence."""
    y = target.values[selection]
    base = F.regression_scores(y, predictions[("persistence", "")][selection])
    rows = [{"cell": cell_name, "feature_set": "-", "model": "persistence",
             **base, "skill_vs_persistence": 0.0, "n": int(selection.sum())}]
    for (feature_set, model), arr in predictions.items():
        if feature_set == "persistence":
            continue
        s = F.regression_scores(y, arr[selection])
        s["skill_vs_persistence"] = (base["MAE"] - s["MAE"]) / base["MAE"]
        rows.append({"cell": cell_name, "feature_set": feature_set, "model": model,
                     **s, "n": int(selection.sum())})
    return pd.DataFrame(rows)


def skill_decomposition(primary: pd.DataFrame) -> pd.DataFrame:
    """Where does skill come from: autoregressive -> + driver levels -> + driver changes."""
    def r2(feature_set, model):
        row = primary[(primary.feature_set == feature_set) & (primary.model == model)]
        return float(row.iloc[0]["R2"]) if len(row) else np.nan
    rows = [{"model": m,
             "autoregressive_R2": r2("autoregressive", m),
             "nowcast_R2": r2("nowcast", m),
             "nowcast_change_R2": r2("nowcast_change", m)}
            for m in ("xgboost", "random_forest", "lightgbm", "decision_tree")]
    return pd.DataFrame(rows)


# ============================================================ per-country & localization
def per_country_table(target, predictions, selection, panel) -> pd.DataFrame:
    """Per-country R²/MAE/n for each (feature_set, model) + persistence, on the primary cell."""
    country = panel[COUNTRY_COL].values
    rows = []
    for name in np.unique(country[selection]):
        mask = selection & (country == name)
        if mask.sum() < MIN_ROWS_TO_REPORT:
            continue
        y = target.values[mask]
        for (feature_set, model), arr in predictions.items():
            if feature_set == "persistence":
                continue
            rows.append({"Country": name, "feature_set": feature_set, "model": model,
                         **F.regression_scores(y, arr[mask]), "n": int(mask.sum())})
        rows.append({"Country": name, "feature_set": "-", "model": "persistence",
                     **F.regression_scores(y, predictions[("persistence", "")][mask]),
                     "n": int(mask.sum())})
    return pd.DataFrame(rows)


def _scope_predictions(features, target, panel, cols, membership, is_current):
    """Pool rolling-origin predictions from a per-subgroup model (region / country / cluster).

    For each subgroup clearing MIN_ROWS_FOR_LOCAL_MODEL rows, run the walk-forward backtest restricted
    to that subgroup (train on its past rows, predict its current rows). Rows in too-small subgroups
    stay NaN. `membership` is a per-row label array.
    """
    predictions = np.full(len(target), np.nan)
    for value in pd.unique(membership[pd.notna(membership)]):
        mask = membership == value
        if mask.sum() >= MIN_ROWS_FOR_LOCAL_MODEL:
            predictions[mask] = F.rolling_origin_predictions(
                features, target, panel, cols, mask, mask & is_current)[mask]
    return predictions


def localization_scopes(features, target, panel):
    """Per-country + overall metrics under global / regional / local / cluster scopes (rolling-origin).

    regional groups by the 6-region map; local by country; cluster by each data-driven cluster scheme
    present in `panel` (see config.CLUSTER_SCOPES). Local and cluster subgroups need
    MIN_ROWS_FOR_LOCAL_MODEL rows to be fitted at all. Returns (per_country_scope_df, overall_df).
    """
    cols = F.feature_sets(features)["nowcast"]
    country = panel[COUNTRY_COL].values
    is_current = panel["is_projection"].values == 0     # evaluate only on observed current windows
    all_rows = np.ones(len(target), bool)

    preds = {"global": F.rolling_origin_predictions(features, target, panel, cols, all_rows, is_current)}

    # regional: no data floor (regions are always large enough)
    regional = np.full(len(target), np.nan)
    for members in REGIONS.values():
        mask = np.isin(country, members)
        if mask.any():
            regional[mask] = F.rolling_origin_predictions(
                features, target, panel, cols, mask, mask & is_current)[mask]
    preds["regional"] = regional
    preds["local"] = _scope_predictions(features, target, panel, cols, country, is_current)
    for name in CLUSTER_SCOPE_NAMES:
        if name in panel.columns:
            preds[name] = _scope_predictions(features, target, panel, cols,
                                             panel[name].values, is_current)

    scope_dfs = {s: F.score_by_country(target, p, country, min_rows=MIN_ROWS_TO_REPORT)
                 for s, p in preds.items()}
    return F.combine_scopes(scope_dfs), F.overall_scope_metrics(target, preds, country)


# ============================================================ plots
def plot_pred_vs_actual(target, predictions, selection, outdir):
    for model in ("decision_tree", "random_forest", "xgboost", "lightgbm"):
        arr = predictions[("nowcast", model)]
        sel = selection & ~np.isnan(arr)
        r2 = F.regression_scores(target.values[sel], arr[sel])["R2"]
        fig, ax = plt.subplots(figsize=(5, 5))
        ax.scatter(target.values[sel], arr[sel], s=8, alpha=0.25)
        ax.plot([0, 100], [0, 100], "r--", lw=1)
        ax.set_xlim(0, 100); ax.set_ylim(0, 100)
        ax.set_xlabel("actual phase 3+ %"); ax.set_ylabel("nowcast phase 3+ %")
        ax.set_title(f"nowcast {model}  (backtest OOF, R²={r2:.3f})")
        fig.tight_layout(); fig.savefig(outdir / f"pred_vs_actual_{model}.png", dpi=120)
        plt.close(fig)


def plot_change_scatter(target, predictions, panel, selection, outdir) -> float:
    """Predicted vs actual CHANGE since the last assessment (the honest hard part of nowcasting)."""
    last_known = panel["lag1"].values
    arr = predictions[("nowcast_change", "xgboost")]
    sel = selection & ~np.isnan(arr) & ~np.isnan(last_known)
    actual_change = target.values[sel] - last_known[sel]
    predicted_change = arr[sel] - last_known[sel]
    r = float(np.corrcoef(actual_change, predicted_change)[0, 1])
    lim = max(20, np.nanpercentile(np.abs(actual_change), 99))
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.scatter(actual_change, predicted_change, s=8, alpha=0.25)
    ax.plot([-lim, lim], [-lim, lim], "r--", lw=1)
    ax.axhline(0, color="grey", lw=0.5); ax.axvline(0, color="grey", lw=0.5)
    ax.set_xlim(-lim, lim); ax.set_ylim(-lim, lim)
    ax.set_xlabel("actual change since last (pp)"); ax.set_ylabel("predicted change (pp)")
    ax.set_title(f"nowcast XGBoost — change captured (r={r:.2f})")
    fig.tight_layout(); fig.savefig(outdir / "change_scatter.png", dpi=120)
    plt.close(fig)
    return r


def write_readme(dataset, panel_current, panel_proj, backtest, decomposition,
                 shap_by_source, change_r, scope_df, overall, outdir):
    def cell(df, name):
        return (df[df.cell == name][["feature_set", "model", "MAE", "R2", "skill_vs_persistence"]]
                .sort_values("R2", ascending=False).round(3).to_string(index=False))
    scope_df = scope_df.copy(); scope_df["best_scope"] = scope_df.apply(F.best_scope, axis=1)
    lines = [
        f"# Nowcasting — findings ({dataset})\n",
        f"Dataset: `{DATASETS[dataset].name}` | current windows: {len(panel_current)} | "
        f"with projections: {len(panel_proj)} ({int(panel_proj['is_projection'].sum())} projection). "
        f"Drivers only. Baseline = persistence (carry last IPC forward).\n",
        "\n## Rolling backtest — train_all | eval_current (PRIMARY)\n",
        "```", cell(backtest, PRIMARY_CELL), "```\n",
        "\n## Skill decomposition — autoregressive -> + driver levels -> + driver changes (R²)\n",
        "```", decomposition.round(3).to_string(index=False), "```\n",
        f"\nChange-direction correlation (predicted vs actual change since last): r = {change_r:.2f}.\n",
        "\n## SHAP by data source (nowcast_change XGBoost)\n",
        "```", shap_by_source.round(3).to_string(), "```\n",
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


# ============================================================ main
def main(dataset: str):
    outdir = results_dir(ROUND, dataset)
    print(f"[nowcast / {dataset}] loading {DATASETS[dataset].name}")
    df = F.load_dataset(dataset)
    panel_current = F.build_panel(df, include_projections=False)
    panel_proj = F.build_panel(df, include_projections=True)
    Xc, yc = F.make_features(panel_current)
    Xa, ya = F.make_features(panel_proj)
    is_projection = panel_proj["is_projection"].values.astype(bool)
    print(f"  current windows={len(Xc)}  with projections={len(Xa)} "
          f"({int(is_projection.sum())} projection)")

    pred_current, tested_current = rolling_backtest(Xc, yc, panel_current)
    pred_proj, tested_proj = rolling_backtest(Xa, ya, panel_proj)
    primary_mask = tested_proj & ~is_projection

    backtest = pd.concat([
        score_cell(yc, pred_current, tested_current, "train_cur|eval_current"),
        score_cell(ya, pred_proj, primary_mask, PRIMARY_CELL),
        score_cell(ya, pred_proj, tested_proj & is_projection, "train_all|eval_projection"),
    ], ignore_index=True)
    backtest.to_csv(outdir / "metrics_backtest.csv", index=False)

    primary = backtest[backtest.cell == PRIMARY_CELL]
    (primary[["feature_set", "model", "MAE", "R2", "skill_vs_persistence"]]
     .sort_values("skill_vs_persistence", ascending=False)
     .to_csv(outdir / "skill_vs_persistence.csv", index=False))
    decomposition = skill_decomposition(primary)
    decomposition.to_csv(outdir / "driver_contribution.csv", index=False)
    print(primary[["feature_set", "model", "R2", "skill_vs_persistence"]]
          .sort_values("skill_vs_persistence", ascending=False).head(6).round(3).to_string(index=False))

    pct = per_country_table(ya, pred_proj, primary_mask, panel_proj)
    pct.to_csv(outdir / "metrics_per_country.csv", index=False)
    F.plot_skill_vs_baseline(
        pct[(pct.feature_set == "nowcast_change") & (pct.model == HEADLINE_MODEL)].set_index("Country"),
        pct[pct.model == "persistence"].set_index("Country"),
        "Nowcast", "persistence", outdir / "skill_vs_baseline.png")
    plot_pred_vs_actual(ya, pred_proj, primary_mask, outdir)
    change_r = plot_change_scatter(ya, pred_proj, panel_proj, primary_mask, outdir)

    cols = F.feature_sets(Xa)["nowcast_change"]
    xgb = make_models()[HEADLINE_MODEL].fit(Xa[cols], ya)
    sample = Xa[cols].sample(min(SHAP_SAMPLE_SIZE, len(Xa)), random_state=RANDOM_STATE)
    _, by_source = F.save_shap(xgb, sample, "Nowcast — SHAP by data source (XGBoost)", outdir)

    scope_df, overall = localization_scopes(Xa, ya, panel_proj)
    scope_df.to_csv(outdir / "metrics_scopes.csv")
    overall.to_csv(outdir / "metrics_scopes_overall.csv")
    F.plot_scopes(scope_df, "Nowcast", outdir / "scope_comparison.png")
    persistence_mae = pct[pct.model == "persistence"].set_index("Country")["MAE"]
    F.plot_scopes_skill_box(scope_df, persistence_mae, "Nowcast", outdir / "scope_box.png")
    print("Localization:", F.scope_summary(scope_df))
    print("Overall by scope:\n" + overall.to_string())

    write_readme(dataset, panel_current, panel_proj, backtest, decomposition,
                 by_source, change_r, scope_df, overall, outdir)
    print(f"Done -> {outdir}")


if __name__ == "__main__":
    dataset = sys.argv[1] if len(sys.argv) > 1 else "imputed"
    assert dataset in DATASETS, f"dataset must be one of {list(DATASETS)}"
    main(dataset)
