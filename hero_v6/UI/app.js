// ISO3 to ISO2 code mapping for svgMap integration
const ISO3_TO_ISO2 = {
    "AFG": "AF", "AGO": "AO", "BDI": "BI", "BEN": "BJ", "BFA": "BF", "BGD": "BD",
    "CAF": "CF", "CIV": "CI", "CMR": "CM", "COD": "CD", "CPV": "CV", "DJI": "DJ",
    "DOM": "DO", "ECU": "EC", "ETH": "ET", "GHA": "GH", "GIN": "GN", "GMB": "GM",
    "GNB": "GW", "GTM": "GT", "HND": "HN", "HTI": "HT", "KEN": "KE", "LBN": "LB",
    "LBR": "LR", "LSO": "LS", "MDG": "MG", "MLI": "ML", "MOZ": "MZ", "MRT": "MR",
    "MWI": "MW", "NAM": "NA", "NER": "NE", "NGA": "NG", "PAK": "PK", "PSE": "PS",
    "SDN": "SD", "SEN": "SN", "SLE": "SL", "SLV": "SV", "SOM": "SO", "SSD": "SS",
    "SWZ": "SZ", "TCD": "TD", "TGO": "TG", "TLS": "TL", "TZA": "TZ", "UGA": "UG",
    "YEM": "YE", "ZAF": "ZA", "ZMB": "ZM", "ZWE": "ZW"
};

const ISO2_TO_ISO3 = {};
for (let key in ISO3_TO_ISO2) {
    ISO2_TO_ISO3[ISO3_TO_ISO2[key]] = key;
}

// Application State
let state = {
    currentView: 'global', // 'global' or 'country'
    countrySubView: 'map', // 'map', 'markets', 'charts'
    adminLevel: 'adm1',    // 'adm1' or 'adm2'
    selectedCountry: '',   // ISO3 code, e.g. 'AFG'
    heatmapTheme: 'overall', // 'overall', 'ipc', 'acled', 'idp', 'rainfall', 'wfp'
    subregion: 'national',  // 'national' or PCode
    chartType: 'linear',     // 'linear' or 'circular'
    preselectedSubregion: null, // Temp store for subregion selection from modal
    compareCountries: [],   // List of ISO3 codes for comparison
    activeMapCountry: null  // ISO3 code of the currently highlighted map country
};

// Data Cache
let globalData = null;
let countryCache = {};

// Chart References
let heatmapChart = null;
let countryCharts = {
    ipc: null,
    acled: null,
    idp: null,
    rainfall: null,
    wfp: null
};
let svgMapInstance = null;

// Initial Load
window.addEventListener("DOMContentLoaded", () => {
    initApp();
});

async function initApp() {
    // Restore sidebar state
    if (localStorage.getItem("sidebarCollapsed") === "true") {
        const aside = document.querySelector("aside");
        if (aside) aside.classList.add("collapsed");
    }
    
    try {
        console.log("Initializing HERO v6 Explorer...");
        await loadGlobalData();
        setupEventListeners();
        
        // Default View
        switchView('global');
    } catch (err) {
        console.error("Critical error during app initialization:", err);
    }
}

// Load Global Summary
async function loadGlobalData() {
    try {
        const response = await fetch('data/global_summary.json');
        globalData = await response.json();
        console.log("Global data loaded:", globalData);
        
        // Populate global UI elements
        populateGlobalStats();
        populateCountrySelector();
        populateMapCountryList();
        
        // Render Visualizations
        renderWorldMap();
        renderHeatmap();
    } catch (err) {
        console.error("Failed to load global summary dataset:", err);
        const listContainer = document.getElementById("map-countries-items");
        if (listContainer) {
            listContainer.innerHTML = `
                <div style="padding: 1rem; text-align: center; color: var(--color-danger); font-size: 0.75rem;">
                    <i class="fa-solid fa-triangle-exclamation mr-1"></i> Errore caricamento
                </div>
            `;
        }
    }
}

// Setup Navigation & Controls Events
function setupEventListeners() {
    // Close modals on overlay background click
    const periodModal = document.getElementById("period-detail-modal");
    if (periodModal) {
        periodModal.addEventListener("click", (e) => {
            if (e.target.id === "period-detail-modal") {
                closePeriodDetailModal();
            }
        });
    }
    const auditModal = document.getElementById("country-audit-modal");
    if (auditModal) {
        auditModal.addEventListener("click", (e) => {
            if (e.target.id === "country-audit-modal") {
                closeCountryAuditModal();
            }
        });
    }
}

// Switch between Global and Country views
function switchView(viewName) {
    state.currentView = viewName;
    
    // Stop timeline play if user navigates away
    stopTimelinePlay();
    
    // Safety check: remove stuck tooltips from svgMap on view changes
    document.querySelectorAll('.svgMap-tooltip').forEach(el => el.remove());
    
    // Toggle active panel class
    document.querySelectorAll('.view-panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
    
    // Toggle sidebar country sub-menu visibility
    const countrySubMenu = document.getElementById('country-sub-menu');
    if (countrySubMenu) {
        countrySubMenu.style.display = viewName === 'country' ? 'flex' : 'none';
    }
    
    if (viewName === 'global') {
        document.getElementById('panel-global').classList.add('active');
        document.getElementById('nav-global').classList.add('active');
        
        document.getElementById('view-title').innerText = "Panoramica Globale dei Dati";
        document.getElementById('view-subtitle').innerText = "Monitoraggio della completezza spazio-temporale in 52 paesi";
        
        // Show admin level, hide country selector and chart toggle
        document.getElementById('admin-level-toggle-wrapper').style.display = 'flex';
        const toggleGroupVal = document.getElementById('chart-layout-toggle-group');
        if (toggleGroupVal) toggleGroupVal.style.display = 'none';
        document.getElementById('country-selector-wrapper').style.display = 'none';
        
        // Re-render map and heatmap to handle container resized issues
        setTimeout(() => {
            if (heatmapChart) heatmapChart.windowResizeHandler();
        }, 100);
    } else if (viewName === 'country') {
        document.getElementById('panel-country').classList.add('active');
        document.getElementById('nav-country').classList.add('active');
        
        // Hide admin level, show country selector and chart toggle
        document.getElementById('admin-level-toggle-wrapper').style.display = 'none';
        const toggleGroupVal = document.getElementById('chart-layout-toggle-group');
        if (toggleGroupVal) {
            toggleGroupVal.style.display = state.countrySubView === 'charts' ? 'flex' : 'none';
        }
        document.getElementById('country-selector-wrapper').style.display = 'block';
        
        // Load default country if none selected
        if (!state.selectedCountry && globalData && globalData.countries.length > 0) {
            state.selectedCountry = globalData.countries[0].code;
            document.getElementById('country-selector').value = state.selectedCountry;
        }
        
        if (state.selectedCountry) {
            const pcode = state.preselectedSubregion;
            state.preselectedSubregion = null; // Clear
            loadCountryDetails(state.selectedCountry, pcode);
        }
    } else if (viewName === 'compare') {
        document.getElementById('panel-compare').classList.add('active');
        document.getElementById('nav-compare').classList.add('active');
        
        document.getElementById('view-title').innerText = "Confronto Multidimensionale Paesi";
        document.getElementById('view-subtitle').innerText = "Confronta l'andamento degli indicatori tra due paesi";
        
        document.getElementById('admin-level-toggle-wrapper').style.display = 'none';
        const toggleGroupVal = document.getElementById('chart-layout-toggle-group');
        if (toggleGroupVal) toggleGroupVal.style.display = 'none';
        document.getElementById('country-selector-wrapper').style.display = 'none';
        
        initCompareSelectors();
    } else if (viewName === 'heatmaps') {
        document.getElementById('panel-heatmaps').classList.add('active');
        document.getElementById('nav-heatmaps').classList.add('active');
        
        document.getElementById('view-title').innerText = "Mappa Temporale dell'Evoluzione Dati";
        document.getElementById('view-subtitle').innerText = "Visualizza l'andamento geografico reale nel tempo con animazione controllata";
        
        document.getElementById('admin-level-toggle-wrapper').style.display = 'none';
        const toggleGroupVal = document.getElementById('chart-layout-toggle-group');
        if (toggleGroupVal) toggleGroupVal.style.display = 'none';
        document.getElementById('country-selector-wrapper').style.display = 'none';
        
        initTimelineControls();
        renderTemporalMap();
    }
}

// Toggle Admin Level
function toggleAdminLevel(level) {
    if (state.adminLevel === level) return;
    
    state.adminLevel = level;
    
    // Toggle active class on buttons
    document.getElementById('btn-level-adm1').classList.toggle('active', level === 'adm1');
    document.getElementById('btn-level-adm2').classList.toggle('active', level === 'adm2');
    
    // Refresh global view visuals
    renderWorldMap();
    renderHeatmap();
    populateMapCountryList();
}

// Populate Global Dashboard stats
function populateGlobalStats() {
    if (!globalData) return;
    
    const stats = globalData.stats;
    const setSafeText = (id, text) => {
        const el = document.getElementById(id);
        if (el) el.innerText = text;
    };
    const setSafeHtml = (id, html) => {
        const el = document.getElementById(id);
        if (el) el.innerHTML = html;
    };
    
    setSafeText("stat-countries", stats.countries_count);
    setSafeText("stat-ipc-avg", stats.avg_completeness_ipc.toFixed(1) + "%");
    setSafeText("stat-acled-avg", stats.avg_completeness_acled.toFixed(1) + "%");
    setSafeText("stat-wfp-avg", stats.avg_completeness_wfp.toFixed(1) + "%");
    
    // Customize trend visual clues
    setSafeHtml("stat-acled-trend", `<i class="fa-solid fa-circle-info"></i> Eventi totali: ${stats.total_rows_adm1.toLocaleString()} ADM1 rows`);
    setSafeHtml("stat-wfp-trend", `<i class="fa-solid fa-circle-info"></i> Prezzi alimentari disponibili`);
}

// Populate Country Selector dropdown
function populateCountrySelector() {
    if (!globalData) return;
    
    const selector = document.getElementById("country-selector");
    // Clear and keep default option
    selector.innerHTML = '<option value="">Seleziona Paese...</option>';
    
    globalData.countries.forEach(c => {
        const opt = document.createElement("option");
        const flag = getFlagEmoji(ISO3_TO_ISO2[c.code]);
        opt.value = c.code;
        opt.innerText = `${flag} ${c.name} (${c.code})`;
        selector.appendChild(opt);
    });
}

// Render Rankings list sidebar
function renderRankingsList(countries) {
    const container = document.getElementById("rankings-scroll-container");
    if (!container) return;
    container.innerHTML = "";
    
    if (countries.length === 0) {
        container.innerHTML = `<div style="padding: 2rem; text-align: center; color: var(--text-muted);">Nessun paese trovato</div>`;
        return;
    }
    
    countries.forEach(c => {
        const score = state.adminLevel === 'adm1' ? c.score_adm1 : c.score_adm2;
        const item = document.createElement("div");
        item.className = `country-list-item ${state.selectedCountry === c.code ? 'selected' : ''}`;
        item.id = `rank-item-${c.code}`;
        item.onclick = () => {
            // Highlight item
            document.querySelectorAll('.country-list-item').forEach(el => el.classList.remove('selected'));
            item.classList.add('selected');
            
            // Switch view
            state.selectedCountry = c.code;
            document.getElementById('country-selector').value = c.code;
            switchView('country');
        };
        
        item.innerHTML = `
            <div class="country-item-info">
                <span class="country-item-name">${c.name}</span>
                <span class="country-item-code">${c.code} • ${state.adminLevel.toUpperCase()}</span>
            </div>
            <span class="country-item-badge">${score.toFixed(0)}%</span>
        `;
        
        container.appendChild(item);
    });
}

// Search countries filter
function onSearchCountries(query = "") {
    if (!globalData) return;
    const cleanQuery = query.toLowerCase().trim();
    const filtered = globalData.countries.filter(c => 
        c.name.toLowerCase().includes(cleanQuery) || 
        c.code.toLowerCase().includes(cleanQuery)
    );
    renderRankingsList(filtered);
}

// World Map Rendering using svgMap library
function renderWorldMap() {
    if (!globalData) return;
    
    // Prepare data values for svgMap (requires ISO-2 code keys)
    const mapValues = {};
    const heatmapData = globalData.heatmaps[state.adminLevel][state.heatmapTheme];
    
    // Loop through countries, calculate average completeness across time periods
    heatmapData.y_codes.forEach((iso3, idx) => {
        const zRow = heatmapData.z[idx];
        // Average non-null values in the quarter timeline
        const validValues = zRow.filter(val => val !== null);
        const avg = validValues.length > 0 ? (validValues.reduce((a, b) => a + b, 0) / validValues.length) : 0;
        
        const iso2 = ISO3_TO_ISO2[iso3];
        if (iso2) {
            mapValues[iso2] = {
                completeness: parseFloat(avg.toFixed(1))
            };
        }
    });

    const container = document.getElementById("world-map");
    if (!container) return;

    // Check if svgMapInstance is already initialized
    if (svgMapInstance) {
        // Reset all values first to handle missing data countries
        for (let iso2 in svgMapInstance.options.data.values) {
            svgMapInstance.options.data.values[iso2] = undefined;
        }
        
        // Reset all path fills
        const paths = container.querySelectorAll('.svgMap-country');
        paths.forEach(path => {
            path.style.fill = '#090d16';
        });
        
        // Update values and colors
        for (let iso2 in mapValues) {
            const val = mapValues[iso2].completeness;
            const path = container.querySelector(`.svgMap-country-${iso2}`) || container.querySelector(`.svgMap-country[data-id="${iso2}"]`);
            svgMapInstance.options.data.values[iso2] = {
                completeness: val
            };
            const factor = val / 100;
            const color = interpolateColor('#1e293b', '#4f46e5', factor);
            if (path) {
                path.style.fill = color;
            }
        }
        if (state.activeMapCountry) {
            highlightCountryOnMap(state.activeMapCountry);
        }
        return; // Completed in-place update!
    }
    
    // Initialize svgMap
    svgMapInstance = new svgMap({
        targetElementID: 'world-map',
        showTooltips: false, // disable built-in tooltips
        data: {
            data: {
                completeness: {
                    name: 'Disponibilità media',
                    format: '{0}%',
                    thresholdMax: 100,
                    thresholdMin: 0
                }
            },
            applyData: 'completeness',
            values: mapValues
        },
        colorMin: '#1e293b', // slate
        colorMax: '#4f46e5', // indigo
        colorNoData: '#090d16',
        onCountryClick: function(countryID) {
            const iso3 = ISO2_TO_ISO3[countryID.toUpperCase()];
            if (iso3 && globalData.countries.some(c => c.code === iso3)) {
                highlightCountryOnMap(iso3);
                openCountryAuditModal(iso3);
            }
        }
    });
    
    // Bind custom tooltips with event delegation
    initCustomMapTooltips('world-map', getWorldMapTooltipContent);
}

// Render Heatmap Matrix using ApexCharts
function renderHeatmap() {
    if (!globalData) return;
    
    const container = document.getElementById("heatmap-chart-container");
    container.innerHTML = "";
    
    const heatmapData = globalData.heatmaps[state.adminLevel][state.heatmapTheme];
    
    // Prepare series for ApexCharts Heatmap
    // Format: series = [{ name: countryName, data: [{ x: quarter, y: val }, ...] }]
    const series = heatmapData.y.map((countryName, idx) => {
        const iso3 = heatmapData.y_codes[idx];
        const zRow = heatmapData.z[idx];
        
        const dataPoints = heatmapData.x.map((quarter, qIdx) => {
            const val = zRow[qIdx];
            return {
                x: quarter,
                y: val !== null ? Math.round(val) : null
            };
        });
        
        return {
            name: `${countryName} (${iso3})`,
            data: dataPoints
        };
    });
    
    const options = {
        series: series,
        chart: {
            height: 950,
            type: 'heatmap',
            toolbar: {
                show: true
            },
            animations: {
                enabled: false // Disable to handle large matrix renders instantly
            },
            background: 'transparent',
            events: {
                dataPointSelection: function(event, chartContext, config) {
                    const seriesIndex = config.seriesIndex;
                    if (seriesIndex !== undefined && seriesIndex >= 0) {
                        const series = chartContext.w.config.series[seriesIndex];
                        if (series) {
                            const match = series.name.match(/\(([A-Z]{3})\)/);
                            if (match) {
                                openCountryAuditModal(match[1]);
                            }
                        }
                    }
                }
            }
        },
        stroke: {
            width: 0
        },
        dataLabels: {
            enabled: false
        },
        colors: ["#6366f1"], // Base color indigo, gradient determined by value
        plotOptions: {
            heatmap: {
                radius: 0, // Flat rectangle cells for clean matrix look
                enableShades: true,
                shadeIntensity: 0.6,
                colorScale: {
                    ranges: [
                        { from: 0, to: 0, name: 'Assente', color: '#1a1f2c' },
                        { from: 1, to: 30, name: 'Basso (<30%)', color: '#312e81' },
                        { from: 31, to: 70, name: 'Medio (30-70%)', color: '#4338ca' },
                        { from: 71, to: 99, name: 'Alto (70-99%)', color: '#4f46e5' },
                        { from: 100, to: 100, name: 'Completo (100%)', color: '#10b981' }
                    ]
                }
            }
        },
        theme: {
            mode: 'dark'
        },
        legend: {
            onItemClick: {
                toggleDataSeries: false
            },
            onItemHover: {
                highlightDataSeries: false
            }
        },
        xaxis: {
            type: 'category',
            labels: {
                rotate: -90,
                rotateAlways: true,
                style: {
                    fontSize: '8px',
                    fontFamily: 'Inter'
                }
            }
        },
        yaxis: {
            labels: {
                style: {
                    fontSize: '9px',
                    fontFamily: 'Inter'
                }
            }
        },
        tooltip: {
            custom: function({ series, seriesIndex, dataPointIndex, w }) {
                const country = w.config.series[seriesIndex].name;
                const quarter = w.globals.labels[dataPointIndex];
                const value = w.config.series[seriesIndex].data[dataPointIndex].y;
                
                const valStr = value !== null ? `${value}%` : 'Dato Non Rilevato';
                const statusColor = value === null ? '#ef4444' : (value === 100 ? '#10b981' : '#6366f1');
                
                return `
                    <div style="padding: 10px; background: #0f172a; border-radius: 8px;">
                        <div style="font-weight: 700; font-family: Outfit; font-size: 0.85rem; margin-bottom: 4px; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 4px;">
                            ${country}
                        </div>
                        <div style="font-size: 0.75rem; color: var(--text-secondary); margin-bottom: 2px;">
                            Periodo: <span style="font-weight: 600; color: white;">${quarter}</span>
                        </div>
                        <div style="font-size: 0.75rem; color: var(--text-secondary);">
                            Disponibilità: <span style="font-weight: 700; color: ${statusColor};">${valStr}</span>
                        </div>
                    </div>
                `;
            }
        }
    };
    
    if (heatmapChart) {
        heatmapChart.destroy();
    }
    heatmapChart = new ApexCharts(container, options);
    heatmapChart.render();
}

// Handle Heatmap theme switch
function onHeatmapThemeChange() {
    state.heatmapTheme = document.getElementById("heatmap-theme-selector").value;
    
    // Update map indicator badge text
    const labels = {
        "overall": "Tutti i Temi",
        "ipc": "Sicurezza Alimentare (IPC)",
        "acled": "Conflitti (ACLED)",
        "idp": "Sfollati (IDP)",
        "rainfall": "Precipitazioni (CHIRPS)",
        "wfp": "Prezzi Alimentari (WFP)"
    };
    document.getElementById("map-indicator-badge").innerText = labels[state.heatmapTheme];
    
    renderWorldMap();
    renderHeatmap();
}

// Selector change callback in main header (country view only)
function onCountrySelectorChange() {
    const val = document.getElementById("country-selector").value;
    if (val) {
        state.selectedCountry = val;
        loadCountryDetails(val);
    }
}

// Fetch country details from cache/JSON file
async function loadCountryDetails(code, pcodeToSelect = null) {
    if (!code) return;
    
    // Set title and loader
    document.getElementById('view-title').innerText = `Dati Paese: ${code}`;
    document.getElementById('view-subtitle').innerText = "Caricamento delle serie storiche in corso...";
    
    // Clear subregion selector options
    const subSel = document.getElementById("subregion-selector");
    subSel.innerHTML = '<option value="national">Nazionale (Tutte le Aree)</option>';
    
    try {
        let data = countryCache[code];
        if (!data) {
            const res = await fetch(`data/countries/${code}.json`);
            data = await res.json();
            countryCache[code] = data; // Cache it
        }
        
        console.log(`Loaded country details for ${code}:`, data);
        
        // Reset subregion state
        if (pcodeToSelect) {
            state.subregion = `adm1_${pcodeToSelect}`;
        } else {
            state.subregion = 'national';
        }
        
        // Update details
        const flag = getFlagEmoji(ISO3_TO_ISO2[code]);
        document.getElementById('view-title').innerText = `${flag} ${data.name} (${code})`;
        document.getElementById('view-subtitle').innerText = `Serie storiche e covariate a livello amministrativo`;
        
        // Populate selectors
        populateSubregionSelector(data);
        
        if (pcodeToSelect) {
            document.getElementById("subregion-selector").value = `adm1_${pcodeToSelect}`;
        }
        
        // Render active country details depending on selected sub-tab
        switchCountrySubView(state.countrySubView || 'map');

        // Render view
        updateCountryDashboard();
    } catch (err) {
        console.error(`Failed to load details for country ${code}:`, err);
        document.getElementById('view-subtitle').innerText = "Errore nel caricamento del dettaglio paese.";
    }
}

// Populate Subregion Selector dropdown
function populateSubregionSelector(data) {
    const selector = document.getElementById("subregion-selector");
    
    // Add Admin 1 division header
    if (data.adm1_units && data.adm1_units.length > 0) {
        const grp1 = document.createElement("optgroup");
        grp1.label = "Livello 1 (Province)";
        data.adm1_units.forEach(unit => {
            const opt = document.createElement("option");
            opt.value = `adm1_${unit.pcode}`;
            opt.innerText = unit.name;
            grp1.appendChild(opt);
        });
        selector.appendChild(grp1);
    }
    
    // Add Admin 2 division header
    if (data.adm2_units && data.adm2_units.length > 0) {
        const grp2 = document.createElement("optgroup");
        grp2.label = "Livello 2 (Distretti)";
        data.adm2_units.forEach(unit => {
            const opt = document.createElement("option");
            opt.value = `adm2_${unit.pcode}`;
            opt.innerText = `${unit.name} (${unit.pcode})`;
            grp2.appendChild(opt);
        });
        selector.appendChild(grp2);
    }
}

function onSubregionSelectorChange() {
    state.subregion = document.getElementById("subregion-selector").value;
    updateCountryDashboard();
}

// Render active country details based on selectors
function updateCountryDashboard() {
    const code = state.selectedCountry;
    const data = countryCache[code];
    if (!data) return;
    
    // Determine active trend list
    let activeTrends = [];
    let isAdm2Level = false;
    
    if (state.subregion === 'national') {
        if (data.trends.adm1 && data.trends.adm1.length > 0) {
            activeTrends = data.trends.adm1;
            isAdm2Level = false;
        } else {
            activeTrends = data.trends.adm2;
            isAdm2Level = true;
        }
    } else {
        const parts = state.subregion.split('_');
        const level = parts[0]; // 'adm1' or 'adm2'
        const pcode = parts[1];
        activeTrends = data.regions[level][pcode] || [];
        isAdm2Level = (level === 'adm2');
    }
    
    // Use full series trends for country charts
    const filteredTrends = activeTrends;
    
    // Update KPI cards (always shows latest or selected period averages)
    // updateKpiCards(filteredTrends); // Removed KPI cards grid
    
    // Update Quality Badges
    updateQualityBadges(data, filteredTrends, isAdm2Level);
    
    // Switch between Linear and Circular (Radar) visualisations
    const linearCont = document.getElementById('country-linear-container');
    const seasonalCont = document.getElementById('country-seasonal-container');
    
    if (state.chartType === 'linear') {
        if (linearCont) linearCont.style.display = 'block';
        if (seasonalCont) seasonalCont.style.display = 'none';
        
        // Restore standard titles
        document.getElementById("chart-ipc-title").innerText = "Evoluzione Classificazione Fasi IPC (Popolazione %)";
        document.getElementById("chart-acled-title").innerText = "Frequenza ed Intensità dei Conflitti (ACLED)";
        document.getElementById("chart-idp-title").innerText = "Popolazione Sfollata Interna (IDP)";
        document.getElementById("chart-rainfall-title").innerText = "Andamento Precipitazioni e Anomalia CHIRPS";
        document.getElementById("chart-wfp-title").innerText = "Indice Prezzi Alimentari e Inflazione Locale (WFP)";
        
        // Render Cartesian charts
        renderIpcChart(filteredTrends);
        renderAcledChart(filteredTrends);
        renderIdpChart(filteredTrends);
        renderRainfallChart(filteredTrends);
        renderWfpChart(filteredTrends);
        
        // Populate the details sidebar with the latest period initially
        if (filteredTrends.length > 0) {
            updateHoverDetailPanel(filteredTrends, filteredTrends.length - 1);
        } else {
            resetDetailSidebar();
        }
    } else {
        if (linearCont) linearCont.style.display = 'none';
        if (seasonalCont) seasonalCont.style.display = 'block';
        
        // Render Radar charts
        renderRadarCharts(filteredTrends);
    }
    
    // Populate raw historical data table
    populateCountryTabTable(filteredTrends);
}

// Toggle chart type (linear vs circular radar)
function toggleChartType(type) {
    if (state.chartType === type) return;
    state.chartType = type;
    
    document.getElementById('btn-chart-linear').classList.toggle('active', type === 'linear');
    document.getElementById('btn-chart-circular').classList.toggle('active', type === 'circular');
    
    updateCountryDashboard();
}

// Format numbers nicely
function formatNumber(num) {
    if (num === null || num === undefined) return "N/A";
    if (num >= 1000000) return (num / 1000000).toFixed(1) + "M";
    if (num >= 1000) return (num / 1000).toFixed(1) + "k";
    return num.toLocaleString();
}

// Update KPI cards values
function updateKpiCards(trends) {
    if (!trends || trends.length === 0) {
        document.getElementById("kpi-country-ipc").innerText = "N/A";
        document.getElementById("kpi-country-acled").innerText = "N/A";
        document.getElementById("kpi-country-idp").innerText = "N/A";
        document.getElementById("kpi-country-rain").innerText = "N/A mm";
        return;
    }
    
    const latest = trends[trends.length - 1];
    const prev = trends.length > 1 ? trends[trends.length - 2] : null;
    
    // 1. IPC Phase 3+ percentage
    const ipcVal = latest.phase_3plus_percentage;
    if (ipcVal !== undefined && ipcVal !== null) {
        document.getElementById("kpi-country-ipc").innerText = ipcVal.toFixed(1) + "%";
        if (prev && prev.phase_3plus_percentage !== null) {
            const diff = ipcVal - prev.phase_3plus_percentage;
            setTrendLabel("kpi-country-ipc-trend", diff, "%");
        } else {
            setTrendLabelNeutral("kpi-country-ipc-trend");
        }
    } else {
        document.getElementById("kpi-country-ipc").innerText = "N/A";
        setTrendLabelNeutral("kpi-country-ipc-trend");
    }
    
    // 2. ACLED Conflicts
    const acledVal = latest.acled_total_events;
    if (acledVal !== undefined && acledVal !== null) {
        document.getElementById("kpi-country-acled").innerText = formatNumber(acledVal);
        if (prev && prev.acled_total_events !== null) {
            const diff = acledVal - prev.acled_total_events;
            setTrendLabel("kpi-country-acled-trend", diff, "");
        } else {
            setTrendLabelNeutral("kpi-country-acled-trend");
        }
    } else {
        document.getElementById("kpi-country-acled").innerText = "N/A";
        setTrendLabelNeutral("kpi-country-acled-trend");
    }
    
    // 3. IDP Population
    const idpVal = latest.idp_population;
    if (idpVal !== undefined && idpVal !== null) {
        document.getElementById("kpi-country-idp").innerText = formatNumber(idpVal);
        if (prev && prev.idp_population !== null) {
            const diff = idpVal - prev.idp_population;
            setTrendLabel("kpi-country-idp-trend", diff, "");
        } else {
            setTrendLabelNeutral("kpi-country-idp-trend");
        }
    } else {
        document.getElementById("kpi-country-idp").innerText = "N/A";
        setTrendLabelNeutral("kpi-country-idp-trend");
    }
    
    // 4. Rainfall
    const rainVal = latest.rain_1m;
    const rainAnomVal = latest.rain_anomaly_1m;
    if (rainVal !== undefined && rainVal !== null) {
        document.getElementById("kpi-country-rain").innerText = Math.round(rainVal) + " mm";
        if (rainAnomVal !== undefined && rainAnomVal !== null) {
            const sign = rainAnomVal >= 0 ? "+" : "";
            const colorClass = rainAnomVal >= 0 ? "trend-up" : "trend-down";
            document.getElementById("kpi-country-rain-trend").className = `kpi-trend ${colorClass}`;
            document.getElementById("kpi-country-rain-trend").innerHTML = `<i class="fa-solid fa-droplet"></i> Anomalia: ${sign}${rainAnomVal.toFixed(0)}%`;
        } else {
            setTrendLabelNeutral("kpi-country-rain-trend");
        }
    } else {
        document.getElementById("kpi-country-rain").innerText = "N/A";
        setTrendLabelNeutral("kpi-country-rain-trend");
    }
}

function setTrendLabel(elementId, diff, unit) {
    const el = document.getElementById(elementId);
    const sign = diff >= 0 ? "+" : "";
    const arrow = diff >= 0 ? "▲" : "▼";
    let colorClass = diff >= 0 ? "trend-down" : "trend-up";
    
    if (elementId === "kpi-country-ipc-trend" || elementId === "kpi-country-acled-trend" || elementId === "kpi-country-idp-trend") {
        colorClass = diff > 0 ? "trend-down" : "trend-up"; // increase of severity or conflict is negative (red)
    }
    
    el.className = `kpi-trend ${colorClass}`;
    el.innerHTML = `${arrow} ${sign}${diff.toFixed(1)}${unit}`;
}

function setTrendLabelNeutral(elementId) {
    const el = document.getElementById(elementId);
    el.className = "kpi-trend trend-neutral";
    el.innerHTML = `<i class="fa-solid fa-minus"></i> Stabile`;
}

// Update Quality badges and metadata cards
function updateQualityBadges(data, trends, isAdm2Level) {
    const badgeContainer = document.getElementById("country-active-badges");
    badgeContainer.innerHTML = "";
    
    const lvlBadge = document.createElement("span");
    lvlBadge.className = "badge badge-blue";
    lvlBadge.innerText = isAdm2Level ? "Risoluzione: Admin 2" : "Risoluzione: Admin 1";
    badgeContainer.appendChild(lvlBadge);
    
    const setMetaText = (id, txt) => {
        const el = document.getElementById(id);
        if (el) el.innerText = txt;
    };
    
    if (!trends || trends.length === 0) {
        setMetaText("meta-idp-staleness", "N/A");
        setMetaText("meta-wfp-mapping", "N/A");
        setMetaText("meta-records-count", "N/A");
        return;
    }
    
    const latest = trends[trends.length - 1];
    
    const staleness = latest.idp_staleness_days;
    if (staleness !== undefined && staleness !== null) {
        setMetaText("meta-idp-staleness", Math.round(staleness) + " giorni");
        const staleBadge = document.createElement("span");
        if (staleness < 60) {
            staleBadge.className = "badge badge-green";
            staleBadge.innerText = "IDP: Recenti";
        } else if (staleness < 180) {
            staleBadge.className = "badge badge-yellow";
            staleBadge.innerText = "IDP: Moderati";
        } else {
            staleBadge.className = "badge badge-red";
            staleBadge.innerText = "IDP: Stantii";
        }
        badgeContainer.appendChild(staleBadge);
    } else {
        setMetaText("meta-idp-staleness", "N/A");
    }
    
    const wfpMap = latest.wfp_mapping_method;
    if (wfpMap) {
        setMetaText("meta-wfp-mapping", wfpMap);
        const wfpBadge = document.createElement("span");
        if (wfpMap.includes("strict")) {
            wfpBadge.className = "badge badge-green";
            wfpBadge.innerText = "WFP: Strict mapping";
        } else {
            wfpBadge.className = "badge badge-yellow";
            wfpBadge.innerText = "WFP: Elastic buffer";
        }
        badgeContainer.appendChild(wfpBadge);
    } else {
        setMetaText("meta-wfp-mapping", "N/A");
    }
    
    const rows = latest.rows_count;
    if (rows !== undefined) {
        setMetaText("meta-records-count", rows.toLocaleString() + " aree");
    } else {
        setMetaText("meta-records-count", "Non Rilevato");
    }
}

// Reset details sidebar content (no longer used since we show details in modal on click)
function resetDetailSidebar() {
    // Empty
}

// Helper to determine the quarter index (0-3) from a date string (YYYY-MM-DD)
function getQuarterFromDate(dateStr) {
    if (!dateStr) return 0;
    const parts = dateStr.split('-');
    if (parts.length < 2) return 0;
    const month = parseInt(parts[1], 10);
    if (month >= 1 && month <= 3) return 0;  // Q1
    if (month >= 4 && month <= 6) return 1;  // Q2
    if (month >= 7 && month <= 9) return 2;  // Q3
    return 3;                                // Q4
}

// Update sidebar panel on hover (no longer used since we show details in modal on click)
function updateHoverDetailPanel(trends, index) {
    // Empty
}

// Open modal showing comprehensive metrics for a specific period (triggered by clicking chart nodes)
function openPeriodDetailModal(trends, index) {
    if (!trends || index < 0 || index >= trends.length) return;
    const data = trends[index];
    
    // Get current country name
    const selector = document.getElementById("country-selector");
    const countryName = selector && selector.selectedIndex >= 0 ? selector.options[selector.selectedIndex].text : "Paese Selezionato";
    const code = selector ? selector.value : "";
    const flag = code ? getFlagEmoji(ISO3_TO_ISO2[code]) : "";
    
    const p1 = data.phase_1_percentage !== undefined && data.phase_1_percentage !== null ? data.phase_1_percentage : 0;
    const p2 = data.phase_2_percentage !== undefined && data.phase_2_percentage !== null ? data.phase_2_percentage : 0;
    const p3 = data.phase_3_percentage !== undefined && data.phase_3_percentage !== null ? data.phase_3_percentage : 0;
    const p4 = data.phase_4_percentage !== undefined && data.phase_4_percentage !== null ? data.phase_4_percentage : 0;
    const p5 = data.phase_5_percentage !== undefined && data.phase_5_percentage !== null ? data.phase_5_percentage : 0;
    const p3plus = data.phase_3plus_percentage !== undefined && data.phase_3plus_percentage !== null ? data.phase_3plus_percentage : (p3 + p4 + p5);
    
    const acledEvents = data.acled_total_events !== undefined && data.acled_total_events !== null ? data.acled_total_events : "N/A";
    const acledFatalities = data.acled_total_fatalities !== undefined && data.acled_total_fatalities !== null ? data.acled_total_fatalities : "N/A";
    
    // ACLED Event Types and Fatalities Breakdown
    const acledPolEvents = data.acled_political_violence_events !== undefined && data.acled_political_violence_events !== null ? data.acled_political_violence_events : 0;
    const acledDemoEvents = data.acled_demonstration_events !== undefined && data.acled_demonstration_events !== null ? data.acled_demonstration_events : 0;
    const acledCivEvents = data.acled_civilian_targeting_events !== undefined && data.acled_civilian_targeting_events !== null ? data.acled_civilian_targeting_events : 0;
    
    const acledPolFatal = data.acled_civilian_targeting_fatalities !== undefined && data.acled_civilian_targeting_fatalities !== null ? data.acled_civilian_targeting_fatalities : 0;
    const acledDemoFatal = data.acled_demonstration_fatalities !== undefined && data.acled_demonstration_fatalities !== null ? data.acled_demonstration_fatalities : 0;
    const acledCivFatal = data.acled_political_violence_fatalities !== undefined && data.acled_political_violence_fatalities !== null ? data.acled_political_violence_fatalities : 0;
    
    const idpVal = data.idp_population !== undefined && data.idp_population !== null ? formatNumber(data.idp_population) : "N/A";
    const idpStale = data.idp_staleness_days !== undefined && data.idp_staleness_days !== null ? Math.round(data.idp_staleness_days) + " gg" : "N/A";
    const idpAssType = data.idp_assessment_type || "N/A";
    const idpRepRound = data.idp_reporting_round || "N/A";
    
    const rainVal = data.rain_1m !== undefined && data.rain_1m !== null ? Math.round(data.rain_1m) + " mm" : "N/A";
    const rainAnom = data.rain_anomaly_1m !== undefined && data.rain_anomaly_1m !== null ? (data.rain_anomaly_1m >= 0 ? "+" : "") + Math.round(data.rain_anomaly_1m) + "%" : "N/A";
    const rain3m = data.rain_3m !== undefined && data.rain_3m !== null ? Math.round(data.rain_3m) + " mm" : "N/A";
    const rainAnom3 = data.rain_anomaly_3m !== undefined && data.rain_anomaly_3m !== null ? (data.rain_anomaly_3m >= 0 ? "+" : "") + Math.round(data.rain_anomaly_3m) + "%" : "N/A";
    
    const wfpPrice = data.wfp_price !== undefined && data.wfp_price !== null ? data.wfp_price.toFixed(2) : "N/A";
    const wfpInf = data.wfp_inflation !== undefined && data.wfp_inflation !== null ? (data.wfp_inflation * 100).toFixed(1) + "%" : "N/A";
    const wfpMethod = data.wfp_mapping_method || "N/A";
    const wfpObs = data.wfp_obs_count !== undefined && data.wfp_obs_count !== null ? Math.round(data.wfp_obs_count) : "N/A";

    const content = `
        <div style="margin-bottom: 1.25rem; display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; border-bottom: 1px solid var(--border-color); padding-bottom: 1rem;">
            <div>
                <span style="font-size: 0.7rem; text-transform: uppercase; color: var(--text-muted); font-weight: 700;">Inizio Periodo:</span>
                <div style="font-size: 0.95rem; color: #a5b4fc; font-weight: 600; margin-top: 0.1rem;">${data.from}</div>
            </div>
            <div>
                <span style="font-size: 0.7rem; text-transform: uppercase; color: var(--text-muted); font-weight: 700;">Fine Periodo:</span>
                <div style="font-size: 0.95rem; color: #a5b4fc; font-weight: 600; margin-top: 0.1rem;">${data.to}</div>
            </div>
        </div>

        <div style="display: grid; grid-template-columns: 1fr; gap: 1.25rem;">
            <!-- IPC SECTION -->
            <div class="detail-section" style="background: rgba(255,255,255,0.02); border: 1px solid var(--border-color); padding: 1rem; border-radius: 8px;">
                <div class="detail-section-title" style="color: #34d399; font-weight: 700; margin-bottom: 0.75rem; display: flex; align-items: center; gap: 0.5rem; font-size: 0.9rem;">
                    <i class="fa-solid fa-wheat-awn"></i> Sicurezza Alimentare (Classificazione Fasi IPC)
                </div>
                
                <div style="display: flex; flex-direction: column; gap: 0.6rem;">
                    <div class="ipc-progress-row">
                        <div class="ipc-progress-info" style="display: flex; justify-content: space-between; font-size: 0.8rem; margin-bottom: 0.2rem;">
                            <span class="detail-label">Fase 1 (Sicura)</span>
                            <span class="detail-value" style="font-weight: 600;">${p1.toFixed(1)}%</span>
                        </div>
                        <div class="ipc-progress-bar" style="height: 6px; background: rgba(255,255,255,0.05); border-radius: 3px; overflow: hidden;">
                            <div class="ipc-progress-fill" style="width: ${p1}%; height: 100%; background-color: #10b981;"></div>
                        </div>
                    </div>
                    <div class="ipc-progress-row">
                        <div class="ipc-progress-info" style="display: flex; justify-content: space-between; font-size: 0.8rem; margin-bottom: 0.2rem;">
                            <span class="detail-label">Fase 2 (Stressata)</span>
                            <span class="detail-value" style="font-weight: 600;">${p2.toFixed(1)}%</span>
                        </div>
                        <div class="ipc-progress-bar" style="height: 6px; background: rgba(255,255,255,0.05); border-radius: 3px; overflow: hidden;">
                            <div class="ipc-progress-fill" style="width: ${p2}%; height: 100%; background-color: #84cc16;"></div>
                        </div>
                    </div>
                    <div class="ipc-progress-row">
                        <div class="ipc-progress-info" style="display: flex; justify-content: space-between; font-size: 0.8rem; margin-bottom: 0.2rem;">
                            <span class="detail-label">Fase 3 (Crisi)</span>
                            <span class="detail-value" style="font-weight: 600;">${p3.toFixed(1)}%</span>
                        </div>
                        <div class="ipc-progress-bar" style="height: 6px; background: rgba(255,255,255,0.05); border-radius: 3px; overflow: hidden;">
                            <div class="ipc-progress-fill" style="width: ${p3}%; height: 100%; background-color: #eab308;"></div>
                        </div>
                    </div>
                    <div class="ipc-progress-row">
                        <div class="ipc-progress-info" style="display: flex; justify-content: space-between; font-size: 0.8rem; margin-bottom: 0.2rem;">
                            <span class="detail-label">Fase 4 (Emergenza)</span>
                            <span class="detail-value" style="font-weight: 600;">${p4.toFixed(1)}%</span>
                        </div>
                        <div class="ipc-progress-bar" style="height: 6px; background: rgba(255,255,255,0.05); border-radius: 3px; overflow: hidden;">
                            <div class="ipc-progress-fill" style="width: ${p4}%; height: 100%; background-color: #f97316;"></div>
                        </div>
                    </div>
                    <div class="ipc-progress-row">
                        <div class="ipc-progress-info" style="display: flex; justify-content: space-between; font-size: 0.8rem; margin-bottom: 0.2rem;">
                            <span class="detail-label">Fase 5 (Carestia)</span>
                            <span class="detail-value" style="font-weight: 600;">${p5.toFixed(1)}%</span>
                        </div>
                        <div class="ipc-progress-bar" style="height: 6px; background: rgba(255,255,255,0.05); border-radius: 3px; overflow: hidden;">
                            <div class="ipc-progress-fill" style="width: ${p5}%; height: 100%; background-color: #ef4444;"></div>
                        </div>
                    </div>
                    <div class="detail-row" style="margin-top: 0.75rem; border-top: 1px dashed rgba(255,255,255,0.08); padding-top: 0.5rem; display: flex; justify-content: space-between; align-items: center;">
                        <span class="detail-label" style="font-weight: 700;">Totale Fase 3+ (In Sicurezza Alimentare Grave):</span>
                        <span class="detail-value" style="color: #f87171; font-weight: 800; font-size: 0.95rem;">${p3plus.toFixed(1)}%</span>
                    </div>
                </div>
            </div>

            <!-- OTHER INDICATORS GRID -->
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                <!-- ACLED CONFLICTS -->
                <div class="detail-section" style="background: rgba(255,255,255,0.02); border: 1px solid var(--border-color); padding: 0.85rem; border-radius: 8px;">
                    <div class="detail-section-title" style="color: #f87171; font-weight: 700; margin-bottom: 0.5rem; display: flex; align-items: center; gap: 0.4rem; font-size: 0.85rem;">
                        <i class="fa-solid fa-burst"></i> Conflitti (ACLED)
                    </div>
                    <div style="display: flex; flex-direction: column; gap: 0.35rem; font-size: 0.8rem;">
                        <div style="display: flex; justify-content: space-between; font-weight: 700; border-bottom: 1px dashed rgba(255,255,255,0.08); padding-bottom: 0.25rem; margin-bottom: 0.25rem;">
                            <span>Eventi totali: ${acledEvents}</span>
                            <span style="color: #ef4444;">Vittime: ${acledFatalities}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--text-secondary);">
                            <span>Violenza Politica:</span>
                            <span>${acledPolEvents} (${acledPolFatal} vit.)</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--text-secondary);">
                            <span>Manifestazioni:</span>
                            <span>${acledDemoEvents} (${acledDemoFatal} vit.)</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--text-secondary);">
                            <span>Target Civili:</span>
                            <span>${acledCivEvents} (${acledCivFatal} vit.)</span>
                        </div>
                    </div>
                </div>

                <!-- IDP POPULATION -->
                <div class="detail-section" style="background: rgba(255,255,255,0.02); border: 1px solid var(--border-color); padding: 0.85rem; border-radius: 8px;">
                    <div class="detail-section-title" style="color: #fbbf24; font-weight: 700; margin-bottom: 0.5rem; display: flex; align-items: center; gap: 0.4rem; font-size: 0.85rem;">
                        <i class="fa-solid fa-person-walking-arrow-right"></i> Sfollati (IDP)
                    </div>
                    <div style="display: flex; flex-direction: column; gap: 0.35rem; font-size: 0.8rem;">
                        <div style="display: flex; justify-content: space-between;">
                            <span class="detail-label">Popolazione IDP:</span>
                            <span class="detail-value" style="font-weight: 600;">${idpVal}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between;">
                            <span class="detail-label">Obsolescenza dati:</span>
                            <span class="detail-value" style="font-weight: 600;">${idpStale}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; font-size: 0.7rem; color: var(--text-secondary);">
                            <span>Assessment:</span>
                            <span style="text-align: right; max-width: 130px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${idpAssType}">${idpAssType}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; font-size: 0.7rem; color: var(--text-secondary);">
                            <span>Round:</span>
                            <span style="text-align: right; max-width: 130px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${idpRepRound}">${idpRepRound}</span>
                        </div>
                    </div>
                </div>

                <!-- CLIMATE / CHIRPS -->
                <div class="detail-section" style="background: rgba(255,255,255,0.02); border: 1px solid var(--border-color); padding: 0.85rem; border-radius: 8px;">
                    <div class="detail-section-title" style="color: #60a5fa; font-weight: 700; margin-bottom: 0.5rem; display: flex; align-items: center; gap: 0.4rem; font-size: 0.85rem;">
                        <i class="fa-solid fa-cloud-showers-water"></i> Precipitazioni (CHIRPS)
                    </div>
                    <div style="display: flex; flex-direction: column; gap: 0.35rem; font-size: 0.8rem;">
                        <div style="display: flex; justify-content: space-between;">
                            <span class="detail-label">Quantità (1M):</span>
                            <span class="detail-value" style="font-weight: 600;">${rainVal}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between;">
                            <span class="detail-label">Anomalia (1M):</span>
                            <span class="detail-value" style="color: ${data.rain_anomaly_1m >= 0 ? '#34d399' : '#f87171'}; font-weight: 600;">${rainAnom}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--text-secondary);">
                            <span>Rainfall (3M):</span>
                            <span>${rain3m}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--text-secondary);">
                            <span>Anomalia (3M):</span>
                            <span style="color: ${data.rain_anomaly_3m >= 0 ? '#34d399' : '#f87171'};">${rainAnom3}</span>
                        </div>
                    </div>
                </div>

                <!-- WFP PRICES -->
                <div class="detail-section" style="background: rgba(255,255,255,0.02); border: 1px solid var(--border-color); padding: 0.85rem; border-radius: 8px;">
                    <div class="detail-section-title" style="color: #818cf8; font-weight: 700; margin-bottom: 0.5rem; display: flex; align-items: center; gap: 0.4rem; font-size: 0.85rem;">
                        <i class="fa-solid fa-store"></i> Mercati (WFP)
                    </div>
                    <div style="display: flex; flex-direction: column; gap: 0.35rem; font-size: 0.8rem;">
                        <div style="display: flex; justify-content: space-between;">
                            <span class="detail-label">Indice Prezzi:</span>
                            <span class="detail-value" style="font-weight: 600;">${wfpPrice}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between;">
                            <span class="detail-label">Inflazione:</span>
                            <span class="detail-value" style="font-weight: 600;">${wfpInf}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--text-secondary);">
                            <span>Metodo:</span>
                            <span style="text-align: right; max-width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${wfpMethod}">${wfpMethod}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--text-secondary);">
                            <span>Prezzi (Obs):</span>
                            <span>${wfpObs} record</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    document.getElementById("modal-period-body").innerHTML = content;
    document.getElementById("modal-period-title").innerText = `Dettagli Periodo: ${data.period || getQuarterFromDate(data.from)}`;
    document.getElementById("modal-period-subtitle").innerText = `Statistiche dettagliate per ${flag} ${countryName}`;
    document.getElementById("period-detail-modal").style.display = "flex";
}

// Close the period detail modal
function closePeriodDetailModal() {
    const modal = document.getElementById("period-detail-modal");
    if (modal) modal.style.display = "none";
}

// ── CARTESIAN CHARTS BUILDERS (Linear) ──

// Destroy previous chart if exists
function destroyChart(chartKey) {
    if (countryCharts[chartKey]) {
        countryCharts[chartKey].destroy();
        countryCharts[chartKey] = null;
    }
}

// Render Food Security (IPC) Stacked Bar Chart
function renderIpcChart(trends) {
    destroyChart('ipc');
    const container = document.getElementById("chart-ipc");
    container.innerHTML = "";
    
    if (!trends || trends.length === 0) {
        container.innerHTML = `<div style="height: 320px; display: flex; align-items: center; justify-content: center; color: var(--text-muted);">Nessun dato IPC disponibile</div>`;
        return;
    }
    
    const categories = trends.map(t => `${t.from}`);
    const p1 = trends.map(t => t.phase_1_percentage !== null ? parseFloat(t.phase_1_percentage.toFixed(1)) : 0);
    const p2 = trends.map(t => t.phase_2_percentage !== null ? parseFloat(t.phase_2_percentage.toFixed(1)) : 0);
    const p3 = trends.map(t => t.phase_3_percentage !== null ? parseFloat(t.phase_3_percentage.toFixed(1)) : 0);
    const p4 = trends.map(t => t.phase_4_percentage !== null ? parseFloat(t.phase_4_percentage.toFixed(1)) : 0);
    const p5 = trends.map(t => t.phase_5_percentage !== null ? parseFloat(t.phase_5_percentage.toFixed(1)) : 0);
    
    const options = {
        series: [
            { name: 'Fase 1: Minima', data: p1, color: '#10b981' },
            { name: 'Fase 2: Stress', data: p2, color: '#84cc16' },
            { name: 'Fase 3: Crisi', data: p3, color: '#eab308' },
            { name: 'Fase 4: Emergenza', data: p4, color: '#f97316' },
            { name: 'Fase 5: Catastrofe', data: p5, color: '#ef4444' }
        ],
        chart: {
            type: 'bar',
            height: 320,
            stacked: true,
            stackType: '100%',
            group: 'hero-v6-country',
            id: 'chart-ipc',
            toolbar: { show: false },
            background: 'transparent',
            events: {
                dataPointSelection: function(event, chartContext, config) {
                    const dataPointIndex = config.dataPointIndex;
                    if (dataPointIndex !== undefined && dataPointIndex >= 0) {
                        openPeriodDetailModal(trends, dataPointIndex);
                    }
                }
            }
        },
        theme: { mode: 'dark' },
        plotOptions: {
            bar: {
                horizontal: false,
                columnWidth: '65%'
            }
        },
        dataLabels: {
            enabled: true,
            formatter: function(val) {
                return val > 7 ? Math.round(val) + "%" : "";
            },
            style: {
                fontSize: '8px',
                fontFamily: 'Inter',
                fontWeight: 'normal',
                colors: ['#ffffff']
            }
        },
        xaxis: {
            categories: categories,
            tickAmount: Math.min(categories.length, 10),
            crosshairs: { show: true },
            tooltip: { enabled: false },
            labels: {
                style: { fontSize: '9px', fontFamily: 'Inter' }
            }
        },
        yaxis: {
            title: { text: 'Percentuale Popolazione' }
        },
        tooltip: {
            enabled: true,
            shared: true,
            intersect: false
        },
        legend: {
            position: 'top',
            horizontalAlign: 'center',
            fontFamily: 'Inter',
            fontSize: '11px'
        }
    };
    
    countryCharts.ipc = new ApexCharts(container, options);
    countryCharts.ipc.render();
}

// Render ACLED Conflict Dual-Axis Chart
function renderAcledChart(trends) {
    destroyChart('acled');
    const container = document.getElementById("chart-acled");
    container.innerHTML = "";
    
    const hasData = trends.some(t => t.acled_total_events !== null);
    if (!trends || trends.length === 0 || !hasData) {
        container.innerHTML = `<div style="height: 320px; display: flex; align-items: center; justify-content: center; color: var(--text-muted);">Nessun dato sui conflitti (ACLED) disponibile</div>`;
        return;
    }
    
    const categories = trends.map(t => `${t.from}`);
    const events = trends.map(t => t.acled_total_events !== null ? Math.round(t.acled_total_events) : 0);
    const fatalities = trends.map(t => t.acled_total_fatalities !== null ? Math.round(t.acled_total_fatalities) : 0);
    
    const options = {
        series: [
            { name: 'Eventi Conflitto', type: 'line', data: events, color: '#f59e0b' },
            { name: 'Vittime (Fatalities)', type: 'line', data: fatalities, color: '#ef4444' }
        ],
        chart: {
            height: 320,
            type: 'line',
            group: 'hero-v6-country',
            id: 'chart-acled',
            toolbar: { show: false },
            background: 'transparent',
            events: {
                markerClick: function(event, chartContext, { seriesIndex, dataPointIndex, config }) {
                    if (dataPointIndex !== undefined && dataPointIndex >= 0) {
                        openPeriodDetailModal(trends, dataPointIndex);
                    }
                },
                dataPointSelection: function(event, chartContext, config) {
                    const dataPointIndex = config.dataPointIndex;
                    if (dataPointIndex !== undefined && dataPointIndex >= 0) {
                        openPeriodDetailModal(trends, dataPointIndex);
                    }
                }
            }
        },
        theme: { mode: 'dark' },
        stroke: {
            width: [3, 3],
            curve: 'smooth',
            connectNulls: true
        },
        markers: {
            size: 5,
            hover: {
                size: 7
            }
        },
        xaxis: {
            categories: categories,
            tickAmount: Math.min(categories.length, 10),
            crosshairs: { show: true },
            tooltip: { enabled: false },
            labels: {
                style: { fontSize: '9px' }
            }
        },
        yaxis: [
            {
                title: { text: 'Numero di Eventi', style: { color: '#f59e0b' } },
                labels: { style: { colors: '#f59e0b' } }
            },
            {
                opposite: true,
                title: { text: 'Numero di Vittime', style: { color: '#ef4444' } },
                labels: { style: { colors: '#ef4444' } }
            }
        ],
        tooltip: {
            enabled: true,
            shared: true,
            intersect: false
        },
        legend: {
            position: 'top',
            fontFamily: 'Inter'
        }
    };
    
    countryCharts.acled = new ApexCharts(container, options);
    countryCharts.acled.render();
}

// Render IDP Displacement line chart
function renderIdpChart(trends) {
    destroyChart('idp');
    const container = document.getElementById("chart-idp");
    container.innerHTML = "";
    
    const hasData = trends.some(t => t.idp_population !== null);
    if (!trends || trends.length === 0 || !hasData) {
        container.innerHTML = `<div style="height: 320px; display: flex; align-items: center; justify-content: center; color: var(--text-muted);">Nessun dato sugli sfollati (IDP) disponibile</div>`;
        return;
    }
    
    const categories = trends.map(t => `${t.from}`);
    const idpPop = trends.map(t => t.idp_population);
    
    const options = {
        series: [{
            name: 'Popolazione IDP',
            data: idpPop
        }],
        chart: {
            type: 'line',
            height: 320,
            group: 'hero-v6-country',
            id: 'chart-idp',
            toolbar: { show: false },
            background: 'transparent',
            events: {
                markerClick: function(event, chartContext, { seriesIndex, dataPointIndex, config }) {
                    if (dataPointIndex !== undefined && dataPointIndex >= 0) {
                        openPeriodDetailModal(trends, dataPointIndex);
                    }
                },
                dataPointSelection: function(event, chartContext, config) {
                    const dataPointIndex = config.dataPointIndex;
                    if (dataPointIndex !== undefined && dataPointIndex >= 0) {
                        openPeriodDetailModal(trends, dataPointIndex);
                    }
                }
            }
        },
        theme: { mode: 'dark' },
        stroke: {
            width: 3,
            curve: 'smooth',
            connectNulls: true
        },
        colors: ['#fbbf24'],
        xaxis: {
            categories: categories,
            tickAmount: Math.min(categories.length, 10),
            crosshairs: { show: true },
            tooltip: { enabled: false },
            labels: {
                style: { fontSize: '9px' }
            }
        },
        yaxis: {
            title: { text: 'Popolazione Sfollata' },
            labels: {
                formatter: function(val) {
                    return formatNumber(val);
                }
            }
        },
        markers: {
            size: 5,
            hover: {
                size: 7
            }
        },
        tooltip: {
            enabled: true,
            shared: true,
            intersect: false
        }
    };
    
    countryCharts.idp = new ApexCharts(container, options);
    countryCharts.idp.render();
}

// Render Rainfall and anomalies
function renderRainfallChart(trends) {
    destroyChart('rainfall');
    const container = document.getElementById("chart-rainfall");
    container.innerHTML = "";
    
    const hasData = trends.some(t => t.rain_1m !== null);
    if (!trends || trends.length === 0 || !hasData) {
        container.innerHTML = `<div style="height: 320px; display: flex; align-items: center; justify-content: center; color: var(--text-muted);">Nessun dato sulle precipitazioni disponibile</div>`;
        return;
    }
    
    const categories = trends.map(t => `${t.from}`);
    const rain = trends.map(t => t.rain_1m !== null ? parseFloat(t.rain_1m.toFixed(1)) : null);
    const anomaly = trends.map(t => t.rain_anomaly_1m !== null ? parseFloat(t.rain_anomaly_1m.toFixed(1)) : null);
    
    const options = {
        series: [
            { name: 'Precipitazioni (mm)', type: 'line', data: rain, color: '#3b82f6' },
            { name: 'Anomalia (mm)', type: 'line', data: anomaly, color: '#a855f7' }
        ],
        chart: {
            height: 320,
            type: 'line',
            group: 'hero-v6-country',
            id: 'chart-rainfall',
            toolbar: { show: false },
            background: 'transparent',
            events: {
                markerClick: function(event, chartContext, { seriesIndex, dataPointIndex, config }) {
                    if (dataPointIndex !== undefined && dataPointIndex >= 0) {
                        openPeriodDetailModal(trends, dataPointIndex);
                    }
                },
                dataPointSelection: function(event, chartContext, config) {
                    const dataPointIndex = config.dataPointIndex;
                    if (dataPointIndex !== undefined && dataPointIndex >= 0) {
                        openPeriodDetailModal(trends, dataPointIndex);
                    }
                }
            }
        },
        theme: { mode: 'dark' },
        stroke: {
            width: [3, 3],
            curve: 'straight',
            connectNulls: true
        },
        markers: {
            size: 5,
            hover: {
                size: 7
            }
        },
        xaxis: {
            categories: categories,
            tickAmount: Math.min(categories.length, 10),
            crosshairs: { show: true },
            tooltip: { enabled: false },
            labels: {
                style: { fontSize: '9px' }
            }
        },
        yaxis: [
            {
                title: { text: 'Pioggia (mm)', style: { color: '#3b82f6' } },
                labels: { style: { colors: '#3b82f6' } }
            },
            {
                opposite: true,
                title: { text: 'Anomalia Pioggia (mm)', style: { color: '#a855f7' } },
                labels: {
                    style: { colors: '#a855f7' }
                }
            }
        ],
        tooltip: {
            enabled: true,
            shared: true,
            intersect: false
        },
        legend: {
            position: 'top',
            fontFamily: 'Inter'
        }
    };
    
    countryCharts.rainfall = new ApexCharts(container, options);
    countryCharts.rainfall.render();
}

// Render WFP Food Prices & Inflation
function renderWfpChart(trends) {
    destroyChart('wfp');
    const container = document.getElementById("chart-wfp");
    container.innerHTML = "";
    
    const hasData = trends.some(t => t.wfp_price !== null);
    if (!trends || trends.length === 0 || !hasData) {
        container.innerHTML = `<div style="height: 320px; display: flex; align-items: center; justify-content: center; color: var(--text-muted);">Nessun dato sui prezzi di mercato (WFP) disponibile</div>`;
        return;
    }
    
    const categories = trends.map(t => `${t.from}`);
    const price = trends.map(t => t.wfp_price !== null ? parseFloat(t.wfp_price.toFixed(2)) : null);
    const inflation = trends.map(t => t.wfp_inflation !== null ? parseFloat((t.wfp_inflation * 100).toFixed(1)) : null);
    
    const options = {
        series: [
            { name: 'Indice dei Prezzi', type: 'line', data: price, color: '#818cf8' },
            { name: 'Inflazione Alimentare (%)', type: 'line', data: inflation, color: '#f97316' }
        ],
        chart: {
            height: 320,
            type: 'line',
            group: 'hero-v6-country',
            id: 'chart-wfp',
            toolbar: { show: false },
            background: 'transparent',
            events: {
                markerClick: function(event, chartContext, { seriesIndex, dataPointIndex, config }) {
                    if (dataPointIndex !== undefined && dataPointIndex >= 0) {
                        openPeriodDetailModal(trends, dataPointIndex);
                    }
                },
                dataPointSelection: function(event, chartContext, config) {
                    const dataPointIndex = config.dataPointIndex;
                    if (dataPointIndex !== undefined && dataPointIndex >= 0) {
                        openPeriodDetailModal(trends, dataPointIndex);
                    }
                }
            }
        },
        theme: { mode: 'dark' },
        stroke: {
            width: [3, 3],
            curve: 'smooth',
            connectNulls: true
        },
        markers: {
            size: 5,
            hover: {
                size: 7
            }
        },
        xaxis: {
            categories: categories,
            tickAmount: Math.min(categories.length, 10),
            crosshairs: { show: true },
            tooltip: { enabled: false },
            labels: {
                style: { fontSize: '9px' }
            }
        },
        yaxis: [
            {
                title: { text: 'Indice Prezzi', style: { color: '#818cf8' } },
                labels: { style: { colors: '#818cf8' } }
            },
            {
                opposite: true,
                title: { text: 'Inflazione Alimentare (%)', style: { color: '#f97316' } },
                labels: {
                    style: { colors: '#f97316' },
                    formatter: function(val) {
                        return val !== null ? `${val}%` : "";
                    }
                }
            }
        ],
        tooltip: {
            enabled: true,
            shared: true,
            intersect: false
        },
        legend: {
            position: 'top',
            fontFamily: 'Inter'
        }
    };
    
    countryCharts.wfp = new ApexCharts(container, options);
    countryCharts.wfp.render();
}

// ── CIRCULAR/RADAR CHARTS BUILDER (Seasonal Analysis) ──

// Synchronized hover highlights for seasonal radar charts
function highlightMarkerInAllSeasonalCharts(qIndex) {
    const chartIds = [
        'chart-ipc-seasonal', 'chart-acled-events-seasonal', 'chart-acled-fatalities-seasonal', 
        'chart-idp-seasonal', 'chart-rainfall-rain-seasonal', 'chart-rainfall-anomaly-seasonal', 
        'chart-wfp-price-seasonal', 'chart-wfp-inflation-seasonal'
    ];
    chartIds.forEach(id => {
        const container = document.getElementById(id);
        if (!container) return;
        
        const markers = container.querySelectorAll('.apexcharts-marker');
        markers.forEach(marker => {
            const relVal = marker.getAttribute('rel');
            if (relVal === null) return;
            const markerQ = parseInt(relVal, 10);
            
            if (markerQ === qIndex) {
                // Glow marker
                marker.setAttribute('r', '7');
                marker.style.stroke = '#ffffff';
                marker.style.strokeWidth = '2px';
            } else {
                // Reset
                marker.setAttribute('r', '4');
                marker.style.stroke = '';
                marker.style.strokeWidth = '';
            }
        });
    });
}

function clearHighlightInAllSeasonalCharts() {
    const chartIds = [
        'chart-ipc-seasonal', 'chart-acled-events-seasonal', 'chart-acled-fatalities-seasonal', 
        'chart-idp-seasonal', 'chart-rainfall-rain-seasonal', 'chart-rainfall-anomaly-seasonal', 
        'chart-wfp-price-seasonal', 'chart-wfp-inflation-seasonal'
    ];
    chartIds.forEach(id => {
        const container = document.getElementById(id);
        if (!container) return;
        
        const markers = container.querySelectorAll('.apexcharts-marker');
        markers.forEach(marker => {
            marker.setAttribute('r', '4');
            marker.style.stroke = '';
            marker.style.strokeWidth = '';
        });
    });
}

// Calculate and render seasonal diagrams using synchronized radar (quadrilateral) charts with gradients
function renderRadarCharts(trends) {
    if (!trends || trends.length === 0) {
        const keys = [
            'ipc-seasonal', 'acled-events-seasonal', 'acled-fatalities-seasonal', 
            'idp-seasonal', 'rainfall-rain-seasonal', 'rainfall-anomaly-seasonal', 
            'wfp-price-seasonal', 'wfp-inflation-seasonal'
        ];
        keys.forEach(k => {
            const el = document.getElementById(`chart-${k}`);
            if (el) el.innerHTML = `<div style="height: 320px; display: flex; align-items: center; justify-content: center; color: var(--text-muted);">Nessun dato disponibile</div>`;
        });
        return;
    }

    // Group trends by year and quarter
    const seasonalByYear = {};
    
    trends.forEach(t => {
        if (!t.from) return;
        const year = t.from.split('-')[0];
        const qIndex = getQuarterFromDate(t.from);
        
        if (!seasonalByYear[year]) {
            seasonalByYear[year] = { 0: [], 1: [], 2: [], 3: [] };
        }
        seasonalByYear[year][qIndex].push(t);
    });
    
    const years = Object.keys(seasonalByYear).sort();
    const categories = ['Q1 (Gen-Mar)', 'Q2 (Apr-Giu)', 'Q3 (Lug-Set)', 'Q4 (Ott-Dic)'];
    
    function getAvg(arr, key) {
        const vals = arr.map(x => x[key]).filter(v => v !== null && v !== undefined);
        if (vals.length === 0) return null;
        return vals.reduce((a, b) => a + b, 0) / vals.length;
    }
    
    function buildSeries(metricGetter) {
        return years.map(year => {
            const data = [0, 1, 2, 3].map(q => {
                const qArr = seasonalByYear[year][q];
                if (!qArr || qArr.length === 0) return null;
                return metricGetter(qArr);
            });
            return {
                name: year,
                data: data.map(val => val !== null && !isNaN(val) ? parseFloat(val.toFixed(2)) : null)
            };
        });
    }

    const seasonalCommonOptions = {
        stroke: {
            width: 2
        },
        fill: {
            type: 'gradient',
            gradient: {
                shade: 'dark',
                type: 'diagonal1',
                shadeIntensity: 0.5,
                inverseColors: false,
                opacityFrom: 0.45,
                opacityTo: 0.05,
                stops: [0, 100]
            }
        },
        markers: {
            size: 4,
            hover: {
                size: 6
            }
        },
        plotOptions: {
            radar: {
                polygons: {
                    strokeColors: 'rgba(255, 255, 255, 0.08)',
                    connectorColors: 'rgba(255, 255, 255, 0.08)',
                    fill: {
                        colors: ['rgba(255, 255, 255, 0.01)', 'rgba(255, 255, 255, 0.03)']
                    }
                }
            }
        },
        xaxis: {
            categories: categories,
            labels: {
                style: {
                    colors: ['#94a3b8', '#94a3b8', '#94a3b8', '#94a3b8'],
                    fontSize: '10px',
                    fontFamily: 'Outfit',
                    fontWeight: 500
                }
            }
        },
        yaxis: {
            show: true,
            labels: {
                style: {
                    colors: '#64748b',
                    fontSize: '8px',
                    fontFamily: 'Inter'
                }
            }
        },
        theme: { mode: 'dark' },
        chart: {
            type: 'radar',
            height: 320,
            toolbar: { show: false },
            background: 'transparent',
            events: {
                markerClick: function(event, chartContext, { seriesIndex, dataPointIndex, config }) {
                    if (seriesIndex !== undefined && dataPointIndex !== undefined && seriesIndex !== -1 && dataPointIndex !== -1) {
                        const year = chartContext.w.config.series[seriesIndex].name;
                        const targetTrend = trends.find(t => t.from.startsWith(year) && getQuarterFromDate(t.from) === dataPointIndex);
                        if (targetTrend) {
                            const idx = trends.indexOf(targetTrend);
                            if (idx !== -1) {
                                openPeriodDetailModal(trends, idx);
                            }
                        }
                    }
                },
                dataPointSelection: function(event, chartContext, config) {
                    const seriesIndex = config.seriesIndex;
                    const dataPointIndex = config.dataPointIndex;
                    if (seriesIndex !== undefined && dataPointIndex !== undefined && seriesIndex !== -1 && dataPointIndex !== -1) {
                        const year = chartContext.w.config.series[seriesIndex].name;
                        const targetTrend = trends.find(t => t.from.startsWith(year) && getQuarterFromDate(t.from) === dataPointIndex);
                        if (targetTrend) {
                            const idx = trends.indexOf(targetTrend);
                            if (idx !== -1) {
                                openPeriodDetailModal(trends, idx);
                            }
                        }
                    }
                },
                legendClick: function(chartContext, seriesIndex, opts) {
                    const seriesName = opts.config.series[seriesIndex].name;
                    const currentChartId = opts.config.chart.id;
                    const chartIds = [
                        'chart-ipc-seasonal', 'chart-acled-events-seasonal', 'chart-acled-fatalities-seasonal', 
                        'chart-idp-seasonal', 'chart-rainfall-rain-seasonal', 'chart-rainfall-anomaly-seasonal', 
                        'chart-wfp-price-seasonal', 'chart-wfp-inflation-seasonal'
                    ];
                    chartIds.forEach(id => {
                        if (id !== currentChartId) {
                            ApexCharts.exec(id, 'toggleSeries', seriesName);
                        }
                    });
                },
                mouseMove: function(event, chartContext, config) {
                    const qIndex = config.dataPointIndex;
                    if (qIndex !== undefined && qIndex !== -1) {
                        highlightMarkerInAllSeasonalCharts(qIndex);
                    } else {
                        clearHighlightInAllSeasonalCharts();
                    }
                },
                mouseLeave: function(event, chartContext, config) {
                    clearHighlightInAllSeasonalCharts();
                }
            }
        },
        tooltip: {
            enabled: true
        },
        legend: {
            position: 'top',
            fontFamily: 'Inter',
            fontSize: '11px'
        }
    };
    
    // 1. IPC Phase 3+
    const ipcSeries = buildSeries(qArr => {
        const val = getAvg(qArr, 'phase_3plus_percentage');
        if (val !== null) return val;
        const p3 = getAvg(qArr, 'phase_3_percentage') || 0;
        const p4 = getAvg(qArr, 'phase_4_percentage') || 0;
        const p5 = getAvg(qArr, 'phase_5_percentage') || 0;
        return (p3 + p4 + p5) > 0 ? (p3 + p4 + p5) : null;
    });
    
    // 2. ACLED Events
    const acledEventsSeries = buildSeries(qArr => getAvg(qArr, 'acled_total_events'));
    
    // 3. ACLED Fatalities
    const acledFatalitiesSeries = buildSeries(qArr => getAvg(qArr, 'acled_total_fatalities'));
    
    // 4. IDP
    const idpSeries = buildSeries(qArr => getAvg(qArr, 'idp_population'));
    
    // 5. Rain
    const rainSeries = buildSeries(qArr => getAvg(qArr, 'rain_1m'));
    
    // 6. Rain Anomaly
    const rainAnomalySeries = buildSeries(qArr => getAvg(qArr, 'rain_anomaly_1m'));
    
    // 7. WFP Price
    const wfpPriceSeries = buildSeries(qArr => getAvg(qArr, 'wfp_price'));
    
    // 8. WFP Inflation
    const wfpInflationSeries = buildSeries(qArr => {
        const val = getAvg(qArr, 'wfp_inflation');
        return val !== null ? val * 100 : null;
    });

    const chartsToRender = [
        { key: 'ipc_seasonal', containerId: 'chart-ipc-seasonal', series: ipcSeries },
        { key: 'acled_events_seasonal', containerId: 'chart-acled-events-seasonal', series: acledEventsSeries },
        { key: 'acled_fatalities_seasonal', containerId: 'chart-acled-fatalities-seasonal', series: acledFatalitiesSeries },
        { key: 'idp_seasonal', containerId: 'chart-idp-seasonal', series: idpSeries },
        { key: 'rainfall_rain_seasonal', containerId: 'chart-rainfall-rain-seasonal', series: rainSeries },
        { key: 'rainfall_anomaly_seasonal', containerId: 'chart-rainfall-anomaly-seasonal', series: rainAnomalySeries },
        { key: 'wfp_price_seasonal', containerId: 'chart-wfp-price-seasonal', series: wfpPriceSeries },
        { key: 'wfp_inflation_seasonal', containerId: 'chart-wfp-inflation-seasonal', series: wfpInflationSeries }
    ];

    chartsToRender.forEach(c => {
        destroyChart(c.key);
        const container = document.getElementById(c.containerId);
        if (container) {
            container.innerHTML = "";
            const hasData = c.series.some(s => s.data.some(d => d !== null));
            if (!hasData) {
                container.innerHTML = `<div style="height: 320px; display: flex; align-items: center; justify-content: center; color: var(--text-muted); font-size: 0.8rem;">Nessun dato disponibile</div>`;
                return;
            }
            const options = {
                ...seasonalCommonOptions,
                series: c.series,
                chart: {
                    ...seasonalCommonOptions.chart,
                    id: c.containerId
                }
            };
            countryCharts[c.key] = new ApexCharts(container, options);
            countryCharts[c.key].render();
        }
    });
}

// Update sidebar panel on seasonal radar hover (Circular/Seasonal view)
function updateHoverSeasonalPanel(seasonalAverages, qIndex) {
    if (!seasonalAverages || qIndex < 0 || qIndex >= seasonalAverages.length) return;
    if (!document.getElementById("detail-sidebar-content")) return;
    const data = seasonalAverages[qIndex];
    
    const p1 = data.phase_1_percentage || 0;
    const p2 = data.phase_2_percentage || 0;
    const p3 = data.phase_3_percentage || 0;
    const p4 = data.phase_4_percentage || 0;
    const p5 = data.phase_5_percentage || 0;
    const p3plus = data.phase_3plus_percentage || (p3 + p4 + p5);

    const acledEvents = data.acled_total_events !== null ? Math.round(data.acled_total_events) : "N/A";
    const acledFatalities = data.acled_total_fatalities !== null ? Math.round(data.acled_total_fatalities) : "N/A";
    const idpVal = data.idp_population !== null ? formatNumber(Math.round(data.idp_population)) : "N/A";
    const idpStale = data.idp_staleness_days !== null ? Math.round(data.idp_staleness_days) + " gg" : "N/A";
    const rainVal = data.rain_1m !== null ? Math.round(data.rain_1m) + " mm" : "N/A";
    const rainAnom = data.rain_anomaly_1m !== null ? (data.rain_anomaly_1m >= 0 ? "+" : "") + Math.round(data.rain_anomaly_1m) + "%" : "N/A";
    const wfpPrice = data.wfp_price !== null ? data.wfp_price.toFixed(2) : "N/A";
    const wfpInf = data.wfp_inflation !== null ? data.wfp_inflation.toFixed(1) + "%" : "N/A";
    const wfpMethod = data.wfp_mapping_method || "N/A";

    const content = `
        <div style="margin-bottom: 1.25rem;">
            <div class="detail-row">
                <span class="detail-label" style="font-weight: 700;">Periodo Stagionale:</span>
                <span class="detail-value" style="font-size: 0.9rem; color: #a5b4fc; font-weight: 800;">${data.quarter}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Tipo Aggregazione:</span>
                <span class="badge badge-yellow">Media Storica (Tutti gli anni)</span>
            </div>
        </div>

        <!-- IPC SECTION -->
        <div class="detail-section">
            <div class="detail-section-title" style="color: #34d399;">
                <i class="fa-solid fa-wheat-awn"></i> Sicurezza Alimentare (Media)
            </div>
            
            <div class="ipc-progress-row">
                <div class="ipc-progress-info">
                    <span class="detail-label">Fase 1 (Sicura)</span>
                    <span class="detail-value">${p1.toFixed(1)}%</span>
                </div>
                <div class="ipc-progress-bar">
                    <div class="ipc-progress-fill" style="width: ${p1}%; background-color: #10b981;"></div>
                </div>
            </div>
            <div class="ipc-progress-row">
                <div class="ipc-progress-info">
                    <span class="detail-label">Fase 2 (Stressata)</span>
                    <span class="detail-value">${p2.toFixed(1)}%</span>
                </div>
                <div class="ipc-progress-bar">
                    <div class="ipc-progress-fill" style="width: ${p2}%; background-color: #84cc16;"></div>
                </div>
            </div>
            <div class="ipc-progress-row">
                <div class="ipc-progress-info">
                    <span class="detail-label">Fase 3 (Crisi)</span>
                    <span class="detail-value">${p3.toFixed(1)}%</span>
                </div>
                <div class="ipc-progress-bar">
                    <div class="ipc-progress-fill" style="width: ${p3}%; background-color: #eab308;"></div>
                </div>
            </div>
            <div class="ipc-progress-row">
                <div class="ipc-progress-info">
                    <span class="detail-label">Fase 4 (Emergenza)</span>
                    <span class="detail-value">${p4.toFixed(1)}%</span>
                </div>
                <div class="ipc-progress-bar">
                    <div class="ipc-progress-fill" style="width: ${p4}%; background-color: #f97316;"></div>
                </div>
            </div>
            <div class="ipc-progress-row">
                <div class="ipc-progress-info">
                    <span class="detail-label">Fase 5 (Carestia)</span>
                    <span class="detail-value">${p5.toFixed(1)}%</span>
                </div>
                <div class="ipc-progress-bar">
                    <div class="ipc-progress-fill" style="width: ${p5}%; background-color: #ef4444;"></div>
                </div>
            </div>
            <div class="detail-row" style="margin-top: 0.75rem; border-top: 1px dashed rgba(255,255,255,0.06); padding-top: 0.5rem;">
                <span class="detail-label" style="font-weight: 700;">Media Fase 3+ :</span>
                <span class="detail-value" style="color: #f87171; font-weight: 800; font-size: 0.85rem;">${p3plus.toFixed(1)}%</span>
            </div>
        </div>

        <!-- ACLED CONFLICTS -->
        <div class="detail-section">
            <div class="detail-section-title" style="color: #f87171;">
                <i class="fa-solid fa-burst"></i> Conflitti ACLED (Media)
            </div>
            <div class="detail-row">
                <span class="detail-label">Media Eventi:</span>
                <span class="detail-value">${acledEvents}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Media Vittime:</span>
                <span class="detail-value" style="color: #ef4444;">${acledFatalities}</span>
            </div>
        </div>

        <!-- IDP POPULATION -->
        <div class="detail-section">
            <div class="detail-section-title" style="color: #fbbf24;">
                <i class="fa-solid fa-person-walking-arrow-right"></i> Sfollati IDP (Media)
            </div>
            <div class="detail-row">
                <span class="detail-label">Media IDP:</span>
                <span class="detail-value">${idpVal}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Obsolescenza dati:</span>
                <span class="detail-value">${idpStale}</span>
            </div>
        </div>

        <!-- CLIMATE / CHIRPS -->
        <div class="detail-section">
            <div class="detail-section-title" style="color: #60a5fa;">
                <i class="fa-solid fa-cloud-showers-water"></i> Clima & Piogge (Media)
            </div>
            <div class="detail-row">
                <span class="detail-label">Pioggia media:</span>
                <span class="detail-value">${rainVal}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Media Anomalia:</span>
                <span class="detail-value" style="color: ${data.rain_anomaly_1m >= 0 ? '#34d399' : '#f87171'}">${rainAnom}</span>
            </div>
        </div>

        <!-- WFP PRICES -->
        <div class="detail-section">
            <div class="detail-section-title" style="color: #818cf8;">
                <i class="fa-solid fa-store"></i> Prezzi & Inflazione (Media)
            </div>
            <div class="detail-row">
                <span class="detail-label">Media Indice:</span>
                <span class="detail-value">${wfpPrice}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Media Inflazione:</span>
                <span class="detail-value">${wfpInf}</span>
            </div>
        </div>
    `;
    
    document.getElementById("detail-sidebar-content").innerHTML = content;
}

// Populate raw historical data table in country details sub-tab
function populateCountryTabTable(trends) {
    const tbody = document.getElementById("country-tab-table-body");
    const subLabel = document.getElementById("country-table-subregion-label");
    if (!tbody) return;
    tbody.innerHTML = "";
    
    let areaName = "Nazionale (Tutte le Aree)";
    if (state.subregion !== 'national') {
        const selector = document.getElementById("subregion-selector");
        if (selector) {
            for (let i = 0; i < selector.options.length; i++) {
                const opt = selector.options[i];
                if (opt.value === state.subregion) {
                    areaName = opt.text;
                    break;
                }
            }
        }
    }
    if (subLabel) subLabel.innerText = `Area: ${areaName}`;
    
    if (!trends || trends.length === 0) {
        tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; padding: 2rem; color: var(--text-muted);">Nessun dato storico disponibile</td></tr>`;
        return;
    }
    
    const sorted = [...trends].sort((a, b) => b.from.localeCompare(a.from));
    
    sorted.forEach(t => {
        const tr = document.createElement("tr");
        
        const ipcVal = t.phase_3plus_percentage !== null && t.phase_3plus_percentage !== undefined 
            ? `${t.phase_3plus_percentage.toFixed(1)}%` 
            : (t.phase_3_percentage !== null && t.phase_3_percentage !== undefined
               ? `${(t.phase_3_percentage + (t.phase_4_percentage||0) + (t.phase_5_percentage||0)).toFixed(1)}%`
               : '-');
               
        const acledEvents = t.acled_total_events !== null && t.acled_total_events !== undefined ? Math.round(t.acled_total_events) : '-';
        const acledFatalities = t.acled_total_fatalities !== null && t.acled_total_fatalities !== undefined ? Math.round(t.acled_total_fatalities) : '-';
        const idpVal = t.idp_population !== null && t.idp_population !== undefined ? formatNumber(t.idp_population) : '-';
        const rainVal = t.rain_1m !== null && t.rain_1m !== undefined ? `${Math.round(t.rain_1m)} mm` : '-';
        const rainAnom = t.rain_anomaly_1m !== null && t.rain_anomaly_1m !== undefined ? `${t.rain_anomaly_1m >= 0 ? '+' : ''}${Math.round(t.rain_anomaly_1m)}%` : '-';
        const wfpPrice = t.wfp_price !== null && t.wfp_price !== undefined ? t.wfp_price.toFixed(2) : '-';
        const wfpInf = t.wfp_inflation !== null && t.wfp_inflation !== undefined ? `${(t.wfp_inflation * 100).toFixed(1)}%` : '-';
        
        tr.innerHTML = `
            <td style="text-align: left; font-weight: 600; color: #a5b4fc; padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05);">${t.from}</td>
            <td style="text-align: right; font-weight: 600; color: #10b981; padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05);">${ipcVal}</td>
            <td style="text-align: right; color: #f43f5e; padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05);">${acledEvents}</td>
            <td style="text-align: right; color: #ef4444; padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05);">${acledFatalities}</td>
            <td style="text-align: right; color: #fbbf24; padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05);">${idpVal}</td>
            <td style="text-align: right; color: #60a5fa; padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05);">${rainVal}</td>
            <td style="text-align: right; color: #3b82f6; padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05);">${rainAnom}</td>
            <td style="text-align: right; color: #818cf8; padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05);">${wfpPrice}</td>
            <td style="text-align: right; color: #4f46e5; padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05);">${wfpInf}</td>
        `;
        tbody.appendChild(tr);
    });
}

// ── REGIONAL SVG BOUNDARIES DRAWING & TOOLTIPS ──

let activeSubregionMapData = null; // Cache active boundaries/data for toggles

// Color interpolation helper (Hex to RGB and back)
function interpolateColor(color1, color2, factor) {
    if (factor < 0) factor = 0;
    if (factor > 1) factor = 1;
    
    // Parse hex
    const r1 = parseInt(color1.substring(1, 3), 16);
    const g1 = parseInt(color1.substring(3, 5), 16);
    const b1 = parseInt(color1.substring(5, 7), 16);
    
    const r2 = parseInt(color2.substring(1, 3), 16);
    const g2 = parseInt(color2.substring(3, 5), 16);
    const b2 = parseInt(color2.substring(5, 7), 16);
    
    // Interpolate
    const r = Math.round(r1 + factor * (r2 - r1));
    const g = Math.round(g1 + factor * (g2 - g1));
    const b = Math.round(b1 + factor * (b2 - b1));
    
    // Format to hex
    const rHex = r.toString(16).padStart(2, '0');
    const gHex = g.toString(16).padStart(2, '0');
    const bHex = b.toString(16).padStart(2, '0');
    
    return `#${rHex}${gHex}${bHex}`;
}

// Helper to extract a specific metric's raw value from trend data
function getMetricValFromTrend(t, metricKey) {
    if (!t) return null;
    if (metricKey === 'ipc') {
        const p3 = t.phase_3_percentage;
        const p4 = t.phase_4_percentage;
        const p5 = t.phase_5_percentage;
        const p3plus = t.phase_3plus_percentage;
        if (p3plus !== undefined && p3plus !== null) return p3plus;
        if (p3 !== undefined && p3 !== null && p4 !== undefined && p4 !== null && p5 !== undefined && p5 !== null) {
            return p3 + p4 + p5;
        }
        return null;
    }
    if (metricKey === 'acled') {
        return t.acled_total_events !== undefined && t.acled_total_events !== null ? t.acled_total_events : null;
    }
    if (metricKey === 'idp') {
        return t.idp_population !== undefined && t.idp_population !== null ? t.idp_population : null;
    }
    if (metricKey === 'rainfall') {
        return t.rain_1m !== undefined && t.rain_1m !== null ? t.rain_1m : null;
    }
    if (metricKey === 'wfp') {
        return t.wfp_price !== undefined && t.wfp_price !== null ? t.wfp_price : null;
    }
    return null;
}

function drawSubregionMap(containerId, geojson, countryData) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = "";
    
    if (!geojson || !geojson.features || geojson.features.length === 0) {
        container.innerHTML = `
            <div style="height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; color: var(--text-muted); font-size: 0.75rem; text-align: center; padding: 1rem;">
                <i class="fa-solid fa-map-location-dot fa-2x mb-2" style="opacity:0.5;"></i>
                Mappa regionale non disponibile
            </div>
        `;
        return;
    }
    
    // Store globally for toggle layer switches
    if (containerId === "sidebar-country-map-container") {
        activeSubregionMapData = { geojson, countryData };
    }
    
    // Calculate bounding box of all coordinates
    let minLon = 180, maxLon = -180, minLat = 90, maxLat = -90;
    
    function parseCoord(lon, lat) {
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
    
    // If bbox is invalid, set defaults
    if (minLon >= maxLon || minLat >= maxLat) {
        minLon = -180; maxLon = 180; minLat = -90; maxLat = 90;
    }
    
    const width = container.clientWidth || 300;
    const height = container.clientHeight || 250;
    const pad = 15;
    
    // Maintain aspect ratio
    const mapW = maxLon - minLon;
    const mapH = maxLat - minLat;
    
    let scale;
    if (mapW / mapH > width / height) {
        scale = (width - 2 * pad) / mapW;
    } else {
        scale = (height - 2 * pad) / mapH;
    }
    
    const offsetX = pad + (width - 2 * pad - mapW * scale) / 2;
    const offsetY = pad + (height - 2 * pad - mapH * scale) / 2;
    
    const scaleX = (lon) => offsetX + (lon - minLon) * scale;
    const scaleY = (lat) => height - (offsetY + (lat - minLat) * scale);
    
    // Create SVG element
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("width", "100%");
    svg.setAttribute("height", "100%");
    svg.style.display = "block";
    container.appendChild(svg);
    
    // Create Tooltip
    const tooltip = document.createElement("div");
    tooltip.className = "regional-map-tooltip";
    tooltip.style.display = "none";
    container.appendChild(tooltip);
    
    // Determine metric for coloring
    const metricSelector = document.getElementById("map-color-metric");
    const metricKey = (containerId === "sidebar-country-map-container" && metricSelector) 
        ? metricSelector.value 
        : "completeness";
        
    // Compute completeness score or metric average for each pcode
    const regionValues = {};
    let validValues = [];
    
    geojson.features.forEach(f => {
        const pcode = f.properties.adm1_pcode || f.properties.adm2_pcode;
        if (!pcode) return;
        
        // Find region trends in countryData
        const pcodeTrends = (countryData.regions) 
            ? ((countryData.regions.adm1 && countryData.regions.adm1[pcode]) 
               || (countryData.regions.adm2 && countryData.regions.adm2[pcode]) 
               || []) 
            : [];
            
        if (pcodeTrends.length > 0) {
            if (metricKey === "completeness") {
                let totalFields = 0;
                let validFields = 0;
                pcodeTrends.forEach(t => {
                    const indicators = [
                        (t.phase_3plus_percentage !== undefined && t.phase_3plus_percentage !== null) || (t.phase_3_percentage !== undefined && t.phase_3_percentage !== null),
                        t.acled_total_events !== undefined && t.acled_total_events !== null,
                        t.idp_population !== undefined && t.idp_population !== null,
                        t.rain_1m !== undefined && t.rain_1m !== null,
                        t.wfp_price !== undefined && t.wfp_price !== null
                    ];
                    validFields += indicators.filter(Boolean).length;
                    totalFields += indicators.length;
                });
                const score = totalFields > 0 ? (validFields / totalFields) * 100 : 0;
                regionValues[pcode] = score;
                validValues.push(score);
            } else {
                // Get average of raw indicator
                const vals = pcodeTrends.map(t => getMetricValFromTrend(t, metricKey)).filter(v => v !== null && v !== undefined);
                if (vals.length > 0) {
                    const avg = vals.reduce((sum, val) => sum + val, 0) / vals.length;
                    regionValues[pcode] = avg;
                    validValues.push(avg);
                } else {
                    regionValues[pcode] = null;
                }
            }
        } else {
            regionValues[pcode] = null;
        }
    });
    
    // Dynamic ranges for coloring normalization
    let minVal = 0;
    let maxVal = 100;
    
    if (metricKey !== "completeness") {
        if (validValues.length > 0) {
            minVal = Math.min(...validValues);
            maxVal = Math.max(...validValues);
        } else {
            minVal = 0;
            maxVal = 1;
        }
    }
    
    const colorMin = "#1e293b"; // Slate 800
    let colorMax = "#10b981"; // Emerald
    
    if (metricKey === 'ipc') colorMax = '#ef4444'; // Red
    else if (metricKey === 'acled') colorMax = '#f43f5e'; // Rose
    else if (metricKey === 'idp') colorMax = '#fbbf24'; // Amber
    else if (metricKey === 'rainfall') colorMax = '#3b82f6'; // Blue
    else if (metricKey === 'wfp') colorMax = '#818cf8'; // Indigo
    
    // Generate paths for subregions
    geojson.features.forEach(f => {
        const pcode = f.properties.adm1_pcode || f.properties.adm2_pcode;
        const name = f.properties.adm1_name || f.properties.adm2_name || pcode;
        const val = regionValues[pcode];
        
        let color = '#090d16'; // no data color
        if (val !== null && val !== undefined) {
            let factor = 0;
            if (maxVal > minVal) {
                factor = (val - minVal) / (maxVal - minVal);
            }
            color = interpolateColor(colorMin, colorMax, factor);
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
            geom.coordinates.forEach(poly => {
                d += generatePathString(poly);
            });
        }
        
        if (d === "") return;
        
        const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        path.setAttribute("d", d);
        path.setAttribute("fill", color);
        path.setAttribute("class", `region-path region-pcode-${pcode}`);
        if (state.subregion === `adm1_${pcode}`) {
            path.classList.add("active-region");
        }
        
        // Custom Tooltip text depending on metric
        let valStr = "";
        if (val === null || val === undefined) {
            valStr = "Nessun dato";
        } else {
            if (metricKey === 'completeness') {
                valStr = `Completezza: <span style="color:#10b981; font-weight:700;">${val.toFixed(0)}%</span>`;
            } else if (metricKey === 'ipc') {
                valStr = `IPC Fase 3+ (Media): <span style="color:#ef4444; font-weight:700;">${val.toFixed(1)}%</span>`;
            } else if (metricKey === 'acled') {
                valStr = `Eventi Conflitto (Media): <span style="color:#f43f5e; font-weight:700;">${val.toFixed(1)}</span>`;
            } else if (metricKey === 'idp') {
                valStr = `Sfollati IDP (Media): <span style="color:#fbbf24; font-weight:700;">${formatNumber(Math.round(val))}</span>`;
            } else if (metricKey === 'rainfall') {
                valStr = `Precipitazioni (Media): <span style="color:#3b82f6; font-weight:700;">${Math.round(val)} mm</span>`;
            } else if (metricKey === 'wfp') {
                valStr = `Indice Prezzi (Media): <span style="color:#818cf8; font-weight:700;">${val.toFixed(2)}</span>`;
            }
        }
        
        // Hover listeners
        path.addEventListener("mouseover", (e) => {
            path.style.filter = "brightness(1.2)";
            tooltip.style.display = "block";
            tooltip.innerHTML = `
                <div style="font-weight:700; font-family:Outfit;">${name}</div>
                <div style="font-size:0.65rem; color:var(--text-secondary); margin-top:2px;">
                    ${valStr}
                </div>
            `;
        });
        
        path.addEventListener("mousemove", (e) => {
            const rect = container.getBoundingClientRect();
            tooltip.style.left = (e.clientX - rect.left + 10) + "px";
            tooltip.style.top = (e.clientY - rect.top + 10) + "px";
        });
        
        path.addEventListener("mouseout", () => {
            path.style.filter = "";
            tooltip.style.display = "none";
        });
        
        path.addEventListener("click", () => {
            if (containerId === "sidebar-country-map-container" || containerId === "country-tab-map-container") {
                const selectEl = document.getElementById("subregion-selector");
                const targetValue = `adm1_${pcode}`;
                
                // Toggle selection
                if (state.subregion === targetValue) {
                    state.subregion = 'national';
                } else {
                    state.subregion = targetValue;
                }
                
                // Highlight path manually
                document.querySelectorAll(".region-path").forEach(p => p.classList.remove("active-region"));
                if (state.subregion !== 'national') {
                    path.classList.add("active-region");
                }
                if (selectEl) selectEl.value = state.subregion;
                
                // If clicked from the country detail large map tab, jump to charts tab to see results immediately
                if (containerId === "country-tab-map-container") {
                    switchCountrySubView('charts');
                }
                
                updateCountryDashboard();
            } else {
                // Clicked from Global Overview Geographic Audit Modal map
                closeCountryAuditModal();
                state.selectedCountry = countryData.code;
                state.preselectedSubregion = pcode;
                document.getElementById('country-selector').value = countryData.code;
                switchView('country');
                // Ensure it opens the charts sub-tab directly so they see filtered graphs
                switchCountrySubView('charts');
            }
        });
        
        svg.appendChild(path);
    });
    
    // Draw markets overlay dots
    const toggleMarkets = document.getElementById("toggle-markets-layer");
    const showMarkets = (containerId === "sidebar-country-map-container" && toggleMarkets)
        ? toggleMarkets.checked
        : true; // Always show in modal geo audit
        
    if (showMarkets && countryData.markets && countryData.markets.length > 0) {
        countryData.markets.forEach(m => {
            const cx = scaleX(m.lon);
            const cy = scaleY(m.lat);
            
            if (cx < 0 || cx > width || cy < 0 || cy > height) return;
            
            const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
            circle.setAttribute("cx", cx);
            circle.setAttribute("cy", cy);
            circle.setAttribute("r", "3");
            circle.setAttribute("class", "market-dot");
            
            circle.addEventListener("mouseover", (e) => {
                tooltip.style.display = "block";
                tooltip.innerHTML = `
                    <div style="font-weight:700; font-family:Outfit; color:#818cf8;"><i class="fa-solid fa-store mr-1"></i>Mercato: ${m.name}</div>
                    <div style="font-size:0.6rem; color:var(--text-secondary); margin-top:2px;">
                        Lat: ${m.lat.toFixed(3)}, Lon: ${m.lon.toFixed(3)}
                    </div>
                `;
            });
            
            circle.addEventListener("mousemove", (e) => {
                const rect = container.getBoundingClientRect();
                tooltip.style.left = (e.clientX - rect.left + 10) + "px";
                tooltip.style.top = (e.clientY - rect.top + 10) + "px";
            });
            
            circle.addEventListener("mouseout", () => {
                tooltip.style.display = "none";
            });
            
            svg.appendChild(circle);
        });
    }
    
    // Append colorbar legend
    const legendDiv = document.createElement("div");
    legendDiv.className = "map-legend-colorbar";
    legendDiv.style.position = "absolute";
    legendDiv.style.bottom = "8px";
    legendDiv.style.left = "8px";
    legendDiv.style.right = "8px";
    legendDiv.style.background = "rgba(15, 23, 42, 0.85)";
    legendDiv.style.backdropFilter = "blur(4px)";
    legendDiv.style.padding = "4px 8px";
    legendDiv.style.borderRadius = "6px";
    legendDiv.style.border = "1px solid rgba(255, 255, 255, 0.08)";
    legendDiv.style.display = "flex";
    legendDiv.style.flexDirection = "column";
    legendDiv.style.gap = "2px";
    legendDiv.style.pointerEvents = "none";
    
    const titleText = getMetricLegendTitle(metricKey);
    const minText = formatLegendLabel(minVal, metricKey);
    const maxText = formatLegendLabel(maxVal, metricKey);
    
    legendDiv.innerHTML = `
        <div style="display: flex; justify-content: space-between; font-size: 0.6rem; color: var(--text-secondary); line-height: 1;">
            <span>${minText}</span>
            <span style="font-weight: 600; color: white;">${titleText}</span>
            <span>${maxText}</span>
        </div>
        <div style="height: 5px; width: 100%; border-radius: 2px; background: linear-gradient(to right, ${colorMin}, ${colorMax}); margin-top: 2px;"></div>
    `;
    container.appendChild(legendDiv);
}

function toggleMarketsLayer() {
    if (activeSubregionMapData) {
        drawSubregionMap("sidebar-country-map-container", activeSubregionMapData.geojson, activeSubregionMapData.countryData);
    }
}

function onMapColorMetricChange() {
    if (activeSubregionMapData) {
        drawSubregionMap("sidebar-country-map-container", activeSubregionMapData.geojson, activeSubregionMapData.countryData);
    }
}

// ── AUDIT MODAL LOGIC ──

async function openCountryAuditModal(iso3) {
    const modal = document.getElementById("country-audit-modal");
    if (!modal) return;
    modal.style.display = "flex";
    
    const modalTitle = document.getElementById("modal-country-name");
    modalTitle.innerText = `Caricamento... (${iso3})`;
    
    const mapContainer = document.getElementById("modal-country-map-container");
    mapContainer.innerHTML = `
        <div style="display:flex; align-items:center; justify-content:center; color:var(--text-muted); font-size:0.85rem; height: 100%;">
            <i class="fa-solid fa-spinner fa-spin mr-2"></i> Caricamento confini e statistiche...
        </div>
    `;
    
    const listContainer = document.getElementById("modal-subregions-list");
    listContainer.innerHTML = "";
    
    try {
        const [countryData, geojson] = await Promise.all([
            getOrFetchCountry(iso3),
            fetch(`data/boundaries/${iso3}.json`).then(r => r.ok ? r.json() : null).catch(() => null)
        ]);
        
        modalTitle.innerText = `${countryData.name} (${iso3})`;
        
        const btn = document.getElementById("modal-go-to-details-btn");
        btn.onclick = () => {
            closeCountryAuditModal();
            state.selectedCountry = iso3;
            document.getElementById('country-selector').value = iso3;
            switchView('country');
        };
        
        if (!geojson) {
            mapContainer.innerHTML = `
                <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; color: var(--text-muted); text-align: center; padding: 1.5rem; font-size:0.8rem; height: 100%;">
                    <i class="fa-solid fa-triangle-exclamation fa-2x mb-2" style="color:var(--color-warning);"></i>
                    Confini GeoJSON non trovati per questo paese.
                </div>
            `;
            listContainer.innerHTML = `<div style="padding:1rem; text-align:center; color:var(--text-muted); font-size:0.75rem;">Nessuna sotto-regione da elencare</div>`;
            return;
        }
        
        drawSubregionMap("modal-country-map-container", geojson, countryData);
        
        // Calculate scores and populate list
        const regionScores = [];
        geojson.features.forEach(f => {
            const pcode = f.properties.adm1_pcode;
            const name = f.properties.adm1_name || pcode;
            if (!pcode) return;
            
            const pcodeTrends = (countryData.regions && countryData.regions.adm1) ? (countryData.regions.adm1[pcode] || []) : [];
            let score = 0;
            let latestMetrics = { ipc: null, acled: null, idp: null, rain: null, wfp: null };
            if (pcodeTrends.length > 0) {
                let totalFields = 0;
                let validFields = 0;
                pcodeTrends.forEach(t => {
                    const indicators = [
                        t.phase_3plus_percentage !== undefined && t.phase_3plus_percentage !== null,
                        t.acled_total_events !== undefined && t.acled_total_events !== null,
                        t.idp_population !== undefined && t.idp_population !== null,
                        t.rain_1m !== undefined && t.rain_1m !== null,
                        t.wfp_price !== undefined && t.wfp_price !== null
                    ];
                    validFields += indicators.filter(Boolean).length;
                    totalFields += indicators.length;
                });
                score = totalFields > 0 ? (validFields / totalFields) * 100 : 0;
                
                // Scan backwards to find the latest non-null value for each metric
                for (let i = pcodeTrends.length - 1; i >= 0; i--) {
                    const t = pcodeTrends[i];
                    if (latestMetrics.ipc === null && t.phase_3plus_percentage !== undefined && t.phase_3plus_percentage !== null) {
                        latestMetrics.ipc = t.phase_3plus_percentage;
                    }
                    if (latestMetrics.acled === null && t.acled_total_events !== undefined && t.acled_total_events !== null) {
                        latestMetrics.acled = t.acled_total_events;
                    }
                    if (latestMetrics.idp === null && t.idp_population !== undefined && t.idp_population !== null) {
                        latestMetrics.idp = t.idp_population;
                    }
                    if (latestMetrics.rain === null && t.rain_1m !== undefined && t.rain_1m !== null) {
                        latestMetrics.rain = t.rain_1m;
                    }
                    if (latestMetrics.wfp === null && t.wfp_price !== undefined && t.wfp_price !== null) {
                        latestMetrics.wfp = t.wfp_price;
                    }
                }
            }
            regionScores.push({ name, pcode, score, metrics: latestMetrics });
        });
        
        regionScores.sort((a, b) => b.score - a.score);
        
        listContainer.innerHTML = "";
        regionScores.forEach(r => {
            const item = document.createElement("div");
            item.className = "modal-subregion-item";
            item.style.cursor = "pointer";
            item.style.transition = "all 0.2s ease";
            item.onmouseenter = () => {
                item.style.borderColor = "rgba(99, 102, 241, 0.4)";
                item.style.background = "rgba(99, 102, 241, 0.05)";
            };
            item.onmouseleave = () => {
                item.style.borderColor = "";
                item.style.background = "";
            };
            item.onclick = () => {
                closeCountryAuditModal();
                state.selectedCountry = countryData.code;
                state.preselectedSubregion = r.pcode;
                document.getElementById('country-selector').value = countryData.code;
                switchView('country');
                switchCountrySubView('charts');
            };
            
            const ipcStr = r.metrics.ipc !== null ? `${r.metrics.ipc.toFixed(1)}%` : 'N/A';
            const acledStr = r.metrics.acled !== null ? `${r.metrics.acled}` : 'N/A';
            const idpStr = r.metrics.idp !== null ? formatNumber(r.metrics.idp) : 'N/A';
            const rainStr = r.metrics.rain !== null ? `${Math.round(r.metrics.rain)}mm` : 'N/A';
            const wfpStr = r.metrics.wfp !== null ? `${r.metrics.wfp.toFixed(2)}` : 'N/A';
            
            item.innerHTML = `
                <div style="display: flex; flex-direction: column; gap: 0.35rem; width: 100%;">
                    <div style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
                        <div>
                            <span style="font-weight:700; color:white; font-size: 0.85rem;">${r.name}</span>
                            <span style="font-size:0.6rem; color:var(--text-muted); margin-left:0.5rem;">${r.pcode}</span>
                        </div>
                        <span class="badge ${r.score > 70 ? 'badge-green' : (r.score > 30 ? 'badge-yellow' : 'badge-red')}">${r.score.toFixed(0)}%</span>
                    </div>
                    <div style="display: flex; gap: 0.75rem; font-size: 0.7rem; color: var(--text-secondary); border-top: 1px dashed rgba(255,255,255,0.06); padding-top: 0.35rem; margin-top: 0.15rem;">
                        <span title="IPC 3+ (Sicurezza Alimentare)"><i class="fa-solid fa-wheat-awn text-emerald-400 mr-1"></i>${ipcStr}</span>
                        <span title="Eventi Conflitto ACLED"><i class="fa-solid fa-burst text-rose-400 mr-1"></i>${acledStr}</span>
                        <span title="Popolazione Sfollata IDP"><i class="fa-solid fa-person-walking-arrow-right text-amber-400 mr-1"></i>${idpStr}</span>
                        <span title="Pioggia CHIRPS"><i class="fa-solid fa-cloud-showers-water text-blue-400 mr-1"></i>${rainStr}</span>
                        <span title="Indice Prezzi WFP"><i class="fa-solid fa-store text-indigo-400 mr-1"></i>${wfpStr}</span>
                    </div>
                </div>
            `;
            listContainer.appendChild(item);
        });
        
    } catch (err) {
        console.error("Error opening modal audit:", err);
        mapContainer.innerHTML = `<div style="padding:1rem; color:var(--color-danger); height: 100%; display: flex; align-items: center; justify-content: center;">Errore nel caricamento dell'audit.</div>`;
    }
}

function closeCountryAuditModal() {
    const modal = document.getElementById("country-audit-modal");
    if (modal) modal.style.display = "none";
}

// ── COMPARE COUNTRIES TAB LOGIC ──

let compareCharts = null;

function initCompareSelectors() {
    if (!globalData) return;
    
    // Initialize default compare list if empty
    if (!state.compareCountries || state.compareCountries.length === 0) {
        state.compareCountries = [];
        if (globalData.countries.length > 0) {
            state.compareCountries.push(globalData.countries[0].code);
        }
        if (globalData.countries.length > 1) {
            state.compareCountries.push(globalData.countries[1].code);
        }
    }
    
    renderCompareTags();
    populateCompareAddSelector();
    onCompareCountriesChange();
}

function populateCompareAddSelector() {
    if (!globalData) return;
    const select = document.getElementById("compare-add-selector");
    if (!select) return;
    select.innerHTML = "";
    
    // Filter out countries that are already in the comparison
    const remaining = globalData.countries.filter(c => !state.compareCountries.includes(c.code));
    
    remaining.forEach(c => {
        const opt = document.createElement("option");
        opt.value = c.code;
        opt.innerText = `${c.name} (${c.code})`;
        select.appendChild(opt);
    });
}

async function addCountryToComparison() {
    const select = document.getElementById("compare-add-selector");
    if (!select) return;
    const code = select.value;
    if (!code) return;
    
    if (!state.compareCountries.includes(code)) {
        state.compareCountries.push(code);
        renderCompareTags();
        populateCompareAddSelector();
        await onCompareCountriesChange();
    }
}

async function removeCountryFromComparison(code) {
    state.compareCountries = state.compareCountries.filter(c => c !== code);
    renderCompareTags();
    populateCompareAddSelector();
    await onCompareCountriesChange();
}

function renderCompareTags() {
    const container = document.getElementById("compare-tags-container");
    if (!container) return;
    container.innerHTML = "";
    
    state.compareCountries.forEach(code => {
        const country = globalData.countries.find(c => c.code === code);
        if (!country) return;
        
        const tag = document.createElement("div");
        tag.className = "compare-tag";
        tag.innerHTML = `
            <span>${country.name} (${code})</span>
            <button class="compare-tag-remove" onclick="removeCountryFromComparison('${code}')">&times;</button>
        `;
        container.appendChild(tag);
    });
}

async function onCompareCountriesChange() {
    const metricKey = document.getElementById("compare-metric").value;
    
    if (!state.compareCountries || state.compareCountries.length === 0) {
        document.getElementById("chart-compare").innerHTML = `
            <div style="height: 380px; display: flex; align-items: center; justify-content: center; color: var(--text-muted);">
                Aggiungi almeno un paese per visualizzare il confronto
            </div>
        `;
        document.getElementById("compare-details-grid").innerHTML = "";
        return;
    }
    
    try {
        // Fetch data for all selected countries in parallel
        const promises = state.compareCountries.map(code => getOrFetchCountry(code));
        const countriesData = await Promise.all(promises);
        
        renderComparativeChart(countriesData, metricKey);
        renderComparativeDetails(countriesData);
        
    } catch (err) {
        console.error("Comparison load error:", err);
    }
}

async function getOrFetchCountry(code) {
    if (countryCache[code]) return countryCache[code];
    const res = await fetch(`data/countries/${code}.json`);
    const data = await res.json();
    countryCache[code] = data;
    return data;
}

function renderComparativeChart(countriesData, metricKey) {
    // Find all unique dates from all selected countries
    const datesSet = new Set();
    countriesData.forEach(data => {
        const trends = data.trends.adm1.length > 0 ? data.trends.adm1 : data.trends.adm2;
        trends.forEach(t => datesSet.add(t.from));
    });
    const sortedDates = Array.from(datesSet).sort();
    
    // Pre-defined color palette for countries in comparison
    const colors = ['#6366f1', '#a855f7', '#fbbf24', '#10b981', '#f43f5e', '#06b6d4', '#ea580c', '#ec4899'];
    
    const series = countriesData.map((data, idx) => {
        const trends = data.trends.adm1.length > 0 ? data.trends.adm1 : data.trends.adm2;
        const valMap = {};
        trends.forEach(t => {
            const val = getMetricValFromTrend(t, metricKey);
            valMap[t.from] = val !== undefined && val !== null ? parseFloat(val.toFixed(1)) : null;
        });
        
        return {
            name: data.name,
            data: sortedDates.map(d => valMap[d] !== undefined ? valMap[d] : null),
            color: colors[idx % colors.length]
        };
    });
    
    const options = {
        series: series,
        chart: {
            type: 'line',
            height: 380,
            id: 'chart-compare-view',
            toolbar: { show: true },
            background: 'transparent'
        },
        theme: { mode: 'dark' },
        stroke: {
            width: countriesData.map(() => 3),
            curve: 'straight',
            connectNulls: true
        },
        xaxis: {
            categories: sortedDates,
            tickAmount: Math.min(sortedDates.length, 10),
            labels: {
                style: { fontSize: '10px' }
            }
        },
        yaxis: {
            title: { text: getMetricLabel(metricKey) },
            labels: {
                formatter: function(val) {
                    return val !== null ? formatNumber(val) : "";
                }
            }
        },
        markers: {
            size: 5,
            hover: {
                size: 7
            }
        },
        tooltip: {
            enabled: true,
            shared: true,
            intersect: false
        },
        legend: {
            position: 'top',
            fontFamily: 'Inter',
            fontSize: '12px'
        }
    };
    
    const container = document.getElementById("chart-compare");
    container.innerHTML = "";
    if (compareCharts) compareCharts.destroy();
    compareCharts = new ApexCharts(container, options);
    compareCharts.render();
}

function getMetricLabel(key) {
    if (key === 'ipc') return 'Percentuale Popolazione IPC 3+';
    if (key === 'acled') return 'Eventi di Conflitto';
    if (key === 'idp') return 'Popolazione IDP';
    if (key === 'rainfall') return 'Precipitazioni (mm)';
    if (key === 'wfp') return 'Indice dei Prezzi Alimentari';
    return '';
}

function renderComparativeDetails(countriesData) {
    const grid = document.getElementById("compare-details-grid");
    if (!grid) return;
    grid.innerHTML = "";
    
    countriesData.forEach(data => {
        const card = document.createElement("div");
        card.className = "glass-card";
        card.style.padding = "1.25rem 1.5rem";
        
        const trends = data.trends.adm1.length > 0 ? data.trends.adm1 : data.trends.adm2;
        
        const getAvgField = (field) => {
            const vals = trends.map(t => {
                if (field === 'phase_3plus_percentage') return getMetricValFromTrend(t, 'ipc');
                return t[field];
            }).filter(v => v !== null && v !== undefined);
            return vals.length > 0 ? (vals.reduce((a, b) => a + b, 0) / vals.length) : null;
        };
        
        const avgIpc = getAvgField('phase_3plus_percentage');
        const avgAcled = getAvgField('acled_total_events');
        const avgIdp = getAvgField('idp_population');
        const avgRain = getAvgField('rain_1m');
        const avgPrice = getAvgField('wfp_price');
        const flag = getFlagEmoji(ISO3_TO_ISO2[data.code]);
        
        const content = `
            <div class="card-title" style="margin-bottom: 0.75rem; border-bottom: 1px solid var(--border-color); padding-bottom: 0.5rem;">
                <div class="card-title-text">
                    <span style="font-size: 1.15rem; margin-right: 0.25rem;">${flag}</span>
                    <span>${data.name} (${data.code})</span>
                </div>
            </div>
            <div style="display: flex; flex-direction: column; gap: 0.75rem;">
                <div class="detail-row">
                    <span class="detail-label" style="font-weight:700;">Risoluzione Dati:</span>
                    <span class="badge badge-blue">${data.trends.adm1.length > 0 ? "Admin 1 (Province)" : "Admin 2 (Distretti)"}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label" style="font-weight:700;">Totale Mercati (WFP):</span>
                    <span class="badge badge-green">${data.markets ? data.markets.length : 0} mercati</span>
                </div>
                
                <h4 style="margin-top: 0.5rem; color: var(--text-secondary); font-size: 0.75rem; text-transform: uppercase;">Valori Medi Storici:</h4>
                
                <div class="detail-row" style="background: rgba(255,255,255,0.01); padding: 0.4rem 0.6rem; border-radius: 6px;">
                    <span class="detail-label">IPC Fase 3+ (Sicurezza Alimentare):</span>
                    <span class="detail-value" style="color: #ef4444; font-weight:700;">${avgIpc !== null ? avgIpc.toFixed(1) + "%" : "N/A"}</span>
                </div>
                <div class="detail-row" style="background: rgba(255,255,255,0.01); padding: 0.4rem 0.6rem; border-radius: 6px;">
                    <span class="detail-label">Eventi Conflitto ACLED (Media/Mese):</span>
                    <span class="detail-value" style="color: #f43f5e; font-weight:700;">${avgAcled !== null ? avgAcled.toFixed(1) : "N/A"}</span>
                </div>
                <div class="detail-row" style="background: rgba(255,255,255,0.01); padding: 0.4rem 0.6rem; border-radius: 6px;">
                    <span class="detail-label">Popolazione IDP (Media):</span>
                    <span class="detail-value" style="color: #fbbf24; font-weight:700;">${avgIdp !== null ? formatNumber(Math.round(avgIdp)) : "N/A"}</span>
                </div>
                <div class="detail-row" style="background: rgba(255,255,255,0.01); padding: 0.4rem 0.6rem; border-radius: 6px;">
                    <span class="detail-label">Precipitazioni CHIRPS (Media):</span>
                    <span class="detail-value" style="color: #3b82f6; font-weight:700;">${avgRain !== null ? Math.round(avgRain) + " mm" : "N/A"}</span>
                </div>
                <div class="detail-row" style="background: rgba(255,255,255,0.01); padding: 0.4rem 0.6rem; border-radius: 6px;">
                    <span class="detail-label">Indice Prezzi Alimentari WFP (Media):</span>
                    <span class="detail-value" style="color: #818cf8; font-weight:700;">${avgPrice !== null ? avgPrice.toFixed(2) : "N/A"}</span>
                </div>
            </div>
        `;
        card.innerHTML = content;
        grid.appendChild(card);
    });
}

// ── TEMPORAL MAP PANEL LOGIC ──

let temporalMapInstance = null;
let currentTemporalTheme = null;
let timelineInterval = null;
let currentTimelineIndex = 0;

function onValuesThemeChange() {
    stopTimelinePlay();
    initTimelineControls();
    renderTemporalMap();
}

function initTimelineControls() {
    if (!globalData) return;
    
    const theme = document.getElementById("values-theme-selector").value;
    const heatmapData = globalData.value_heatmaps[theme];
    if (!heatmapData) return;
    
    const slider = document.getElementById("timeline-slider");
    if (!slider) return;
    
    slider.min = 0;
    slider.max = heatmapData.x.length - 1;
    if (currentTimelineIndex >= heatmapData.x.length) {
        currentTimelineIndex = 0;
    }
    slider.value = currentTimelineIndex;
    
    document.getElementById("timeline-quarter-label").innerText = heatmapData.x[currentTimelineIndex];
}

function onTimelineSliderInput(value) {
    currentTimelineIndex = parseInt(value);
    const theme = document.getElementById("values-theme-selector").value;
    const heatmapData = globalData.value_heatmaps[theme];
    if (heatmapData) {
        document.getElementById("timeline-quarter-label").innerText = heatmapData.x[currentTimelineIndex];
        renderTemporalMap();
    }
}

function toggleTimelinePlay() {
    const playBtn = document.getElementById("btn-play-timeline");
    const playText = document.getElementById("btn-play-text");
    if (!playBtn || !playText) return;
    
    if (timelineInterval) {
        stopTimelinePlay();
    } else {
        playText.innerText = "PAUSA";
        playBtn.querySelector("i").className = "fa-solid fa-pause";
        playBtn.classList.add("active");
        
        const theme = document.getElementById("values-theme-selector").value;
        const heatmapData = globalData.value_heatmaps[theme];
        if (!heatmapData) return;
        
        timelineInterval = setInterval(() => {
            currentTimelineIndex++;
            if (currentTimelineIndex >= heatmapData.x.length) {
                currentTimelineIndex = 0;
            }
            document.getElementById("timeline-slider").value = currentTimelineIndex;
            document.getElementById("timeline-quarter-label").innerText = heatmapData.x[currentTimelineIndex];
            renderTemporalMap();
        }, 1000); // 1-second step for smooth reading
    }
}

function stopTimelinePlay() {
    if (timelineInterval) {
        clearInterval(timelineInterval);
        timelineInterval = null;
    }
    const playBtn = document.getElementById("btn-play-timeline");
    const playText = document.getElementById("btn-play-text");
    if (playBtn && playText) {
        playText.innerText = "AVVIA";
        playBtn.querySelector("i").className = "fa-solid fa-play";
        playBtn.classList.remove("active");
    }
}

function renderTemporalMap() {
    if (!globalData) return;
    
    const theme = document.getElementById("values-theme-selector").value;
    const heatmapData = globalData.value_heatmaps[theme];
    if (!heatmapData) return;
    
    if (currentTimelineIndex >= heatmapData.x.length) {
        currentTimelineIndex = 0;
    }
    
    // Prepare values for svgMap
    const mapValues = {};
    
    let metricName = "Valore";
    let metricFormat = "{0}";
    let colorMax = "#6366f1";
    let maxVal = undefined;
    
    if (theme === 'ipc') {
        metricName = "IPC Fase 3+";
        metricFormat = "{0}%";
        colorMax = "#ef4444";
        maxVal = 100;
    } else if (theme === 'acled') {
        metricName = "Conflitti (Eventi)";
        metricFormat = "{0}";
        colorMax = "#f43f5e";
        maxVal = 300;
    } else if (theme === 'idp') {
        metricName = "Sfollati Interni";
        metricFormat = "{0}";
        colorMax = "#fbbf24";
        maxVal = 1000000;
    } else if (theme === 'rainfall') {
        metricName = "Precipitazioni";
        metricFormat = "{0} mm";
        colorMax = "#3b82f6";
        maxVal = 300;
    } else if (theme === 'wfp') {
        metricName = "Indice Prezzi";
        metricFormat = "{0}";
        colorMax = "#818cf8";
        maxVal = 3.0;
    }
    
    heatmapData.y_codes.forEach((iso3, idx) => {
        const val = heatmapData.z[idx][currentTimelineIndex];
        const iso2 = ISO3_TO_ISO2[iso3];
        if (iso2 && val !== null && val !== undefined) {
            mapValues[iso2] = {
                val: parseFloat(val.toFixed(1))
            };
        }
    });

    const container = document.getElementById("temporal-map");
    if (!container) return;
    
    // Check if temporalMapInstance is already initialized AND the theme hasn't changed
    if (temporalMapInstance && currentTemporalTheme === theme) {
        // Reset all values first to handle missing data countries
        for (let iso2 in temporalMapInstance.options.data.values) {
            temporalMapInstance.options.data.values[iso2] = undefined;
        }
        
        // Find all country path elements and set default color
        const paths = container.querySelectorAll('.svgMap-country');
        paths.forEach(path => {
            path.style.fill = '#090d16';
        });
        
        // Update values and update path colors
        heatmapData.y_codes.forEach((iso3, idx) => {
            const val = heatmapData.z[idx][currentTimelineIndex];
            const iso2 = ISO3_TO_ISO2[iso3];
            if (iso2) {
                const path = container.querySelector(`.svgMap-country-${iso2}`) || container.querySelector(`.svgMap-country[data-id="${iso2}"]`);
                if (val !== null && val !== undefined) {
                    const parsedVal = parseFloat(val.toFixed(1));
                    temporalMapInstance.options.data.values[iso2] = {
                        val: parsedVal
                    };
                    // Calculate color
                    const factor = maxVal ? Math.min(Math.max(parsedVal / maxVal, 0), 1) : 0;
                    const color = interpolateColor('#1e293b', colorMax, factor);
                    if (path) {
                        path.style.fill = color;
                    }
                } else {
                    temporalMapInstance.options.data.values[iso2] = undefined;
                    if (path) {
                        path.style.fill = '#090d16';
                    }
                }
            }
        });
        return; // Complete! Preserved zoom and pan.
    }
    
    // Clear any stuck tooltips to prevent leaks during animation/recreation
    document.querySelectorAll('.svgMap-tooltip').forEach(el => el.remove());
    container.innerHTML = "";
    
    currentTemporalTheme = theme;
    
    // Initialize svgMap
    temporalMapInstance = new svgMap({
        targetElementID: 'temporal-map',
        showTooltips: false, // disable built-in tooltips
        data: {
            data: {
                val: {
                    name: metricName,
                    format: metricFormat,
                    thresholdMax: maxVal,
                    thresholdMin: 0
                }
            },
            applyData: 'val',
            values: mapValues
        },
        colorMin: '#1e293b', // slate
        colorMax: colorMax,
        colorNoData: '#090d16',
        onCountryClick: function(countryID) {
            const iso3 = ISO2_TO_ISO3[countryID.toUpperCase()];
            if (iso3 && globalData.countries.some(c => c.code === iso3)) {
                highlightCountryOnMap(iso3);
                openCountryAuditModal(iso3);
            }
        }
    });
    
    // Bind custom tooltips with event delegation
    initCustomMapTooltips('temporal-map', getTemporalMapTooltipContent);
}

// ── NEW HELPER FUNCTIONS ──

function getFlagEmoji(iso2) {
    if (!iso2) return "🏳️";
    const codePoints = iso2
        .toUpperCase()
        .split('')
        .map(char => 127397 + char.charCodeAt(0));
    try {
        return String.fromCodePoint(...codePoints);
    } catch (e) {
        return "🏳️";
    }
}

function populateMapCountryList() {
    const container = document.getElementById("map-countries-items");
    if (!container || !globalData) return;
    container.innerHTML = "";
    
    const sorted = [...globalData.countries].sort((a, b) => a.name.localeCompare(b.name));
    
    sorted.forEach(c => {
        const score = state.adminLevel === 'adm1' ? c.score_adm1 : c.score_adm2;
        const iso2 = ISO3_TO_ISO2[c.code];
        const flag = getFlagEmoji(iso2);
        
        const item = document.createElement("div");
        item.className = "map-country-item";
        item.id = `map-item-${c.code}`;
        item.setAttribute("data-code", c.code);
        item.title = c.name;
        item.onclick = () => {
            highlightCountryOnMap(c.code);
            openCountryAuditModal(c.code);
        };
        
        // Add hover highlights to the world map
        item.onmouseenter = () => {
            hoverCountryOnMap(c.code, true);
        };
        item.onmouseleave = () => {
            hoverCountryOnMap(c.code, false);
        };
        
        item.innerHTML = `
            <div style="display: flex; align-items: center; gap: 0.35rem; min-width: 0;">
                <span style="font-size: 1rem;">${flag}</span>
                <span style="font-weight: 700; color: white;">${c.code}</span>
            </div>
            <span style="font-size: 0.75rem; color: var(--text-secondary); font-weight: 600;">${score.toFixed(0)}%</span>
        `;
        container.appendChild(item);
    });
}

function highlightCountryOnMap(iso3) {
    state.activeMapCountry = iso3;
    // Remove active highlight from all
    document.querySelectorAll('#world-map .svgMap-country').forEach(el => {
        el.style.stroke = '';
        el.style.strokeWidth = '';
        el.style.filter = '';
    });
    
    // Highlight the selected one
    const iso2 = ISO3_TO_ISO2[iso3];
    if (iso2) {
        const path = document.querySelector(`#world-map .svgMap-country-${iso2}`) || 
                     document.querySelector(`#world-map .svgMap-country[data-id="${iso2}"]`);
        if (path) {
            path.style.setProperty('stroke', 'var(--color-primary)', 'important');
            path.style.setProperty('stroke-width', '2px', 'important');
            path.style.setProperty('filter', 'brightness(1.2)', 'important');
        }
    }
    
    // Highlight active item in list
    document.querySelectorAll('#map-countries-items .map-country-item').forEach(el => {
        el.style.background = '';
        el.style.borderColor = '';
    });
    const item = document.getElementById(`map-item-${iso3}`);
    if (item) {
        item.style.background = 'rgba(99, 102, 241, 0.2)';
        item.style.borderColor = 'rgba(99, 102, 241, 0.4)';
        item.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
}

function hoverCountryOnMap(iso3, isHover) {
    if (state.activeMapCountry === iso3) return; // Don't override the clicked country's active styling
    
    const iso2 = ISO3_TO_ISO2[iso3];
    if (!iso2) return;
    
    const path = document.querySelector(`#world-map .svgMap-country-${iso2}`) || 
                 document.querySelector(`#world-map .svgMap-country[data-id="${iso2}"]`);
    if (!path) return;
    
    if (isHover) {
        // Subtle, non-intrusive highlight
        path.style.setProperty('stroke', 'rgba(129, 140, 248, 0.8)', 'important'); // Light indigo
        path.style.setProperty('stroke-width', '1.5px', 'important');
        path.style.setProperty('filter', 'brightness(1.15)', 'important');
    } else {
        // Restore default
        path.style.removeProperty('stroke');
        path.style.removeProperty('stroke-width');
        path.style.removeProperty('filter');
    }
}

function filterMapCountryList(query) {
    const cleanQuery = query.toLowerCase().trim();
    const items = document.querySelectorAll('#map-countries-items .map-country-item');
    items.forEach(item => {
        const code = item.getAttribute("data-code");
        const country = globalData.countries.find(c => c.code === code);
        if (country) {
            const matches = country.name.toLowerCase().includes(cleanQuery) || 
                            country.code.toLowerCase().includes(cleanQuery);
            item.style.display = matches ? 'flex' : 'none';
        }
    });
}

function toggleSidebar() {
    const aside = document.querySelector("aside");
    if (!aside) return;
    
    aside.classList.toggle("collapsed");
    
    const isCollapsed = aside.classList.contains("collapsed");
    localStorage.setItem("sidebarCollapsed", isCollapsed ? "true" : "false");
    
    // Dispatch a resize event to make charts redraw
    setTimeout(() => {
        window.dispatchEvent(new Event('resize'));
    }, 300);
}

function formatLegendLabel(val, metricKey) {
    if (val === null || val === undefined) return "0";
    if (metricKey === 'completeness') return val.toFixed(0) + "%";
    if (metricKey === 'ipc') return val.toFixed(0) + "%";
    if (metricKey === 'acled') return val.toFixed(0);
    if (metricKey === 'idp') {
        if (val >= 1000000) return (val / 1000000).toFixed(1) + "M";
        if (val >= 1000) return (val / 1000).toFixed(0) + "k";
        return val.toFixed(0);
    }
    if (metricKey === 'rainfall') return val.toFixed(0) + " mm";
    if (metricKey === 'wfp') return val.toFixed(1);
    return val.toFixed(0);
}

function getMetricLegendTitle(metricKey) {
    if (metricKey === 'completeness') return 'Completezza';
    if (metricKey === 'ipc') return 'IPC Fase 3+';
    if (metricKey === 'acled') return 'Conflitti';
    if (metricKey === 'idp') return 'Sfollati';
    if (metricKey === 'rainfall') return 'Precipitazioni';
    if (metricKey === 'wfp') return 'Indice Prezzi';
    return '';
}

// ── CUSTOM WORLD & TEMPORAL MAP TOOLTIPS ──

function initCustomMapTooltips(containerId, getTooltipContentFn) {
    const container = document.getElementById(containerId);
    if (!container) return;
    
    const wrapper = container.parentElement;
    if (!wrapper) return;
    
    // Check if tooltip already exists
    let tooltip = wrapper.querySelector(".custom-map-tooltip");
    if (!tooltip) {
        tooltip = document.createElement("div");
        tooltip.className = "custom-map-tooltip";
        tooltip.style.cssText = `
            position: absolute;
            z-index: 10000;
            background: rgba(15, 23, 42, 0.95);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 8px;
            padding: 6px 10px;
            font-family: var(--font-sans);
            font-size: 11px;
            color: #fff;
            pointer-events: none;
            display: none;
            box-shadow: 0 10px 25px -5px rgba(0,0,0,0.5);
            white-space: nowrap;
            transition: opacity 0.1s ease;
            opacity: 0;
        `;
        wrapper.appendChild(tooltip);
    }
    
    if (container.dataset.tooltipsInitialized) return;
    container.dataset.tooltipsInitialized = "true";
    
    // Bind mouseover/mousemove/mouseleave to the container using event delegation
    container.addEventListener("mouseover", (e) => {
        const path = e.target.closest('.svgMap-country');
        if (!path) return;
        
        let iso2 = path.getAttribute('data-id');
        if (!iso2) {
            const classes = Array.from(path.classList);
            for (let cls of classes) {
                if (cls.startsWith('svgMap-country-')) {
                    iso2 = cls.replace('svgMap-country-', '');
                    break;
                }
            }
        }
        if (!iso2) return;
        iso2 = iso2.toUpperCase();
        const iso3 = ISO2_TO_ISO3[iso2];
        if (!iso3) return;
        
        const content = getTooltipContentFn(iso2, iso3);
        if (content) {
            tooltip.innerHTML = content;
            tooltip.style.display = "block";
            // Trigger reflow
            tooltip.offsetHeight;
            tooltip.style.opacity = "1";
        } else {
            tooltip.style.opacity = "0";
            tooltip.style.display = "none";
        }
    });
    
    container.addEventListener("mousemove", (e) => {
        const path = e.target.closest('.svgMap-country');
        if (!path || tooltip.style.display === "none") return;
        
        const rect = wrapper.getBoundingClientRect();
        // Position tooltip near the cursor
        tooltip.style.left = (e.clientX - rect.left + 15) + "px";
        tooltip.style.top = (e.clientY - rect.top + 15) + "px";
    });
    
    container.addEventListener("mouseout", (e) => {
        const path = e.target.closest('.svgMap-country');
        if (!path) return;
        
        tooltip.style.opacity = "0";
        tooltip.style.display = "none";
    });
}

function getWorldMapTooltipContent(iso2, iso3) {
    const country = globalData.countries.find(c => c.code === iso3);
    if (!country) return null; // Only show tooltip for tracked countries
    
    let val = null;
    const heatmapData = globalData.heatmaps[state.adminLevel][state.heatmapTheme];
    if (heatmapData) {
        const idx = heatmapData.y_codes.indexOf(iso3);
        if (idx !== -1) {
            const zRow = heatmapData.z[idx];
            const validValues = zRow.filter(val => val !== null);
            val = validValues.length > 0 ? (validValues.reduce((a, b) => a + b, 0) / validValues.length) : null;
        }
    }
    
    let themeName = "";
    if (state.heatmapTheme === 'overall') themeName = "Completezza Media";
    else if (state.heatmapTheme === 'ipc') themeName = "Sicurezza Alimentare (IPC)";
    else if (state.heatmapTheme === 'acled') themeName = "Conflitti (ACLED)";
    else if (state.heatmapTheme === 'idp') themeName = "Sfollati Interni (IDP)";
    else if (state.heatmapTheme === 'rainfall') themeName = "Precipitazioni (CHIRPS)";
    else if (state.heatmapTheme === 'wfp') themeName = "Prezzi Alimentari (WFP)";
    
    const flag = getFlagEmoji(iso2);
    const valStr = (val !== null && val !== undefined) ? `${val.toFixed(1)}%` : "Nessun dato";
    
    return `
        <div style="display: flex; align-items: center; gap: 0.35rem; font-weight: 700; font-family: Outfit;">
            <span style="font-size: 1.1rem;">${flag}</span>
            <span>${country.name} (${iso3})</span>
        </div>
        <div style="font-size: 0.7rem; color: var(--text-secondary); margin-top: 3px; font-weight: 500;">
            ${themeName}: <span style="color: #a5b4fc; font-weight: 700;">${valStr}</span>
        </div>
    `;
}

function getTemporalMapTooltipContent(iso2, iso3) {
    const country = globalData.countries.find(c => c.code === iso3);
    if (!country) return null; // Only show tooltip for tracked countries
    
    const theme = document.getElementById("values-theme-selector").value;
    const heatmapData = globalData.value_heatmaps[theme];
    if (!heatmapData) return null;
    
    let val = null;
    const idx = heatmapData.y_codes.indexOf(iso3);
    if (idx !== -1) {
        val = heatmapData.z[idx][currentTimelineIndex];
    }
    
    let metricName = "Valore";
    let formattedVal = "Nessun dato";
    if (val !== null && val !== undefined) {
        if (theme === 'ipc') {
            metricName = "IPC Fase 3+";
            formattedVal = `${val.toFixed(1)}%`;
        } else if (theme === 'acled') {
            metricName = "Conflitti (Eventi)";
            formattedVal = `${val.toFixed(0)}`;
        } else if (theme === 'idp') {
            metricName = "Sfollati Interni";
            formattedVal = formatNumber(Math.round(val));
        } else if (theme === 'rainfall') {
            metricName = "Precipitazioni";
            formattedVal = `${Math.round(val)} mm`;
        } else if (theme === 'wfp') {
            metricName = "Indice Prezzi";
            formattedVal = `${val.toFixed(2)}`;
        }
    }
    
    const flag = getFlagEmoji(iso2);
    
    return `
        <div style="display: flex; align-items: center; gap: 0.35rem; font-weight: 700; font-family: Outfit;">
            <span style="font-size: 1.1rem;">${flag}</span>
            <span>${country.name} (${iso3})</span>
        </div>
        <div style="font-size: 0.7rem; color: var(--text-secondary); margin-top: 3px; font-weight: 500;">
            ${metricName}: <span style="color: #a5b4fc; font-weight: 700;">${formattedVal}</span>
        </div>
    `;
}

// ── COUNTRY SUB-VIEWS NAV LOGIC ──

function switchCountrySubView(subViewName) {
    state.countrySubView = subViewName;
    
    // Toggle active tab buttons
    const btnMap = document.getElementById('btn-country-tab-map');
    const btnMarkets = document.getElementById('btn-country-tab-markets');
    const btnCharts = document.getElementById('btn-country-tab-charts');
    const btnTable = document.getElementById('btn-country-tab-table');
    
    if (btnMap) btnMap.classList.toggle('active', subViewName === 'map');
    if (btnMarkets) btnMarkets.classList.toggle('active', subViewName === 'markets');
    if (btnCharts) btnCharts.classList.toggle('active', subViewName === 'charts');
    if (btnTable) btnTable.classList.toggle('active', subViewName === 'table');
    
    // Toggle active sidebar sub-menu items
    const navMap = document.getElementById('nav-country-map');
    const navMarkets = document.getElementById('nav-country-markets');
    const navCharts = document.getElementById('nav-country-charts');
    const navTable = document.getElementById('nav-country-table');
    
    if (navMap) navMap.classList.toggle('active', subViewName === 'map');
    if (navMarkets) navMarkets.classList.toggle('active', subViewName === 'markets');
    if (navCharts) navCharts.classList.toggle('active', subViewName === 'charts');
    if (navTable) navTable.classList.toggle('active', subViewName === 'table');
    
    // Toggle active sub-panels
    const panelMap = document.getElementById('country-sub-panel-map');
    const panelMarkets = document.getElementById('country-sub-panel-markets');
    const panelCharts = document.getElementById('country-sub-panel-charts');
    const panelTable = document.getElementById('country-sub-panel-table');
    
    if (panelMap) panelMap.style.display = subViewName === 'map' ? 'block' : 'none';
    if (panelMarkets) panelMarkets.style.display = subViewName === 'markets' ? 'block' : 'none';
    if (panelCharts) panelCharts.style.display = subViewName === 'charts' ? 'block' : 'none';
    if (panelTable) panelTable.style.display = subViewName === 'table' ? 'block' : 'none';
    
    // Manage chart toggles visibility (only visible in charts sub-view)
    const toggleGroupVal = document.getElementById('chart-layout-toggle-group');
    if (toggleGroupVal) {
        toggleGroupVal.style.display = subViewName === 'charts' ? 'flex' : 'none';
    }
    
    // Render/Redraw components
    if (subViewName === 'map') {
        const code = state.selectedCountry;
        const data = countryCache[code];
        if (data) {
            fetch(`data/boundaries/${code}.json`)
                .then(res => res.ok ? res.json() : null)
                .then(geojson => {
                    drawSubregionMap("country-tab-map-container", geojson, data);
                    populateCountryTabSubregionsList(geojson, data);
                })
                .catch(err => console.error("Error loading boundaries in sub-tab map:", err));
        }
    } else if (subViewName === 'markets') {
        const code = state.selectedCountry;
        const data = countryCache[code];
        if (data) {
            fetch(`data/boundaries/${code}.json`)
                .then(res => res.ok ? res.json() : null)
                .then(geojson => {
                    drawMarketsOnlyMap("country-tab-markets-container", geojson, data);
                    populateCountryTabMarketsList(data);
                })
                .catch(err => console.error("Error loading boundaries in sub-tab markets:", err));
        }
    } else if (subViewName === 'charts') {
        setTimeout(() => {
            for (let key in countryCharts) {
                if (countryCharts[key]) countryCharts[key].windowResizeHandler();
            }
        }, 100);
    }
}

function switchCountrySubViewFromSidebar(subViewName) {
    if (state.currentView !== 'country') {
        switchView('country');
    }
    switchCountrySubView(subViewName);
}

function populateCountryTabSubregionsList(geojson, countryData) {
    const listContainer = document.getElementById("country-tab-subregions-list");
    if (!listContainer) return;
    listContainer.innerHTML = "";
    
    const regionScores = [];
    geojson.features.forEach(f => {
        const pcode = f.properties.adm1_pcode;
        const name = f.properties.adm1_name || pcode;
        if (!pcode) return;
        
        const pcodeTrends = (countryData.regions && countryData.regions.adm1) ? (countryData.regions.adm1[pcode] || []) : [];
        let score = 0;
        let latestMetrics = { ipc: null, acled: null, idp: null, rain: null, wfp: null };
        if (pcodeTrends.length > 0) {
            let totalFields = 0;
            let validFields = 0;
            pcodeTrends.forEach(t => {
                const indicators = [
                    t.phase_3plus_percentage !== undefined && t.phase_3plus_percentage !== null,
                    t.acled_total_events !== undefined && t.acled_total_events !== null,
                    t.idp_population !== undefined && t.idp_population !== null,
                    t.rain_1m !== undefined && t.rain_1m !== null,
                    t.wfp_price !== undefined && t.wfp_price !== null
                ];
                validFields += indicators.filter(Boolean).length;
                totalFields += indicators.length;
            });
            score = totalFields > 0 ? (validFields / totalFields) * 100 : 0;
            
            for (let i = pcodeTrends.length - 1; i >= 0; i--) {
                const t = pcodeTrends[i];
                if (latestMetrics.ipc === null && t.phase_3plus_percentage !== undefined && t.phase_3plus_percentage !== null) {
                    latestMetrics.ipc = t.phase_3plus_percentage;
                }
                if (latestMetrics.acled === null && t.acled_total_events !== undefined && t.acled_total_events !== null) {
                    latestMetrics.acled = t.acled_total_events;
                }
                if (latestMetrics.idp === null && t.idp_population !== undefined && t.idp_population !== null) {
                    latestMetrics.idp = t.idp_population;
                }
                if (latestMetrics.rain === null && t.rain_1m !== undefined && t.rain_1m !== null) {
                    latestMetrics.rain = t.rain_1m;
                }
                if (latestMetrics.wfp === null && t.wfp_price !== undefined && t.wfp_price !== null) {
                    latestMetrics.wfp = t.wfp_price;
                }
            }
        }
        regionScores.push({ name, pcode, score, metrics: latestMetrics });
    });
    
    regionScores.sort((a, b) => b.score - a.score);
    
    regionScores.forEach(r => {
        const item = document.createElement("div");
        item.className = "modal-subregion-item";
        item.style.cursor = "pointer";
        item.style.transition = "all 0.2s ease";
        item.onmouseenter = () => {
            item.style.borderColor = "rgba(99, 102, 241, 0.4)";
            item.style.background = "rgba(99, 102, 241, 0.05)";
        };
        item.onmouseleave = () => {
            item.style.borderColor = "";
            item.style.background = "";
        };
        item.onclick = () => {
            const selectEl = document.getElementById("subregion-selector");
            state.subregion = `adm1_${r.pcode}`;
            if (selectEl) selectEl.value = state.subregion;
            
            // Switch to charts sub-tab and render updated dashboard
            switchCountrySubView('charts');
            updateCountryDashboard();
        };
        
        const ipcStr = r.metrics.ipc !== null ? `${r.metrics.ipc.toFixed(1)}%` : 'N/A';
        const acledStr = r.metrics.acled !== null ? `${r.metrics.acled}` : 'N/A';
        const idpStr = r.metrics.idp !== null ? formatNumber(r.metrics.idp) : 'N/A';
        const rainStr = r.metrics.rain !== null ? `${Math.round(r.metrics.rain)}mm` : 'N/A';
        const wfpStr = r.metrics.wfp !== null ? `${r.metrics.wfp.toFixed(2)}` : 'N/A';
        
        item.innerHTML = `
            <div style="display: flex; flex-direction: column; gap: 0.35rem; width: 100%;">
                <div style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
                    <div>
                        <span style="font-weight:700; color:white; font-size: 0.85rem;">${r.name}</span>
                        <span style="font-size:0.6rem; color:var(--text-muted); margin-left:0.5rem;">${r.pcode}</span>
                    </div>
                    <span class="badge ${r.score > 70 ? 'badge-green' : (r.score > 30 ? 'badge-yellow' : 'badge-red')}">${r.score.toFixed(0)}%</span>
                </div>
                <div style="display: flex; gap: 0.75rem; font-size: 0.7rem; color: var(--text-secondary); border-top: 1px dashed rgba(255,255,255,0.06); padding-top: 0.35rem; margin-top: 0.15rem;">
                    <span title="IPC 3+ (Sicurezza Alimentare)"><i class="fa-solid fa-wheat-awn text-emerald-400 mr-1"></i>${ipcStr}</span>
                    <span title="Eventi Conflitto ACLED"><i class="fa-solid fa-burst text-rose-400 mr-1"></i>${acledStr}</span>
                    <span title="Popolazione Sfollata IDP"><i class="fa-solid fa-person-walking-arrow-right text-amber-400 mr-1"></i>${idpStr}</span>
                    <span title="Pioggia CHIRPS"><i class="fa-solid fa-cloud-showers-water text-blue-400 mr-1"></i>${rainStr}</span>
                    <span title="Indice Prezzi WFP"><i class="fa-solid fa-store text-indigo-400 mr-1"></i>${wfpStr}</span>
                </div>
            </div>
        `;
        listContainer.appendChild(item);
    });
}

function drawMarketsOnlyMap(containerId, geojson, countryData) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = "";
    
    if (!geojson || !geojson.features || geojson.features.length === 0) {
        container.innerHTML = `
            <div style="height: 100%; display: flex; align-items: center; justify-content: center; color: var(--text-muted); font-size: 0.75rem;">
                Mappa non disponibile
            </div>
        `;
        return;
    }
    
    // Calculate bounding box
    let minLon = 180, maxLon = -180, minLat = 90, maxLat = -90;
    geojson.features.forEach(f => {
        const geom = f.geometry;
        if (!geom) return;
        if (geom.type === "Polygon") {
            geom.coordinates.forEach(ring => ring.forEach(pt => {
                if (pt[0] < minLon) minLon = pt[0];
                if (pt[0] > maxLon) maxLon = pt[0];
                if (pt[1] < minLat) minLat = pt[1];
                if (pt[1] > maxLat) maxLat = pt[1];
            }));
        } else if (geom.type === "MultiPolygon") {
            geom.coordinates.forEach(poly => poly.forEach(ring => ring.forEach(pt => {
                if (pt[0] < minLon) minLon = pt[0];
                if (pt[0] > maxLon) maxLon = pt[0];
                if (pt[1] < minLat) minLat = pt[1];
                if (pt[1] > maxLat) maxLat = pt[1];
            })));
        }
    });
    
    const width = container.clientWidth || 400;
    const height = container.clientHeight || 400;
    const pad = 15;
    
    const mapW = maxLon - minLon;
    const mapH = maxLat - minLat;
    
    let scale;
    if (mapW / mapH > width / height) {
        scale = (width - 2 * pad) / mapW;
    } else {
        scale = (height - 2 * pad) / mapH;
    }
    
    const offsetX = pad + (width - 2 * pad - mapW * scale) / 2;
    const offsetY = pad + (height - 2 * pad - mapH * scale) / 2;
    
    const scaleX = (lon) => offsetX + (lon - minLon) * scale;
    const scaleY = (lat) => height - (offsetY + (lat - minLat) * scale);
    
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("width", "100%");
    svg.setAttribute("height", "100%");
    svg.style.display = "block";
    container.appendChild(svg);
    
    const tooltip = document.createElement("div");
    tooltip.className = "regional-map-tooltip";
    tooltip.style.display = "none";
    container.appendChild(tooltip);
    
    // Draw background subregions (neutral dark)
    geojson.features.forEach(f => {
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
            geom.coordinates.forEach(poly => {
                d += generatePathString(poly);
            });
        }
        
        if (d === "") return;
        
        const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        path.setAttribute("d", d);
        path.setAttribute("fill", "#111827");
        path.setAttribute("stroke", "rgba(255,255,255,0.06)");
        path.setAttribute("stroke-width", "0.8");
        svg.appendChild(path);
    });
    
    // Draw markets overlay dots
    if (countryData.markets && countryData.markets.length > 0) {
        countryData.markets.forEach(m => {
            const cx = scaleX(m.lon);
            const cy = scaleY(m.lat);
            
            if (cx < 0 || cx > width || cy < 0 || cy > height) return;
            
            const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
            circle.setAttribute("cx", cx);
            circle.setAttribute("cy", cy);
            circle.setAttribute("r", "5");
            circle.setAttribute("class", "market-dot");
            circle.setAttribute("data-name", m.name);
            circle.style.fill = "#6366f1";
            circle.style.stroke = "white";
            circle.style.strokeWidth = "1.5px";
            circle.style.cursor = "pointer";
            circle.style.filter = "drop-shadow(0 0 4px rgba(99, 102, 241, 0.8))";
            
            circle.addEventListener("mouseover", (e) => {
                circle.setAttribute("r", "7");
                tooltip.style.display = "block";
                tooltip.innerHTML = `
                    <div style="font-weight:700; font-family:Outfit; color:#818cf8;"><i class="fa-solid fa-store mr-1"></i>Mercato: ${m.name}</div>
                    <div style="font-size:0.65rem; color:var(--text-secondary); margin-top:2px;">
                        Provincia: ${m.adm1_pcode || 'N/A'}<br>
                        Lat: ${m.lat.toFixed(3)}, Lon: ${m.lon.toFixed(3)}
                    </div>
                `;
            });
            
            circle.addEventListener("mousemove", (e) => {
                const rect = container.getBoundingClientRect();
                tooltip.style.left = (e.clientX - rect.left + 12) + "px";
                tooltip.style.top = (e.clientY - rect.top + 12) + "px";
            });
            
            circle.addEventListener("mouseout", () => {
                // Restore size if not currently selected
                const name = circle.getAttribute("data-name");
                const item = document.getElementById(`mkt-item-${name.replace(/\s+/g, '-')}`);
                const isSelected = item && item.classList.contains("selected-market-item");
                
                circle.setAttribute("r", isSelected ? "8" : "5");
                tooltip.style.display = "none";
            });
            
            circle.addEventListener("click", () => {
                highlightMarketInList(m.name);
            });
            
            svg.appendChild(circle);
        });
    }
}

function populateCountryTabMarketsList(countryData) {
    const container = document.getElementById("country-tab-markets-list");
    if (!container) return;
    container.innerHTML = "";
    
    if (!countryData.markets || countryData.markets.length === 0) {
        container.innerHTML = `
            <div style="padding:1.5rem; text-align:center; color:var(--text-muted); font-size:0.75rem;">
                Nessun mercato censito per questo paese.
            </div>
        `;
        return;
    }
    
    const sortedMarkets = [...countryData.markets].sort((a, b) => a.name.localeCompare(b.name));
    
    sortedMarkets.forEach(m => {
        const item = document.createElement("div");
        item.className = "modal-subregion-item market-list-item";
        item.id = `mkt-item-${m.name.replace(/\s+/g, '-')}`;
        item.style.cursor = "pointer";
        item.style.transition = "all 0.2s ease";
        
        item.onclick = () => {
            // Reset all marker dots sizes
            const dots = document.querySelectorAll("#country-tab-markets-container .market-dot");
            dots.forEach(d => {
                d.setAttribute("r", "5");
                d.style.fill = "#6366f1";
                d.style.filter = "drop-shadow(0 0 4px rgba(99, 102, 241, 0.8))";
            });
            
            // Find matched marker dot and expand it
            const match = Array.from(dots).find(d => d.getAttribute("data-name") === m.name);
            if (match) {
                match.setAttribute("r", "8");
                match.style.fill = "#ef4444";
                match.style.filter = "drop-shadow(0 0 8px rgba(239, 68, 68, 0.9))";
            }
            
            // Toggle active list items classes
            document.querySelectorAll(".market-list-item").forEach(el => el.classList.remove("selected-market-item"));
            item.classList.add("selected-market-item");
        };
        
        item.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center; width:100%;">
                <div>
                    <span style="font-weight:700; color:white;"><i class="fa-solid fa-store text-indigo-400 mr-2"></i>${m.name}</span>
                    <span style="font-size:0.6rem; color:var(--text-muted); margin-left:0.5rem;">${m.adm1_pcode || m.adm2_pcode || ''}</span>
                </div>
                <span style="font-size:0.65rem; color:var(--text-secondary);">Lat: ${m.lat.toFixed(2)} Lon: ${m.lon.toFixed(2)}</span>
            </div>
        `;
        container.appendChild(item);
    });
}

function highlightMarketInList(mktName) {
    const items = document.querySelectorAll(".market-list-item");
    items.forEach(el => el.classList.remove("selected-market-item"));
    
    // Find the item
    const targetItem = Array.from(items).find(el => {
        const itemSpan = el.querySelector("span");
        return itemSpan && itemSpan.innerText.includes(mktName);
    });
    
    if (targetItem) {
        // Click it to trigger marker size changes
        targetItem.click();
        targetItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}


