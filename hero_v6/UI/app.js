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
    activeMapCountry: null, // ISO3 code of the currently highlighted map country
    ipcProportional: false, // Toggle for proportional-width timeline in IPC nativi
    ipcMainProportional: false, // Toggle for proportional-width timeline in main IPC chart
    ipcPeriodFilter: 'all', // Filter for period type: 'all', 'current', 'projection'
    radarAvgModeGlobal: false, // Toggle for showing only Historical Average in global radar charts
    nativeRadarModes: {}, // Map of containerId -> boolean for native radar charts
    compareRadarSoloAvg: false, // Toggle for showing only Comparison Average in compare radar chart
    compareRadarResolution: 'quarterly' // Resolution toggle ('quarterly' or 'monthly') for robust multi-country comparison across different sampling rates
};

// Data Cache
let globalData = null;
let countryCache = {};
let rawCache = {}; // Cache for raw high-resolution datasets: rawCache[iso3][feature]

// Chart References
let heatmapChart = null;
let countryCharts = {
    ipc: null,
    acled: null,
    idp: null,
    rainfall: null,
    wfp: null,
    ndvi: null,
    gdelt: null
};
let gdeltTabCharts = {
    tone: null,
    salience: null
};
let rawCharts = {
    ipc: null,
    ipcSeasonal: null,
    acledEvents: null,
    acledFatalities: null,
    acledSeasonal: null,
    idp: null,
    idpSeasonal: null,
    rainfallReal: null,
    rainfallAnom: null,
    rainfallSeasonal: null,
    ndviVim: null,
    ndviViq: null,
    ndviSeasonal: null,
    gdeltSeasonal: null
};
let wfpMarketsCache = {}; // Cache for raw market prices: wfpMarketsCache[iso3]
let wfpMarketCharts = {
    priceIndex: null,
    inflation: null
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

let currentLightboxZoom = 1;

window.openImageLightbox = function(src, caption) {
    const modal = document.getElementById('image-lightbox-modal');
    const img = document.getElementById('lightbox-img');
    const cap = document.getElementById('lightbox-caption');
    if (modal && img) {
        img.src = src;
        currentLightboxZoom = 1;
        img.style.transform = `scale(1)`;
        if (cap) cap.innerText = caption || 'Ingrandimento Grafico';
        modal.style.display = 'flex';
    }
};

window.closeImageLightbox = function() {
    const modal = document.getElementById('image-lightbox-modal');
    if (modal) modal.style.display = 'none';
};

window.zoomLightboxImage = function(factor) {
    const img = document.getElementById('lightbox-img');
    if (!img) return;
    currentLightboxZoom = Math.min(Math.max(0.5, currentLightboxZoom * factor), 6);
    img.style.transform = `scale(${currentLightboxZoom})`;
};

window.resetLightboxZoom = function() {
    const img = document.getElementById('lightbox-img');
    if (!img) return;
    currentLightboxZoom = 1;
    img.style.transform = `scale(1)`;
};

// Global click handler per aprire in lightbox qualsiasi immagine di report
document.addEventListener('click', function(e) {
    if (e.target && e.target.tagName === 'IMG' && (e.target.closest('#panel-tsa-global') || e.target.closest('#panel-clustering') || e.target.closest('#panel-country'))) {
        if (e.target.id !== 'lightbox-img' && e.target.src && !e.target.src.endsWith('.svg')) {
            const title = e.target.alt || e.target.title || (e.target.previousElementSibling ? e.target.previousElementSibling.innerText : 'Ingrandimento Grafico');
            openImageLightbox(e.target.src, title);
        }
    }
});

// Mouse wheel zoom sul contenitore dell'immagine lightbox
document.addEventListener('wheel', function(e) {
    const modal = document.getElementById('image-lightbox-modal');
    if (modal && modal.style.display === 'flex') {
        const wrapper = document.getElementById('lightbox-img-wrapper');
        if (wrapper && wrapper.contains(e.target)) {
            e.preventDefault();
            const factor = e.deltaY < 0 ? 1.15 : 0.85;
            zoomLightboxImage(factor);
        }
    }
}, { passive: false });

// Switch between Global and Country views
function switchView(viewName) {
    state.currentView = viewName;
    
    // Stop timeline play if user navigates away
    stopTimelinePlay();
    
    // Safety check: remove stuck tooltips from svgMap on view changes
    document.querySelectorAll('.svgMap-tooltip').forEach(el => el.remove());
    
    // Toggle main header visibility & main container padding for full-bleed views
    const mainHeader = document.getElementById('main-header');
    const mainElem = document.querySelector('main');
    if (viewName === 'tsgraph' || viewName === 'clustering-evolution') {
        if (mainHeader) mainHeader.style.setProperty('display', 'none', 'important');
        if (mainElem) mainElem.style.padding = '0';
    } else {
        if (mainHeader) mainHeader.style.display = 'flex';
        if (mainElem) mainElem.style.padding = '1.5rem';
    }
    
    // Toggle active panel class
    document.querySelectorAll('.view-panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
    
    // Toggle sidebar country sub-menu visibility
    const countrySubMenu = document.getElementById('country-sub-menu');
    if (countrySubMenu) {
        if (viewName === 'country') {
            if (state.currentView === 'country') {
                countrySubMenu.style.display = countrySubMenu.style.display === 'none' ? 'flex' : 'none';
            } else {
                countrySubMenu.style.display = 'flex';
            }
        } else {
            countrySubMenu.style.display = 'none';
        }
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
        const subregSel = document.getElementById('subregion-selector-wrapper');
        if (subregSel) subregSel.style.display = 'none';
        
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
        const subregSel = document.getElementById('subregion-selector-wrapper');
        if (subregSel) subregSel.style.display = 'block';
        
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
    } else if (viewName === 'spatiotemporal') {
        document.getElementById('panel-spatiotemporal').classList.add('active');
        document.getElementById('nav-spatiotemporal').classList.add('active');
        
        document.getElementById('view-title').innerText = "Esplorazione Spazio-Temporale";
        document.getElementById('view-subtitle').innerText = "Visualizza l'andamento geografico reale e le heatmap matriciali nel tempo";
        
        document.getElementById('admin-level-toggle-wrapper').style.display = 'none';
        const toggleGroupVal = document.getElementById('chart-layout-toggle-group');
        if (toggleGroupVal) toggleGroupVal.style.display = 'none';
        document.getElementById('country-selector-wrapper').style.display = 'none';
        const subregSel = document.getElementById('subregion-selector-wrapper');
        if (subregSel) subregSel.style.display = 'none';
        
        initTimelineControls();
        renderTemporalMap();
        renderGlobalSpatiotemporalHeatmap();
    } else if (viewName === 'tsa-global') {
        document.getElementById('panel-tsa-global').classList.add('active');
        document.getElementById('nav-tsa-global').classList.add('active');
        
        document.getElementById('view-title').innerText = "TSA Clustering Globale";
        document.getElementById('view-subtitle').innerText = "Analisi di clustering e confronto globale delle serie temporali nazionali e regionali";
        
        document.getElementById('admin-level-toggle-wrapper').style.display = 'none';
        const toggleGroupVal = document.getElementById('chart-layout-toggle-group');
        if (toggleGroupVal) toggleGroupVal.style.display = 'none';
        document.getElementById('country-selector-wrapper').style.display = 'none';
        const subregSel = document.getElementById('subregion-selector-wrapper');
        if (subregSel) subregSel.style.display = 'none';
        
        loadTsaGlobalPanel();
    } else if (viewName === 'clustering') {
        document.getElementById('panel-clustering').classList.add('active');
        document.getElementById('nav-clustering').classList.add('active');
        
        document.getElementById('view-title').innerText = "Clustering & Pattern Comparati";
        document.getElementById('view-subtitle').innerText = "Confronta le strategie di clustering univariate e multivariate per le province";
        
        document.getElementById('admin-level-toggle-wrapper').style.display = 'none';
        const toggleGroupVal = document.getElementById('chart-layout-toggle-group');
        if (toggleGroupVal) toggleGroupVal.style.display = 'none';
        document.getElementById('country-selector-wrapper').style.display = 'none';
        const subregSel = document.getElementById('subregion-selector-wrapper');
        if (subregSel) subregSel.style.display = 'none';
        
        if (typeof renderClusteringView === 'function') {
            renderClusteringView();
        }
    } else if (viewName === 'tsgraph') {
        document.getElementById('panel-tsgraph').classList.add('active');
        document.getElementById('nav-tsgraph').classList.add('active');
        
        const mainHeader = document.getElementById('main-header');
        if (mainHeader) mainHeader.style.display = viewName === 'tsgraph' ? 'none' : 'flex';
        
        document.getElementById('admin-level-toggle-wrapper').style.display = 'none';
        const toggleGroupVal = document.getElementById('chart-layout-toggle-group');
        if (toggleGroupVal) toggleGroupVal.style.display = 'none';
        document.getElementById('country-selector-wrapper').style.display = 'none';
        const subregSel = document.getElementById('subregion-selector-wrapper');
        if (subregSel) subregSel.style.display = 'none';
        
        const iframe = document.getElementById('tsgraph-iframe');
        if (iframe && !iframe.getAttribute('src')) {
            iframe.src = iframe.getAttribute('data-src');
        }
    } else if (viewName === 'clustering-evolution') {
        document.getElementById('panel-clustering-evolution').classList.add('active');
        document.getElementById('nav-clustering-evolution').classList.add('active');
        
        document.getElementById('admin-level-toggle-wrapper').style.display = 'none';
        const toggleGroupVal = document.getElementById('chart-layout-toggle-group');
        if (toggleGroupVal) toggleGroupVal.style.display = 'none';
        document.getElementById('country-selector-wrapper').style.display = 'none';
        const subregSel = document.getElementById('subregion-selector-wrapper');
        if (subregSel) subregSel.style.display = 'none';
        
        const iframe = document.getElementById('clustering-evolution-iframe');
        if (iframe && !iframe.getAttribute('src')) {
            iframe.src = iframe.getAttribute('data-src');
        }
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

// Populate Country Selector dropdowns (Global and Clustering)
function populateCountrySelector() {
    if (!globalData || !globalData.countries) return;
    
    const selector = document.getElementById("country-selector");
    if (selector) {
        selector.innerHTML = '<option value="">Seleziona Paese...</option>';
        globalData.countries.forEach(c => {
            const opt = document.createElement("option");
            const flag = getFlagEmoji(ISO3_TO_ISO2[c.code]);
            opt.value = c.code;
            opt.innerText = `${flag} ${c.name} (${c.code})`;
            selector.appendChild(opt);
        });
    }

    const clusteringSel = document.getElementById("clustering-country-selector");
    if (clusteringSel) {
        clusteringSel.innerHTML = '';
        globalData.countries.forEach(c => {
            const opt = document.createElement("option");
            const flag = getFlagEmoji(ISO3_TO_ISO2[c.code]);
            opt.value = c.code;
            opt.innerText = `${flag} ${c.name} (${c.code})`;
            clusteringSel.appendChild(opt);
        });
        if (state && state.selectedCountry) clusteringSel.value = state.selectedCountry;
    }
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
    
    const labels = {
        "overall": "Tutti i Temi",
        "ipc": "Sicurezza Alimentare (IPC)",
        "acled": "Conflitti (ACLED)",
        "idp": "Sfollati (IDP)",
        "rainfall": "Precipitazioni (CHIRPS)",
        "wfp": "Prezzi Alimentari (WFP)",
        "ndvi": "Vegetazione (NDVI)",
        "gdelt": "Copertura News (GDELT)"
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
    
    // Hide market details section on country switch
    const mktDet = document.getElementById("country-market-details-section");
    if (mktDet) mktDet.style.display = "none";
    if (wfpMarketCharts.priceIndex) { wfpMarketCharts.priceIndex.destroy(); wfpMarketCharts.priceIndex = null; }
    if (wfpMarketCharts.inflation) { wfpMarketCharts.inflation.destroy(); wfpMarketCharts.inflation = null; }

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

    // Aggiornamento dinamico pulsanti download ZIP per singola pagina
    const globalBannerTitle = document.getElementById('global-country-banner-title');
    if (globalBannerTitle) {
        const countryName = (data && data.name) ? data.name : code;
        globalBannerTitle.textContent = `${countryName} (${code})`;
    }

    const pageZips = [
        { id: 'charts', file: `Grafici_Trend_${code}.zip` },
        { id: 'ipc', file: `Grafici_IPC_${code}.zip` },
        { id: 'acled', file: `Grafici_ACLED_${code}.zip` },
        { id: 'idp', file: `Grafici_IDP_${code}.zip` },
        { id: 'rainfall', file: `Grafici_Rainfall_${code}.zip` },
        { id: 'ndvi', file: `Grafici_NDVI_${code}.zip` },
        { id: 'gdelt', file: `Grafici_GDELT_${code}.zip` }
    ];

    pageZips.forEach(cfg => {
        const btn = document.getElementById(`btn-dl-zip-${cfg.id}`);
        const lbl = document.getElementById(`lbl-dl-zip-${cfg.id}`);
        if (btn && lbl) {
            btn.href = `data/page_zips/${cfg.file}`;
            btn.setAttribute('download', cfg.file);
            lbl.textContent = code;
        }
    });

    const tsaZipBtn = document.getElementById('tsa-download-all-zip-btn');
    const tsaZipLabel = document.getElementById('tsa-zip-country-label');
    if (tsaZipBtn && tsaZipLabel) {
        tsaZipBtn.href = `data/ts_reorganized/zip/Grafici_HTML_${code}.zip`;
        tsaZipBtn.setAttribute('download', `Grafici_HTML_${code}.zip`);
        tsaZipLabel.textContent = code;
    }
    const saveAllCountryLbl = document.getElementById('lbl-save-all-country-code');
    if (saveAllCountryLbl) {
        saveAllCountryLbl.textContent = code;
    }
    
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
        document.getElementById("chart-ndvi-title").innerText = "Indice Vegetazione NDVI (VIM & VIQ)";
        document.getElementById("chart-gdelt-title").innerText = "Instabilità Media (GDELT CAMEO QuadClass)";
        
        // Render Cartesian charts
        renderIpcChart(filteredTrends);
        renderAcledChart(filteredTrends);
        renderIdpChart(filteredTrends);
        renderRainfallChart(filteredTrends);
        renderWfpChart(filteredTrends);
        renderNdviChart(filteredTrends);
        renderGdeltChart(filteredTrends);
        
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
    
    // Update GDELT tab if active
    if (state.countrySubView === 'gdelt') {
        renderGdeltTab(filteredTrends);
    }
    
    // Update WFP Markets tab if active
    if (state.countrySubView === 'markets') {
        const data = countryCache[code];
        if (data) {
            fetch(`data/boundaries/${code}.json`)
                .then(res => res.ok ? res.json() : null)
                .then(geojson => {
                    drawMarketsOnlyMap("country-tab-markets-container", geojson, data);
                    populateCountryTabMarketsList(data);
                })
                .catch(err => console.error("Error loading boundaries in markets sub-view:", err));
        }
    }
    
    // Update raw tabs if active
    if (['ipc', 'acled', 'idp', 'rainfall', 'ndvi'].includes(state.countrySubView)) {
        loadAndRenderRawTab(state.selectedCountry, state.countrySubView);
    }
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

function toggleGlobalRadarMode() {
    state.radarAvgModeGlobal = !state.radarAvgModeGlobal;
    const btn = document.getElementById("btn-toggle-global-radar-mode");
    const legendContainer = document.getElementById("seasonal-common-legend-container");
    if (btn) {
        if (state.radarAvgModeGlobal) {
            btn.innerHTML = `<i class="fa-solid fa-calendar-days text-indigo-400"></i> <span>Mostra Tutti gli Anni</span>`;
            btn.className = "px-4 py-1.5 rounded-full text-xs font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 hover:bg-indigo-500/30 transition-all flex items-center gap-2 shadow-sm cursor-pointer outline-none";
            if (legendContainer) legendContainer.style.display = "none";
        } else {
            btn.innerHTML = `<i class="fa-solid fa-star text-amber-400"></i> <span>Mostra Solo Media Storica</span>`;
            btn.className = "px-4 py-1.5 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/40 hover:bg-amber-500/25 transition-all flex items-center gap-2 shadow-sm cursor-pointer outline-none";
            if (legendContainer) legendContainer.style.display = "flex";
        }
    }
    if (typeof renderRadarCharts === "function") {
        renderRadarCharts();
    }
}

function toggleNativeRadarMode(containerId) {
    state.nativeRadarModes = state.nativeRadarModes || {};
    state.nativeRadarModes[containerId] = !state.nativeRadarModes[containerId];
    const el = document.getElementById(containerId);
    if (el && el._lastRadarArgs) {
        const args = el._lastRadarArgs;
        renderNativeSeasonalRadar(args.trends, args.containerId, args.metricGetter, args.chartKey, args.mode, args.linkedChartInstance, args.linkedSeriesIdx);
    }
}

function toggleCompareRadarMode() {
    state.compareRadarSoloAvg = !state.compareRadarSoloAvg;
    const container = document.getElementById("chart-compare-radar");
    if (container && container._lastCompareRadarArgs) {
        const args = container._lastCompareRadarArgs;
        renderComparativeRadarChart(args.countriesData, args.metricKey, args.dataType);
    }
}

function toggleCompareRadarResolution() {
    state.compareRadarResolution = (state.compareRadarResolution === 'monthly') ? 'quarterly' : 'monthly';
    const container = document.getElementById("chart-compare-radar");
    if (container && container._lastCompareRadarArgs) {
        const args = container._lastCompareRadarArgs;
        renderComparativeRadarChart(args.countriesData, args.metricKey, args.dataType);
    }
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

    const ndviVim = data.ndvi_vim !== undefined && data.ndvi_vim !== null ? data.ndvi_vim.toFixed(3) : "N/A";
    const ndviViq = data.ndvi_viq !== undefined && data.ndvi_viq !== null ? data.ndvi_viq.toFixed(1) + "%" : "N/A";

    const gdeltVCoop = data.gdelt_verbal_coop_events !== undefined && data.gdelt_verbal_coop_events !== null ? Math.round(data.gdelt_verbal_coop_events) : "N/A";
    const gdeltMCoop = data.gdelt_material_coop_events !== undefined && data.gdelt_material_coop_events !== null ? Math.round(data.gdelt_material_coop_events) : "N/A";
    const gdeltVConf = data.gdelt_verbal_conflict_events !== undefined && data.gdelt_verbal_conflict_events !== null ? Math.round(data.gdelt_verbal_conflict_events) : "N/A";
    const gdeltMConf = data.gdelt_material_conflict_events !== undefined && data.gdelt_material_conflict_events !== null ? Math.round(data.gdelt_material_conflict_events) : "N/A";
    const gdeltTone = data.gdelt_material_conflict_tone !== undefined && data.gdelt_material_conflict_tone !== null ? data.gdelt_material_conflict_tone.toFixed(2) : "N/A";

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

                <!-- NDVI VEGETATION -->
                <div class="detail-section" style="background: rgba(255,255,255,0.02); border: 1px solid var(--border-color); padding: 0.85rem; border-radius: 8px;">
                    <div class="detail-section-title" style="color: #10b981; font-weight: 700; margin-bottom: 0.5rem; display: flex; align-items: center; gap: 0.4rem; font-size: 0.85rem;">
                        <i class="fa-solid fa-seedling"></i> Vegetazione (NDVI)
                    </div>
                    <div style="display: flex; flex-direction: column; gap: 0.35rem; font-size: 0.8rem;">
                        <div style="display: flex; justify-content: space-between;">
                            <span class="detail-label">NDVI VIM (Verde):</span>
                            <span class="detail-value" style="font-weight: 600;">${ndviVim}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between;">
                            <span class="detail-label">NDVI VIQ (Condizione):</span>
                            <span class="detail-value" style="font-weight: 600;">${ndviViq}</span>
                        </div>
                    </div>
                </div>

                <!-- GDELT MEDIA -->
                <div class="detail-section" style="background: rgba(255,255,255,0.02); border: 1px solid var(--border-color); padding: 0.85rem; border-radius: 8px;">
                    <div class="detail-section-title" style="color: #a855f7; font-weight: 700; margin-bottom: 0.5rem; display: flex; align-items: center; gap: 0.4rem; font-size: 0.85rem;">
                        <i class="fa-solid fa-globe"></i> Media & Instabilità (GDELT)
                    </div>
                    <div style="display: flex; flex-direction: column; gap: 0.35rem; font-size: 0.8rem;">
                        <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--text-secondary);">
                            <span>Conflitto Mat/Verb:</span>
                            <span>${gdeltMConf} / ${gdeltVConf}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--text-secondary);">
                            <span>Coop Mat/Verb:</span>
                            <span>${gdeltMCoop} / ${gdeltVCoop}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between;">
                            <span class="detail-label">Tono Conflitto Mat.:</span>
                            <span class="detail-value" style="font-weight: 600;">${gdeltTone}</span>
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
// Render Food Security (IPC) Stacked Bar Chart
function renderIpcChart(trends) {
    if (trends) {
        window.currentIpcMainTrends = trends;
    } else {
        trends = window.currentIpcMainTrends;
    }
    
    if (!trends) return;
    
    // Apply period type filtering
    let filteredTrends = trends;
    if (state.ipcPeriodFilter === 'current') {
        filteredTrends = trends.filter(t => t.period === 'current');
    } else if (state.ipcPeriodFilter === 'projection') {
        filteredTrends = trends.filter(t => t.period && t.period.toLowerCase().includes('projection'));
    }
    
    destroyChart('ipc');
    const container = document.getElementById("chart-ipc");
    container.innerHTML = "";
    
    if (!filteredTrends || filteredTrends.length === 0) {
        container.innerHTML = `<div style="height: 320px; display: flex; align-items: center; justify-content: center; color: var(--text-muted); font-family: Inter, sans-serif;">Nessun dato IPC disponibile per il filtro selezionato</div>`;
        return;
    }
    
    // Update toggle checkbox and select filter in UI
    const toggleEl = document.getElementById('ipc-main-proportional-toggle');
    if (toggleEl) {
        toggleEl.checked = !!state.ipcMainProportional;
    }
    const filterEl = document.getElementById('ipc-period-type-filter');
    if (filterEl) {
        filterEl.value = state.ipcPeriodFilter || 'all';
    }
    
    if (state.ipcMainProportional) {
        renderIpcProportionalChart(container, filteredTrends);
        return;
    }
    
    const categories = filteredTrends.map(t => t.from.substring(0, 7));
    const p1 = filteredTrends.map(t => t.phase_1_percentage !== null ? parseFloat(t.phase_1_percentage.toFixed(1)) : 0);
    const p2 = filteredTrends.map(t => t.phase_2_percentage !== null ? parseFloat(t.phase_2_percentage.toFixed(1)) : 0);
    const p3 = filteredTrends.map(t => t.phase_3_percentage !== null ? parseFloat(t.phase_3_percentage.toFixed(1)) : 0);
    const p4 = filteredTrends.map(t => t.phase_4_percentage !== null ? parseFloat(t.phase_4_percentage.toFixed(1)) : 0);
    const p5 = filteredTrends.map(t => t.phase_5_percentage !== null ? parseFloat(t.phase_5_percentage.toFixed(1)) : 0);
    
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
            id: 'chart-ipc',
            toolbar: { show: false },
            background: 'transparent',
            events: {
                dataPointSelection: function(event, chartContext, config) {
                    const dataPointIndex = config.dataPointIndex;
                    if (dataPointIndex !== undefined && dataPointIndex >= 0) {
                        openPeriodDetailModal(filteredTrends, dataPointIndex);
                    }
                }
            }
        },
        theme: { mode: 'dark' },
        plotOptions: {
            bar: {
                horizontal: false,
                columnWidth: '75%'
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
            type: 'category',
            categories: categories,
            tickAmount: Math.min(categories.length, 12),
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

// Handler for toggle of proportional width timeline in main IPC chart
function toggleIpcMainProportionalView() {
    const toggleEl = document.getElementById('ipc-main-proportional-toggle');
    if (toggleEl) {
        state.ipcMainProportional = toggleEl.checked;
        renderIpcChart();
    }
}

// Handler for period filter change in main IPC chart
function onIpcPeriodFilterChange() {
    const filterEl = document.getElementById('ipc-period-type-filter');
    if (filterEl) {
        state.ipcPeriodFilter = filterEl.value;
        renderIpcChart();
    }
}

// Custom renderer for 100% stacked proportional timeline of main IPC phases
function renderIpcProportionalChart(container, trends) {
    const CHART_HEIGHT = 265; // px - matches ApexCharts plot area within 320px total
    const TOTAL_CONTAINER = 320; // px - same as ApexCharts chart height
    const Y_AXIS_WIDTH = 65; // px - space for y-axis title + labels
    const X_AXIS_HEIGHT = 28; // px - bottom axis labels
    const LEGEND_HEIGHT = 27; // p    // Sort trends chronologically, parsing start/end consistently as UTC to prevent timezone overlaps
    const sorted = trends.filter(t => t.from && t.to)
                         .map((t, idx) => {
                             const start = new Date(t.from.substring(0, 10) + "T00:00:00Z");
                             const end = new Date(t.to.substring(0, 10) + "T23:59:59Z");
                             return { ...t, start, end, originalIndex: idx };
                         })
                         .sort((a, b) => a.start - b.start);
                         
    if (sorted.length === 0) {
        container.innerHTML = `<div style="height: ${TOTAL_CONTAINER}px; display: flex; align-items: center; justify-content: center; color: var(--text-muted); font-family: Inter, sans-serif;">Nessun dato IPC disponibile</div>`;
        return;
    }
    
    const minDate = sorted[0].start;
    // Calculate the absolute latest end date across all elements to prevent right-overflow
    let maxDate = sorted[0].end;
    sorted.forEach(t => {
        if (t.end > maxDate) {
            maxDate = t.end;
        }
    });
    const totalTime = maxDate - minDate || 1;
    
    // Generate year labels (without drawing vertical grid lines to match standard plot)
    const minYear = minDate.getUTCFullYear();
    const maxYear = maxDate.getUTCFullYear();
    
    let vGridHtml = '';
    for (let y = minYear; y <= maxYear + 1; y++) {
        const gridDate = new Date(Date.UTC(y, 0, 1));
        if (gridDate >= minDate && gridDate <= maxDate) {
            const offset = ((gridDate - minDate) / totalTime) * 100;
            vGridHtml += `<div style="position: absolute; left: ${offset}%; top: ${CHART_HEIGHT + 8}px; transform: translateX(-50%); font-size: 9px; color: #94a3b8; font-family: Inter, Helvetica, sans-serif; pointer-events: none;">${y}</div>`;
        }
    }
    
    // Dashed horizontal gridlines matching ApexCharts
    let hGridHtml = '';
    for (let pct = 0; pct <= 100; pct += 20) {
        const yPos = CHART_HEIGHT - (pct / 100) * CHART_HEIGHT;
        hGridHtml += `<div style="position: absolute; left: 0; right: 0; top: ${yPos}px; border-top: 1px dashed rgba(255,255,255,0.08); pointer-events: none;"></div>`;
    }
    
    // Generate bars
    let barsHtml = '';
    sorted.forEach((t, i) => {
        const left = ((t.start - minDate) / totalTime) * 100;
        const width = ((t.end - t.start) / totalTime) * 100;
        
        const p1 = t.phase_1_percentage ?? 0;
        const p2 = t.phase_2_percentage ?? 0;
        const p3 = t.phase_3_percentage ?? 0;
        const p4 = t.phase_4_percentage ?? 0;
        const p5 = t.phase_5_percentage ?? 0;
        const sum = p1 + p2 + p3 + p4 + p5 || 1;
        
        const pcts = [
            { val: p1, color: '#10b981' },
            { val: p2, color: '#84cc16' },
            { val: p3, color: '#eab308' },
            { val: p4, color: '#f97316' },
            { val: p5, color: '#ef4444' }
        ];
        
        // Build stacked segments with absolute positioning to grow in place from their baseline, staggered left-to-right
        let segmentsHtml = '';
        let currentBottom = 0;
        const animDelay = i * 40; // 40ms stagger delay per bar
        pcts.forEach(s => {
            const hPct = (s.val / sum) * 100;
            const label = hPct > 7 ? `<span style="font-size: 8px; font-family: Inter, Helvetica, sans-serif; color: #fff; font-weight: normal; pointer-events: none; user-select: none;">${Math.round(hPct)}%</span>` : '';
            segmentsHtml += `<div class="ipc-prop-segment" style="position: absolute; left: 0; width: 100%; bottom: ${currentBottom}%; height: ${hPct}%; background-color: ${s.color}; opacity: 0.85; border: 1.5px solid #0b0f19; box-sizing: border-box; display: flex; align-items: center; justify-content: center; min-height: 0; overflow: hidden; animation-delay: ${animDelay}ms;">${label}</div>`;
            currentBottom += hPct;
        });
        
        barsHtml += `
            <div class="ipc-prop-bar" 
                 style="position: absolute; left: ${left}%; width: ${width}%; bottom: 0; height: ${CHART_HEIGHT}px; cursor: pointer;"
                 onclick="openPeriodDetailModal(window.currentIpcMainTrends, ${t.originalIndex})"
                 data-idx="${t.originalIndex}"
            >${segmentsHtml}</div>
        `;
    });
    
    // Y-axis labels (matching ApexCharts: decimal format, 9px, color: #94a3b8)
    let yLabelsHtml = '';
    for (let pct = 0; pct <= 100; pct += 20) {
        const yPos = CHART_HEIGHT - (pct / 100) * CHART_HEIGHT;
        yLabelsHtml += `<div style="position: absolute; right: 8px; top: ${yPos}px; transform: translateY(-50%); font-size: 9px; color: #94a3b8; font-family: Inter, Helvetica, Arial, sans-serif;">${pct.toFixed(1)}</div>`;
    }
    
    // Legend (matching ApexCharts: top center, 11px Inter, colored circles, color: #e2e8f0)
    const legendItems = [
        { name: 'Fase 1: Minima', color: '#10b981' },
        { name: 'Fase 2: Stress', color: '#84cc16' },
        { name: 'Fase 3: Crisi', color: '#eab308' },
        { name: 'Fase 4: Emergenza', color: '#f97316' },
        { name: 'Fase 5: Catastrofe', color: '#ef4444' },
    ];
    let legendHtml = `<div style="display: flex; gap: 15px; justify-content: center; flex-wrap: wrap; height: ${LEGEND_HEIGHT}px; align-items: center; font-family: Inter, Helvetica, Arial, sans-serif; font-size: 11px;">`;
    legendItems.forEach(l => {
        legendHtml += `<div style="display: flex; align-items: center; gap: 6px; cursor: pointer;"><span style="display: inline-block; width: 12px; height: 12px; border-radius: 50%; background: ${l.color};"></span><span style="color: #e2e8f0;">${l.name}</span></div>`;
    });
    // Extra legend item for gaps
    legendHtml += `<div style="display: flex; align-items: center; gap: 6px; margin-left: 6px; padding-left: 10px; border-left: 1px solid rgba(255,255,255,0.1); cursor: default;"><span style="display: inline-block; width: 12px; height: 8px; background: repeating-linear-gradient(90deg, rgba(255,255,255,0.15) 0 2px, transparent 2px 5px); border-radius: 2px;"></span><span style="color: #e2e8f0;">Periodo scoperto</span></div>`;
    legendHtml += `</div>`;
 
    container.innerHTML = `
        <style>
            @keyframes ipcSegmentGrow {
                from { height: 0; }
            }
            .ipc-prop-bar {
                box-sizing: border-box;
                transition: filter 0.2s ease, box-shadow 0.2s ease;
            }
            .ipc-prop-segment {
                animation: ipcSegmentGrow 0.8s ease-in-out both;
            }
            .ipc-prop-bar:hover {
                filter: brightness(1.15);
                box-shadow: 0 0 10px rgba(99, 102, 241, 0.3);
                z-index: 10 !important;
            }
        </style>
        ${legendHtml}
        <div style="position: relative; width: 100%; height: ${TOTAL_CONTAINER - LEGEND_HEIGHT}px; font-family: Inter, Helvetica, sans-serif;">
            <!-- Tooltip -->
            <div id="ipc-main-timeline-tooltip" style="position: absolute; display: none; background: #1a1a2e; border: 1px solid rgba(255,255,255,0.1); border-radius: 4px; padding: 8px 12px; font-size: 12px; color: #e5e7eb; pointer-events: none; box-shadow: 0 2px 8px rgba(0,0,0,0.5); z-index: 100; min-width: 200px; font-family: Inter, Helvetica, sans-serif;"></div>
 
            <!-- Y-axis title (rotated, matching ApexCharts) -->
            <div style="position: absolute; left: 0; top: ${CHART_HEIGHT / 2}px; transform: rotate(-90deg) translateX(-50%); transform-origin: 0 0; font-size: 11px; color: #94a3b8; font-family: Inter, Helvetica, Arial, sans-serif; white-space: nowrap;">Percentuale Popolazione</div>
            
            <!-- Y-axis labels -->
            <div style="position: absolute; left: 20px; top: 0; width: ${Y_AXIS_WIDTH - 20}px; height: ${CHART_HEIGHT}px;">
                ${yLabelsHtml}
            </div>
            
            <!-- Plot area -->
            <!-- Plot area (bars + gridlines) -->
            <div style="position: absolute; left: ${Y_AXIS_WIDTH}px; right: 8px; top: 0; height: ${CHART_HEIGHT}px; overflow: visible;">
                <!-- Horizontal gridlines -->
                ${hGridHtml}
                <!-- Bars -->
                ${barsHtml}
            </div>
            <!-- X-axis area (year labels, below bars) -->
            <div style="position: absolute; left: ${Y_AXIS_WIDTH}px; right: 8px; top: 0; height: ${CHART_HEIGHT + X_AXIS_HEIGHT}px; pointer-events: none; overflow: visible;">
                ${vGridHtml}
            </div>
        </div>
    `;
    
    // Tooltip event listeners (matching ApexCharts shared tooltip style)
    const tooltipEl = document.getElementById("ipc-main-timeline-tooltip");
    
    container.querySelectorAll(".ipc-prop-bar").forEach(bar => {
        const idx = parseInt(bar.getAttribute("data-idx"));
        const t = trends[idx];
        
        bar.addEventListener("mouseenter", () => {
            const p1 = t.phase_1_percentage ?? 0;
            const p2 = t.phase_2_percentage ?? 0;
            const p3 = t.phase_3_percentage ?? 0;
            const p4 = t.phase_4_percentage ?? 0;
            const p5 = t.phase_5_percentage ?? 0;
            const sum = p1 + p2 + p3 + p4 + p5 || 1;
            
            const rows = [
                { name: 'Fase 1: Minima', color: '#10b981', val: p1 },
                { name: 'Fase 2: Stress', color: '#84cc16', val: p2 },
                { name: 'Fase 3: Crisi', color: '#eab308', val: p3 },
                { name: 'Fase 4: Emergenza', color: '#f97316', val: p4 },
                { name: 'Fase 5: Catastrofe', color: '#ef4444', val: p5 },
            ];
            
            let rowsHtml = rows.map(r => {
                const pct = ((r.val / sum) * 100).toFixed(1);
                return `<div style="display: flex; align-items: center; justify-content: space-between; padding: 2px 0;"><span style="display: flex; align-items: center; gap: 5px;"><span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: ${r.color};"></span>${r.name}</span><span style="font-weight: 600; margin-left: 12px;">${pct}%</span></div>`;
            }).join('');
            
            tooltipEl.innerHTML = `
                <div style="font-size: 11px; color: #9ca3af; margin-bottom: 6px; padding-bottom: 4px; border-bottom: 1px solid rgba(255,255,255,0.08);">
                    ${t.from.substring(0, 10)} → ${t.to.substring(0, 10)} (${t.period === 'current' ? 'Corrente' : 'Proiezione'})
                </div>
                ${rowsHtml}
            `;
            tooltipEl.style.display = "block";
        });
        
        bar.addEventListener("mousemove", (e) => {
            const rect = container.getBoundingClientRect();
            let leftPos = e.clientX - rect.left + 15;
            let topPos = e.clientY - rect.top - 10;
            
            if (leftPos + 230 > rect.width) leftPos = e.clientX - rect.left - 240;
            if (topPos < 0) topPos = 10;
            
            tooltipEl.style.left = leftPos + "px";
            tooltipEl.style.top = topPos + "px";
        });
        
        bar.addEventListener("mouseleave", () => {
            tooltipEl.style.display = "none";
        });
    });
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
    
    const eventsData = [];
    const fatalitiesData = [];
    
    trends.forEach(t => {
        const ts = new Date(t.from).getTime();
        if (t.acled_total_events !== null) {
            eventsData.push({ x: ts, y: Math.round(t.acled_total_events) });
        }
        if (t.acled_total_fatalities !== null) {
            fatalitiesData.push({ x: ts, y: Math.round(t.acled_total_fatalities) });
        }
    });
    
    const options = {
        series: [
            { name: 'Eventi Conflitto', type: 'line', data: eventsData, color: '#f59e0b' },
            { name: 'Vittime (Fatalities)', type: 'line', data: fatalitiesData, color: '#ef4444' }
        ],
        chart: {
            height: 320,
            type: 'line',
            group: 'hero-v6-country-linear',
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
            type: 'datetime',
            crosshairs: { show: true },
            tooltip: { enabled: false },
            labels: {
                datetimeUTC: false,
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
            intersect: false,
            x: { format: 'yyyy-MM-dd' }
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
    
    const idpData = [];
    trends.forEach(t => {
        if (t.idp_population !== null) {
            idpData.push({
                x: new Date(t.from).getTime(),
                y: t.idp_population
            });
        }
    });
    
    const options = {
        series: [{
            name: 'Popolazione IDP',
            data: idpData
        }],
        chart: {
            type: 'line',
            height: 320,
            group: 'hero-v6-country-linear',
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
            type: 'datetime',
            crosshairs: { show: true },
            tooltip: { enabled: false },
            labels: {
                datetimeUTC: false,
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
            intersect: false,
            x: { format: 'yyyy-MM-dd' }
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
    
    const rainData = [];
    const anomalyData = [];
    trends.forEach(t => {
        const ts = new Date(t.from).getTime();
        if (t.rain_1m !== null) {
            rainData.push({ x: ts, y: parseFloat(t.rain_1m.toFixed(1)) });
        }
        if (t.rain_anomaly_1m !== null) {
            anomalyData.push({ x: ts, y: parseFloat(t.rain_anomaly_1m.toFixed(1)) });
        }
    });
    
    const options = {
        series: [
            { name: 'Precipitazioni (mm)', type: 'line', data: rainData, color: '#3b82f6' },
            { name: 'Anomalia (mm)', type: 'line', data: anomalyData, color: '#a855f7' }
        ],
        chart: {
            height: 320,
            type: 'line',
            group: 'hero-v6-country-linear',
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
            type: 'datetime',
            crosshairs: { show: true },
            tooltip: { enabled: false },
            labels: {
                datetimeUTC: false,
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
            intersect: false,
            x: { format: 'yyyy-MM-dd' }
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
    
    const priceData = [];
    const inflationData = [];
    trends.forEach(t => {
        const ts = new Date(t.from).getTime();
        if (t.wfp_price !== null) {
            priceData.push({ x: ts, y: parseFloat(t.wfp_price.toFixed(2)) });
        }
        if (t.wfp_inflation !== null) {
            inflationData.push({ x: ts, y: parseFloat((t.wfp_inflation * 100).toFixed(1)) });
        }
    });
    
    const options = {
        series: [
            { name: 'Indice dei Prezzi', type: 'line', data: priceData, color: '#818cf8' },
            { name: 'Inflazione Alimentare (%)', type: 'line', data: inflationData, color: '#f97316' }
        ],
        chart: {
            height: 320,
            type: 'line',
            group: 'hero-v6-country-linear',
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
            type: 'datetime',
            crosshairs: { show: true },
            tooltip: { enabled: false },
            labels: {
                datetimeUTC: false,
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
            intersect: false,
            x: { format: 'yyyy-MM-dd' }
        },
        legend: {
            position: 'top',
            fontFamily: 'Inter'
        }
    };
    
    countryCharts.wfp = new ApexCharts(container, options);
    countryCharts.wfp.render();
}

// Render NDVI Vegetation Signal
function renderNdviChart(trends) {
    destroyChart('ndvi');
    const container = document.getElementById("chart-ndvi");
    if (!container) return;
    container.innerHTML = "";
    
    const hasData = trends.some(t => t.ndvi_vim !== null && t.ndvi_vim !== undefined);
    if (!trends || trends.length === 0 || !hasData) {
        container.innerHTML = `<div style="height: 320px; display: flex; align-items: center; justify-content: center; color: var(--text-muted); font-size: 0.85rem;">Nessun dato NDVI (Vegetazione) disponibile</div>`;
        return;
    }
    
    const vimData = [];
    const viqData = [];
    trends.forEach(t => {
        const ts = new Date(t.from).getTime();
        if (t.ndvi_vim !== null && t.ndvi_vim !== undefined) {
            vimData.push({ x: ts, y: parseFloat(t.ndvi_vim.toFixed(3)) });
        }
        if (t.ndvi_viq !== null && t.ndvi_viq !== undefined) {
            viqData.push({ x: ts, y: parseFloat(t.ndvi_viq.toFixed(1)) });
        }
    });
    
    const options = {
        series: [
            { name: 'NDVI VIM (Verde)', type: 'line', data: vimData, color: '#10b981' },
            { name: 'NDVI VIQ (Condizione %)', type: 'line', data: viqData, color: '#fbbf24' }
        ],
        chart: {
            height: 320,
            type: 'line',
            group: 'hero-v6-country-linear',
            id: 'chart-ndvi',
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
            hover: { size: 7 }
        },
        xaxis: {
            type: 'datetime',
            crosshairs: { show: true },
            tooltip: { enabled: false },
            labels: {
                datetimeUTC: false,
                style: { fontSize: '10px' }
            }
        },
        yaxis: [
            {
                title: { text: 'NDVI VIM' },
                labels: { formatter: val => (val !== null && val !== undefined) ? val.toFixed(3) : "" }
            },
            {
                opposite: true,
                title: { text: 'NDVI VIQ (%)' },
                labels: { formatter: val => (val !== null && val !== undefined) ? val.toFixed(1) + "%" : "" }
            }
        ],
        tooltip: {
            shared: true,
            intersect: false,
            x: { format: 'yyyy-MM-dd' }
        },
        legend: { position: 'top', fontFamily: 'Inter', fontSize: '11px' }
    };
    
    countryCharts.ndvi = new ApexCharts(container, options);
    countryCharts.ndvi.render();
}

// Render GDELT Media Instability
function renderGdeltChart(trends) {
    destroyChart('gdelt');
    const container = document.getElementById("chart-gdelt");
    if (!container) return;
    container.innerHTML = "";
    
    const hasData = trends.some(t => t.gdelt_material_conflict_events !== null && t.gdelt_material_conflict_events !== undefined);
    if (!trends || trends.length === 0 || !hasData) {
        container.innerHTML = `<div style="height: 320px; display: flex; align-items: center; justify-content: center; color: var(--text-muted); font-size: 0.85rem;">Nessun dato GDELT (Instabilità Mediatica) disponibile per questa selezione</div>`;
        return;
    }
    
    const vCoopData = [];
    const mCoopData = [];
    const vConfData = [];
    const mConfData = [];
    const toneData = [];
    
    trends.forEach(t => {
        const ts = new Date(t.from).getTime();
        vCoopData.push({ x: ts, y: (t.gdelt_verbal_coop_events !== null && t.gdelt_verbal_coop_events !== undefined) ? Math.round(t.gdelt_verbal_coop_events) : 0 });
        mCoopData.push({ x: ts, y: (t.gdelt_material_coop_events !== null && t.gdelt_material_coop_events !== undefined) ? Math.round(t.gdelt_material_coop_events) : 0 });
        vConfData.push({ x: ts, y: (t.gdelt_verbal_conflict_events !== null && t.gdelt_verbal_conflict_events !== undefined) ? Math.round(t.gdelt_verbal_conflict_events) : 0 });
        mConfData.push({ x: ts, y: (t.gdelt_material_conflict_events !== null && t.gdelt_material_conflict_events !== undefined) ? Math.round(t.gdelt_material_conflict_events) : 0 });
        toneData.push({ x: ts, y: (t.gdelt_material_conflict_tone !== null && t.gdelt_material_conflict_tone !== undefined) ? parseFloat(t.gdelt_material_conflict_tone.toFixed(2)) : null });
    });
    
    const gdeltViewMode = (state.gdeltViewModes && state.gdeltViewModes['chart-gdelt']) || 'events';
    
    let gdeltSeries = [
        { name: 'Coop. Verbale (Eventi)', type: 'column', data: vCoopData, color: '#34d399' },
        { name: 'Coop. Materiale (Eventi)', type: 'column', data: mCoopData, color: '#60a5fa' },
        { name: 'Conflitto Verbale (Eventi)', type: 'column', data: vConfData, color: '#fbbf24' },
        { name: 'Conflitto Materiale (Eventi)', type: 'column', data: mConfData, color: '#f87171' },
        { name: 'Tono Conflitto Materiale', type: 'line', data: toneData, color: '#a855f7' }
    ];
    let gdeltYAxis = [
        {
            title: { text: 'Numero di Eventi' },
            labels: { formatter: val => (val !== null && val !== undefined) ? formatNumber(Math.round(val)) : "" }
        },
        {
            opposite: true,
            title: { text: 'Tono Medio (-10 a +10)' },
            labels: { formatter: val => (val !== null && val !== undefined) ? val.toFixed(1) : "" }
        }
    ];
    
    if (gdeltViewMode === 'events') {
        gdeltSeries = gdeltSeries.slice(0, 4);
        gdeltYAxis = [gdeltYAxis[0]];
    } else if (gdeltViewMode === 'tone') {
        gdeltSeries = [gdeltSeries[4]];
        gdeltYAxis = [{ ...gdeltYAxis[1], opposite: false }];
    }
    
    const options = {
        series: gdeltSeries,
        chart: {
            height: 320,
            type: 'line',
            stacked: true,
            group: 'hero-v6-country-linear',
            id: 'chart-gdelt',
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
            width: gdeltViewMode === 'events' ? [0, 0, 0, 0] : (gdeltViewMode === 'tone' ? [3] : [0, 0, 0, 0, 3]),
            curve: 'smooth',
            connectNulls: true
        },
        markers: {
            size: gdeltViewMode === 'events' ? [0, 0, 0, 0] : (gdeltViewMode === 'tone' ? [5] : [0, 0, 0, 0, 5]),
            hover: { size: 7 }
        },
        plotOptions: {
            bar: {
                columnWidth: '55%',
                opacity: 0.85
            }
        },
        xaxis: {
            type: 'datetime',
            crosshairs: { show: true },
            tooltip: { enabled: false },
            labels: {
                datetimeUTC: false,
                style: { fontSize: '10px' }
            }
        },
        yaxis: gdeltYAxis,
        tooltip: {
            shared: true,
            intersect: false,
            x: { format: 'yyyy-MM-dd' }
        },
        legend: { position: 'top', fontFamily: 'Inter', fontSize: '11px' }
    };
    
    countryCharts.gdelt = new ApexCharts(container, options);
    countryCharts.gdelt.render();
}

// ── CIRCULAR/RADAR CHARTS BUILDER (Seasonal Analysis) ──

// Synchronized hover highlights for seasonal radar charts
function highlightMarkerInAllSeasonalCharts(qIndex) {
    const chartIds = [
        'chart-ipc-seasonal', 'chart-acled-events-seasonal', 'chart-acled-fatalities-seasonal', 
        'chart-idp-seasonal', 'chart-rainfall-rain-seasonal', 'chart-rainfall-anomaly-seasonal', 
        'chart-wfp-price-seasonal', 'chart-wfp-inflation-seasonal',
        'chart-ndvi-vim-seasonal', 'chart-ndvi-viq-seasonal',
        'chart-gdelt-events-seasonal', 'chart-gdelt-tone-seasonal',
        'chart-raw-ipc-pop-seasonal', 'chart-raw-ipc-pct-seasonal',
        'chart-raw-acled-events-seasonal', 'chart-raw-acled-fatalities-seasonal',
        'chart-raw-idp-seasonal', 'chart-raw-rainfall-rain-seasonal', 'chart-raw-rainfall-anomaly-seasonal',
        'chart-raw-ndvi-vim-seasonal', 'chart-raw-ndvi-viq-seasonal',
        'chart-raw-gdelt-events-seasonal', 'chart-raw-gdelt-tone-seasonal'
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
                marker.style.filter = 'drop-shadow(0 0 6px rgba(255, 255, 255, 0.9))';
            } else {
                // Reset
                marker.setAttribute('r', '4');
                marker.style.stroke = '';
                marker.style.strokeWidth = '';
                marker.style.filter = '';
            }
        });
    });
}

function clearHighlightInAllSeasonalCharts() {
    const chartIds = [
        'chart-ipc-seasonal', 'chart-acled-events-seasonal', 'chart-acled-fatalities-seasonal', 
        'chart-idp-seasonal', 'chart-rainfall-rain-seasonal', 'chart-rainfall-anomaly-seasonal', 
        'chart-wfp-price-seasonal', 'chart-wfp-inflation-seasonal',
        'chart-ndvi-vim-seasonal', 'chart-ndvi-viq-seasonal',
        'chart-gdelt-events-seasonal', 'chart-gdelt-tone-seasonal',
        'chart-raw-ipc-pop-seasonal', 'chart-raw-ipc-pct-seasonal',
        'chart-raw-acled-events-seasonal', 'chart-raw-acled-fatalities-seasonal',
        'chart-raw-idp-seasonal', 'chart-raw-rainfall-rain-seasonal', 'chart-raw-rainfall-anomaly-seasonal',
        'chart-raw-ndvi-vim-seasonal', 'chart-raw-ndvi-viq-seasonal',
        'chart-raw-gdelt-events-seasonal', 'chart-raw-gdelt-tone-seasonal'
    ];
    chartIds.forEach(id => {
        const container = document.getElementById(id);
        if (!container) return;
        
        const markers = container.querySelectorAll('.apexcharts-marker');
        markers.forEach(marker => {
            marker.setAttribute('r', '4');
            marker.style.stroke = '';
            marker.style.strokeWidth = '';
            marker.style.filter = '';
        });
    });
}

// Calculate and render seasonal diagrams using synchronized radar (quadrilateral) charts with gradients
function renderRadarCharts(trends) {
    if (!trends || trends.length === 0) {
        const keys = [
            'ipc-seasonal', 'acled-events-seasonal', 'acled-fatalities-seasonal', 
            'idp-seasonal', 'rainfall-rain-seasonal', 'rainfall-anomaly-seasonal', 
            'wfp-price-seasonal', 'wfp-inflation-seasonal',
            'ndvi-vim-seasonal', 'ndvi-viq-seasonal',
            'gdelt-events-seasonal', 'gdelt-tone-seasonal'
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
    
    const isSoloMedia = !!state.radarAvgModeGlobal;
    
    // Programmatic year color gradient (cool blue to warm orange/red)
    const yearColors = years.map((y, idx) => {
        const hue = 220 - (idx / (years.length - 1 || 1)) * 205;
        return `hsl(${hue}, 85%, 60%)`;
    });
    
    // Populate the common year legend
    const commonLegend = document.getElementById("seasonal-common-legend");
    if (commonLegend) {
        commonLegend.innerHTML = "";
        years.forEach((year, idx) => {
            const color = yearColors[idx];
            const pill = document.createElement("button");
            pill.id = `seasonal-legend-pill-${year}`;
            pill.style.cssText = `
                background: rgba(255, 255, 255, 0.04);
                border: 1px solid rgba(255, 255, 255, 0.08);
                color: #e2e8f0;
                padding: 0.35rem 0.75rem;
                border-radius: 20px;
                font-size: 0.75rem;
                font-weight: 600;
                cursor: pointer;
                display: inline-flex;
                align-items: center;
                gap: 0.4rem;
                transition: all 0.2s ease;
                outline: none;
            `;
            pill.innerHTML = `<span style="width: 8px; height: 8px; border-radius: 50%; background: ${color}; display: inline-block;"></span> ${year}`;
            pill.onclick = () => toggleSeasonalYear(year);
            commonLegend.appendChild(pill);
        });
    }
    
    function getAvg(arr, key) {
        const vals = arr.map(x => x[key]).filter(v => v !== null && v !== undefined);
        if (vals.length === 0) return null;
        return vals.reduce((a, b) => a + b, 0) / vals.length;
    }
    
    function buildSeries(metricGetter) {
        const sList = years.map(year => {
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
        if (isSoloMedia) {
            const avgData = [0, 1, 2, 3].map(q => {
                const validVals = sList.map(s => s.data[q]).filter(v => v !== null && v !== undefined && !isNaN(v));
                return validVals.length > 0 ? parseFloat((validVals.reduce((a, b) => a + b, 0) / validVals.length).toFixed(2)) : null;
            });
            return [{
                name: '⭐ Media Storica',
                data: avgData
            }];
        }
        return sList;
    }

    const seasonalCommonOptions = {
        colors: isSoloMedia ? ['#fbbf24'] : yearColors,
        stroke: {
            width: isSoloMedia ? 3 : 2,
            spanNulls: true
        },
        fill: {
            type: 'solid',
            opacity: 0,
            colors: Array(35).fill('transparent')
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
                        if (year === '⭐ Media Storica' || !String(year).match(/^\d{4}/)) return;
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
                        if (year === '⭐ Media Storica' || !String(year).match(/^\d{4}/)) return;
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
                    toggleSeasonalYear(seriesName);
                },
                mouseMove: function(event, chartContext, config) {
                    const qIndex = config.dataPointIndex;
                    if (qIndex !== undefined && qIndex !== -1) {
                        setTimeout(() => highlightMarkerInAllSeasonalCharts(qIndex), 0);
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
            show: false
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
 
    // 9. NDVI Vim
    const ndviVimSeries = buildSeries(qArr => getAvg(qArr, 'ndvi_vim'));
    
    // 10. NDVI Viq
    const ndviViqSeries = buildSeries(qArr => getAvg(qArr, 'ndvi_viq'));
    
    // 11. GDELT Events
    const gdeltEventsSeries = buildSeries(qArr => getAvg(qArr, 'gdelt_material_conflict_events'));
    
    // 12. GDELT Tone
    const gdeltToneSeries = buildSeries(qArr => getAvg(qArr, 'gdelt_material_conflict_tone'));
 
    const chartsToRender = [
        { key: 'ipc_seasonal', containerId: 'chart-ipc-seasonal', series: ipcSeries, height: 300 },
        { key: 'acled_events_seasonal', containerId: 'chart-acled-events-seasonal', series: acledEventsSeries, height: 300 },
        { key: 'acled_fatalities_seasonal', containerId: 'chart-acled-fatalities-seasonal', series: acledFatalitiesSeries, height: 300 },
        { key: 'idp_seasonal', containerId: 'chart-idp-seasonal', series: idpSeries, height: 300 },
        { key: 'rainfall_rain_seasonal', containerId: 'chart-rainfall-rain-seasonal', series: rainSeries, height: 300 },
        { key: 'rainfall_anomaly_seasonal', containerId: 'chart-rainfall-anomaly-seasonal', series: rainAnomalySeries, height: 300 },
        { key: 'wfp_price_seasonal', containerId: 'chart-wfp-price-seasonal', series: wfpPriceSeries, height: 300 },
        { key: 'wfp_inflation_seasonal', containerId: 'chart-wfp-inflation-seasonal', series: wfpInflationSeries, height: 300 },
        { key: 'ndvi_vim_seasonal', containerId: 'chart-ndvi-vim-seasonal', series: ndviVimSeries, height: 300 },
        { key: 'ndvi_viq_seasonal', containerId: 'chart-ndvi-viq-seasonal', series: ndviViqSeries, height: 300 },
        { key: 'gdelt_events_seasonal', containerId: 'chart-gdelt-events-seasonal', series: gdeltEventsSeries, height: 300 },
        { key: 'gdelt_tone_seasonal', containerId: 'chart-gdelt-tone-seasonal', series: gdeltToneSeries, height: 300 }
    ];
 
    chartsToRender.forEach(c => {
        destroyChart(c.key);
        const container = document.getElementById(c.containerId);
        if (container) {
            container.innerHTML = "";
            const hasData = c.series.some(s => s.data.some(d => d !== null));
            if (!hasData) {
                container.innerHTML = `<div style="height: ${c.height}px; display: flex; align-items: center; justify-content: center; color: var(--text-muted); font-size: 0.8rem;">Nessun dato disponibile</div>`;
                return;
            }
            const options = {
                ...seasonalCommonOptions,
                colors: colors,
                series: c.series,
                chart: {
                    ...seasonalCommonOptions.chart,
                    id: c.containerId,
                    height: c.height
                }
            };
            countryCharts[c.key] = new ApexCharts(container, options);
            countryCharts[c.key].render();
        }
    });
}

// Global helper to toggle seasonal series on all charts simultaneously
function toggleSeasonalYear(year) {
    const chartIds = [
        'chart-ipc-seasonal', 'chart-acled-events-seasonal', 'chart-acled-fatalities-seasonal', 
        'chart-idp-seasonal', 'chart-rainfall-rain-seasonal', 'chart-rainfall-anomaly-seasonal', 
        'chart-wfp-price-seasonal', 'chart-wfp-inflation-seasonal',
        'chart-ndvi-vim-seasonal', 'chart-ndvi-viq-seasonal',
        'chart-gdelt-events-seasonal', 'chart-gdelt-tone-seasonal'
    ];
    
    chartIds.forEach(id => {
        const key = id.replace('chart-', '').replace(/-/g, '_');
        if (countryCharts[key]) {
            countryCharts[key].toggleSeries(year);
        }
    });
    
    const pill = document.getElementById(`seasonal-legend-pill-${year}`);
    if (pill) {
        pill.classList.toggle('inactive');
        if (pill.classList.contains('inactive')) {
            pill.style.opacity = '0.35';
            pill.style.background = 'transparent';
            pill.style.borderColor = 'rgba(255,255,255,0.04)';
        } else {
            pill.style.opacity = '1';
            pill.style.background = 'rgba(255, 255, 255, 0.04)';
            pill.style.borderColor = 'rgba(255, 255, 255, 0.08)';
        }
    }
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

    const ndviVim = data.ndvi_vim !== null && data.ndvi_vim !== undefined ? data.ndvi_vim.toFixed(3) : "N/A";
    const ndviViq = data.ndvi_viq !== null && data.ndvi_viq !== undefined ? data.ndvi_viq.toFixed(1) + "%" : "N/A";

    const gdeltMConf = data.gdelt_material_conflict_events !== null && data.gdelt_material_conflict_events !== undefined ? Math.round(data.gdelt_material_conflict_events) : "N/A";
    const gdeltTone = data.gdelt_material_conflict_tone !== null && data.gdelt_material_conflict_tone !== undefined ? data.gdelt_material_conflict_tone.toFixed(2) : "N/A";

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

        <!-- NDVI VEGETATION -->
        <div class="detail-section">
            <div class="detail-section-title" style="color: #10b981;">
                <i class="fa-solid fa-seedling"></i> Vegetazione NDVI (Media)
            </div>
            <div class="detail-row">
                <span class="detail-label">Media NDVI VIM:</span>
                <span class="detail-value">${ndviVim}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Media NDVI VIQ:</span>
                <span class="detail-value">${ndviViq}</span>
            </div>
        </div>

        <!-- GDELT MEDIA -->
        <div class="detail-section">
            <div class="detail-section-title" style="color: #a855f7;">
                <i class="fa-solid fa-globe"></i> Instabilità GDELT (Media)
            </div>
            <div class="detail-row">
                <span class="detail-label">Media Conflitti Mat.:</span>
                <span class="detail-value">${gdeltMConf}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Tono Conflitti Mat.:</span>
                <span class="detail-value">${gdeltTone}</span>
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
        tbody.innerHTML = `<tr><td colspan="13" style="text-align: center; padding: 2rem; color: var(--text-muted);">Nessun dato storico disponibile</td></tr>`;
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
        const ndviVim = t.ndvi_vim !== null && t.ndvi_vim !== undefined ? t.ndvi_vim.toFixed(3) : '-';
        const ndviViq = t.ndvi_viq !== null && t.ndvi_viq !== undefined ? `${t.ndvi_viq.toFixed(1)}%` : '-';
        const gdeltMConf = t.gdelt_material_conflict_events !== null && t.gdelt_material_conflict_events !== undefined ? Math.round(t.gdelt_material_conflict_events) : '-';
        const gdeltTone = t.gdelt_material_conflict_tone !== null && t.gdelt_material_conflict_tone !== undefined ? t.gdelt_material_conflict_tone.toFixed(2) : '-';
        
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
            <td style="text-align: right; color: #10b981; padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05);">${ndviVim}</td>
            <td style="text-align: right; color: #fbbf24; padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05);">${ndviViq}</td>
            <td style="text-align: right; color: #f87171; padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05);">${gdeltMConf}</td>
            <td style="text-align: right; color: #a855f7; padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05);">${gdeltTone}</td>
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
    if (metricKey === 'ndvi') {
        return t.ndvi_vim !== undefined && t.ndvi_vim !== null ? t.ndvi_vim : null;
    }
    if (metricKey === 'gdelt') {
        return t.gdelt_material_conflict_events !== undefined && t.gdelt_material_conflict_events !== null ? t.gdelt_material_conflict_events : null;
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
    if (containerId === "sidebar-country-map-container" || containerId === "country-tab-map-container") {
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
    const metricKey = ((containerId === "sidebar-country-map-container" || containerId === "country-tab-map-container") && metricSelector) 
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
                        t.wfp_price !== undefined && t.wfp_price !== null,
                        t.ndvi_vim !== undefined && t.ndvi_vim !== null,
                        t.gdelt_verbal_coop_events !== undefined && t.gdelt_verbal_coop_events !== null
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
    else if (metricKey === 'ndvi') colorMax = '#10b981'; // Emerald
    else if (metricKey === 'gdelt') colorMax = '#a855f7'; // Purple
    
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
    const showMarkets = ((containerId === "sidebar-country-map-container" || containerId === "country-tab-map-container") && toggleMarkets)
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
        drawSubregionMap("country-tab-map-container", activeSubregionMapData.geojson, activeSubregionMapData.countryData);
    }
}

function onMapColorMetricChange() {
    if (activeSubregionMapData) {
        drawSubregionMap("country-tab-map-container", activeSubregionMapData.geojson, activeSubregionMapData.countryData);
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

const compareRawCache = {}; // Cache for raw comparison data: { country_feature: data }

async function getOrFetchCompareRaw(code, feature) {
    const cacheKey = `${code}_${feature}`;
    if (compareRawCache[cacheKey]) return compareRawCache[cacheKey];
    
    const res = await fetch(`data/countries/${code}_raw_${feature}.json?t=${Date.now()}`);
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    const data = await res.json();
    compareRawCache[cacheKey] = data;
    return data;
}

function getRawMetricVal(t, metricKey) {
    if (metricKey === 'ipc') return t.phase_3plus_percentage;
    if (metricKey === 'acled') return t.total_events;
    if (metricKey === 'idp') return t.population;
    if (metricKey === 'rainfall') return t.rain_1m;
    if (metricKey === 'ndvi') return t.vim;
    return null;
}

async function onCompareCountriesChange() {
    const metricKey = document.getElementById("compare-metric").value;
    let dataType = document.getElementById("compare-data-type") ? document.getElementById("compare-data-type").value : 'aggregated';
    
    if (!state.compareCountries || state.compareCountries.length === 0) {
        document.getElementById("chart-compare").innerHTML = `
            <div style="height: 380px; display: flex; align-items: center; justify-content: center; color: var(--text-muted);">
                Aggiungi almeno un paese per visualizzare il confronto
            </div>
        `;
        const radarEl = document.getElementById("chart-compare-radar");
        if (radarEl) {
            radarEl.innerHTML = `
                <div style="height: 380px; display: flex; align-items: center; justify-content: center; color: var(--text-muted);">
                    Aggiungi almeno un paese per visualizzare il confronto stagionale
                </div>
            `;
        }
        document.getElementById("compare-details-grid").innerHTML = "";
        return;
    }
    
    // Warning banner check
    const warningEl = document.getElementById("compare-raw-warning");
    if (dataType === 'raw' && ['wfp', 'gdelt'].includes(metricKey)) {
        if (warningEl) {
            warningEl.style.display = "block";
            warningEl.innerText = "Nota: I dati originali (Raw) non sono disponibili per questo indicatore. Viene mostrato il dato aggregato.";
        }
        dataType = 'aggregated';
    } else {
        if (warningEl) warningEl.style.display = "none";
    }
    
    try {
        let countriesData = [];
        if (dataType === 'raw') {
            const promises = state.compareCountries.map(code => getOrFetchCompareRaw(code, metricKey));
            countriesData = await Promise.all(promises);
        } else {
            const promises = state.compareCountries.map(code => getOrFetchCountry(code));
            countriesData = await Promise.all(promises);
        }
        
        renderComparativeChart(countriesData, metricKey, dataType);
        renderComparativeRadarChart(countriesData, metricKey, dataType);
        
        // Always render comparative details using the main aggregated country data
        const aggPromises = state.compareCountries.map(code => getOrFetchCountry(code));
        const aggCountriesData = await Promise.all(aggPromises);
        renderComparativeDetails(aggCountriesData);
        
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

function renderComparativeChart(countriesData, metricKey, dataType = 'aggregated') {
    // Pre-defined color palette for countries in comparison (Okabe-Ito colorblind friendly)
    const colors = ['#56B4E9', '#E69F00', '#009E73', '#CC79A7', '#D55E00', '#0072B2', '#F0E442', '#94A3B8'];
    
    const series = countriesData.map((data, idx) => {
        let trends = [];
        let countryName = "";
        
        if (dataType === 'raw') {
            trends = data.national || [];
            const cObj = globalData.countries.find(c => c.code === state.compareCountries[idx]);
            countryName = cObj ? cObj.name : state.compareCountries[idx];
        } else {
            trends = data.trends.adm1.length > 0 ? data.trends.adm1 : data.trends.adm2;
            countryName = data.name;
        }
        
        const points = [];
        trends.forEach(t => {
            let val = null;
            if (dataType === 'raw') {
                val = getRawMetricVal(t, metricKey);
            } else {
                val = getMetricValFromTrend(t, metricKey);
            }
            
            if (val !== undefined && val !== null) {
                const dateStr = t.from || t.date;
                if (dateStr) {
                    points.push({
                        x: new Date(dateStr).getTime(),
                        y: parseFloat(val.toFixed(2))
                    });
                }
            }
        });
        
        // Sort chronologically
        points.sort((a, b) => a.x - b.x);
        
        return {
            name: countryName,
            data: points,
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
            curve: 'smooth',
            connectNulls: true
        },
        xaxis: {
            type: 'datetime',
            labels: {
                datetimeUTC: false,
                style: { fontSize: '10px' }
            }
        },
        yaxis: {
            title: { text: getMetricLabel(metricKey) + (dataType === 'raw' ? ' (Dato Originale)' : ' (Dato Aggregato)') },
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
            intersect: false,
            x: {
                format: 'yyyy-MM-dd'
            }
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

let compareRadarChart = null;

function renderComparativeRadarChart(countriesData, metricKey, dataType = 'aggregated') {
    const container = document.getElementById("chart-compare-radar");
    if (!container) return;
    
    const countryColors = ['#56B4E9', '#E69F00', '#009E73', '#CC79A7', '#D55E00', '#0072B2', '#F0E442', '#94A3B8'];
    const isQuarterly = (state.compareRadarResolution || 'quarterly') === 'quarterly';
    const categories = isQuarterly 
        ? ['Q1 (Gen-Mar)', 'Q2 (Apr-Giu)', 'Q3 (Lug-Set)', 'Q4 (Ott-Dic)'] 
        : ['Gen', 'Feb', 'Mar', 'Apr', 'Mag', 'Giu', 'Lug', 'Ago', 'Set', 'Ott', 'Nov', 'Dic'];
    const numCats = categories.length;
    
    const countrySeries = countriesData.map((data, idx) => {
        let trends = [];
        let countryName = "";
        if (dataType === 'raw') {
            trends = data.national || [];
            const cObj = globalData.countries.find(c => c.code === state.compareCountries[idx]);
            countryName = cObj ? cObj.name : state.compareCountries[idx];
        } else {
            trends = data.trends.adm1.length > 0 ? data.trends.adm1 : data.trends.adm2;
            countryName = data.name;
        }
        
        const buckets = Array.from({ length: numCats }, () => []);
        trends.forEach(t => {
            let val = null;
            if (dataType === 'raw') {
                val = getRawMetricVal(t, metricKey);
            } else {
                val = getMetricValFromTrend(t, metricKey);
            }
            if (val !== undefined && val !== null && !isNaN(val)) {
                const dateFromStr = t.from || t.date;
                const dateToStr = t.to || t.from || t.date;
                if (dateFromStr && dateFromStr.length >= 7) {
                    const startMonth = parseInt(dateFromStr.substring(5, 7), 10);
                    const endMonth = (dateToStr && dateToStr.length >= 7) ? parseInt(dateToStr.substring(5, 7), 10) : startMonth;
                    if (!isNaN(startMonth) && startMonth >= 1 && startMonth <= 12) {
                        let sM = startMonth;
                        let eM = (!isNaN(endMonth) && endMonth >= 1 && endMonth <= 12 && endMonth >= startMonth) ? endMonth : startMonth;
                        
                        // Map across all covered months/quarters to handle different sampling rates and multi-month periods
                        const coveredCatIndices = new Set();
                        for (let m = sM; m <= eM; m++) {
                            const catIdx = isQuarterly ? Math.floor((m - 1) / 3) : (m - 1);
                            coveredCatIndices.add(catIdx);
                        }
                        coveredCatIndices.forEach(catIdx => {
                            buckets[catIdx].push(parseFloat(val));
                        });
                    }
                }
            }
        });
        
        let periodAvgs = buckets.map(arr => {
            if (arr.length === 0) return null;
            return parseFloat((arr.reduce((a, b) => a + b, 0) / arr.length).toFixed(2));
        });
        
        // Circular perimeter interpolation: prevent radial collapse to origin 0 when a country has missing seasons/months
        const validCount = periodAvgs.filter(v => v !== null && v !== undefined && !isNaN(v)).length;
        if (validCount > 0 && validCount < numCats) {
            if (validCount === 1) {
                const singleVal = periodAvgs.find(v => v !== null && v !== undefined && !isNaN(v));
                periodAvgs = periodAvgs.map(() => singleVal);
            } else {
                for (let i = 0; i < numCats; i++) {
                    if (periodAvgs[i] === null || periodAvgs[i] === undefined || isNaN(periodAvgs[i])) {
                        let prevDist = 1;
                        while (periodAvgs[(i - prevDist + numCats) % numCats] === null) {
                            prevDist++;
                        }
                        const prevVal = periodAvgs[(i - prevDist + numCats) % numCats];
                        
                        let nextDist = 1;
                        while (periodAvgs[(i + nextDist) % numCats] === null) {
                            nextDist++;
                        }
                        const nextVal = periodAvgs[(i + nextDist) % numCats];
                        
                        const totalDist = prevDist + nextDist;
                        periodAvgs[i] = parseFloat(((prevVal * nextDist + nextVal * prevDist) / totalDist).toFixed(2));
                    }
                }
            }
        }
        
        return {
            name: countryName,
            data: periodAvgs,
            color: countryColors[idx % countryColors.length]
        };
    });
    
    const globalAvgs = categories.map((_, catIdx) => {
        const validVals = countrySeries.map(s => s.data[catIdx]).filter(v => v !== null && v !== undefined && !isNaN(v));
        return validVals.length > 0 ? parseFloat((validVals.reduce((a, b) => a + b, 0) / validVals.length).toFixed(2)) : null;
    });
    
    const isSoloMedia = !!state.compareRadarSoloAvg;
    
    const cardEl = container.parentElement;
    let toolbarEl = cardEl ? cardEl.querySelector('.radar-compare-toolbar') : null;
    if (cardEl && !toolbarEl) {
        toolbarEl = document.createElement('div');
        toolbarEl.className = 'radar-compare-toolbar';
        toolbarEl.style.cssText = 'display: flex; justify-content: flex-end; gap: 0.5rem; padding: 0.5rem 1rem 0 1rem; flex-wrap: wrap;';
        cardEl.insertBefore(toolbarEl, container);
    }
    if (toolbarEl) {
        const resBtnText = isQuarterly ? 'Stagionale (4 Trimestri)' : 'Mensile (12 Mesi)';
        const resBtnIcon = isQuarterly ? 'fa-calendar-days' : 'fa-calendar';
        toolbarEl.innerHTML = `
            <button onclick="toggleCompareRadarResolution()" title="Cambia risoluzione temporale (risolve frequenze di campionamento difformi)" class="px-3 py-1 rounded-full text-xs font-semibold bg-slate-700/50 text-slate-200 border border-slate-600/50 hover:bg-slate-700 transition-all flex items-center gap-1.5 cursor-pointer outline-none shadow-sm">
                <i class="fa-solid ${resBtnIcon} text-sky-400"></i>
                <span>${resBtnText}</span>
            </button>
            ${isSoloMedia ? `
                <button onclick="toggleCompareRadarMode()" class="px-3 py-1 rounded-full text-xs font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 hover:bg-indigo-500/30 transition-all flex items-center gap-1.5 cursor-pointer outline-none shadow-sm">
                    <i class="fa-solid fa-earth-americas text-indigo-400"></i>
                    <span>Mostra Confronto Paesi</span>
                </button>
            ` : `
                <button onclick="toggleCompareRadarMode()" class="px-3 py-1 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/40 hover:bg-amber-500/25 transition-all flex items-center gap-1.5 cursor-pointer outline-none shadow-sm">
                    <i class="fa-solid fa-star text-amber-400"></i>
                    <span>Mostra Solo Media Confronto</span>
                </button>
            `}
        `;
    }
    
    container._lastCompareRadarArgs = { countriesData, metricKey, dataType };
    
    let finalSeries = [...countrySeries];
    let finalColors = countrySeries.map(s => s.color);
    
    if (isSoloMedia) {
        finalSeries = [{
            name: '⭐ Media Confronto',
            data: globalAvgs
        }];
        finalColors = ['#fbbf24'];
    }
    
    const options = {
        series: finalSeries.map(s => ({ name: s.name, data: s.data })),
        chart: {
            type: 'radar',
            height: 380,
            id: 'chart-compare-radar-view',
            toolbar: { show: true },
            background: 'transparent'
        },
        colors: finalColors,
        stroke: {
            width: isSoloMedia ? 3 : 2,
            spanNulls: true
        },
        fill: {
            type: 'solid',
            opacity: 0,
            colors: Array(30).fill('transparent')
        },
        plotOptions: {
            radar: {
                polygons: {
                    strokeColors: 'rgba(255, 255, 255, 0.08)',
                    connectorColors: 'rgba(255, 255, 255, 0.08)',
                    fill: { colors: ['transparent', 'transparent'] }
                }
            }
        },
        markers: {
            size: 4,
            hover: { size: 6 }
        },
        xaxis: {
            categories: categories,
            labels: {
                style: {
                    colors: Array(numCats).fill('#94a3b8'),
                    fontSize: '11px',
                    fontFamily: 'Outfit',
                    fontWeight: 500
                }
            }
        },
        yaxis: {
            show: true,
            labels: {
                style: { colors: '#64748b', fontSize: '9px', fontFamily: 'Inter' }
            }
        },
        theme: { mode: 'dark' },
        tooltip: {
            shared: true,
            intersect: false
        },
        legend: {
            position: 'top',
            fontFamily: 'Inter',
            fontSize: '12px'
        }
    };
    
    container.innerHTML = "";
    if (compareRadarChart) { try { compareRadarChart.destroy(); } catch(e) {} }
    compareRadarChart = new ApexCharts(container, options);
    compareRadarChart.render();
}

function getMetricLabel(key) {
    if (key === 'ipc') return 'Percentuale Popolazione IPC 3+';
    if (key === 'acled') return 'Eventi di Conflitto';
    if (key === 'idp') return 'Popolazione IDP';
    if (key === 'rainfall') return 'Precipitazioni (mm)';
    if (key === 'wfp') return 'Indice dei Prezzi Alimentari';
    if (key === 'ndvi') return 'Indice NDVI (VIM)';
    if (key === 'gdelt') return 'Conflitti (GDELT)';
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
        const avgNdvi = getAvgField('ndvi_vim');
        const avgGdelt = getAvgField('gdelt_material_conflict_events');
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
                <div class="detail-row" style="background: rgba(255,255,255,0.01); padding: 0.4rem 0.6rem; border-radius: 6px;">
                    <span class="detail-label">Vegetazione NDVI (VIM Media):</span>
                    <span class="detail-value" style="color: #10b981; font-weight:700;">${avgNdvi !== null ? avgNdvi.toFixed(3) : "N/A"}</span>
                </div>
                <div class="detail-row" style="background: rgba(255,255,255,0.01); padding: 0.4rem 0.6rem; border-radius: 6px;">
                    <span class="detail-label">GDELT Eventi (Conflitti Materiali Media):</span>
                    <span class="detail-value" style="color: #a855f7; font-weight:700;">${avgGdelt !== null ? avgGdelt.toFixed(1) : "N/A"}</span>
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
    } else if (theme === 'ndvi') {
        metricName = "Indice NDVI (VIM)";
        metricFormat = "{0}";
        colorMax = "#10b981";
        maxVal = 1.0;
    } else if (theme === 'gdelt') {
        metricName = "Conflitti (GDELT)";
        metricFormat = "{0}";
        colorMax = "#a855f7";
        maxVal = 1000;
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
    else if (state.heatmapTheme === 'ndvi') themeName = "Vegetazione (NDVI)";
    else if (state.heatmapTheme === 'gdelt') themeName = "Copertura News (GDELT)";
    
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
    const btnGdelt = document.getElementById('btn-country-tab-gdelt');
    const btnIpc = document.getElementById('btn-country-tab-ipc');
    const btnAcled = document.getElementById('btn-country-tab-acled');
    const btnIdp = document.getElementById('btn-country-tab-idp');
    const btnRainfall = document.getElementById('btn-country-tab-rainfall');
    const btnNdvi = document.getElementById('btn-country-tab-ndvi');
    const btnTsa = document.getElementById('btn-country-tab-tsa');
    
    if (btnMap) btnMap.classList.toggle('active', subViewName === 'map');
    if (btnMarkets) btnMarkets.classList.toggle('active', subViewName === 'markets');
    if (btnCharts) btnCharts.classList.toggle('active', subViewName === 'charts');
    if (btnTable) btnTable.classList.toggle('active', subViewName === 'table');
    if (btnGdelt) btnGdelt.classList.toggle('active', subViewName === 'gdelt');
    if (btnIpc) btnIpc.classList.toggle('active', subViewName === 'ipc');
    if (btnAcled) btnAcled.classList.toggle('active', subViewName === 'acled');
    if (btnIdp) btnIdp.classList.toggle('active', subViewName === 'idp');
    if (btnRainfall) btnRainfall.classList.toggle('active', subViewName === 'rainfall');
    if (btnNdvi) btnNdvi.classList.toggle('active', subViewName === 'ndvi');
    if (btnTsa) btnTsa.classList.toggle('active', subViewName === 'tsa');
    
    // Toggle active sidebar sub-menu items
    const navMap = document.getElementById('nav-country-map');
    const navMarkets = document.getElementById('nav-country-markets');
    const navCharts = document.getElementById('nav-country-charts');
    const navTable = document.getElementById('nav-country-table');
    const navGdelt = document.getElementById('nav-country-gdelt');
    const navIpc = document.getElementById('nav-country-ipc');
    const navAcled = document.getElementById('nav-country-acled');
    const navIdp = document.getElementById('nav-country-idp');
    const navRainfall = document.getElementById('nav-country-rainfall');
    const navNdvi = document.getElementById('nav-country-ndvi');
    const navSpatiotemporal = document.getElementById('nav-country-spatiotemporal');
    const navTsa = document.getElementById('nav-country-tsa');
    
    if (navMap) navMap.classList.toggle('active', subViewName === 'map');
    if (navMarkets) navMarkets.classList.toggle('active', subViewName === 'markets');
    if (navCharts) navCharts.classList.toggle('active', subViewName === 'charts');
    if (navTable) navTable.classList.toggle('active', subViewName === 'table');
    if (navGdelt) navGdelt.classList.toggle('active', subViewName === 'gdelt');
    if (navIpc) navIpc.classList.toggle('active', subViewName === 'ipc');
    if (navAcled) navAcled.classList.toggle('active', subViewName === 'acled');
    if (navIdp) navIdp.classList.toggle('active', subViewName === 'idp');
    if (navRainfall) navRainfall.classList.toggle('active', subViewName === 'rainfall');
    if (navNdvi) navNdvi.classList.toggle('active', subViewName === 'ndvi');
    if (navSpatiotemporal) navSpatiotemporal.classList.toggle('active', subViewName === 'spatiotemporal');
    if (navTsa) navTsa.classList.toggle('active', subViewName === 'tsa');
    
    // Toggle active sub-panels
    const panelMap = document.getElementById('country-sub-panel-map');
    const panelMarkets = document.getElementById('country-sub-panel-markets');
    const panelCharts = document.getElementById('country-sub-panel-charts');
    const panelTable = document.getElementById('country-sub-panel-table');
    const panelGdelt = document.getElementById('country-sub-panel-gdelt');
    const panelIpc = document.getElementById('country-sub-panel-ipc');
    const panelAcled = document.getElementById('country-sub-panel-acled');
    const panelIdp = document.getElementById('country-sub-panel-idp');
    const panelRainfall = document.getElementById('country-sub-panel-rainfall');
    const panelNdvi = document.getElementById('country-sub-panel-ndvi');
    const panelSpatiotemporal = document.getElementById('country-sub-panel-spatiotemporal');
    const panelTsa = document.getElementById('country-sub-panel-tsa');
    
    if (panelMap) panelMap.style.display = subViewName === 'map' ? 'block' : 'none';
    if (panelMarkets) panelMarkets.style.display = subViewName === 'markets' ? 'block' : 'none';
    if (panelCharts) panelCharts.style.display = subViewName === 'charts' ? 'block' : 'none';
    if (panelTable) panelTable.style.display = subViewName === 'table' ? 'block' : 'none';
    if (panelGdelt) panelGdelt.style.display = subViewName === 'gdelt' ? 'block' : 'none';
    if (panelIpc) panelIpc.style.display = subViewName === 'ipc' ? 'block' : 'none';
    if (panelAcled) panelAcled.style.display = subViewName === 'acled' ? 'block' : 'none';
    if (panelIdp) panelIdp.style.display = subViewName === 'idp' ? 'block' : 'none';
    if (panelRainfall) panelRainfall.style.display = subViewName === 'rainfall' ? 'block' : 'none';
    if (panelNdvi) panelNdvi.style.display = subViewName === 'ndvi' ? 'block' : 'none';
    if (panelSpatiotemporal) panelSpatiotemporal.style.display = subViewName === 'spatiotemporal' ? 'block' : 'none';
    if (panelTsa) panelTsa.style.display = subViewName === 'tsa' ? 'block' : 'none';
    
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
            updateCountryDashboard();
        }, 50);
    } else if (subViewName === 'gdelt') {
        const code = state.selectedCountry;
        const data = countryCache[code];
        if (data) {
            let activeTrends = [];
            if (state.subregion === 'national') {
                activeTrends = (data.trends.adm1 && data.trends.adm1.length > 0) ? data.trends.adm1 : data.trends.adm2;
            } else {
                const parts = state.subregion.split('_');
                const level = parts[0];
                const pcode = parts[1];
                activeTrends = data.regions[level][pcode] || [];
            }
            renderGdeltTab(activeTrends);
        }
    } else if (subViewName === 'spatiotemporal') {
        setTimeout(() => {
            renderCountrySpatiotemporalHeatmap();
        }, 50);
    } else if (subViewName === 'tsa') {
        setTimeout(() => {
            renderTsaDiagnostics();
        }, 50);
    } else if (['ipc', 'acled', 'idp', 'rainfall', 'ndvi'].includes(subViewName)) {
        loadAndRenderRawTab(state.selectedCountry, subViewName);
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
    
    // Extract subregion PCode if active
    let subregPcode = null;
    if (state.subregion !== 'national') {
        const parts = state.subregion.split('_');
        subregPcode = parts[1];
    }

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
            
            // Subregion filter opacity
            const isMatch = !subregPcode || (m.adm1_pcode === subregPcode || m.adm2_pcode === subregPcode);
            if (!isMatch) {
                circle.style.opacity = "0.15";
                circle.style.pointerEvents = "none";
            }
            
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
    
    // Filter markets by active subregion
    let filteredMarkets = [...countryData.markets];
    if (state.subregion !== 'national') {
        const parts = state.subregion.split('_');
        const pcode = parts[1];
        filteredMarkets = filteredMarkets.filter(m => m.adm1_pcode === pcode || m.adm2_pcode === pcode);
    }
    
    if (filteredMarkets.length === 0) {
        container.innerHTML = `
            <div style="padding:1.5rem; text-align:center; color:var(--text-muted); font-size:0.75rem;">
                Nessun mercato censito in questa sotto-regione.
            </div>
        `;
        return;
    }
    
    const sortedMarkets = filteredMarkets.sort((a, b) => a.name.localeCompare(b.name));
    
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
            
            // Load and render price trend charts for this market
            loadAndRenderMarketDetail(m.name, m.lat, m.lon);
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

// Lazy load and render WFP market detailed charts
async function loadAndRenderMarketDetail(marketName, lat, lon) {
    const code = state.selectedCountry;
    if (!code) return;
    
    const detailsSection = document.getElementById("country-market-details-section");
    if (!detailsSection) return;
    
    // Update titles and coords
    document.getElementById("selected-market-title").innerText = `Dettaglio Mercato: ${marketName}`;
    document.getElementById("selected-market-coords").innerText = `Lat: ${lat.toFixed(3)} Lon: ${lon.toFixed(3)}`;
    detailsSection.style.display = "block";
    
    // Show loading spinners in chart placeholders
    showRawSpinner("chart-market-price-index", "Caricamento prezzi alimentari...");
    showRawSpinner("chart-market-inflation", "Caricamento inflazione locale...");
    
    try {
        let data = wfpMarketsCache[code];
        if (!data) {
            const res = await fetch(`data/countries/${code}_raw_markets.json?t=${Date.now()}`);
            if (!res.ok) throw new Error(`HTTP error ${res.status}`);
            data = await res.json();
            wfpMarketsCache[code] = data;
        }
        
        const mktSeries = data.markets[marketName] || [];
        renderMarketCharts(mktSeries);
    } catch (err) {
        console.error("Failed to load WFP raw market prices:", err);
        const errMessage = `<div style="height: 250px; display: flex; align-items: center; justify-content: center; color: var(--color-danger); font-size: 0.8rem; gap: 0.5rem;"><i class="fa-solid fa-triangle-exclamation"></i> Nessun dato storico sui prezzi disponibile per questo mercato.</div>`;
        document.getElementById("chart-market-price-index").innerHTML = errMessage;
        document.getElementById("chart-market-inflation").innerHTML = errMessage;
    }
}

// Render WFP market charts using ApexCharts
function renderMarketCharts(mktSeries) {
    if (wfpMarketCharts.priceIndex) { wfpMarketCharts.priceIndex.destroy(); wfpMarketCharts.priceIndex = null; }
    if (wfpMarketCharts.inflation) { wfpMarketCharts.inflation.destroy(); wfpMarketCharts.inflation = null; }
    
    const containerPrice = document.getElementById("chart-market-price-index");
    const containerInflation = document.getElementById("chart-market-inflation");
    
    if (!containerPrice || !containerInflation) return;
    containerPrice.innerHTML = "";
    containerInflation.innerHTML = "";
    
    if (!mktSeries || mktSeries.length === 0) {
        const noData = `<div style="height: 250px; display: flex; align-items: center; justify-content: center; color: var(--text-muted); font-size: 0.85rem;">Nessun record sui prezzi trovato per questo mercato</div>`;
        containerPrice.innerHTML = noData;
        containerInflation.innerHTML = noData;
        return;
    }
    
    // Sort chronological
    mktSeries.sort((a, b) => a.date.localeCompare(b.date));
    
    const priceData = [];
    const inflationData = [];
    
    mktSeries.forEach(s => {
        const ts = new Date(s.date).getTime();
        if (s.price_index !== null && s.price_index !== undefined) {
            priceData.push({ x: ts, y: s.price_index });
        }
        if (s.inflation !== null && s.inflation !== undefined) {
            inflationData.push({ x: ts, y: parseFloat((s.inflation * 100).toFixed(1)) });
        }
    });
    
    // Price Index Line Chart
    const priceOptions = {
        series: [{ name: 'Indice Prezzi Alimentari', data: priceData }],
        chart: {
            height: 280,
            type: 'line',
            group: 'raw-wfp-market',
            id: 'chart-market-price-index-detail',
            toolbar: { show: false },
            background: 'transparent'
        },
        theme: { mode: 'dark' },
        colors: ['#818cf8'],
        stroke: { width: 3, curve: 'smooth', connectNulls: true },
        markers: { size: 4, hover: { size: 6 } },
        xaxis: {
            type: 'datetime',
            labels: {
                datetimeUTC: false,
                style: { fontSize: '9px' }
            }
        },
        yaxis: {
            title: { text: 'Indice Prezzi' },
            labels: { formatter: val => (val !== null && val !== undefined) ? val.toFixed(1) : "" }
        },
        tooltip: {
            shared: true,
            intersect: false,
            x: { format: 'yyyy-MM-dd' }
        }
    };
    
    wfpMarketCharts.priceIndex = new ApexCharts(containerPrice, priceOptions);
    wfpMarketCharts.priceIndex.render();
    
    // Inflation Column Chart
    const inflationOptions = {
        series: [{ name: 'Tasso di Inflazione Mensile (%)', data: inflationData }],
        chart: {
            height: 280,
            type: 'bar',
            group: 'raw-wfp-market',
            id: 'chart-market-inflation-detail',
            toolbar: { show: false },
            background: 'transparent'
        },
        theme: { mode: 'dark' },
        dataLabels: { enabled: false },
        colors: ['#f87171'],
        plotOptions: {
            bar: {
                colors: {
                    ranges: [
                        { from: -100, to: 0, color: '#34d399' },
                        { from: 0.01, to: 1000, color: '#f87171' }
                    ]
                },
                columnWidth: '60%'
            }
        },
        xaxis: {
            type: 'datetime',
            labels: {
                datetimeUTC: false,
                style: { fontSize: '9px' }
            }
        },
        yaxis: {
            title: { text: 'Inflazione (%)' },
            labels: { formatter: val => (val !== null && val !== undefined) ? val.toFixed(1) + "%" : "" }
        },
        tooltip: {
            shared: true,
            intersect: false,
            x: { format: 'yyyy-MM-dd' }
        }
    };
    
    wfpMarketCharts.inflation = new ApexCharts(containerInflation, inflationOptions);
    wfpMarketCharts.inflation.render();
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

// Render GDELT Sub-Panel Media & News
function renderGdeltTab(trends) {
    // Determine fallback trends if adm2 is selected
    const warningBanner = document.getElementById("gdelt-adm2-warning");
    let displayTrends = trends;
    
    if (state.subregion && state.subregion.startsWith("adm2")) {
        if (warningBanner) warningBanner.style.display = "flex";
        const code = state.selectedCountry;
        const data = countryCache[code];
        if (data) {
            let parentPcode = null;
            if (trends && trends.length > 0 && trends[0].adm1_pcode) {
                parentPcode = trends[0].adm1_pcode;
            }
            if (parentPcode && data.regions.adm1[parentPcode]) {
                displayTrends = data.regions.adm1[parentPcode];
            } else {
                displayTrends = data.trends.adm1 && data.trends.adm1.length > 0 ? data.trends.adm1 : data.trends.adm2;
            }
        }
    } else {
        if (warningBanner) warningBanner.style.display = "none";
    }
    
    // Destroy previous charts in the tab
    if (gdeltTabCharts.tone) {
        gdeltTabCharts.tone.destroy();
        gdeltTabCharts.tone = null;
    }
    if (gdeltTabCharts.salience) {
        gdeltTabCharts.salience.destroy();
        gdeltTabCharts.salience = null;
    }
    destroyRawChart('gdeltEventsSeasonal');
    destroyRawChart('gdeltToneSeasonal');
    
    const containerTone = document.getElementById("chart-gdelt-tab-tone");
    const containerSalience = document.getElementById("chart-gdelt-tab-salience");
    
    if (!containerTone || !containerSalience) return;
    containerTone.innerHTML = "";
    containerSalience.innerHTML = "";
    
    const hasData = displayTrends && displayTrends.some(t => t.gdelt_material_conflict_events !== null && t.gdelt_material_conflict_events !== undefined);
    if (!displayTrends || displayTrends.length === 0 || !hasData) {
        const noDataHtml = `<div style="height: 380px; display: flex; align-items: center; justify-content: center; color: var(--text-muted); font-size: 0.85rem;">Nessun dato di copertura informativa GDELT disponibile</div>`;
        containerTone.innerHTML = noDataHtml;
        containerSalience.innerHTML = noDataHtml;
        return;
    }
    
    const toneSeries = [
        { name: 'Coop. Verbale (Tono)', data: displayTrends.map(t => ({ x: new Date(t.from).getTime(), y: t.gdelt_verbal_coop_tone })), color: '#34d399' },
        { name: 'Coop. Materiale (Tono)', data: displayTrends.map(t => ({ x: new Date(t.from).getTime(), y: t.gdelt_material_coop_tone })), color: '#60a5fa' },
        { name: 'Conflitto Verbale (Tono)', data: displayTrends.map(t => ({ x: new Date(t.from).getTime(), y: t.gdelt_verbal_conflict_tone })), color: '#fbbf24' },
        { name: 'Conflitto Materiale (Tono)', data: displayTrends.map(t => ({ x: new Date(t.from).getTime(), y: t.gdelt_material_conflict_tone })), color: '#f87171' }
    ];
    
    // 1. TONE CHART OPTIONS
    const toneOptions = {
        series: toneSeries,
        chart: {
            height: 380,
            type: 'line',
            group: 'raw-gdelt',
            id: 'chart-gdelt-tab-tone',
            toolbar: { show: false },
            background: 'transparent'
        },
        theme: { mode: 'dark' },
        stroke: { width: 3, curve: 'smooth', connectNulls: true },
        markers: { size: 4, hover: { size: 6 } },
        xaxis: {
            type: 'datetime',
            labels: {
                datetimeUTC: false,
                style: { fontSize: '10px' }
            }
        },
        yaxis: {
            title: { text: 'Tono Medio (-10 a +10)' },
            min: -10,
            max: 10,
            labels: { formatter: val => (val !== null && val !== undefined) ? val.toFixed(1) : "" }
        },
        tooltip: {
            shared: true,
            intersect: false,
            x: { format: 'yyyy-MM-dd' }
        },
        legend: { position: 'top', fontFamily: 'Inter', fontSize: '11px' }
    };
    
    gdeltTabCharts.tone = new ApexCharts(containerTone, toneOptions);
    gdeltTabCharts.tone.render();
    
    const salienceViewMode = (state.gdeltViewModes && state.gdeltViewModes['chart-gdelt-tab-salience']) || 'histogram';
    
    let salienceSeries = [
        { name: 'Coop. Verbale (Menzioni)', type: 'column', data: displayTrends.map(t => ({ x: new Date(t.from).getTime(), y: t.gdelt_verbal_coop_mentions ? Math.round(t.gdelt_verbal_coop_mentions) : 0 })), color: '#34d399' },
        { name: 'Coop. Materiale (Menzioni)', type: 'column', data: displayTrends.map(t => ({ x: new Date(t.from).getTime(), y: t.gdelt_material_coop_mentions ? Math.round(t.gdelt_material_coop_mentions) : 0 })), color: '#60a5fa' },
        { name: 'Conflitto Verbale (Menzioni)', type: 'column', data: displayTrends.map(t => ({ x: new Date(t.from).getTime(), y: t.gdelt_verbal_conflict_mentions ? Math.round(t.gdelt_verbal_conflict_mentions) : 0 })), color: '#fbbf24' },
        { name: 'Conflitto Materiale (Menzioni)', type: 'column', data: displayTrends.map(t => ({ x: new Date(t.from).getTime(), y: t.gdelt_material_conflict_mentions ? Math.round(t.gdelt_material_conflict_mentions) : 0 })), color: '#f87171' },
        { name: 'Eventi Conflitto Materiale', type: 'line', data: displayTrends.map(t => ({ x: new Date(t.from).getTime(), y: t.gdelt_material_conflict_events ? Math.round(t.gdelt_material_conflict_events) : 0 })), color: '#a855f7' }
    ];
    let salienceYAxis = [
        {
            title: { text: 'Menzioni Totali nei Media' },
            labels: { formatter: val => (val !== null && val !== undefined) ? formatNumber(Math.round(val)) : "" }
        },
        {
            opposite: true,
            title: { text: 'Numero Eventi Reali' },
            labels: { formatter: val => (val !== null && val !== undefined) ? formatNumber(Math.round(val)) : "" }
        }
    ];
    
    if (salienceViewMode === 'histogram') {
        salienceSeries = salienceSeries.slice(0, 4);
        salienceYAxis = [salienceYAxis[0]];
    } else if (salienceViewMode === 'line') {
        salienceSeries = [salienceSeries[4]];
        salienceYAxis = [{ ...salienceYAxis[1], opposite: false }];
    }
    
    // 2. SALIENCE/MENTIONS CHART OPTIONS
    const salienceOptions = {
        series: salienceSeries,
        chart: {
            height: 380,
            type: 'line',
            stacked: true,
            group: 'raw-gdelt',
            id: 'chart-gdelt-tab-salience',
            toolbar: { show: false },
            background: 'transparent'
        },
        theme: { mode: 'dark' },
        stroke: {
            width: salienceViewMode === 'histogram' ? [0, 0, 0, 0] : (salienceViewMode === 'line' ? [3] : [0, 0, 0, 0, 3]),
            curve: 'smooth',
            connectNulls: true
        },
        markers: {
            size: salienceViewMode === 'histogram' ? [0, 0, 0, 0] : (salienceViewMode === 'line' ? [5] : [0, 0, 0, 0, 5]),
            hover: { size: 7 }
        },
        plotOptions: {
            bar: {
                columnWidth: '55%',
                opacity: 0.85
            }
        },
        xaxis: {
            type: 'datetime',
            labels: {
                datetimeUTC: false,
                style: { fontSize: '10px' }
            }
        },
        yaxis: salienceYAxis,
        tooltip: {
            shared: true,
            intersect: false,
            x: { format: 'yyyy-MM-dd' }
        },
        legend: { position: 'top', fontFamily: 'Inter', fontSize: '11px' }
    };
    
    gdeltTabCharts.salience = new ApexCharts(containerSalience, salienceOptions);
    gdeltTabCharts.salience.render();
    
    renderNativeSeasonalRadar(displayTrends, 'chart-raw-gdelt-events-seasonal', arr => {
        const vals = arr.map(x => x.gdelt_material_conflict_events).filter(v => v !== null && v !== undefined && !isNaN(v));
        return vals.length > 0 ? vals.reduce((a,b)=>a+b,0) : null;
    }, 'gdeltEventsSeasonal', 'monthly', gdeltTabCharts.salience, 4);

    renderNativeSeasonalRadar(displayTrends, 'chart-raw-gdelt-tone-seasonal', arr => {
        const vals = arr.map(x => x.gdelt_avg_tone).filter(v => v !== null && v !== undefined && !isNaN(v));
        return vals.length > 0 ? vals.reduce((a,b)=>a+b,0)/vals.length : null;
    }, 'gdeltToneSeasonal', 'monthly', gdeltTabCharts.tone, 3);
}

// ── RAW DATA HIGH-RESOLUTION TABS LOGIC ──

// Helper to destroy raw charts safely
function destroyRawChart(key) {
    if (rawCharts[key]) {
        rawCharts[key].destroy();
        rawCharts[key] = null;
    }
}

// Helper to show a loading spinner inside a container
function showRawSpinner(containerId, message = "Caricamento dati nativi...") {
    const el = document.getElementById(containerId);
    if (el) {
        el.innerHTML = `
            <div style="height: 100%; min-height: 250px; display: flex; align-items: center; justify-content: center; color: var(--text-muted); font-size: 0.85rem; flex-direction: column; gap: 0.5rem;">
                <i class="fa-solid fa-spinner fa-spin fa-xl text-indigo-400"></i>
                <span>${message}</span>
            </div>
        `;
    }
}

// Universal helper to render Native High-Resolution Seasonal Radar charts
function renderNativeSeasonalRadar(trends, containerId, metricGetter, chartKey, mode = 'monthly', linkedChartInstance = null, linkedSeriesIdx = 0) {
    const el = document.getElementById(containerId);
    if (!el) return;
    el.innerHTML = "";
    if (!trends || trends.length === 0) {
        el.innerHTML = `<div style="height: 320px; display: flex; align-items: center; justify-content: center; color: var(--text-muted); font-size: 0.85rem;">Nessun dato stagionale disponibile</div>`;
        return;
    }
    
    // Group trends by year and period (month 0-11 or quarter 0-3)
    const byYear = {};
    trends.forEach(t => {
        const dateStr = t.from || t.date;
        if (!dateStr) return;
        const year = dateStr.split('-')[0];
        let pIndex = 0;
        if (mode === 'monthly') {
            const parts = dateStr.split('-');
            if (parts.length >= 2) pIndex = parseInt(parts[1], 10) - 1;
        } else {
            pIndex = typeof getQuarterFromDate === 'function' ? getQuarterFromDate(dateStr) : Math.floor((parseInt(dateStr.split('-')[1]||1, 10)-1)/3);
        }
        if (isNaN(pIndex) || pIndex < 0) pIndex = 0;
        if (mode === 'monthly' && pIndex > 11) pIndex = 11;
        if (mode !== 'monthly' && pIndex > 3) pIndex = 3;
        
        if (!byYear[year]) {
            byYear[year] = mode === 'monthly' 
                ? { 0:[], 1:[], 2:[], 3:[], 4:[], 5:[], 6:[], 7:[], 8:[], 9:[], 10:[], 11:[] } 
                : { 0:[], 1:[], 2:[], 3:[] };
        }
        byYear[year][pIndex].push(t);
    });
    
    const years = Object.keys(byYear).sort();
    const categories = mode === 'monthly'
        ? ['Gen', 'Feb', 'Mar', 'Apr', 'Mag', 'Giu', 'Lug', 'Ago', 'Set', 'Ott', 'Nov', 'Dic']
        : ['Q1 (Gen-Mar)', 'Q2 (Apr-Giu)', 'Q3 (Lug-Set)', 'Q4 (Ott-Dic)'];
        
    state.nativeRadarModes = state.nativeRadarModes || {};
    const isSoloMedia = !!state.nativeRadarModes[containerId];
    
    const cardEl = el.parentElement;
    let toolbarEl = cardEl ? cardEl.querySelector('.radar-native-toolbar') : null;
    if (cardEl && !toolbarEl) {
        toolbarEl = document.createElement('div');
        toolbarEl.className = 'radar-native-toolbar';
        toolbarEl.style.cssText = 'display: flex; justify-content: flex-end; padding: 0.5rem 1rem 0 1rem;';
        cardEl.insertBefore(toolbarEl, el);
    }
    if (toolbarEl) {
        toolbarEl.innerHTML = isSoloMedia ? `
            <button onclick="toggleNativeRadarMode('${containerId}')" class="px-3 py-1 rounded-full text-xs font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 hover:bg-indigo-500/30 transition-all flex items-center gap-1.5 cursor-pointer outline-none shadow-sm">
                <i class="fa-solid fa-calendar-days text-indigo-400"></i>
                <span>Mostra Tutti gli Anni</span>
            </button>
        ` : `
            <button onclick="toggleNativeRadarMode('${containerId}')" class="px-3 py-1 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/40 hover:bg-amber-500/25 transition-all flex items-center gap-1.5 cursor-pointer outline-none shadow-sm">
                <i class="fa-solid fa-star text-amber-400"></i>
                <span>Mostra Solo Media</span>
            </button>
        `;
    }
    
    el._lastRadarArgs = { trends, containerId, metricGetter, chartKey, mode, linkedChartInstance, linkedSeriesIdx };
    
    const yearColors = years.map((y, idx) => {
        const hue = 220 - (idx / (years.length - 1 || 1)) * 205;
        return `hsl(${hue}, 85%, 60%)`;
    });
    
    let series = years.map(year => {
        const data = categories.map((_, idx) => {
            const arr = byYear[year][idx];
            if (!arr || arr.length === 0) return null;
            return metricGetter(arr);
        });
        return {
            name: year,
            data: data.map(val => val !== null && !isNaN(val) ? parseFloat(val.toFixed(2)) : null)
        };
    });
    
    let colors = yearColors;
    if (isSoloMedia) {
        const avgData = categories.map((_, idx) => {
            const validVals = series.map(s => s.data[idx]).filter(v => v !== null && v !== undefined && !isNaN(v));
            return validVals.length > 0 ? parseFloat((validVals.reduce((a, b) => a + b, 0) / validVals.length).toFixed(2)) : null;
        });
        series = [{
            name: '⭐ Media Storica',
            data: avgData
        }];
        colors = ['#fbbf24'];
    }
    
    const options = {
        series: series,
        chart: {
            type: 'radar',
            height: 350,
            toolbar: { show: true },
            background: 'transparent',
            events: {
                dataPointMouseEnter: function(event, chartContext, config) {
                    if (linkedChartInstance && typeof linkedChartInstance.tooltip === 'object' && typeof linkedChartInstance.tooltip.showTooltip === 'function') {
                        const sObj = config.w.config.series[config.seriesIndex];
                        const sName = sObj ? sObj.name : null;
                        if (!sName || sName === '⭐ Media Storica' || !String(sName).match(/^\d{4}/)) return;
                        const year = sName;
                        const pIdx = config.dataPointIndex;
                        let targetDatePrefix = year + "-";
                        if (mode === 'monthly') {
                            const mStr = (pIdx + 1).toString().padStart(2, '0');
                            targetDatePrefix += mStr;
                        }
                        try {
                            const sData = linkedChartInstance.w && linkedChartInstance.w.config && linkedChartInstance.w.config.series && linkedChartInstance.w.config.series[linkedSeriesIdx] && linkedChartInstance.w.config.series[linkedSeriesIdx].data;
                            const cats = linkedChartInstance.w && linkedChartInstance.w.config && linkedChartInstance.w.config.xaxis && linkedChartInstance.w.config.xaxis.categories;
                            if (sData && Array.isArray(sData)) {
                                let matchIdx = -1;
                                const matchQuarter = (dateStr, qIdx) => {
                                    const m = parseInt(dateStr.substring(5, 7), 10);
                                    if (isNaN(m)) return false;
                                    return Math.floor((m - 1) / 3) === qIdx;
                                };
                                for (let i = 0; i < sData.length; i++) {
                                    const pt = sData[i];
                                    let xVal = (pt && typeof pt === 'object' && pt.x !== undefined) ? pt.x : (cats && cats[i] ? cats[i] : null);
                                    if (xVal === null || xVal === undefined) continue;
                                    let xStr = typeof xVal === 'string' ? xVal : (typeof xVal === 'number' ? (new Date(xVal)).toISOString() : String(xVal));
                                    if (!xStr) continue;
                                    if (mode === 'monthly') {
                                        if (xStr.startsWith(targetDatePrefix)) { matchIdx = i; break; }
                                    } else {
                                        if (xStr.startsWith(year + "-") && matchQuarter(xStr, pIdx)) { matchIdx = i; break; }
                                    }
                                }
                                if (matchIdx >= 0) {
                                    linkedChartInstance.tooltip.showTooltip(linkedSeriesIdx, matchIdx);
                                }
                            }
                        } catch(e) {}
                    }
                }
            }
        },
        colors: colors,
        stroke: { 
            width: isSoloMedia ? 3 : 2, 
            spanNulls: true 
        },
        fill: {
            type: 'solid',
            opacity: 0,
            colors: Array(35).fill('transparent')
        },
        plotOptions: {
            radar: {
                polygons: {
                    strokeColors: 'rgba(255, 255, 255, 0.08)',
                    connectorColors: 'rgba(255, 255, 255, 0.08)',
                    fill: { colors: ['transparent', 'transparent'] }
                }
            }
        },
        markers: { size: 3, hover: { size: 6 } },
        xaxis: {
            categories: categories,
            labels: {
                style: {
                    colors: Array(categories.length).fill('#94a3b8'),
                    fontSize: '10px',
                    fontFamily: 'Outfit',
                    fontWeight: 500
                }
            }
        },
        yaxis: {
            show: true,
            labels: {
                style: { colors: '#64748b', fontSize: '8px', fontFamily: 'Inter' }
            }
        },
        theme: { mode: 'dark' },
        tooltip: { shared: true, intersect: false },
        legend: { position: 'bottom', fontFamily: 'Inter', fontSize: '11px', horizontalAlign: 'center' }
    };
    
    if (rawCharts[chartKey]) {
        try { rawCharts[chartKey].destroy(); } catch(e) {}
    }
    rawCharts[chartKey] = new ApexCharts(el, options);
    rawCharts[chartKey].render();
}

// Main coordinator for loading and rendering raw tabs
async function loadAndRenderRawTab(countryCode, feature) {
    if (!countryCode) return;
    
    // Initialize cache structures
    rawCache[countryCode] = rawCache[countryCode] || {};
    
    // Show spinner if not cached yet
    if (!rawCache[countryCode][feature]) {
        if (feature === 'ipc') {
            showRawSpinner('chart-raw-ipc-time');
            showRawSpinner('chart-raw-ipc-pop-seasonal');
            showRawSpinner('chart-raw-ipc-pct-seasonal');
        } else if (feature === 'acled') {
            showRawSpinner('chart-raw-acled-events');
            showRawSpinner('chart-raw-acled-fatalities');
            showRawSpinner('chart-raw-acled-events-seasonal');
            showRawSpinner('chart-raw-acled-fatalities-seasonal');
        } else if (feature === 'idp') {
            showRawSpinner('chart-raw-idp-time');
            showRawSpinner('chart-raw-idp-seasonal');
        } else if (feature === 'rainfall') {
            showRawSpinner('chart-raw-rainfall-real');
            showRawSpinner('chart-raw-rainfall-anom');
            showRawSpinner('chart-raw-rainfall-rain-seasonal');
            showRawSpinner('chart-raw-rainfall-anomaly-seasonal');
        } else if (feature === 'ndvi') {
            showRawSpinner('chart-raw-ndvi-vim');
            showRawSpinner('chart-raw-ndvi-viq');
            showRawSpinner('chart-raw-ndvi-vim-seasonal');
            showRawSpinner('chart-raw-ndvi-viq-seasonal');
        }
    }
    
    try {
        let data = rawCache[countryCode][feature];
        if (!data) {
            const res = await fetch(`data/countries/${countryCode}_raw_${feature}.json?t=${Date.now()}`);
            if (!res.ok) throw new Error(`HTTP error ${res.status}`);
            data = await res.json();
            rawCache[countryCode][feature] = data;
        }
        
        // Extract subset based on selected subregion
        let trends = [];
        if (state.subregion === 'national') {
            trends = data.national || [];
        } else {
            const parts = state.subregion.split('_');
            const level = parts[0];
            const pcode = parts[1];
            trends = (data.regions && data.regions[level]) ? (data.regions[level][pcode] || []) : [];
        }
        
        // Route to specific renderer
        if (feature === 'ipc') {
            renderIpcTab(trends);
        } else if (feature === 'acled') {
            renderAcledTab(trends);
        } else if (feature === 'idp') {
            renderIdpTab(trends);
        } else if (feature === 'rainfall') {
            renderRainfallTab(trends);
        } else if (feature === 'ndvi') {
            renderNdviTab(trends);
        }
    } catch (err) {
        console.error(`Failed to load raw data for ${countryCode} / ${feature}:`, err);
        const errMessage = `<div style="height: 100%; min-height: 200px; display: flex; align-items: center; justify-content: center; color: var(--color-danger); font-size: 0.8rem; gap: 0.5rem;"><i class="fa-solid fa-triangle-exclamation"></i> Impossibile caricare i dati nativi per questa area.</div>`;
        
        if (feature === 'ipc') {
            document.getElementById('chart-raw-ipc-time').innerHTML = errMessage;
        } else if (feature === 'acled') {
            document.getElementById('chart-raw-acled-events').innerHTML = errMessage;
            document.getElementById('chart-raw-acled-fatalities').innerHTML = errMessage;
        } else if (feature === 'idp') {
            document.getElementById('chart-raw-idp-time').innerHTML = errMessage;
        } else if (feature === 'rainfall') {
            document.getElementById('chart-raw-rainfall-real').innerHTML = errMessage;
            document.getElementById('chart-raw-rainfall-anom').innerHTML = errMessage;
        } else if (feature === 'ndvi') {
            document.getElementById('chart-raw-ndvi-vim').innerHTML = errMessage;
            document.getElementById('chart-raw-ndvi-viq').innerHTML = errMessage;
        }
    }
}

// 1. IPC RAW RENDERER
function renderIpcTab(trends) {
    destroyRawChart('ipc');
    destroyRawChart('ipcPopSeasonal');
    destroyRawChart('ipcPctSeasonal');
    const container = document.getElementById("chart-raw-ipc-time");
    const tbody = document.querySelector("#table-raw-ipc tbody");
    
    if (tbody) tbody.innerHTML = "";
    if (!container) return;
    container.innerHTML = "";
    
    if (!trends || trends.length === 0) {
        container.innerHTML = `<div style="height: 320px; display: flex; align-items: center; justify-content: center; color: var(--text-muted); font-size: 0.85rem;">Nessun dato IPC nativo disponibile per questa area</div>`;
        if (tbody) {
            tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">Nessun record trovato</td></tr>`;
        }
        return;
    }
    
    // Sort and populate table
    trends.forEach(t => {
        if (!tbody) return;
        const tr = document.createElement("tr");
        const rangeText = `${t.from.substring(0, 10)} a ${t.to.substring(0, 10)}`;
        tr.innerHTML = `
            <td style="padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05); font-weight: 500;">${rangeText}</td>
            <td style="padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05); text-transform: capitalize;">${t.type}</td>
            <td style="padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05); text-align: right;">${formatNumber(t.phase_1)}</td>
            <td style="padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05); text-align: right;">${formatNumber(t.phase_2)}</td>
            <td style="padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05); text-align: right;">${formatNumber(t.phase_3)}</td>
            <td style="padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05); text-align: right;">${formatNumber(t.phase_4)}</td>
            <td style="padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05); text-align: right;">${formatNumber(t.phase_5)}</td>
            <td style="padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05); text-align: right; color: var(--color-danger); font-weight: 600;">${formatNumber(t.phase_3plus)}</td>
            <td style="padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05); text-align: right; color: var(--color-danger); font-weight: 600;">${t.phase_3plus_percentage.toFixed(1)}%</td>
        `;
        tbody.appendChild(tr);
    });
    
    // Check toggle state
    const toggleEl = document.getElementById('ipc-proportional-toggle');
    if (toggleEl) {
        toggleEl.checked = !!state.ipcProportional;
    }
    
    if (state.ipcProportional) {
        renderIpcProportionalTimeline(container, trends);
        return;
    }
    
    // Render Dual Axis Chart (Phase 3+ Pop vs Phase 3+ %)
    const categories = trends.map(t => `${t.from.substring(0, 7)} (${t.type === 'current' ? 'Corr' : 'Proj'})`);
    const pop = trends.map(t => t.phase_3plus);
    const pct = trends.map(t => parseFloat(t.phase_3plus_percentage.toFixed(1)));
    
    const options = {
        series: [
            { name: 'Popolazione in Fase 3+ (Persone)', type: 'column', data: pop, color: '#f59e0b' },
            { name: 'Popolazione in Fase 3+ (%)', type: 'line', data: pct, color: '#ef4444' }
        ],
        chart: {
            height: 380,
            type: 'line',
            toolbar: { show: false },
            background: 'transparent'
        },
        theme: { mode: 'dark' },
        stroke: {
            width: [0, 4],
            curve: 'smooth'
        },
        markers: {
            size: [0, 5],
            hover: { size: 7 }
        },
        xaxis: {
            categories: categories,
            labels: { style: { fontSize: '9px' } }
        },
        yaxis: [
            {
                title: { text: 'Popolazione Fase 3+', style: { color: '#f59e0b' } },
                labels: {
                    style: { colors: '#f59e0b' },
                    formatter: val => formatNumber(val)
                }
            },
            {
                opposite: true,
                title: { text: 'Popolazione Fase 3+ (%)', style: { color: '#ef4444' } },
                labels: {
                    style: { colors: '#ef4444' },
                    formatter: val => val !== null ? val + "%" : ""
                }
            }
        ],
        tooltip: { shared: true, intersect: false },
        legend: { position: 'top', fontFamily: 'Inter', fontSize: '11px' }
    };
    
    rawCharts.ipc = new ApexCharts(container, options);
    rawCharts.ipc.render();
    
    renderNativeSeasonalRadar(trends, 'chart-raw-ipc-pop-seasonal', arr => {
        const vals = arr.map(x => x.phase_3plus).filter(v => v !== null && v !== undefined && !isNaN(v));
        return vals.length > 0 ? vals.reduce((a,b)=>a+b,0)/vals.length : null;
    }, 'ipcPopSeasonal', 'quarterly', rawCharts.ipc, 0);

    renderNativeSeasonalRadar(trends, 'chart-raw-ipc-pct-seasonal', arr => {
        const vals = arr.map(x => x.phase_3plus_percentage).filter(v => v !== null && v !== undefined && !isNaN(v));
        return vals.length > 0 ? vals.reduce((a,b)=>a+b,0)/vals.length : null;
    }, 'ipcPctSeasonal', 'quarterly', rawCharts.ipc, 1);
}

// Handler for toggle of proportional width timeline in IPC tab
function toggleIpcProportionalView() {
    const toggleEl = document.getElementById('ipc-proportional-toggle');
    if (toggleEl) {
        state.ipcProportional = toggleEl.checked;
        
        // Re-render the tab with currently cached data
        if (state.selectedCountry) {
            const cachedData = rawCache[state.selectedCountry] && rawCache[state.selectedCountry]['ipc'];
            if (cachedData) {
                let trends = [];
                if (state.subregion === 'national') {
                    trends = cachedData.national || [];
                } else {
                    const parts = state.subregion.split('_');
                    const level = parts[0];
                    const pcode = parts[1];
                    trends = (cachedData.regions && cachedData.regions[level]) ? (cachedData.regions[level][pcode] || []) : [];
                }
                renderIpcTab(trends);
            }
        }
    }
}

// Custom renderer for proportional timeline of IPC analyses
function renderIpcProportionalTimeline(container, trends) {
    // Save trends reference globally for event listeners/modals
    window.currentIpcTrends = trends;
    
    // Sort trends chronologically
    const sorted = trends.map((t, idx) => ({ ...t, originalIndex: idx }))
                         .sort((a, b) => new Date(a.from) - new Date(b.from));
                         
    const minDate = new Date(sorted[0].from);
    const maxDate = new Date(sorted[sorted.length - 1].to);
    const totalTime = maxDate - minDate || 1;
    
    // Generate year/month gridlines
    const minYear = minDate.getFullYear();
    const maxYear = maxDate.getFullYear();
    const yearDiff = maxYear - minYear;
    
    let gridHtml = '';
    if (yearDiff === 0) {
        // Month gridlines
        const minMonth = minDate.getMonth();
        const maxMonth = maxDate.getMonth();
        const monthNames = ["Gen", "Feb", "Mar", "Apr", "Mag", "Giu", "Lug", "Ago", "Set", "Ott", "Nov", "Dic"];
        for (let m = minMonth; m <= maxMonth; m++) {
            const gridDate = new Date(minYear, m, 1);
            if (gridDate >= minDate && gridDate <= maxDate) {
                const offset = ((gridDate - minDate) / totalTime) * 100;
                gridHtml += `
                    <div style="position: absolute; left: ${offset}%; top: 0; bottom: 0; border-left: 1px dashed rgba(255,255,255,0.06); pointer-events: none; z-index: 1;"></div>
                    <div style="position: absolute; left: ${offset}%; bottom: -20px; transform: translateX(-50%); font-size: 0.65rem; color: var(--text-muted); font-family: 'Inter', sans-serif; pointer-events: none; z-index: 1;">${monthNames[m]}</div>
                `;
            }
        }
    } else {
        // Year gridlines
        for (let y = minYear; y <= maxYear + 1; y++) {
            const gridDate = new Date(y, 0, 1);
            if (gridDate >= minDate && gridDate <= maxDate) {
                const offset = ((gridDate - minDate) / totalTime) * 100;
                gridHtml += `
                    <div style="position: absolute; left: ${offset}%; top: 0; bottom: 0; border-left: 1px dashed rgba(255,255,255,0.06); pointer-events: none; z-index: 1;"></div>
                    <div style="position: absolute; left: ${offset}%; bottom: -20px; transform: translateX(-50%); font-size: 0.65rem; color: var(--text-muted); font-family: 'Inter', sans-serif; pointer-events: none; z-index: 1;">${y}</div>
                `;
            }
        }
    }
    
    // Generate bars
    let barsHtml = '';
    sorted.forEach(t => {
        const start = new Date(t.from);
        const end = new Date(t.to);
        const left = ((start - minDate) / totalTime) * 100;
        const width = ((end - start) / totalTime) * 100;
        
        const val = t.phase_3plus_percentage !== null && t.phase_3plus_percentage !== undefined ? t.phase_3plus_percentage : 0;
        const height = Math.min(100, Math.max(2, val)); // Min height 2% for visibility
        
        const p3 = t.phase_3_percentage || 0;
        const p4 = t.phase_4_percentage || 0;
        const p5 = t.phase_5_percentage || 0;
        const sum = p3 + p4 + p5 || 1;
        
        const p3Height = (p3 / sum) * 100;
        const p4Height = (p4 / sum) * 100;
        const p5Height = (p5 / sum) * 100;
        
        barsHtml += `
            <div class="ipc-proportional-bar" 
                 style="position: absolute; left: ${left}%; width: ${width}%; bottom: 0; height: ${height}%; display: flex; flex-direction: column-reverse; cursor: pointer;"
                 onclick="openPeriodDetailModal(window.currentIpcTrends, ${t.originalIndex})"
                 data-idx="${t.originalIndex}"
            >
                <div style="height: ${p3Height}%; background-color: #eab308; width: 100%;"></div>
                <div style="height: ${p4Height}%; background-color: #f97316; width: 100%;"></div>
                <div style="height: ${p5Height}%; background-color: #ef4444; width: 100%;"></div>
            </div>
        `;
    });
    
    container.innerHTML = `
        <style>
            .ipc-proportional-bar {
                border-radius: 4px;
                border: 1px solid rgba(255,255,255,0.06);
                background: rgba(30, 41, 59, 0.4);
                box-shadow: 0 4px 10px rgba(0,0,0,0.3);
                transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
                overflow: hidden;
            }
            .ipc-proportional-bar:hover {
                transform: translateY(-2px);
                box-shadow: 0 8px 16px rgba(99, 102, 241, 0.25);
                border-color: rgba(99, 102, 241, 0.5);
                filter: brightness(1.15);
            }
        </style>
        <div style="display: flex; height: 100%; width: 100%; font-family: 'Inter', sans-serif; box-sizing: border-box; overflow: hidden; position: relative;">
            <!-- Custom HTML Tooltip -->
            <div id="ipc-timeline-tooltip" style="position: absolute; display: none; background: rgba(15, 23, 42, 0.95); border: 1px solid rgba(255,255,255,0.12); border-radius: 8px; padding: 10px; font-size: 0.75rem; color: white; pointer-events: none; box-shadow: 0 4px 15px rgba(0,0,0,0.5); z-index: 100; min-width: 200px;"></div>

            <!-- Y-Axis -->
            <div style="width: 45px; height: 100%; display: flex; flex-direction: column; justify-content: space-between; align-items: flex-end; padding-right: 8px; box-sizing: border-box; font-size: 0.65rem; color: var(--text-muted); border-right: 1px solid rgba(255,255,255,0.08); z-index: 2;">
                <div style="height: calc(100% - 55px); margin-top: 15px; margin-bottom: 40px; display: flex; flex-direction: column; justify-content: space-between; align-items: flex-end;">
                    <div>100%</div>
                    <div>80%</div>
                    <div>60%</div>
                    <div>40%</div>
                    <div>20%</div>
                    <div>0%</div>
                </div>
            </div>
            
            <!-- Chart Area -->
            <div style="flex-grow: 1; height: 100%; position: relative; background: rgba(15, 23, 42, 0.2); box-sizing: border-box; overflow: visible; z-index: 2;">
                <!-- Horizontal Gridlines -->
                <div style="position: absolute; left: 0; right: 0; top: 15px; border-top: 1px solid rgba(255,255,255,0.04); pointer-events: none;"></div>
                <div style="position: absolute; left: 0; right: 0; top: calc(15px + (100% - 55px) * 0.2); border-top: 1px solid rgba(255,255,255,0.04); pointer-events: none;"></div>
                <div style="position: absolute; left: 0; right: 0; top: calc(15px + (100% - 55px) * 0.4); border-top: 1px solid rgba(255,255,255,0.04); pointer-events: none;"></div>
                <div style="position: absolute; left: 0; right: 0; top: calc(15px + (100% - 55px) * 0.6); border-top: 1px solid rgba(255,255,255,0.04); pointer-events: none;"></div>
                <div style="position: absolute; left: 0; right: 0; top: calc(15px + (100% - 55px) * 0.8); border-top: 1px solid rgba(255,255,255,0.04); pointer-events: none;"></div>
                <div style="position: absolute; left: 0; right: 0; bottom: 40px; border-top: 1px dashed rgba(255,255,255,0.15); pointer-events: none; z-index: 3;"></div>
                
                <!-- Vertical Gridlines and labels -->
                <div style="position: absolute; left: 0; right: 0; top: 15px; bottom: 40px; overflow: visible;">
                    ${gridHtml}
                </div>
                
                <!-- Bars container -->
                <div id="ipc-proportional-bars-container" style="position: absolute; left: 0; right: 0; top: 15px; bottom: 40px; z-index: 2;">
                    ${barsHtml}
                </div>
            </div>
        </div>
    `;
    
    // Add tooltip event listeners to bars
    const tooltipEl = document.getElementById("ipc-timeline-tooltip");
    
    container.querySelectorAll(".ipc-proportional-bar").forEach(bar => {
        const idx = parseInt(bar.getAttribute("data-idx"));
        const t = trends[idx];
        
        bar.addEventListener("mouseenter", (e) => {
            const p3 = t.phase_3_percentage || 0;
            const p4 = t.phase_4_percentage || 0;
            const p5 = t.phase_5_percentage || 0;
            
            tooltipEl.innerHTML = `
                <div style="font-weight: 700; margin-bottom: 5px; border-bottom: 1px solid rgba(255,255,255,0.12); padding-bottom: 3px; font-family: 'Inter', sans-serif;">
                    Analisi IPC (${t.type === 'current' ? 'Corrente' : 'Proiezione'})
                </div>
                <div style="margin-bottom: 5px; color: var(--text-muted); font-size: 0.65rem; font-family: 'Inter', sans-serif;">
                    Periodo: ${t.from.substring(0, 10)} al ${t.to.substring(0, 10)}
                </div>
                <div style="display: flex; justify-content: space-between; gap: 1rem; margin-bottom: 3px; font-family: 'Inter', sans-serif;">
                    <span>Fase 3+ (%):</span>
                    <span style="color: var(--color-danger); font-weight: 700;">${t.phase_3plus_percentage.toFixed(1)}%</span>
                </div>
                <div style="display: flex; justify-content: space-between; gap: 1rem; margin-bottom: 5px; font-family: 'Inter', sans-serif;">
                    <span>Fase 3+ Pop.:</span>
                    <span style="color: var(--color-danger); font-weight: 700;">${formatNumber(t.phase_3plus)}</span>
                </div>
                <div style="font-size: 0.65rem; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 5px; display: flex; flex-direction: column; gap: 2px; font-family: 'Inter', sans-serif;">
                    <div style="display: flex; justify-content: space-between;"><span style="color: #eab308;">Fase 3 (Crisi):</span> <span>${t.phase_3_percentage !== null ? t.phase_3_percentage.toFixed(1) + '%' : 'N/A'}</span></div>
                    <div style="display: flex; justify-content: space-between;"><span style="color: #f97316;">Fase 4 (Emergenza):</span> <span>${t.phase_4_percentage !== null ? t.phase_4_percentage.toFixed(1) + '%' : 'N/A'}</span></div>
                    <div style="display: flex; justify-content: space-between;"><span style="color: #ef4444;">Fase 5 (Catastrofe):</span> <span>${t.phase_5_percentage !== null ? t.phase_5_percentage.toFixed(1) + '%' : 'N/A'}</span></div>
                </div>
            `;
            tooltipEl.style.display = "block";
        });
        
        bar.addEventListener("mousemove", (e) => {
            const currentContainerRect = container.getBoundingClientRect();
            const leftPos = e.clientX - currentContainerRect.left + 15;
            const topPos = e.clientY - currentContainerRect.top + 15;
            
            if (leftPos + 220 > currentContainerRect.width) {
                tooltipEl.style.left = `${e.clientX - currentContainerRect.left - 230}px`;
            } else {
                tooltipEl.style.left = `${leftPos}px`;
            }
            tooltipEl.style.top = `${topPos}px`;
        });
        
        bar.addEventListener("mouseleave", () => {
            tooltipEl.style.display = "none";
        });
    });
}

// 2. ACLED RAW RENDERER
function renderAcledTab(trends) {
    destroyRawChart('acledEvents');
    destroyRawChart('acledFatalities');
    destroyRawChart('acledEventsSeasonal');
    destroyRawChart('acledFatalitiesSeasonal');
    const containerEvents = document.getElementById("chart-raw-acled-events");
    const containerFatal = document.getElementById("chart-raw-acled-fatalities");
    const tbody = document.querySelector("#table-raw-acled tbody");
    
    if (tbody) tbody.innerHTML = "";
    if (!containerEvents || !containerFatal) return;
    containerEvents.innerHTML = "";
    containerFatal.innerHTML = "";
    
    if (!trends || trends.length === 0) {
        const nodata = `<div style="height: 320px; display: flex; align-items: center; justify-content: center; color: var(--text-muted); font-size: 0.85rem;">Nessun dato conflitti nativo disponibile per questa area</div>`;
        containerEvents.innerHTML = nodata;
        containerFatal.innerHTML = nodata;
        if (tbody) {
            tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">Nessun record trovato</td></tr>`;
        }
        return;
    }
    
    // Sort chronological and populate table
    trends.forEach(t => {
        if (!tbody) return;
        const tr = document.createElement("tr");
        const monthLabel = t.from.substring(0, 7);
        tr.innerHTML = `
            <td style="padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05); font-weight: 600;">${monthLabel}</td>
            <td style="padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05); text-align: right;">${t.political_violence_events}</td>
            <td style="padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05); text-align: right; color: var(--color-danger);">${Math.round(t.political_violence_fatalities)}</td>
            <td style="padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05); text-align: right;">${t.civilian_targeting_events}</td>
            <td style="padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05); text-align: right; color: var(--color-danger);">${Math.round(t.civilian_targeting_fatalities)}</td>
            <td style="padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05); text-align: right;">${t.demonstrations_events}</td>
            <td style="padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05); text-align: right; color: var(--color-danger);">${Math.round(t.demonstrations_fatalities)}</td>
            <td style="padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05); text-align: right; font-weight: 700;">${t.total_events}</td>
            <td style="padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05); text-align: right; font-weight: 700; color: var(--color-danger);">${Math.round(t.total_fatalities)}</td>
        `;
        tbody.appendChild(tr);
    });
    
    // Event series formatted for datetime axis
    const eventSeries = [
        { name: 'Violenza Politica', data: trends.map(t => ({ x: new Date(t.from).getTime(), y: t.political_violence_events })), color: '#ef4444' },
        { name: 'Targeting Civili', data: trends.map(t => ({ x: new Date(t.from).getTime(), y: t.civilian_targeting_events })), color: '#f59e0b' },
        { name: 'Dimostrazioni/Proteste', data: trends.map(t => ({ x: new Date(t.from).getTime(), y: t.demonstrations_events })), color: '#3b82f6' }
    ];
    
    // Stacked column of event categories
    const eventOptions = {
        series: eventSeries,
        chart: {
            height: 380,
            type: 'bar',
            stacked: true,
            group: 'raw-acled',
            id: 'chart-raw-acled-events',
            toolbar: { show: false },
            background: 'transparent'
        },
        theme: { mode: 'dark' },
        dataLabels: { enabled: false },
        plotOptions: { bar: { columnWidth: '60%' } },
        xaxis: {
            type: 'datetime',
            labels: {
                datetimeUTC: false,
                style: { fontSize: '9px' }
            }
        },
        yaxis: { title: { text: 'Numero Eventi' } },
        tooltip: {
            shared: true,
            intersect: false,
            x: { format: 'yyyy-MM-dd' }
        },
        legend: { position: 'top', fontFamily: 'Inter', fontSize: '11px' }
    };
    
    rawCharts.acledEvents = new ApexCharts(containerEvents, eventOptions);
    rawCharts.acledEvents.render();
    
    // Fatalities series formatted for datetime axis
    const fatalSeries = [
        { name: 'Violenza Politica', data: trends.map(t => ({ x: new Date(t.from).getTime(), y: Math.round(t.political_violence_fatalities) })), color: '#b91c1c' },
        { name: 'Targeting Civili', data: trends.map(t => ({ x: new Date(t.from).getTime(), y: Math.round(t.civilian_targeting_fatalities) })), color: '#d97706' },
        { name: 'Dimostrazioni/Proteste', data: trends.map(t => ({ x: new Date(t.from).getTime(), y: Math.round(t.demonstrations_fatalities) })), color: '#1d4ed8' }
    ];
    
    // Stacked column of fatalities
    const fatalOptions = {
        series: fatalSeries,
        chart: {
            height: 380,
            type: 'bar',
            stacked: true,
            group: 'raw-acled',
            id: 'chart-raw-acled-fatalities',
            toolbar: { show: false },
            background: 'transparent'
        },
        theme: { mode: 'dark' },
        dataLabels: { enabled: false },
        plotOptions: { bar: { columnWidth: '60%' } },
        xaxis: {
            type: 'datetime',
            labels: {
                datetimeUTC: false,
                style: { fontSize: '9px' }
            }
        },
        yaxis: { title: { text: 'Stima Vittime' } },
        tooltip: {
            shared: true,
            intersect: false,
            x: { format: 'yyyy-MM-dd' }
        },
        legend: { position: 'top', fontFamily: 'Inter', fontSize: '11px' }
    };
    
    rawCharts.acledFatalities = new ApexCharts(containerFatal, fatalOptions);
    rawCharts.acledFatalities.render();
    
    renderNativeSeasonalRadar(trends, 'chart-raw-acled-events-seasonal', arr => {
        const vals = arr.map(x => x.total_events).filter(v => v !== null && v !== undefined && !isNaN(v));
        return vals.length > 0 ? vals.reduce((a,b)=>a+b,0) : null;
    }, 'acledEventsSeasonal', 'monthly', rawCharts.acledEvents, 0);

    renderNativeSeasonalRadar(trends, 'chart-raw-acled-fatalities-seasonal', arr => {
        const vals = arr.map(x => x.total_fatalities).filter(v => v !== null && v !== undefined && !isNaN(v));
        return vals.length > 0 ? vals.reduce((a,b)=>a+b,0) : null;
    }, 'acledFatalitiesSeasonal', 'monthly', rawCharts.acledFatalities, 0);
}

// 3. IDP RAW RENDERER
function renderIdpTab(trends) {
    destroyRawChart('idp');
    destroyRawChart('idpSeasonal');
    const container = document.getElementById("chart-raw-idp-time");
    const tbody = document.querySelector("#table-raw-idp tbody");
    
    if (tbody) tbody.innerHTML = "";
    if (!container) return;
    container.innerHTML = "";
    
    if (!trends || trends.length === 0) {
        container.innerHTML = `<div style="height: 320px; display: flex; align-items: center; justify-content: center; color: var(--text-muted); font-size: 0.85rem;">Nessun dato IDP nativo disponibile per questa area</div>`;
        if (tbody) {
            tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">Nessun record trovato</td></tr>`;
        }
        return;
    }
    
    // Sort chronological and populate table
    trends.forEach(t => {
        if (!tbody) return;
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td style="padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05); font-weight: 500;">${t.from.substring(0, 10)}</td>
            <td style="padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05); font-weight: 700;">Round ${t.round}</td>
            <td style="padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05); text-transform: uppercase;">${t.type}</td>
            <td style="padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05); text-align: right; color: var(--color-info); font-weight: 600;">${formatNumber(t.population)}</td>
        `;
        tbody.appendChild(tr);
    });
    
    const categories = trends.map(t => `${t.from.substring(0, 10)} (R${t.round})`);
    const pop = trends.map(t => t.population);
    
    const options = {
        series: [
            { name: 'Popolazione Sfollata Interna', data: pop }
        ],
        chart: {
            height: 380,
            type: 'area',
            toolbar: { show: false },
            background: 'transparent'
        },
        theme: { mode: 'dark' },
        colors: ['#60a5fa'],
        fill: {
            type: 'gradient',
            gradient: { shadeIntensity: 1, opacityFrom: 0.45, opacityTo: 0.05 }
        },
        stroke: { width: 3, curve: 'smooth' },
        markers: { size: 5, hover: { size: 7 } },
        xaxis: {
            categories: categories,
            tickAmount: Math.min(categories.length, 12),
            labels: { style: { fontSize: '9px' } }
        },
        yaxis: {
            title: { text: 'Popolazione IDP' },
            labels: { formatter: val => formatNumber(val) }
        },
        tooltip: { shared: true, intersect: false }
    };
    
    rawCharts.idp = new ApexCharts(container, options);
    rawCharts.idp.render();
    
    renderNativeSeasonalRadar(trends, 'chart-raw-idp-seasonal', arr => {
        const vals = arr.map(x => x.population).filter(v => v !== null && v !== undefined && !isNaN(v));
        return vals.length > 0 ? vals.reduce((a,b)=>a+b,0)/vals.length : null;
    }, 'idpSeasonal', 'quarterly', rawCharts.idp, 0);
}

// 4. RAINFALL RAW RENDERER
function renderRainfallTab(trends) {
    destroyRawChart('rainfallReal');
    destroyRawChart('rainfallAnom');
    destroyRawChart('rainfallRainSeasonal');
    destroyRawChart('rainfallAnomalySeasonal');
    const containerReal = document.getElementById("chart-raw-rainfall-real");
    const containerAnom = document.getElementById("chart-raw-rainfall-anom");
    const tbody = document.querySelector("#table-raw-rainfall tbody");
    
    if (tbody) tbody.innerHTML = "";
    if (!containerReal || !containerAnom) return;
    containerReal.innerHTML = "";
    containerAnom.innerHTML = "";
    
    if (!trends || trends.length === 0) {
        const nodata = `<div style="height: 320px; display: flex; align-items: center; justify-content: center; color: var(--text-muted); font-size: 0.85rem;">Nessun dato precipitazioni nativo disponibile per questa area</div>`;
        containerReal.innerHTML = nodata;
        containerAnom.innerHTML = nodata;
        if (tbody) {
            tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">Nessun record trovato</td></tr>`;
        }
        return;
    }
    
    // Sort and populate table
    trends.forEach(t => {
        if (!tbody) return;
        const tr = document.createElement("tr");
        const rain1m = t.rain_1m !== null ? t.rain_1m.toFixed(1) : '-';
        const rain3m = t.rain_3m !== null ? t.rain_3m.toFixed(1) : '-';
        const anom1m = t.rain_anomaly_1m !== null ? t.rain_anomaly_1m.toFixed(1) : '-';
        const anom3m = t.rain_anomaly_3m !== null ? t.rain_anomaly_3m.toFixed(1) : '-';
        
        tr.innerHTML = `
            <td style="padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05); font-weight: 500;">${t.date.substring(0, 7)}</td>
            <td style="padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05); text-align: right;">${rain1m} mm</td>
            <td style="padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05); text-align: right;">${rain3m} mm</td>
            <td style="padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05); text-align: right; color: ${t.rain_anomaly_1m >= 0 ? '#34d399' : '#f87171'}">${anom1m} mm</td>
            <td style="padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05); text-align: right; color: ${t.rain_anomaly_3m >= 0 ? '#34d399' : '#f87171'}">${anom3m} mm</td>
        `;
        tbody.appendChild(tr);
    });
    
    const realSeries = [
        { name: 'Pioggia Mensile Cumulata (1M)', data: trends.map(t => ({ x: new Date(t.date).getTime(), y: t.rain_1m !== null ? parseFloat(t.rain_1m.toFixed(1)) : null })), color: '#38bdf8' },
        { name: 'Pioggia Cumulata 3 Mesi (3M)', data: trends.map(t => ({ x: new Date(t.date).getTime(), y: t.rain_3m !== null ? parseFloat(t.rain_3m.toFixed(1)) : null })), color: '#1d4ed8' }
    ];
    
    // Real cumulative rain chart
    const realOptions = {
        series: realSeries,
        chart: {
            height: 380,
            type: 'line',
            group: 'raw-rainfall',
            id: 'chart-raw-rainfall-real',
            toolbar: { show: false },
            background: 'transparent'
        },
        theme: { mode: 'dark' },
        stroke: { width: 3, curve: 'smooth', connectNulls: true },
        markers: { size: 4, hover: { size: 6 } },
        xaxis: {
            type: 'datetime',
            labels: {
                datetimeUTC: false,
                style: { fontSize: '9px' }
            }
        },
        yaxis: {
            title: { text: 'Precipitazioni (mm)' },
            labels: { formatter: val => val !== null ? val.toFixed(0) + " mm" : "" }
        },
        tooltip: {
            shared: true,
            intersect: false,
            x: { format: 'yyyy-MM-dd' }
        },
        legend: { position: 'top', fontFamily: 'Inter', fontSize: '11px' }
    };
    
    rawCharts.rainfallReal = new ApexCharts(containerReal, realOptions);
    rawCharts.rainfallReal.render();
    
    const anomSeries = [
        { name: 'Anomalia Pioggia 1 Mese', data: trends.map(t => ({ x: new Date(t.date).getTime(), y: t.rain_anomaly_1m !== null ? parseFloat(t.rain_anomaly_1m.toFixed(1)) : null })), color: '#a78bfa' },
        { name: 'Anomalia Pioggia 3 Mesi', data: trends.map(t => ({ x: new Date(t.date).getTime(), y: t.rain_anomaly_3m !== null ? parseFloat(t.rain_anomaly_3m.toFixed(1)) : null })), color: '#db2777' }
    ];
    
    // Anomalies chart
    const anomOptions = {
        series: anomSeries,
        chart: {
            height: 380,
            type: 'line',
            group: 'raw-rainfall',
            id: 'chart-raw-rainfall-anom',
            toolbar: { show: false },
            background: 'transparent'
        },
        theme: { mode: 'dark' },
        stroke: { width: 3, curve: 'smooth', connectNulls: true },
        markers: { size: 4, hover: { size: 6 } },
        xaxis: {
            type: 'datetime',
            labels: {
                datetimeUTC: false,
                style: { fontSize: '9px' }
            }
        },
        yaxis: {
            title: { text: 'Deviazione dalla Norma (mm)' },
            labels: { formatter: val => val !== null ? (val > 0 ? "+" : "") + val.toFixed(0) + " mm" : "" }
        },
        tooltip: {
            shared: true,
            intersect: false,
            x: { format: 'yyyy-MM-dd' }
        },
        legend: { position: 'top', fontFamily: 'Inter', fontSize: '11px' }
    };
    
    rawCharts.rainfallAnom = new ApexCharts(containerAnom, anomOptions);
    rawCharts.rainfallAnom.render();
    
    renderNativeSeasonalRadar(trends, 'chart-raw-rainfall-rain-seasonal', arr => {
        const vals = arr.map(x => x.rain_1m).filter(v => v !== null && v !== undefined && !isNaN(v));
        return vals.length > 0 ? vals.reduce((a,b)=>a+b,0)/vals.length : null;
    }, 'rainfallRainSeasonal', 'monthly', rawCharts.rainfallReal, 0);

    renderNativeSeasonalRadar(trends, 'chart-raw-rainfall-anomaly-seasonal', arr => {
        const vals = arr.map(x => x.rain_anomaly_1m).filter(v => v !== null && v !== undefined && !isNaN(v));
        return vals.length > 0 ? vals.reduce((a,b)=>a+b,0)/vals.length : null;
    }, 'rainfallAnomalySeasonal', 'monthly', rawCharts.rainfallAnom, 0);
}

// 5. NDVI RAW RENDERER
function renderNdviTab(trends) {
    destroyRawChart('ndviVim');
    destroyRawChart('ndviViq');
    destroyRawChart('ndviVimSeasonal');
    destroyRawChart('ndviViqSeasonal');
    const containerVim = document.getElementById("chart-raw-ndvi-vim");
    const containerViq = document.getElementById("chart-raw-ndvi-viq");
    const tbody = document.querySelector("#table-raw-ndvi tbody");
    
    if (tbody) tbody.innerHTML = "";
    if (!containerVim || !containerViq) return;
    containerVim.innerHTML = "";
    containerViq.innerHTML = "";
    
    if (!trends || trends.length === 0) {
        const nodata = `<div style="height: 320px; display: flex; align-items: center; justify-content: center; color: var(--text-muted); font-size: 0.85rem;">Nessun dato NDVI nativo disponibile per questa area</div>`;
        containerVim.innerHTML = nodata;
        containerViq.innerHTML = nodata;
        if (tbody) {
            tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">Nessun record trovato</td></tr>`;
        }
        return;
    }
    
    // Sort and populate table
    trends.forEach(t => {
        if (!tbody) return;
        const tr = document.createElement("tr");
        const vim = t.vim !== null ? t.vim.toFixed(3) : '-';
        const vim_avg = t.vim_avg !== null ? t.vim_avg.toFixed(3) : '-';
        const viq = t.viq !== null ? t.viq.toFixed(1) + '%' : '-';
        
        tr.innerHTML = `
            <td style="padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05); font-weight: 500;">${t.date}</td>
            <td style="padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05); text-align: right; color: var(--color-success); font-weight: 600;">${vim}</td>
            <td style="padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05); text-align: right; color: var(--text-muted);">${vim_avg}</td>
            <td style="padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05); text-align: right; color: var(--color-warning); font-weight: 600;">${viq}</td>
        `;
        tbody.appendChild(tr);
    });
    
    // Sample dekads to avoid chart clutter (max 100 points, or show all if smaller)
    let chartTrends = trends;
    if (trends.length > 120) {
        const step = Math.ceil(trends.length / 100);
        chartTrends = trends.filter((_, idx) => idx % step === 0);
    }
    
    const vimSeries = [
        { name: 'NDVI VIM Corrente', data: chartTrends.map(t => ({ x: new Date(t.date).getTime(), y: t.vim !== null ? parseFloat(t.vim.toFixed(3)) : null })), color: '#10b981' },
        { name: 'NDVI VIM Storico Medio', data: chartTrends.map(t => ({ x: new Date(t.date).getTime(), y: t.vim_avg !== null ? parseFloat(t.vim_avg.toFixed(3)) : null })), color: '#6b7280' }
    ];
    
    // NDVI VIM real vs average
    const vimOptions = {
        series: vimSeries,
        chart: {
            height: 380,
            type: 'line',
            group: 'raw-ndvi',
            id: 'chart-raw-ndvi-vim',
            toolbar: { show: false },
            background: 'transparent'
        },
        theme: { mode: 'dark' },
        stroke: { width: [3, 2], curve: 'smooth', dashArray: [0, 4], connectNulls: true },
        markers: { size: [3, 0], hover: { size: 5 } },
        xaxis: {
            type: 'datetime',
            labels: {
                datetimeUTC: false,
                style: { fontSize: '9px' }
            }
        },
        yaxis: {
            title: { text: 'Indice Greenness (NDVI)' },
            labels: { formatter: val => val !== null ? val.toFixed(2) : "" }
        },
        tooltip: {
            shared: true,
            intersect: false,
            x: { format: 'yyyy-MM-dd' }
        },
        legend: { position: 'top', fontFamily: 'Inter', fontSize: '11px' }
    };
    
    rawCharts.ndviVim = new ApexCharts(containerVim, vimOptions);
    rawCharts.ndviVim.render();
    
    const viqSeries = [
        { name: 'Vegetation Condition Index (NDVI VIQ)', data: chartTrends.map(t => ({ x: new Date(t.date).getTime(), y: t.viq !== null ? parseFloat(t.viq.toFixed(1)) : null })) }
    ];
    
    // NDVI VIQ Ratio chart
    const viqOptions = {
        series: viqSeries,
        chart: {
            height: 380,
            type: 'line',
            group: 'raw-ndvi',
            id: 'chart-raw-ndvi-viq',
            toolbar: { show: false },
            background: 'transparent'
        },
        theme: { mode: 'dark' },
        colors: ['#fbbf24'],
        stroke: { width: 3, curve: 'smooth', connectNulls: true },
        markers: { size: 3, hover: { size: 5 } },
        xaxis: {
            type: 'datetime',
            labels: {
                datetimeUTC: false,
                style: { fontSize: '9px' }
            }
        },
        yaxis: {
            title: { text: 'VCI Ratio (%)' },
            labels: { formatter: val => val !== null ? val.toFixed(0) + "%" : "" }
        },
        tooltip: {
            shared: true,
            intersect: false,
            x: { format: 'yyyy-MM-dd' }
        }
    };
    
    rawCharts.ndviViq = new ApexCharts(containerViq, viqOptions);
    rawCharts.ndviViq.render();
    
    renderNativeSeasonalRadar(trends, 'chart-raw-ndvi-vim-seasonal', arr => {
        const vals = arr.map(x => x.vim).filter(v => v !== null && v !== undefined && !isNaN(v));
        return vals.length > 0 ? vals.reduce((a,b)=>a+b,0)/vals.length : null;
    }, 'ndviVimSeasonal', 'monthly', rawCharts.ndviVim, 0);

    renderNativeSeasonalRadar(trends, 'chart-raw-ndvi-viq-seasonal', arr => {
        const vals = arr.map(x => x.viq).filter(v => v !== null && v !== undefined && !isNaN(v));
        return vals.length > 0 ? vals.reduce((a,b)=>a+b,0)/vals.length : null;
    }, 'ndviViqSeasonal', 'monthly', rawCharts.ndviViq, 0);
}

// ── SPATIOTEMPORAL HEATMAPS LOGIC ──

// Main state handlers
function onGlobalSpatiotemporalChange() {
    state.spatiotemporalMetric = document.getElementById("spatiotemporal-metric-selector").value;
    state.spatiotemporalLevel = document.getElementById("spatiotemporal-level-selector").value;
    renderGlobalSpatiotemporalHeatmap();
}

function onCountrySpatiotemporalChange() {
    state.countrySpatiotemporalMetric = document.getElementById("country-spatiotemporal-metric-selector").value;
    renderCountrySpatiotemporalHeatmap();
}

// Dynamic range scaling helper for heatmaps
function getHeatmapColorScale(metric, maxVal = 100) {
    if (metric === 'ipc') {
        return [
            { from: 0, to: 5, name: 'Basso (<5%)', color: '#065f46' },
            { from: 5, to: 15, name: 'Lieve (5-15%)', color: '#047857' },
            { from: 15, to: 25, name: 'Moderato (15-25%)', color: '#fbbf24' },
            { from: 25, to: 45, name: 'Elevato (25-45%)', color: '#f97316' },
            { from: 45, to: 100, name: 'Critico (>45%)', color: '#dc2626' }
        ];
    } else if (metric === 'acled') {
        return [
            { from: 0, to: 0, name: 'Nessun Evento', color: '#1a1f2c' },
            { from: 1, to: 5, name: 'Lieve (1-5)', color: '#fed7aa' },
            { from: 5, to: 20, name: 'Moderato (5-20)', color: '#fb923c' },
            { from: 20, to: 80, name: 'Frequente (20-80)', color: '#ea580c' },
            { from: 80, to: 999999, name: 'Intenso (>80)', color: '#b91c1c' }
        ];
    } else if (metric === 'idp') {
        return [
            { from: 0, to: 0, name: 'Nessun IDP', color: '#1a1f2c' },
            { from: 1, to: 5000, name: 'Basso (<5k)', color: '#a5f3fc' },
            { from: 5000, to: 25000, name: 'Medio (5-25k)', color: '#22d3ee' },
            { from: 25000, to: 100000, name: 'Alto (25-100k)', color: '#06b6d4' },
            { from: 100000, to: 99999999, name: 'Critico (>100k)', color: '#0891b2' }
        ];
    } else if (metric === 'rainfall') {
        return [
            { from: 0, to: 15, name: 'Siccità (<15mm)', color: '#fef08a' },
            { from: 15, to: 50, name: 'Scarse (15-50mm)', color: '#7dd3fc' },
            { from: 50, to: 150, name: 'Medie (50-150mm)', color: '#38bdf8' },
            { from: 150, to: 300, name: 'Abbondanti (150-300mm)', color: '#0284c7' },
            { from: 300, to: 9999, name: 'Intense (>300mm)', color: '#0369a1' }
        ];
    } else if (metric === 'wfp') {
        return [
            { from: 0.0, to: 0.8, name: 'Sottocosto (<0.8)', color: '#a7f3d0' },
            { from: 0.8, to: 1.2, name: 'Normale (0.8-1.2)', color: '#e2e8f0' },
            { from: 1.2, to: 1.5, name: 'Allerta (1.2-1.5)', color: '#fef08a' },
            { from: 1.5, to: 2.0, name: 'Caro (1.5-2.0)', color: '#c084fc' },
            { from: 2.0, to: 99.0, name: 'Iper-inflazione (>2.0)', color: '#7e22ce' }
        ];
    } else if (metric === 'ndvi') {
        return [
            { from: 0.0, to: 0.15, name: 'Arido (<0.15)', color: '#fca5a5' },
            { from: 0.15, to: 0.25, name: 'Scarso (0.15-0.25)', color: '#fef08a' },
            { from: 0.25, to: 0.4, name: 'Medio (0.25-0.4)', color: '#86efac' },
            { from: 0.4, to: 0.6, name: 'Buono (0.4-0.6)', color: '#22c55e' },
            { from: 0.6, to: 2.0, name: 'Lussureggiante (>0.6)', color: '#15803d' }
        ];
    } else if (metric === 'gdelt') {
        return [
            { from: 0, to: 50, name: 'Calmo (<50)', color: '#1e293b' },
            { from: 50, to: 500, name: 'Basso (50-500)', color: '#fda4af' },
            { from: 500, to: 2500, name: 'Medio (500-2500)', color: '#f43f5e' },
            { from: 2500, to: 10000, name: 'Alto (2500-10000)', color: '#e11d48' },
            { from: 10000, to: 99999999, name: 'Critico (>10000)', color: '#9f1239' }
        ];
    }
    return [
        { from: 0, to: 30, name: 'Basso', color: '#312e81' },
        { from: 31, to: 70, name: 'Medio', color: '#4338ca' },
        { from: 71, to: 100, name: 'Alto', color: '#4f46e5' }
    ];
}

// Render Global Heatmap
function renderGlobalSpatiotemporalHeatmap() {
    if (!globalData) return;
    
    const container = document.getElementById("spatiotemporal-chart-container");
    if (!container) return;
    container.innerHTML = "";
    
    const metric = state.spatiotemporalMetric || 'ipc';
    const level = state.spatiotemporalLevel || 'national';
    
    // Choose correct dataset key
    const datasetKey = level === 'national' ? 'value_heatmaps' : 'value_heatmaps_adm1';
    if (!globalData[datasetKey] || !globalData[datasetKey][metric]) {
        container.innerHTML = `<div style="height: 550px; display: flex; align-items: center; justify-content: center; color: var(--text-muted);">Danti non disponibili per questa combinazione.</div>`;
        return;
    }
    
    const heatmapData = globalData[datasetKey][metric];
    
    // Series formatting
    let maxVal = 0;
    const series = heatmapData.y.map((name, idx) => {
        const yCode = heatmapData.y_codes[idx];
        const zRow = heatmapData.z[idx];
        
        const dataPoints = heatmapData.x.map((quarter, qIdx) => {
            const val = zRow[qIdx];
            if (val !== null && val > maxVal) maxVal = val;
            return {
                x: quarter,
                y: val !== null ? parseFloat(val.toFixed(2)) : null
            };
        });
        
        return {
            name: `${name} (${yCode})`,
            data: dataPoints
        };
    });
    
    // Height depends on number of rows (Y axis) to avoid squeezing
    const chartHeight = level === 'national' ? 950 : 2500;
    
    const options = {
        series: series,
        chart: {
            height: chartHeight,
            type: 'heatmap',
            toolbar: { show: true },
            animations: { enabled: false },
            background: 'transparent'
        },
        stroke: { width: 0 },
        dataLabels: { enabled: false },
        plotOptions: {
            heatmap: {
                radius: 0,
                enableShades: true,
                shadeIntensity: 0.6,
                colorScale: {
                    ranges: getHeatmapColorScale(metric, maxVal)
                }
            }
        },
        theme: { mode: 'dark' },
        xaxis: {
            type: 'category',
            labels: {
                rotate: -90,
                rotateAlways: true,
                style: { fontSize: '9px', fontFamily: 'Inter' }
            }
        },
        yaxis: {
            labels: {
                style: { fontSize: '9px', fontFamily: 'Inter' }
            }
        },
        tooltip: {
            custom: function({ series, seriesIndex, dataPointIndex, w }) {
                const rowName = w.config.series[seriesIndex].name;
                const timeLabel = w.globals.labels[dataPointIndex];
                const value = w.config.series[seriesIndex].data[dataPointIndex].y;
                const formattedVal = value !== null ? value : 'N/A';
                return `
                    <div style="padding: 8px 12px; background: rgba(15, 23, 42, 0.95); border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; color: white; font-family: Inter; font-size: 11px;">
                        <div style="font-weight: 700; font-family: Outfit; font-size: 12px; color: #a5b4fc; margin-bottom: 4px;">${rowName}</div>
                        <div>Periodo: <span style="font-weight: 600;">${timeLabel}</span></div>
                        <div>Valore: <span style="font-weight: 600; color: #10b981;">${formattedVal}</span></div>
                    </div>
                `;
            }
        }
    };
    
    if (globalSpatiotemporalChart) {
        globalSpatiotemporalChart.destroy();
    }
    globalSpatiotemporalChart = new ApexCharts(container, options);
    globalSpatiotemporalChart.render();
}

// Render Local Country Heatmap
function renderCountrySpatiotemporalHeatmap() {
    const code = state.selectedCountry;
    const data = countryCache[code];
    if (!data) return;
    
    const container = document.getElementById("country-spatiotemporal-chart-container");
    if (!container) return;
    container.innerHTML = "";
    
    const metric = state.countrySpatiotemporalMetric || 'ipc';
    
    // Metric property mapping in country JSON trends
    const metricProps = {
        ipc: 'phase_3plus_percentage',
        acled: 'acled_total_events',
        idp: 'idp_population',
        rainfall: 'rain_1m',
        wfp: 'wfp_price',
        ndvi: 'ndvi_vim',
        gdelt: 'gdelt_material_conflict_events'
    };
    const prop = metricProps[metric];
    
    // Extract unique dates/quarters from all regions
    const datesSet = new Set();
    if (data.regions && data.regions.adm1) {
        Object.keys(data.regions.adm1).forEach(pcode => {
            const list = data.regions.adm1[pcode] || [];
            list.forEach(t => {
                if (t.from) {
                    datesSet.add(t.from.substring(0, 7));
                }
            });
        });
    }
    
    const sortedDates = sortedDatesList(Array.from(datesSet));
    if (sortedDates.length === 0 || !data.adm1_units || data.adm1_units.length === 0) {
        container.innerHTML = `<div style="height: 450px; display: flex; align-items: center; justify-content: center; color: var(--text-muted);">Nessun dato storico provinciale rilevato per questo paese.</div>`;
        return;
    }
    
    let maxVal = 0;
    const series = data.adm1_units.map(unit => {
        const pcodeTrends = (data.regions && data.regions.adm1) ? (data.regions.adm1[unit.pcode] || []) : [];
        
        // Map date to value
        const valMap = {};
        pcodeTrends.forEach(t => {
            if (t.from && t[prop] !== undefined && t[prop] !== null) {
                valMap[t.from.substring(0, 7)] = t[prop];
            }
        });
        
        const dataPoints = sortedDates.map(date => {
            const val = valMap[date] !== undefined ? valMap[date] : null;
            if (val !== null && val > maxVal) maxVal = val;
            return {
                x: date,
                y: val !== null ? parseFloat(val.toFixed(2)) : null
            };
        });
        
        return {
            name: `${unit.name} (${unit.pcode})`,
            data: dataPoints
        };
    });
    
    // Dynamically adjust height depending on number of admin units
    const chartHeight = Math.max(300, data.adm1_units.length * 28 + 60);
    
    const options = {
        series: series,
        chart: {
            height: chartHeight,
            type: 'heatmap',
            toolbar: { show: true },
            animations: { enabled: false },
            background: 'transparent'
        },
        stroke: { width: 0 },
        dataLabels: { enabled: false },
        plotOptions: {
            heatmap: {
                radius: 0,
                enableShades: true,
                shadeIntensity: 0.6,
                colorScale: {
                    ranges: getHeatmapColorScale(metric, maxVal)
                }
            }
        },
        theme: { mode: 'dark' },
        xaxis: {
            type: 'category',
            labels: {
                rotate: -90,
                rotateAlways: true,
                style: { fontSize: '9px', fontFamily: 'Inter' }
            }
        },
        yaxis: {
            labels: {
                style: { fontSize: '9px', fontFamily: 'Inter' }
            }
        },
        tooltip: {
            custom: function({ series, seriesIndex, dataPointIndex, w }) {
                const rowName = w.config.series[seriesIndex].name;
                const timeLabel = w.globals.labels[dataPointIndex];
                const value = w.config.series[seriesIndex].data[dataPointIndex].y;
                const formattedVal = value !== null ? value : 'N/A';
                return `
                    <div style="padding: 8px 12px; background: rgba(15, 23, 42, 0.95); border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; color: white; font-family: Inter; font-size: 11px;">
                        <div style="font-weight: 700; font-family: Outfit; font-size: 12px; color: #a5b4fc; margin-bottom: 4px;">${rowName}</div>
                        <div>Periodo: <span style="font-weight: 600;">${timeLabel}</span></div>
                        <div>Valore: <span style="font-weight: 600; color: #10b981;">${formattedVal}</span></div>
                    </div>
                `;
            }
        }
    };
    
    if (countrySpatiotemporalChart) {
        countrySpatiotemporalChart.destroy();
    }
    countrySpatiotemporalChart = new ApexCharts(container, options);
    countrySpatiotemporalChart.render();
}

// Chronological sorting for string dates
function sortedDatesList(arr) {
    return arr.sort((a, b) => {
        return new Date(a + "-01") - new Date(b + "-01");
    });
}

// Global chart references
let globalSpatiotemporalChart = null;
let countrySpatiotemporalChart = null;


// ======================================================================
// TSA DIAGNOSTICS INTEGRATION
// ======================================================================

const TSA_BASE_PATH = '../TSA/results';

const TSA_DIAGNOSTIC_FILES = {
    'stl': '01_Statistical_Decomposition_STL.png',
    'acf': '02_Autocorrelation_ACF_PACF.png',
    'acf_compare': '02b_Compare_Series_Autocorrelation.png',
    'ccf': '02c_Cross_Correlation_with_Target.png',
    'matrix_profile': '04_Matrix_Profile_Anomalies_Discords.png',
    'forecast': '05_MultiModel_Forecast_Comparison.png',
    'aic_bic': '05b_SARIMAX_AIC_BIC_Evaluation.png',
    'residuals': '06_Model_Residuals_Diagnostics.png'
};

const TSA_DIAGNOSTIC_TITLES = {
    'stl': 'Decomposizione Stagionale (STL) — Trend, Stagionalità e Residuo',
    'acf': 'Funzione di Autocorrelazione (ACF) e Parziale (PACF)',
    'acf_compare': 'Autocorrelazione Comparata di Tutte le Variabili',
    'ccf': 'Cross-Correlazione dei Predittori con il Target IPC',
    'matrix_profile': 'Anomalie e Pattern via Matrix Profile',
    'forecast': 'Confronto Previsioni Multi-Modello',
    'aic_bic': 'Valutazione Parametri SARIMAX (AIC/BIC)',
    'residuals': 'Diagnostica dei Residui del Modello'
};

// Cache for TSA diagnostic directory listings per country
const tsaDiagCache = {};

function renderTsaDiagnostics() {
    const code = state.selectedCountry;
    if (!code) return;
    
    // Populate region selector
    populateTsaRegionSelector(code);
    
    // Render selected diagnostic
    renderTsaDiagnosticImage();
    
    // Load Granger causality table
    loadTsaGrangerTable();
    
    // Load forecast metrics table
    loadTsaMetricsTable();
    
    // Load clustering images
    loadTsaClusteringImages();
}

function populateTsaRegionSelector(countryCode) {
    const selector = document.getElementById('tsa-region-selector');
    if (!selector) return;
    
    const currentVal = selector.value;
    selector.innerHTML = '<option value="national">Nazionale (Aggregato)</option>';
    
    // Try to get region list from the country data cache
    const data = countryCache[countryCode];
    if (data && data.regions && data.regions.adm1) {
        const pcodes = Object.keys(data.regions.adm1).sort();
        pcodes.forEach(pcode => {
            // Try to find the region name from trends
            let name = pcode;
            const adm1Trends = data.regions.adm1[pcode];
            if (adm1Trends && adm1Trends.length > 0 && adm1Trends[0].adm1_name) {
                name = adm1Trends[0].adm1_name;
            }
            const opt = document.createElement('option');
            opt.value = pcode;
            opt.textContent = `${name} (${pcode})`;
            selector.appendChild(opt);
        });
    }
    
    // Restore previous selection if valid
    if (currentVal) {
        const exists = Array.from(selector.options).some(o => o.value === currentVal);
        if (exists) selector.value = currentVal;
    }
}

function getTsaDiagnosticPath(countryCode, regionValue, diagnosticKey) {
    const filename = TSA_DIAGNOSTIC_FILES[diagnosticKey];
    if (!filename) return null;
    
    if (regionValue === 'national') {
        return `${TSA_BASE_PATH}/${countryCode}/national/${filename}`;
    } else {
        // Need to find the diagnostics subfolder name for this pcode
        // Convention: {COUNTRY}_{RegionName}_{PCode}
        // We'll search by pcode suffix
        return `${TSA_BASE_PATH}/${countryCode}/diagnostics/${regionValue}/${filename}`;
    }
}

function renderTsaDiagnosticImage() {
    const container = document.getElementById('tsa-diagnostic-image-container');
    if (!container) return;
    
    const code = state.selectedCountry;
    const regionSelector = document.getElementById('tsa-region-selector');
    const diagSelector = document.getElementById('tsa-diagnostic-selector');
    if (!code || !regionSelector || !diagSelector) return;
    
    const regionValue = regionSelector.value;
    const diagKey = diagSelector.value;
    const title = TSA_DIAGNOSTIC_TITLES[diagKey] || '';
    
    // For regional diagnostics, we need to find the folder name
    // The folder name pattern: {COUNTRY}_{RegionName}_{PCode}
    // We must scan via an approach that works in browser
    let imgPath;
    if (regionValue === 'national') {
        imgPath = `${TSA_BASE_PATH}/${code}/national/${TSA_DIAGNOSTIC_FILES[diagKey]}`;
    } else {
        // Use a cached folder name or try to discover it
        const folderName = findTsaDiagFolder(code, regionValue);
        if (folderName) {
            imgPath = `${TSA_BASE_PATH}/${code}/diagnostics/${folderName}/${TSA_DIAGNOSTIC_FILES[diagKey]}`;
        } else {
            imgPath = `${TSA_BASE_PATH}/${code}/diagnostics/${code}_${regionValue}/${TSA_DIAGNOSTIC_FILES[diagKey]}`;
        }
    }
    
    container.innerHTML = `
        <div style="font-size: 0.85rem; font-weight: 600; color: var(--text-secondary); margin-bottom: 0.5rem; text-align: center;">
            ${title}
        </div>
        <img src="${imgPath}" alt="${title}" 
             style="width: 100%; max-width: 1000px; border-radius: 8px; border: 1px solid var(--border-color);" 
             loading="lazy"
             onerror="this.parentElement.innerHTML='<div style=\'color: var(--text-muted); padding: 2rem; text-align: center;\'><i class=\'fa-solid fa-triangle-exclamation\' style=\'font-size: 2rem; margin-bottom: 0.5rem; display: block; opacity: 0.4;\'></i>Diagnostica non disponibile per questa regione.<br><span style=\'font-size: 0.72rem; opacity: 0.6;\'>Eseguire prima la pipeline TSA su questo paese.</span></div>'">
    `;
}

function findTsaDiagFolder(countryCode, pcode) {
    // Check cache
    if (tsaDiagCache[countryCode]) {
        const folders = tsaDiagCache[countryCode];
        const match = folders.find(f => f.endsWith('_' + pcode) || f.includes('_' + pcode));
        return match || null;
    }
    
    // Try to discover by attempting common naming conventions
    // The data cache might have region names
    const data = countryCache[countryCode];
    if (data && data.regions && data.regions.adm1 && data.regions.adm1[pcode]) {
        const trends = data.regions.adm1[pcode];
        if (trends.length > 0 && trends[0].adm1_name) {
            const regionName = trends[0].adm1_name.replace(/[\s/]+/g, '_').replace(/[^a-zA-Z0-9_]/g, '');
            return `${countryCode}_${regionName}_${pcode}`;
        }
    }
    return null;
}

function onTsaRegionChange() {
    renderTsaDiagnosticImage();
    loadTsaGrangerTable();
    loadTsaMetricsTable();
}

function onTsaDiagnosticChange() {
    renderTsaDiagnosticImage();
}

function loadTsaGrangerTable() {
    const container = document.getElementById('tsa-granger-table-container');
    if (!container) return;
    
    const code = state.selectedCountry;
    const regionSelector = document.getElementById('tsa-region-selector');
    if (!code || !regionSelector) return;
    
    const regionValue = regionSelector.value;
    let csvPath;
    if (regionValue === 'national') {
        csvPath = `${TSA_BASE_PATH}/${code}/national/03_Multivariate_Granger_Causality.csv`;
    } else {
        const folderName = findTsaDiagFolder(code, regionValue);
        csvPath = `${TSA_BASE_PATH}/${code}/diagnostics/${folderName || (code + '_' + regionValue)}/03_Multivariate_Granger_Causality.csv`;
    }
    
    fetch(csvPath)
        .then(res => {
            if (!res.ok) throw new Error('Not found');
            return res.text();
        })
        .then(csv => {
            const rows = csv.trim().split('\n').map(r => r.split(','));
            if (rows.length < 2) {
                container.innerHTML = '<div style="color: var(--text-muted); padding: 1rem; text-align: center; font-size: 0.8rem;">Nessun dato causalità disponibile</div>';
                return;
            }
            const headers = rows[0];
            let html = '<table style="width: 100%; border-collapse: collapse; font-size: 0.78rem;">';
            html += '<thead><tr>';
            headers.forEach(h => {
                html += `<th style="padding: 0.5rem 0.75rem; text-align: left; border-bottom: 2px solid var(--border-color); color: var(--text-secondary); font-weight: 700; text-transform: uppercase; font-size: 0.7rem;">${h.trim()}</th>`;
            });
            html += '</tr></thead><tbody>';
            for (let i = 1; i < rows.length; i++) {
                const cells = rows[i];
                const pVal = parseFloat(cells[1]);
                const isSignificant = pVal < 0.05;
                const rowBg = isSignificant ? 'rgba(16, 185, 129, 0.08)' : 'transparent';
                html += `<tr style="background: ${rowBg}; border-bottom: 1px solid var(--border-color);">`;
                cells.forEach((c, idx) => {
                    let cellStyle = 'padding: 0.5rem 0.75rem; color: white;';
                    if (idx === 1) {
                        cellStyle += isSignificant ? ' color: #10b981; font-weight: 700;' : ' color: #ef4444;';
                    }
                    html += `<td style="${cellStyle}">${c.trim()}</td>`;
                });
                html += '</tr>';
            }
            html += '</tbody></table>';
            container.innerHTML = html;
        })
        .catch(() => {
            container.innerHTML = '<div style="color: var(--text-muted); padding: 1rem; text-align: center; font-size: 0.8rem;">Nessun dato causalità disponibile per questa regione</div>';
        });
}

function loadTsaMetricsTable() {
    const container = document.getElementById('tsa-metrics-table-container');
    if (!container) return;
    
    const code = state.selectedCountry;
    const regionSelector = document.getElementById('tsa-region-selector');
    if (!code || !regionSelector) return;
    
    const regionValue = regionSelector.value;
    let csvPath;
    if (regionValue === 'national') {
        csvPath = `${TSA_BASE_PATH}/${code}/national/05_MultiModel_Forecast_Comparison.csv`;
    } else {
        const folderName = findTsaDiagFolder(code, regionValue);
        csvPath = `${TSA_BASE_PATH}/${code}/diagnostics/${folderName || (code + '_' + regionValue)}/05_MultiModel_Forecast_Comparison.csv`;
    }
    
    fetch(csvPath)
        .then(res => {
            if (!res.ok) throw new Error('Not found');
            return res.text();
        })
        .then(csv => {
            const rows = csv.trim().split('\n').map(r => r.split(','));
            if (rows.length < 2) {
                container.innerHTML = '<div style="color: var(--text-muted); padding: 1rem; text-align: center; font-size: 0.8rem;">Nessun dato metriche disponibile</div>';
                return;
            }
            const headers = rows[0];
            let html = '<table style="width: 100%; border-collapse: collapse; font-size: 0.78rem;">';
            html += '<thead><tr>';
            headers.forEach(h => {
                html += `<th style="padding: 0.5rem 0.75rem; text-align: left; border-bottom: 2px solid var(--border-color); color: var(--text-secondary); font-weight: 700; text-transform: uppercase; font-size: 0.7rem;">${h.trim()}</th>`;
            });
            html += '</tr></thead><tbody>';
            
            // Find best model (lowest MAE)
            let bestIdx = 1;
            let bestMae = Infinity;
            for (let i = 1; i < rows.length; i++) {
                const mae = parseFloat(rows[i][1]);
                if (!isNaN(mae) && mae < bestMae) {
                    bestMae = mae;
                    bestIdx = i;
                }
            }
            
            for (let i = 1; i < rows.length; i++) {
                const cells = rows[i];
                const isBest = i === bestIdx;
                const rowBg = isBest ? 'rgba(99, 102, 241, 0.12)' : 'transparent';
                html += `<tr style="background: ${rowBg}; border-bottom: 1px solid var(--border-color);">`;
                cells.forEach((c, idx) => {
                    let cellStyle = 'padding: 0.5rem 0.75rem; color: white;';
                    if (isBest && idx === 0) cellStyle += ' font-weight: 700; color: #818cf8;';
                    const val = c.trim();
                    const numVal = parseFloat(val);
                    const displayVal = (!isNaN(numVal) && idx > 0) ? numVal.toFixed(4) : val;
                    html += `<td style="${cellStyle}">${displayVal}${isBest && idx === 0 ? ' ⭐' : ''}</td>`;
                });
                html += '</tr>';
            }
            html += '</tbody></table>';
            container.innerHTML = html;
        })
        .catch(() => {
            container.innerHTML = '<div style="color: var(--text-muted); padding: 1rem; text-align: center; font-size: 0.8rem;">Nessun dato metriche disponibile per questa regione</div>';
        });
}

function loadTsaClusteringImages() {
    const container = document.getElementById('tsa-clustering-container');
    if (!container) return;
    
    const code = state.selectedCountry;
    if (!code) return;
    
    const clusteringFiles = [
        { file: 'Hierarchical_Dendrogram_Shape.png', title: 'Dendrogramma Shape-Based (DTW)' },
        { file: 'Hierarchical_Dendrogram_Features.png', title: 'Dendrogramma Feature-Based' },
        { file: 'Cluster_Map_Admin1.png', title: 'Mappa Cluster Admin1' },
        { file: 'Feature_Based_PCA_Scatter.png', title: 'PCA Scatter delle Province' }
    ];
    
    let html = '';
    clusteringFiles.forEach(cf => {
        const path = `${TSA_BASE_PATH}/${code}/clustering/${cf.file}`;
        html += `
            <div style="text-align: center;">
                <div style="font-size: 0.75rem; color: var(--text-secondary); font-weight: 600; margin-bottom: 0.5rem;">${cf.title}</div>
                <img src="${path}" alt="${cf.title}" 
                     style="width: 100%; border-radius: 8px; border: 1px solid var(--border-color);" 
                     loading="lazy"
                     onerror="this.parentElement.style.display='none';">
            </div>
        `;
    });
    container.innerHTML = html;
}

function loadTsaGlobalPanel() {
    if (typeof renderGlobalClusteringMaps === 'function') {
        renderGlobalClusteringMaps();
    }
    
    const basePath = "../TS/TSclusters/results";
    
    const mappings = [
        { id: 'tsa-global-dendro-shape', file: 'national_univariate/national_univariate_evaluation_metrics.png' },
        { id: 'tsa-global-dendro-ncd', file: 'national_univariate/k_2/strategy_similarity_heatmap.png' },
        { id: 'tsa-global-heatmap-dtw', file: 'national_univariate/k_2/dtw_hierarchical/crosstab_ipc.png' },
        { id: 'tsa-global-heatmap-ncd', file: 'national_univariate/k_2/dtw_hierarchical/medoids.png' },
        { id: 'tsa-global-pca-national', file: 'national_multivariate/k_3/multivariate_dtw_hierarchical/pca.png' },
        { id: 'tsa-global-pca-regions', file: 'national_multivariate/k_3/multivariate_dtw_hierarchical/umap.png' },
        { id: 'tsa-global-regions-map-hierarchical', file: 'national_multivariate/k_3/multivariate_dtw_hierarchical/map.png' },
        { id: 'tsa-global-regions-map-kmeans', file: 'national_multivariate/k_3/multivariate_kmeans/map.png' }
    ];
    
    mappings.forEach(m => {
        const img = document.getElementById(m.id);
        if (img) {
            img.src = `${basePath}/${m.file}`;
            img.onerror = function() {
                this.style.display = 'none';
            };
        }
    });
}

// ── GDELT VIEW TOGGLE & SEPARATE EXPORTS ──

function toggleGdeltView(containerId, mode) {
    state.gdeltViewModes = state.gdeltViewModes || {};
    state.gdeltViewModes[containerId] = mode;
    
    // Update active button styling in DOM
    const card = document.getElementById(containerId)?.closest('.glass-card');
    if (card) {
        card.querySelectorAll('.gdelt-toggle-btn').forEach(btn => {
            if (btn.dataset.mode === mode) {
                btn.style.background = 'rgba(99, 102, 241, 0.4)';
                btn.style.color = '#fff';
                btn.style.borderColor = 'rgba(99, 102, 241, 0.6)';
            } else {
                btn.style.background = 'rgba(15, 23, 42, 0.4)';
                btn.style.color = 'rgba(255, 255, 255, 0.5)';
                btn.style.borderColor = 'rgba(255, 255, 255, 0.1)';
            }
        });
    }
    
    // Re-render target chart
    if (containerId === 'chart-gdelt') {
        const trends = typeof getFilteredTrends === 'function' ? getFilteredTrends() : (state.countryData?.trends?.national || []);
        renderGdeltChart(trends);
    } else if (containerId === 'chart-gdelt-tab-salience') {
        const trends = typeof getFilteredTrends === 'function' ? getFilteredTrends() : (state.countryData?.trends?.national || []);
        renderGdeltTab(trends);
    }
}

// ── TRIGGER ALL COUNTRY SECTION SAVES (EXPORT MASTER ARCHIVE & SECTION ZIPS) ──

function triggerAllCountrySectionSaves() {
    const code = state.activeMapCountry || 'AFG';
    const sectionIds = ['charts', 'ipc', 'acled', 'idp', 'rainfall', 'ndvi', 'gdelt'];
    
    // 1. Download Master TSA HTML archive (contains all HTMLs of the country)
    const tsaBtn = document.getElementById('tsa-download-all-zip-btn');
    if (tsaBtn && tsaBtn.href) {
        const a = document.createElement('a');
        a.href = tsaBtn.href;
        a.download = tsaBtn.getAttribute('download') || `Grafici_HTML_${code}.zip`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    }
    
    // 2. Sequentially trigger all section ZIP archives so every section is saved
    sectionIds.forEach((id, index) => {
        setTimeout(() => {
            const btn = document.getElementById(`btn-dl-zip-${id}`);
            if (btn && btn.href) {
                const a = document.createElement('a');
                a.href = btn.href;
                a.download = btn.getAttribute('download') || `Grafici_${id}_${code}.zip`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
            }
        }, (index + 1) * 350);
    });
}

// ── INTERACTIVE CHART EXPORT DELEGATE (DUAL EXPORT FOR GDELT) ──

window.exportInteractiveChart = function(configToExport, containerId) {
    if (!configToExport.chart) configToExport.chart = {};
    configToExport.chart.background = '#0f172a';
    if (!configToExport.chart.toolbar) configToExport.chart.toolbar = {};
    configToExport.chart.toolbar.show = true;

    function downloadHtmlBlob(config, filename) {
        const htmlContent = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>${config.title?.text || 'HERO v6 Chart Export'}</title>
    <script src="https://cdn.jsdelivr.net/npm/apexcharts"><\/script>
    <style>
        body { background-color: #0f172a; color: white; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; font-family: sans-serif; padding: 20px; box-sizing: border-box; }
        #chart { width: 100%; max-width: 1200px; background: #1e293b; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
    </style>
</head>
<body>
    <div id="chart"></div>
    <script>
        var options = ${JSON.stringify(config)};
        var chart = new ApexCharts(document.querySelector("#chart"), options);
        chart.render();
    <\/script>
</body>
</html>`;
        const blob = new Blob([htmlContent], { type: 'text/html' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    if (containerId === 'chart-gdelt' || containerId === 'chart-gdelt-tab-salience') {
        const code = state.activeMapCountry || 'AFG';
        const isTab = (containerId === 'chart-gdelt-tab-salience');
        
        // 1. Istogramma (Eventi / Menzioni)
        const histConfig = JSON.parse(JSON.stringify(configToExport));
        histConfig.series = (histConfig.series || []).filter(s => s.type === 'column' || (!s.type && !String(s.name).toLowerCase().includes('tono') && !String(s.name).toLowerCase().includes('eventi conflitto')));
        if (histConfig.yaxis && Array.isArray(histConfig.yaxis)) {
            histConfig.yaxis = [histConfig.yaxis[0]];
        }
        histConfig.title = { text: isTab ? `Salienza Mediatica GDELT (Istogramma Menzioni) - ${code}` : `Instabilità GDELT (Istogramma Eventi) - ${code}`, style: { color: '#fff', fontSize: '16px' } };
        downloadHtmlBlob(histConfig, isTab ? `gdelt_salienza_istogramma_menzioni_${code}.html` : `gdelt_instabilita_istogramma_eventi_${code}.html`);
        
        // 2. Linegraph (Tono / Volume Eventi Reali)
        setTimeout(() => {
            const lineConfig = JSON.parse(JSON.stringify(configToExport));
            lineConfig.series = (lineConfig.series || []).filter(s => s.type === 'line' || String(s.name).toLowerCase().includes('tono') || String(s.name).toLowerCase().includes('eventi conflitto'));
            if (lineConfig.yaxis && Array.isArray(lineConfig.yaxis) && lineConfig.yaxis.length > 1) {
                lineConfig.yaxis = [{ ...lineConfig.yaxis[1], opposite: false }];
            }
            lineConfig.title = { text: isTab ? `Salienza Mediatica GDELT (Linegraph Eventi Reali) - ${code}` : `Instabilità GDELT (Linegraph Tono) - ${code}`, style: { color: '#fff', fontSize: '16px' } };
            downloadHtmlBlob(lineConfig, isTab ? `gdelt_salienza_linegraph_eventi_${code}.html` : `gdelt_instabilita_linegraph_tono_${code}.html`);
        }, 400);
    } else {
        const defaultName = (configToExport.title?.text ? configToExport.title.text.replace(/[^a-z0-9]/gi, '_').toLowerCase() : (containerId || 'interactive_chart')) + '.html';
        downloadHtmlBlob(configToExport, defaultName);
    }
};


