# `extensions/` — drop-in upgrades for base pipeline steps

This folder is a deliberate seam for richer alternatives to the base pipeline steps,
so the core (`fetch.py`, `merge.py`, `widen.py`) stays small and the upgrades stay
isolated.

## Contract

Every script in `extensions/` either:

1. **Precedes** a base step — writes to the same path that step reads from, e.g. a
   cleaner `data/raw/ipc.parquet`. The base step is unchanged.
2. **Replaces** a base step — same input(s), same output path, same output schema
   as the step it stands in for. Callers swap which script they run.

The merge layer reads from `data/raw/{ipc,acled,idp,rainfall}.parquet` and from
`WFP_WITH_PCODES`. It does not care how those files were produced.

## Planned drop-ins (not yet implemented)

### `ipc_pcode_rescue.py` — precedes `merge.py`

Some IPC rows arrive with blank `admin1_code` / `admin2_code` but a valid
`admin1_name` / `admin2_name`. The hero_v5 reconciliation rescues these by looking
the name up in the corresponding boundary GeoJSON (with per-country spelling
overrides for YEM / SOM / SLE / TCD).

**Input**:  `data/raw/ipc.parquet`, `BOUNDARIES_DIR`
**Output**: overwrites `data/raw/ipc.parquet` (or writes to a sibling path the user
chooses to point `merge.py` at).
**Logic to port**: `hero_v5/libs/reconcile_pipeline_v5_final.py:273-412`. Port it
*without* `iterrows()` — build a `(country, normalized_name) → pcode` `pandas.Series`
once per admin level and `.map` it onto the IPC frame.

### Why the WFP elastic buffer is NOT in `extensions/`

The WFP prep chain in `hero_v5/libs/` (`wfp_consolidate.py` +
`wfp_spatial_mapping.py`) already includes the elastic-buffer fallback for markets
whose GPS coordinates fall outside any admin polygon (typical for coastal markets
that land in the sea). That fallback is intentional and part of the *baseline* WFP
prep — not an optional upgrade. Treating it as an extension would mis-describe the
design.
