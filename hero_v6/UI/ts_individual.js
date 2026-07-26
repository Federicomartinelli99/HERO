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

// Cache globale per i dataset riorganizzati
let tsaReorganizedCache = {};

async function loadTsaReorganizedCountry(countryCode) {
    if (!countryCode) countryCode = 'AFG';
    if (tsaReorganizedCache[countryCode]) return tsaReorganizedCache[countryCode];
    try {
        const res = await fetch(`data/ts_reorganized/${countryCode}.json`);
        if (res.ok) {
            tsaReorganizedCache[countryCode] = await res.json();
            return tsaReorganizedCache[countryCode];
        } else {
            console.warn(`File data/ts_reorganized/${countryCode}.json non trovato.`);
        }
    } catch (e) {
        console.error(`Errore nel caricamento di data/ts_reorganized/${countryCode}.json:`, e);
    }
    return null;
}

// Avvia il pre-loading non bloccante
loadTsaStlData();
loadTsaReorganizedCountry('AFG');

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

// Sovrascriviamo renderTsaDiagnosticImage di app.js per utilizzare 100% dati reali da results_reorganized
window.renderTsaDiagnosticImage = async function() {
    const container = document.getElementById('tsa-diagnostic-image-container');
    if (!container) return;
    
    // Lo stato è in window.state gestito da app.js
    const code = (typeof state !== 'undefined' && state.selectedCountry) ? state.selectedCountry : 'AFG';
    const regionSelector = document.getElementById('tsa-region-selector');
    const diagSelector = document.getElementById('tsa-diagnostic-selector');
    
    if (!code || !regionSelector || !diagSelector) return;
    
    const pcode = regionSelector.value || 'national';
    const diagKey = diagSelector.value || '01_STL_Decomposition';
    
    // Resettiamo il container con spinner
    container.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 3rem;">
        <i class="fa-solid fa-circle-notch fa-spin" style="font-size: 2.5rem; margin-bottom: 1rem; color: #6366f1;"></i><br>
        <span style="font-size: 1rem; font-weight: 500;">Caricamento diagnostica reale da results_reorganized...</span>
    </div>`;

    const countryData = await loadTsaReorganizedCountry(code);
    if (!countryData) {
        container.innerHTML = `<div style="color: #ef4444; padding: 2rem; text-align: center;">
            <i class="fa-solid fa-triangle-exclamation" style="font-size: 2rem; margin-bottom: 0.5rem;"></i><br>
            Dati TSA riorganizzati non trovati per il paese <b>${code}</b>.
        </div>`;
        return;
    }

    // Ricerca intelligente degli item per la categoria selezionata
    let itemsMap = null;
    let fallbackContext = '';

    if (countryData.regions && countryData.regions[pcode] && countryData.regions[pcode][diagKey]) {
        itemsMap = countryData.regions[pcode][diagKey];
    }
    if ((!itemsMap || Object.keys(itemsMap).length === 0) && countryData.country_level && countryData.country_level[diagKey]) {
        itemsMap = countryData.country_level[diagKey];
        fallbackContext = ' (Livello Paese)';
    }
    if ((!itemsMap || Object.keys(itemsMap).length === 0) && countryData.regions && countryData.regions['clustering'] && countryData.regions['clustering'][diagKey]) {
        itemsMap = countryData.regions['clustering'][diagKey];
        fallbackContext = ' (Clustering Nazionale/Regionale)';
    }
    if ((!itemsMap || Object.keys(itemsMap).length === 0) && countryData.regions && countryData.regions['national'] && countryData.regions['national'][diagKey]) {
        itemsMap = countryData.regions['national'][diagKey];
        fallbackContext = ' (Livello Nazionale Aggregato)';
    }

    if (!itemsMap || Object.keys(itemsMap).length === 0) {
        container.innerHTML = `<div style="color: var(--text-muted); padding: 3rem; text-align: center;">
            <i class="fa-solid fa-folder-open" style="font-size: 2.5rem; opacity: 0.4; margin-bottom: 0.75rem;"></i><br>
            <span style="font-size: 1.1rem; font-weight: 600;">Nessuna analisi disponibile per la categoria "${diagKey.replace(/_/g, ' ')}"</span><br>
            <span style="font-size: 0.85rem; opacity: 0.7;">Paese: ${code} &bull; Regione: ${pcode}</span>
        </div>`;
        return;
    }

    // Costruiamo il layout per i grafici
    container.innerHTML = '';
    const wrapper = document.createElement('div');
    wrapper.style.cssText = 'width: 100%; display: flex; flex-direction: column; gap: 1.5rem;';
    container.appendChild(wrapper);

    const entries = Object.entries(itemsMap);

    for (const [baseName, info] of entries) {
        const card = document.createElement('div');
        card.className = 'glass-card';
        card.style.cssText = 'background: rgba(30, 41, 59, 0.75); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 12px; padding: 1.5rem; width: 100%; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);';

        const cleanTitle = baseName.replace(/^([A-Z]{3}_([a-zA-Z0-9_-]+_)?)?/, '').replace(/_/g, ' ');
        const safeId = baseName.replace(/[^a-zA-Z0-9]/g, '_');

        let buttonsHtml = '';
        if (info.html_file) {
            buttonsHtml += `<a href="../TSA/results_reorganized/${diagKey}/${info.html_file}" target="_blank" class="sub-tab-btn" style="background: rgba(99, 102, 241, 0.2); color: #c7d2fe; border: 1px solid rgba(99, 102, 241, 0.4); text-decoration: none; padding: 0.4rem 0.8rem; font-size: 0.75rem; border-radius: 6px; display: inline-flex; align-items: center; gap: 0.4rem; transition: all 0.2s;"><i class="fa-solid fa-external-link-alt"></i> Apri HTML Stand-Alone</a>`;
        }
        if (info.png_file) {
            buttonsHtml += `<a href="../TSA/results_reorganized/${diagKey}/${info.png_file}" download="${info.png_file}" class="sub-tab-btn" style="background: rgba(51, 65, 85, 0.8); color: #e2e8f0; text-decoration: none; padding: 0.4rem 0.8rem; font-size: 0.75rem; border-radius: 6px; display: inline-flex; align-items: center; gap: 0.4rem; transition: all 0.2s;"><i class="fa-solid fa-image"></i> Salva PNG</a>`;
        }
        if (info.csv_file) {
            buttonsHtml += `<a href="../TSA/results_reorganized/${diagKey}/${info.csv_file}" download="${info.csv_file}" class="sub-tab-btn" style="background: rgba(16, 185, 129, 0.2); color: #6ee7b7; border: 1px solid rgba(16, 185, 129, 0.4); text-decoration: none; padding: 0.4rem 0.8rem; font-size: 0.75rem; border-radius: 6px; display: inline-flex; align-items: center; gap: 0.4rem; transition: all 0.2s;"><i class="fa-solid fa-file-csv"></i> Salva CSV</a>`;
        }

        card.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem; margin-bottom: 1.25rem; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 0.75rem;">
                <div>
                    <div style="font-size: 0.75rem; font-weight: 700; color: #818cf8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.2rem;"><i class="fa-solid fa-wave-square"></i> ${diagKey.replace(/_/g, ' ')} &bull; ${pcode}${fallbackContext}</div>
                    <h3 style="font-size: 1.15rem; font-weight: 700; color: white; margin: 0;">${cleanTitle || baseName}</h3>
                </div>
                <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
                    ${buttonsHtml}
                </div>
            </div>
            <div id="chart-area-${safeId}" style="width: 100%;"></div>
            <div id="image-area-${safeId}" style="width: 100%; margin-top: 1rem;"></div>
        `;

        wrapper.appendChild(card);

        const chartArea = card.querySelector(`#chart-area-${safeId}`);
        const imageArea = card.querySelector(`#image-area-${safeId}`);

        // 1. Renderizzazione Grafici Interattivi se ci sono dati CSV
        if (info.data && Array.isArray(info.data) && info.data.length > 0) {
            const data = info.data;
            const headers = Object.keys(data[0]);
            
            const commonOptions = {
                chart: {
                    type: 'line',
                    height: 280,
                    toolbar: { show: true, tools: { download: true, selection: true, zoom: true, zoomin: true, zoomout: true, pan: true, reset: true } },
                    background: 'transparent',
                    animations: { enabled: true }
                },
                stroke: { width: 2, curve: 'smooth' },
                theme: { mode: 'dark' },
                grid: { borderColor: 'rgba(255,255,255,0.05)' },
                xaxis: { labels: { style: { colors: '#94a3b8', fontSize: '10px' } } },
                yaxis: { labels: { style: { colors: '#94a3b8', fontSize: '10px' }, formatter: (val) => val ? val.toFixed(2) : '' } },
                tooltip: { theme: 'dark' }
            };

            // Caso speciale: Decomposizione STL (4 grafici sincronizzati)
            if (headers.includes('observed') && headers.includes('trend') && headers.includes('seasonal') && headers.includes('residual')) {
                chartArea.innerHTML = `
                    <div style="display: flex; flex-direction: column; gap: 0.75rem;">
                        <div id="stl-obs-${safeId}" style="height: 160px;"></div>
                        <div id="stl-tr-${safeId}" style="height: 160px;"></div>
                        <div id="stl-sea-${safeId}" style="height: 160px;"></div>
                        <div id="stl-res-${safeId}" style="height: 160px;"></div>
                    </div>
                `;
                const xVals = data.map(r => new Date(r.date || r.Date).getTime());
                const formatStl = (col) => data.map((r, i) => ({ x: xVals[i], y: r[col] }));

                new ApexCharts(card.querySelector(`#stl-obs-${safeId}`), {
                    ...commonOptions, chart: { ...commonOptions.chart, height: 160, group: `stl-${safeId}`, id: `obs-${safeId}` },
                    colors: ['#ef4444'], series: [{ name: 'Observed (IPC Phase 3+ %)', data: formatStl('observed') }],
                    xaxis: { ...commonOptions.xaxis, type: 'datetime' }
                }).render();

                new ApexCharts(card.querySelector(`#stl-tr-${safeId}`), {
                    ...commonOptions, chart: { ...commonOptions.chart, height: 160, group: `stl-${safeId}`, id: `tr-${safeId}` },
                    colors: ['#3b82f6'], series: [{ name: 'Trend Component', data: formatStl('trend') }],
                    xaxis: { ...commonOptions.xaxis, type: 'datetime' }
                }).render();

                new ApexCharts(card.querySelector(`#stl-sea-${safeId}`), {
                    ...commonOptions, chart: { ...commonOptions.chart, height: 160, group: `stl-${safeId}`, id: `sea-${safeId}` },
                    colors: ['#10b981'], series: [{ name: 'Seasonal Component', data: formatStl('seasonal') }],
                    xaxis: { ...commonOptions.xaxis, type: 'datetime' }
                }).render();

                new ApexCharts(card.querySelector(`#stl-res-${safeId}`), {
                    ...commonOptions, chart: { ...commonOptions.chart, height: 160, group: `stl-${safeId}`, id: `res-${safeId}` },
                    colors: ['#a855f7'], series: [{ name: 'Residual (Anomalies)', data: formatStl('residual') }],
                    xaxis: { ...commonOptions.xaxis, type: 'datetime' }
                }).render();
            }
            // Caso speciale: ACF e PACF
            else if (headers.includes('lag') && headers.includes('acf') && headers.includes('pacf')) {
                chartArea.innerHTML = `
                    <div style="display: flex; flex-direction: column; gap: 1rem;">
                        <div id="acf-chart-${safeId}" style="height: 220px;"></div>
                        <div id="pacf-chart-${safeId}" style="height: 220px;"></div>
                    </div>
                `;
                const lags = data.map(r => r.lag);
                
                new ApexCharts(card.querySelector(`#acf-chart-${safeId}`), {
                    ...commonOptions, chart: { ...commonOptions.chart, type: 'bar', height: 220 },
                    colors: ['#38bdf8'], series: [{ name: 'ACF', data: data.map(r => r.acf) }],
                    xaxis: { categories: lags, title: { text: 'Lags', style: { color: '#94a3b8' } } },
                    annotations: { yaxis: [{ y: 0.2, strokeDashArray: 4, borderColor: '#ef4444' }, { y: -0.2, strokeDashArray: 4, borderColor: '#ef4444' }] }
                }).render();

                new ApexCharts(card.querySelector(`#pacf-chart-${safeId}`), {
                    ...commonOptions, chart: { ...commonOptions.chart, type: 'bar', height: 220 },
                    colors: ['#a855f7'], series: [{ name: 'PACF', data: data.map(r => r.pacf) }],
                    xaxis: { categories: lags, title: { text: 'Lags', style: { color: '#94a3b8' } } },
                    annotations: { yaxis: [{ y: 0.2, strokeDashArray: 4, borderColor: '#ef4444' }, { y: -0.2, strokeDashArray: 4, borderColor: '#ef4444' }] }
                }).render();
            }
            // Caso generico per altre tabelle numeriche (CCF, Forecast, Residui, Matrix Profile)
            else if (headers.includes('date') || headers.includes('Date') || headers.includes('lag')) {
                const xCol = headers.includes('date') ? 'date' : (headers.includes('Date') ? 'Date' : 'lag');
                const xVals = data.map(r => r[xCol]);
                const yCols = headers.filter(h => h !== xCol && typeof data[0][h] === 'number');

                if (yCols.length > 0) {
                    chartArea.innerHTML = `<div id="gen-chart-${safeId}" style="height: 320px; width: 100%;"></div>`;
                    const series = yCols.map(col => ({ name: col, data: data.map(r => r[col]) }));

                    new ApexCharts(card.querySelector(`#gen-chart-${safeId}`), {
                        ...commonOptions,
                        chart: { ...commonOptions.chart, type: xCol === 'lag' ? 'bar' : 'line', height: 320 },
                        series: series,
                        xaxis: { ...commonOptions.xaxis, categories: xVals, title: { text: xCol.toUpperCase(), style: { color: '#818cf8', fontSize: '11px' } } },
                        colors: ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#38bdf8', '#ec4899', '#8b5cf6', '#14b8a6']
                    }).render();
                }
            }

            // Se abbiamo sia grafico interattivo che PNG, inseriamo il PNG sotto in un box comprimibile / secondario
            if (info.png_file) {
                imageArea.innerHTML = `
                    <details style="background: rgba(15, 23, 42, 0.5); border: 1px solid rgba(255,255,255,0.05); border-radius: 8px; padding: 0.75rem;">
                        <summary style="cursor: pointer; font-size: 0.8rem; color: #a5b4fc; font-weight: 600; outline: none;">
                            <i class="fa-solid fa-image mr-2"></i> Visualizza Grafico Originale ad Alta Risoluzione
                        </summary>
                        <div style="margin-top: 1rem; display: flex; justify-content: center; overflow: auto; max-height: 600px; padding: 0.5rem; background: #0b0f19; border-radius: 6px;">
                            <img src="../TSA/results_reorganized/${diagKey}/${info.png_file}" alt="${cleanTitle}" style="max-width: 100%; height: auto; border-radius: 4px;">
                        </div>
                    </details>
                `;
            }
        }
        // 2. Se non ci sono dati CSV (es. Mappe, Dendrogrammi, Scatter PCA), visualizziamo direttamente l'immagine PNG in modo prominente
        else if (info.png_file) {
            imageArea.innerHTML = `
                <div style="display: flex; justify-content: center; overflow: auto; max-height: 700px; padding: 1rem; background: #0b0f19; border: 1px solid rgba(255,255,255,0.05); border-radius: 8px;">
                    <img src="../TSA/results_reorganized/${diagKey}/${info.png_file}" alt="${cleanTitle}" style="max-width: 100%; height: auto; border-radius: 6px; box-shadow: 0 4px 20px rgba(0,0,0,0.5);">
                </div>
            `;
        }
    }
};
