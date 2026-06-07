# HAPI Pipeline — Design Decisions

A pipeline that pulls IPC, ACLED, and IDP from the HDX HAPI API, joins them (plus an
externally-supplied rainfall layer and WFP food prices) into one analysis table per
admin level, with IPC as the spine.

```
config.py
   │
   ├─ fetch.py  ──► data/raw/{ipc,acled,idp}.parquet
   ├─ (external) data/raw/rainfall.parquet
   ├─ (external) hero_v5/data/wfp_with_pcodes.parquet   ← WFP prep, see below
   │
   ▼
merge.py  ──► data/final/hapi_merged_2017_adm1.parquet
          ──► data/final/hapi_merged_2017_adm2.parquet
   │
   ▼
widen.py --in X --out Y   (run once per level)
          ──► data/final/hapi_merged_2017_adm1_wide.parquet
          ──► data/final/hapi_merged_2017_adm2_wide.parquet

compare_levels.py  ──► compare_levels.csv   (QA: per-country theme coverage at each level)
```

## Scope

- **52 countries** (`config.COUNTRIES`), **2017 onwards** (`DATE_FROM = "2017-01-01"`).
- Five layers: **IPC** (food security, spine), **ACLED** (conflict), **IDP** (displacement),
  **rainfall** (precipitation), **WFP** (food prices).
- IPC / ACLED / IDP are API-fetched. Rainfall is supplied externally. WFP is produced by
  a small two-script prep chain in `hero_v5/libs/` (see *WFP source* below).

## Fetching (`fetch.py`)

- **One global pull per theme**, not per country. Each theme is fetched once with **no
  `location_code`** (the whole world), paginated at `LIMIT = 10000`, then filtered
  client-side to `COUNTRIES`. 3 requests' worth of pagination instead of 156.
  - Rationale: far fewer API calls; HAPI returns the full dataset efficiently.
  - Trade-off: downloads all countries and discards most (ACLED global is ~5–7M rows
    before filtering to ~2.4M kept). Only affects fetch time, not output.
- **Output:** one parquet per theme — `data/raw/{ipc,acled,idp}.parquet`. No per-country
  files.
- **Resume-safe** at theme granularity (skips a theme whose file already exists).

## Merging (`merge.py`) — admin1 / admin2 split, no fallback

IPC is the **spine**. Every IPC row carries an `admin_level` column (1 or 2) that
indicates the level at which it was reported. `merge.py` runs **once per level**:

- `admin_level == 1` → join on `admin1_code` → `hapi_merged_2017_adm1.parquet`
- `admin_level == 2` → join on `admin2_code` → `hapi_merged_2017_adm2.parquet`

Each output is a *pure-level* dataset. No admin2 → admin1 fallback, no
`*_match_level` provenance flags — IPC's own level is authoritative per row.

### Why the split replaced the old fallback

The previous design joined every IPC row at admin2, then filled admin2 misses from
an admin1 aggregate (a whole-province total stamped with `*_match_level = 1`).
That muddled the unit of analysis: a "match_level=1" row mixed district IPC
demographics with province-level conflict/displacement/rain magnitudes. Splitting
by IPC's own `admin_level` gives a clean two-dataset layout — pick whichever level
your downstream analysis needs.

### Temporal join logic (per theme, unchanged from before)

- **ACLED → IPC (flow data): sum within the period.** Monthly event counts summed
  over each IPC reference period (month start within `[ipc_start, ipc_end]`),
  pivoted wide by event_type, plus `acled_total_events` / `acled_total_fatalities`.
- **IDP → IPC (stock data): most recent snapshot at or before period end.** For
  each IPC row, the latest IDP snapshot with `idp_start <= ipc_end`. Carried
  forward, but capped — see staleness section.
- **Rainfall → IPC: per-period sum (1m, a true total) + means (1m, 3m, anomaly
  1m, anomaly 3m).** 3m is a rolling/overlapping window so mean only; anomalies
  are percentages so mean only.
- **WFP → IPC: per-period mean of `price` + mean of `inflation` + `wfp_obs_count`
  (number of contributing market-months) + `wfp_mapping_method`** (`elastic_buffer`
  if any contributing market used the buffer, else `strict_pip` — worst-case
  propagation, so the buffer signal survives aggregation).

### IDP staleness cap

- `MAX_IDP_STALENESS_DAYS = 400`. An IDP match is **dropped** if its snapshot is
  more than 400 days older than the IPC period end. Set to `None` to disable.
- `idp_staleness_days` is written to the output so the lag travels with the data.

## WFP source — `hero_v5/data/wfp_with_pcodes.parquet`

WFP is **not** API-fetched and **not** processed inside `hapi_pipeline/`. The
canonical prep is a two-script chain in `hero_v5/libs/`, treated as a black box
upstream of `merge.py`:

```
World_Food_Prices/data/raw_food_prices/global_food_*.csv
   │
   ▼ hero_v5/libs/wfp_consolidate.py
hero_v5/data/wfp_consolidate.parquet
   │
   ▼ hero_v5/libs/wfp_spatial_mapping.py   (uses hero_v5/data/boundaries/)
hero_v5/data/wfp_with_pcodes.parquet   ← contract input to merge.py
```

`wfp_spatial_mapping.py` does **strict PIP + a 0.05° elastic-buffer fallback** for
markets that fail strict PIP. **The buffer is intentional**: coastal WFP markets
routinely fall a few hundred metres outside the polygon (GPS imprecision, or
polygons clipped to the coastline). Strict PIP would silently lose them. The
`mapping_method_adm{1,2}` column on every WFP row records which strategy
recovered each market (`strict_pip` / `elastic_buffer` / `unmapped`), and
`aggregate_wfp` in `merge.py` propagates that signal up to the IPC period
(worst case wins).

If `WFP_WITH_PCODES` is missing when `merge.py` runs, the script logs a warning
and produces outputs with empty `wfp_*` columns.

## QA — `compare_levels.py`

Reports per-country raw theme coverage (`acled_total_events.notna().mean()`,
etc.) at each admin level. Derives from the live `merge.merge_country`, so it
always reflects current config (e.g. the staleness cap). Writes
`compare_levels.csv`.

The previous "pure admin2 vs admin2+admin1 fallback" comparison no longer
applies; the new script reports admin1 and admin2 coverage side by side.

## Extensibility — `extensions/`

A seam for richer alternatives to base steps. Today it's empty; the planned
drop-in is `extensions/ipc_pcode_rescue.py`, which reads `data/raw/ipc.parquet`,
fills blank `admin{1,2}_code` from boundary GeoJSON lookups (logic to port from
`hero_v5/libs/reconcile_pipeline_v5_final.py:273-412`, vectorized), and writes
back. `merge.py` is unchanged.

See `extensions/README.md` for the contract.

## Environment

- Runs in the **`ewm` conda env** (`C:\Users\jonas\miniconda3\envs\ewm`).
- **`PARQUET_ENGINE = "fastparquet"`** — pyarrow's DLLs fail to load in this env;
  fastparquet works. All `read_parquet` / `to_parquet` calls pass this engine.

## Run order

```powershell
conda activate ewm

# One-time / when WFP CSVs change:
python hero_v5/libs/wfp_consolidate.py
python hero_v5/libs/wfp_spatial_mapping.py

# Main pipeline:
cd hapi_pipeline
python fetch.py
python merge.py
python widen.py --in data/final/hapi_merged_2017_adm1.parquet `
                --out data/final/hapi_merged_2017_adm1_wide.parquet
python widen.py --in data/final/hapi_merged_2017_adm2.parquet `
                --out data/final/hapi_merged_2017_adm2_wide.parquet
python compare_levels.py
```

## Outputs

`data/final/hapi_merged_2017_adm{1,2}.parquet` — IPC rows reported at the given
admin level, joined with ACLED, IDP, rainfall, and WFP. Key columns beyond the
IPC fields:

- `acled_*_events` + `acled_*_fatalities` (one per event_type) + `acled_total_events`
  + `acled_total_fatalities`
- `idp_population` + `idp_assessment_type` + `idp_reporting_round` + `idp_staleness_days`
- `rain_1m_sum` + `rain_1m_mean` + `rain_3m_mean` + `rain_anom_1m_mean` + `rain_anom_3m_mean`
- `wfp_price` + `wfp_inflation` + `wfp_obs_count` + `wfp_mapping_method`
