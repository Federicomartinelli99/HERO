"""
Bronze -> Silver transformer for HDX CHIRPS rainfall data.

Reads all per-country CSVs in data/raw_rainfall/, keeps only the last
dekad of each month (date.dt.day == 21), drops dekad-specific and
metadata columns, concatenates everything into a single Parquet at
data/clean_rainfall/rainfall_monthly.parquet.
"""
from pathlib import Path

import pandas as pd

from libs.logger_config import get_logger

logger = get_logger("rainfall_transformer")

DEFAULT_RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw_rainfall"
DEFAULT_CLEAN_DIR = Path(__file__).resolve().parent.parent / "data" / "clean_rainfall"

DROP_COLS = ["n_pixels", "version", "rfh", "rfh_avg"]
CATEGORICAL_COLS = ["ISO3", "PCODE", "adm_level"]


class RainfallTransformer:
    """Consolidates raw dekadal rainfall CSVs into one monthly Parquet."""

    def __init__(
        self,
        raw_dir: Path = DEFAULT_RAW_DIR,
        clean_dir: Path = DEFAULT_CLEAN_DIR,
        engine: str = "pyarrow",
    ) -> None:
        self.raw_dir = Path(raw_dir)
        self.clean_dir = Path(clean_dir)
        self.engine = engine

    def build(self) -> Path:
        """Run the full bronze -> silver pipeline. Returns the output Parquet path."""
        csv_files = sorted(self.raw_dir.glob("*-rainfall-subnat-full.csv"))
        if not csv_files:
            raise FileNotFoundError(f"No raw rainfall CSVs found in {self.raw_dir}")

        frames = []
        for csv_path in csv_files:
            iso3 = csv_path.name.split("-")[0].upper()
            logger.info(f"[{iso3}] Reading {csv_path.name}")
            df = pd.read_csv(csv_path, parse_dates=["date"], low_memory=False)

            df = df[df["date"].dt.day == 21]
            df = df.drop(columns=[c for c in DROP_COLS if c in df.columns])
            df["ISO3"] = iso3

            frames.append(df)
            logger.info(f"[{iso3}] Kept {len(df):,} monthly rows")

        df_total = pd.concat(frames, ignore_index=True)
        for col in CATEGORICAL_COLS:
            if col in df_total.columns:
                df_total[col] = df_total[col].astype("category")

        self.clean_dir.mkdir(parents=True, exist_ok=True)
        out_path = self.clean_dir / "rainfall_monthly.parquet"
        df_total.to_parquet(out_path, engine=self.engine, index=False)

        size_mb = out_path.stat().st_size / (1024 * 1024)
        logger.info(f"Wrote {len(df_total):,} rows ({size_mb:.1f} MB) -> {out_path}")
        return out_path
