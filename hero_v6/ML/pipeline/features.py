"""
Shared feature engineering, scoring, and validation helpers used by both rounds.

- Static features  : `build_features`  (drivers + cyclical seasonality)
- Nowcast features : `build_panel` -> `make_features` (adds autoregressive lags + driver changes)
- Explainability   : `driver_source` groups a feature into its data source for SHAP-by-source
- Validation       : `groupkfold_predictions` (static, by area) and
                     `rolling_origin_predictions` (nowcast, walk-forward)
- Localization     : `score_by_country`, `combine_scopes`, `best_scope`, `plot_scopes`
"""

import config  # first — sets the OpenMP/MKL guards before numpy is imported

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.lines as mlines
import shap
from sklearn.base import clone
from sklearn.model_selection import GroupKFold
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from config import (TARGET, AREA_COL, COUNTRY_COL, CLUSTER_SCOPES, CLUSTER_JOIN_COL, DRIVERS, N_SPLITS,
                    BACKTEST_ORIGINS, TEST_WINDOW_MONTHS, MIN_TRAIN_ROWS_PER_FOLD,
                    make_models, HEADLINE_MODEL, DATASETS, CLUSTERS_PATH)

# The training scopes compared in localization, in a fixed order (colour-stable across charts).
SCOPES = ["global", "regional", "local", "cluster_kmeans", "cluster_hierarchical"]
SCOPE_COLORS = {"global": "#adb5bd", "regional": "#4895ef", "local": "#f3722c",
                "cluster_kmeans": "#2a9d8f", "cluster_hierarchical": "#9b5de5"}

# Autoregressive features (nowcast only): last value, one before, recent trend.
AR_FEATURES = ["lag1", "lag2", "recent_trend"]
SEASONALITY = ["month_sin", "month_cos"]           # not differenced when building driver changes
# IPC re-classifies a window across analyses; prefer the authoritative "current" reading.
VALIDITY_RANK = {"current": 0, "first projection": 1, "second projection": 2}


# ============================================================ loading
def load_dataset(dataset: str) -> pd.DataFrame:
    """Read one dataset parquet, drop no-analysis rows, and attach the cluster columns (by area code).

    Rows with `phase_all_number` <= 0 (or NaN) have no analysed population — no IPC analysis existed
    for that area-window, so every phase count is a mechanical 0 and `phase_3plus_percentage` = 0 is a
    *phantom* observation, not a true "0% in crisis". Left in, these fake zeros contaminate training
    and (worse) become lag values, manufacturing huge spurious window-to-window swings (e.g. Yemen
    showed ±50pp jumps that were entirely these rows). They are dropped here so both rounds see only
    genuine observations.

    Clusters are a separate, static per-adm1 table, so this join applies identically regardless of
    imputation — both cluster scopes end up available for both datasets. It is keyed on
    `CLUSTER_JOIN_COL` (adm1_pcode), which is present at both levels, so an adm2 row inherits its parent
    adm1's cluster (adm2 areas whose parent adm1 isn't in the table stay NaN — handled gracefully).
    """
    df = pd.read_parquet(DATASETS[dataset])
    df = df[df["phase_all_number"].fillna(0) > 0].copy()      # drop no-analysis (phantom) rows
    clusters = pd.read_csv(CLUSTERS_PATH, sep=";", usecols=[CLUSTER_JOIN_COL, *CLUSTER_SCOPES.values()])
    clusters = clusters.rename(columns={v: k for k, v in CLUSTER_SCOPES.items()})
    return df.merge(clusters, on=CLUSTER_JOIN_COL, how="left")


# ============================================================ static features
def build_features(df: pd.DataFrame):
    """Return (features, target, meta) for rows with an observed target.

    `features` = the engineered drivers present + cyclical seasonality (drivers only — no country,
    no coordinates). `meta` carries Country + area code for grouping/reporting, never as features.
    NaN is left intact (tree models handle it natively).
    """
    df = df[df[TARGET].notna()].copy()
    features = pd.DataFrame(index=df.index)
    for col in DRIVERS:
        if col in df.columns:
            series = df[col]
            # some engineered columns are pandas nullable Float64 (pd.NA); cast to plain float64
            # (np.nan) — modelling is identical, but SHAP's colouring mishandles pd.NA.
            features[col] = (series.to_numpy(dtype="float64", na_value=np.nan)
                             if str(series.dtype) == "Float64" else series)
    month = pd.to_datetime(df["From"]).dt.month
    features["month_sin"] = np.sin(2 * np.pi * month / 12)   # cyclical: no absolute year
    features["month_cos"] = np.cos(2 * np.pi * month / 12)

    assert not [c for c in features.columns if "phase_" in c], "leakage: phase_* in features"
    meta = pd.DataFrame({COUNTRY_COL: df[COUNTRY_COL].values,
                         AREA_COL: df[AREA_COL].astype(str).values})
    for name in CLUSTER_SCOPES:                          # carried for the cluster scopes, never features
        if name in df.columns:
            meta[name] = df[name].values
    target = df[TARGET].astype(float)
    return (features.reset_index(drop=True), target.reset_index(drop=True),
            meta.reset_index(drop=True))


# ============================================================ nowcast features
def build_panel(df: pd.DataFrame, include_projections: bool) -> pd.DataFrame:
    """One row per (area, window `From`), with autoregressive features added per area.

    Windows are deduplicated preferring current > first projection > second projection, so each
    (area, window) keeps one authoritative IPC value. `include_projections` toggles whether
    projection windows are added at all.
    """
    panel = df[df[TARGET].notna()].copy()
    if not include_projections:
        panel = panel[panel["Validity period"] == "current"].copy()
    panel["From"] = pd.to_datetime(panel["From"])
    panel["Date of analysis"] = pd.to_datetime(panel["Date of analysis"], errors="coerce")
    panel["vp_rank"] = panel["Validity period"].map(VALIDITY_RANK).fillna(9)
    panel = panel.sort_values([AREA_COL, "From", "vp_rank", "Date of analysis"])
    panel = panel.drop_duplicates([AREA_COL, "From"], keep="first")      # authoritative value/window
    panel = panel.sort_values([AREA_COL, "From"]).reset_index(drop=True)

    by_area = panel.groupby(AREA_COL, sort=False)
    panel["lag1"] = by_area[TARGET].shift(1)                     # last known IPC
    panel["lag2"] = by_area[TARGET].shift(2)                     # the one before
    panel["recent_trend"] = panel["lag1"] - panel["lag2"]       # recent momentum
    panel["is_projection"] = (panel["Validity period"] != "current").astype(int)
    return panel


def make_features(panel: pd.DataFrame):
    """Nowcast model matrix: drivers + seasonality + AR features + per-area driver changes."""
    features, target, _ = build_features(panel)                  # drivers + seasonality (aligned)
    features = features.reset_index(drop=True)
    ar = panel[AR_FEATURES].reset_index(drop=True)
    features = pd.concat([features, ar], axis=1)

    # driver changes: difference each continuous driver vs the area's previous window
    continuous = [c for c in features.columns if c not in AR_FEATURES + SEASONALITY]
    changes = features[continuous].copy()
    changes[AREA_COL] = panel[AREA_COL].values                   # panel is sorted by (area, From)
    changes = changes.groupby(AREA_COL, sort=False).diff()       # NaN at each area's first window
    changes.columns = ["change_" + c for c in continuous]
    features = pd.concat([features, changes], axis=1)
    return features, target.reset_index(drop=True)


def feature_sets(features: pd.DataFrame) -> dict:
    """Nested sets that decompose where nowcast skill comes from.

    persistence (AR only) ⊂ nowcast (+ driver levels) ⊂ nowcast_change (+ driver changes);
    plus `drivers_only` (drivers + seasonality, no AR) to isolate the exogenous signal.
    """
    change_cols = [c for c in features.columns if c.startswith("change_")]
    core = [c for c in features.columns if c not in change_cols]     # drivers + seasonality + AR
    return {
        "autoregressive": [c for c in core if c in AR_FEATURES],     # AR terms only
        "drivers_only":   [c for c in core if c not in AR_FEATURES], # drivers + seasonality, no AR
        "nowcast":        core,                                       # AR + driver levels
        "nowcast_change": list(features.columns),                     # + driver changes
    }


# ============================================================ explainability
SOURCE_COLORS = {
    "persistence": "#6c757d", "seasonality": "#8ecae6", "conflict": "#d00000",
    "displacement": "#e07b39", "rain": "#0077b6", "vegetation": "#2d9e6b",
    "prices": "#9d4edd", "media": "#adb5bd", "other": "#495057",
}


def driver_source(feature: str) -> str:
    """Map a feature (including AR terms and `change_` deltas) to its data source."""
    name = feature[len("change_"):] if feature.startswith("change_") else feature
    if name in AR_FEATURES:
        return "persistence"
    if name.startswith("month_"):
        return "seasonality"
    if name.startswith("acled"):
        return "conflict"
    if name.startswith("idp"):
        return "displacement"
    if name.startswith("rain"):
        return "rain"
    if name.startswith("ndvi"):
        return "vegetation"
    if name.startswith("wfp"):
        return "prices"
    if name.startswith("gdelt"):
        return "media"
    return "other"


def shap_by_source(shap_importance: pd.Series) -> pd.Series:
    """Sum per-feature mean|SHAP| into data-source groups."""
    grouped = shap_importance.groupby(shap_importance.index.map(driver_source)).sum()
    return grouped.sort_values(ascending=False)


def save_shap(model, features_sample: pd.DataFrame, title: str, outdir):
    """Fit-agnostic SHAP report: beeswarm + importance CSV + by-source bar. `model` already fitted."""
    shap_values = shap.TreeExplainer(model).shap_values(features_sample)
    plt.figure()
    shap.summary_plot(shap_values, features_sample, show=False, max_display=15)
    plt.tight_layout(); plt.savefig(outdir / "shap_beeswarm.png", dpi=120, bbox_inches="tight")
    plt.close()

    importance = pd.Series(np.abs(shap_values).mean(0),
                           index=features_sample.columns).sort_values(ascending=False)
    importance.to_csv(outdir / "shap_importance.csv", header=["mean_abs_shap"])

    by_source = shap_by_source(importance)
    by_source.to_csv(outdir / "shap_by_source.csv", header=["mean_abs_shap"])
    order = by_source.sort_values()
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.barh(order.index, order.values, color=[SOURCE_COLORS.get(s, "#888888") for s in order.index])
    for i, v in enumerate(order.values):
        ax.text(v, i, f" {v:.2f}", va="center", fontsize=8)
    ax.set_xlabel("Σ mean|SHAP|  (total contribution)")
    ax.set_title(title, fontsize=10, fontweight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    ax.margins(x=0.12)
    fig.tight_layout(); fig.savefig(outdir / "shap_by_source.png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    return importance, by_source


# ============================================================ scoring
def regression_scores(y_true, y_pred) -> dict:
    return {
        "MAE": mean_absolute_error(y_true, y_pred),
        "RMSE": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "R2": r2_score(y_true, y_pred),
    }


def country_mean_baseline(country_train, y_train, country_eval):
    """Predict each area's country mean, learned on the training fold only (honest baseline)."""
    means = y_train.groupby(country_train).mean()
    return country_eval.map(means).fillna(y_train.mean()).values


# ============================================================ validation
def groupkfold_predictions(features, target, groups, estimator, mask=None) -> np.ndarray:
    """Out-of-fold predictions from GroupKFold by area, optionally within a subset `mask`.

    Every area is held out once, so predictions are for unseen areas. With `mask` (a boolean array)
    only those rows are used — this is how the regional/local localization scopes are scored.
    Returns an array of length len(target), NaN outside the evaluated rows.
    """
    predictions = np.full(len(target), np.nan)
    index = np.arange(len(target)) if mask is None else np.where(mask)[0]
    if len(index) == 0:
        return predictions
    area = groups.iloc[index]
    if area.nunique() < 2:
        return predictions
    splitter = GroupKFold(n_splits=min(N_SPLITS, area.nunique()))
    X, y = features.iloc[index], target.iloc[index]
    for train_idx, test_idx in splitter.split(X, y, area):
        model = clone(estimator)
        model.fit(X.iloc[train_idx], y.iloc[train_idx])
        predictions[index[test_idx]] = model.predict(X.iloc[test_idx])
    return predictions


def rolling_origin_predictions(features, target, panel, cols, train_mask, eval_mask) -> np.ndarray:
    """Walk-forward out-of-sample predictions (HEADLINE_MODEL) within a scope.

    For each origin, train on rows before it (intersected with `train_mask`) and predict the next
    TEST_WINDOW_MONTHS (intersected with `eval_mask`). Skips a fold whose train set is too small to
    fit a full model. Used for the regional/local nowcast scopes.
    """
    when = panel["From"].values
    predictions = np.full(len(target), np.nan)
    for origin in BACKTEST_ORIGINS:
        start = np.datetime64(pd.Timestamp(origin))
        end = np.datetime64(pd.Timestamp(origin) + pd.DateOffset(months=TEST_WINDOW_MONTHS))
        train = (when < start) & train_mask
        test = (when >= start) & (when < end) & eval_mask
        if test.sum() == 0 or train.sum() < MIN_TRAIN_ROWS_PER_FOLD:
            continue
        model = make_models()[HEADLINE_MODEL]
        model.fit(features.loc[train, cols], target.loc[train])
        predictions[test] = model.predict(features.loc[test, cols])
    return predictions


# ============================================================ localization scopes
def score_by_country(target, predictions, country, selection=None, min_rows=30) -> pd.DataFrame:
    """Per-country R²/MAE/n over rows with a finite prediction (optionally within `selection`).

    Countries with fewer than `min_rows` scored rows are dropped (R² unstable on few points). The
    round passes its own floor (static vs nowcast differ; see config.MIN_ROWS_TO_REPORT_*). Indexed
    by Country.
    """
    scored = np.isfinite(predictions)
    if selection is not None:
        scored = scored & selection
    y = target.values if hasattr(target, "values") else target
    rows = []
    for name in np.unique(country[scored]):
        mask = scored & (country == name)
        if mask.sum() < min_rows:
            continue
        rows.append({"Country": name, **regression_scores(y[mask], predictions[mask]),
                     "n": int(mask.sum())})
    return pd.DataFrame(rows).set_index("Country")


def combine_scopes(scope_dfs: dict) -> pd.DataFrame:
    """Merge each scope's per-country table into R2_/MAE_/n_<scope> columns.

    `scope_dfs` maps scope name -> per-country score table (from `score_by_country`); a `None` value
    (a scope that doesn't apply, e.g. missing data) is simply omitted.
    """
    out = None
    for name, df in scope_dfs.items():
        if df is None:
            continue
        part = df.add_suffix(f"_{name}")
        out = part if out is None else out.join(part, how="outer")
    keep = [c for c in out.columns if c.startswith(("R2_", "MAE_", "n_"))]
    return out[keep]


def best_scope(row) -> str:
    candidates = {s: row.get(f"R2_{s}") for s in SCOPES}
    candidates = {s: v for s, v in candidates.items() if pd.notna(v)}
    return max(candidates, key=candidates.get) if candidates else "-"


# Each scope gets its own colour AND marker shape, so the dot charts stay readable in greyscale / for
# colour-vision deficiency (colour alone never carries identity).
SCOPE_MARKERS = {"global": "D", "regional": "o", "local": "^",
                 "cluster_kmeans": "s", "cluster_hierarchical": "v"}


def _scope_dot_panel(ax, table, scopes, order, clip, xlabel):
    """One dot panel: a row per country, one marker per scope, values clipped to `clip` for display."""
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels(order, fontsize=7.5)
    ax.yaxis.set_tick_params(length=0)
    ax.grid(axis="x", lw=0.4, alpha=0.5, zorder=0)
    ax.axvline(0, color="#333333", lw=0.8, zorder=1)
    for i, country in enumerate(order):
        ax.axhline(i, color="#eeeeee", lw=0.6, zorder=0)
        for scope in scopes:
            v = table.loc[country, scope]
            if pd.isna(v):
                continue
            ax.plot(np.clip(v, *clip), i, color=SCOPE_COLORS[scope], marker=SCOPE_MARKERS[scope],
                    markersize=5.5, markeredgewidth=0.4, markeredgecolor="white", linestyle="none",
                    zorder=3)
    ax.set_ylim(-0.8, len(order) - 0.2)
    ax.set_xlabel(xlabel, fontsize=9)
    ax.spines[["top", "right", "left"]].set_visible(False)


def plot_scopes(scope_df: pd.DataFrame, round_name: str, path):
    """Per-country R² & MAE by training scope, as a two-panel dot chart (best country at top).

    One row per country; a coloured, shaped marker per scope (global / regional / local / 2 clusters) —
    a scope's marker is simply absent where there wasn't enough data to fit that model. Left panel = R²
    (clipped at −1 for display), right = MAE (pp). The two panels tell different stories for low-variance
    countries (tiny MAE but hugely negative R²), so both are shown side by side. Replaces the old grouped
    bar chart — dots read more cleanly across many countries and scopes.
    """
    scopes = [s for s in SCOPES if f"R2_{s}" in scope_df.columns]
    r2 = scope_df[[f"R2_{s}" for s in scopes]].copy();  r2.columns = scopes
    mae = scope_df[[f"MAE_{s}" for s in scopes]].copy(); mae.columns = scopes
    order = r2["global"].sort_values(ascending=True).index.tolist()   # best (highest global R²) at top
    if not order:
        return
    fig, (ax_r2, ax_mae) = plt.subplots(
        1, 2, figsize=(13, max(6, len(order) * 0.32)), sharey=True)
    _scope_dot_panel(ax_r2, r2, scopes, order, (-1.0, 1.0), "R²  (clipped at −1)")
    ax_r2.set_xlim(-1.08, 1.05)
    mae_max = float(np.nanmax(mae.values)) * 1.05
    _scope_dot_panel(ax_mae, mae, scopes, order, (0, mae_max), "MAE (pp)  — lower is better")
    ax_mae.set_xlim(0, mae_max)
    ax_r2.set_title("R²", fontsize=9); ax_mae.set_title("MAE (pp)", fontsize=9)
    handles = [mlines.Line2D([], [], color=SCOPE_COLORS[s], marker=SCOPE_MARKERS[s], linestyle="none",
                             markersize=6, label=s) for s in scopes]
    fig.legend(handles=handles, loc="lower center", ncol=len(scopes), fontsize=8, frameon=True,
               framealpha=0.9, bbox_to_anchor=(0.5, -0.01))
    fig.suptitle(f"{round_name} — per-country R² & MAE by training scope", fontsize=11,
                 fontweight="bold")
    fig.tight_layout(rect=[0, 0.04, 1, 0.97])
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_scopes_skill(scope_df: pd.DataFrame, baseline_mae, round_name: str, path):
    """Per-country **skill-vs-persistence** & MAE by training scope, as a two-panel dot chart.

    The nowcast twin of `plot_scopes`: the left panel swaps R² for **skill = % MAE improvement over
    persistence**, the honest lens for the operational round. Per-country R² is savage for a persistent,
    low-variance target — the tiny *within*-country variance blows up the R² denominator — so scope
    routing can look terrible in R² while every scope is comfortably beating persistence in absolute
    (MAE) terms. Skill is well-defined there: a marker right of 0 = that scope beats persistence for that
    country. `baseline_mae` is a per-country persistence MAE (Series or dict, indexed by Country); right
    panel = MAE (pp), identical to `plot_scopes`. Best country (highest global skill) at top. This is an
    *additional* plotter — `plot_scopes` (the R²/MAE version) is left in place and unchanged.
    """
    scopes = [s for s in SCOPES if f"MAE_{s}" in scope_df.columns]
    mae = scope_df[[f"MAE_{s}" for s in scopes]].copy(); mae.columns = scopes
    base = pd.Series(dict(baseline_mae)).reindex(mae.index)
    mae = mae[base.notna() & (base > 0)]
    base = base.loc[mae.index]
    if mae.empty:
        return
    skill = mae.apply(lambda col: 100.0 * (base - col) / base)     # per-scope % improvement vs persistence
    order = skill["global"].sort_values(ascending=True).index.tolist()   # best global skill at top
    if not order:
        return
    fig, (ax_sk, ax_mae) = plt.subplots(
        1, 2, figsize=(13, max(6, len(order) * 0.32)), sharey=True)
    lim = min(60.0, float(np.nanmax(np.abs(skill.values))))
    _scope_dot_panel(ax_sk, skill, scopes, order, (-lim, lim),
                     "skill vs persistence (% MAE improvement; →better)")
    ax_sk.set_xlim(-lim * 1.05, lim * 1.05)
    mae_max = float(np.nanmax(mae.values)) * 1.05
    _scope_dot_panel(ax_mae, mae, scopes, order, (0, mae_max), "MAE (pp)  — lower is better")
    ax_mae.set_xlim(0, mae_max)
    ax_sk.set_title("skill vs persistence (%)", fontsize=9); ax_mae.set_title("MAE (pp)", fontsize=9)
    handles = [mlines.Line2D([], [], color=SCOPE_COLORS[s], marker=SCOPE_MARKERS[s], linestyle="none",
                             markersize=6, label=s) for s in scopes]
    fig.legend(handles=handles, loc="lower center", ncol=len(scopes), fontsize=8, frameon=True,
               framealpha=0.9, bbox_to_anchor=(0.5, -0.01))
    fig.suptitle(f"{round_name} — per-country skill vs persistence & MAE by training scope",
                 fontsize=11, fontweight="bold")
    fig.tight_layout(rect=[0, 0.04, 1, 0.97])
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_skill_vs_baseline(model_scores, baseline_scores, round_name, baseline_label, path):
    """Per-country skill: % MAE improvement of the headline model over its naive baseline.

    The honest per-country question — "is the model worth more than just <baseline>?" — and, unlike R²,
    well-defined even where the target barely varies. Positive (right, teal) = model beats baseline;
    negative (left, orange) = baseline wins. `model_scores` / `baseline_scores` are per-country frames
    indexed by Country with an `MAE` column (already floored by MIN_ROWS_TO_REPORT upstream).
    """
    j = (model_scores[["MAE"]].rename(columns={"MAE": "model"})
         .join(baseline_scores[["MAE"]].rename(columns={"MAE": "base"}), how="inner"))
    j = j[j["base"] > 0]
    j["skill"] = 100 * (j["base"] - j["model"]) / j["base"]
    j = j.sort_values("skill")                      # ascending -> best skill at top of a barh
    if j.empty:
        return
    y = np.arange(len(j))
    colors = ["#2a9d8f" if s > 0 else "#e76f51" for s in j["skill"]]
    fig, ax = plt.subplots(figsize=(7, max(4, len(j) * 0.32)))
    ax.barh(y, j["skill"].values, color=colors, zorder=3)
    for i, s in enumerate(j["skill"].values):
        ax.text(s + (1.2 if s >= 0 else -1.2), i, f"{s:+.0f}%", va="center",
                ha="left" if s >= 0 else "right", fontsize=7)
    ax.axvline(0, color="#333", lw=0.9)
    ax.set_yticks(y); ax.set_yticklabels(j.index, fontsize=8)
    lim = float(np.nanmax(np.abs(j["skill"].values))) * 1.25 + 1
    ax.set_xlim(-lim, lim)
    ax.set_xlabel(f"skill vs {baseline_label}  (% MAE improvement; →better)", fontsize=9)
    beats = int((j["skill"] > 0).sum())
    ax.set_title(f"{round_name} — per-country skill over {baseline_label}  ({beats}/{len(j)} beat it)",
                 fontsize=11, fontweight="bold")
    ax.grid(axis="x", lw=0.4, alpha=0.4, zorder=0)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def scope_summary(scope_df: pd.DataFrame) -> str:
    """One-line count of how often each localized scope beats global (for the README)."""
    df = scope_df.copy()
    parts = []
    for scope in [s for s in SCOPES if s != "global"]:
        col = f"R2_{scope}"
        if col not in df.columns:
            continue
        has = df[df[col].notna()]
        n = int((has[col] > has["R2_global"]).sum())
        parts.append(f"{scope} beats global in {n}/{len(has)}")
    return "; ".join(parts) + " countries (of those with that scope's model)."


def overall_scope_metrics(target, scope_preds: dict, country) -> pd.DataFrame:
    """Pooled (overall) R²/MAE per scope, over the rows each scope actually scored.

    `scope_preds` maps scope name -> per-row prediction array (NaN where unscored); it must include
    `"global"`. Because local/cluster scopes only score their data-rich subgroups, a scope's row
    coverage differs from global's — so for every localized scope we also report the **global model on
    those same rows** (`R2_vs_global`, `MAE_vs_global`) and the gap (`dR2`), the honest apples-to-apples
    "did routing help overall?" number. Coverage is shown as `n_rows` / `n_countries`.
    """
    y = target.values if hasattr(target, "values") else np.asarray(target, dtype=float)
    country = np.asarray(country)
    glob = np.asarray(scope_preds["global"], dtype=float)
    rows = []
    for name in [s for s in SCOPES if s in scope_preds]:
        pred = np.asarray(scope_preds[name], dtype=float)
        m = np.isfinite(pred)
        if m.sum() < 2:
            continue
        s = regression_scores(y[m], pred[m])
        row = {"scope": name, "n_rows": int(m.sum()), "n_countries": int(pd.unique(country[m]).size),
               "R2": round(s["R2"], 3), "MAE": round(s["MAE"], 2)}
        if name != "global":
            gm = m & np.isfinite(glob)
            gs = regression_scores(y[gm], glob[gm])
            row["R2_vs_global"] = round(gs["R2"], 3)      # global model on this scope's rows
            row["MAE_vs_global"] = round(gs["MAE"], 2)
            row["dR2"] = round(s["R2"] - gs["R2"], 3)     # >0 => routing beats global overall
        rows.append(row)
    return pd.DataFrame(rows).set_index("scope")
