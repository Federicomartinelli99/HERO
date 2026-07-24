# Admin-1 nowcast map (with admin-2 drill-down)

`nowcast_map.html` — a **single self-contained** interactive Leaflet map. Each admin-1 area is coloured by
its **latest nowcasted** IPC Phase 3+ level; hovering pops a trend graph (observed IPC + walk-forward
nowcast, with a dotted connector from the last real assessment to the latest nowcast); clicking zooms into
the province and, for **Cameroon and DR Congo**, drills into a real **admin-2** layer — same colouring,
same hover trend, one level finer.

Admin-1 pilot: **Afghanistan, Somalia, Cameroon, DR Congo**, **imputed** dataset. Admin-2 drill-down
pilot: **Cameroon, DR Congo**. Data and boundaries are inlined into the one file, so there is **no
runtime `fetch`** — it opens straight from `file://` (double-click it) and needs no server.

## Country selection for admin-2

Cameroon and DR Congo have **complete admin-1 coverage** (every province has real admin-1 nowcast data)
*and* real, well-performing admin-2 nowcast results (`results/nowcast/adm2/unimputed/README.md` —
global-model per-country R² 0.430 Cameroon, 0.318 DR Congo). Afghanistan and Somalia — the original
admin-1 pilot — don't work for admin-2 at all: Somalia's admin-2 join is a single placeholder unit and
Afghanistan's is mostly unresolved, which is why neither appears in the admin-2 nowcast results.

Mali and Burkina Faso were tried first and then dropped from the pilot: they score *higher* on raw
admin-2 R² (0.573, 0.596 — the best two of 25 candidate countries) but only had 9/20 and 2/17 admin-1
coverage, so their admin-1 choropleth was mostly "no data" (grey) even though their admin-2 layer
underneath was rich. Ranked across all 25 candidate countries by admin-1 coverage × admin-2 skill:

| country | admin-1 coverage | admin-2 R² (best model) | admin-2 vs persistence | admin-2 units |
|---|---|---|---|---|
| Cameroon | **10/10 (full)** | 0.430 | 0.124 → **+0.31** | 58 |
| DR Congo | **26/26 (full)** | 0.318 | 0.024 → **+0.29** | 164 |
| Nigeria | 37/37 (full) | 0.432 (2nd best overall) | −0.268 → **+0.70** | 768 (not used — too heavy to inline) |
| Burkina Faso *(tried, dropped)* | 2/17 | **0.596 (best overall)** | 0.201 → +0.40 | 47 |
| Mali *(tried, dropped)* | 9/20 | 0.573 | 0.364 → +0.21 | 160 |

Boundaries: OCHA COD-AB, admin-2 layer, fetched from HDX (`cod-ab-{cmr,cod}` on data.humdata.org,
`*_admin_boundaries.geojson.zip` — the site 403s a plain `curl`/`WebFetch`, needs a browser User-Agent),
simplified and stripped to `{adm2_pcode, adm2_name, adm1_pcode}`. The `adm2_pcode`/parent-`adm1_pcode`
values match the modelling data almost exactly (Cameroon 58/58; DR Congo 162/167 — 5 codes in the
modelling data aren't in this COD-AB vintage, a minor gap) — both boundary files already in
`UI/data/boundaries/{CMR,COD}.json` come from the same COD-AB vintage used here. (Mali/Burkina Faso's
`{MLI,BFA}.json` admin-2 files are still on disk under `UI/data/boundaries/adm2/` from the earlier trial,
just unused now that they're out of `PILOT`.)

## Regenerate

From `hero_v6/ML/pipeline/`, with the `ewm` interpreter (imports `config` first for the MKL/OpenMP guard):

```
C:/Users/jonas/miniconda3/envs/ewm/python.exe export_nowcast_map.py            # imputed (default)
C:/Users/jonas/miniconda3/envs/ewm/python.exe export_nowcast_map.py unimputed  # other dataset
```

This single command builds both layers: the admin-1 panel in-process, then `export_nowcast_map_adm2.py`
as a **subprocess** with `HERO_LEVEL=adm2` (`config.LEVEL` is read once at import, so the admin-2 panel
needs its own interpreter — same reason `run_all.py adm2` is a separate invocation). Both reuse
`nowcast_viz.walk_forward_predictions` by **importing it read-only** — neither edits `nowcast_viz.py` (or
any pipeline file) and neither re-runs metrics. Each prints a per-country join-coverage report (boundary
areas with data, no-data areas, and any data areas missing from the boundary file).

To run just the admin-2 sub-build on its own (e.g. while iterating on it):
```
set HERO_LEVEL=adm2
C:/Users/jonas/miniconda3/envs/ewm/python.exe export_nowcast_map_adm2.py
```
It writes `nowcast_map/adm2_payload.json`, which `export_nowcast_map.py` then reads back in.

## Embed in the Jekyll site (`g5-2026-website`)

Same mechanism the site already documents in `folium.markdown` and uses for `assets/charts/usa.html`:

1. Copy `nowcast_map.html` into the site at `assets/charts/nowcast_map.html`.
2. Add one line to a page (e.g. `_pages/modelling.markdown`):

```html
<iframe src="{{site.baseurl}}/assets/charts/nowcast_map.html" width="100%" height="600px"></iframe>
```

The map fills 100% of its box, so the `<iframe>` `width`/`height` control the size. It uses **Leaflet 1.9.3
from `cdn.jsdelivr.net`** (the site's exact version/CDN), renders in the viewer's light/dark theme, and
touches nothing else on the page (full isolation inside the iframe).

## Notes / extending

- **Admin-2 drill-down is live for Cameroon and DR Congo**; other pilot countries (Afghanistan, Somalia)
  still show a "not available for this country" panel on click, since their admin-2 join has no usable
  data.
- **Add more admin-2 countries:** add the ISO3 to `PILOT` (dict) in `export_nowcast_map_adm2.py`, drop a
  `{ISO3}.json` admin-2 boundary file (OCHA COD-AB, `{adm2_pcode, adm2_name, adm1_pcode}` properties) into
  `hero_v6/UI/data/boundaries/adm2/`, and re-run `export_nowcast_map.py` — check the join-coverage report
  it prints first (real per-country `adm2_pcode` coverage varies a lot; see
  `results/nowcast/adm2/unimputed/metrics_per_country.csv` for which countries have real per-country
  admin-2 nowcast results before picking one).
- **Add more admin-1 countries:** widen `PILOT` (dict) in `export_nowcast_map.py` to any ISO3 that has a
  boundary file in `hero_v6/UI/data/boundaries/` and re-run — the country selector generalizes
  automatically.
- **Palette:** ColorBrewer **YlOrRd** (5-class), a vetted CVD-safe sequential ramp for choropleths,
  confirmed monotonic in CIELAB L*. Bins: `<10 / 10–20 / 20–30 / 30–45 / 45+ %`.
