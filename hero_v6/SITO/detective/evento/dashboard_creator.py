import pandas as pd
import zipfile
import json
import re
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

# --- 1. CONFIGURAZIONE E COLORI ---
colors = {
    'ipc_line': '#eab308', 'idp': '#fbbf24', 'acled_events': '#f59e0b', 
    'acled_fatal': '#ef4444', 'gdelt': '#a855f7', 'wfp_price': '#818cf8', 
    'bg': '#0b0f19', 'grid': 'rgba(255, 255, 255, 0.06)', 
    'text_muted': '#94a3b8', 'event_line': '#ef4444',
    'radar_hist': '#3b82f6', 'radar_2021': '#ef4444' # Colore standard per l'area di crisi
}

default_configs = {
    'AFG': {'code': 'AFG', 'event_date': '2021-05-01', 'event_label': '<b>MAG 2021</b><br>Ritiro USA', 'start': '2017-11-01', 'end': '2023-04-30', 'crisis_year': 2021},
    'SDN': {'code': 'SDN', 'event_date': '2023-04-15', 'event_label': '<b>APR 2023</b><br>Scoppio Guerra', 'start': '2020-01-01', 'end': '2024-12-31', 'crisis_year': 2023},
    'ETH': {'code': 'ETH', 'event_date': '2020-11-03', 'event_label': '<b>NOV 2020</b><br>Guerra del Tigrè', 'start': '2018-01-01', 'end': '2023-12-31', 'crisis_year': 2020},
    'HTI': {'code': 'HTI', 'event_date': '2021-07-07', 'event_label': '<b>LUG 2021</b><br>Omicidio Moïse', 'start': '2019-01-01', 'end': '2023-12-31', 'crisis_year': 2021}
}

# Helper per calcolare i dati del radar (Media Pre-Evento e Media Post-Evento, con frequenza opzionale)
def get_radar_data(df, val_col, event_date, freq='monthly'):
    d_temp = df.copy().dropna(subset=[val_col])
    event_dt = pd.to_datetime(event_date)
    
    if freq == 'trimestrale':
        d_temp['Period'] = (d_temp['Data'].dt.month - 1) // 3 + 1
        reindex_range = [1, 2, 3, 4]
        theta_out = ['Gen-Mar', 'Apr-Giu', 'Lug-Set', 'Ott-Dic', 'Gen-Mar']
    else:
        d_temp['Period'] = d_temp['Data'].dt.month
        reindex_range = list(range(1, 13))
        theta_out = ['Gen', 'Feb', 'Mar', 'Apr', 'Mag', 'Giu', 'Lug', 'Ago', 'Set', 'Ott', 'Nov', 'Dic', 'Gen']
    
    # Media Pre-Evento (dati prima della data evento)
    pre_df = d_temp[d_temp['Data'] < event_dt]
    if len(pre_df) > 0:
        pre_avg = pre_df.groupby('Period')[val_col].mean().reindex(reindex_range).fillna(0).tolist()
    else:
        pre_avg = d_temp.groupby('Period')[val_col].mean().reindex(reindex_range).fillna(0).tolist()
        
    # Media Post-Evento (dati dalla data evento in poi)
    post_df = d_temp[d_temp['Data'] >= event_dt]
    if len(post_df) > 0:
        post_avg = post_df.groupby('Period')[val_col].mean().reindex(reindex_range).fillna(0).tolist()
    else:
        post_avg = d_temp.groupby('Period')[val_col].mean().reindex(reindex_range).fillna(0).tolist()
    
    # Chiusura del poligono per il chart polare
    pre_avg.append(pre_avg[0])
    post_avg.append(post_avg[0])
    return pre_avg, post_avg, theta_out

theta = ['Gen', 'Feb', 'Mar', 'Apr', 'Mag', 'Giu', 'Lug', 'Ago', 'Set', 'Ott', 'Nov', 'Dic', 'Gen']

# --- 2. ELABORAZIONE PAESI ---
script_dir = os.path.dirname(os.path.abspath(__file__))

# Rilevamento automatico di tutti i paesi presenti nelle cartelle (es. AFG, SDN, ETH, HTI o altri nuovi)
detected_codes = set(default_configs.keys())
dirs_to_scan = [script_dir, os.getcwd(), os.path.join(script_dir, ".."), os.path.join(script_dir, "../..")]
for d in dirs_to_scan:
    if os.path.exists(d):
        try:
            for item in os.listdir(d):
                m = re.search(r'(?:Esportazione_Completa_HERO_|Suite_Esportazione_Completa_|Grafici_.*_)([A-Z]{3})', item)
                if m:
                    detected_codes.add(m.group(1))
        except Exception:
            pass

configs = []
for code in sorted(detected_codes):
    if code in default_configs:
        configs.append(default_configs[code])
    else:
        configs.append({
            'code': code, 'event_date': '2022-06-01', 'event_label': f'<b>GIU 2022</b><br>Evento {code}', 
            'start': '2018-01-01', 'end': '2024-12-31', 'crisis_year': 2022
        })

for cfg in configs:
    code = cfg['code']
    print(f"Generazione Dashboard per: {code}...")
    
    # Ricerca robusta della cartella dati del paese, ignorando cartelle vuote o spostate
    candidates = [
        os.path.join(script_dir, f"Suite_Esportazione_Completa_{code}", f"Esportazione_Completa_HERO_{code}"),
        os.path.join(script_dir, f"Esportazione_Completa_HERO_{code}"),
        os.path.join(script_dir, f"Suite_Esportazione_Completa_{code}"),
        os.path.join(os.getcwd(), f"Suite_Esportazione_Completa_{code}", f"Esportazione_Completa_HERO_{code}"),
        os.path.join(os.getcwd(), f"Esportazione_Completa_HERO_{code}"),
        os.path.join(os.getcwd(), f"Suite_Esportazione_Completa_{code}"),
        os.path.abspath(os.path.join(script_dir, "../../UI/data/page_zips")),
        os.path.abspath(os.path.join(script_dir, "../../../UI/data/page_zips")),
        os.path.abspath(os.path.join(script_dir, f"../Esportazione_Completa_HERO_{code}")),
        os.path.abspath(os.path.join(script_dir, f"../Suite_Esportazione_Completa_{code}", f"Esportazione_Completa_HERO_{code}")),
        os.path.abspath(os.path.join(script_dir, f"../Suite_Esportazione_Completa_{code}"))
    ]
    
    base_path = None
    for cand in candidates:
        if os.path.exists(cand) and os.path.isdir(cand):
            try:
                # Verifica che la cartella contenga realmente i file zip/csv/json/html e non sia vuota
                if any(f.endswith((".zip", ".csv", ".json", ".html")) for f in os.listdir(cand)):
                    base_path = cand
                    break
            except Exception:
                pass
                
    if not base_path:
        for cand in candidates:
            if os.path.exists(cand):
                base_path = cand
                break
        if not base_path:
            base_path = candidates[0]
    
    dfs = {}

    # IPC
    try:
        with zipfile.ZipFile(os.path.join(base_path, f'Grafici_IPC_{code}.zip'), 'r') as z:
            df_ipc = pd.read_csv(z.open(f'Serie_Temporale_IPC_Alta_Risoluzione_{code}.csv'))
            df_ipc['Data'] = pd.to_datetime(df_ipc['Data'])
            dfs['ipc'] = df_ipc.groupby('Data').mean().reset_index()
    except Exception as e: print(f"  [!] Dati IPC non trovati per {code}")

    # GDELT
    try:
        with zipfile.ZipFile(os.path.join(base_path, f'Grafici_GDELT_{code}.zip'), 'r') as z:
            df_gdelt = pd.read_csv(z.open(f'Serie_Temporale_GDELT_Alta_Risoluzione_{code}.csv'))
            df_gdelt['Data'] = pd.to_datetime(df_gdelt['Data'])
            dfs['gdelt'] = df_gdelt.groupby('Data').mean().reset_index()
    except Exception as e:
        # Fallback se non c'è il file alta risoluzione (HTI, SDN etc.) -> pesca dal JSON trend
        try:
            with zipfile.ZipFile(os.path.join(base_path, f'Grafici_Trend_{code}.zip'), 'r') as z:
                with z.open(f'{code}_trends.json') as jf:
                    c_json = json.load(jf)
                    if 'adm1' in c_json['trends']:
                        t_df = pd.DataFrame(c_json['trends']['adm1'])
                        t_df['Data'] = pd.to_datetime(t_df['from']).dt.strftime('%Y-%m-01')
                        g_agg = t_df.groupby('Data')['gdelt_material_conflict_events'].sum().reset_index()
                        g_agg['Data'] = pd.to_datetime(g_agg['Data'])
                        # Rinominiamo la colonna per farla combaciare con l'estrazione successiva
                        g_agg.rename(columns={'gdelt_material_conflict_events': 'Conflitto Materiale'}, inplace=True)
                        dfs['gdelt'] = g_agg
        except Exception as e2: print(f"  [!] Dati GDELT non trovati per {code}")

    # IDP
    try:
        with zipfile.ZipFile(os.path.join(base_path, f'Grafici_IDP_{code}.zip'), 'r') as z:
            df_idp = pd.read_csv(z.open(f'Serie_Temporale_IDP_Alta_Risoluzione_{code}.csv'))
            date_col = 'Data Rilevazione' if 'Data Rilevazione' in df_idp.columns else 'Data'
            df_idp['Data'] = pd.to_datetime(df_idp[date_col])
            
            # Normalizzazione del nome colonna IDP
            pop_col = 'Popolazione IDP' if 'Popolazione IDP' in df_idp.columns else 'Popolazione Sfollata'
            df_idp = df_idp[['Data', pop_col]].groupby('Data').mean().reset_index()
            df_idp.rename(columns={pop_col: 'Popolazione IDP'}, inplace=True)
            dfs['idp'] = df_idp
    except Exception as e: print(f"  [!] Dati IDP non trovati per {code}")

    # ACLED
    try:
        with zipfile.ZipFile(os.path.join(base_path, f'Grafici_ACLED_{code}.zip'), 'r') as z:
            df_acled = pd.read_csv(z.open(f'Serie_Temporale_ACLED_Alta_Risoluzione_{code}.csv'))
            df_acled['Data'] = pd.to_datetime(df_acled['Data'])
            dfs['acled'] = df_acled.groupby('Data').mean().reset_index()
    except Exception as e: print(f"  [!] Dati ACLED non trovati per {code}")

    # WFP (Estrapolazione dal file HTML specifico)
    try:
        html_path = os.path.join(base_path, f'chart-market-national-ts_{code}.html')
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
            match = re.search(r'var options = (\{.*?\});', html_content, re.DOTALL)
            if match:
                options_json = json.loads(match.group(1))
                series = options_json['series']
                price_data = [s for s in series if 'Indice' in s['name']][0]['data']
                df_wfp = pd.DataFrame(price_data)
                df_wfp['Data'] = pd.to_datetime(df_wfp['x'], unit='ms')
                df_wfp = df_wfp.rename(columns={'y': 'Indice Prezzi WFP'})
                dfs['wfp'] = df_wfp
    except Exception as e: 
        print(f"  [!] HTML WFP nativo non trovato per {code}, cerco nel CSV Trend")
        try:
            with zipfile.ZipFile(os.path.join(base_path, f'Grafici_Trend_{code}.zip'), 'r') as z:
                df_wfp = pd.read_csv(z.open(f'Serie_Temporale_Tutti_i_Trend_Aggregati_{code}.csv'))
                df_wfp['Data'] = pd.to_datetime(df_wfp['Data'])
                dfs['wfp'] = df_wfp[['Data', 'Indice Prezzi WFP']].groupby('Data').mean().reset_index()
        except: pass

    # Se non c'è ACLED come base, usiamo il primo dataset disponibile
    if 'acled' in dfs:
        df_master = dfs['acled'].copy()
    elif len(dfs) > 0:
        df_master = list(dfs.values())[0].copy()
    else:
        print(f"  [!] Nessun dato estratto per {code}")
        continue

    # Merge dinamico mantenendo alta risoluzione
    for k, df_temp in dfs.items():
        if k != 'acled':
            df_master = pd.merge(df_master, df_temp, on='Data', how='outer')

    df_master = df_master.sort_values('Data')
    mask = (df_master['Data'] >= cfg['start']) & (df_master['Data'] <= cfg['end'])
    df_plot = df_master.loc[mask].copy()

    # --- 3. CREAZIONE DELLA SUPER-DASHBOARD ---
    fig = make_subplots(
        rows=5, cols=2,
        shared_xaxes=False,
        vertical_spacing=0.04,  
        horizontal_spacing=0.06,
        column_widths=[0.80, 0.20],  # Rapporto 4:1 (1:4 tra radar e TS) come richiesto
        specs=[[{"type": "xy"}, {"type": "polar"}]] * 5,
        subplot_titles=(
            "<span style='color: white; font-size: 13px; font-weight: bold;'><i class='fa-solid fa-wheat-awn' style='color:#34d399'></i> Sicurezza Alimentare (IPC Fase 3+ %)</span>", "<span style='font-size: 11px;'>Stagionalità</span>",
            "<span style='color: white; font-size: 13px; font-weight: bold;'><i class='fa-solid fa-globe' style='color:#a855f7'></i> Salienza Mediatica - Conflitti (GDELT)</span>", "<span style='font-size: 11px;'>Stagionalità</span>",
            "<span style='color: white; font-size: 13px; font-weight: bold;'><i class='fa-solid fa-person-walking-arrow-right' style='color:#fbbf24'></i> Sfollati Interni (IDP)</span>", "<span style='font-size: 11px;'>Stagionalità</span>",
            "<span style='color: white; font-size: 13px; font-weight: bold;'><i class='fa-solid fa-burst' style='color:#f87171'></i> Frequenza Conflitti (ACLED)</span>", "<span style='font-size: 11px;'>Stagionalità</span>",
            "<span style='color: white; font-size: 13px; font-weight: bold;'><i class='fa-solid fa-store' style='color:#818cf8'></i> Indice Prezzi Alimentari (WFP)</span>", "<span style='font-size: 11px;'>Stagionalità</span>"
        )
    )

    def add_row(col_names_to_check, row_idx, color, name, fill='none', fillcolor=None, freq='monthly'):
        col_name = next((c for c in col_names_to_check if c in df_plot.columns), None)
        if not col_name: return
        
        # Time Series Trace (con punti marcatore visibili come su UI)
        trace_kwargs = dict(
            x=df_plot['Data'], y=df_plot[col_name], name=name, mode='lines+markers',
            line=dict(color=color, width=2, shape='spline'),
            marker=dict(size=5, color=color, line=dict(width=1, color='#0b0f19'), symbol='circle'),
            connectgaps=True, showlegend=False
        )
        if fill != 'none': trace_kwargs['fill'] = fill
        if fillcolor: trace_kwargs['fillcolor'] = fillcolor
            
        fig.add_trace(go.Scatter(**trace_kwargs), row=row_idx, col=1)
        
        # Radar Trace (Media Pre-Evento e Media Post-Evento con frequenza opportuna)
        pre_avg, post_avg, theta_row = get_radar_data(df_plot, col_name, cfg['event_date'], freq=freq)
        fig.add_trace(go.Scatterpolar(
            r=pre_avg, theta=theta_row, name='Media Pre-Evento', line=dict(color=colors['radar_hist'], width=2, dash='dot'), showlegend=(row_idx==1)
        ), row=row_idx, col=2)
        fig.add_trace(go.Scatterpolar(
            r=post_avg, theta=theta_row, name='Media Post-Evento', line=dict(color=colors['radar_2021'], width=2), fill='toself', fillcolor='rgba(239, 68, 68, 0.2)', showlegend=(row_idx==1), visible=False
        ), row=row_idx, col=2)  # Compare solo quando svelo evento

    # Popolamento righe dinamico (Primi 3 trimestrali, ultimi 2 mensili)
    add_row(['Popolazione Fase 3+ (%)', 'phase_3plus_percentage'], 1, colors['ipc_line'], 'IPC 3+ (%)', freq='trimestrale')
    add_row(['Conflitto Materiale'], 2, colors['gdelt'], 'Menzioni', freq='trimestrale')
    add_row(['Popolazione IDP', 'idp_population'], 3, colors['idp'], 'IDPs', freq='trimestrale')
    add_row(['Eventi Totali', 'acled_total_events'], 4, colors['acled_events'], 'Eventi', fill='tozeroy', fillcolor='rgba(245, 158, 11, 0.05)', freq='monthly')
    add_row(['Indice Prezzi WFP', 'wfp_price'], 5, colors['wfp_price'], 'Indice Prezzi', freq='monthly')

    # --- 4. GESTIONE EVENTO CHIAVE INTERATTIVO ---
    event_date = cfg['event_date']
    
    # Aggiunta linea evento verticale su tutte e 5 le righe temporali (x1..x5) e molto più evidente
    for i in range(1, 6):
        fig.add_shape(
            type="line", x0=event_date, x1=event_date, y0=0, y1=1,
            xref=f"x{i}" if i > 1 else "x", yref=f"y{i} domain" if i > 1 else "y domain",
            line=dict(color='#ef4444', width=3, dash="dash"),  # Più spessa, rossa e visibile
            opacity=1.0, visible=False, name=f"event_shape_{i}"
        )

    fig.add_annotation(
        x=event_date, y=1.07, yref="paper", xref="x",
        text=cfg['event_label'], showarrow=False, font=dict(color="white", size=12, family="Inter, sans-serif", weight="bold"),
        bgcolor="#ef4444", bordercolor="#ffffff", borderwidth=2, borderpad=6,
        xanchor="center", align="center", visible=False, name="event_anno"
    )

    num_shapes = len(fig.layout.shapes)
    num_annos = len(fig.layout.annotations)

    update_reveal = {f"shapes[{i}].visible": True for i in range(num_shapes-5, num_shapes)}
    update_reveal[f"annotations[{num_annos-1}].visible"] = True

    update_hide = {f"shapes[{i}].visible": False for i in range(num_shapes-5, num_shapes)}
    update_hide[f"annotations[{num_annos-1}].visible"] = False

    # Costruzione liste visibilità dinamiche per i bottoni
    reveal_vis = []
    hide_vis = []
    for tr in fig.data:
        if 'Post-Evento' in tr.name:
            reveal_vis.append(True)
            hide_vis.append(False)
        else:
            reveal_vis.append(True)
            hide_vis.append(True)

    reveal_traces = {"visible": reveal_vis}
    hide_traces = {"visible": hide_vis}

    fig.update_layout(
        updatemenus=[dict(type="buttons", direction="right", x=0.0, y=1.03, xanchor="left", yanchor="bottom", 
            bgcolor="#1e293b", font=dict(color="white", size=11, family="Inter, sans-serif"), bordercolor="#3b82f6", borderwidth=1, showactive=False,
            buttons=[
                dict(label="❓ Svela Evento Chiave", method="update", args=[reveal_traces, update_reveal]),
                dict(label="❌ Nascondi", method="update", args=[hide_traces, update_hide])
            ]
        )]
    )

    # Styling dei Radar e del Layout globale
    polars = {f"polar{i if i>1 else ''}": dict(bgcolor='#0b0f19', radialaxis=dict(gridcolor=colors['grid'], showticklabels=False), angularaxis=dict(gridcolor=colors['grid'], tickfont=dict(color=colors['text_muted'], size=8))) for i in range(1,6)}

    fig.update_layout(
        height=1200, plot_bgcolor='#0b0f19', paper_bgcolor='#0b0f19', hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.03, xanchor="right", x=1, font=dict(color=colors['text_muted'], size=10)),
        margin=dict(l=40, r=20, t=80, b=40), 
        font=dict(family="Inter, sans-serif", color=colors['text_muted']),
        hoverlabel=dict(bgcolor="#0f172a", font_size=11, font_family="Inter, sans-serif", bordercolor="rgba(255,255,255,0.12)"),
        **polars
    )

    # Sincronizza assi X e rimuove tutte le griglie come richiesto
    for i in range(1, 6):
        xaxis_name = f"xaxis{i}" if i > 1 else "xaxis"
        if xaxis_name in fig.layout:
            fig.layout[xaxis_name].update(showgrid=False, tickfont=dict(color=colors['text_muted']), showline=True, linewidth=1, linecolor='rgba(255, 255, 255, 0.2)', matches='x')
        
        yaxis_name = f"yaxis{i}" if i > 1 else "yaxis"
        if yaxis_name in fig.layout:
            fig.layout[yaxis_name].update(showgrid=False, tickfont=dict(color=colors['text_muted'], size=9), zeroline=False, showline=True, linewidth=1, linecolor='rgba(255, 255, 255, 0.15)')

    # --- 5. SALVATAGGIO ROBUSTO NELLA CARTELLA DELLO SCRIPT ---
    output_filename = os.path.join(script_dir, f'Dashboard_{code}_Storytelling.html')
    fig.write_html(output_filename, include_plotlyjs='cdn')
    print(f"  [OK] Salvato: {output_filename}")

print("\nTutte le dashboard sono state generate con successo!")