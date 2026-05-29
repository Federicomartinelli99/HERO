import os
import pandas as pd
import numpy as np
import altair as alt
import plotly.express as px
import plotly.graph_objects as go
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

def get_default_save_dir():
    """Restituisce il percorso predefinito per salvare i grafici."""
    current_dir = Path(__file__).resolve().parent
    save_dir = current_dir.parent.parent / "data" / "plots"
    save_dir.mkdir(parents=True, exist_ok=True)
    return save_dir

def load_reconciled_data(csv_path=None):
    """Carica il dataset riconciliato ipc_wfp_reconciled.csv."""
    if csv_path is None:
        workspace_dir = Path(__file__).resolve().parent.parent.parent.parent
        csv_path = workspace_dir / "hero_v4" / "data" / "reconciled" / "ipc_wfp_reconciled.csv"
    
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"File non trovato in: {csv_path}")
        
    df = pd.read_csv(csv_path)
    
    # Conversione date
    df["date_from"] = pd.to_datetime(df["From"], format="%d/%m/%Y", errors="coerce")
    df["date_to"] = pd.to_datetime(df["To"], format="%d/%m/%Y", errors="coerce")
    
    return df

def plot_wfp_match_distribution(df, save_dir=None):
    """
    Crea un grafico a barre impilate 100% (Altair) della distribuzione dei livelli
    di match spaziale di WFP per paese e lo salva.
    """
    if save_dir is None:
        save_dir = get_default_save_dir()
    else:
        save_dir = Path(save_dir)
        
    chart_data = df.groupby(['Country', 'wfp_match_level']).size().reset_index(name='count')
    
    domain_levels = ['Admin2', 'Admin1_Code', 'Admin1_Name', 'National', 'No_Match']
    color_range = ['#2ca02c', '#117768', '#1f3b8b', '#ffa600', '#a2a9b1'] 
    
    sort_map = {level: i for i, level in enumerate(domain_levels)}
    chart_data['sort_index'] = chart_data['wfp_match_level'].map(sort_map)
    
    chart = alt.Chart(chart_data).mark_bar().encode(
        x=alt.X('Country:N', 
                title='Paese', 
                sort=alt.EncodingSortField(field="count", op="sum", order='descending'),
                axis=alt.Axis(labelAngle=-45)),
        
        y=alt.Y('count:Q', 
                stack='normalize', 
                title='Frazione Analisi IPC', 
                axis=alt.Axis(format='%')),
        
        color=alt.Color('wfp_match_level:N', 
                        scale=alt.Scale(domain=domain_levels, range=color_range),
                        legend=alt.Legend(title="Livello Match WFP")),
        
        order=alt.Order('sort_index:Q'),
        tooltip=['Country', 'wfp_match_level', 'count']
    ).properties(
        width=700,
        height=380,
        title=alt.TitleParams(
            text='Distribuzione Livelli di Match Spaziale — WFP (hero_v4)',
            subtitle='Quota di righe IPC associate a ciascun livello di fallback gerarchico',
            anchor='start',
            fontSize=16,
            subtitleFontSize=11,
            subtitleColor='gray'
        )
    ).configure_axis(
        grid=False
    ).configure_view(
        strokeWidth=0
    )
    
    # Salvataggio
    sub_dir = save_dir / "distributions"
    sub_dir.mkdir(parents=True, exist_ok=True)
    html_path = sub_dir / "wfp_match_distribution.html"
    chart.save(str(html_path))
    
    png_path = sub_dir / "wfp_match_distribution.png"
    try:
        chart.save(str(png_path))
    except Exception as e:
        print(f"Salvataggio PNG non supportato o errore: {e}")
        
    return chart

def plot_rain_match_distribution(df, save_dir=None):
    """
    Crea un grafico a barre impilate 100% (Altair) della distribuzione dei livelli
    di match spaziale di Rainfall per paese e lo salva.
    """
    if save_dir is None:
        save_dir = get_default_save_dir()
    else:
        save_dir = Path(save_dir)
        
    chart_data = df.groupby(['Country', 'rain_match_level']).size().reset_index(name='count')
    
    domain_levels = ['Admin2', 'Admin1', 'National', 'No_Match']
    color_range = ['#4682b4', '#1f77b4', '#aec7e8', '#d3d3d3'] 
    
    sort_map = {level: i for i, level in enumerate(domain_levels)}
    chart_data['sort_index'] = chart_data['rain_match_level'].map(sort_map)
    
    chart = alt.Chart(chart_data).mark_bar().encode(
        x=alt.X('Country:N', 
                title='Paese', 
                sort=alt.EncodingSortField(field="count", op="sum", order='descending'),
                axis=alt.Axis(labelAngle=-45)),
        
        y=alt.Y('count:Q', 
                stack='normalize', 
                title='Frazione Analisi IPC', 
                axis=alt.Axis(format='%')),
        
        color=alt.Color('rain_match_level:N', 
                        scale=alt.Scale(domain=domain_levels, range=color_range),
                        legend=alt.Legend(title="Livello Match Pioggia")),
        
        order=alt.Order('sort_index:Q'),
        tooltip=['Country', 'rain_match_level', 'count']
    ).properties(
        width=700,
        height=380,
        title=alt.TitleParams(
            text='Distribuzione Livelli di Match Spaziale — CHIRPS Rainfall',
            subtitle='Quota di righe IPC associate a ciascun livello di fallback per i dati di piovosità',
            anchor='start',
            fontSize=16,
            subtitleFontSize=11,
            subtitleColor='gray'
        )
    ).configure_axis(
        grid=False
    ).configure_view(
        strokeWidth=0
    )
    
    # Salvataggio
    sub_dir = save_dir / "distributions"
    sub_dir.mkdir(parents=True, exist_ok=True)
    html_path = sub_dir / "rain_match_distribution.html"
    chart.save(str(html_path))
    
    png_path = sub_dir / "rain_match_distribution.png"
    try:
        chart.save(str(png_path))
    except Exception as e:
        print(f"Salvataggio PNG non supportato o errore: {e}")
        
    return chart

def plot_correlation_matrix(df, save_dir=None):
    """
    Genera un heatmap (Seaborn/Matplotlib) delle correlazioni lineari
    tra i dati di prezzo/inflazione, piovosità e le fasi IPC e lo salva.
    """
    if save_dir is None:
        save_dir = get_default_save_dir()
    else:
        save_dir = Path(save_dir)
        
    cols_corr = [
        'phase_1_percentage', 'phase_2_percentage', 'phase_3_percentage', 
        'phase_4_percentage', 'phase_5_percentage', 'phase_3plus_percentage',
        'WFP_avg_price', 'WFP_avg_inflation', 'Rain_avg_r1h', 'Rain_avg_rfq'
    ]
    
    # Assicurati che le colonne esistano e abbiano dati validi
    cols_present = [c for c in cols_corr if c in df.columns]
    
    df_sub = df[cols_present].dropna()
    if df_sub.empty:
        print("Dati insufficienti per la matrice di correlazione.")
        return None
        
    corr = df_sub.corr()
    
    fig, ax = plt.subplots(figsize=(10, 8), dpi=150)
    sns.heatmap(
        corr, 
        annot=True, 
        fmt=".2f", 
        cmap="coolwarm", 
        vmin=-1, 
        vmax=1, 
        center=0,
        square=True, 
        linewidths=.5, 
        cbar_kws={"shrink": .8},
        ax=ax
    )
    
    ax.set_title("Matrice di Correlazione: IPC vs Prezzi Alimentari vs Piovosità", fontsize=14, fontweight='bold', pad=15)
    plt.xticks(rotation=45, ha='right')
    plt.yticks(rotation=0)
    plt.tight_layout()
    
    # Salvataggio
    sub_dir = save_dir / "correlations"
    sub_dir.mkdir(parents=True, exist_ok=True)
    png_path = sub_dir / "correlation_matrix.png"
    plt.savefig(png_path, bbox_inches='tight')
    plt.close()
    
    return fig

def plot_inflation_vs_ipc(df, country=None, save_dir=None):
    """
    Crea un grafico a dispersione interattivo (Plotly) dell'inflazione WFP vs severità IPC
    (quota di popolazione in Fase 3+).
    """
    if save_dir is None:
        save_dir = get_default_save_dir()
    else:
        save_dir = Path(save_dir)
        
    df_plot = df.dropna(subset=['WFP_avg_inflation', 'phase_3plus_percentage']).copy()
    
    if country is not None:
        df_plot = df_plot[df_plot['Country'] == country]
        title_suffix = f" - Paese: {country}"
        file_suffix = f"_{country.lower()}"
    else:
        title_suffix = " - Tutti i Paesi"
        file_suffix = "_global"
        
    if df_plot.empty:
        print(f"Nessun dato per il grafico inflazione vs IPC per {country if country else 'globale'}.")
        return None
        
    fig = px.scatter(
        df_plot,
        x="WFP_avg_inflation",
        y="phase_3plus_percentage",
        color="Country",
        size="Total country population",
        hover_data=["Level 1", "Area", "Validity period"],
        opacity=0.7,
        trendline="ols",
        labels={
            "WFP_avg_inflation": "Inflazione Alimentare Media WFP",
            "phase_3plus_percentage": "Quota Popolazione IPC Fase 3+ (%)",
            "Country": "Paese",
            "Total country population": "Popolazione Totale"
        },
        title=f"Inflazione Alimentare WFP vs Severità Crisi IPC{title_suffix}"
    )
    
    fig.update_layout(
        template="plotly_white",
        title_font_size=16,
        margin=dict(l=40, r=40, t=60, b=40)
    )
    
    # Salvataggio
    sub_dir = save_dir / "scatters"
    sub_dir.mkdir(parents=True, exist_ok=True)
    html_path = sub_dir / f"inflation_vs_ipc{file_suffix}.html"
    fig.write_html(str(html_path))
    
    return fig

def plot_rain_vs_ipc(df, country=None, save_dir=None):
    """
    Crea un grafico a dispersione interattivo (Plotly) della piovosità media
    vs la severità IPC (quota di popolazione in Fase 3+).
    """
    if save_dir is None:
        save_dir = get_default_save_dir()
    else:
        save_dir = Path(save_dir)
        
    df_plot = df.dropna(subset=['Rain_avg_rfq', 'phase_3plus_percentage']).copy()
    
    if country is not None:
        df_plot = df_plot[df_plot['Country'] == country]
        title_suffix = f" - Paese: {country}"
        file_suffix = f"_{country.lower()}"
    else:
        title_suffix = " - Tutti i Paesi"
        file_suffix = "_global"
        
    if df_plot.empty:
        print(f"Nessun dato per il grafico pioggia vs IPC per {country if country else 'globale'}.")
        return None
        
    fig = px.scatter(
        df_plot,
        x="Rain_avg_rfq",
        y="phase_3plus_percentage",
        color="Country",
        size="Total country population",
        hover_data=["Level 1", "Area", "Validity period"],
        opacity=0.7,
        trendline="ols",
        labels={
            "Rain_avg_rfq": "Anomalia di Frequenza della Pioggia (rfq) CHIRPS",
            "phase_3plus_percentage": "Quota Popolazione IPC Fase 3+ (%)",
            "Country": "Paese",
            "Total country population": "Popolazione Totale"
        },
        title=f"Mancanza di Pioggia CHIRPS vs Severità Crisi IPC{title_suffix}"
    )
    
    fig.update_layout(
        template="plotly_white",
        title_font_size=16,
        margin=dict(l=40, r=40, t=60, b=40)
    )
    
    # Salvataggio
    sub_dir = save_dir / "scatters"
    sub_dir.mkdir(parents=True, exist_ok=True)
    html_path = sub_dir / f"rain_vs_ipc{file_suffix}.html"
    fig.write_html(str(html_path))
    
    return fig

def plot_temporal_trends(df, country, save_dir=None):
    """
    Mostra l'evoluzione temporale dell'inflazione WFP, piovosità e della severità IPC
    per un dato paese (es. Yemen o Afghanistan), usando un grafico a doppia scala o subplot.
    """
    if save_dir is None:
        save_dir = get_default_save_dir()
    else:
        save_dir = Path(save_dir)
        
    df_country = df[df["Country"] == country].copy()
    
    if df_country.empty:
        print(f"Nessun dato per il paese {country}.")
        return None
        
    # Per avere un trend temporale pulito per paese, aggreghiamo per data di inizio validity
    df_trend = df_country.groupby("date_from").agg(
        phase_3plus_percentage=("phase_3plus_percentage", "mean"),
        WFP_avg_inflation=("WFP_avg_inflation", "mean"),
        Rain_avg_rfq=("Rain_avg_rfq", "mean")
    ).reset_index().sort_values("date_from")
    
    # Creazione grafico plotly con due assi Y
    fig = go.Figure()
    
    # Traccia 1: Severità IPC (Fase 3+)
    fig.add_trace(go.Scatter(
        x=df_trend["date_from"],
        y=df_trend["phase_3plus_percentage"],
        name="IPC Severità (% Fase 3+)",
        line=dict(color="#d62728", width=3),
        yaxis="y1"
    ))
    
    # Traccia 2: Inflazione Alimentare
    fig.add_trace(go.Scatter(
        x=df_trend["date_from"],
        y=df_trend["WFP_avg_inflation"],
        name="Inflazione Alimentare (WFP)",
        line=dict(color="#ff7f0e", width=2, dash="dash"),
        yaxis="y2"
    ))
    
    # Traccia 3: Deficit di pioggia
    fig.add_trace(go.Scatter(
        x=df_trend["date_from"],
        y=df_trend["Rain_avg_rfq"],
        name="Anomalia Pioggia (CHIRPS)",
        line=dict(color="#1f77b4", width=2, dash="dot"),
        yaxis="y3",
        visible="legendonly" # opzionale all'inizio
    ))
    
    # Layout con più assi Y
    fig.update_layout(
        title=f"Evoluzione Temporale Co-variabile: IPC vs Prezzi vs Pioggia ({country})",
        xaxis=dict(title="Data dell'Analisi"),
        yaxis=dict(
            title=dict(text="IPC Severità (% Popolazione)", font=dict(color="#d62728")),
            tickfont=dict(color="#d62728")
        ),
        yaxis2=dict(
            title=dict(text="Inflazione Alimentare Media", font=dict(color="#ff7f0e")),
            tickfont=dict(color="#ff7f0e"),
            anchor="free",
            overlaying="y",
            side="right",
            position=0.95
        ),
        yaxis3=dict(
            title=dict(text="Anomalia Pioggia (rfq)", font=dict(color="#1f77b4")),
            tickfont=dict(color="#1f77b4"),
            anchor="x",
            overlaying="y",
            side="right"
        ),
        template="plotly_white",
        legend=dict(x=0.01, y=0.99, bgcolor="rgba(255,255,255,0.7)")
    )
    
    # Salvataggio
    sub_dir = save_dir / "temporal_trends"
    sub_dir.mkdir(parents=True, exist_ok=True)
    html_path = sub_dir / f"temporal_trends_{country.lower()}.html"
    fig.write_html(str(html_path))
    
    return fig

def plot_mapping_quality(df, save_dir=None):
    """
    Crea un grafico a barre impilate Altair che mostra la distribuzione dei metodi di
    mappatura spaziale (strict_pip, elastic_buffer, national_fallback, unmapped) per paese.
    """
    if save_dir is None:
        save_dir = get_default_save_dir()
    else:
        save_dir = Path(save_dir)
        
    # Calcoliamo i conteggi
    chart_data = df.groupby(['Country', 'wfp_spatial_mapping_method']).size().reset_index(name='count')
    
    domain_methods = ['strict_pip', 'elastic_buffer', 'national_fallback', 'unmapped']
    color_range = ['#2ca02c', '#ff7f0e', '#1f77b4', '#d62728']
    
    sort_map = {method: i for i, method in enumerate(domain_methods)}
    chart_data['sort_index'] = chart_data['wfp_spatial_mapping_method'].map(sort_map)
    
    chart = alt.Chart(chart_data).mark_bar().encode(
        x=alt.X('Country:N', 
                title='Paese', 
                sort=alt.EncodingSortField(field="count", op="sum", order='descending'),
                axis=alt.Axis(labelAngle=-45)),
        
        y=alt.Y('count:Q', 
                stack='normalize', 
                title='Frazione Analisi IPC', 
                axis=alt.Axis(format='%')),
        
        color=alt.Color('wfp_spatial_mapping_method:N', 
                        scale=alt.Scale(domain=domain_methods, range=color_range),
                        legend=alt.Legend(title="Metodo Mapping")),
        
        order=alt.Order('sort_index:Q'),
        tooltip=['Country', 'wfp_spatial_mapping_method', 'count']
    ).properties(
        width=750,
        height=380,
        title=alt.TitleParams(
            text='Distribuzione Metodi Mapping Spaziale WFP (hero_v4)',
            subtitle='Incidenza di strict PIP e del buffer di elasticità (coastal/riverbank) sui match',
            anchor='start',
            fontSize=16,
            subtitleFontSize=11,
            subtitleColor='gray'
        )
    ).configure_axis(
        grid=False
    ).configure_view(
        strokeWidth=0
    )
    
    sub_dir = save_dir / "distributions"
    sub_dir.mkdir(parents=True, exist_ok=True)
    html_path = sub_dir / "wfp_mapping_quality.html"
    chart.save(str(html_path))
    
    png_path = sub_dir / "wfp_mapping_quality.png"
    try:
        chart.save(str(png_path))
    except Exception as e:
        pass
        
    return chart

def plot_geographic_markets(wfp_parquet_path=None, save_dir=None):
    """
    Genera una mappa geografica interattiva (Plotly Mapbox) di tutti i mercati WFP,
    colorati in base al metodo di mapping spaziale per Admin2 (strict_pip, elastic_buffer, unmapped).
    """
    if save_dir is None:
        save_dir = get_default_save_dir()
    else:
        save_dir = Path(save_dir)
        
    if wfp_parquet_path is None:
        workspace_dir = Path(__file__).resolve().parent.parent.parent.parent
        wfp_parquet_path = workspace_dir / "hero_v4" / "data" / "interim" / "wfp_with_pcodes.parquet"
        
    if not os.path.exists(wfp_parquet_path):
        print(f"File mercati non trovato: {wfp_parquet_path}")
        return None
        
    df_wfp = pd.read_parquet(wfp_parquet_path)
    
    # Seleziona mercati unici
    cols_geo = ['ISO3', 'mkt_name', 'lat', 'lon', 'mapping_method_adm1', 'mapping_method_adm2', 'adm1_name', 'adm2_name']
    cols_present = [c for c in cols_geo if c in df_wfp.columns]
    
    df_mkt = df_wfp[cols_present].drop_duplicates().dropna(subset=['lat', 'lon']).copy()
    
    if df_mkt.empty:
        print("Nessun mercato con coordinate geografiche valide per la mappa.")
        return None
        
    # Creazione mappa geografica con Plotly Mapbox
    fig = px.scatter_mapbox(
        df_mkt,
        lat="lat",
        lon="lon",
        color="mapping_method_adm2",
        hover_name="mkt_name",
        hover_data=["ISO3", "adm1_name", "adm2_name", "mapping_method_adm1"],
        zoom=1.5,
        color_discrete_map={
            "strict_pip": "#2ca02c",      # Verde
            "elastic_buffer": "#ff7f0e",  # Arancione
            "unmapped": "#d62728"        # Rosso
        },
        labels={
            "mapping_method_adm2": "Metodo Mapping Admin2",
            "lat": "Latitudine",
            "lon": "Longitudine",
            "mkt_name": "Nome Mercato"
        },
        title="Mappa Geografica dei Mercati WFP e Metodo di Mapping Spaziale (Admin2)"
    )
    
    fig.update_layout(
        mapbox_style="open-street-map",
        margin={"r":0,"t":40,"l":0,"b":0},
        template="plotly_white",
        title_font_size=16
    )
    
    sub_dir = save_dir / "geographical"
    sub_dir.mkdir(parents=True, exist_ok=True)
    html_path = sub_dir / "geographic_markets_map.html"
    fig.write_html(str(html_path))
    
    return fig

def plot_country_spatial_assignment(iso3, df_reconciled=None, save_dir=None):
    """
    Genera un grafico Matplotlib/Geopandas mostrando i confini distrettuali (Admin2)
    colorati in base alla severità IPC media (% Fase 3+) e i mercati WFP sovrapposti,
    colorati in base al metodo di mapping spaziale.
    """
    import re
    import geopandas as gpd
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import matplotlib.lines as mlines
    
    if save_dir is None:
        save_dir = get_default_save_dir()
    else:
        save_dir = Path(save_dir)
        
    workspace_dir = Path(__file__).resolve().parent.parent.parent.parent
    boundaries_dir = workspace_dir / "hero_v4" / "data" / "boundaries"
    fallback_dir = workspace_dir / "rainfall" / "data" / "raw_boundaries0"
    if not fallback_dir.exists():
        fallback_dir = workspace_dir / "rainfall" / "data" / "raw_boundaries"
    
    # Trova il file confini Admin2
    file_adm2 = None
    for b_dir in [boundaries_dir, fallback_dir]:
        if b_dir is None or not b_dir.exists():
            continue
        country_dir = b_dir / iso3.lower()
        if not country_dir.exists():
            continue
        
        all_files = list(country_dir.rglob("*.geojson")) + list(country_dir.rglob("*.shp"))
        regex_pattern = rf"[._-]adm(in)?2([._-]|$)"
        matching_files = [f for f in all_files if re.search(regex_pattern, f.name.lower())]
        geojson_files = [f for f in matching_files if f.suffix.lower() == ".geojson"]
        shp_files = [f for f in matching_files if f.suffix.lower() == ".shp"]
        
        if geojson_files:
            file_adm2 = geojson_files[0]
            break
        elif shp_files:
            file_adm2 = shp_files[0]
            break
        elif len(all_files) == 1:
            file_adm2 = all_files[0]
            break
            
    if not file_adm2:
        print(f"Confini Admin2 non trovati per {iso3}. Mappa non generata.")
        return None
        
    # Carica confini
    try:
        gdf_adm2 = gpd.read_file(file_adm2)
        if gdf_adm2.crs != "EPSG:4326":
            gdf_adm2 = gdf_adm2.to_crs("EPSG:4326")
    except Exception as e:
        print(f"Errore caricamento confini per {iso3}: {e}")
        return None
        
    # Standardizzazione colonna pcode
    def standardize_pcode_column(gdf, level=2):
        standard_name = f"adm{level}_pcode"
        if standard_name in gdf.columns:
            return gdf
        for col in gdf.columns:
            col_lower = str(col).lower()
            if (f"adm{level}" in col_lower or f"admin{level}" in col_lower) and "pco" in col_lower:
                return gdf.rename(columns={col: standard_name})
        for col in gdf.columns:
            col_lower = str(col).lower()
            if "pcode" in col_lower and str(level) in col_lower:
                return gdf.rename(columns={col: standard_name})
        return gdf

    gdf_adm2 = standardize_pcode_column(gdf_adm2, 2)
    
    # Carica e aggrega dati di severità IPC
    if df_reconciled is None:
        try:
            df_reconciled = load_reconciled_data()
        except Exception:
            df_reconciled = None
            
    has_ipc = False
    if df_reconciled is not None and 'adm2_pcode' in gdf_adm2.columns:
        df_country_ipc = df_reconciled[df_reconciled['Country'] == iso3.upper()]
        if not df_country_ipc.empty:
            severity_col = 'phase_3plus_percentage'
            if severity_col in df_country_ipc.columns:
                df_country_ipc = df_country_ipc.dropna(subset=['adm2_pcode', severity_col])
                if not df_country_ipc.empty:
                    ipc_severity = df_country_ipc.groupby('adm2_pcode')[severity_col].mean().reset_index()
                    max_val = ipc_severity[severity_col].max()
                    if max_val <= 1.0:
                        ipc_severity['Percentage'] = ipc_severity[severity_col] * 100
                    else:
                        ipc_severity['Percentage'] = ipc_severity[severity_col]
                    gdf_adm2 = gdf_adm2.merge(ipc_severity, on='adm2_pcode', how='left')
                    has_ipc = True

    # Carica mercati con PCODE
    wfp_parquet_path = workspace_dir / "hero_v4" / "data" / "interim" / "wfp_with_pcodes.parquet"
    has_wfp_mkts = False
    gdf_mkt = None
    
    if wfp_parquet_path.exists():
        try:
            df_wfp = pd.read_parquet(wfp_parquet_path)
            df_country = df_wfp[df_wfp['ISO3'] == iso3.upper()]
            if not df_country.empty:
                df_mkt = df_country[['mkt_name', 'lat', 'lon', 'mapping_method_adm2']].drop_duplicates().dropna(subset=['lat', 'lon']).copy()
                if not df_mkt.empty:
                    has_wfp_mkts = True
                    gdf_mkt = gpd.GeoDataFrame(
                        df_mkt,
                        geometry=gpd.points_from_xy(df_mkt.lon, df_mkt.lat),
                        crs="EPSG:4326"
                    )
        except Exception as e:
            print(f"Errore lettura mercati WFP per {iso3}: {e}")
            
    # Disegno grafico
    fig, ax = plt.subplots(figsize=(12, 10), dpi=150)
    
    # Plot choropleth di sfondo
    if has_ipc and 'Percentage' in gdf_adm2.columns and gdf_adm2['Percentage'].notna().any():
        gdf_adm2.plot(
            column='Percentage',
            ax=ax,
            cmap='OrRd',
            edgecolor='#7f8c8d',
            linewidth=0.4,
            legend=True,
            legend_kwds={'label': 'Severità IPC Fase 3+ Media (% Popolazione)', 'shrink': 0.6},
            missing_kwds={'color': '#f2f2f2', 'label': 'Nessun dato IPC'}
        )
    else:
        gdf_adm2.plot(ax=ax, color='#f5f6f8', edgecolor='#bdc3c7', linewidth=0.6)
        
    # Plot dei punti mercati se presenti
    if has_wfp_mkts and gdf_mkt is not None:
        colors = {
            'strict_pip': '#2ca02c',      # Verde
            'elastic_buffer': '#ff7f0e',  # Arancione
            'unmapped': '#d62728'        # Rosso
        }
        for method, group in gdf_mkt.groupby('mapping_method_adm2'):
            color = colors.get(method, '#7f7f7f')
            group.plot(ax=ax, color=color, markersize=60, edgecolors='black', linewidths=0.5, alpha=0.9, zorder=5)
            
            # Annotazioni per i mercati elastic_buffer
            if method == 'elastic_buffer':
                for idx, row in group.iterrows():
                    ax.annotate(
                        f"{row['mkt_name']} (Rescued)", 
                        (row.lon, row.lat), 
                        textcoords="offset points", 
                        xytext=(6,6), 
                        ha='left', 
                        fontsize=7, 
                        color='#d35400', 
                        weight='bold',
                        bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#ff7f0e", lw=0.5, alpha=0.8),
                        zorder=10
                    )
            # Annotazioni per i mercati unmapped
            elif method == 'unmapped':
                for idx, row in group.iterrows():
                    ax.annotate(
                        f"{row['mkt_name']} (Unmapped)", 
                        (row.lon, row.lat), 
                        textcoords="offset points", 
                        xytext=(6,6), 
                        ha='left', 
                        fontsize=7, 
                        color='#c0392b', 
                        weight='bold',
                        bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#d62728", lw=0.5, alpha=0.8),
                        zorder=10
                    )
                    
    # Legenda personalizzata
    legend_handles = [
        mpatches.Patch(facecolor='#f5f6f8', edgecolor='#bdc3c7', linewidth=0.6, label='Confini Distrettuali (Admin2)')
    ]
    if has_wfp_mkts:
        legend_handles.extend([
            mlines.Line2D([], [], color='#2ca02c', marker='o', linestyle='None', markersize=8, markeredgecolor='black', markeredgewidth=0.5, label='Strict PIP (Dentro Confini)'),
            mlines.Line2D([], [], color='#ff7f0e', marker='o', linestyle='None', markersize=8, markeredgecolor='black', markeredgewidth=0.5, label='Elastic Buffer (Rescued <5.5km)'),
            mlines.Line2D([], [], color='#d62728', marker='o', linestyle='None', markersize=8, markeredgecolor='black', markeredgewidth=0.5, label='Non Mappato (Unmapped)')
        ])
    ax.legend(handles=legend_handles, loc='best', fontsize=9, frameon=True, facecolor='white', framealpha=0.9)
    
    # Dettagli del grafico
    tot_m = len(gdf_mkt) if gdf_mkt is not None else 0
    pip_m = (gdf_mkt['mapping_method_adm2'] == 'strict_pip').sum() if gdf_mkt is not None else 0
    buf_m = (gdf_mkt['mapping_method_adm2'] == 'elastic_buffer').sum() if gdf_mkt is not None else 0
    unm_m = (gdf_mkt['mapping_method_adm2'] == 'unmapped').sum() if gdf_mkt is not None else 0
    
    title_text = f"Diagnostica Spaziale Confini e Mercati WFP — {iso3.upper()}"
    if has_wfp_mkts:
        subtitle_text = f"Totale mercati: {tot_m} | Strict PIP: {pip_m} | Buffer elastico: {buf_m} | Non mappati: {unm_m}"
    else:
        subtitle_text = "Nessun dato mercati WFP disponibile per questo paese"
        
    ax.text(0.5, 1.05, title_text, transform=ax.transAxes, ha='center', fontsize=14, weight='bold')
    ax.text(0.5, 1.01, subtitle_text, transform=ax.transAxes, ha='center', fontsize=10, color='gray')
    
    ax.set_xlabel("Longitudine (GCS WGS84)")
    ax.set_ylabel("Latitudine (GCS WGS84)")
    ax.grid(True, linestyle=':', alpha=0.6)
    
    # Salvataggio
    sub_dir = save_dir / "spatial_diagnostics"
    sub_dir.mkdir(parents=True, exist_ok=True)
    png_path = sub_dir / f"spatial_diagnostic_{iso3.lower()}.png"
    plt.savefig(png_path, bbox_inches='tight', dpi=150)
    plt.close()
    print(f"Mappa diagnostica spaziale salvata in: {png_path}")
    return png_path


def generate_all_plots(df, save_dir=None):
    """Genera ed esporta tutti i grafici standard."""
    if save_dir is None:
        save_dir = get_default_save_dir()
        
    print(f"Salvataggio di tutti i grafici in: {save_dir}")
    
    print("1. Stacked bar per WFP...")
    plot_wfp_match_distribution(df, save_dir)
    
    print("2. Stacked bar per Rainfall...")
    plot_rain_match_distribution(df, save_dir)
    
    print("3. Matrice di correlazione...")
    plot_correlation_matrix(df, save_dir)
    
    print("4. Grafico qualità del mapping spaziale...")
    plot_mapping_quality(df, save_dir)
    
    print("5. Mappa geografica dei mercati...")
    plot_geographic_markets(None, save_dir)
    
    print("6. Scatter plot globali e per paesi (YEM, AFG)...")
    plot_inflation_vs_ipc(df, save_dir=save_dir)
    plot_rain_vs_ipc(df, save_dir=save_dir)
    for country in ["YEM", "AFG"]:
        plot_inflation_vs_ipc(df, country=country, save_dir=save_dir)
        plot_rain_vs_ipc(df, country=country, save_dir=save_dir)
        plot_temporal_trends(df, country=country, save_dir=save_dir)
        
    print("7. Mappe di diagnostica spaziale per confini e mercati...")
    countries = sorted(df["Country"].dropna().unique())
    print(f"Generazione diagnostica spaziale per {len(countries)} paesi...")
    for country in countries:
        try:
            plot_country_spatial_assignment(country, df_reconciled=df, save_dir=save_dir)
        except Exception as e:
            print(f"Errore nella generazione della diagnostica spaziale per {country}: {e}")
        
    print("Completato! Tutti i grafici salvati in:", save_dir)

if __name__ == "__main__":
    # Esempio esecuzione standalone
    try:
        data = load_reconciled_data()
        generate_all_plots(data)
    except Exception as e:
        print("Errore durante l'esecuzione standalone del plotter:", e)
