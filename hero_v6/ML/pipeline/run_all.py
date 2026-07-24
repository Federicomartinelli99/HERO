"""
Run the whole pipeline for every dataset of one spatial level: static inference, nowcasting,
per-country charts, and the nowcast time-series grids.

Run:  python run_all.py            # admin-1 (unimputed & imputed)
      python run_all.py adm2       # admin-2 (unimputed only; needs prepare_adm2.py first)

The level is set from the CLI arg into HERO_LEVEL *before* importing config/round modules, since config
reads it once at import to fix AREA_COL / DATASETS / the results tree.
"""

import os
import sys

os.environ["HERO_LEVEL"] = sys.argv[1].lower() if len(sys.argv) > 1 else "adm1"

import config  # first — MKL guards; also reads HERO_LEVEL
import static_inference
import nowcast
import plot_country_metrics
import nowcast_viz
from config import DATASETS, LEVEL


def main():
    for dataset in DATASETS:
        print(f"\n{'=' * 72}\nLEVEL: {LEVEL} | DATASET: {dataset}\n{'=' * 72}")
        static_inference.main(dataset)
        nowcast.main(dataset)
        plot_country_metrics.main(dataset)
        nowcast_viz.main(dataset)
    print("\nAll done.")


if __name__ == "__main__":
    main()
