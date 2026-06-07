"""
review.py - Minimal merge-output diagnostic.

One file, no plots, ASCII only. Prints clean tables to stdout and writes the
same content to diagnostics/outputs/review.md. No matplotlib, no plotly.

What it answers:
  1. Integrity:    do the files hold together (row counts, dupes, level purity)?
  2. Coverage:     per-country, per-theme % of IPC rows with data attached
  3. Loss causes:  where did the unmatched raw rows go (per theme, per level)?
  4. Focus list:   ranked countries by composite (sample size + coverage)

Usage:  python diagnostics/review.py    (from hapi_pipeline/, in the ewm env)
"""

import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

# Imports from hapi_pipeline/.
HAPI_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HAPI_DIR))

from config import (
    COUNTRIES, FINAL_FILE_ADM1, FINAL_FILE_ADM2,
    PARQUET_ENGINE, raw_file, WFP_WITH_PCODES, MAX_IDP_STALENESS_DAYS,
)
from merge import to_dt

OUT_DIR = Path(__file__).resolve().parent / "outputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)
REPORT  = OUT_DIR / "review.md"

THEME_COL = {
    "acled": "acled_total_events",
    "idp":   "idp_population",
    "rain":  "rain_1m_sum",
    "wfp":   "wfp_price",
}


# ── data loading ─────────────────────────────────────────────────────────────

def load_all():
    a1 = pd.read_parquet(FINAL_FILE_ADM1, engine=PARQUET_ENGINE)
    a2 = pd.read_parquet(FINAL_FILE_ADM2, engine=PARQUET_ENGINE)
    ipc   = pd.read_parquet(raw_file("ipc"),      engine=PARQUET_ENGINE)
    acled = pd.read_parquet(raw_file("acled"),    engine=PARQUET_ENGINE)
    idp   = pd.read_parquet(raw_file("idp"),      engine=PARQUET_ENGINE)
    rain  = pd.read_parquet(raw_file("rainfall"), engine=PARQUET_ENGINE)
    wfp   = (pd.read_parquet(WFP_WITH_PCODES, engine=PARQUET_ENGINE)
             if os.path.exists(WFP_WITH_PCODES) else pd.DataFrame())
    return a1, a2, ipc, acled, idp, rain, wfp


# ── 1. integrity (counts + dupes only, no fancy phase sums) ───────────────────

def integrity(a1, a2, ipc):
    checks = []

    # row count budget: adm1 + adm2 long-form should equal #IPC rows we can use
    level_str = ipc["admin_level"].astype(str)
    has_a1 = (level_str == "1") & ipc["admin1_code"].astype(str).str.strip().ne("").fillna(False)
    has_a2 = (level_str == "2") & ipc["admin2_code"].astype(str).str.strip().ne("").fillna(False)
    kept_expected = (has_a1 | has_a2).sum()
    kept_actual   = len(a1) + len(a2)
    checks.append(("row-count budget",
                   abs(kept_expected - kept_actual) < 50,
                   f"raw={len(ipc):,} kept={kept_actual:,} expected={kept_expected:,} "
                   f"diff={kept_actual - kept_expected:+,} bad_level={(~level_str.isin(['1','2'])).sum():,}"))

    # level purity
    p1 = sorted(a1["admin_level"].astype(str).unique().tolist())
    p2 = sorted(a2["admin_level"].astype(str).unique().tolist())
    checks.append(("level purity", p1 == ["1"] and p2 == ["2"],
                   f"adm1={p1} adm2={p2}"))

    # blank pcodes at the keyed level
    blank1 = (a1["admin1_code"].isna() | a1["admin1_code"].astype(str).str.strip().isin(["", "nan"])).sum()
    blank2 = (a2["admin2_code"].isna() | a2["admin2_code"].astype(str).str.strip().isin(["", "nan"])).sum()
    checks.append(("pcodes present at keyed level", blank1 == 0 and blank2 == 0,
                   f"adm1 blank adm1_code={blank1} adm2 blank adm2_code={blank2}"))

    # duplicate long-form key (each IPC long row should be unique)
    long_key1 = ["location_code", "admin1_code", "ipc_start", "ipc_end", "ipc_type", "ipc_phase"]
    long_key2 = ["location_code", "admin2_code", "ipc_start", "ipc_end", "ipc_type", "ipc_phase"]
    d1 = a1.duplicated(subset=long_key1).sum()
    d2 = a2.duplicated(subset=long_key2).sum()
    checks.append(("no long-form key duplicates", d1 == 0 and d2 == 0,
                   f"adm1 dupes={d1:,} adm2 dupes={d2:,}"))

    return pd.DataFrame(checks, columns=["check", "ok", "detail"])


# ── 2. per-country coverage ──────────────────────────────────────────────────

def coverage_table(long_df):
    rows = []
    for c, g in long_df.groupby("location_code", observed=True):
        n = len(g)
        row = {"country": c, "ipc_rows": n}
        for t, col in THEME_COL.items():
            row[f"{t}_pct"] = round(g[col].notna().mean() * 100, 1) if col in g.columns else 0.0
        rows.append(row)
    return pd.DataFrame(rows).sort_values("country").reset_index(drop=True)


def overall_coverage(cov):
    """Row-weighted overall coverage per theme."""
    total = cov["ipc_rows"].sum()
    return {t: round((cov[f"{t}_pct"] * cov["ipc_rows"]).sum() / total, 1)
            for t in THEME_COL}


# ── 3. loss attribution (vectorized; no per-row .apply) ──────────────────────

def filter_ipc(ipc, level):
    code_col = f"admin{level}_code"
    df = ipc[ipc["admin_level"].astype(str) == str(level)].copy()
    df["ipc_start"] = to_dt(df["reference_period_start"])
    df["ipc_end"]   = to_dt(df["reference_period_end"])
    df[code_col]    = df[code_col].astype(str)
    df = df[~df[code_col].isin(["", "nan", "None"])]
    return df, code_col


def bucket_pcode(theme_df, theme_country_col, theme_code_col, ipc_at_level, ipc_code_col):
    """Stages 1-3: country / level / pcode. Returns Series of bucket labels."""
    bucket = pd.Series("matched", index=theme_df.index, dtype="object")
    out_of_scope = ~theme_df[theme_country_col].isin(COUNTRIES)
    bucket.loc[out_of_scope] = "country_not_in_scope"

    countries_at_level = set(ipc_at_level["location_code"].unique())
    no_ipc = bucket.eq("matched") & ~theme_df[theme_country_col].isin(countries_at_level)
    bucket.loc[no_ipc] = "no_ipc_at_level"

    cand = bucket.eq("matched")
    if cand.any():
        ipc_idx = pd.MultiIndex.from_frame(
            ipc_at_level[["location_code", ipc_code_col]].astype(str).drop_duplicates()
        )
        theme_idx = pd.MultiIndex.from_arrays([
            theme_df.loc[cand, theme_country_col].astype(str).values,
            theme_df.loc[cand, theme_code_col].astype(str).values,
        ])
        has = theme_idx.isin(ipc_idx)
        cand_indices = bucket.index[cand]
        bucket.loc[cand_indices[~has]] = "pcode_mismatch"
    return bucket


def temporal_filter(theme_df, bucket, country_col, code_col, date_col, ipc_at_level, ipc_code_col):
    """Stage 4: temporal overlap on remaining 'matched' candidates."""
    cand_idx = bucket.eq("matched")
    if not cand_idx.any():
        return bucket
    cand = theme_df.loc[cand_idx, [country_col, code_col, date_col]].copy()
    cand["theme_date"]  = to_dt(cand[date_col])
    cand[code_col]      = cand[code_col].astype(str)
    cand["_idx"]        = cand.index

    ipc_lite = ipc_at_level[["location_code", ipc_code_col, "ipc_start", "ipc_end"]].drop_duplicates()
    merged = cand.merge(ipc_lite, left_on=[country_col, code_col],
                                  right_on=["location_code", ipc_code_col], how="left")
    overlap = (merged["theme_date"] >= merged["ipc_start"]) & \
              (merged["theme_date"] <= merged["ipc_end"])
    matched = set(merged.loc[overlap, "_idx"].unique())
    cand_indices = bucket.index[cand_idx]
    bucket.loc[cand_indices[~cand_indices.isin(matched)]] = "temporal_no_overlap"
    return bucket


def attribute_acled(acled, ipc, level):
    ipc_at, code_col = filter_ipc(ipc, level)
    b = bucket_pcode(acled, "location_code", code_col, ipc_at, code_col)
    b = temporal_filter(acled, b, "location_code", code_col, "reference_period_start",
                        ipc_at, code_col)
    return b


def attribute_idp(idp, ipc, level):
    ipc_at, code_col = filter_ipc(ipc, level)
    b = bucket_pcode(idp, "location_code", code_col, ipc_at, code_col)

    # Replay match_idp staleness logic to split unmatched-yet-candidate rows
    # into 'not_selected' / 'idp_too_stale' / 'matched'.
    cand_idx = b.eq("matched")
    if not cand_idx.any():
        return b
    sub = idp.loc[cand_idx, ["location_code", code_col, "reference_period_start"]].copy()
    sub["idp_start"] = to_dt(sub["reference_period_start"])
    sub[code_col]    = sub[code_col].astype(str)
    sub["_idx"]      = sub.index

    ipc_ends = ipc_at[["location_code", code_col, "ipc_end"]].drop_duplicates()
    merged = ipc_ends.merge(sub, on=["location_code", code_col], how="left")
    merged = merged[merged["idp_start"] <= merged["ipc_end"]]
    chosen = (merged.sort_values("idp_start")
                    .groupby(["location_code", code_col, "ipc_end"], as_index=False).last())
    chosen["staleness"] = (chosen["ipc_end"] - chosen["idp_start"]).dt.days

    matched_raw   = set(chosen.loc[chosen["staleness"] <= MAX_IDP_STALENESS_DAYS, "_idx"]
                              .dropna().astype(int))
    ever_chosen   = set(chosen["_idx"].dropna().astype(int))
    only_dropped  = ever_chosen - matched_raw

    cand_indices = b.index[cand_idx]
    too_stale_mask = cand_indices.isin(only_dropped) & ~cand_indices.isin(matched_raw)
    b.loc[cand_indices[too_stale_mask]] = "idp_too_stale"
    not_selected_mask = ~cand_indices.isin(ever_chosen) & ~cand_indices.isin(matched_raw)
    b.loc[cand_indices[not_selected_mask]] = "not_selected"
    return b


def attribute_rainfall(rain, ipc, level):
    ipc_at, code_col = filter_ipc(ipc, level)
    b = pd.Series("matched", index=rain.index, dtype="object")
    b.loc[~rain["ISO3"].isin(COUNTRIES)] = "country_not_in_scope"
    b.loc[b.eq("matched") & (rain["adm_level"].astype(str) != str(level))] = "wrong_adm_level"
    countries_at_level = set(ipc_at["location_code"].unique())
    b.loc[b.eq("matched") & ~rain["ISO3"].isin(countries_at_level)] = "no_ipc_at_level"

    cand = b.eq("matched")
    if cand.any():
        ipc_idx = pd.MultiIndex.from_frame(
            ipc_at[["location_code", code_col]].astype(str).drop_duplicates()
        )
        theme_idx = pd.MultiIndex.from_arrays([
            rain.loc[cand, "ISO3"].astype(str).values,
            rain.loc[cand, "PCODE"].astype(str).values,
        ])
        has = theme_idx.isin(ipc_idx)
        cand_indices = b.index[cand]
        b.loc[cand_indices[~has]] = "pcode_mismatch"

    cand_idx = b.eq("matched")
    if not cand_idx.any():
        return b
    sub = rain.loc[cand_idx, ["ISO3", "PCODE", "date"]].copy()
    sub["theme_date"] = to_dt(sub["date"])
    sub["PCODE"]      = sub["PCODE"].astype(str)
    sub["_idx"]       = sub.index
    ipc_lite = ipc_at[["location_code", code_col, "ipc_start", "ipc_end"]].drop_duplicates()
    merged = sub.merge(ipc_lite, left_on=["ISO3", "PCODE"],
                                 right_on=["location_code", code_col], how="left")
    overlap = (merged["theme_date"] >= merged["ipc_start"]) & \
              (merged["theme_date"] <= merged["ipc_end"])
    matched = set(merged.loc[overlap, "_idx"].unique())
    cand_indices = b.index[cand_idx]
    b.loc[cand_indices[~cand_indices.isin(matched)]] = "temporal_no_overlap"
    return b


def attribute_wfp(wfp, ipc, level):
    if wfp.empty:
        return pd.Series([], dtype="object")
    ipc_at, ipc_code_col = filter_ipc(ipc, level)
    wfp_code = f"adm{level}_pcode"
    wfp_method = f"mapping_method_adm{level}"

    b = pd.Series("matched", index=wfp.index, dtype="object")
    b.loc[~wfp["ISO3"].isin(COUNTRIES)] = "country_not_in_scope"
    countries_at_level = set(ipc_at["location_code"].unique())
    b.loc[b.eq("matched") & ~wfp["ISO3"].isin(countries_at_level)] = "no_ipc_at_level"

    method = wfp[wfp_method]
    unmapped = b.eq("matched") & (method.isna() | (method == "unmapped") | wfp[wfp_code].isna())
    b.loc[unmapped] = "wfp_unmapped"

    cand = b.eq("matched")
    if cand.any():
        ipc_idx = pd.MultiIndex.from_frame(
            ipc_at[["location_code", ipc_code_col]].astype(str).drop_duplicates()
        )
        theme_idx = pd.MultiIndex.from_arrays([
            wfp.loc[cand, "ISO3"].astype(str).values,
            wfp.loc[cand, wfp_code].astype(str).values,
        ])
        has = theme_idx.isin(ipc_idx)
        cand_indices = b.index[cand]
        b.loc[cand_indices[~has]] = "pcode_mismatch"

    cand_idx = b.eq("matched")
    if not cand_idx.any():
        return b
    sub = wfp.loc[cand_idx, ["ISO3", wfp_code, "date"]].copy()
    sub["theme_date"] = to_dt(sub["date"])
    sub[wfp_code]     = sub[wfp_code].astype(str)
    sub["_idx"]       = sub.index
    ipc_lite = ipc_at[["location_code", ipc_code_col, "ipc_start", "ipc_end"]].drop_duplicates()
    merged = sub.merge(ipc_lite, left_on=["ISO3", wfp_code],
                                 right_on=["location_code", ipc_code_col], how="left")
    overlap = (merged["theme_date"] >= merged["ipc_start"]) & \
              (merged["theme_date"] <= merged["ipc_end"])
    matched = set(merged.loc[overlap, "_idx"].unique())
    cand_indices = b.index[cand_idx]
    b.loc[cand_indices[~cand_indices.isin(matched)]] = "temporal_no_overlap"
    return b


def summarize_bucket(b):
    if b.empty:
        return pd.DataFrame(columns=["bucket", "n_rows", "pct"])
    c = b.value_counts(dropna=False)
    total = c.sum()
    return (pd.DataFrame({"bucket": c.index, "n_rows": c.values})
              .assign(pct=lambda d: (d["n_rows"] / total * 100).round(1))
              .sort_values("n_rows", ascending=False)
              .reset_index(drop=True))


# ── 4. ranking ───────────────────────────────────────────────────────────────

def rank_countries(cov):
    df = cov.copy()
    df["mean_cov"] = df[["acled_pct", "idp_pct", "rain_pct", "wfp_pct"]].mean(axis=1).round(1)
    df["score"]    = (np.sqrt(df["ipc_rows"]) * df["mean_cov"] / 100).round(2)
    return df.sort_values("score", ascending=False).reset_index(drop=True)


# ── output ───────────────────────────────────────────────────────────────────

def emit(s, lines):
    """Print and accumulate."""
    print(s)
    lines.append(s)


def df_to_text(df, max_rows=None):
    """ASCII-safe table rendering."""
    if df.empty:
        return "(empty)"
    if max_rows is not None:
        df = df.head(max_rows)
    return df.to_string(index=False)


def main():
    t0 = time.time()
    print("Loading...")
    a1, a2, ipc, acled, idp, rain, wfp = load_all()
    print(f"  adm1={len(a1):,}  adm2={len(a2):,}  ipc={len(ipc):,}  acled={len(acled):,}  "
          f"idp={len(idp):,}  rain={len(rain):,}  wfp={len(wfp):,}")

    out = []

    # ── header ──
    emit("", out)
    emit("=" * 78, out)
    emit("HAPI MERGE OUTPUT REVIEW", out)
    emit(f"Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}", out)
    emit("=" * 78, out)

    # ── 1. integrity ──
    emit("\n## 1. INTEGRITY\n", out)
    integ = integrity(a1, a2, ipc)
    integ["status"] = integ["ok"].map({True: "OK", False: "FAIL"})
    emit(df_to_text(integ[["check", "status", "detail"]]), out)

    # ── 2. coverage ──
    emit("\n## 2. COVERAGE per country (% of IPC rows with each theme attached)\n", out)
    cov1 = coverage_table(a1)
    cov2 = coverage_table(a2)
    over1, over2 = overall_coverage(cov1), overall_coverage(cov2)
    emit("Overall row-weighted coverage:", out)
    emit(f"  adm1 ({cov1['ipc_rows'].sum():,} rows, {len(cov1)} countries):  "
         f"ACLED {over1['acled']:>4.1f}% | IDP {over1['idp']:>4.1f}% | "
         f"RAIN {over1['rain']:>4.1f}% | WFP {over1['wfp']:>4.1f}%", out)
    emit(f"  adm2 ({cov2['ipc_rows'].sum():,} rows, {len(cov2)} countries):  "
         f"ACLED {over2['acled']:>4.1f}% | IDP {over2['idp']:>4.1f}% | "
         f"RAIN {over2['rain']:>4.1f}% | WFP {over2['wfp']:>4.1f}%", out)
    emit("", out)
    emit("Per-country coverage - admin1:", out)
    emit(df_to_text(cov1), out)
    emit("\nPer-country coverage - admin2:", out)
    emit(df_to_text(cov2), out)

    # ── 3. loss attribution ──
    emit("\n## 3. LOSS ATTRIBUTION (where dropped raw rows went)\n", out)
    raw_n = {"acled": len(acled), "idp": len(idp), "rain": len(rain), "wfp": len(wfp)}
    for level in (1, 2):
        emit(f"--- admin{level} ---", out)
        for theme, attr in [("acled", attribute_acled),
                             ("idp",   attribute_idp),
                             ("rain",  attribute_rainfall),
                             ("wfp",   attribute_wfp)]:
            t1 = time.time()
            raw = {"acled": acled, "idp": idp, "rain": rain, "wfp": wfp}[theme]
            b = attr(raw, ipc, level) if not raw.empty else pd.Series([], dtype="object")
            sm = summarize_bucket(b)
            elapsed = time.time() - t1
            emit(f"\n{theme.upper()}  (raw {raw_n[theme]:,} rows, {elapsed:.1f}s):", out)
            emit(df_to_text(sm), out)
        emit("", out)

    # ── 4. ranking ──
    emit("\n## 4. COUNTRY FOCUS RANKING (composite: sqrt(ipc_rows) * mean(coverage) / 100)\n", out)
    r1 = rank_countries(cov1)
    r2 = rank_countries(cov2)
    emit("Top 10 - admin1:", out)
    emit(df_to_text(r1.head(10)), out)
    emit("\nTop 10 - admin2:", out)
    emit(df_to_text(r2.head(10)), out)

    only_a1 = sorted(set(cov1["country"]) - set(cov2["country"]))
    only_a2 = sorted(set(cov2["country"]) - set(cov1["country"]))
    emit(f"\nOnly in adm1 (use adm1): {', '.join(only_a1) or '(none)'}", out)
    emit(f"Only in adm2 (use adm2): {', '.join(only_a2) or '(none)'}", out)

    emit("\nFull ranking - admin1:", out)
    emit(df_to_text(r1), out)
    emit("\nFull ranking - admin2:", out)
    emit(df_to_text(r2), out)

    # ── write markdown ──
    REPORT.write_text("\n".join(out), encoding="utf-8")
    emit("", out)
    emit(f"Done in {time.time() - t0:.1f}s.  Report written to: {REPORT}", out)
    print(f"  -> {REPORT}")


if __name__ == "__main__":
    main()
