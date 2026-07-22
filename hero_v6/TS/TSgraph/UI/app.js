let networkData = { nodes: [], edges: [] };
let filteredEdges = [];
let map;
let mapLayers = [];
let currentCountry = 'AFG';

// DOM Elements
const countrySelect = document.getElementById('countrySelect');
const metricSelect = document.getElementById('metricSelect');
const lagSelect = document.getElementById('lagSelect');
const statCheck = document.getElementById('statCheck');
const modeFixed = document.getElementById('modeFixed');
const modeTopological = document.getElementById('modeTopological');
const fixedSlider = document.getElementById('fixedSlider');
const fixedVal = document.getElementById('fixedVal');
const topoSlider = document.getElementById('topoSlider');
const topoVal = document.getElementById('topoVal');
const fixedControls = document.getElementById('fixedControls');
const topoControls = document.getElementById('topoControls');
const toggleSidebar = document.getElementById('toggleSidebar');
const sidebar = document.getElementById('sidebar');

document.addEventListener("DOMContentLoaded", async () => {
    initMap();
    await loadAvailableCountries();
    loadData();
    attachListeners();
});

async function loadAvailableCountries() {
    try {
        const response = await fetch('data/countries_list.json');
        if(response.ok) {
            const countries = await response.json();
            const select = document.getElementById('countrySelect');
            select.innerHTML = '';
            countries.forEach(c => {
                let opt = document.createElement('option');
                opt.value = c;
                opt.textContent = c === 'GLOBAL' ? 'GLO' : c;
                select.appendChild(opt);
                
                let optCmp = document.createElement('option');
                optCmp.value = c;
                optCmp.textContent = c === 'GLOBAL' ? 'GLO' : c;
                document.getElementById('cmpAddCountrySelect').appendChild(optCmp);
            });
            if (countries.length > 0) {
                currentCountry = countries[0];
            }
        }
    } catch(err) {
        console.warn("Could not load countries_list.json, falling back to static HTML options.", err);
    }
}

function initMap() {
    map = L.map('map', {zoomControl: false}).setView([33.9, 67.7], 5);
    L.control.zoom({position: 'topright'}).addTo(map);
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; CARTO'
    }).addTo(map);
}

// MATH UTILS FOR FITTING
function fitModel(x, y, modelType) {
    let n = x.length; if(n < 2) return null;
    let sumX = 0, sumY = 0, sumXY = 0, sumXX = 0; let valid = 0;
    
    let x_used = []; let y_used = [];
    for(let i=0; i<n; i++) {
        let lx, ly;
        if (modelType === 'exponential') {
            if(y[i] <= 0) continue;
            lx = x[i]; ly = Math.log(y[i]);
        } else if (modelType === 'powerlaw') {
            if(y[i] <= 0 || x[i] <= 0) continue;
            lx = Math.log(x[i]); ly = Math.log(y[i]);
        } else if (modelType === 'linear') {
            lx = x[i]; ly = y[i];
        }
        x_used.push(x[i]); y_used.push(y[i]);
        sumX += lx; sumY += ly; sumXY += lx * ly; sumXX += lx * lx;
        valid++;
    }
    
    if(valid < 2) return null;
    let denom = (valid * sumXX - sumX * sumX);
    if(denom === 0) return null;
    let m = (valid * sumXY - sumX * sumY) / denom;
    let b = (sumY - m * sumX) / valid;
    
    let ssTot = 0; let ssRes = 0;
    let meanY = y_used.reduce((a,v)=>a+v,0) / valid;
    
    let fitX = []; let fitY = [];
    let minX = Math.min(...x_used); let maxX = Math.max(...x_used);
    let steps = 50;
    if(minX === maxX) steps = 1;
    for(let i=0; i<=steps; i++) {
        let cx = minX + (maxX - minX) * (i/steps);
        if(modelType === 'powerlaw' && cx <= 0) cx = 0.001;
        fitX.push(cx);
        if(modelType === 'exponential') fitY.push(Math.exp(b) * Math.exp(m * cx));
        else if(modelType === 'powerlaw') fitY.push(Math.exp(b) * Math.pow(cx, m));
        else if(modelType === 'linear') fitY.push(m * cx + b);
    }
    
    for(let i=0; i<valid; i++) {
        let actualY = y_used[i];
        let cx = x_used[i];
        let predY = 0;
        if(modelType === 'exponential') predY = Math.exp(b) * Math.exp(m * cx);
        else if(modelType === 'powerlaw') predY = Math.exp(b) * Math.pow(cx, m);
        else if(modelType === 'linear') predY = m * cx + b;
        
        ssRes += Math.pow(actualY - predY, 2);
        ssTot += Math.pow(actualY - meanY, 2);
    }
    
    let r2 = 1 - (ssRes / (ssTot || 1e-10));
    
    let label = '';
    let eq = '';
    
    function fmt(val) {
        if(Math.abs(val) < 0.001 && val !== 0) return val.toExponential(2);
        return val.toFixed(3);
    }
    
    if(modelType === 'exponential') { label = `Exp(λ=${fmt(-m)}, R²=${r2.toFixed(2)})`; eq = `Exp(λ=${fmt(-m)})`; }
    else if(modelType === 'powerlaw') { label = `Pow(α=${fmt(-m)}, R²=${r2.toFixed(2)})`; eq = `Pow(α=${fmt(-m)})`; }
    else if(modelType === 'linear') { label = `Lin(m=${fmt(m)}, R²=${r2.toFixed(2)})`; eq = `Lin(m=${fmt(m)})`; }
    
    return { fitX, fitY, r2, label, eq };
}

function attachListeners() {
    toggleSidebar.addEventListener('click', () => {
        sidebar.classList.toggle('collapsed');
        document.getElementById('sidebarRight').classList.toggle('collapsed-right');
        setTimeout(() => { map.invalidateSize(); drawCharts(); }, 350);
    });

    countrySelect.addEventListener('change', (e) => { currentCountry = e.target.value; loadData(); });
    
    metricSelect.addEventListener('change', (e) => {
        const m = e.target.value;
        if(m === 'Pearson') {
            fixedSlider.value = 0.92; fixedVal.textContent = "0.92";
        } else if(m === 'STE') {
            fixedSlider.value = 0.22; fixedVal.textContent = "0.22";
            if(lagSelect.value === "0") lagSelect.value = "1";
            statCheck.checked = false;
        } else if(m === 'MI') {
            fixedSlider.value = 0.10; fixedVal.textContent = "0.10";
        }
        updateApp();
    });
    
    lagSelect.addEventListener('change', updateApp);
    statCheck.addEventListener('change', updateApp);
    
    modeFixed.addEventListener('change', () => {
        fixedControls.style.display = 'block'; topoControls.style.display = 'none'; updateApp();
    });
    
    modeTopological.addEventListener('change', () => {
        fixedControls.style.display = 'none'; topoControls.style.display = 'block'; updateApp();
    });
    
    fixedSlider.addEventListener('input', (e) => { fixedVal.textContent = parseFloat(e.target.value).toFixed(2); updateApp(); });
    topoSlider.addEventListener('input', (e) => { topoVal.textContent = e.target.value; updateApp(); });
    
    window.addEventListener('resize', () => {
        map.invalidateSize();
        drawCharts();
    });
    
    const tf = document.getElementById('toggleFitting');
    if(tf) tf.addEventListener('change', drawCharts);
    
    document.querySelectorAll('input[name="scaleDegree"]').forEach(r => r.addEventListener('change', drawCharts));
    document.querySelectorAll('input[name="assortType"]').forEach(r => r.addEventListener('change', drawCharts));
    if(document.getElementById('fitModelSelect')) document.getElementById('fitModelSelect').addEventListener('change', drawCharts);
    
    // Comparison Modal Listeners
    if(document.getElementById('btnOpenCompare')) {
        document.getElementById('btnOpenCompare').addEventListener('click', (e) => {
            e.preventDefault();
            document.getElementById('compareModal').style.display = 'flex';
            drawComparisonPlot();
        });
    }
    if(document.getElementById('btnCloseCompare')) {
        document.getElementById('btnCloseCompare').addEventListener('click', () => {
            document.getElementById('compareModal').style.display = 'none';
        });
    }
    if(document.getElementById('cmpBtnAdd')) {
        document.getElementById('cmpBtnAdd').addEventListener('click', addCountryToComparison);
    }
    
    // Slider logic for Comparison Modal
    const cmpThrMode = document.getElementById('cmpThrMode');
    const cmpThrVal = document.getElementById('cmpThrVal');
    const cmpThrValLabel = document.getElementById('cmpThrValLabel');
    const cmpMetric = document.getElementById('cmpMetric');
    
    if(cmpThrMode && cmpThrVal && cmpThrValLabel && cmpMetric) {
        function updateCmpSliderConstraints() {
            if(cmpThrMode.value === 'fixed') {
                cmpThrVal.min = 0; cmpThrVal.max = 1; cmpThrVal.step = 0.01;
                // Set default based on metric
                if(cmpMetric.value === 'Pearson') cmpThrVal.value = 0.92;
                else if(cmpMetric.value === 'STE') cmpThrVal.value = 0.22;
                else if(cmpMetric.value === 'MI') cmpThrVal.value = 0.10;
            } else {
                cmpThrVal.min = 1; cmpThrVal.max = 100; cmpThrVal.step = 1;
                cmpThrVal.value = 5;
            }
            cmpThrValLabel.textContent = parseFloat(cmpThrVal.value).toFixed(cmpThrMode.value === 'fixed' ? 2 : 0) + (cmpThrMode.value === 'fixed' ? '' : '%');
            drawComparisonPlot();
        }
        
        cmpThrMode.addEventListener('change', updateCmpSliderConstraints);
        cmpMetric.addEventListener('change', () => {
            if(cmpThrMode.value === 'fixed') updateCmpSliderConstraints();
            else drawComparisonPlot(); // if topological, just redraw
        });
        
        cmpThrVal.addEventListener('input', (e) => {
            cmpThrValLabel.textContent = parseFloat(e.target.value).toFixed(cmpThrMode.value === 'fixed' ? 2 : 0) + (cmpThrMode.value === 'fixed' ? '' : '%');
            drawComparisonPlot();
        });
    }
    
    const cmpInputs = ['cmpLag', 'cmpSig', 'cmpPlotType', 'cmpFitToggle', 'cmpOnlyFit', 'cmpFitModel'];
    cmpInputs.forEach(id => {
        if(document.getElementById(id)) {
            document.getElementById(id).addEventListener('change', drawComparisonPlot);
        }
    });
}

async function loadData() {
    try {
        const response = await fetch(`data/network_data_${currentCountry}.json`);
        if(response.ok) {
            networkData = await response.json();
            if(networkData.nodes.length > 0) {
                const lats = networkData.nodes.map(n => n.lat);
                const lons = networkData.nodes.map(n => n.lon);
                map.fitBounds([[Math.min(...lats), Math.min(...lons)], [Math.max(...lats), Math.max(...lons)]], {padding: [50, 50]});
            }
            updateApp();
        } else {
            console.error("Data not found for country", currentCountry);
        }
    } catch(err) {
        console.error("Fetch error:", err);
    }
}

function updateApp() {
    filterData();
    drawMap();
    drawCharts();
    updateMetrics();
}

function filterData() {
    const metric = metricSelect.value;
    const lag = parseInt(lagSelect.value);
    const requireSig = statCheck.checked;
    const mode = modeFixed.checked ? 'fixed' : 'topological';
    const fixedThresh = parseFloat(fixedSlider.value);
    const topoThresh = parseInt(topoSlider.value);
    
    let candidates = [];
    networkData.edges.forEach(e => {
        if(e.lag === lag && e.metrics[metric]) {
            const mData = e.metrics[metric];
            if(mData.val > 0) {
                if(!requireSig || mData.sig === true) {
                    candidates.push({...e, weight: mData.val});
                }
            }
        }
    });
    
    if(mode === 'fixed') {
        filteredEdges = candidates.filter(e => e.weight >= fixedThresh);
    } else {
        if(candidates.length === 0) { filteredEdges = []; } 
        else {
            candidates.sort((a,b) => b.weight - a.weight);
            const keepCount = Math.max(1, Math.floor(candidates.length * (topoThresh / 100)));
            filteredEdges = candidates.slice(0, keepCount);
        }
    }
}

function drawMap() {
    mapLayers.forEach(l => map.removeLayer(l));
    mapLayers = [];
    
    const nodeMap = {};
    networkData.nodes.forEach(n => {
        nodeMap[n.id] = [n.lat, n.lon];
        const marker = L.circleMarker([n.lat, n.lon], {
            radius: 4, color: '#0ea5e9', fillColor: '#0f172a', fillOpacity: 1, weight: 2,
            nodeId: n.id
        }).addTo(map);
        
        marker.on('click', () => {
            let k = 0;
            filteredEdges.forEach(e => { if(e.source === n.id || e.target === n.id) k++; });
            highlightNodeInCharts(k);
            
            const popupContent = `
                <div style="width: 320px; height: 220px; color: #f8fafc; font-family: Outfit;">
                    <div style="font-weight: 600; margin-bottom: 5px; color: #38bdf8;">${n.id} Market Prices</div>
                    <div id="popupChart_${n.id.replace(/\s+/g, '')}" style="width: 100%; height: 180px;"></div>
                </div>
            `;
            marker.bindPopup(popupContent, {className: 'glass-popup'}).openPopup();
            
            setTimeout(() => {
                if(n.dates && n.prices) {
                    Plotly.newPlot(`popupChart_${n.id.replace(/\s+/g, '')}`, [{
                        x: n.dates,
                        y: n.prices,
                        type: 'scatter',
                        mode: 'lines',
                        line: {color: '#38bdf8', width: 2}
                    }], {
                        margin: {t: 5, b: 25, l: 30, r: 10},
                        paper_bgcolor: 'rgba(0,0,0,0)',
                        plot_bgcolor: 'rgba(0,0,0,0)',
                        xaxis: {showgrid: false, tickfont: {size: 9, color: '#94a3b8'}},
                        yaxis: {title: {text: 'Returns (Log-Diff)', font: {size: 10, color: '#94a3b8'}}, showgrid: true, gridcolor: 'rgba(255,255,255,0.05)', tickfont: {size: 9, color: '#94a3b8'}}
                    }, {displayModeBar: false});
                } else {
                    document.getElementById(`popupChart_${n.id.replace(/\s+/g, '')}`).innerHTML = "<br><small style='color:#94a3b8'>No time series data available.<br>Please regenerate JSON with the updated Python script.</small>";
                }
            }, 100);
        });
        
        mapLayers.push(marker);
    });
    
    filteredEdges.forEach(e => {
        const p1 = nodeMap[e.source];
        const p2 = nodeMap[e.target];
        if(!p1 || !p2) return;
        
        const metric = metricSelect.value;
        const color = metric === 'STE' ? '#ef4444' : (metric === 'Pearson' ? '#3b82f6' : '#22c55e');
        const weightScale = Math.max(1, e.weight * 5);
        
        const line = L.polyline([p1, p2], { 
            color: color, weight: weightScale, opacity: 0.6,
            originalColor: color, originalWeight: weightScale, edgeData: e
        }).addTo(map);
        
        line.on('click', () => { 
            highlightEdgeInCharts(e.distance, e.weight); 
            highlightEdgeOnMap(e.distance, e.weight);
        });
        
        line.bindPopup(`${e.source} &rarr; ${e.target}<br>Weight: ${e.weight.toFixed(3)}<br>Distance: ${e.distance.toFixed(1)} km`);
        mapLayers.push(line);
        
        const decorator = L.polylineDecorator(line, {
            patterns: [{offset: '100%', repeat: 0, symbol: L.Symbol.arrowHead({pixelSize: 8, pathOptions: {color, fillOpacity: 1, weight: 0}})}]
        }).addTo(map);
        mapLayers.push(decorator);
    });
    
    // Add map click listener to reset highlights
    map.off('click').on('click', resetMapHighlights);
}

let highlightedLayer = null;

function resetMapHighlights() {
    mapLayers.forEach(l => {
        if(l.setStyle) {
            if(l.options.originalColor) {
                l.setStyle({ color: l.options.originalColor, weight: l.options.originalWeight, opacity: 0.6 });
            } else {
                // node markers
                if(l.options.fillColor) l.setStyle({ color: '#0ea5e9', radius: 4, weight: 2 });
            }
        }
    });
}

function highlightEdgeOnMap(dist, weight) {
    resetMapHighlights();
    mapLayers.forEach(l => {
        if(l.options && l.options.edgeData) {
            let e = l.options.edgeData;
            if(Math.abs(e.distance - dist) < 0.001 && Math.abs(e.weight - weight) < 0.001) {
                l.setStyle({ color: '#fcd34d', weight: l.options.originalWeight + 5, opacity: 1 });
                l.bringToFront();
                l.openPopup();
            } else {
                l.setStyle({ opacity: 0.1 });
            }
        }
    });
}

function highlightNodeOnMap(nodeId) {
    resetMapHighlights();
    mapLayers.forEach(l => {
        if(l.options && l.options.nodeId) {
            if(l.options.nodeId === nodeId) {
                l.setStyle({ color: '#fcd34d', radius: 8, weight: 4 });
                l.bringToFront();
                l.openPopup();
            } else {
                l.setStyle({ color: '#334155', weight: 1 });
            }
        } else if (l.options && l.options.originalColor) {
            l.setStyle({ opacity: 0.1 }); // dim all edges
        }
    });
}

function highlightNodesByDegree(k) {
    resetMapHighlights();
    let targets = [];
    const outDegree = {}; const inDegree = {};
    networkData.nodes.forEach(n => { outDegree[n.id] = 0; inDegree[n.id] = 0; });
    filteredEdges.forEach(e => { outDegree[e.source]++; inDegree[e.target]++; });
    
    networkData.nodes.forEach(n => {
        if (outDegree[n.id] + inDegree[n.id] === k) targets.push(n.id);
    });
    
    mapLayers.forEach(l => {
        if(l.options && l.options.nodeId) {
            if(targets.includes(l.options.nodeId)) {
                l.setStyle({ color: '#fcd34d', radius: 8, weight: 4 });
                l.bringToFront();
            } else {
                l.setStyle({ color: '#334155', weight: 1 });
            }
        } else if (l.options && l.options.originalColor) {
            l.setStyle({ opacity: 0.1 }); // dim all edges
        }
    });
}

function highlightEdgeInCharts(dist, weight) {
    let chart = document.getElementById('plotDistanceDecay');
    if(!chart || !chart.data) return;
    if(chart.data[chart.data.length-1].name === 'Highlight') {
        Plotly.deleteTraces('plotDistanceDecay', chart.data.length-1);
    }
    Plotly.addTraces('plotDistanceDecay', {
        x: [dist], y: [weight], mode: 'markers', type: 'scatter',
        marker: { color: '#fcd34d', size: 12, symbol: 'cross', line: {color: '#fff', width:2} }, name: 'Highlight'
    });
}

function highlightNodeInCharts(k) {
    let chart = document.getElementById('plotDegreeDist');
    if(!chart || !chart.data || !chart.data[0]) return;
    if(chart.data[chart.data.length-1].name === 'Highlight') {
        Plotly.deleteTraces('plotDegreeDist', chart.data.length-1);
    }
    let xArr = chart.data[0].x;
    let yArr = chart.data[0].y;
    let idx = xArr.indexOf(k);
    if(idx !== -1) {
        Plotly.addTraces('plotDegreeDist', {
            x: [k], y: [yArr[idx]], type: 'bar', marker: { color: '#fcd34d', opacity: 1 }, name: 'Highlight'
        });
    }
}

function drawCharts() {
    const layoutBase = {
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        font: { color: '#94a3b8', family: 'Outfit', size: 10 },
        margin: { t: 20, b: 25, l: 30, r: 10 },
        autosize: true,
        uirevision: currentCountry
    };
    const configOpts = {displayModeBar: false, responsive: true};
    const axStyle = { showgrid: true, gridcolor: 'rgba(255,255,255,0.03)', zerolinecolor: 'rgba(255,255,255,0.1)' };

    let maxDist = 0;
    networkData.edges.forEach(e => { if(e.distance > maxDist) maxDist = e.distance; });
    const N = networkData.nodes.length || 1;

    const distances = filteredEdges.map(e => e.distance);
    const weights = filteredEdges.map(e => e.weight);
    
    let ddData = [{
        x: distances, y: weights, mode: 'markers', type: 'scatter',
        marker: { color: '#38bdf8', size: 4, opacity: 0.6 }, name: 'Data'
    }];
    
    let ddTitle = 'Distance Decay';
    const showFitting = document.getElementById('toggleFitting') && document.getElementById('toggleFitting').checked;
    let fitModelVal = document.getElementById('fitModelSelect') ? document.getElementById('fitModelSelect').value : 'exponential';
    
    if (showFitting && distances.length > 2) {
        let fitRes = fitModel(distances, weights, fitModelVal);
        if (fitRes) {
            ddData.push({
                x: fitRes.fitX, y: fitRes.fitY, mode: 'lines', type: 'scatter',
                line: { color: '#ef4444', width: 2, dash: 'dot' }, name: 'Fit', hoverinfo: 'none'
            });
            ddTitle += ` (${fitRes.label})`;
        }
    }

    Plotly.react('plotDistanceDecay', ddData, { 
        ...layoutBase, title: {text: ddTitle, font:{color:'#f8fafc', size:11}}, 
        xaxis: {title: 'Dist (km)', range: [0, maxDist * 1.05], ...axStyle}, 
        yaxis: {title: 'W', range: [0, 1.05], ...axStyle},
        showlegend: false
    }, configOpts);
    
    let ddChart = document.getElementById('plotDistanceDecay');
    if(!ddChart._hasClick) {
        ddChart.on('plotly_click', function(data) {
            if(data.points && data.points[0]) {
                highlightEdgeOnMap(data.points[0].x, data.points[0].y);
            }
        });
        ddChart._hasClick = true;
    }

    const outDegree = {}; const inDegree = {};
    networkData.nodes.forEach(n => { outDegree[n.id] = 0; inDegree[n.id] = 0; });
    filteredEdges.forEach(e => { outDegree[e.source]++; inDegree[e.target]++; });
    
    const degrees = Object.values(outDegree).filter(d => d > 0);
    const degCounts = {};
    degrees.forEach(d => { degCounts[d] = (degCounts[d] || 0) + 1; });
    const dX = Object.keys(degCounts).map(Number);
    const dY = Object.values(degCounts);
    
    const scaleChoice = document.querySelector('input[name="scaleDegree"]:checked') ? document.querySelector('input[name="scaleDegree"]:checked').value : 'loglog';
    let xType = 'linear', yType = 'linear';
    let xRange = [0, N], yRange = [0, N];
    
    if(scaleChoice === 'loglog') { xType = 'log'; yType = 'log'; xRange = [0, Math.log10(N)]; yRange = [0, Math.log10(N)]; }
    else if(scaleChoice === 'linlog') { xType = 'linear'; yType = 'log'; xRange = [0, N]; yRange = [0, Math.log10(N)]; }
    else { xType = 'linear'; yType = 'linear'; xRange = [0, N]; yRange = [0, N]; }
    
    let degData = [{
        x: dX, y: dY, type: 'bar', marker: { color: '#818cf8', opacity: 0.8 }, name: 'Data'
    }];
    
    let degreeTitle = 'Degree Dist';
    
    if (showFitting && dX.length > 2) {
        let fitRes = fitModel(dX, dY, fitModelVal);
        if (fitRes) {
            degData.push({
                x: fitRes.fitX, y: fitRes.fitY, type: 'scatter', mode: 'lines',
                line: { color: '#ef4444', width: 2, dash: 'dot' }, name: 'Fit', hoverinfo: 'none'
            });
            degreeTitle += ` (${fitRes.label})`;
        }
    }

    Plotly.react('plotDegreeDist', degData, { 
          ...layoutBase, title: {text: degreeTitle, font:{color:'#f8fafc', size:11}}, 
          xaxis: {title: 'k', type: xType, range: xRange, ...axStyle}, 
          yaxis: {title: 'Count', type: yType, range: yRange, ...axStyle}, showlegend: false }, configOpts);

    let degChart = document.getElementById('plotDegreeDist');
    if(!degChart._hasClick) {
        degChart.on('plotly_click', function(data) {
            if(data.points && data.points[0]) {
                highlightNodesByDegree(data.points[0].x);
            }
        });
        degChart._hasClick = true;
    }

    const assortChoice = document.querySelector('input[name="assortType"]:checked') ? document.querySelector('input[name="assortType"]:checked').value : 'knn';

    if (assortChoice === 'knn') {
        const k_knn = {}; const k_counts = {};
        networkData.nodes.forEach(n => {
            let d = outDegree[n.id] + inDegree[n.id];
            if(d===0) return;
            let neighborDegSum = 0;
            filteredEdges.forEach(e => {
                if(e.source === n.id) neighborDegSum += outDegree[e.target] + inDegree[e.target];
                if(e.target === n.id) neighborDegSum += outDegree[e.source] + inDegree[e.source];
            });
            let knn = neighborDegSum / d;
            k_knn[d] = (k_knn[d] || 0) + knn; k_counts[d] = (k_counts[d] || 0) + 1;
        });
        
        const knnX = Object.keys(k_knn).map(Number);
        const knnY = knnX.map(k => k_knn[k] / k_counts[k]);
        
        let knnData = [{
            x: knnX, y: knnY, mode: 'markers', type: 'scatter', marker: { color: '#a78bfa', size: 5 }, name: 'Data'
        }];
        let knnTitle = 'Assortativity (Knn)';
        
        if (showFitting && knnX.length > 2) {
            let fitRes = fitModel(knnX, knnY, fitModelVal);
            if (fitRes) {
                knnData.push({
                    x: fitRes.fitX, y: fitRes.fitY, mode: 'lines', type: 'scatter',
                    line: { color: '#ef4444', width: 2, dash: 'dot' }, name: 'Fit', hoverinfo: 'none'
                });
                knnTitle += ` (${fitRes.label})`;
            }
        }
        
        Plotly.react('plotAssortativity', knnData, { 
              ...layoutBase, title: {text: knnTitle, font:{color:'#f8fafc', size:11}}, 
              xaxis: {title: 'k', ...axStyle}, 
              yaxis: {title: 'Knn', ...axStyle}, showlegend: false }, configOpts);
              
        let asChart = document.getElementById('plotAssortativity');
        if(asChart.removeAllListeners) asChart.removeAllListeners('plotly_click');
    } else {
        let k1_arr = [];
        let k2_arr = [];
        let edgeRef = [];
        
        filteredEdges.forEach(e => {
            let u = e.source, v = e.target;
            let ku = outDegree[u] + inDegree[u];
            let kv = outDegree[v] + inDegree[v];
            k1_arr.push(ku); k2_arr.push(kv); edgeRef.push(e);
            k1_arr.push(kv); k2_arr.push(ku); edgeRef.push(e);
        });

        let maxK_scatter = Math.max(...k1_arr, 1);
        
        let assortScatterData = [{
            x: k1_arr, y: k2_arr, mode: 'markers', type: 'scatter',
            marker: { color: '#fb923c', size: 5, opacity: 0.6 }, name: 'Edge'
        }];
        
        assortScatterData.push({
            x: [0, maxK_scatter + 5], y: [0, maxK_scatter + 5], mode: 'lines', type: 'scatter',
            line: { color: '#94a3b8', width: 1, dash: 'dash' }, name: 'y=x', hoverinfo: 'none'
        });

        Plotly.react('plotAssortativity', assortScatterData, { 
              ...layoutBase, title: {text: 'Edge Degrees (k1 vs k2)', font:{color:'#f8fafc', size:11}}, 
              xaxis: {title: 'k1', range: [0, maxK_scatter + 2], ...axStyle}, 
              yaxis: {title: 'k2', range: [0, maxK_scatter + 2], ...axStyle}, 
              showlegend: false }, configOpts);

        let asChart = document.getElementById('plotAssortativity');
        if(asChart.removeAllListeners) asChart.removeAllListeners('plotly_click');
        asChart.on('plotly_click', function(data) {
            if(data.points && data.points[0] && data.points[0].curveNumber === 0) {
                let idx = data.points[0].pointIndex;
                if(edgeRef[idx]) {
                    highlightEdgeOnMap(edgeRef[idx].distance, edgeRef[idx].weight);
                }
            }
        });
    }
}

function getGraphMetrics() {
    const N = networkData.nodes.length;
    document.getElementById('statNodes').textContent = N;
    
    if(N < 3 || filteredEdges.length === 0) {
        document.getElementById('statEdges').textContent = 0;
        return [];
    }
    
    const adj = Array(N).fill(0).map(() => Array(N).fill(0));
    const nodeIdx = {};
    networkData.nodes.forEach((n,i) => nodeIdx[n.id] = i);
    
    filteredEdges.forEach(e => {
        let u = nodeIdx[e.source], v = nodeIdx[e.target];
        if(u !== undefined && v !== undefined) {
            adj[u][v] = 1; adj[v][u] = 1;
        }
    });
    
    // Count exact undirected edges in the real graph
    let E = 0;
    for(let i=0; i<N; i++){
        for(let j=i+1; j<N; j++){
            if(adj[i][j]) E++;
        }
    }
    document.getElementById('statEdges').textContent = E;
    
    // Find Components (Real Graph only)
    let visited = Array(N).fill(false);
    let components = [];
    let isolatedNodes = 0;
    
    for(let i=0; i<N; i++) {
        if(!visited[i]) {
            let compSize = 0;
            let q = [i];
            visited[i] = true;
            while(q.length > 0) {
                let u = q.shift();
                compSize++;
                for(let v=0; v<N; v++) {
                    if(adj[u][v] && !visited[v]) {
                        visited[v] = true;
                        q.push(v);
                    }
                }
            }
            components.push(compSize);
            if(compSize === 1) isolatedNodes++;
        }
    }
    
    // Calculate Assortativity Coefficient r
    let realDegrees = Array(N).fill(0);
    for(let i=0; i<N; i++) for(let j=0; j<N; j++) if(adj[i][j]) realDegrees[i]++;
    
    let sum_xy = 0, sum_x = 0, sum_y = 0, sum_x2 = 0, sum_y2 = 0, M = 0;
    for(let i=0; i<N; i++) {
        for(let j=i+1; j<N; j++) {
            if(adj[i][j]) {
                let ki = realDegrees[i], kj = realDegrees[j];
                sum_xy += 2 * ki * kj;
                sum_x += ki + kj;
                sum_y += ki + kj;
                sum_x2 += ki*ki + kj*kj;
                sum_y2 += ki*ki + kj*kj;
                M += 2;
            }
        }
    }
    let r = 0;
    if(M > 0) {
        let num = sum_xy - (sum_x * sum_y / M);
        let den = Math.sqrt((sum_x2 - (sum_x * sum_x / M)) * (sum_y2 - (sum_y * sum_y / M)));
        if(den > 0) r = num / den;
    }
    
    let gcSize = components.length > 0 ? Math.max(...components) : 0;
    let statCompEl = document.getElementById('statComponents');
    if(statCompEl) statCompEl.textContent = components.length;
    let statGCEl = document.getElementById('statGC');
    if(statGCEl) statGCEl.textContent = `${gcSize} (${((gcSize/N)*100).toFixed(1)}%)`;
    let statIsoEl = document.getElementById('statIsolated');
    if(statIsoEl) statIsoEl.textContent = isolatedNodes;
    let statAssortEl = document.getElementById('statAssortativity');
    if(statAssortEl) statAssortEl.textContent = r.toFixed(3);
    
    // Top 3 Hubs
    let degreeScores = networkData.nodes.map((n, i) => ({ id: n.id, k: realDegrees[i] }));
    degreeScores.sort((a,b) => b.k - a.k);
    let topHubs = degreeScores.slice(0, 3).filter(d => d.k > 0).map(d => `<a href="#" onclick="highlightNodeOnMap('${d.id}'); return false;" style="color:inherit; text-decoration:underline;">${d.id}</a>`).join(', ') || '-';
    let statHubsEl = document.getElementById('statHubs');
    if(statHubsEl) statHubsEl.innerHTML = topHubs;
    
    if (E === 0) {
        if(document.getElementById('statCloseness')) document.getElementById('statCloseness').textContent = '-';
        return [];
    }

    function calcStats(matrix, isReal = false) {
        let cTotal = 0; let activeNodes = 0;
        let totalPath = 0; let pathsCount = 0;
        let linksTotal = 0;
        let maxCloseness = -1;
        let maxClosenessNode = -1;
        
        for(let i=0; i<N; i++) {
            let neighbors = [];
            for(let j=0; j<N; j++) {
                if(matrix[i][j]) { neighbors.push(j); linksTotal++; }
            }
            let k = neighbors.length;
            if(k >= 2) {
                let links = 0;
                for(let a=0; a<k; a++) {
                    for(let b=a+1; b<k; b++) { if(matrix[neighbors[a]][neighbors[b]]) links++; }
                }
                cTotal += (2 * links) / (k * (k-1));
                activeNodes++;
            }
            
            // BFS for shortest path
            let nodePathsCount = 0;
            let nodeTotalPath = 0;
            let dist = Array(N).fill(-1);
            let q = [i]; dist[i] = 0;
            while(q.length > 0) {
                let u = q.shift();
                for(let v=0; v<N; v++) {
                    if(matrix[u][v] && dist[v] === -1) {
                        dist[v] = dist[u] + 1;
                        nodeTotalPath += dist[v];
                        nodePathsCount++;
                        q.push(v);
                    }
                }
            }
            totalPath += nodeTotalPath;
            pathsCount += nodePathsCount;
            
            let closeness = nodePathsCount > 0 ? (nodePathsCount / nodeTotalPath) : 0;
            if(closeness > maxCloseness) {
                maxCloseness = closeness;
                maxClosenessNode = i;
            }
        }
        
        if (isReal && maxClosenessNode >= 0) {
            let statClosenessEl = document.getElementById('statCloseness');
            let cId = networkData.nodes[maxClosenessNode].id;
            if(statClosenessEl) statClosenessEl.innerHTML = `<a href="#" onclick="highlightNodeOnMap('${cId}'); return false;" style="color:inherit; text-decoration:underline;">${cId}</a>`;
        }
        
        const cc = activeNodes > 0 ? (cTotal / activeNodes) : 0;
        const sp = pathsCount > 0 ? (totalPath / pathsCount) : 0;
        const avgK = linksTotal / N;
        return { cc, sp, avgK };
    }
    
    const realStats = calcStats(adj, true);
    
    function fillEdgesRandomly(matrix, targetEdges) {
        let currentEdges = 0;
        for(let i=0; i<N; i++){
            for(let j=i+1; j<N; j++){
                if(matrix[i][j]) currentEdges++;
            }
        }
        let attempts = 0;
        while(currentEdges < targetEdges && attempts < targetEdges*100) {
            let u = Math.floor(Math.random() * N);
            let v = Math.floor(Math.random() * N);
            if(u !== v && !matrix[u][v]) {
                matrix[u][v] = 1; matrix[v][u] = 1;
                currentEdges++;
            }
            attempts++;
        }
    }

    function removeEdgesRandomly(matrix, targetEdges) {
        let edgesList = [];
        for(let i=0; i<N; i++){
            for(let j=i+1; j<N; j++){
                if(matrix[i][j]) edgesList.push([i,j]);
            }
        }
        while(edgesList.length > targetEdges) {
            let idx = Math.floor(Math.random() * edgesList.length);
            let [u, v] = edgesList[idx];
            matrix[u][v] = 0; matrix[v][u] = 0;
            edgesList.splice(idx, 1);
        }
    }
    
    // 1. ER Random (G(N, M) model)
    const er_adj = Array(N).fill(0).map(() => Array(N).fill(0));
    fillEdgesRandomly(er_adj, E);
    
    // 2. Watts-Strogatz
    const ws_adj = Array(N).fill(0).map(() => Array(N).fill(0));
    let K = Math.floor((2*E) / N);
    if(K % 2 !== 0) K -= 1; if(K < 2) K = 2;
    for(let i=0; i<N; i++) {
        for(let j=1; j<=K/2; j++) {
            let neighbor = (i + j) % N;
            ws_adj[i][neighbor] = 1; ws_adj[neighbor][i] = 1;
        }
    }
    for(let i=0; i<N; i++) {
        for(let j=1; j<=K/2; j++) {
            let right = (i + j) % N;
            if(ws_adj[i][right] && Math.random() < 0.1) {
                ws_adj[i][right] = 0; ws_adj[right][i] = 0;
                let w = Math.floor(Math.random() * N);
                let attempts = 0;
                while((w === i || ws_adj[i][w]) && attempts < 50) { w = Math.floor(Math.random() * N); attempts++; }
                if(w !== i && !ws_adj[i][w]) { ws_adj[i][w] = 1; ws_adj[w][i] = 1; }
                else { ws_adj[i][right] = 1; ws_adj[right][i] = 1; }
            }
        }
    }
    let wsE = 0;
    for(let i=0; i<N; i++) for(let j=i+1; j<N; j++) if(ws_adj[i][j]) wsE++;
    if(wsE < E) fillEdgesRandomly(ws_adj, E);
    else if(wsE > E) removeEdgesRandomly(ws_adj, E);
    
    // 3. Barabasi-Albert
    const ba_adj = Array(N).fill(0).map(() => Array(N).fill(0));
    let m = Math.max(1, Math.floor(E / N));
    let degrees = Array(N).fill(0);
    for(let i=0; i<m; i++) {
        for(let j=0; j<m; j++) { if(i!==j && !ba_adj[i][j]) { ba_adj[i][j] = 1; ba_adj[j][i] = 1; degrees[i]++; } }
    }
    for(let i=m; i<N; i++) {
        let targets = [];
        let totalDeg = degrees.reduce((a,b)=>a+b, 0);
        let attempts = 0;
        while(targets.length < m && attempts < m*10) {
            let r = Math.random() * totalDeg;
            let sum = 0;
            for(let j=0; j<i; j++) {
                sum += degrees[j];
                if(r <= sum) {
                    if(!targets.includes(j)) targets.push(j);
                    break;
                }
            }
            attempts++;
        }
        targets.forEach(t => { ba_adj[i][t] = 1; ba_adj[t][i] = 1; degrees[i]++; degrees[t]++; });
    }
    let baE = 0;
    for(let i=0; i<N; i++) for(let j=i+1; j<N; j++) if(ba_adj[i][j]) baE++;
    
    if(baE < E) fillEdgesRandomly(ba_adj, E);
    else if(baE > E) removeEdgesRandomly(ba_adj, E);

    return [
        {model: 'Real', stats: realStats},
        {model: 'ER', stats: calcStats(er_adj)},
        {model: 'WS', stats: calcStats(ws_adj)},
        {model: 'BA', stats: calcStats(ba_adj)}
    ];
}

function updateMetrics() {
    const tbody = document.querySelector('#benchmarkTable tbody');
    tbody.innerHTML = '';
    const results = getGraphMetrics();
    results.forEach(r => {
        const tr = document.createElement('tr');
        
        let modelTooltip = "";
        if(r.model === 'Real') modelTooltip = "The empirical network constructed from data";
        else if(r.model === 'ER') modelTooltip = "Erdős-Rényi: Random graph with the same density";
        else if(r.model === 'WS') modelTooltip = "Watts-Strogatz: Small-world model with rewiring probability 0.1";
        else if(r.model === 'BA') modelTooltip = "Barabási-Albert: Scale-free model built via preferential attachment";
        
        tr.innerHTML = `<td class="has-tooltip" data-tooltip="${modelTooltip}" style="font-weight:600;">${r.model}</td>
                        <td>${r.stats.avgK.toFixed(1)}</td>
                        <td>${r.stats.cc.toFixed(3)}</td>
                        <td>${r.stats.sp.toFixed(2)}</td>`;
        tbody.appendChild(tr);
    });
}

// ==========================================
// COMPARISON MODAL LOGIC
// ==========================================
let comparisonCountries = [];
let countryDataCache = {};
const colors = ['#38bdf8', '#fb923c', '#a78bfa', '#4ade80', '#f43f5e', '#facc15', '#22d3ee', '#e879f9'];

async function addCountryToComparison() {
    let sel = document.getElementById('cmpAddCountrySelect').value;
    if(!sel || comparisonCountries.includes(sel)) return;
    
    if(!countryDataCache[sel]) {
        try {
            const resp = await fetch(`data/network_data_${sel}.json`);
            if(resp.ok) {
                countryDataCache[sel] = await resp.json();
            } else return;
        } catch(e) { return; }
    }
    comparisonCountries.push(sel);
    renderComparisonCards();
    drawComparisonPlot();
}

// Make globally accessible for inline onclick handlers
window.removeCountryFromComparison = function(country) {
    comparisonCountries = comparisonCountries.filter(c => c !== country);
    renderComparisonCards();
    drawComparisonPlot();
};

function renderComparisonCards() {
    let container = document.getElementById('cmpCardsContainer');
    if(!container) return;
    container.innerHTML = '';
    comparisonCountries.forEach((c, idx) => {
        let color = colors[idx % colors.length];
        let d = document.createElement('div');
        d.style.cssText = `background:rgba(0,0,0,0.4); border-left:4px solid ${color}; padding:8px 12px; border-radius:4px; display:flex; align-items:center; gap:10px; min-width:120px; font-size:0.85rem;`;
        d.innerHTML = `
            <span style="font-weight:600; color:#f8fafc;">${c === 'GLOBAL' ? 'GLO' : c}</span>
            <button onclick="removeCountryFromComparison('${c}')" style="background:transparent; border:none; color:#ef4444; cursor:pointer;"><i class="fa-solid fa-xmark"></i></button>
        `;
        container.appendChild(d);
    });
}

function drawComparisonPlot() {
    if(comparisonCountries.length === 0) {
        Plotly.purge('cmpPlotArea');
        return;
    }
    
    let plotType = document.getElementById('cmpPlotType').value;
    let metric = document.getElementById('cmpMetric').value;
    let lag = parseInt(document.getElementById('cmpLag').value);
    let thrMode = document.getElementById('cmpThrMode').value;
    let thrVal = parseFloat(document.getElementById('cmpThrVal').value);
    let requireSig = document.getElementById('cmpSig').checked;
    
    let showFit = document.getElementById('cmpFitToggle').checked;
    let onlyFit = document.getElementById('cmpOnlyFit').checked;
    let fitModelVal = document.getElementById('cmpFitModel').value;
    
    let traces = [];
    
    comparisonCountries.forEach((c, idx) => {
        let color = colors[idx % colors.length];
        let data = countryDataCache[c];
        if(!data) return;
        
        let validEdges = [];
        data.edges.forEach(e => {
            if(e.lag === lag && e.metrics && e.metrics[metric]) {
                let mData = e.metrics[metric];
                if(!requireSig || mData.sig) validEdges.push({...e, _val: mData.val});
            }
        });
        
        validEdges.sort((a,b) => b._val - a._val);
        let currentEdges = [];
        if(thrMode === 'fixed') {
            currentEdges = validEdges.filter(e => e._val >= thrVal);
        } else {
            let keepCount = Math.max(1, Math.floor(validEdges.length * (thrVal / 100)));
            currentEdges = validEdges.slice(0, keepCount);
        }
        
        let outDegree = {}; let inDegree = {};
        data.nodes.forEach(n => { outDegree[n.id] = 0; inDegree[n.id] = 0; });
        currentEdges.forEach(e => { outDegree[e.source]++; inDegree[e.target]++; });
        
        let cName = c === 'GLOBAL' ? 'GLO' : c;
        
        if (plotType === 'distDecay') {
            let xArr = []; let yArr = [];
            currentEdges.forEach(e => { xArr.push(e.distance); yArr.push(e._val); });
            if (!onlyFit) {
                traces.push({ x: xArr, y: yArr, mode: 'markers', type: 'scatter', name: cName, marker: {color: color, size:5, opacity:0.6} });
            }
            
            if (showFit && xArr.length > 2) {
                let fitRes = fitModel(xArr, yArr, fitModelVal);
                if (fitRes) {
                    traces.push({ x: fitRes.fitX, y: fitRes.fitY, mode: 'lines', type: 'scatter', name: `${cName} (${fitRes.eq})`, line: {color: color, dash: 'dot', width:2}, hoverinfo:'none' });
                }
            }
        } 
        else if (plotType === 'degreeDist') {
            let degCounts = {};
            data.nodes.forEach(n => {
                let k = outDegree[n.id] + inDegree[n.id];
                if(k>0) degCounts[k] = (degCounts[k] || 0) + 1;
            });
            let xArr = Object.keys(degCounts).map(Number);
            let yArr = xArr.map(k => degCounts[k]);
            
            if (!onlyFit) {
                traces.push({ x: xArr, y: yArr, type: 'scatter', mode: 'markers+lines', name: cName, marker: {color: color, opacity:0.8} });
            }
            
            if (showFit && xArr.length > 2) {
                let fitRes = fitModel(xArr, yArr, fitModelVal);
                if (fitRes) {
                    traces.push({ x: fitRes.fitX, y: fitRes.fitY, mode: 'lines', type: 'scatter', name: `${cName} (${fitRes.eq})`, line: {color: color, dash: 'dot', width:2}, hoverinfo:'none' });
                }
            }
        }
        else if (plotType === 'assortKnn') {
            let k_knn = {}; let k_counts = {};
            data.nodes.forEach(n => {
                let d = outDegree[n.id] + inDegree[n.id];
                if(d===0) return;
                let sum = 0;
                currentEdges.forEach(e => {
                    if(e.source === n.id) sum += outDegree[e.target] + inDegree[e.target];
                    if(e.target === n.id) sum += outDegree[e.source] + inDegree[e.source];
                });
                k_knn[d] = (k_knn[d] || 0) + (sum / d);
                k_counts[d] = (k_counts[d] || 0) + 1;
            });
            let xArr = Object.keys(k_knn).map(Number);
            let yArr = xArr.map(k => k_knn[k] / k_counts[k]);
            if (!onlyFit) {
                traces.push({ x: xArr, y: yArr, mode: 'markers', type: 'scatter', name: cName, marker: {color: color, size:6, opacity:0.8} });
            }
            
            if (showFit && xArr.length > 2) {
                let fitRes = fitModel(xArr, yArr, fitModelVal);
                if (fitRes) {
                    traces.push({ x: fitRes.fitX, y: fitRes.fitY, mode: 'lines', type: 'scatter', name: `${cName} (${fitRes.eq})`, line: {color: color, dash: 'dot', width:2}, hoverinfo:'none' });
                }
            }
        }
        else if (plotType === 'assortScatter') {
            let xArr = []; let yArr = [];
            currentEdges.forEach(e => {
                let k1 = outDegree[e.source] + inDegree[e.source];
                let k2 = outDegree[e.target] + inDegree[e.target];
                xArr.push(k1, k2); yArr.push(k2, k1);
            });
            if (!onlyFit) {
                traces.push({ x: xArr, y: yArr, mode: 'markers', type: 'scatter', name: cName, marker: {color: color, size:4, opacity:0.4} });
            }
        }
    });
    
    let layout = {
        paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
        font: { color: '#f8fafc', family: 'Outfit' },
        margin: { t:40, b:40, l:50, r:20 },
        xaxis: { showgrid: true, gridcolor: 'rgba(255,255,255,0.05)' },
        yaxis: { showgrid: true, gridcolor: 'rgba(255,255,255,0.05)' },
        hovermode: 'closest',
        title: { text: document.getElementById('cmpPlotType').options[document.getElementById('cmpPlotType').selectedIndex].text }
    };
    
    if(plotType === 'distDecay') { 
        layout.xaxis.title = 'Distance (km)'; 
        layout.yaxis.title = 'Weight'; 
        layout.yaxis.range = [0, 1];
    }
    if(plotType === 'degreeDist') { 
        layout.xaxis.title = 'k (Degree)'; layout.yaxis.title = 'Count'; 
        // Force log scale for Degree Dist if needed? Actually leave it linear and let them see, or maybe they want log? 
        // The comparison panel doesn't have the lin/log toggles yet, default to linear or log?
        // Let's keep it linear but if they want we can add a toggle.
    }
    if(plotType === 'assortKnn') { layout.xaxis.title = 'k'; layout.yaxis.title = 'Knn'; }
    if(plotType === 'assortScatter') {
        layout.xaxis.title = 'k1'; layout.yaxis.title = 'k2';
        let maxX = 0;
        traces.forEach(t => { if(t.x && t.x.length > 0) maxX = Math.max(maxX, Math.max(...t.x)); });
        traces.push({ x:[0, maxX], y:[0, maxX], mode:'lines', type:'scatter', name:'y=x', line:{color:'#94a3b8', dash:'dash'}, hoverinfo:'none' });
    }
    
    Plotly.react('cmpPlotArea', traces, layout, {displayModeBar: true});
}
