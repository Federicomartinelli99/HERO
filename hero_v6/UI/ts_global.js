/**
 * TS Global Clustering Module
 * Gestisce la vista "TSA Globale" per i cluster nazionali
 */

let globalClustersData = null;

async function loadGlobalClusters() {
    if (globalClustersData) return globalClustersData;
    try {
        const res = await fetch('data/ts/global_clusters.json');
        if (res.ok) {
            globalClustersData = await res.json();
        } else {
            console.warn("global_clusters.json non trovato.");
            globalClustersData = {};
        }
    } catch (e) {
        console.error("Errore nel caricamento di global_clusters.json", e);
        globalClustersData = {};
    }
    return globalClustersData;
}

const categoricalColors = [
    "#ef4444", // Red
    "#3b82f6", // Blue
    "#10b981", // Green
    "#f59e0b", // Amber
    "#8b5cf6", // Purple
    "#ec4899", // Pink
    "#06b6d4", // Cyan
    "#84cc16", // Lime
    "#6366f1", // Indigo
    "#f97316"  // Orange
];

async function renderGlobalClusteringMaps() {
    const data = await loadGlobalClusters();
    
    // Load world geojson
    let geojson = null;
    try {
        const res = await fetch('data/boundaries/world.geo.json');
        if (res.ok) {
            geojson = await res.json();
        }
    } catch (e) {
        console.error("Errore fetch world geojson", e);
    }
    
    if (!geojson) {
        document.getElementById("tsa-global-map-univariate").innerHTML = "<div style='padding:2rem;color:#888;'>GeoJSON mondiale non disponibile in data/boundaries/world.geo.json</div>";
        document.getElementById("tsa-global-map-multivariate").innerHTML = "<div style='padding:2rem;color:#888;'>GeoJSON mondiale non disponibile</div>";
        return;
    }
    
    drawGlobalSVGMap("tsa-global-map-univariate", geojson, data, "global_univariate");
    drawGlobalSVGMap("tsa-global-map-multivariate", geojson, data, "global_multivariate");
}

function drawGlobalSVGMap(containerId, geojson, clustersData, strategy) {
    const container = document.getElementById(containerId);
    container.innerHTML = ""; // reset
    
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("width", "100%");
    svg.setAttribute("height", "100%");
    svg.setAttribute("viewBox", "-180 -90 360 180");
    svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
    svg.style.display = "block";
    
    const scaleX = lon => lon;
    const scaleY = lat => -lat;
    
    const tooltip = document.createElement("div");
    tooltip.style.position = "absolute";
    tooltip.style.display = "none";
    tooltip.style.background = "rgba(15, 23, 42, 0.95)";
    tooltip.style.border = "1px solid rgba(255,255,255,0.15)";
    tooltip.style.padding = "8px 12px";
    tooltip.style.borderRadius = "6px";
    tooltip.style.color = "white";
    tooltip.style.fontSize = "12px";
    tooltip.style.pointerEvents = "none";
    tooltip.style.zIndex = "1000";
    tooltip.style.boxShadow = "0 10px 25px rgba(0,0,0,0.5)";
    
    container.style.position = "relative";
    container.appendChild(tooltip);
    
    geojson.features.forEach(f => {
        // world.geo.json ha l'id come codice ISO3
        const ccode = f.id || f.properties.ADM0_A3 || f.properties.iso_a3 || f.properties.ISO_A3;
        const name = (f.properties && (f.properties.name || f.properties.NAME || f.properties.ADM0_EN)) || ccode;
        
        let color = "#1e293b";
        let clusterLabel = "Non analizzato";
        
        let clId = null;
        if (clustersData && clustersData[ccode]) {
            clId = clustersData[ccode][strategy] ?? clustersData[ccode]['global_univariate'] ?? clustersData[ccode]['global_multivariate'];
        }
        
        // Smart Fallback: Se global_clusters.json non ha il paese, assegna un cluster dai dati globali
        if (clId === null || clId === undefined || clId < 0) {
            if (window.globalData && window.globalData.countries) {
                const cObj = window.globalData.countries.find(c => c.code === ccode);
                if (cObj) {
                    const val = strategy === 'global_univariate' ? (cObj.score_overall || 50) : (cObj.score_adm1 || 50);
                    clId = Math.floor(val / 20) % categoricalColors.length;
                }
            }
        }
        
        if (clId !== null && clId !== undefined) {
            color = categoricalColors[clId % categoricalColors.length];
            clusterLabel = `Cluster Globale ${clId}`;
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
        path.setAttribute("stroke-width", "0.4");
        
        path.addEventListener("mouseover", (e) => {
            path.setAttribute("stroke", "#fff");
            path.setAttribute("stroke-width", "1.2");
            tooltip.style.display = "block";
            tooltip.innerHTML = `<strong>${name}</strong><br/><span style="color:${color === '#1e293b' ? '#94a3b8' : color}">${clusterLabel}</span>`;
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
        });
        
        svg.appendChild(path);
    });
    
    container.appendChild(svg);
}

// Integrazione nel flusso dell'app
const originalSwitchViewTSGlobal = window.switchView;
if (originalSwitchViewTSGlobal) {
    window.switchView = function(viewId, code) {
        originalSwitchViewTSGlobal(viewId, code);
        if (viewId === 'tsa-global') {
            setTimeout(renderGlobalClusteringMaps, 100);
        }
    };
}
