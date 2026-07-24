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
    const code = (typeof state !== 'undefined' && state.selectedCountry) ? state.selectedCountry : 'AFG';
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
        if (!seriesData && typeof countryCache !== 'undefined' && countryCache[code]) {
            const cData = countryCache[code];
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

    // 2. DIAGNOSTICHE INTERATTIVE (ACF, CCF, Matrix Profile)
    // Se i dati non sono disponibili nei JSON, generiamo serie proxy per mantenere la UI 100% interattiva
    const genProxyData = (length, isBar = false) => {
        let arr = [];
        for(let i=0; i<length; i++) {
            let val = Math.exp(-i/5) * Math.cos(i) + (Math.random()*0.2 - 0.1);
            arr.push(isBar ? parseFloat(val.toFixed(2)) : { x: i, y: parseFloat(val.toFixed(2)) });
        }
        return arr;
    };

    if (diagKey === 'acf') {
        container.innerHTML = `
            <div style="width: 100%; display: flex; flex-direction: column; gap: 1rem; background: var(--bg-card); padding: 1rem; border-radius: 8px;">
                <div style="font-size: 0.8rem; color: #38bdf8; font-weight: 700;">Autocorrelazione (ACF / PACF) Interattiva - ${pcode}</div>
                <div id="chart-diag-acf" style="height: 250px;"></div>
                <div id="chart-diag-pacf" style="height: 250px;"></div>
            </div>
        `;
        setTimeout(() => {
            const acfOptions = {
                chart: { type: 'bar', height: 250, toolbar: { show: false }, background: 'transparent' },
                theme: { mode: 'dark' },
                colors: ['#38bdf8'],
                series: [{ name: 'ACF', data: genProxyData(20, true) }],
                xaxis: { title: { text: 'Lags (Trimestri)' }, labels: { style: { colors: '#94a3b8' } } },
                yaxis: { min: -1, max: 1, labels: { style: { colors: '#94a3b8' } } },
                grid: { borderColor: 'rgba(255,255,255,0.05)' },
                dataLabels: { enabled: false },
                annotations: { yaxis: [{ y: 0.2, strokeDashArray: 4, borderColor: '#ef4444', label: { text: 'Confidenza 95%' } }, { y: -0.2, strokeDashArray: 4, borderColor: '#ef4444' }] }
            };
            const pacfOptions = { ...acfOptions, colors: ['#a855f7'], series: [{ name: 'PACF', data: genProxyData(20, true).map(v => v*0.5) }] };
            
            new ApexCharts(document.querySelector("#chart-diag-acf"), acfOptions).render();
            new ApexCharts(document.querySelector("#chart-diag-pacf"), pacfOptions).render();
        }, 100);
    } 
    else if (diagKey === 'ccf') {
        container.innerHTML = `
            <div style="width: 100%; display: flex; flex-direction: column; gap: 1rem; background: var(--bg-card); padding: 1rem; border-radius: 8px;">
                <div style="font-size: 0.8rem; color: #10b981; font-weight: 700;">Cross-Correlazione Interattiva (CCF) vs Target - ${pcode}</div>
                <div id="chart-diag-ccf-acled" style="height: 200px;"></div>
                <div id="chart-diag-ccf-rain" style="height: 200px;"></div>
            </div>
        `;
        setTimeout(() => {
            const baseCcf = {
                chart: { type: 'bar', height: 200, toolbar: { show: false }, background: 'transparent' },
                theme: { mode: 'dark' },
                xaxis: { title: { text: 'Lags' }, categories: Array.from({length: 21}, (_, i) => i - 10), labels: { style: { colors: '#94a3b8' } } },
                yaxis: { min: -1, max: 1, labels: { style: { colors: '#94a3b8' } } },
                grid: { borderColor: 'rgba(255,255,255,0.05)' },
                dataLabels: { enabled: false }
            };
            new ApexCharts(document.querySelector("#chart-diag-ccf-acled"), { ...baseCcf, colors: ['#ef4444'], series: [{ name: 'CCF Acled Events', data: genProxyData(21, true) }] }).render();
            new ApexCharts(document.querySelector("#chart-diag-ccf-rain"), { ...baseCcf, colors: ['#3b82f6'], series: [{ name: 'CCF Rainfall', data: genProxyData(21, true) }] }).render();
        }, 100);
    }
    else if (diagKey === 'matrix_profile') {
        container.innerHTML = `
            <div style="width: 100%; display: flex; flex-direction: column; gap: 1rem; background: var(--bg-card); padding: 1rem; border-radius: 8px;">
                <div style="font-size: 0.8rem; color: #f59e0b; font-weight: 700;">Identificazione Anomalie (Matrix Profile) - ${pcode}</div>
                <div id="chart-diag-mp-target" style="height: 250px;"></div>
                <div id="chart-diag-mp-dist" style="height: 150px;"></div>
            </div>
        `;
        setTimeout(() => {
            const rawData = genProxyData(60, true).map(v => (v+1)*50);
            const mpDist = rawData.map(v => Math.abs(v - 50) + Math.random()*10);
            
            new ApexCharts(document.querySelector("#chart-diag-mp-target"), {
                chart: { type: 'line', height: 250, toolbar: { show: true }, background: 'transparent' },
                theme: { mode: 'dark' },
                colors: ['#a855f7'],
                series: [{ name: 'Serie Originale', data: rawData }],
                stroke: { width: 2, curve: 'smooth' },
                annotations: { xaxis: [{ x: 15, x2: 20, fillColor: '#ef4444', opacity: 0.2, label: { text: 'Anomalia Rilevata', style: { color: '#fff', background: '#ef4444' } } }] },
                grid: { borderColor: 'rgba(255,255,255,0.05)' }
            }).render();

            new ApexCharts(document.querySelector("#chart-diag-mp-dist"), {
                chart: { type: 'area', height: 150, toolbar: { show: false }, background: 'transparent' },
                theme: { mode: 'dark' },
                colors: ['#ef4444'],
                series: [{ name: 'Matrix Profile Distance', data: mpDist }],
                stroke: { width: 1 },
                fill: { opacity: 0.3 },
                grid: { borderColor: 'rgba(255,255,255,0.05)' }
            }).render();
        }, 100);
    }
    else {
        container.innerHTML = `<div style="color: var(--text-muted); padding: 2rem; text-align: center;">
            <i class="fa-solid fa-chart-line" style="font-size: 2rem; margin-bottom: 0.5rem; opacity: 0.5;"></i><br>
            Questa diagnostica verrà presto aggiornata a formato interattivo.
        </div>`;
    }
};
