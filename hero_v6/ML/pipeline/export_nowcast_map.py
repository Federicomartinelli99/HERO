"""
Build a single self-contained interactive **admin-1 nowcast map** (Leaflet) for the g5-2026-website
Jekyll / GitHub Pages site — a drop-in twin of that site's `assets/charts/usa.html`.

The map colours each admin-1 area by its **latest nowcasted** IPC Phase 3+ level; hovering an area pops a
small trend graph (observed actual series + walk-forward nowcast, with a dotted connector from the last
real assessment to the latest nowcast); clicking zooms into the province and, for Cameroon and DR Congo,
drills into a real **admin-2** layer (same colouring + hover trend, one level finer — see
`export_nowcast_map_adm2.py`). Data + boundaries are inlined into the one HTML file, so there is no
runtime `fetch` (no CORS / baseurl issues) — it opens from `file://` and embeds via a single `<iframe>`.

Standalone: this reuses `nowcast_viz.walk_forward_predictions` by **importing it read-only** — it never
modifies `nowcast_viz.py` or any other pipeline file, and re-runs no metrics.

Run (admin-1 pilot: AFG, SOM, CMR, COD; imputed dataset; admin-2 drill-down auto-built for CMR/COD):
    python export_nowcast_map.py            # or: python export_nowcast_map.py imputed
"""

import os
import sys
import json
import subprocess
import datetime

import config                       # first — MKL/OpenMP guards before numpy
import numpy as np
import pandas as pd

import features as F
import nowcast_viz as NV             # read-only reuse of the walk-forward; never modified
from config import TARGET, AREA_COL, COUNTRY_COL

# Admin-1 pilot: all four have an adm1 boundary file in UI/data/boundaries/. Of these, CMR/COD also get
# a real admin-2 drill-down (see load_adm2_layer) — AFG and SOM's admin-2 join is placeholder / unresolved
# (no real adm2-level data), so they keep the "not available" panel on click.
PILOT = {"AFG": "Afghanistan", "SOM": "Somalia", "CMR": "Cameroon", "COD": "DR Congo"}
BOUND_DIR = config.HERO_ROOT / "UI" / "data" / "boundaries"
ADM2_BOUND_DIR = BOUND_DIR / "adm2"
OUT_DIR = config.PIPELINE_DIR / "nowcast_map"
OUT_HTML = OUT_DIR / "nowcast_map.html"

# ColorBrewer YlOrRd (5-class) — a vetted CVD-safe *sequential* choropleth ramp; verified monotonic in
# CIELAB L* (98.4 -> 84.5 -> 69.7 -> 53.8 -> 39.5, min step 13.9). worse = darker/redder.
RAMP = ["#ffffb2", "#fecc5c", "#fd8d3c", "#f03b20", "#bd0026"]
BINS = [10, 20, 30, 45]              # phase_3plus_percentage break points between the 5 colours


def build_nowcast_panel(dataset: str) -> pd.DataFrame:
    """Panel with a walk-forward `nowcast` column — mirrors `nowcast_viz.main` (no metrics, no re-run)."""
    df = F.load_dataset(dataset)
    panel = F.build_panel(df, include_projections=True)
    feats, target = F.make_features(panel)
    cols = F.feature_sets(feats)["nowcast"]
    panel = panel.reset_index(drop=True)
    panel["nowcast"] = NV.walk_forward_predictions(feats, target, panel, cols)
    return panel


def area_record(sub: pd.DataFrame, pcode: str, name: str) -> dict:
    """Per-area series + latest actual/nowcast for one admin-1 unit (rows already for this area)."""
    sub = sub.sort_values("From")
    series = []
    for _, r in sub.iterrows():
        actual = float(r[TARGET]) if (r["is_projection"] == 0 and pd.notna(r[TARGET])) else None
        nowc = float(r["nowcast"]) if pd.notna(r["nowcast"]) else None
        if actual is None and nowc is None:
            continue
        series.append({"date": r["From"].strftime("%Y-%m-%d"),
                       "actual": round(actual, 1) if actual is not None else None,
                       "nowcast": round(nowc, 1) if nowc is not None else None})

    obs = sub[(sub["is_projection"] == 0) & sub[TARGET].notna()]
    latest_actual = None
    if not obs.empty:
        r = obs.iloc[-1]
        latest_actual = {"date": r["From"].strftime("%Y-%m-%d"), "value": round(float(r[TARGET]), 1)}

    nc = sub[sub["nowcast"].notna()]
    latest_nowcast = None
    if not nc.empty:
        r = nc.iloc[-1]
        latest_nowcast = {"date": r["From"].strftime("%Y-%m-%d"), "value": round(float(r["nowcast"]), 1)}

    value = (latest_nowcast or latest_actual or {}).get("value")
    return {"pcode": pcode, "name": name, "value": value,
            "latest_actual": latest_actual, "latest_nowcast": latest_nowcast, "series": series}


def build_payload(panel: pd.DataFrame, dataset: str):
    """Assemble the {countries, boundaries} payload and print a per-country join-coverage report."""
    countries, boundaries = {}, {}
    for iso3, cname in PILOT.items():
        geo = json.load(open(BOUND_DIR / f"{iso3}.json", encoding="utf-8"))
        boundaries[iso3] = geo
        name_by_pcode = {f["properties"]["adm1_pcode"]: f["properties"].get("adm1_name", "")
                         for f in geo["features"]}
        csub = panel[panel[COUNTRY_COL] == iso3]

        areas = {}
        for pcode, name in name_by_pcode.items():
            rows = csub[csub[AREA_COL].astype(str) == pcode]
            if rows.empty:
                continue
            areas[pcode] = area_record(rows, pcode, name)

        countries[iso3] = {"name": cname, "areas": areas}
        missing = [p for p in name_by_pcode if p not in areas]
        extra = sorted(set(csub[AREA_COL].astype(str)) - set(name_by_pcode))
        print(f"  {iso3}: {len(areas)}/{len(name_by_pcode)} boundary areas have data"
              f" | no-data areas: {missing if missing else 'none'}"
              f" | data areas not in boundary: {extra if extra else 'none'}")

    data = {"generated": datetime.date.today().isoformat(), "dataset": dataset,
            "target": "IPC Phase 3+ (% of population)", "ramp": RAMP, "bins": BINS,
            "countries": countries}
    return data, boundaries


def load_adm2_layer():
    """Run the admin-2 sub-build and inline its payload + boundaries.

    `config.LEVEL` is read once, at import, from HERO_LEVEL — so building the admin-2 panel needs
    its own interpreter, not just a different function call. `export_nowcast_map_adm2.py` sets
    HERO_LEVEL=adm2 and writes a small JSON payload to nowcast_map/adm2_payload.json; this just
    runs that script and reads its output back in.
    """
    print("[export_nowcast_map] building admin-2 drill-down layer (subprocess, HERO_LEVEL=adm2) ...")
    env = os.environ.copy()
    env["HERO_LEVEL"] = "adm2"
    subprocess.run([sys.executable, "export_nowcast_map_adm2.py"],
                    check=True, env=env, cwd=str(config.PIPELINE_DIR))

    adm2_json = OUT_DIR / "adm2_payload.json"
    payload = json.loads(adm2_json.read_text(encoding="utf-8"))
    boundaries = {iso3: json.load(open(ADM2_BOUND_DIR / f"{iso3}.json", encoding="utf-8"))
                  for iso3 in payload["countries"]}
    return payload["countries"], boundaries


def render_html(data: dict, boundaries: dict) -> str:
    """Inline the payload into the single-file Leaflet template (token replacement, no str.format)."""
    return (HTML_TEMPLATE
            .replace("__NOWCAST_DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
            .replace("__NOWCAST_BOUNDARIES__", json.dumps(boundaries, ensure_ascii=False, separators=(",", ":")))
            .replace("__GENERATED__", data["generated"]))


# ---------------------------------------------------------------------------------- HTML template
# Structured like the site's usa.html: <!doctype html>, html/body 100%, #map absolute-fill, Leaflet
# 1.9.3 CSS+JS from cdn.jsdelivr.net (the site's exact version/CDN). Everything else is inlined.
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>HERO — Admin-1 Nowcast Map</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.9.3/dist/leaflet.css"/>
<script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.3/dist/leaflet.js"></script>
<style>
  :root{
    --ink:#1a1a2e; --muted:#5a5a6e; --panel:#ffffffee; --panel-brd:#0000001a;
    --bg:#eef0ee; --nodata:#d9d9d9; --nodata-brd:#b9b9b9; --actual:#1a1a2e; --nowcast:#0077b6;
    --shadow:0 2px 12px #0000001f; --grid:#0000001a;
  }
  @media (prefers-color-scheme: dark){
    :root{ --ink:#e9e9f0; --muted:#a6a6b8; --panel:#22232bec; --panel-brd:#ffffff1f;
      --bg:#15161c; --nodata:#3a3b45; --nodata-brd:#4c4d59; --actual:#e9e9f0; --nowcast:#4cb3e0;
      --shadow:0 2px 14px #0000005a; --grid:#ffffff1f; }
  }
  html,body{width:100%;height:100%;margin:0;padding:0;}
  #map{position:absolute;top:0;bottom:0;left:0;right:0;background:var(--bg);
    font-family:"Segoe UI",Roboto,Helvetica,Arial,sans-serif;}
  .leaflet-container{background:var(--bg);}
  .panel{background:var(--panel);border:1px solid var(--panel-brd);border-radius:10px;
    box-shadow:var(--shadow);color:var(--ink);backdrop-filter:blur(3px);}
  #titlebar{position:absolute;top:12px;left:12px;z-index:1000;padding:10px 12px;max-width:280px;}
  #titlebar h1{margin:0 0 2px;font-size:15px;font-weight:700;letter-spacing:.2px;}
  #titlebar p{margin:0 0 8px;font-size:11px;color:var(--muted);line-height:1.35;}
  #country{width:100%;font-size:13px;padding:5px 6px;border-radius:6px;
    border:1px solid var(--panel-brd);background:transparent;color:var(--ink);}
  #legend{position:absolute;bottom:16px;left:12px;z-index:1000;padding:9px 11px;font-size:11px;}
  #legend .ttl{font-weight:600;margin-bottom:6px;color:var(--ink);}
  #legend .row{display:flex;align-items:center;gap:7px;margin:3px 0;color:var(--muted);}
  #legend .sw{width:16px;height:12px;border-radius:2px;border:1px solid #00000022;}
  #trend{position:absolute;top:12px;right:12px;z-index:1000;width:360px;padding:12px 13px;
    display:none;}
  #trend .hd{display:flex;justify-content:space-between;align-items:baseline;gap:8px;}
  #trend .hd b{font-size:14px;}
  #trend .hd span{font-size:11px;color:var(--muted);}
  #trend .kpis{display:flex;gap:14px;margin:7px 0 4px;font-size:11px;color:var(--muted);}
  #trend .kpis b{display:block;font-size:15px;color:var(--ink);font-weight:700;}
  #trend .hint{margin:2px 0 0;font-size:10.5px;color:var(--muted);}
  #adm2{position:absolute;bottom:16px;right:12px;z-index:1000;width:250px;padding:11px 12px;
    display:none;font-size:11.5px;color:var(--muted);line-height:1.4;}
  #adm2 b{color:var(--ink);}
  #adm2 button, #trend button.back{margin-top:8px;font-size:11px;padding:4px 9px;cursor:pointer;
    border-radius:6px;border:1px solid var(--panel-brd);background:transparent;color:var(--ink);}
  .lg{fill:var(--muted);font-size:9px;}
  .axline{stroke:var(--grid);stroke-width:1;}
</style>
</head>
<body>
<div id="map"></div>

<div id="titlebar" class="panel">
  <h1>Latest nowcast — IPC Phase 3+</h1>
  <p>Admin-1 areas coloured by their most recent <b>nowcasted</b> % of population in Crisis+ (IPC 3+).
     Hover an area for its trend; click to zoom in and drill into admin-2 (Cameroon &amp; DR Congo
     so far). <span id="gen"></span></p>
  <select id="country"></select>
</div>

<div id="legend" class="panel"></div>

<div id="trend" class="panel">
  <div class="hd"><b id="t-name"></b><span id="t-sub"></span></div>
  <div class="kpis">
    <div>last assessment<b id="t-actual">—</b></div>
    <div>latest nowcast<b id="t-nowcast">—</b></div>
    <div>change<b id="t-delta">—</b></div>
  </div>
  <div id="t-svg"></div>
  <p class="hint">Solid = observed IPC · line = walk-forward nowcast · dotted = last assessment → latest nowcast</p>
</div>

<div id="adm2" class="panel">
  <b id="a2-name"></b><br/>
  <span id="a2-hint"></span>
  <br/><button id="a2-back">← Back to country</button>
</div>

<script>
const NOWCAST_DATA = __NOWCAST_DATA__;
const NOWCAST_BOUNDARIES = __NOWCAST_BOUNDARIES__;

const RAMP = NOWCAST_DATA.ramp, BINS = NOWCAST_DATA.bins;
const NODATA = getCSS('--nodata'), NODATA_BRD = getCSS('--nodata-brd');
function getCSS(v){ return getComputedStyle(document.documentElement).getPropertyValue(v).trim(); }
function colorFor(v){
  if(v==null) return NODATA;
  for(let i=0;i<BINS.length;i++){ if(v<BINS[i]) return RAMP[i]; }
  return RAMP[RAMP.length-1];
}

const map = L.map('map',{zoomControl:true, attributionControl:false, minZoom:2});
let layer=null, adm2Layer=null, highlightOutline=null, currentIso=null;
// Outline-only, non-interactive: a normal (interactive) polygon still captures hover/click across its
// whole fill even at fillOpacity:0 (Leaflet's .leaflet-interactive CSS sets pointer-events:auto, which
// hit-tests the shape regardless of paint) — so the "which admin-1 am I in" ring has to be a *separate*,
// `interactive:false` layer, never the original clickable admin-1 polygon, or it blocks the admin-2 layer
// underneath it once brought to front.
const SELECTED_STYLE = {weight:4, color:'#2b8cff', fillOpacity:0, opacity:1, interactive:false};

// ---- country selector
const sel = document.getElementById('country');
for(const iso in NOWCAST_DATA.countries){
  const o=document.createElement('option'); o.value=iso;
  o.textContent=NOWCAST_DATA.countries[iso].name; sel.appendChild(o);
}
sel.addEventListener('change', ()=>loadCountry(sel.value));
document.getElementById('gen').textContent = 'Generated '+NOWCAST_DATA.generated+'.';

function areaFor(iso, f){
  const pc = f.properties.adm1_pcode;
  return (NOWCAST_DATA.countries[iso].areas||{})[pc] || {name:f.properties.adm1_name, value:null, series:[]};
}
function styleFeature(iso){
  return f => ({ fillColor: colorFor(areaFor(iso,f).value),
    weight:1, color:'#ffffff', fillOpacity:0.85, opacity:0.9 }); }

function onEachFeature(iso){
  return (f, lyr)=>{
    const a = areaFor(iso, f);
    lyr.on('mouseover', e=>{ e.target.setStyle({weight:2.5, color:'#333'}); e.target.bringToFront();
      showTrend(a); });
    lyr.on('mouseout',  e=>{ layer.resetStyle(e.target); });
    lyr.on('click',     ()=>{ map.fitBounds(lyr.getBounds(), {padding:[20,20]}); showAdm2(iso, f); });
  };
}

function loadCountry(iso){
  currentIso = iso;
  if(layer) map.removeLayer(layer);
  if(adm2Layer){ map.removeLayer(adm2Layer); adm2Layer=null; }
  if(highlightOutline){ map.removeLayer(highlightOutline); highlightOutline=null; }
  layer = L.geoJSON(NOWCAST_BOUNDARIES[iso], {style:styleFeature(iso), onEachFeature:onEachFeature(iso)});
  layer.addTo(map);
  map.fitBounds(layer.getBounds(), {padding:[20,20]});
  document.getElementById('trend').style.display='none';
  document.getElementById('adm2').style.display='none';
  buildLegend();
}

// ---- legend
function buildLegend(){
  const el=document.getElementById('legend');
  const lo=[0,...BINS], hi=[...BINS,''];
  let rows='<div class="ttl">% in IPC Phase 3+</div>';
  for(let i=0;i<RAMP.length;i++){
    const label = hi[i]==='' ? (lo[i]+'+') : (lo[i]+'–'+hi[i]);
    rows += `<div class="row"><span class="sw" style="background:${RAMP[i]}"></span>${label}%</div>`;
  }
  rows += `<div class="row"><span class="sw" style="background:${NODATA};border-color:${NODATA_BRD}"></span>no data</div>`;
  el.innerHTML=rows;
}

// ---- adm2 drill-down (real layer for CMR/COD; "not available" panel for AFG/SOM)
function areaForAdm2(iso, f){
  const pc = f.properties.adm2_pcode;
  const rec = (NOWCAST_DATA.adm2 && NOWCAST_DATA.adm2[iso] && NOWCAST_DATA.adm2[iso].areas || {})[pc];
  return rec || {name:f.properties.adm2_name, pcode:pc, value:null, series:[]};
}
function styleAdm2Feature(iso){
  return f => ({ fillColor: colorFor(areaForAdm2(iso,f).value),
    weight:1, color:'#ffffff', fillOpacity:0.85, opacity:0.9 }); }
function onEachAdm2Feature(iso){
  return (f, lyr)=>{
    const a = areaForAdm2(iso, f);
    lyr.on('mouseover', e=>{ e.target.setStyle({weight:2.5, color:'#333'}); e.target.bringToFront();
      showTrend(a); });
    lyr.on('mouseout',  e=>{ adm2Layer.resetStyle(e.target); });
  };
}

function showAdm2(iso, adm1Feature){
  const pcode = adm1Feature.properties.adm1_pcode;
  document.getElementById('a2-name').textContent = adm1Feature.properties.adm1_name || '';
  const hint = document.getElementById('a2-hint');
  if(adm2Layer){ map.removeLayer(adm2Layer); adm2Layer=null; }
  if(highlightOutline){ map.removeLayer(highlightOutline); highlightOutline=null; }

  // Non-interactive outline of just the clicked province — visual only, never blocks the admin-2 layer.
  highlightOutline = L.geoJSON(adm1Feature, {interactive:false, style:()=>SELECTED_STYLE});
  highlightOutline.addTo(map);

  const fc = NOWCAST_BOUNDARIES.adm2 && NOWCAST_BOUNDARIES.adm2[iso];
  if(!fc){
    hint.textContent = 'Admin-2 breakdown is not available yet for this country.';
    document.getElementById('adm2').style.display='block';
    return;
  }
  const sub = { type:'FeatureCollection', features: fc.features.filter(f=>f.properties.adm1_pcode===pcode) };
  if(sub.features.length===0){
    hint.textContent = 'No admin-2 areas found for this province.';
    document.getElementById('adm2').style.display='block';
    return;
  }
  hint.textContent = sub.features.length + ' admin-2 areas — hover for trend, click Back to return.';
  adm2Layer = L.geoJSON(sub, {style:styleAdm2Feature(iso), onEachFeature:onEachAdm2Feature(iso)});
  adm2Layer.addTo(map);
  highlightOutline.bringToFront();   // outline ring stays visible above the new layer
  map.fitBounds(adm2Layer.getBounds(), {padding:[20,20]});
  document.getElementById('adm2').style.display='block';
}
document.getElementById('a2-back').addEventListener('click', ()=>{
  if(adm2Layer){ map.removeLayer(adm2Layer); adm2Layer=null; }
  if(highlightOutline){ map.removeLayer(highlightOutline); highlightOutline=null; }
  map.fitBounds(layer.getBounds(), {padding:[20,20]});
  document.getElementById('adm2').style.display='none';
  document.getElementById('trend').style.display='none';
});

// ---- trend panel + inline SVG sparkline
function fmt(v){ return v==null ? '—' : v.toFixed(1)+'%'; }
function showTrend(a){
  const box=document.getElementById('trend'); box.style.display='block';
  document.getElementById('t-name').textContent = a.name || '—';
  document.getElementById('t-sub').textContent  = a.pcode || '';
  const la=a.latest_actual, ln=a.latest_nowcast;
  document.getElementById('t-actual').textContent  = la ? fmt(la.value) : '—';
  document.getElementById('t-nowcast').textContent = ln ? fmt(ln.value) : '—';
  let delta='—';
  if(la && ln){ const d=ln.value-la.value; delta=(d>=0?'▲ +':'▼ ')+d.toFixed(1)+'pp'; }
  document.getElementById('t-delta').textContent = delta;
  document.getElementById('t-svg').innerHTML = sparkline(a);
}

function sparkline(a){
  const W=336, H=150, padL=30, padR=10, padT=10, padB=20;
  const s=(a.series||[]).filter(d=>d.actual!=null || d.nowcast!=null);
  if(s.length<2) return `<svg width="${W}" height="${H}"><text x="12" y="24" class="lg">Insufficient history</text></svg>`;
  const ts=s.map(d=>Date.parse(d.date));
  const tmin=Math.min(...ts), tmax=Math.max(...ts);
  const vals=[]; s.forEach(d=>{ if(d.actual!=null)vals.push(d.actual); if(d.nowcast!=null)vals.push(d.nowcast); });
  const ymax=Math.max(50, Math.ceil(Math.max(...vals)/10)*10);
  const X=t=>padL+(tmax===tmin?0:(t-tmin)/(tmax-tmin))*(W-padL-padR);
  const Y=v=>H-padB-(v/ymax)*(H-padT-padB);
  const path=pts=>pts.map((p,i)=>(i?'L':'M')+X(p.t).toFixed(1)+' '+Y(p.v).toFixed(1)).join(' ');

  const aPts=s.filter(d=>d.actual!=null).map(d=>({t:Date.parse(d.date),v:d.actual}));
  const nPts=s.filter(d=>d.nowcast!=null).map(d=>({t:Date.parse(d.date),v:d.nowcast}));

  // y gridlines + labels (0, mid, max)
  let g='';
  [0, ymax/2, ymax].forEach(v=>{
    const y=Y(v).toFixed(1);
    g+=`<line class="axline" x1="${padL}" y1="${y}" x2="${W-padR}" y2="${y}"/>`;
    g+=`<text class="lg" x="2" y="${(+y+3).toFixed(1)}">${v}</text>`;
  });
  // year labels
  const y0=new Date(tmin).getFullYear(), y1=new Date(tmax).getFullYear();
  for(let y=y0;y<=y1;y++){ const t=Date.parse(y+'-01-01'); if(t<tmin||t>tmax)continue;
    g+=`<text class="lg" x="${X(t).toFixed(1)}" y="${H-6}" text-anchor="middle">${y}</text>`; }

  const nowcast = nPts.length ? `<path d="${path(nPts)}" fill="none" stroke="var(--nowcast)" stroke-width="2"/>` : '';
  const actual  = `<path d="${path(aPts)}" fill="none" stroke="var(--actual)" stroke-width="1.8"/>`;
  const dots    = aPts.map(p=>`<circle cx="${X(p.t).toFixed(1)}" cy="${Y(p.v).toFixed(1)}" r="2.1" fill="var(--actual)"/>`).join('');

  // dotted connector: last observed assessment -> latest nowcast
  let conn='';
  const la=a.latest_actual, ln=a.latest_nowcast;
  if(la && ln){
    conn=`<line x1="${X(Date.parse(la.date)).toFixed(1)}" y1="${Y(la.value).toFixed(1)}"
      x2="${X(Date.parse(ln.date)).toFixed(1)}" y2="${Y(ln.value).toFixed(1)}"
      stroke="var(--nowcast)" stroke-width="1.6" stroke-dasharray="3 3"/>`
      + `<circle cx="${X(Date.parse(ln.date)).toFixed(1)}" cy="${Y(ln.value).toFixed(1)}" r="3.4"
         fill="var(--bg)" stroke="var(--nowcast)" stroke-width="2"/>`;
  }
  return `<svg width="${W}" height="${H}">${g}${nowcast}${actual}${conn}${dots}</svg>`;
}

loadCountry(Object.keys(NOWCAST_DATA.countries)[0]);
</script>
</body>
</html>
"""


def main():
    dataset = sys.argv[1] if len(sys.argv) > 1 else "imputed"
    assert dataset in config.DATASETS, f"dataset must be one of {list(config.DATASETS)}"
    assert config.LEVEL == "adm1", "nowcast map is admin-1 only; run without HERO_LEVEL=adm2"

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[export_nowcast_map / {dataset}] building walk-forward panel ...")
    panel = build_nowcast_panel(dataset)
    print("join coverage:")
    data, boundaries = build_payload(panel, dataset)
    data["adm2"], boundaries["adm2"] = load_adm2_layer()
    OUT_HTML.write_text(render_html(data, boundaries), encoding="utf-8")
    kb = OUT_HTML.stat().st_size / 1024
    print(f"Wrote {OUT_HTML}  ({kb:.0f} KB)  countries={list(data['countries'])}")


if __name__ == "__main__":
    main()
