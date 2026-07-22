const metricSelect = document.getElementById('metricSelectCompare');
const lagSelect = document.getElementById('lagSelectCompare');
const loadingMsg = document.getElementById('loadingMsg');
const plotCompare = document.getElementById('plotCompare');

const countries = ['AFG', 'SSD', 'COD'];
const colors = ['#38bdf8', '#ef4444', '#22c55e'];
const datasets = {};

async function loadAllData() {
    let allLoaded = true;
    for (let c of countries) {
        try {
            const res = await fetch(`data/network_data_${c}.json?v=${new Date().getTime()}`); // Cache bust
            if (res.ok) {
                datasets[c] = await res.json();
            } else {
                allLoaded = false;
            }
        } catch (e) {
            allLoaded = false;
        }
    }
    
    if (Object.keys(datasets).length > 0) {
        loadingMsg.style.display = 'none';
        plotCompare.style.display = 'block';
        drawComparison();
    } else {
        loadingMsg.innerHTML = `<i class="fa-solid fa-triangle-exclamation" style="color:#ef4444;"></i><br><br>Impossibile caricare i file JSON.<br><small>Devi prima eseguire lo script Python per generare i dati di AFG, SSD e COD.</small>`;
    }
}

function drawComparison() {
    const metric = metricSelect.value;
    const lag = parseInt(lagSelect.value);
    
    const plotData = [];
    
    countries.forEach((c, i) => {
        if(!datasets[c]) return;
        
        const edges = datasets[c].edges;
        const weights = [];
        
        edges.forEach(e => {
            if (e.lag === lag && e.metrics[metric]) {
                weights.push(e.metrics[metric].val);
            }
        });
        
        if (weights.length > 0) {
            plotData.push({
                x: weights,
                type: 'histogram',
                name: c,
                opacity: 0.6,
                marker: { color: colors[i] },
                histnorm: 'probability density', // KDE-like
                xbins: { size: 0.05 }
            });
        }
    });
    
    const layout = {
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        font: { color: '#94a3b8', family: 'Outfit', size: 12 },
        margin: { t: 30, b: 40, l: 50, r: 20 },
        autosize: true,
        barmode: 'overlay',
        title: { text: `Distribuzione Pesi (${metric} - Lag ${lag})`, font: { color: '#f8fafc', size: 16 } },
        xaxis: { title: 'Weight', showgrid: true, gridcolor: 'rgba(255,255,255,0.05)' },
        yaxis: { title: 'Density', showgrid: true, gridcolor: 'rgba(255,255,255,0.05)' },
        legend: { font: { color: '#f8fafc' } }
    };
    
    Plotly.newPlot('plotCompare', plotData, layout, {displayModeBar: false, responsive: true});
}

metricSelect.addEventListener('change', drawComparison);
lagSelect.addEventListener('change', drawComparison);

// Init
loadAllData();
