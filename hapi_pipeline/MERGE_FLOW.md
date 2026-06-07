# Merge flow — how each source attaches to the IPC spine

A reference diagram of how `merge.py` joins ACLED, IDP, rainfall, and WFP onto
IPC at both admin levels. No fallback — IPC's own `admin_level` field decides
which pass each row belongs to.

## Contents

1. [Overall flow](#overall-flow)
2. [ACLED — flow data](#acled--flow-data-sum-within-period)
3. [IDP — stock data](#idp--stock-data-latest-snapshot--ipc_end)
4. [Rainfall — native rows per level](#rainfall--native-rows-per-level)
5. [WFP — point data per level](#wfp--point-data-level-chosen-by-pcode-column)
6. [One IPC row, four sources](#one-ipc-row-four-sources)

---

## Overall flow

```
                    IPC SPINE (446,571 rows, each row = one phase × period × admin level)
                    ─────────────────────────────────────────────────────────
                    location_code, admin_level∈{1,2}, admin1_code, admin2_code,
                    reference_period_start/end, ipc_phase, population_in_phase
                                            │
                ┌───────────────────────────┴───────────────────────────┐
                │                                                       │
        FILTER admin_level==1                                   FILTER admin_level==2
        join key = admin1_code                                  join key = admin2_code
        79,300 rows                                             360,849 rows
                │                                                       │
                ▼                                                       ▼
      ADM1 MERGE PASS                                        ADM2 MERGE PASS
```

Each non-IPC source is then joined into one or both of these passes. Sections below
describe each source.

---

## ACLED — flow data (sum within period)

Raw shape: every event row already carries both codes (`admin1_code` and `admin2_code`).

```
acled.parquet  ───────────────────────────────────────────────────────────────────────
2,435,715 rows | location_code, admin1_code, admin2_code,
               | reference_period_start (monthly), event_type, events, fatalities
                                       │
            ┌──────────────────────────┴──────────────────────────┐
            │                                                     │
   ADM1 PASS (aggregate_acled at key=admin1_code)      ADM2 PASS (key=admin2_code)
   1. groupby (admin1_code, month, event_type)         1. groupby (admin2_code, month, event_type)
      → sum events, sum fatalities                        → sum events, sum fatalities
   2. join IPC adm1 periods on admin1_code             2. join IPC adm2 periods on admin2_code
      keep rows where month ∈ [ipc_start, ipc_end]        keep rows where month ∈ [ipc_start, ipc_end]
   3. pivot event_type wide                            3. pivot event_type wide
                                       │                                     │
                                       ▼                                     ▼
                       acled_battles_events, acled_riots_events, ...
                       acled_battles_fatalities, acled_riots_fatalities, ...
                       acled_total_events, acled_total_fatalities
```

The adm1 number for "Kano State, Nigeria, 2023-Q1" is the *sum across all districts in
Kano* — not a fallback from adm2, just a different groupby.

Source: [`aggregate_acled`](merge.py).

---

## IDP — stock data (latest snapshot ≤ ipc_end)

```
idp.parquet  ────────────────────────────────────────────────────────────────────────
72,281 rows | location_code, admin1_code, admin2_code,
            | reference_period_start (snapshot date), population,
            | assessment_type, reporting_round
                                       │
            ┌──────────────────────────┴──────────────────────────┐
            │                                                     │
   ADM1 PASS (match_idp at key=admin1_code)            ADM2 PASS (key=admin2_code)
   1. join IPC adm1 ipc_ends on admin1_code            1. join IPC adm2 ipc_ends on admin2_code
   2. keep snapshots where idp_start ≤ ipc_end         2. same
   3. per (admin1_code, ipc_end): take LAST            3. per (admin2_code, ipc_end): take LAST
   4. drop rows where staleness > 400 days             4. same
                                       │                                     │
                                       ▼                                     ▼
                          idp_population, idp_assessment_type,
                          idp_reporting_round, idp_staleness_days
```

The "latest" pick creates the `not_selected` loss bucket (76% at adm1) — older raw
rows get shadowed by fresher ones for the same period end.

Source: [`match_idp`](merge.py).

---

## Rainfall — native rows per level

Different from ACLED/IDP: rainfall publishes *separate rows* per level.
`adm_level=1` rows are province totals; `adm_level=2` rows are district totals. The
same district appears once as a district AND its province appears once as a province.

```
rainfall.parquet  ──────────────────────────────────────────────────────────────────
966,672 rows | ISO3, PCODE, adm_level∈{1,2}, date (monthly),
             | rain_1m, rain_3m, rain_anomaly_1m, rain_anomaly_3m
                                       │
            ┌──────────────────────────┴──────────────────────────┐
            │                                                     │
   ADM1 PASS (aggregate_rainfall at level=1)          ADM2 PASS (level=2)
   1. FILTER rain[adm_level == 1]   (113,847 rows)    1. FILTER rain[adm_level == 2]  (852,825 rows)
   2. join IPC adm1 periods on PCODE == admin1_code   2. join on PCODE == admin2_code
   3. keep rain rows where date ∈ [ipc_start, end]    3. same
   4. groupby (admin1_code, ipc_start, ipc_end):      4. same with admin2_code
        rain_1m_sum, rain_1m_mean,
        rain_3m_mean, rain_anom_*_mean
                                       │                                     │
                                       ▼                                     ▼
                            rain_1m_sum, rain_1m_mean, rain_3m_mean,
                            rain_anom_1m_mean, rain_anom_3m_mean
```

This is why 88% of raw rain rows are `wrong_adm_level` in the adm1 loss bucket — the
adm1 pass deliberately ignores the adm2-level rows. They're picked up by the adm2
pass instead.

Source: [`aggregate_rainfall`](merge.py).

---

## WFP — point data, level chosen by pcode column

Each market is a `(lat, lon)` point. The PIP step in
[`hero_v5/libs/wfp_spatial_mapping.py`](../hero_v5/libs/wfp_spatial_mapping.py) runs
*twice* per market — once against adm1 polygons, once against adm2 polygons — and
writes both `adm1_pcode` and `adm2_pcode`, plus a `mapping_method_adm{1,2}` flag
(`strict_pip` / `elastic_buffer` / `unmapped`) per level.

```
wfp_with_pcodes.parquet  ──────────────────────────────────────────────────────────
757,541 rows | ISO3, adm1_pcode, adm2_pcode, mkt_name, lat, lon, date (monthly),
             | price, inflation, mapping_method_adm1, mapping_method_adm2
                                       │
            ┌──────────────────────────┴──────────────────────────┐
            │                                                     │
   ADM1 PASS (aggregate_wfp at level=1)               ADM2 PASS (level=2)
   1. DROP rows where adm1_pcode is NaN               1. DROP rows where adm2_pcode is NaN
      or mapping_method_adm1 == 'unmapped'               or mapping_method_adm2 == 'unmapped'
   2. join IPC adm1 periods on adm1_pcode ==          2. join on adm2_pcode == admin2_code
      admin1_code
   3. keep where date ∈ [ipc_start, ipc_end]          3. same
   4. groupby (admin1_code, ipc_start, ipc_end):      4. same with admin2_code
        mean(price), mean(inflation),                      same aggregations
        count, worst-case(mapping_method_adm1)
                                       │                                     │
                                       ▼                                     ▼
                          wfp_price, wfp_inflation, wfp_obs_count,
                          wfp_mapping_method ('elastic_buffer' if any market
                                                used it, else 'strict_pip')
```

The same market contributes to both adm1 and adm2 averages — just averaged with
different peer groups (other markets in the same province vs other markets in the
same district). The `elastic_buffer` flag bubbles up: if even one contributing market
in a (province, period) used the buffer, the aggregate is tagged `elastic_buffer` so
the analyst knows.

Source: [`aggregate_wfp`](merge.py).

---

## One IPC row, four sources

```
IPC row at adm1: ("ETH", "ET01", admin_level=1, 2023-04 → 2023-09)
                              │
        ┌─────────────────────┼─────────────────────┐
        │           │         │         │           │
        ▼           ▼         ▼         ▼           ▼
     ACLED       IDP       Rain       WFP       (output row)
   sum of all   latest   sum/mean   mean of    one row in
   events in    snapshot of mm of   prices     hapi_merged_2017
   ET01 in      ≤ ipc_end ET01-     reported   _adm1.parquet
   that period            level     in ET01    with 48 cols
                          rain      markets
                          rows in
                          period
```

Same logic at adm2 — just swap `ET01 → ET010104` (a specific district) and use the
adm2-flavored columns of each source. The merge layer doesn't know or care about
hierarchy; it's just four parallel joins on the level-appropriate key.

## A word of caution on magnitudes

ACLED / IDP / rainfall sums and counts at adm1 are *whole-province totals*; at adm2
they're per-district. Do not compare absolute counts across the two output files —
they are not the same quantity. Coverage percentages (the diagnostic numbers in
[`diagnostics/outputs/review.md`](diagnostics/outputs/review.md)) are comparable
because they're relative; absolute values are not.
