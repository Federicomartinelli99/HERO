# Rainfall Data — Structure Overview

Subnational dekadal rainfall data from **HDX / CHIRPS**, fetched via
`HDXRainfallLoader` and stored under `data/raw_rainfall/{iso3}/{iso2}-rainfall-subnat-full.csv`.

## 1. Source

- Pattern: `https://data.humdata.org/dataset/{iso3}-rainfall-subnational`
- Resource picked: `*-subnat-full.csv` (full history, no 5-year truncation)
- Underlying data: **CHIRPS** (Climate Hazards group InfraRed Precipitation with Stations)

## 2. Granularity — one row = one admin unit × one dekad

A **dekad** is a 10-day interval; each month has three (starting the 1st, 11th, and 21st), so ~36 per year. Coverage starts **1981-01-01** and runs through the current dekad plus a short forecast horizon.

Files contain rows at multiple administrative levels (region + district) for the same date.

## 3. Schema — 15 columns

| Column | Type | Description |
|---|---|---|
| `date` | date | Dekad start date (always the 1st, 11th, or 21st of a month) |
| `adm_level` | int | Administrative level: `1` (region / governorate / state) or `2` (district / LGA) |
| `adm_id` | int | Internal HDX numeric ID for the admin unit |
| `PCODE` | str | Official admin P-code (e.g. `YE12`, `AF0617`, `NG022021`) |
| `n_pixels` | float | Number of CHIRPS pixels contained in the polygon (proxy for area) |
| `rfh` | float | **Rainfall this dekad** (mm) |
| `rfh_avg` | float | Long-term mean rainfall for this dekad (mm) |
| `r1h` | float | 1-month rolling sum: rainfall over the last 3 dekads (mm) |
| `r1h_avg` | float | Long-term mean of `r1h` |
| `r3h` | float | 3-month rolling sum: rainfall over the last 9 dekads (mm) |
| `r3h_avg` | float | Long-term mean of `r3h` |
| `rfq` | float | This dekad's rainfall as **% of normal** (≈ `rfh / rfh_avg × 100`) |
| `r1q` | float | 1-month rainfall as % of normal |
| `r3q` | float | 3-month rainfall as % of normal |
| `version` | str | `final` (historical), `prelim` (recent observation), `forecast` (upcoming dekad) |

> The first few dekads of each admin unit have `NaN` in `r1h`/`r3h` (and their `_avg` / `_q` counterparts) because the rolling window isn't filled yet.

## 4. File sizes (sample fetched)

| ISO3 | Rows | Admin levels present |
|---|---|---|
| YEM | ~555 k | 1 + 2 |
| AFG | ~707 k | 1 + 2 |
| NGA | ~1.31 M | 1 + 2 |

Row count scales roughly with: `n_admin_units × ~36 dekads × ~45 years`.

## 5. Typical analysis hooks

- **Drought indicator**: low `rfq` / `r3q` (< 80% of normal) sustained over several dekads.
- **Anomaly trend**: deviation `rfh - rfh_avg` aggregated to monthly/seasonal.
- **Seasonality**: group by dekad-of-year, average `rfh` across all years.
- **Joining with WFP food prices**: aggregate dekads to month, then merge on (`PCODE` ↔ `adm1_name` mapping, `year`+`month`).
