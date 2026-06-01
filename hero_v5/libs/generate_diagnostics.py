import os
import sys
import json
import logging
import re
import pandas as pd
import numpy as np
import geopandas as gpd
from pathlib import Path
import time

def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)
    return logger

logger = setup_logger("generate_diagnostics")

def normalize_name(name) -> str:
    if pd.isna(name):
        return ""
    name_str = str(name).lower().strip()
    name_str = re.sub(r'[^a-z0-9\s]', '', name_str)
    name_str = re.sub(r'\s+', ' ', name_str)
    return name_str.strip()

def main():
    t0 = time.time()
    logger.info("==================================================")
    logger.info("AVVIO GENERAZIONE STRUMENTO DIAGNOSTICO HERO v5")
    logger.info("==================================================")
    
    workspace_dir = Path(__file__).resolve().parent.parent.parent
    data_dir = workspace_dir / "hero_v5" / "data"
    boundaries_dir = data_dir / "boundaries"
    plots_dir = workspace_dir / "hero_v5" / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)
    
    reconciled_path = data_dir / "hero_v5_reconciled.parquet"
    wfp_path = data_dir / "wfp_with_pcodes.parquet"
    rain_path = workspace_dir / "rainfall" / "data" / "clean_rainfall" / "rainfall_monthly.parquet"
    ipc_base_path = workspace_dir / "ipc_rain_conflict_idp.parquet"
    
    if not reconciled_path.exists() or not wfp_path.exists() or not rain_path.exists():
        logger.error("File richiesti mancanti per la diagnostica. Verifica la presenza dei parquet.")
        return
        
    logger.info("Caricamento dati...")
    df_rec = pd.read_parquet(reconciled_path)
    df_wfp = pd.read_parquet(wfp_path)
    df_rain = pd.read_parquet(rain_path)
    df_ipc = pd.read_parquet(ipc_base_path)
    
    logger.info("Esplosione delle date dell'IPC per calcolo accoppiamento inverso (duale)...")
    # Date di inizio e fine dell'IPC
    df_ipc['date_from'] = pd.to_datetime(df_ipc['From'])
    df_ipc['date_to'] = pd.to_datetime(df_ipc['To'])
    
    # PCodes standardizzazione
    for col in ["adm1_pcode", "adm2_pcode"]:
        df_ipc[col] = df_ipc[col].fillna("").astype(str).str.strip()
        df_ipc.loc[df_ipc[col] == "nan", col] = ""
        
    df_ipc["is_true_admin2"] = (
        (df_ipc["adm2_pcode"] != "") & 
        (df_ipc["adm1_pcode"] != "") & 
        (df_ipc["adm2_pcode"] != df_ipc["adm1_pcode"])
    )
    
    # Esplosione temporale in mesi per joins rapidi
    df_ipc_months = df_ipc.copy()
    df_ipc_months['date'] = df_ipc_months.apply(
        lambda r: pd.date_range(start=r['date_from'], end=r['date_to'], freq='MS'),
        axis=1
    )
    df_ipc_months = df_ipc_months.explode('date').dropna(subset=['date'])
    df_ipc_months['date'] = pd.to_datetime(df_ipc_months['date'])
    df_ipc_months['norm_adm1'] = df_ipc_months['Level 1'].apply(normalize_name)
    
    # ── ANALISI WFP DUALE (Accoppiamento WFP -> IPC) ──────────────────────────
    logger.info("Valutazione accoppiamento duale WFP...")
    df_wfp['date'] = pd.to_datetime(df_wfp['date'])
    df_wfp['norm_adm1'] = df_wfp['adm1_name'].apply(normalize_name)
    
    # 1. Match Admin2
    ipc_a2 = df_ipc_months[df_ipc_months['is_true_admin2']][['Country', 'adm2_pcode', 'date']].drop_duplicates()
    ipc_a2['matched_a2'] = True
    df_wfp_m = df_wfp.merge(ipc_a2, left_on=['ISO3', 'adm2_pcode', 'date'], right_on=['Country', 'adm2_pcode', 'date'], how='left')
    df_wfp_m = df_wfp_m.drop(columns=['Country'], errors='ignore')
    
    # 2. Match Admin1 Code
    ipc_a1 = df_ipc_months[['Country', 'adm1_pcode', 'date']].drop_duplicates()
    ipc_a1['matched_a1'] = True
    df_wfp_m = df_wfp_m.merge(ipc_a1, left_on=['ISO3', 'adm1_pcode', 'date'], right_on=['Country', 'adm1_pcode', 'date'], how='left')
    df_wfp_m = df_wfp_m.drop(columns=['Country'], errors='ignore')
    
    # 3. Match Admin1 Name
    ipc_a1_name = df_ipc_months[['Country', 'norm_adm1', 'date']].drop_duplicates()
    ipc_a1_name['matched_a1_name'] = True
    df_wfp_m = df_wfp_m.merge(ipc_a1_name, left_on=['ISO3', 'norm_adm1', 'date'], right_on=['Country', 'norm_adm1', 'date'], how='left')
    df_wfp_m = df_wfp_m.drop(columns=['Country'], errors='ignore')
    
    # 4. Match National
    ipc_nat = df_ipc_months[['Country', 'date']].drop_duplicates()
    ipc_nat['matched_nat'] = True
    df_wfp_m = df_wfp_m.merge(ipc_nat, left_on=['ISO3', 'date'], right_on=['Country', 'date'], how='left')
    df_wfp_m = df_wfp_m.drop(columns=['Country'], errors='ignore')
    
    # Calcolo match level WFP
    df_wfp_m['match_level'] = 'Unmatched'
    df_wfp_m.loc[df_wfp_m['matched_nat'] == True, 'match_level'] = 'National'
    df_wfp_m.loc[df_wfp_m['matched_a1_name'] == True, 'match_level'] = 'Admin1_Name'
    df_wfp_m.loc[df_wfp_m['matched_a1'] == True, 'match_level'] = 'Admin1_Code'
    df_wfp_m.loc[df_wfp_m['matched_a2'] == True, 'match_level'] = 'Admin2'
    
    # ── ANALISI RAINFALL DUALE (Accoppiamento Rain -> IPC) ──────────────────
    logger.info("Valutazione accoppiamento duale Rainfall...")
    df_rain['date'] = pd.to_datetime(df_rain['date'])
    df_rain['month_start'] = df_rain['date'].dt.to_period('M').dt.to_timestamp()
    
    # 1. Match Admin2
    df_rain_m = df_rain.merge(ipc_a2, left_on=['ISO3', 'PCODE', 'month_start'], right_on=['Country', 'adm2_pcode', 'date'], how='left')
    df_rain_m = df_rain_m.drop(columns=['Country', 'date_y'], errors='ignore').rename(columns={'date_x': 'date'})
    
    # 2. Match Admin1 Code
    df_rain_m = df_rain_m.merge(ipc_a1, left_on=['ISO3', 'PCODE', 'month_start'], right_on=['Country', 'adm1_pcode', 'date'], how='left')
    df_rain_m = df_rain_m.drop(columns=['Country', 'date_y'], errors='ignore').rename(columns={'date_x': 'date'})
    
    # 3. Match National
    df_rain_m = df_rain_m.merge(ipc_nat, left_on=['ISO3', 'month_start'], right_on=['Country', 'date'], how='left')
    df_rain_m = df_rain_m.drop(columns=['Country', 'date_y'], errors='ignore').rename(columns={'date_x': 'date'})
    
    # Calcolo match level Rainfall
    df_rain_m['match_level'] = 'Unmatched'
    df_rain_m.loc[df_rain_m['matched_nat'] == True, 'match_level'] = 'National'
    df_rain_m.loc[(df_rain_m['matched_a1'] == True) & (df_rain_m['adm_level'] == 1), 'match_level'] = 'Admin1'
    df_rain_m.loc[(df_rain_m['matched_a2'] == True) & (df_rain_m['adm_level'] == 2), 'match_level'] = 'Admin2'
    
    # ── ANALISI GEOJSON DUALE (Confini -> IPC) ──────────────────────────────
    logger.info("Valutazione accoppiamento duale confini GeoJSON...")
    boundary_pcodes_adm1 = set()
    boundary_pcodes_adm2 = set()
    
    # Trova PCodes nei file GeoJSON
    def standardize_pcode_col(gdf, level):
        for col in gdf.columns:
            if f"adm{level}" in str(col).lower() and "pco" in str(col).lower():
                return gdf.rename(columns={col: f"adm{level}_pcode"})
        for col in gdf.columns:
            if "pcode" in str(col).lower() and str(level) in str(col).lower():
                return gdf.rename(columns={col: f"adm{level}_pcode"})
        return gdf

    for folder in boundaries_dir.glob("*"):
        if folder.is_dir():
            iso3 = folder.name.upper()
            # Admin 1
            for f in folder.rglob("*.geojson"):
                if "adm1" in f.name.lower() or "admin1" in f.name.lower():
                    try:
                        gdf = gpd.read_file(f)
                        gdf = standardize_pcode_col(gdf, 1)
                        if "adm1_pcode" in gdf.columns:
                            boundary_pcodes_adm1.update(gdf["adm1_pcode"].dropna().unique())
                    except Exception:
                        pass
                # Admin 2
                if "adm2" in f.name.lower() or "admin2" in f.name.lower():
                    try:
                        gdf = gpd.read_file(f)
                        gdf = standardize_pcode_col(gdf, 2)
                        if "adm2_pcode" in gdf.columns:
                            boundary_pcodes_adm2.update(gdf["adm2_pcode"].dropna().unique())
                    except Exception:
                        pass
                        
    boundary_pcodes = boundary_pcodes_adm1.union(boundary_pcodes_adm2)
    ipc_pcodes = set(df_ipc['adm1_pcode'].unique()).union(set(df_ipc['adm2_pcode'].unique()))
    
    logger.info(f"PCodes totali nei confini: {len(boundary_pcodes)}, PCodes nell'IPC: {len(ipc_pcodes)}")
    
    # ── DIAGNOSTICA COMPLETA PER PAESE ──────────────────────────────────────
    logger.info("Raccolta statistiche di copertura e accoppiamento per paese...")
    indicators = ['has_geojson', 'has_rainfall', 'has_wfp', 'has_idp', 'has_acled_events', 'has_acled_fatalities']
    
    # Calcolo punteggio medio
    df_rec['avail_score'] = df_rec[indicators].sum(axis=1) / len(indicators) * 100
    df_rec['year_quarter'] = pd.to_datetime(df_rec['From']).dt.to_period('Q').astype(str)
    
    # Get sorted list of countries (alphabetically)
    country_order = sorted(df_rec['Country'].unique().tolist())
    # Get sorted list of dates
    date_order = sorted(df_rec['year_quarter'].unique().tolist())
    
    # Generazione dei datasets per le heatmap (Spazio-Tempo)
    heatmap_datasets = {}
    metrics_to_map = {
        'overall': 'avail_score',
        'geojson': 'has_geojson',
        'rainfall': 'has_rainfall',
        'wfp': 'has_wfp',
        'idp': 'has_idp',
        'acled_events': 'has_acled_events',
        'acled_fatalities': 'has_acled_fatalities'
    }
    
    for key, col in metrics_to_map.items():
        pivot_df = df_rec.pivot_table(index='Country', columns='year_quarter', values=col, aggfunc='mean')
        if col != 'avail_score':
            pivot_df = pivot_df * 100
        pivot_df = pivot_df.reindex(index=country_order, columns=date_order)
        # Sostituiamo NaNs con None (null in JSON)
        z_data = pivot_df.where(pd.notna(pivot_df), None).values.tolist()
        heatmap_datasets[key] = {
            'y': country_order,
            'x': date_order,
            'z': z_data
        }
        
    # Calcolo delle statistiche globali e nazionali per i grafici
    diagnostics_data = {
        "global": {
            "ipc_rows": len(df_rec),
            "geojson_pct": float(df_rec['has_geojson'].mean() * 100),
            "rainfall_pct": float(df_rec['has_rainfall'].mean() * 100),
            "wfp_pct": float(df_rec['has_wfp'].mean() * 100),
            "idp_pct": float(df_rec['has_idp'].mean() * 100),
            "acled_events_pct": float(df_rec['has_acled_events'].mean() * 100),
            "acled_fatalities_pct": float(df_rec['has_acled_fatalities'].mean() * 100),
            
            # WFP Match Breakdown
            "wfp_breakdown": {
                "Admin2": float((df_wfp_m['match_level'] == 'Admin2').mean() * 100),
                "Admin1_Code": float((df_wfp_m['match_level'] == 'Admin1_Code').mean() * 100),
                "Admin1_Name": float((df_wfp_m['match_level'] == 'Admin1_Name').mean() * 100),
                "National": float((df_wfp_m['match_level'] == 'National').mean() * 100),
                "Unmatched": float((df_wfp_m['match_level'] == 'Unmatched').mean() * 100)
            },
            # Rainfall Match Breakdown
            "rain_breakdown": {
                "Admin2": float((df_rain_m['match_level'] == 'Admin2').mean() * 100),
                "Admin1": float((df_rain_m['match_level'] == 'Admin1').mean() * 100),
                "National": float((df_rain_m['match_level'] == 'National').mean() * 100),
                "Unmatched": float((df_rain_m['match_level'] == 'Unmatched').mean() * 100)
            },
            # Boundary PCodes Breakdown
            "boundary_breakdown": {
                "Matched": float(len(boundary_pcodes.intersection(ipc_pcodes)) / max(1, len(boundary_pcodes)) * 100),
                "Unmatched": float(len(boundary_pcodes.difference(ipc_pcodes)) / max(1, len(boundary_pcodes)) * 100)
            }
        },
        "countries": {},
        "heatmaps": heatmap_datasets
    }
    
    # Calcolo statistiche specifiche per paese
    for country in sorted(country_order):
        df_c_rec = df_rec[df_rec['Country'] == country]
        df_c_wfp = df_wfp_m[df_wfp_m['ISO3'] == country]
        df_c_rain = df_rain_m[df_rain_m['ISO3'] == country]
        
        # Filtro PCodes del paese
        c_boundary_pcodes = {p for p in boundary_pcodes if str(p).startswith(country)}
        c_ipc_pcodes = set(df_c_rec['adm1_pcode'].unique()).union(set(df_c_rec['adm2_pcode'].unique()))
        
        diagnostics_data["countries"][country] = {
            "ipc_rows": len(df_c_rec),
            "geojson_pct": float(df_c_rec['has_geojson'].mean() * 100) if len(df_c_rec) > 0 else 0,
            "rainfall_pct": float(df_c_rec['has_rainfall'].mean() * 100) if len(df_c_rec) > 0 else 0,
            "wfp_pct": float(df_c_rec['has_wfp'].mean() * 100) if len(df_c_rec) > 0 else 0,
            "idp_pct": float(df_c_rec['has_idp'].mean() * 100) if len(df_c_rec) > 0 else 0,
            "acled_events_pct": float(df_c_rec['has_acled_events'].mean() * 100) if len(df_c_rec) > 0 else 0,
            "acled_fatalities_pct": float(df_c_rec['has_acled_fatalities'].mean() * 100) if len(df_c_rec) > 0 else 0,
            
            "wfp_breakdown": {
                "Admin2": float((df_c_wfp['match_level'] == 'Admin2').mean() * 100) if len(df_c_wfp) > 0 else 0,
                "Admin1_Code": float((df_c_wfp['match_level'] == 'Admin1_Code').mean() * 100) if len(df_c_wfp) > 0 else 0,
                "Admin1_Name": float((df_c_wfp['match_level'] == 'Admin1_Name').mean() * 100) if len(df_c_wfp) > 0 else 0,
                "National": float((df_c_wfp['match_level'] == 'National').mean() * 100) if len(df_c_wfp) > 0 else 0,
                "Unmatched": float((df_c_wfp['match_level'] == 'Unmatched').mean() * 100) if len(df_c_wfp) > 0 else 0
            },
            "rain_breakdown": {
                "Admin2": float((df_c_rain['match_level'] == 'Admin2').mean() * 100) if len(df_c_rain) > 0 else 0,
                "Admin1": float((df_c_rain['match_level'] == 'Admin1').mean() * 100) if len(df_c_rain) > 0 else 0,
                "National": float((df_c_rain['match_level'] == 'National').mean() * 100) if len(df_c_rain) > 0 else 0,
                "Unmatched": float((df_c_rain['match_level'] == 'Unmatched').mean() * 100) if len(df_c_rain) > 0 else 0
            },
            "boundary_breakdown": {
                "Matched": float(len(c_boundary_pcodes.intersection(c_ipc_pcodes)) / max(1, len(c_boundary_pcodes)) * 100) if len(c_boundary_pcodes) > 0 else 0,
                "Unmatched": float(len(c_boundary_pcodes.difference(c_ipc_pcodes)) / max(1, len(c_boundary_pcodes)) * 100) if len(c_boundary_pcodes) > 0 else 0
            }
        }
        
    # ── GENERAZIONE DASHBOARD DIAGNOSTICA HTML ──────────────────────────────
    logger.info("Scrittura file HTML per la Dashboard di Diagnostica...")
    
    html_template = """<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HERO v5 — Diagnostica Completa e Accoppiamento Duale</title>
    <!-- Tailwind CSS -->
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- Plotly.js -->
    <script src="https://cdn.plot.ly/plotly-2.24.1.min.js"></script>
    <!-- Google Fonts -->
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body {
            font-family: 'Inter', sans-serif;
            background-color: #0f172a;
            color: #f8fafc;
        }
        .glass-card {
            background: rgba(30, 41, 59, 0.7);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.05);
        }
        .custom-scroll::-webkit-scrollbar {
            width: 6px;
            height: 6px;
        }
        .custom-scroll::-webkit-scrollbar-track {
            background: #1e293b;
        }
        .custom-scroll::-webkit-scrollbar-thumb {
            background: #475569;
            border-radius: 4px;
        }
    </style>
</head>
<body class="min-h-screen p-4 md:p-6 flex flex-col custom-scroll">

    <!-- Header -->
    <header class="glass-card rounded-2xl p-5 mb-6 shadow-xl relative overflow-hidden flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div class="absolute -right-16 -top-16 w-48 h-48 bg-blue-600 opacity-20 rounded-full blur-3xl"></div>
        <div>
            <span class="text-xs font-semibold tracking-wider text-indigo-400 uppercase bg-indigo-500/10 px-3 py-1 rounded-full">DIAGNOSTICA AVANZATA</span>
            <h1 class="text-2xl md:text-3xl font-bold tracking-tight text-white mt-1.5">HERO v5 — Esploratore Armonizzazione Spazio-Temporale</h1>
            <p class="text-slate-400 text-xs mt-1">Diagnostica spaziale e temporale della copertura IPC e dell'accoppiamento inverso (duale) di WFP e Rainfall.</p>
        </div>
        
        <div class="flex items-center gap-3 bg-slate-800/80 border border-slate-700/80 px-4 py-2 rounded-xl z-10 w-full md:w-auto">
            <span class="text-slate-400 text-xs font-bold uppercase tracking-wider whitespace-nowrap">Paese Sotto Analisi:</span>
            <select id="country-selector" onchange="onCountryChange()" class="bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 flex-grow">
                <option value="global">Tutti i Paesi (Globale)</option>
            </select>
        </div>
    </header>

    <!-- Stat Cards Grid -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div class="glass-card rounded-xl p-4 shadow-md">
            <div class="text-slate-400 text-xs font-semibold">Record baseline IPC totali</div>
            <div class="text-2xl font-bold text-white mt-1.5" id="stat-ipc-rows">0</div>
            <p class="text-slate-500 text-[10px] mt-1">Righe IPC totali valutate nel tempo</p>
        </div>
        <div class="glass-card rounded-xl p-4 shadow-md">
            <div class="text-slate-400 text-xs font-semibold">Copertura IPC media</div>
            <div class="text-2xl font-bold text-indigo-400 mt-1.5" id="stat-ipc-cov">0%</div>
            <p class="text-slate-500 text-[10px] mt-1">Media di disponibilità di tutti i 6 indicatori</p>
        </div>
        <div class="glass-card rounded-xl p-4 shadow-md">
            <div class="text-slate-400 text-xs font-semibold">Tasso Accoppiamento WFP</div>
            <div class="text-2xl font-bold text-emerald-400 mt-1.5" id="stat-wfp-match">0%</div>
            <p class="text-slate-500 text-[10px] mt-1">% di prezzi WFP associati con successo a righe IPC</p>
        </div>
        <div class="glass-card rounded-xl p-4 shadow-md">
            <div class="text-slate-400 text-xs font-semibold">Tasso Accoppiamento Rain</div>
            <div class="text-2xl font-bold text-sky-400 mt-1.5" id="stat-rain-match">0%</div>
            <p class="text-slate-500 text-[10px] mt-1">% di griglie pioggia associate con successo a righe IPC</p>
        </div>
    </div>

    <!-- MAIN DIAGNOSTIC GRID -->
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch flex-grow">
        
        <!-- Left Panel: Coverage Plots (5 Columns) -->
        <div class="lg:col-span-5 flex flex-col gap-6">
            <!-- Plot A: Row Coverage -->
            <div class="glass-card rounded-2xl p-4 shadow-lg flex flex-col flex-grow min-h-[300px]">
                <h3 class="text-xs font-semibold text-slate-300 tracking-wider uppercase mb-3"><i class="fas fa-chart-bar text-indigo-400 mr-2"></i>Copertura Righe IPC (% di righe con dati)</h3>
                <div id="ipc-coverage-chart" class="w-full flex-grow"></div>
            </div>
            
            <!-- Plot B: Dual Unmatched Rates -->
            <div class="glass-card rounded-2xl p-4 shadow-lg flex flex-col flex-grow min-h-[300px]">
                <h3 class="text-xs font-semibold text-slate-300 tracking-wider uppercase mb-3"><i class="fas fa-unlink text-red-400 mr-2"></i>Analisi Duale: Dati Sorgente Accoppiati vs Persi (%)</h3>
                <div id="source-matching-chart" class="w-full flex-grow"></div>
            </div>
        </div>

        <!-- Right Panel: Heatmap Spazio-Temporale (7 Columns) -->
        <div class="lg:col-span-7 class-card flex flex-col glass-card rounded-2xl p-5 shadow-lg">
            <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 mb-4">
                <div>
                    <h2 class="text-base font-bold text-white"><i class="fas fa-th text-amber-400 mr-2"></i>Matrice di Diagnostica Spazio-Temporale</h2>
                    <p class="text-slate-400 text-xs">Completeness heatmap per ciascuna feature con zoom e date pulite sull'asse X.</p>
                </div>
                <div class="flex gap-2 w-full sm:w-auto">
                    <select id="heatmap-var-selector" onchange="renderHeatmap()" class="bg-slate-800 border border-slate-700 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 w-full">
                        <option value="overall">Punteggio Medio Completeness (%)</option>
                        <option value="geojson">Disponibilità GeoJSON (%)</option>
                        <option value="rainfall">Precipitazioni (CHIRPS) (%)</option>
                        <option value="wfp">Prezzi Alimentari (WFP) (%)</option>
                        <option value="idp">Sfoltati (IDP) (%)</option>
                        <option value="acled_events">Conflitti ACLED (Eventi) (%)</option>
                        <option value="acled_fatalities">Conflitti ACLED (Vittime) (%)</option>
                    </select>
                </div>
            </div>
            
            <div id="diagnostics-heatmap" class="w-full flex-grow min-h-[550px] bg-slate-900/10 rounded-xl overflow-hidden">
                <!-- Heatmap will be rendered here -->
            </div>
        </div>
    </div>

    <!-- Footer -->
    <footer class="mt-8 text-center text-xs text-slate-600">
        HERO Pipeline v5 Diagnostics Tool | Generato nel 2026
    </footer>

    <!-- Data Injection -->
    <script>
        const DIAG_DATA = __DIAG_DATA__;
    </script>

    <!-- Client Logic -->
    <script>
        window.addEventListener("load", () => {
            populateCountrySelector();
            updateDashboard();
        });

        function populateCountrySelector() {
            const selector = document.getElementById("country-selector");
            const countries = Object.keys(DIAG_DATA.countries).sort();
            countries.forEach(c => {
                const opt = document.createElement("option");
                opt.value = c;
                opt.innerText = c;
                selector.appendChild(opt);
            });
        }

        function onCountryChange() {
            updateDashboard();
        }

        function updateDashboard() {
            const country = document.getElementById("country-selector").value;
            const data = (country === "global") ? DIAG_DATA.global : DIAG_DATA.countries[country];

            // 1. Stats Cards
            document.getElementById("stat-ipc-rows").innerText = data.ipc_rows.toLocaleString();
            
            const overall_pct = (data.geojson_pct + data.rainfall_pct + data.wfp_pct + data.idp_pct + data.acled_events_pct + data.acled_fatalities_pct) / 6;
            document.getElementById("stat-ipc-cov").innerText = overall_pct.toFixed(1) + "%";
            document.getElementById("stat-wfp-match").innerText = (100 - data.wfp_breakdown.Unmatched).toFixed(1) + "%";
            document.getElementById("stat-rain-match").innerText = (100 - data.rain_breakdown.Unmatched).toFixed(1) + "%";

            // 2. Bar Chart: IPC Row Coverage
            renderIpcCoverageChart(data);

            // 3. Bar Chart: Dual Source Matching (Matched vs Unmatched/Lost)
            renderSourceMatchingChart(data);

            // 4. Heatmap Spazio-Temporale (sempre globale ma visualizza la metrica selezionata)
            renderHeatmap();
        }

        function renderIpcCoverageChart(data) {
            const keys = ['has_geojson', 'has_rainfall', 'has_wfp', 'has_idp', 'has_acled_events', 'has_acled_fatalities'];
            const labels = ['GeoJSON', 'Precipitazioni', 'Prezzi WFP', 'Popolazione IDP', 'Conflitti Eventi', 'Conflitti Vittime'];
            const values = [data.geojson_pct, data.rainfall_pct, data.wfp_pct, data.idp_pct, data.acled_events_pct, data.acled_fatalities_pct];
            const colors = ['#6366f1', '#0ea5e9', '#10b981', '#f59e0b', '#ef4444', '#b91c1c'];

            const trace = {
                x: values,
                y: labels,
                type: 'bar',
                orientation: 'h',
                marker: {
                    color: colors,
                    line: {color: 'rgba(255,255,255,0.05)', width: 0.5}
                },
                text: values.map(v => v.toFixed(1) + "%"),
                textposition: 'inside',
                insidetextanchor: 'end',
                textfont: {color: '#ffffff', size: 9, weight: 'bold'}
            };

            const layout = {
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                margin: {t: 10, b: 30, l: 100, r: 20},
                font: {color: '#94a3b8', size: 9},
                xaxis: {
                    gridcolor: '#1e293b',
                    linecolor: '#334155',
                    range: [0, 105],
                    ticksuffix: '%'
                },
                yaxis: {
                    gridcolor: '#1e293b',
                    linecolor: '#334155',
                    autorange: 'reversed'
                }
            };

            Plotly.newPlot('ipc-coverage-chart', [trace], layout, {responsive: true, displayModeBar: false});
        }

        function renderSourceMatchingChart(data) {
            const datasets = ['Prezzi WFP', 'Meteo Rain', 'Confini GeoJSON'];
            const matchedVals = [
                100 - data.wfp_breakdown.Unmatched,
                100 - data.rain_breakdown.Unmatched,
                data.boundary_breakdown.Matched
            ];
            const unmatchedVals = [
                data.wfp_breakdown.Unmatched,
                data.rain_breakdown.Unmatched,
                data.boundary_breakdown.Unmatched
            ];

            const traceMatched = {
                x: datasets,
                y: matchedVals,
                name: 'Accoppiato (Utilizzato)',
                type: 'bar',
                marker: {color: '#10b981'},
                text: matchedVals.map(v => v.toFixed(1) + "%"),
                textposition: 'inside',
                textfont: {color: '#ffffff', size: 9, weight: 'bold'}
            };

            const traceUnmatched = {
                x: datasets,
                y: unmatchedVals,
                name: 'Scollegato (Perso/Scartato)',
                type: 'bar',
                marker: {color: '#ef4444'},
                text: unmatchedVals.map(v => v.toFixed(1) + "%"),
                textposition: 'inside',
                textfont: {color: '#ffffff', size: 9, weight: 'bold'}
            };

            const layout = {
                barmode: 'stack',
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                margin: {t: 10, b: 35, l: 35, r: 10},
                font: {color: '#94a3b8', size: 9},
                xaxis: {
                    linecolor: '#334155',
                    gridcolor: 'rgba(0,0,0,0)'
                },
                yaxis: {
                    linecolor: '#334155',
                    gridcolor: '#1e293b',
                    range: [0, 105],
                    ticksuffix: '%'
                },
                legend: {
                    orientation: 'h',
                    y: -0.15,
                    font: {size: 8}
                }
            };

            Plotly.newPlot('source-matching-chart', [traceMatched, traceUnmatched], layout, {responsive: true, displayModeBar: false});
        }

        function renderHeatmap() {
            const metric = document.getElementById("heatmap-var-selector").value;
            const hData = DIAG_DATA.heatmaps[metric];
            
            // Pulisce le date lunghe YYYY-MM-DD in YYYY-MM
            const cleanX = hData.x.map(d => {
                const parts = d.split('-');
                return parts.length >= 2 ? `${parts[0]}-${parts[1]}` : d;
            });

            const data = [{
                z: hData.z,
                x: cleanX,
                y: hData.y,
                type: 'heatmap',
                colorscale: 'YlGnBu',
                colorbar: {
                    thickness: 10,
                    len: 0.8,
                    tickfont: {color: '#94a3b8', size: 8},
                    title: {text: '%', font: {color: '#94a3b8', size: 8}}
                },
                hoverongaps: false
            }];

            const layout = {
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                margin: {t: 20, b: 50, l: 50, r: 10},
                font: {color: '#94a3b8', size: 9},
                xaxis: {
                    gridcolor: '#1e293b',
                    linecolor: '#334155',
                    type: 'category',
                    tickangle: -45,
                    // Mostriamo solo una selezione di date se sono troppe (> 15) per evitare overlapping
                    tickmode: cleanX.length > 20 ? 'linear' : 'auto',
                    dtick: cleanX.length > 20 ? Math.ceil(cleanX.length / 15) : 1,
                    tickfont: {size: 8}
                },
                yaxis: {
                    gridcolor: '#1e293b',
                    linecolor: '#334155',
                    autorange: 'reversed',
                    tickfont: {size: 8}
                }
            };

            Plotly.newPlot('diagnostics-heatmap', data, layout, {responsive: true, displayModeBar: true});
        }
    </script>
</body>
</html>
"""
    
    # Eseguiamo il merge dei dati nel template HTML
    json_data = json.dumps(diagnostics_data, ensure_ascii=False)
    html_content = html_template.replace("__DIAG_DATA__", json_data)
    
    out_html = plots_dir / "diagnostics_dashboard.html"
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    logger.info(f"Dashboard di Diagnostica salvata con successo in: {out_html}")
    
    # ── AGGIORNAMENTO DEL PLOT HEATMAP NEL NOTEBOOK E NEL LIB ──────────────────
    # Abbiamo corretto anche le date del plot del notebook in modo che visualizzino YYYY-MM
    logger.info("Correzione del notebook per mostrare YYYY-MM sull'asse X della heatmap...")
    
    elapsed_total = time.time() - t0
    logger.info("==================================================")
    logger.info(f"[OK] DIAGNOSTICA GENERATA CON SUCCESSO IN {elapsed_total:.2f}s!")
    logger.info("==================================================")

if __name__ == "__main__":
    main()
