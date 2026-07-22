/**
 * TS Individual Module
 * Gestisce la vista "Diagnostica TSA" per serie temporali individuali (regionali e nazionali).
 * Sovrascrive le funzioni placeholder definite originariamente in app.js.
 */

let tsaStlData = null;

// Funzione globale per caricare i dati JSON della decomposizione STL
async function loadTsaStlData() {
    if (tsaStlData) return tsaStlData;
    try {
        const res = await fetch('data/ts/ts_stl_series.json');
        if (res.ok) {
            tsaStlData = await res.json();
        } else {
            console.warn("ts_stl_series.json non trovato.");
            tsaStlData = {};
        }
    } catch (e) {
        console.error("Errore nel caricamento di ts_stl_series.json", e);
        tsaStlData = {};
    }
    return tsaStlData;
}

// Avvia il pre-loading non bloccante
loadTsaStlData();

// Sovrascriviamo la funzione onTsaRegionChange di app.js
window.onTsaRegionChange = function() {
    renderTsaDiagnosticImage();
    if (typeof loadTsaGrangerTable === 'function') loadTsaGrangerTable();
    if (typeof loadTsaMetricsTable === 'function') loadTsaMetricsTable();
};

// Sovrascriviamo la funzione onTsaDiagnosticChange di app.js
window.onTsaDiagnosticChange = function() {
    renderTsaDiagnosticImage();
};

// Array di variabili predittive comuni per testare le immagini multiple (CCF, MP)
const commonDrivers = ["wfp_price", "rainfall", "ndvi_vim", "acled_events", "idp_population"];

// Sovrascriviamo renderTsaDiagnosticImage di app.js
window.renderTsaDiagnosticImage = async function() {
    const container = document.getElementById('tsa-diagnostic-image-container');
    if (!container) return;
    
    // Lo stato è in window.state gestito da app.js
    const code = window.state.selectedCountry;
    const regionSelector = document.getElementById('tsa-region-selector');
    const diagSelector = document.getElementById('tsa-diagnostic-selector');
    
    if (!code || !regionSelector || !diagSelector) return;
    
    const pcode = regionSelector.value; // 'national' o pcode (es. AFG01)
    const diagKey = diagSelector.value;
    
    // Resettiamo il container
    container.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 2rem;">
        <i class="fa-solid fa-circle-notch fa-spin" style="font-size: 2rem; margin-bottom: 1rem;"></i><br>Caricamento diagnostica...
    </div>`;

    // 1. DECOMPOSIZIONE STL INTERATTIVA (ApexCharts)
    if (diagKey === 'stl') {
        let data = await loadTsaStlData();
        let seriesData = (data && data[pcode]) ? data[pcode] : null;
        
        // Fallback: Se non presente in ts_stl_series.json, calcola le serie storiche interattive da countryCache
        if (!seriesData && window.countryCache && window.countryCache[code]) {
            const cData = window.countryCache[code];
            let rawTrends = [];
            if (pcode === 'national') {
                rawTrends = (cData.trends && cData.trends.adm1 && cData.trends.adm1.length > 0) ? cData.trends.adm1 : (cData.trends ? cData.trends.adm2 : []);
            } else if (cData.regions) {
                if (cData.regions.adm1 && cData.regions.adm1[pcode]) rawTrends = cData.regions.adm1[pcode];
                else if (cData.regions.adm2 && cData.regions.adm2[pcode]) rawTrends = cData.regions.adm2[pcode];
            }
            
            if (rawTrends && rawTrends.length > 0) {
                const dates = rawTrends.map(r => r.from);
                const observed = rawTrends.map(r => r.phase_3plus_percentage || 0);
                const trend = [];
                const seasonal = [];
                const residual = [];
                for (let i = 0; i < observed.length; i++) {
                    const prev = observed[Math.max(0, i - 1)];
                    const next = observed[Math.min(observed.length - 1, i + 1)];
                    const tr = (prev + observed[i] + next) / 3;
                    trend.push(tr);
                    const res = observed[i] - tr;
                    residual.push(res);
                    seasonal.push(0);
                }
                seriesData = { dates, observed, trend, seasonal, residual };
            }
        }
        
        if (!seriesData || !seriesData.dates || seriesData.dates.length === 0) {
            container.innerHTML = `<div style="color: #ef4444; padding: 2rem; text-align: center;">Dati serie temporali non disponibili per ${pcode}.</div>`;
            return;
        }

        // Prepariamo l'HTML per i 4 container ApexCharts
        container.innerHTML = `
            <div style="width: 100%; display: flex; flex-direction: column; gap: 0.5rem; background: var(--bg-card); padding: 1rem; border-radius: 8px;">
                <div style="font-size: 0.8rem; color: #a5b4fc; font-weight: 700; margin-bottom: 0.25rem;">Decomposizione STL Interattiva (Zoom / Hover) - ${pcode}</div>
                <div id="chart-stl-observed" style="height: 160px;"></div>
                <div id="chart-stl-trend" style="height: 160px;"></div>
                <div id="chart-stl-seasonal" style="height: 160px;"></div>
                <div id="chart-stl-residual" style="height: 160px;"></div>
            </div>
        `;
        
        // Funzione helper per formattare dati per ApexCharts
        const formatData = (arr) => seriesData.dates.map((d, i) => ({ x: new Date(d).getTime(), y: arr[i] }));
        
        const commonOptions = {
            chart: {
                type: 'line',
                group: 'stl-sync', // sincronizza hover e zoom
                toolbar: { show: true, tools: { download: false, selection: true, zoom: true, zoomin: true, zoomout: true, pan: true, reset: true } },
                animations: { enabled: true },
                background: 'transparent'
            },
            stroke: { width: 2, curve: 'smooth' },
            xaxis: {
                type: 'datetime',
                labels: { style: { colors: '#94a3b8', fontSize: '10px' } },
                axisBorder: { show: false },
                axisTicks: { show: false }
            },
            yaxis: {
                labels: { style: { colors: '#94a3b8', fontSize: '10px' }, formatter: (val) => val ? val.toFixed(1) : '' }
            },
            theme: { mode: 'dark' },
            grid: { borderColor: 'rgba(255,255,255,0.05)' },
            tooltip: { x: { format: 'MMM yyyy' } }
        };
        
        // 1. Observed (IPC/Target)
        new ApexCharts(document.querySelector("#chart-stl-observed"), {
            ...commonOptions,
            colors: ['#ef4444'],
            series: [{ name: 'Observed (IPC Phase 3+ %)', data: formatData(seriesData.observed) }],
            chart: { ...commonOptions.chart, id: 'observed' }
        }).render();

        // 2. Trend
        new ApexCharts(document.querySelector("#chart-stl-trend"), {
            ...commonOptions,
            colors: ['#3b82f6'],
            series: [{ name: 'Trend (STL Component)', data: formatData(seriesData.trend) }],
            chart: { ...commonOptions.chart, id: 'trend' }
        }).render();

        // 3. Seasonal
        new ApexCharts(document.querySelector("#chart-stl-seasonal"), {
            ...commonOptions,
            colors: ['#10b981'],
            series: [{ name: 'Seasonal Component', data: formatData(seriesData.seasonal) }],
            chart: { ...commonOptions.chart, id: 'seasonal' }
        }).render();

        // 4. Residual
        new ApexCharts(document.querySelector("#chart-stl-residual"), {
            ...commonOptions,
            colors: ['#a855f7'],
            series: [{ name: 'Residual (Anomalies)', data: formatData(seriesData.residual) }],
            chart: { ...commonOptions.chart, id: 'residual' }
        }).render();

        return;
    }

    // 2. IMMAGINI DIAGNOSTICHE
    // Mappatura verso i risultati della nuova pipeline TS_Results
    const basePath = "../TS/TS_Results/Reports";
    let htmlContent = "";

    const generateImgTag = (src, title) => `
        <div style="flex: 1; min-width: 300px; display:flex; flex-direction:column; align-items:center; margin-bottom: 1rem;">
            ${title ? `<span style="font-size:0.8rem; color:var(--text-secondary); margin-bottom:0.5rem;">${title}</span>` : ''}
            <img src="${src}" style="width: 100%; max-width: 600px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.1);" 
                 onerror="this.parentElement.style.display='none'">
        </div>
    `;

    if (diagKey === 'acf') {
        // ACF/PACF (01_stationarity_stl)
        htmlContent = `<div style="display:flex; flex-wrap:wrap; gap:1rem; width: 100%;">
            ${generateImgTag(`${basePath}/${code}/01_stationarity_stl/ACF_${code}_${pcode}.png`, "Autocorrelazione (Target IPC)")}
            ${generateImgTag(`${basePath}/${code}/01_stationarity_stl/ADF_${code}_${pcode}.png`, "Stationarity Test (ADF)")}
        </div>`;
    } 
    else if (diagKey === 'ccf') {
        // Cross-Correlation (02_cross_correlation)
        htmlContent = `<div style="display:flex; flex-wrap:wrap; gap:1rem; width: 100%;">`;
        commonDrivers.forEach(driver => {
            htmlContent += generateImgTag(`${basePath}/${code}/02_cross_correlation/CCF_${code}_${pcode}_${driver}.png`, `Cross-Correlation: ${driver.replace('_', ' ').toUpperCase()}`);
        });
        htmlContent += `</div>`;
    }
    else if (diagKey === 'matrix_profile') {
        // Matrix Profile & Shapelets
        htmlContent = `<div style="display:flex; flex-wrap:wrap; gap:1rem; width: 100%;">`;
        commonDrivers.forEach(driver => {
            htmlContent += generateImgTag(`${basePath}/${code}/03_matrix_profile/MP_${code}_${pcode}_${driver}.png`, `Matrix Profile Anomalies: ${driver.replace('_', ' ').toUpperCase()}`);
            htmlContent += generateImgTag(`${basePath}/${code}/04_shapelets/shapelet_${code}_${pcode}_${driver}.png`, `Shapelets Discovered: ${driver.replace('_', ' ').toUpperCase()}`);
        });
        htmlContent += `</div>`;
    }
    else {
        // Fallback per metriche generiche (usa il vecchio pathing se non matchato dai nuovi)
        htmlContent = `<div style="color: var(--text-muted); padding: 2rem; text-align: center;">
            <i class="fa-solid fa-tools" style="font-size: 2rem; margin-bottom: 0.5rem; opacity: 0.5;"></i><br>
            Funzionalità in aggiornamento (Fallback UI).
        </div>`;
    }

    container.innerHTML = htmlContent;
    
    // Se, dopo un secondo, il container risulta vuoto perché tutti gli onerror hanno nascosto i parent, mostra messaggio di errore
    setTimeout(() => {
        const visibleImages = Array.from(container.querySelectorAll('img')).filter(img => img.parentElement.style.display !== 'none');
        if (visibleImages.length === 0 && diagKey !== 'stl') {
            container.innerHTML = `<div style="color: var(--text-muted); padding: 2rem; text-align: center;">
                <i class="fa-solid fa-image-slash" style="font-size: 2rem; margin-bottom: 0.5rem; display: block; opacity: 0.4;"></i>
                Nessuna diagnostica generata per questa configurazione.<br>
                <span style="font-size: 0.75rem; opacity: 0.6;">(I file richiesti non sono presenti nella cartella TS_Results)</span>
            </div>`;
        }
    }, 1000);
};
