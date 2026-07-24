import os
import glob
import json
import pandas as pd
from pathlib import Path

def process_and_plot_evolution(csv_path):
    print(f"\nElaborazione di: {csv_path}")
    df = pd.read_csv(csv_path)
    
    keyword_col = None
    if 'country' in df.columns and 'period' in df.columns:
        node_col = 'country'
        time_col = 'period'
        if 'km_label' in df.columns:
            cluster_col = 'km_label'
            keyword_col = 'km_keywords' if 'km_keywords' in df.columns else None
        else:
            cluster_col = 'hd_label'
            keyword_col = 'hd_keywords' if 'hd_keywords' in df.columns else None
    elif 'paese' in df.columns and 'inizio_periodo' in df.columns:
        node_col = 'paese'
        time_col = 'inizio_periodo'
        if 'label_kmeans' in df.columns:
            cluster_col = 'label_kmeans'
        elif 'cluster_kmeans' in df.columns:
            cluster_col = 'cluster_kmeans'
        else:
            cluster_col = [c for c in df.columns if 'cluster' in c or 'label' in c][0]
    else:
        print(f"Formato colonne non riconosciuto per {csv_path}")
        return

    if keyword_col:
        def get_short_keywords(k):
            words = [w.strip() for w in str(k).split(',')]
            return ", ".join(words[:3])
        df[cluster_col] = "C" + df[cluster_col].astype(str) + " (" + df[keyword_col].apply(get_short_keywords) + ")"

    time_strings = df[time_col].apply(lambda x: str(x).split('/')[0].strip())
    df['sortable_time'] = pd.to_datetime(time_strings, format='%b %Y', errors='coerce')
    
    if df['sortable_time'].isna().all():
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            df['sortable_time'] = pd.to_datetime(time_strings, errors='coerce')
            
    df = df.dropna(subset=['sortable_time', node_col, cluster_col])
    df['Year'] = df['sortable_time'].dt.year
    df = df[df[cluster_col] != -1]
    
    year_country_cluster = df.groupby(['Year', node_col])[cluster_col].agg(
        lambda x: pd.Series.mode(x).iloc[0] if len(pd.Series.mode(x)) > 0 else list(x)[0]
    ).reset_index()
    
    years = sorted(int(y) for y in year_country_cluster['Year'].unique())
    if len(years) < 2:
        print("Meno di due anni di dati validi.")
        return

    countries = sorted(list(year_country_cluster[node_col].unique()))
    clusters = sorted(list(year_country_cluster[cluster_col].unique()))
    
    records = []
    for _, row in year_country_cluster.iterrows():
        records.append({
            "country": str(row[node_col]),
            "year": int(row['Year']),
            "cluster": str(row[cluster_col])
        })
    
    palette = [
        '#6366f1','#10b981','#f59e0b','#ef4444','#a855f7','#06b6d4',
        '#ec4899','#84cc16','#f97316','#14b8a6','#8b5cf6','#3b82f6',
        '#22c55e','#e11d48','#eab308','#0ea5e9','#d946ef','#60a5fa',
        '#34d399','#f87171','#fbbf24','#818cf8','#4ade80','#fb923c',
        '#2dd4bf','#c084fc','#38bdf8','#a3e635','#fb7185','#facc15'
    ]
    colors = {c: palette[i % len(palette)] for i, c in enumerate(clusters)}

    raw_data = {
        "years": years,
        "countries": countries,
        "clusters": clusters,
        "records": records,
        "colors": colors,
        "filename": Path(csv_path).name
    }
    
    html_template = r"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<title>Cluster Evolution – {FILENAME}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
:root {
    --bg-main: #0b0f19;
    --bg-card: rgba(17, 24, 39, 0.7);
    --bg-card-hover: rgba(26, 36, 56, 0.85);
    --border-color: rgba(255, 255, 255, 0.06);
    --border-hover: rgba(255, 255, 255, 0.12);
    --text-primary: #f8fafc;
    --text-secondary: #94a3b8;
    --text-muted: #64748b;
    --color-primary: #6366f1;
    --color-primary-glow: rgba(99, 102, 241, 0.15);
    --color-success: #10b981;
    --color-warning: #f59e0b;
    --color-danger: #ef4444;
    --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    --font-title: 'Outfit', sans-serif;
}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:var(--font-sans);background:var(--bg-main);color:var(--text-primary);height:100vh;overflow:hidden}

.app{display:flex;height:100vh}

/* --- SIDEBAR --- */
.side{
    width:300px;min-width:300px;
    background:var(--bg-card);backdrop-filter:blur(12px);
    border-right:1px solid var(--border-color);
    display:flex;flex-direction:column;z-index:10;
}
.side-head{
    padding:24px 22px 20px;border-bottom:1px solid var(--border-color);
    background:linear-gradient(180deg, rgba(99,102,241,0.08) 0%, transparent 100%);
}
.side-head h1{font-family:var(--font-title);font-size:24px;font-weight:700;color:var(--text-primary)}
.side-head p{font-size:15px;color:var(--text-secondary);margin-top:4px}

.side-block{padding:16px 22px;border-bottom:1px solid var(--border-color);display:flex;flex-direction:column;overflow:hidden}
.side-block h3{
    font-family:var(--font-title);font-size:14px;text-transform:uppercase;
    letter-spacing:1.4px;color:var(--text-muted);margin-bottom:10px;font-weight:600;
}

.sinput{
    width:100%;padding:12px 16px;
    background:rgba(15,23,42,0.6);border:1px solid var(--border-color);
    border-radius:12px;font-size:16px;outline:none;font-family:inherit;
    color:var(--text-primary);transition:all .2s;
}
.sinput:focus{border-color:var(--color-primary);box-shadow:0 0 0 3px var(--color-primary-glow)}
.sinput::placeholder{color:var(--text-muted)}

.clist{flex:1;overflow-y:auto;margin-top:8px;min-height:0}
.citem{
    padding:8px 12px;border-radius:8px;cursor:pointer;font-size:17px;
    color:var(--text-secondary);transition:all .2s;display:flex;align-items:center;gap:10px;
}
.citem:hover{background:var(--bg-card-hover);color:var(--text-primary)}
.citem.on{
    background:linear-gradient(135deg, rgba(99,102,241,0.25), rgba(168,85,247,0.2));
    color:#fff;font-weight:600;border:1px solid rgba(99,102,241,0.3);
}
.citem .flag{font-size:22px;line-height:1}

/* trajectory panel */
.tpanel{padding:16px 22px;border-bottom:1px solid var(--border-color);display:none}
.tpanel.vis{display:block;background:linear-gradient(180deg, rgba(245,158,11,0.06) 0%, transparent 100%)}
.tpanel h3{font-family:var(--font-title);font-size:18px;font-weight:700;color:var(--color-warning);margin-bottom:10px;display:flex;align-items:center;gap:8px}
.tpanel h3 .flag{font-size:24px}
.tstep{display:flex;align-items:center;gap:8px;padding:6px 0}
.tstep .ty{font-family:var(--font-title);color:var(--text-muted);font-weight:600;font-size:16px;min-width:44px}
.tstep .tc{padding:6px 14px;border-radius:6px;color:#fff;font-weight:500;font-size:15px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:200px}

/* --- MAIN AREA --- */
.main{flex:1;display:flex;flex-direction:column;overflow:hidden}

/* Chart layout: sticky cluster col + scrollable chart */
.chart-wrap{flex:1;overflow:auto;position:relative}
.chart-inner{display:flex;position:relative}

/* Sticky cluster column */
.cluster-col{
    position:sticky;left:0;z-index:5;
    background:var(--bg-main);
    border-right:1px solid var(--border-color);
    flex-shrink:0;
}
.cluster-col .year-header{
    height:60px;display:flex;align-items:center;justify-content:center;
    border-bottom:1px solid var(--border-color);
    padding:0 16px;
}
.cluster-col .year-header span{
    font-family:var(--font-title);font-size:13px;text-transform:uppercase;
    letter-spacing:1.2px;color:var(--text-muted);font-weight:600;
}
.crow{
    display:flex;align-items:center;gap:10px;padding:0 16px;
    cursor:pointer;transition:all .2s;border-bottom:1px solid rgba(255,255,255,0.02);
    user-select:none;
}
.crow:hover{background:rgba(255,255,255,0.03)}
.crow.off{opacity:0.3}
.crow .cdot{width:16px;height:16px;border-radius:4px;flex-shrink:0;transition:all .2s}
.crow.off .cdot{opacity:0.3;filter:grayscale(1)}
.crow .ceye{color:var(--text-muted);font-size:18px;flex-shrink:0;width:24px;text-align:center;transition:all .2s}
.crow.off .ceye{opacity:0.3}
.crow .cname{font-size:18px;color:var(--text-secondary);transition:color .2s;line-height:1.35}
.crow:hover .cname{color:var(--text-primary)}
.crow.off .cname{color:var(--text-muted);text-decoration:line-through}

/* Chart SVG area */
.chart-svg{flex:1}

/* tooltip */
.tip{
    position:fixed;background:var(--bg-card);backdrop-filter:blur(16px);
    border:1px solid var(--border-hover);border-radius:16px;
    padding:16px 20px;pointer-events:none;z-index:999;max-width:380px;
    box-shadow:0 20px 48px rgba(0,0,0,0.45);display:none;font-size:15px;line-height:1.6;
}
.tip .th{font-family:var(--font-title);font-weight:700;color:var(--text-primary);margin-bottom:6px;font-size:17px}
.tip .ts{color:var(--text-muted);font-size:15px;margin-bottom:10px}
.tip .tc{display:flex;flex-wrap:wrap;gap:6px}
.tip .tc span{
    background:rgba(99,102,241,0.12);border:1px solid rgba(99,102,241,0.15);
    padding:4px 12px;border-radius:6px;font-size:14px;color:var(--text-secondary);
}
.tip .tc span .flag{font-size:17px;margin-right:4px}

::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:#1e293b;border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:#334155}
</style>
</head>
<body>
<div class="app">
<div class="side">
 <div class="side-head">
  <h1>Cluster Evolution</h1>
  <p>{FILENAME}</p>
 </div>
 <div class="side-block" style="flex:1;overflow-y:auto">
  <h3>Cerca Paese</h3>
  <input class="sinput" id="sInput" placeholder="Digita per filtrare..." oninput="filterC()">
  <div class="clist" id="cList"></div>
 </div>
 <div class="tpanel" id="tPanel">
  <h3 id="tTitle"></h3>
  <div id="tSteps"></div>
 </div>
</div>

<div class="main">
 <div class="chart-wrap" id="chartWrap">
  <div class="chart-inner" id="chartInner">
   <div class="cluster-col" id="clusterCol"></div>
   <div class="chart-svg" id="chartSvg"></div>
  </div>
 </div>
</div>
</div>
<div class="tip" id="tip"></div>

<script>
const D={RAW_DATA_JSON};
let sel=null, enK=new Set(D.clusters);

// --- FLAG MAPPING ---
const ISO={
"Afghanistan":"AF","Albania":"AL","Algeria":"DZ","Angola":"AO","Argentina":"AR",
"Armenia":"AM","Azerbaijan":"AZ","Bangladesh":"BD","Belarus":"BY","Benin":"BJ",
"Bhutan":"BT","Bolivia":"BO","Bosnia and Herzegovina":"BA","Botswana":"BW","Brazil":"BR",
"Burkina Faso":"BF","Burundi":"BI","Cabo Verde":"CV","Cambodia":"KH","Cameroon":"CM",
"Central African Republic":"CF","Chad":"TD","Chile":"CL","China":"CN","Colombia":"CO",
"Comoros":"KM","Congo":"CG","Costa Rica":"CR","Croatia":"HR",
"Cuba":"CU","Cyprus":"CY","Djibouti":"DJ",
"Democratic Republic of the Congo":"CD","Dominican Republic":"DO","Ecuador":"EC","Egypt":"EG",
"El Salvador":"SV","Equatorial Guinea":"GQ","Eritrea":"ER","Eswatini":"SZ","Ethiopia":"ET",
"Fiji":"FJ","Gambia":"GM","Georgia":"GE","Ghana":"GH","Guatemala":"GT","Guinea":"GN",
"Guinea-Bissau":"GW","Haiti":"HT","Honduras":"HN","India":"IN","Indonesia":"ID","Iran":"IR",
"Iraq":"IQ","Israel":"IL","Ivory Coast":"CI","Jamaica":"JM","Jordan":"JO","Kazakhstan":"KZ",
"Kenya":"KE","Kyrgyzstan":"KG","Lao People's Democratic Republic":"LA","Laos":"LA",
"Lebanon":"LB","Lesotho":"LS","Liberia":"LR","Libya":"LY","Madagascar":"MG","Malawi":"MW",
"Mali":"ML","Mauritania":"MR","Mexico":"MX","Moldova":"MD","Mongolia":"MN","Morocco":"MA",
"Mozambique":"MZ","Myanmar":"MM","Namibia":"NA","Nepal":"NP","Nicaragua":"NI","Niger":"NE",
"Nigeria":"NG","North Korea":"KP","Pakistan":"PK","Palestine":"PS","Panama":"PA",
"Papua New Guinea":"PG","Paraguay":"PY","Peru":"PE","Philippines":"PH","Rwanda":"RW",
"Sao Tome and Principe":"ST","Senegal":"SN","Sierra Leone":"SL","Somalia":"SO",
"South Africa":"ZA","South Sudan":"SS","Sri Lanka":"LK","Sudan":"SD","Suriname":"SR",
"Syria":"SY","Syrian Arab Republic":"SY","Tajikistan":"TJ","Tanzania":"TZ",
"Thailand":"TH","Timor-Leste":"TL","Togo":"TG","Trinidad and Tobago":"TT","Tunisia":"TN",
"Turkey":"TR","Turkiye":"TR","Türkiye":"TR","Uganda":"UG","Ukraine":"UA",
"United Republic of Tanzania":"TZ","Uruguay":"UY","Uzbekistan":"UZ","Venezuela":"VE",
"Viet Nam":"VN","Vietnam":"VN","Yemen":"YE","Zambia":"ZM","Zimbabwe":"ZW",
"Cote d'Ivoire":"CI","Côte d'Ivoire":"CI","State of Palestine":"PS",
"Congo, Democratic Republic of the":"CD","Tanzania, United Republic of":"TZ",
"Iran, Islamic Republic of":"IR","Korea, Democratic People's Republic of":"KP"
};
function getFlag(name){
 const code=ISO[name];
 if(!code)return '';
 return String.fromCodePoint(...[...code.toUpperCase()].map(c=>0x1F1E6+c.charCodeAt(0)-65));
}

// --- SIDEBAR ---
(function(){
 const cl=document.getElementById('cList');
 D.countries.forEach(c=>{
  const d=document.createElement('div');
  d.className='citem';d.dataset.c=c;
  const fl=document.createElement('span');fl.className='flag';fl.textContent=getFlag(c);
  const tx=document.createElement('span');tx.textContent=c;
  d.appendChild(fl);d.appendChild(tx);
  d.onclick=()=>pickC(c);
  cl.appendChild(d);
 });
})();

function filterC(){
 const q=document.getElementById('sInput').value.toLowerCase();
 document.querySelectorAll('.citem').forEach(e=>{e.style.display=e.dataset.c.toLowerCase().includes(q)?'':'none'});
}

function pickC(c){
 sel=sel===c?null:c;
 document.querySelectorAll('.citem').forEach(e=>e.classList.toggle('on',e.dataset.c===sel));
 updTraj();draw();
}

function updTraj(){
 const p=document.getElementById('tPanel'),s=document.getElementById('tSteps'),t=document.getElementById('tTitle');
 if(!sel){p.classList.remove('vis');return}
 p.classList.add('vis');
 t.innerHTML='<span class="flag">'+getFlag(sel)+'</span> '+escH(sel);
 const recs=D.records.filter(r=>r.country===sel&&enK.has(r.cluster)).sort((a,b)=>a.year-b.year);
 s.innerHTML='';
 recs.forEach(r=>{
  const d=document.createElement('div');d.className='tstep';
  const sn=r.cluster.length>28?r.cluster.substring(0,26)+'\u2026':r.cluster;
  d.innerHTML='<span class="ty">'+r.year+'</span><span class="tc" style="background:'+D.colors[r.cluster]+'" title="'+escH(r.cluster)+'">'+escH(sn)+'</span>';
  s.appendChild(d);
 });
 if(!recs.length)s.innerHTML='<div style="color:var(--text-muted);font-size:13px;padding:6px 0">Nessun dato nei cluster attivi.</div>';
}

function escH(s){const d=document.createElement('div');d.textContent=s;return d.innerHTML}

// tooltip
const tipEl=document.getElementById('tip');
function showTip(ev,html){tipEl.innerHTML=html;tipEl.style.display='block';const r=tipEl.getBoundingClientRect();let x=ev.clientX+16,y=ev.clientY+16;if(x+r.width>innerWidth-12)x=ev.clientX-r.width-16;if(y+r.height>innerHeight-12)y=ev.clientY-r.height-16;tipEl.style.left=x+'px';tipEl.style.top=y+'px'}
function hideTip(){tipEl.style.display='none'}

// --- MAIN RENDER ---
function draw(){
 const filt=D.records.filter(r=>enK.has(r.cluster));
 const byY={};D.years.forEach(y=>byY[y]={});
 filt.forEach(r=>{if(!byY[r.year])return;if(!byY[r.year][r.cluster])byY[r.year][r.cluster]=[];byY[r.year][r.cluster].push(r.country)});

 const vis=[...enK].sort();
 const colW=220, rowH=Math.max(70, Math.min(140, 1000/(D.clusters.length||1)));
 const yearHeaderH=60;

 // --- BUILD STICKY CLUSTER COLUMN ---
 const ccol=document.getElementById('clusterCol');
 let colHtml='<div class="year-header"><span>Cluster</span></div>';
 D.clusters.forEach(c=>{
  const isOn=enK.has(c);
  const col=D.colors[c]||'#475569';
  colHtml+='<div class="crow'+(isOn?'':' off')+'" data-cluster="'+btoa(unescape(encodeURIComponent(c)))+'" style="height:'+rowH+'px" title="'+escH(c)+'">';
  colHtml+='<span class="ceye">'+(isOn?'\u25C9':'\u25CB')+'</span>';
  colHtml+='<span class="cdot" style="background:'+col+'"></span>';
  colHtml+='<span class="cname">'+escH(c)+'</span>';
  colHtml+='</div>';
 });
 ccol.innerHTML=colHtml;
 ccol.style.width='300px';

 // Attach click handlers to cluster rows
 ccol.querySelectorAll('.crow').forEach(row=>{
  row.addEventListener('click',()=>{
   const cName=decodeURIComponent(escape(atob(row.dataset.cluster)));
   if(enK.has(cName)){enK.delete(cName);row.classList.add('off');row.classList.remove('on');}
   else{enK.add(cName);row.classList.remove('off');row.classList.add('on');}
   updTraj();draw();
  });
 });

 // --- BUILD SVG ---
 const svgW=D.years.length*colW+60;
 const svgH=yearHeaderH+D.clusters.length*rowH+40;
 const yOf={};
 D.clusters.forEach((c,i)=>{yOf[c]=yearHeaderH+i*rowH+rowH/2});

 let s='<svg width="'+svgW+'" height="'+svgH+'" xmlns="http://www.w3.org/2000/svg" style="font-family:Inter,system-ui,sans-serif">';
 s+='<defs><filter id="glow"><feGaussianBlur stdDeviation="5" result="b"/><feComposite in="SourceGraphic" in2="b" operator="over"/></filter>';
 s+='<filter id="ds"><feDropShadow dx="0" dy="3" stdDeviation="4" flood-opacity="0.3" flood-color="#000"/></filter></defs>';
 s+='<rect width="'+svgW+'" height="'+svgH+'" fill="var(--bg-main)"/>';

 // alternating bands
 D.clusters.forEach((c,i)=>{
  if(i%2===0) s+='<rect x="0" y="'+(yearHeaderH+i*rowH)+'" width="'+svgW+'" height="'+rowH+'" fill="rgba(255,255,255,0.015)"/>';
  // horiz guide
  const cy=yOf[c];
  s+='<line x1="0" y1="'+cy+'" x2="'+svgW+'" y2="'+cy+'" stroke="rgba(255,255,255,0.03)" stroke-width="1"/>';
 });

 // year labels + vertical guides
 D.years.forEach((y,i)=>{
  const x=i*colW+colW/2+30;
  s+='<line x1="'+x+'" y1="'+yearHeaderH+'" x2="'+x+'" y2="'+(svgH-20)+'" stroke="rgba(255,255,255,0.04)" stroke-width="1"/>';
  s+='<text x="'+x+'" y="36" text-anchor="middle" font-size="18" font-weight="700" fill="#64748b" font-family="Outfit,sans-serif">'+y+'</text>';
 });

 // flows
 let mxF=1;const flows=[];
 for(let i=0;i<D.years.length-1;i++){
  const y1=D.years[i],y2=D.years[i+1],d1=byY[y1],d2=byY[y2];
  for(const c1 of Object.keys(d1)){for(const c2 of Object.keys(d2)){
   const sh=d1[c1].filter(p=>d2[c2].includes(p));
   if(sh.length){flows.push({i,c1,c2,cs:sh,n:sh.length});if(sh.length>mxF)mxF=sh.length}
  }}
 }
 const th=n=>Math.max(2,Math.sqrt(n/mxF)*44);
 const hl=sel!==null;

 flows.forEach((f,fi)=>{
  const x1=f.i*colW+colW/2+30, x2=(f.i+1)*colW+colW/2+30;
  const cy1=yOf[f.c1],cy2=yOf[f.c2];
  if(cy1===undefined||cy2===undefined)return;
  const w=th(f.n),cx1=x1+colW*.4,cx2=x2-colW*.4;
  const col=D.colors[f.c1]||'#475569';
  let op=hl?0.04:0.2;
  if(hl&&f.cs.includes(sel))op=0.12;
  const fid='f'+fi;
  s+='<path id="'+fid+'" d="M'+x1+','+cy1+' C'+cx1+','+cy1+' '+cx2+','+cy2+' '+x2+','+cy2+'" fill="none" stroke="'+col+'" stroke-width="'+w+'" opacity="'+op+'" stroke-linecap="round" data-cs="'+f.cs.join('|')+'" data-c1="'+encodeURIComponent(f.c1)+'" data-c2="'+encodeURIComponent(f.c2)+'" data-n="'+f.n+'" onmousemove="sfTip(event,\''+fid+'\')" onmouseleave="hideTip()" style="cursor:pointer;transition:opacity .25s"/>';
 });

 // nodes
 D.years.forEach((y,yi)=>{
  const x=yi*colW+colW/2+30;
  Object.keys(byY[y]).forEach(c=>{
   if(!vis.includes(c))return;
   if(yOf[c]===undefined)return;
   const cy=yOf[c],cs=byY[y][c].sort(),n=cs.length;
   const col=D.colors[c]||'#475569';
   const r=Math.max(14,Math.min(32,6+Math.sqrt(n)*3.5));
   let op=hl?0.2:1;
   if(hl&&cs.includes(sel))op=1;
   const nid='n'+yi+'_'+D.clusters.indexOf(c);
   s+='<g id="'+nid+'" opacity="'+op+'" style="cursor:pointer;transition:opacity .25s" data-k="'+encodeURIComponent(c)+'" data-y="'+y+'" data-cs="'+cs.join('|')+'" onmousemove="snTip(event,\''+nid+'\')" onmouseleave="hideTip()">';
   s+='<circle cx="'+x+'" cy="'+cy+'" r="'+(r+4)+'" fill="'+col+'" fill-opacity=".06"/>';
   s+='<circle cx="'+x+'" cy="'+cy+'" r="'+r+'" fill="rgba(11,15,25,0.85)" stroke="'+col+'" stroke-width="2.5"/>';
   s+='<text x="'+x+'" y="'+(cy+1)+'" text-anchor="middle" dominant-baseline="middle" font-size="16" font-weight="700" fill="'+col+'" font-family="Outfit,sans-serif">'+n+'</text>';
   s+='</g>';
  });
 });

 // highlight path
 if(sel){
  const recs=filt.filter(r=>r.country===sel).sort((a,b)=>a.year-b.year);
  const pts=recs.map(r=>({x:D.years.indexOf(r.year)*colW+colW/2+30,y:yOf[r.cluster],yr:r.year,cl:r.cluster})).filter(p=>p.y!==undefined);
  if(pts.length>=2){
   let d='M'+pts[0].x+','+pts[0].y;
   for(let i=1;i<pts.length;i++){d+=' C'+(pts[i-1].x+colW*.4)+','+pts[i-1].y+' '+(pts[i].x-colW*.4)+','+pts[i].y+' '+pts[i].x+','+pts[i].y}
   s+='<path d="'+d+'" fill="none" stroke="#f59e0b" stroke-width="10" opacity=".25" stroke-linecap="round" filter="url(#glow)"><animate attributeName="opacity" values=".15;.35;.15" dur="2.5s" repeatCount="indefinite"/></path>';
   s+='<path d="'+d+'" fill="none" stroke="#f59e0b" stroke-width="4" stroke-linecap="round"/>';
   s+='<path d="'+d+'" fill="none" stroke="#fde68a" stroke-width="1.5" stroke-linecap="round"/>';
  }
  if(pts.length>0){
   pts.forEach(p=>{
    s+='<circle cx="'+p.x+'" cy="'+p.y+'" r="16" fill="#f59e0b" fill-opacity=".12" stroke="#f59e0b" stroke-width="2"/>';
    s+='<circle cx="'+p.x+'" cy="'+p.y+'" r="6" fill="#fbbf24" stroke="#0b0f19" stroke-width="2.5"/>';
   });
   const fp=pts[0];
   const label=getFlag(sel)+' '+sel;
   const lw=Math.max(100, label.length*8+20);
   s+='<rect x="'+(fp.x-lw/2)+'" y="'+(fp.y-40)+'" width="'+lw+'" height="28" rx="14" fill="#f59e0b" filter="url(#ds)"/>';
   s+='<text x="'+fp.x+'" y="'+(fp.y-22)+'" text-anchor="middle" font-size="15" font-weight="700" fill="#0b0f19" font-family="Outfit,sans-serif">'+escSvg(sel)+'</text>';
  }
 }

 s+='</svg>';
 document.getElementById('chartSvg').innerHTML=s;
}

function escSvg(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}

window.snTip=function(ev,id){
 const el=document.getElementById(id);if(!el)return;
 const k=decodeURIComponent(el.dataset.k),y=el.dataset.y,cs=el.dataset.cs.split('|').sort();
 let h='<div class="th">'+escH(k)+'</div><div class="ts">Anno: '+y+' \u00b7 '+cs.length+' paes'+(cs.length===1?'e':'i')+'</div><div class="tc">'+cs.map(c=>'<span><span class="flag">'+getFlag(c)+'</span>'+escH(c)+'</span>').join('')+'</div>';
 showTip(ev,h);
};
window.sfTip=function(ev,id){
 const el=document.getElementById(id);if(!el)return;
 const c1=decodeURIComponent(el.dataset.c1),c2=decodeURIComponent(el.dataset.c2),cs=el.dataset.cs.split('|').sort(),n=el.dataset.n;
 let h='<div class="th">'+n+' paes'+(n==1?'e':'i')+' in transizione</div><div class="ts">Da: '+escH(c1)+'<br>A: '+escH(c2)+'</div><div class="tc">'+cs.map(c=>'<span><span class="flag">'+getFlag(c)+'</span>'+escH(c)+'</span>').join('')+'</div>';
 showTip(ev,h);
};

draw();
</script>
</body>
</html>"""
    
    html_content = html_template.replace('{FILENAME}', raw_data['filename']).replace('{RAW_DATA_JSON}', json.dumps(raw_data))
    
    output_html = str(Path(csv_path).with_suffix('.html'))
    with open(output_html, 'w', encoding='utf-8') as f:
        f.write(html_content)
        
    print(f"-> Dashboard creata: {output_html}")
    
    try:
        import webbrowser
        webbrowser.open('file://' + os.path.realpath(output_html))
    except Exception:
        pass

if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    csv_files = glob.glob(os.path.join(current_dir, "*.csv"))
    
    if not csv_files:
        print("Nessun file CSV trovato nella cartella corrente.")
    else:
        for csv_file in csv_files:
            try:
                process_and_plot_evolution(csv_file)
            except Exception as e:
                print(f"Errore durante l'elaborazione di {Path(csv_file).name}: {e}")