import pandas as pd
import zipfile
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

# --- 1. CONFIGURAZIONE E COLORI ---
colors = {
    'AGO': '#10b981',  # Verde Smeraldo
    'CPV': '#f97316',  # Arancione
    'ETH': '#eab308',  # Giallo
    'MDG': '#06b6d4',  # Ciano
    'MOZ': '#ef4444',  # Rosso
    'SEN': '#3b82f6',  # Blu
    'UGA': '#a855f7',  # Viola
    'bg': '#0b0f19', 
    'grid': 'rgba(255, 255, 255, 0.06)', 
    'text_muted': '#94a3b8'
}

def hex_to_rgba(hex_color, alpha=0.15):
    """Converte un HEX in RGBA per i riempimenti semitrasparenti del radar."""
    hex_color = hex_color.lstrip('#')
    r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    return f'rgba({r},{g},{b},{alpha})'

# Percorso relativo alla cartella "pioggia" (dove si trova lo script)
base_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()

# Lista aggiornata dei paesi basata sull'alberatura
countries = ['AGO', 'CPV', 'ETH', 'MDG', 'MOZ', 'SEN', 'UGA']
dfs = {}

# --- 2. ESTRAZIONE DATI ---
for code in countries:
    zip_path = os.path.join(base_dir, f'Grafici_Rainfall_{code}.zip')
    csv_name = f'Serie_Temporale_Precipitazioni_Alta_Risoluzione_{code}.csv'
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as z:
            df = pd.read_csv(z.open(csv_name))
            # Identificazione dinamica delle colonne (Data e Valore)
            date_col = [c for c in df.columns if 'Data' in c or 'Date' in c][0]
            val_col = [c for c in df.columns if c != date_col][0]
            
            df[date_col] = pd.to_datetime(df[date_col])
            df = df.rename(columns={date_col: 'Data', val_col: 'Precipitazioni'})
            df = df.sort_values('Data')
            dfs[code] = df
    except Exception as e:
        print(f"[!] Errore nel caricamento di {code}: {e}")

# --- 3. CREAZIONE LAYOUT 4:1 ---
fig = make_subplots(
    rows=1, cols=2,
    shared_xaxes=False,
    horizontal_spacing=0.04,
    column_widths=[0.80, 0.20], # Rapporto 4:1 tra Time Series e Radar
    specs=[[{"type": "xy"}, {"type": "polar"}]],
    subplot_titles=(
        "<span style='color: white; font-size: 14px; font-weight: bold;'><i class='fa-solid fa-cloud-rain' style='color:#60a5fa'></i> Precipitazioni Storiche (Confronto HERO)</span>", 
        "<span style='color: white; font-size: 12px;'>Stagionalità (Media Mensile)</span>"
    )
)

theta = ['Gen', 'Feb', 'Mar', 'Apr', 'Mag', 'Giu', 'Lug', 'Ago', 'Set', 'Ott', 'Nov', 'Dic', 'Gen']

# --- 4. POPOLAMENTO GRAFICI SOVRAPPOSTI ---
for code in countries:
    if code not in dfs:
        continue
        
    df = dfs[code]
    color = colors.get(code, '#ffffff')
    
    # Trace 1: Time Series
    fig.add_trace(go.Scatter(
        x=df['Data'], y=df['Precipitazioni'],
        name=code, mode='lines',
        line=dict(color=color, width=1.5, shape='spline'),
        opacity=0.85,
        legendgroup=code
    ), row=1, col=1)
    
    # Trace 2: Radar Plot (Media Mensile per mostrare i cicli stagionali)
    df_temp = df.copy().dropna(subset=['Precipitazioni'])
    df_temp['Month'] = df_temp['Data'].dt.month
    hist = df_temp.groupby('Month')['Precipitazioni'].mean().reindex(range(1,13)).fillna(0).tolist()
    hist.append(hist[0]) # Chiusura del poligono radar per Plotly
    
    fig.add_trace(go.Scatterpolar(
        r=hist, theta=theta,
        name=f'{code}',
        line=dict(color=color, width=2),
        fill='toself',
        fillcolor=hex_to_rgba(color, 0.15),
        legendgroup=code,
        showlegend=False
    ), row=1, col=2)

# --- 5. STILIZZAZIONE COMPATTA E UI DARK ---
fig.update_layout(
    height=500, # Leggermente più alto per accomodare la legenda con 7 elementi
    plot_bgcolor=colors['bg'], paper_bgcolor=colors['bg'], 
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.1, xanchor="right", x=1, font=dict(color=colors['text_muted'], size=11)),
    margin=dict(l=40, r=20, t=80, b=40), 
    font=dict(family="Inter, sans-serif", color=colors['text_muted']),
    hoverlabel=dict(bgcolor="#0f172a", font_size=11, font_family="Inter, sans-serif", bordercolor="rgba(255,255,255,0.12)"),
    polar=dict(
        bgcolor=colors['bg'], 
        radialaxis=dict(gridcolor=colors['grid'], showticklabels=False, ticks=''), 
        angularaxis=dict(gridcolor=colors['grid'], tickfont=dict(color=colors['text_muted'], size=9))
    )
)

fig.update_xaxes(showgrid=False, tickfont=dict(color=colors['text_muted']), showline=True, linewidth=1, linecolor='rgba(255, 255, 255, 0.2)'),
fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor=colors['grid'], tickfont=dict(color=colors['text_muted'], size=10), zeroline=False)

# --- 6. ESPORTAZIONE ---
output_filename = os.path.join(base_dir, 'Dashboard_Rainfall_Confronto.html')
fig.write_html(output_filename, include_plotlyjs='cdn')
print(f"[✓] Dashboard precipitazioni creata con successo: {output_filename}")