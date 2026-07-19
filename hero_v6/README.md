# hero_v6

A self-contained humanitarian food-security dataset and the pipeline that builds it.
**IPC** (food-security phase classification) is the spine; each IPC row is joined with
**ACLED** (conflict), **IDP** (displacement), **rainfall**, and **WFP** (food prices)
at its own admin level.

> **The data already ships in this folder.** You do **not** need to fetch or merge
> anything to use it — open the files in `data/merged/`. 

## What's in `data/merged/`

| File | Granularity | Rows |
|---|---|---|
| `merged_adm1_wide.parquet` | one row per (admin1 area, IPC period) | ~10,024 |
| `merged_adm2_wide.parquet` | one row per (admin2 area, IPC period) | ~42,957 |

Two parallel datasets, one per admin level — **pick the level your analysis needs.**
They are *not* a hierarchy to be joined: adm1 numbers are whole-province totals, adm2
numbers are per-district. Coverage (share of rows with each theme attached) varies by
level and country.

Each file is "wide": the 7 IPC phases are spread across `phase_*` columns, one row per
area-period. Columns:

- **Identity** — `Country` (ISO3), `location_name_full`, `Level 1` (admin1 name),
  `Area` (admin2 name), `adm1_pcode`, `adm2_pcode`, `From`, `To`, `Validity period`,
  `Date of analysis`, `admin_level`.
- **IPC** — `phase_{1,2,3,3plus,4,5,all}_number` and `…_percentage`.
- **ACLED** — `acled_{political_violence,civilian_targeting,demonstration}_{events,fatalities}`,
  plus `acled_total_events`, `acled_total_fatalities`.
- **IDP** — `idp_population`, `idp_assessment_type`, `idp_reporting_round`,
  `idp_staleness_days`.
- **Rainfall** — `rain_1m_sum`, `rain_1m`, `rain_3m`, `rain_anomaly_1m`, `rain_anomaly_3m`.
- **WFP** — `wfp_price`, `wfp_inflation`, `wfp_obs_count`, `wfp_mapping_method`.
- **GDELT** *(admin1 file only)* — `gdelt_{verbal_coop,material_coop,verbal_conflict,material_conflict}_{events,mentions,tone}`
  (media-based CAMEO signals, collapsed to the 4 QuadClasses; counts summed over the IPC
  period, tone is the mentions-weighted mean). GDELT is admin1-native, so it is **not**
  present in `merged_adm2_wide`. *Note:* `_tone` is noisy where `_mentions` is low (sparse
  classes/periods) — down-weight or filter by `_mentions` when using it. Tone is `NaN` when a
  class had no mentions in the period.
- **NDVI** *(both files)* — `ndvi_vim` (vegetation greenness) and `ndvi_viq` (vegetation
  condition as % of normal — the drought/anomaly signal). Dekadal source, aggregated to the
  IPC period as an `n_pixels`-weighted mean.

```python
import pandas as pd
df = pd.read_parquet("data/merged/merged_adm2_wide.parquet", engine="fastparquet")
```

## Folder layout

```
hero_v6/
├── README.md            ← you are here (what's shipped + key design decisions)
├── MERGE_FLOW.md        ← diagram of how each source attaches to the IPC spine
├── config.py            ← scope (countries, dates), paths, knobs
├── fetch.py             ← IPC/ACLED/IDP from the HDX HAPI API → data/raw/
├── merge.py             ← join all sources onto IPC → data/merged/merged_adm{1,2}.parquet
├── widen.py             ← pivot long → wide → data/merged/merged_adm{1,2}_wide.parquet
└── data/
    ├── raw/             ← inputs: ipc, acled, idp, rainfall, wfp_with_pcodes, df_gdelt_pivot, wfp_ndvi (all shipped)
    └── merged/          ← outputs: the two *_wide.parquet files (shipped)
```

## Data flow

```
config.py  →  fetch.py  →  data/raw/{ipc,acled,idp}.parquet
                           data/raw/{rainfall,wfp_with_pcodes}.parquet  (shipped, not fetched)
              merge.py   →  data/merged/merged_adm{1,2}.parquet         (long)
              widen.py   →  data/merged/merged_adm{1,2}_wide.parquet    (wide, shipped)
```

See **MERGE_FLOW.md** for a per-source diagram of how each layer attaches to IPC.

## Key design decisions

- **Scope:** 52 countries (`config.COUNTRIES`), 2017 onwards.
- **IPC is the spine.** Every other source is *left-joined* onto IPC rows, so the row
  set is always IPC's — a missing theme is a blank cell, never a dropped row.
- **One dataset per admin level, no fallback.** Each IPC row carries its own
  `admin_level` (1 or 2); the merge runs once per level (adm1 joins on `admin1_code`,
  adm2 on `admin2_code`). There is no admin2→admin1 backfill, so the unit of analysis
  stays clean — pick the level your analysis needs.
- **Each theme joins by its natural time logic:**
  - **ACLED** (flow) — *sum* monthly events/fatalities within each IPC period.
  - **IDP** (stock) — the *latest* snapshot at or before period end, dropped if more
    than **400 days** stale (`MAX_IDP_STALENESS_DAYS`; `idp_staleness_days` is kept so
    the lag travels with the data).
  - **Rainfall** — per-period *sum* (`rain_1m_sum`) and *means* (1m, 3m, anomalies),
    joined at the level's native rainfall rows.
  - **WFP** — per-period *mean* price/inflation + obs count; `wfp_mapping_method` flags
    `elastic_buffer` if any contributing market needed the buffer (coastal markets whose
    GPS point falls just outside the polygon), else `strict_pip`.
- **Inputs:** IPC / ACLED / IDP are API-fetched (`fetch.py`, one global pull per theme,
  then filtered to the configured countries); rainfall and WFP ship pre-prepared in
  `data/raw/` (not fetched).
- **Engine:** fastparquet throughout (pyarrow not used in the dev env).

## Reproduce / update

Not required to use the data. To rebuild from scratch:

```powershell
# deps: pandas, numpy, requests, fastparquet
pip install pandas numpy requests fastparquet

cd hero_v6
python fetch.py        # IPC/ACLED/IDP → data/raw/ (skips files that already exist)
python merge.py        # → data/merged/merged_adm{1,2}.parquet
python widen.py --in data/merged/merged_adm1.parquet --out data/merged/merged_adm1_wide.parquet
python widen.py --in data/merged/merged_adm2.parquet --out data/merged/merged_adm2_wide.parquet
```

Notes:
- Parquet engine is **fastparquet** (`config.PARQUET_ENGINE`); pyarrow is not used.
- `rainfall.parquet` and `wfp_with_pcodes.parquet` are supplied inputs (not API-fetched);
  they ship in `data/raw/` (see *Key design decisions* above for WFP provenance).
- If you re-fetch, set your own `EMAIL`/`APP_NAME` in `config.py` for the HAPI token.

## Running the UI (Dashboard)

All configurations and startup scripts are located in the [CNR_setup](file:///c:/Dev/Progetti/HERO/hero_v6/CNR_setup) directory. We support both **Windows** (using `.bat` files) and **Linux/macOS** (using `.sh` scripts).

You can run the UI in two ways:

---

### Option 1: Docker Compose (Recommended)
This approach runs Nginx in a container, bypasses CORS issues, and maps files dynamically so that any changes to `UI/` are hot-reloaded.

*   **Windows (Double-click):** 
    Run [run_ui_docker.bat](file:///c:/Dev/Progetti/HERO/hero_v6/CNR_setup/run_ui_docker.bat)
*   **Linux/macOS:** 
    Execute [run_ui_docker.sh](file:///c:/Dev/Progetti/HERO/hero_v6/CNR_setup/run_ui_docker.sh) (ensure it has execute permissions: `chmod +x run_ui_docker.sh` first)
*   **Manual CLI (from `hero_v6/CNR_setup`):**
    ```bash
    cd hero_v6/CNR_setup
    docker compose up --build
    ```

The dashboard will be available at: **http://localhost:8080**

---

### Option 2: Local Python Server (No Containers)
If you don't have Docker, you can run a local HTTP server using Python. 

*   **Windows (Double-click):** 
    Run [run_ui.bat](file:///c:/Dev/Progetti/HERO/hero_v6/CNR_setup/run_ui.bat)
*   **Linux/macOS:** 
    Execute [run_ui.sh](file:///c:/Dev/Progetti/HERO/hero_v6/CNR_setup/run_ui.sh) (ensure it has execute permissions: `chmod +x run_ui.sh` first)
*   **Manual CLI (from `hero_v6/` root):**
    ```bash
    # IMPORTANT: Run from hero_v6 root, not from UI/ or CNR_setup/ 
    # to let the browser resolve ../TSA/results correctly.
    cd hero_v6
    python3 -m http.server 8080
    ```

The dashboard will be available at: **http://localhost:8080/UI/index.html**



