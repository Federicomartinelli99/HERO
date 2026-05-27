"""
Enrich IPC food-security data with rainfall features.

Each IPC row covers an admin area for a validity period (`current` /
`first projection` / `second projection`) with a From-To date range
spanning 2-6 months. For each row we attach the mean of four monthly
rainfall metrics over the rainfall observations that fall inside that
window.

Match strategy is conservative: we match each IPC row at *its own*
admin resolution. If the IPC row reports at adm1 (adm2_pcode empty),
it gets adm1 rainfall. If the IPC row reports at adm2, it gets adm2
rainfall -- or NaN if that specific adm2 has no rainfall data. We do
NOT upscale small urban LGAs to their parent state, because the
adm1 mean is a poor proxy for a tiny urban polygon. The
`rainfall_match_level` column records the resolution used.

Output: data/enriched/ipc_with_rainfall.parquet
"""
from pathlib import Path

import pandas as pd

from libs.logger_config import get_logger

logger = get_logger("ipc_rainfall_merger")

DEFAULT_IPC_CSV = Path(__file__).resolve().parent.parent / "ipc_global_area_long_pcoded.csv"
DEFAULT_RAINFALL_PARQUET = (
    Path(__file__).resolve().parent.parent.parent
    / "rainfall" / "data" / "clean_rainfall" / "rainfall_monthly.parquet"
)
DEFAULT_OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "enriched"

RAIN_METRICS = ["rain_1m", "rain_3m", "rain_anomaly_1m", "rain_anomaly_3m"]
AGG_COLS = RAIN_METRICS + ["n_rainfall_months"]


class IpcRainfallMerger:
    """Left-joins per-window mean rainfall features onto every IPC row."""

    def __init__(
        self,
        ipc_csv: Path = DEFAULT_IPC_CSV,
        rainfall_parquet: Path = DEFAULT_RAINFALL_PARQUET,
        out_dir: Path = DEFAULT_OUT_DIR,
        engine: str = "pyarrow",
    ) -> None:
        self.ipc_csv = Path(ipc_csv)
        self.rainfall_parquet = Path(rainfall_parquet)
        self.out_dir = Path(out_dir)
        self.engine = engine

    def build(self) -> Path:
        """Run the merge pipeline. Returns the output Parquet path."""
        ipc = self._load_ipc()
        rainfall = self._load_rainfall()

        # Single-pass aggregation keyed on join_pcode. join_pcode is adm2
        # where the IPC row reports at adm2, else adm1 -- so we never use
        # a coarser-than-IPC rainfall polygon. Adm2-level IPC rows whose
        # specific adm2 isn't in rainfall stay NaN by design (we don't
        # impute an urban LGA with its parent state's mean).
        windows = (
            ipc[["join_pcode", "From", "To"]]
            .dropna(subset=["join_pcode"])
            .drop_duplicates()
            .rename(columns={"join_pcode": "pcode"})
        )
        per_window = self._aggregate_per_window(windows, rainfall, label="join")

        enriched = self._merge_and_label(ipc, per_window)
        self._log_coverage(enriched)

        self.out_dir.mkdir(parents=True, exist_ok=True)
        out_path = self.out_dir / "ipc_with_rainfall.parquet"
        enriched.to_parquet(out_path, engine=self.engine, index=False)

        size_mb = out_path.stat().st_size / (1024 * 1024)
        logger.info(f"Wrote {len(enriched):,} rows ({size_mb:.1f} MB) -> {out_path}")
        return out_path

    def _load_ipc(self) -> pd.DataFrame:
        """Load IPC CSV, parse From/To, and derive the join PCODE per row."""
        logger.info(f"Loading IPC from {self.ipc_csv.name}")
        df = pd.read_csv(self.ipc_csv)
        df["From"] = pd.to_datetime(df["From"], format="%d/%m/%Y")
        df["To"] = pd.to_datetime(df["To"], format="%d/%m/%Y")

        # Some IPC rows have adm2_pcode as the literal empty string rather
        # than NaN. Normalise so fillna() actually triggers below.
        for col in ["adm1_pcode", "adm2_pcode"]:
            df[col] = df[col].replace("", pd.NA)

        # Most-granular pcode available per row: adm2 if present, else adm1.
        # (Previous comparison-based logic produced NaN whenever adm2 was
        # missing, silently dropping ~237 rows from the rainfall join.)
        df["join_pcode"] = df["adm2_pcode"].fillna(df["adm1_pcode"])

        logger.info(f"Loaded {len(df):,} IPC rows across {df['Country'].nunique()} countries")
        return df

    def _load_rainfall(self) -> pd.DataFrame:
        """Load the silver rainfall parquet, keeping only the join + metric columns."""
        logger.info(f"Loading rainfall from {self.rainfall_parquet.name}")
        df = pd.read_parquet(
            self.rainfall_parquet,
            columns=["PCODE", "date"] + RAIN_METRICS,
            engine=self.engine,
        )
        df["date"] = pd.to_datetime(df["date"])
        # Categorical PCODE breaks .isin against object dtype downstream.
        df["PCODE"] = df["PCODE"].astype(str)
        logger.info(
            f"Loaded {len(df):,} rainfall rows, "
            f"{df['PCODE'].nunique():,} unique PCODEs, "
            f"date range {df['date'].min().date()} -> {df['date'].max().date()}"
        )
        return df

    @staticmethod
    def _aggregate_per_window(
        windows: pd.DataFrame, rainfall: pd.DataFrame, label: str
    ) -> pd.DataFrame:
        """Compute mean rainfall metrics per unique (pcode, From, To) window.

        `windows` must have columns ['pcode', 'From', 'To']. Returns a frame
        with those three plus the four RAIN_METRICS and n_rainfall_months.

        Pattern: expand -> filter -> reduce. The expand step duplicates each
        window across the months for its PCODE; the filter keeps only months
        inside [From, To]; the reduce groups back to one row per window.
        """
        logger.info(
            f"[{label}] aggregating over {len(windows):,} unique (pcode, From, To) windows"
        )

        # Pre-filter rainfall to PCODEs that actually appear in the window set.
        wanted = set(windows["pcode"].unique())
        rf = rainfall[rainfall["PCODE"].isin(wanted)]

        # Expand: every window paired with every rainfall obs for its PCODE.
        joined = windows.merge(rf, left_on="pcode", right_on="PCODE", how="inner")
        logger.info(f"[{label}] expanded to {len(joined):,} (window x rainfall-obs) pairs")

        # Filter: keep only rainfall obs whose date is inside the window.
        in_window = joined[
            (joined["date"] >= joined["From"]) & (joined["date"] <= joined["To"])
        ]
        logger.info(f"[{label}] kept {len(in_window):,} obs after window filter")

        # Reduce: one row per unique window, mean across surviving months.
        per_window = in_window.groupby(
            ["pcode", "From", "To"], as_index=False
        ).agg(
            rain_1m=("rain_1m", "mean"),
            rain_3m=("rain_3m", "mean"),
            rain_anomaly_1m=("rain_anomaly_1m", "mean"),
            rain_anomaly_3m=("rain_anomaly_3m", "mean"),
            n_rainfall_months=("date", "count"),
        )
        return per_window

    @staticmethod
    def _merge_and_label(
        ipc: pd.DataFrame, per_window: pd.DataFrame
    ) -> pd.DataFrame:
        """Attach per-window aggregates and tag the resolution that matched.

        `rainfall_match_level`:
          - 'adm2': IPC row reports at adm2 and that adm2 was in rainfall
          - 'adm1': IPC row reports at adm1 (adm2_pcode empty) and that
                    adm1 was in rainfall
          - 'none': no rainfall match (adm2 missing from CHIRPS, or window
                    outside the 2015..2026-04 rainfall range)
        """
        enriched = ipc.merge(
            per_window,
            left_on=["join_pcode", "From", "To"],
            right_on=["pcode", "From", "To"],
            how="left",
        ).drop(columns=["pcode"])

        matched = enriched["rain_1m"].notna()
        is_adm2_row = enriched["adm2_pcode"].notna()
        enriched["rainfall_match_level"] = "none"
        enriched.loc[matched & is_adm2_row, "rainfall_match_level"] = "adm2"
        enriched.loc[matched & ~is_adm2_row, "rainfall_match_level"] = "adm1"

        enriched["n_rainfall_months"] = (
            enriched["n_rainfall_months"].fillna(0).astype(int)
        )
        enriched = enriched.drop(columns=["join_pcode"])
        return enriched

    @staticmethod
    def _log_coverage(enriched: pd.DataFrame) -> None:
        covered = enriched["rain_1m"].notna().sum()
        logger.info(
            f"Rainfall coverage: {covered:,}/{len(enriched):,} rows "
            f"({covered / len(enriched):.1%})"
        )
        for level, n in enriched["rainfall_match_level"].value_counts().items():
            logger.info(f"  match level = {level}: {n:,} rows")
        per_period = enriched.groupby("Validity period")["n_rainfall_months"].mean()
        for period, mean_n in per_period.items():
            logger.info(f"  {period}: mean n_rainfall_months = {mean_n:.2f}")
