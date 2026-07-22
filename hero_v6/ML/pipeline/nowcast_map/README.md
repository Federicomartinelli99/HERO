# Admin-1 nowcast map

`nowcast_map.html` — a **single self-contained** interactive Leaflet map. Each admin-1 area is coloured by
its **latest nowcasted** IPC Phase 3+ level; hovering pops a trend graph (observed IPC + walk-forward
nowcast, with a dotted connector from the last real assessment to the latest nowcast); clicking zooms into
the province (the hook where an admin-2 layer will later slot in).

Pilot: **Afghanistan + Somalia**, admin-1, **imputed** dataset. Data and boundaries are inlined into the
one file, so there is **no runtime `fetch`** — it opens straight from `file://` (double-click it) and needs
no server.

## Regenerate

From `hero_v6/ML/pipeline/`, with the `ewm` interpreter (imports `config` first for the MKL/OpenMP guard):

```
C:/Users/jonas/miniconda3/envs/ewm/python.exe export_nowcast_map.py            # imputed (default)
C:/Users/jonas/miniconda3/envs/ewm/python.exe export_nowcast_map.py unimputed  # other dataset
```

The exporter reuses `nowcast_viz.walk_forward_predictions` by **importing it read-only** — it never edits
`nowcast_viz.py` (or any pipeline file) and re-runs no metrics. It prints a per-country join-coverage
report (boundary areas with data, no-data areas, and any data areas missing from the boundary file).

## Embed in the Jekyll site (`g5-2026-website`)

Same mechanism the site already documents in `folium.markdown` and uses for `assets/charts/usa.html`:

1. Copy `nowcast_map.html` into the site at `assets/charts/nowcast_map.html`.
2. Add one line to a page (e.g. `_pages/nowcast-forecast.markdown`):

```html
<iframe src="{{site.baseurl}}/assets/charts/nowcast_map.html" width="100%" height="600px"></iframe>
```

The map fills 100% of its box, so the `<iframe>` `width`/`height` control the size. It uses **Leaflet 1.9.3
from `cdn.jsdelivr.net`** (the site's exact version/CDN), renders in the viewer's light/dark theme, and
touches nothing else on the page (full isolation inside the iframe).

## Notes / extending

- **Admin-2 drill-down is deferred** — the repo has no admin-2 polygons yet. Clicking a province zooms in
  and shows a labelled placeholder panel; once admin-2 GeoJSON (OCHA COD-AB, keyed by `adm2_pcode`) is
  added, that panel is where the finer layer slots in.
- **Add more countries:** widen `PILOT` in `export_nowcast_map.py` to any ISO3 that has a boundary file in
  `hero_v6/UI/data/boundaries/` and re-run — the country selector generalizes automatically.
- **Palette:** ColorBrewer **YlOrRd** (5-class), a vetted CVD-safe sequential ramp for choropleths,
  confirmed monotonic in CIELAB L*. Bins: `<10 / 10–20 / 20–30 / 30–45 / 45+ %`.
