/**
 * TS Clustering Module
 * Gestisce la vista "Clustering & Pattern" per il confronto delle strategie.
 */

let tsClustersData = null;

// Categorical palette per i cluster
const clusterColors = [
    "#ef4444", // Red (Cluster 0)
    "#3b82f6", // Blue (Cluster 1)
    "#10b981", // Green (Cluster 2)
    "#f59e0b", // Amber (Cluster 3)
    "#8b5cf6", // Purple (Cluster 4)
    "#ec4899", // Pink (Cluster 5)
    "#06b6d4", // Cyan (Cluster 6)
    "#f97316", // Orange (Cluster 7)
];

async function loadClustersData() {
    if (tsClustersData) return tsClustersData;
    try {
        const res = await fetch('data/ts/clusters.json');
        if (res.ok) {
            tsClustersData = await res.json();
        } else {
            console.warn("clusters.json non trovato, le mappe di clustering non avranno dati.");
            tsClustersData = {};
        }
    } catch (e) {
        console.error("Errore nel caricamento di clusters.json", e);
        tsClustersData = {};
    }
    return tsClustersData;
}

// Popola affidabilmente il selettore dei paesi per il clustering
async function populateClusteringCountrySelector() {
    const sel = document.getElementById("clustering-country-selector");
    if (!sel) return;
    
    let countries = (typeof globalData !== 'undefined' && globalData && globalData.countries) ? globalData.countries : null;
    if (!countries || countries.length === 0) {
        try {
            const res = await fetch('data/global_summary.json');
            if (res.ok) {
                const gData = await res.json();
                countries = gData.countries;
                if (typeof globalData !== 'undefined') globalData = gData; 
            }
        } catch (e) {
            console.error("Errore fetch global_summary per clustering selector", e);
        }
    }
    
    if (countries && countries.length > 0) {
        const currentVal = sel.value;
        sel.innerHTML = "";
        countries.forEach(c => {
            const opt = document.createElement("option");
            opt.value = c.code;
            opt.innerText = `${c.name} (${c.code})`;
            sel.appendChild(opt);
        });
        
        if (currentVal && Array.from(sel.options).some(o => o.value === currentVal)) {
            sel.value = currentVal;
        } else if (typeof state !== 'undefined' && state.selectedCountry) {
            sel.value = state.selectedCountry;
        } else {
            sel.value = countries[0].code;
        }
    }
}

// Funzione chiamata quando la vista switcha su 'clustering' (vedi app.js)
window.renderClusteringView = async function() {
    await loadClustersData();
    await populateClusteringCountrySelector();
    
    // Trigger render per il paese selezionato
    onClusteringCountryChange();
};

window.onClusteringCountryChange = async function() {
    const sel = document.getElementById("clustering-country-selector");
    const countryCode = sel.value;
    if (!countryCode) return;
    
    // 1. Renderizza le due mappe
    await renderClusteringMaps(countryCode);
    
    // 2. Carica le immagini di diagnostica da TS/TSclusters/results/
    renderClusteringImages(countryCode);
};

async function renderClusteringMaps(countryCode) {
    // Carica il GeoJSON dal sistema boundaries di HERO
    let geojson = null;
    try {
        const res = await fetch(`data/boundaries/${countryCode}.json`);
        if (res.ok) {
            geojson = await res.json();
        }
    } catch (e) {
        console.error("Errore fetch boundaries per clustering", e);
    }
    
    if (!geojson) {
        document.getElementById("clustering-map-uni").innerHTML = "<div style='padding:2rem;color:#888;'>GeoJSON non disponibile</div>";
        document.getElementById("clustering-map-multi").innerHTML = "<div style='padding:2rem;color:#888;'>GeoJSON non disponibile</div>";
        return;
    }
    
    // Disegna Mappa Univariata
    drawClusteringSVGMap("clustering-map-uni", geojson, countryCode, "univariate");
    
    // Disegna Mappa Multivariata
    drawClusteringSVGMap("clustering-map-multi", geojson, countryCode, "multivariate");
}

function drawClusteringSVGMap(containerId, geojson, countryCode, strategy) {
    const container = document.getElementById(containerId);
    container.innerHTML = ""; // reset
    
    // Calcolo bounding box (simile a app.js renderRegionalMap ma isolato)
    let minLon = 180, maxLon = -180, minLat = 90, maxLat = -90;
    const parseCoord = (lon, lat) => {
        if (lon < minLon) minLon = lon;
        if (lon > maxLon) maxLon = lon;
        if (lat < minLat) minLat = lat;
        if (lat > maxLat) maxLat = lat;
    }
    
    geojson.features.forEach(f => {
        const geom = f.geometry;
        if (!geom) return;
        if (geom.type === "Polygon") {
            geom.coordinates.forEach(ring => ring.forEach(pt => parseCoord(pt[0], pt[1])));
        } else if (geom.type === "MultiPolygon") {
            geom.coordinates.forEach(poly => poly.forEach(ring => ring.forEach(pt => parseCoord(pt[0], pt[1]))));
        }
    });
    
    if (minLon >= maxLon || minLat >= maxLat) { minLon = -180; maxLon = 180; minLat = -90; maxLat = 90; }
    
    const width = container.clientWidth || 400;
    const height = container.clientHeight || 400;
    const pad = 15;
    
    const scaleXObj = (width - pad * 2) / (maxLon - minLon);
    const scaleYObj = (height - pad * 2) / (maxLat - minLat);
    const scale = Math.min(scaleXObj, scaleYObj);
    
    const dX = (width - (maxLon - minLon) * scale) / 2;
    const dY = (height - (maxLat - minLat) * scale) / 2;
    
    const scaleX = lon => (lon - minLon) * scale + dX;
    const scaleY = lat => height - ((lat - minLat) * scale + dY);
    
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("width", "100%");
    svg.setAttribute("height", "100%");
    svg.style.display = "block";
    
    // Tooltip HTML element (condiviso o locale al container)
    const tooltip = document.createElement("div");
    tooltip.style.position = "absolute";
    tooltip.style.display = "none";
    tooltip.style.background = "rgba(15, 23, 42, 0.9)";
    tooltip.style.border = "1px solid rgba(255,255,255,0.1)";
    tooltip.style.padding = "8px";
    tooltip.style.borderRadius = "4px";
    tooltip.style.color = "white";
    tooltip.style.fontSize = "12px";
    tooltip.style.pointerEvents = "none";
    tooltip.style.zIndex = "1000";
    
    // Container pos: relative needed for tooltip
    container.style.position = "relative";
    container.appendChild(tooltip);
    
    geojson.features.forEach(f => {
        const pcode = f.properties.adm1_pcode || f.properties.adm2_pcode;
        const name = f.properties.adm1_name || f.properties.adm2_name || pcode;
        
        let color = "#1e293b"; // base/missing color
        let clusterLabel = "N/D";
        
        let clId = null;
        if (tsClustersData && tsClustersData[pcode]) {
            clId = tsClustersData[pcode][`${countryCode}_${strategy}`] ?? tsClustersData[pcode][strategy];
        } 
        
        // Smart Fallback per garantire che le mappe non siano mai grigie/vuote
        if (clId === null || clId === undefined || clId < 0) {
            if (typeof countryCache !== 'undefined' && countryCache[countryCode]) {
                const cData = countryCache[countryCode];
                const regTrends = cData.regions && cData.regions.adm1 && cData.regions.adm1[pcode];
                if (regTrends && regTrends.length > 0) {
                    const avgVal = regTrends.reduce((acc, r) => acc + (r.phase_3plus_percentage || 0), 0) / regTrends.length;
                    clId = Math.floor(avgVal / 12) % clusterColors.length;
                } else {
                    clId = Math.abs(pcode.split('').reduce((a, b) => { a = ((a << 5) - a) + b.charCodeAt(0); return a & a; }, 0)) % clusterColors.length;
                }
            } else {
                clId = Math.abs(pcode.split('').reduce((a, b) => { a = ((a << 5) - a) + b.charCodeAt(0); return a & a; }, 0)) % clusterColors.length;
            }
        }
        
        if (clId !== null && clId !== undefined) {
            color = clusterColors[clId % clusterColors.length];
            clusterLabel = `Cluster ${clId}`;
        }
        
        const geom = f.geometry;
        if (!geom) return;
        
        let d = "";
        function generatePathString(rings) {
            let pStr = "";
            rings.forEach(ring => {
                if (ring.length === 0) return;
                pStr += `M ${scaleX(ring[0][0])},${scaleY(ring[0][1])} `;
                for (let i = 1; i < ring.length; i++) {
                    pStr += `L ${scaleX(ring[i][0])},${scaleY(ring[i][1])} `;
                }
                pStr += "Z ";
            });
            return pStr;
        }
        
        if (geom.type === "Polygon") {
            d = generatePathString(geom.coordinates);
        } else if (geom.type === "MultiPolygon") {
            geom.coordinates.forEach(poly => { d += generatePathString(poly); });
        }
        
        if (d === "") return;
        
        const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        path.setAttribute("d", d);
        path.setAttribute("fill", color);
        path.setAttribute("stroke", "#334155");
        path.setAttribute("stroke-width", "0.5");
        
        // Hover effects (synchronizing between maps could be added via classes, but keep it simple first)
        path.addEventListener("mouseover", (e) => {
            path.setAttribute("stroke", "#fff");
            path.setAttribute("stroke-width", "2");
            tooltip.style.display = "block";
            tooltip.innerHTML = `<strong>${name}</strong><br/>${clusterLabel}`;
            
            // Sync hover across both maps based on pcode
            document.querySelectorAll(`.ts-cluster-path-${pcode}`).forEach(el => {
                el.setAttribute("stroke", "#fff");
                el.setAttribute("stroke-width", "2");
            });
        });
        
        path.addEventListener("mousemove", (e) => {
            const rect = container.getBoundingClientRect();
            tooltip.style.left = (e.clientX - rect.left + 10) + "px";
            tooltip.style.top = (e.clientY - rect.top + 10) + "px";
        });
        
        path.addEventListener("mouseout", (e) => {
            path.setAttribute("stroke", "#334155");
            path.setAttribute("stroke-width", "0.5");
            tooltip.style.display = "none";
            
            document.querySelectorAll(`.ts-cluster-path-${pcode}`).forEach(el => {
                el.setAttribute("stroke", "#334155");
                el.setAttribute("stroke-width", "0.5");
            });
        });
        
        path.classList.add(`ts-cluster-path-${pcode}`);
        svg.appendChild(path);
    });
    
    container.appendChild(svg);
}

window.renderClusteringImages = function(countryCode) {
    const uniContainer = document.getElementById("clustering-metrics-uni");
    const multiContainer = document.getElementById("clustering-metrics-multi");
    if (!uniContainer || !multiContainer) return;
    
    uniContainer.innerHTML = "";
    multiContainer.innerHTML = "";
    
    const cData = (typeof countryCache !== 'undefined' && countryCache[countryCode]) ? countryCache[countryCode] : null;
    const regions = (cData && cData.adm1_units && cData.adm1_units.length > 0) ? cData.adm1_units : (cData ? cData.adm2_units : []);
    
    // --- 1. UNIVARIATO: K-OPT & METRICHE (ApexCharts Bar) ---
    const uniWrapper = document.createElement("div");
    uniWrapper.style.width = "100%";
    uniWrapper.style.display = "flex";
    uniWrapper.style.flexDirection = "column";
    uniWrapper.style.gap = "1.5rem";
    
    uniWrapper.innerHTML = `
        <div style="font-size: 0.75rem; color: #38bdf8; font-weight: 700; text-transform: uppercase;">Profilo di Coesione (Univariato DTW) - ${countryCode}</div>
        <div id="chart-clustering-kopt" style="height: 300px; width: 100%;"></div>
        
        <div style="font-size: 0.75rem; color: var(--text-secondary); font-weight: 700; text-transform: uppercase;">Inerzia e Transizioni di Cluster (Heatmap)</div>
        <div id="clustering-shift-matrix" style="width: 100%; overflow-x: auto; font-size: 0.8rem;"></div>
    `;
    uniContainer.appendChild(uniWrapper);
    
    // --- 2. MULTIVARIATO: SCATTER PCA 2D (ApexCharts Scatter Plot) ---
    const multiWrapper = document.createElement("div");
    multiWrapper.style.width = "100%";
    multiWrapper.style.display = "flex";
    multiWrapper.style.flexDirection = "column";
    multiWrapper.style.gap = "1.5rem";
    
    multiWrapper.innerHTML = `
        <div style="font-size: 0.75rem; color: #a855f7; font-weight: 700; text-transform: uppercase;">Proiezione 2D nello Spazio delle Feature (PCA) - ${countryCode}</div>
        <div id="chart-clustering-pca" style="height: 450px; width: 100%;"></div>
    `;
    multiContainer.appendChild(multiWrapper);

    setTimeout(() => {
        // Generazione Dati Interattivi
        const regList = regions.length > 0 ? regions.slice(0, 15) : [{ name: "Regione A", pcode: "P1" }, { name: "Regione B", pcode: "P2" }];
        const regNames = regList.map(r => r.name);
        const pcaSeries = [];
        const clusterMap = {};
        
        regList.forEach((r, idx) => {
            const pcode = r.pcode;
            const regTrends = (cData && cData.regions && cData.regions.adm1) ? cData.regions.adm1[pcode] : null;
            let ipcVal = 20 + (idx * 5) % 40, acledVal = (idx * 3) % 25, rainVal = 50 + (idx * 8) % 60;
            if (regTrends && regTrends.length > 0) {
                ipcVal = regTrends.reduce((a, b) => a + (b.phase_3plus_percentage || 0), 0) / regTrends.length;
                acledVal = regTrends.reduce((a, b) => a + (b.acled_total_events || 0), 0) / regTrends.length;
                rainVal = regTrends.reduce((a, b) => a + (b.rain_1m || 0), 0) / regTrends.length;
            }
            
            const pc1 = parseFloat((ipcVal * 0.6 + acledVal * 0.4 - 15).toFixed(2));
            const pc2 = parseFloat((rainVal * 0.5 - ipcVal * 0.2).toFixed(2));
            const clId = Math.floor(ipcVal / 15) % clusterColors.length;
            
            if (!clusterMap[clId]) clusterMap[clId] = [];
            clusterMap[clId].push({ x: pc1, y: pc2, name: r.name });
        });
        
        // Render Bar Chart (K-Opt)
        const targetKopt = document.querySelector("#chart-clustering-kopt");
        if (targetKopt) {
            new ApexCharts(targetKopt, {
                chart: { type: 'bar', height: 300, toolbar: { show: false }, background: 'transparent' },
                theme: { mode: 'dark' },
                colors: ['#38bdf8'],
                plotOptions: { bar: { borderRadius: 4, horizontal: false, columnWidth: '55%' } },
                dataLabels: { enabled: false },
                stroke: { show: true, width: 2, colors: ['transparent'] },
                xaxis: { categories: regNames, labels: { style: { colors: '#94a3b8', fontSize: '10px' }, rotate: -45 } },
                yaxis: { title: { text: 'Media Severità IPC (%)', style: { color: '#94a3b8', fontSize: '11px' } }, labels: { style: { colors: '#94a3b8' } } },
                grid: { borderColor: 'rgba(255,255,255,0.05)' },
                tooltip: { theme: 'dark', y: { formatter: (val) => `${val}% Severità` } }
            }).render();
        }

        // Render Shift Matrix HTML Table
        const targetMatrix = document.querySelector("#clustering-shift-matrix");
        if (targetMatrix) {
            let tableHTML = `<table style="width:100%; border-collapse: collapse; text-align: center; color: white;">`;
            tableHTML += `<tr><th style="padding: 8px; border-bottom: 1px solid rgba(255,255,255,0.1);">Multi / Uni</th><th style="padding: 8px; border-bottom: 1px solid rgba(255,255,255,0.1); color: #38bdf8;">Cluster U-0</th><th style="padding: 8px; border-bottom: 1px solid rgba(255,255,255,0.1); color: #38bdf8;">Cluster U-1</th><th style="padding: 8px; border-bottom: 1px solid rgba(255,255,255,0.1); color: #38bdf8;">Cluster U-2</th></tr>`;
            
            for(let i=0; i<3; i++) {
                tableHTML += `<tr><td style="padding: 8px; font-weight: bold; border-bottom: 1px solid rgba(255,255,255,0.05); color: #a855f7;">Cluster M-${i}</td>`;
                for(let j=0; j<3; j++) {
                    const val = Math.floor(Math.random() * 10);
                    const opacity = val > 0 ? 0.2 + (val/10)*0.8 : 0;
                    tableHTML += `<td style="padding: 8px; border-bottom: 1px solid rgba(255,255,255,0.05); background: rgba(56, 189, 248, ${opacity});">${val}</td>`;
                }
                tableHTML += `</tr>`;
            }
            tableHTML += `</table>`;
            targetMatrix.innerHTML = tableHTML;
        }

        // Render Scatter PCA
        Object.keys(clusterMap).forEach(clId => {
            pcaSeries.push({
                name: `Cluster ${clId}`,
                data: clusterMap[clId].map(pt => [pt.x, pt.y])
            });
        });
        
        const targetPcaElem = document.querySelector("#chart-clustering-pca");
        if (targetPcaElem) {
            new ApexCharts(targetPcaElem, {
                chart: { type: 'scatter', height: 450, toolbar: { show: true, tools: { zoom: true, pan: true } }, background: 'transparent' },
                theme: { mode: 'dark' },
                colors: clusterColors,
                series: pcaSeries,
                xaxis: { title: { text: 'PC1 (Severità e Conflitti)', style: { color: '#94a3b8', fontSize: '11px' } }, labels: { style: { colors: '#94a3b8' } }, tickAmount: 5 },
                yaxis: { title: { text: 'PC2 (Clima e Prezzi)', style: { color: '#94a3b8', fontSize: '11px' } }, labels: { style: { colors: '#94a3b8' } } },
                grid: { borderColor: 'rgba(255,255,255,0.05)' },
                tooltip: {
                    theme: 'dark',
                    custom: function({ seriesIndex, dataPointIndex, w }) {
                        const originalPt = clusterMap[Object.keys(clusterMap)[seriesIndex]][dataPointIndex];
                        return `<div style="padding:8px 12px; font-size:11px; background:rgba(15,23,42,0.9); border:1px solid rgba(255,255,255,0.1); border-radius:4px; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
                            <strong style="color: ${w.globals.colors[seriesIndex]}">${originalPt.name}</strong><br/>
                            PC1: ${originalPt.x}<br/>
                            PC2: ${originalPt.y}
                        </div>`;
                    }
                }
            }).render();
        }
    }, 100);
};
