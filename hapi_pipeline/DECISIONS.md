# HAPI Pipeline — Design Decisions

A pipeline that pulls IPC, ACLED, and IDP from the HDX HAPI API, joins them (plus an
externally-supplied rainfall layer) into one analysis table, with IPC as the spine.

```
config.py  →  fetch.py  →  merge.py
                              └─ data/final/hapi_merged_2017.parquet
                          (+ data/raw/rainfall.parquet, supplied externally)

compare_levels.py  →  compare_levels.csv   (QA: per-country match coverage)
```

## Scope

- **52 countries** (`config.COUNTRIES`), **2017 onwards** (`DATE_FROM = "2017-01-01"`).
- Four layers: **IPC** (food security, spine), **ACLED** (conflict), **IDP** (displacement),
  **rainfall** (precipitation). IPC/ACLED/IDP are fetched; rainfall is supplied externally.

## Fetching (`fetch.py`)

- **One global pull per theme**, not per country. Each theme is fetched once with **no
  `location_code`** (the whole world), paginated at `LIMIT = 10000`, then filtered
  client-side to `COUNTRIES`. 3 requests' worth of pagination instead of 156.
  - Rationale: far fewer API calls; HAPI returns the full dataset efficiently.
  - Trade-off: downloads all countries and discards most (ACLED global is ~5–7M rows
    before filtering to ~2.4M kept). Only affects fetch time, not output.
- **Output:** one parquet per theme — `data/raw/{ipc,acled,idp}.parquet`. No per-country
  files (a global pull split back into 52 files would be pointless).
- **Resume-safe** at theme granularity (skips a theme whose file already exists).

## Merging (`merge.py`)

IPC is the **spine** — every IPC row is kept; ACLED and IDP are joined on. Each country is
sliced from the global frames in memory and processed independently.

### Temporal join logic

- **ACLED → IPC (flow data): sum within the period.** ACLED monthly event counts are
  summed over each IPC reference period (month start within `[ipc_start, ipc_end]`),
  pivoted wide by event_type, plus `acled_total_events` / `acled_total_fatalities`.
- **IDP → IPC (stock data): most recent snapshot at or before period end.** For each IPC
  row, take the latest IDP snapshot with `idp_start <= ipc_end` (a point-in-time / "as-of"
  match, not a sum). Snapshots are carried forward.

### Join level: row-level admin2 with admin1 fallback

This replaced an earlier per-country "pick one level" approach.

- Every value is joined at **admin2 (district)** first.
- IPC rows with **no admin2 match are filled from the admin1 (province)** aggregate.
- Provenance is recorded per row so a filled value is never mistaken for a district value:
  - `acled_match_level` / `idp_match_level` = **2** (district), **1** (province fill),
    or **NA** (no match).
  - A province-fill value is a **whole-province total** — respect the flag when comparing
    magnitudes.
- Rationale: keeps admin2 granularity wherever it works, uses admin1 only to plug gaps.
  Beats both pure-admin2 and a per-country switch on coverage.

Coverage (row-weighted, after the staleness cap below):
| Layer | pure admin2 | with admin1 fallback |
|-------|-------------|----------------------|
| ACLED | 42% | **53%** |
| IDP   | 23% | **35%** |
| RAIN  | 52% | **70%** |

### IDP staleness cap

- `MAX_IDP_STALENESS_DAYS = 400`. An IDP match is **dropped** if its snapshot is more than
  400 days older than the IPC period end. Set to `None` to disable.
- `idp_staleness_days` is written to the output so the lag travels with the data.
- Applied **independently at each admin level before the fallback**, so a **stale admin2
  match is discarded and a fresher admin1 snapshot can replace it** (province pooling often
  yields a more recent assessment). ~7,900 output rows are rescued this way.
- Impact: overall IDP coverage 46% → 35% (~50k stale rows dropped). It removes
  carry-forwards up to ~8 years old. Notably **YEM 99%→51%** (its coverage was mostly
  2015–18 snapshots smeared onto recent periods) and one-off sources like **BFA/ECU →0%**.
  Frequently-reporting countries (SDN, ETH, CAF) are barely affected.

## QA

- **`compare_levels.py`** reports per-country match coverage at pure admin2 vs admin2 +
  admin1 fallback, for both ACLED and IDP. It calls the live `merge.merge_country`, so it
  always reflects current config (e.g. the staleness cap). Writes `compare_levels.csv`.

### Rainfall layer

- **Externally supplied**, not fetched: `data/raw/rainfall.parquet` is placed manually (so
  `rainfall` is deliberately absent from `THEMES`). Different schema from the API layers:
  keyed by `ISO3` + a single `PCODE` (OCHA p-codes, joins directly) + `adm_level`; already
  wide with monthly `rain_1m`, `rain_3m`, `rain_anomaly_1m`, `rain_anomaly_3m` (dated the
  21st, 2015+). Covers 51 of 52 countries — **PSE missing**.
- **Aggregation per IPC period** (`aggregate_rainfall`, same within-period logic as ACLED):
  `rain_1m_sum`, `rain_1m_mean`, `rain_3m_mean`, `rain_anom_1m_mean`, `rain_anom_3m_mean`.
  Sum only for 1-month precip (a true total); 3-month is a rolling/overlapping window so mean
  only; anomalies are percentages so mean only.
- **Join:** admin2 on PCODE with **native admin1 fallback** (the file's own `adm_level==1`
  rows — rainfall is intensive mm, so admin1 must be the real value, never a sum of districts),
  flagged by `rain_match_level` (2 / 1 / NA).
- Coverage (row-weighted): **88% admin2 → 96% with fallback**. Near-complete for most
  countries; 0% for a handful whose rainfall p-codes don't align or aren't present (e.g. PSE,
  and Latin-America/Caribbean/island cases like HTI, GTM, HND, DOM, ECU, BGD, LBN, TLS, CPV).

## Environment

- Runs in the **`ewm` conda env** (`C:\Users\jonas\miniconda3\envs\ewm`).
- **`PARQUET_ENGINE = "fastparquet"`** — pyarrow's DLLs fail to load in this env; fastparquet
  works. All `read_parquet` / `to_parquet` calls pass this engine.
- Activate before running: `conda activate ewm`, then `python fetch.py` / `python merge.py`.

## Output

`data/final/hapi_merged_2017.parquet` — 446,571 rows, 36 columns. Key columns beyond the
IPC fields: `acled_*` totals + `acled_match_level`; `idp_population` + `idp_assessment_type`
+ `idp_reporting_round` + `idp_match_level` + `idp_staleness_days`; `rain_1m_sum` +
`rain_1m_mean` + `rain_3m_mean` + `rain_anom_1m_mean` + `rain_anom_3m_mean` +
`rain_match_level`.
