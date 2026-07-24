"""
Build the admin-2 nowcast payload for the pilot admin-2 drill-down countries (Cameroon, DR
Congo) as a standalone JSON — the piece `export_nowcast_map.py` inlines into the single-file map
for the province-level click-through.

Must run with HERO_LEVEL=adm2 (`config` reads the env var once at import, so this script sets it
before importing config — same trick `run_all.py` uses for a full admin-2 pipeline run). Runs in
its own interpreter (spawned by `export_nowcast_map.py` as a subprocess) so it never disturbs the
admin-1 exporter's own already-imported, admin-1-configured `config`/`features`/`nowcast_viz`.

Standalone: reuses `export_nowcast_map.build_nowcast_panel` / `area_record` by importing them
read-only; never modifies `export_nowcast_map.py` or any other pipeline file, and re-runs no
metrics.

Why Cameroon + DR Congo: both have **complete** admin-1 coverage (10/10 and 26/26 provinces have
real admin-1 nowcast data) *and* real, well-performing admin-2 nowcast results
(results/nowcast/adm2/unimputed/README.md — global-model per-country R² 0.430 CMR, 0.318 COD).
Mali and Burkina Faso scored higher on admin-2 R² alone (0.573, 0.596) but only had 9/20 and 2/17
admin-1 coverage, so their admin-1 map read mostly "no data" — dropped from the pilot for that
reason (see the nowcast_map README for the full comparison across all 25 candidate countries).
Afghanistan and Somalia (the admin-1-only pilot) don't work here at all — Somalia's admin-2 join
is a single placeholder unit and Afghanistan's is mostly unresolved.

Run (from hero_v6/ML/pipeline/; invoked automatically by export_nowcast_map.py, or standalone):
    HERO_LEVEL=adm2 python export_nowcast_map_adm2.py
"""
import os
os.environ["HERO_LEVEL"] = "adm2"          # before importing config — config reads it once

import json

import config                              # first — MKL/OpenMP guards; picks up HERO_LEVEL=adm2
from config import AREA_COL, COUNTRY_COL
import export_nowcast_map as M             # read-only reuse: build_nowcast_panel, area_record

PILOT = {"CMR": "Cameroon", "COD": "DR Congo"}
BOUND_DIR = config.HERO_ROOT / "UI" / "data" / "boundaries" / "adm2"
OUT_JSON = M.OUT_DIR / "adm2_payload.json"


def main():
    assert config.LEVEL == "adm2", "run with HERO_LEVEL=adm2"
    print("[export_nowcast_map_adm2] building admin-2 walk-forward panel (unimputed) ...")
    panel = M.build_nowcast_panel("unimputed")

    countries = {}
    for iso3, cname in PILOT.items():
        geo = json.load(open(BOUND_DIR / f"{iso3}.json", encoding="utf-8"))
        name_by_pcode = {f["properties"]["adm2_pcode"]: f["properties"].get("adm2_name", "")
                         for f in geo["features"]}
        csub = panel[panel[COUNTRY_COL] == iso3]

        areas = {}
        for pcode, name in name_by_pcode.items():
            rows = csub[csub[AREA_COL].astype(str) == pcode]
            if rows.empty:
                continue
            areas[pcode] = M.area_record(rows, pcode, name)

        countries[iso3] = {"name": cname, "areas": areas}
        missing = len(name_by_pcode) - len(areas)
        print(f"  {iso3}: {len(areas)}/{len(name_by_pcode)} boundary areas have data"
              f" ({missing} no-data)")

    OUT_JSON.write_text(json.dumps({"countries": countries}, ensure_ascii=False, separators=(",", ":")),
                         encoding="utf-8")
    print(f"Wrote {OUT_JSON.name} ({OUT_JSON.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
