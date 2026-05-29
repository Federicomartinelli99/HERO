# HERO v4 Pipeline: Spatial Reconciled Matching & Analysis

This module implements a robust, modular, and automated pipeline that aligns historical World Food Prices (WFP) data, CHIRPS monthly rainfall anomalies, and Integrated Food Security Phase Classification (IPC) population estimates at multiple administrative levels.

---

## 📂 Directory Structure

The `hero_v4/` module is organized as follows:

```
hero_v4/
├── data/
│   ├── boundaries/      <- Downloaded country administrative boundaries (GeoJSON/Shapefiles)
│   ├── interim/         <- Intermediate parquet datasets (consolidated WFP price & spatial coordinates)
│   ├── logs/            <- Runtime execution logs for each pipeline step
│   ├── plots/           <- Generated diagnostic, trend, and geographical HTML/PNG charts
│   └── reconciled/      <- Final matched and reconciled CSV datasets
├── libs/
│   ├── boundaries_download/
│   │   ├── downloader.py          <- Parses IPC dataset and schedules boundaries download
│   │   └── hdx_boundaries_loader.py <- CKAN API client to download & extract HDX boundaries
│   ├── data_plots/
│   │   └── plotter.py             <- Reusable plotting modules (Altair, Plotly, Seaborn)
│   └── data_preparation/
│       ├── 01_consolidate_wfp.py  <- Combines raw WFP price CSVs into a single Parquet file
│       ├── 02_spatial_mapping.py  <- Runs PIP and nearest-neighbor buffer mapping on market coordinates
│       ├── 03_reconcile_pipeline.py <- Joins IPC, WFP, and Rainfall data using a fallback hierarchy
│       ├── 04_plot_matches.py      <- Diagnostic execution script for all plotters
│       └── utils.py               <- Text normalization and logging helper functions
└── plots/
    └── data_exploration.ipynb   <- Exploratory analysis and plotting notebook
```

---

## ⚙️ Step-by-Step Pipeline Execution

The pipeline is designed to be executed sequentially:

1. **Step 1: Consolidate WFP Data**
   ```bash
   python hero_v4/libs/data_preparation/01_consolidate_wfp.py
   ```
   - Scans `World_Food_Prices/data/raw_food_prices/` for raw market price CSV files.
   - Standardizes columns and consolidates all records into `hero_v4/data/interim/wfp_consolidate.parquet`.

2. **Step 2: Spatial Point-in-Polygon & Elastic Mapping**
   ```bash
   python hero_v4/libs/data_preparation/02_spatial_mapping.py
   ```
   - Matches each unique market coordinate to `adm1_pcode` (province) and `adm2_pcode` (district).
   - Incorporates **strict Point-in-Polygon (PIP)** checks and falls back to a **spatial buffer elasticity** logic if strict checks fail.
   - Saves results to `hero_v4/data/interim/wfp_with_pcodes.parquet`.

3. **Step 3: Reconcile & Fallback Merge**
   ```bash
   python hero_v4/libs/data_preparation/03_reconcile_pipeline.py
   ```
   - Joins IPC area records with aggregated WFP market data and CHIRPS rainfall anomaly data.
   - Implements a hierarchical spatial fallback mechanism.
   - Saves final wide and long datasets into `hero_v4/data/reconciled/`.

4. **Step 4: Generate Diagnostic & Exploratory Plots**
   ```bash
   python hero_v4/libs/data_preparation/04_plot_matches.py
   ```
   - Generates and exports interactive HTML and static PNG plots (such as correlation heatmaps, inflation vs IPC scatters, rainfall anomalies, and geographical maps of markets) into `hero_v4/data/plots/`.

---

## 🗺️ Spatial Fallback Matching Hierarchies

Due to varying spatial resolutions across data sources, a hierarchical fallback mechanism is employed to maximize coverage while avoiding spurious mappings:

### WFP Market Fallback Levels
1. **`Admin2`**: Merges IPC records with WFP markets located in the exact same district (`adm2_pcode`). Checked only for true Admin 2 areas.
2. **`Admin1_Code`**: Merges on exact province code (`adm1_pcode`).
3. **`Admin1_Name`**: Merges on normalized spelling of the province name (to capture markets where code definitions differ slightly).
4. **`National`**: Falls back to the country-level (`ISO3`) average price/inflation for that month.
5. **`No_Match`**: Flags records that cannot be resolved at any level.

### Rainfall Fallback Levels
1. **`Admin2`**: Matches on exact district PCODE.
2. **`Admin1`**: Matches on exact province PCODE.
3. **`National`**: Country-level geographic mean.

---

## 🌊 Spatial Elasticity Buffer Logic (Coastlines & Riverbanks)

### The Challenge
Standard **Point-in-Polygon (PIP)** queries work by testing if a market coordinate point lies strictly inside a country's boundary polygon. In real-world data, this fails for a significant number of markets (historically ~8% of the global dataset) due to:
1. **Simplified boundaries**: Boundary shapefiles often simplify complex coastlines or riverbanks, placing shoreline points slightly in the sea/water.
2. **Border markets**: Markets situated right on coastlines, islands, ports, or major river boundaries (e.g. ports in Yemen, riverbanks in South Sudan) often have coordinates placed just meters outside the digitized land boundary.

### The Elastic Solution
To safely rescue these coordinate points, we implement a **robust spatial elasticity fallback**:
- When standard `intersects` returns `NaN`, the pipeline identifies the unmapped market points.
- It queries the country's boundary layers (Admin 1 and Admin 2) to find the **nearest polygon boundary** using `gpd.sjoin_nearest`.
- To prevent false assignments (e.g., mapping a market across a national boundary to an adjacent country), the search is **strictly restricted to boundaries of the same country** (by grouping and processing each ISO3 individually).
- A maximum distance threshold of **`0.05` decimal degrees** (approx. 5.5 km at the equator) is enforced. Points farther than 5.5 km are rejected and marked as `unmapped`.
- The exact mapping method (`strict_pip` or `elastic_buffer`) is stored as a tracking column in the database and propagated to final outputs to ensure transparency.
