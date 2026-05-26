import os
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
from libs.logger_config import get_logger

logger = get_logger("bulk_exporter")

def esporta_dashboard_avanzate(manager, output_folder="img/paesi"):
    target_path = Path(output_folder)
    target_path.mkdir(parents=True, exist_ok=True)
    
    tutti_i_paesi = list(manager._iso3_to_name.keys())
    logger.info(f"🚀 Inizio esportazione batch per {len(tutti_i_paesi)} paesi...")
    
    for iso3 in tutti_i_paesi:
        nome_paese = manager._iso3_to_name[iso3]
        file_output = target_path / f"{iso3}_dashboard.html"
        
        try:
            logger.info(f"📊 Generazione: {nome_paese} ({iso3})")
            
            # 1. Caricamento Dati Pigro (Solo il paese corrente)
            country = manager.get_country(iso3)
            df = country._data
            if df.empty: 
                continue
            
            # --- SETUP GRIGLIA 2x2 PLOTLY ---
            fig = make_subplots(
                rows=2, cols=2,
                column_widths=[0.6, 0.4], # La mappa e le barre a dx saranno un po' più strette
                row_heights=[0.5, 0.5],
                horizontal_spacing=0.08,
                vertical_spacing=0.12,
                subplot_titles=(
                    f"1. Trend Macroeconomico: Inflazione Alimentare", 
                    f"2. Posizione Geografica Mercati WFP",
                    "3. Incertezza e Volatilità per Regione (ADM1)",
                    "4. Shock Materie Prime (Ultimo Anno)"
                ),
                specs=[
                    [{"type": "xy"}, {"type": "map"}], # Specifichiamo che la cella (1,2) è una MAPPA
                    [{"type": "xy"}, {"type": "xy"}]
                ]
            )
            
            # =================================================================
            # PANNELLO 1 (Top-Left): Trend Storico Nazionale
            # =================================================================
            df_inf = country.get_inflation_series().groupby('date')['inflation_food_price_index'].mean().reset_index()
            fig.add_trace(
                go.Scatter(
                    x=df_inf['date'], y=df_inf['inflation_food_price_index'], 
                    name="Inflazione", line=dict(color="#d32f2f", width=2)
                ),
                row=1, col=1
            )
            
            # =================================================================
            # PANNELLO 2 (Top-Right): Mappa Esatta del Paese con i Mercati
            # =================================================================
            # Estraiamo le coordinate univoche di tutti i mercati mai monitorati nel paese
            df_mercati = df.dropna(subset=['lat', 'lon', 'mkt_name']).drop_duplicates(subset=['mkt_name'])
            
            if not df_mercati.empty:
                # Creiamo la traccia geografica
                mappa = px.scatter_map(
                    df_mercati, lat="lat", lon="lon",
                    hover_name="mkt_name",
                    hover_data={"adm1_name": True, "lat": False, "lon": False},
                    color_discrete_sequence=["#1976D2"], # Blu istituzionale WFP
                    size_max=10
                )
                # Spostiamo la traccia nel Subplot 
                for trace in mappa.data:
                    trace.marker.size = 8 # Dimensione fissa dei mercati
                    fig.add_trace(trace, row=1, col=2)
                
                # Centriamo la telecamera della mappa ESATTAMENTE sul paese
                fig.update_layout(
                    map=dict(
                        style="carto-positron",
                        center=dict(lat=df_mercati["lat"].mean(), lon=df_mercati["lon"].mean()),
                        zoom=4.5 # Zoom sufficiente per vedere i confini nazionali
                    )
                )

            # =================================================================
            # PANNELLO 3 (Bottom-Left): Distribuzione Prezzi / Regione (Boxplot)
            # =================================================================
            df_box = df[df['year'] == df['year'].max()].dropna(subset=['inflation_food_price_index', 'adm1_name'])
            if not df_box.empty:
                fig.add_trace(
                    go.Box(
                        x=df_box['adm1_name'], y=df_box['inflation_food_price_index'], 
                        name="Variazione Regionale", marker_color="#388E3C"
                    ),
                    row=2, col=1
                )
                
            # =================================================================
            # PANNELLO 4 (Bottom-Right): Classifica Shock per Commodity
            # =================================================================
            comm_disp = country.available_commodities[:10] # Prendiamo le 10 materie prime principali
            df_comm = country.get_commodity_trends(comm_disp)
            if not df_comm.empty:
                # Calcoliamo l'aumento di prezzo dall'inizio alla fine del dataset per ogni bene
                delta_prezzi = {}
                for c in comm_disp:
                    if c in df_comm.columns:
                        valori = df_comm[c].dropna()
                        if len(valori) > 2:
                            # Variazione tra l'inizio e la fine della misurazione
                            delta_prezzi[c] = valori.iloc[-1] - valori.iloc[0]
                
                if delta_prezzi:
                    df_delta = pd.DataFrame(list(delta_prezzi.items()), columns=['Commodity', 'Delta_Prezzo']).sort_values(by='Delta_Prezzo')
                    fig.add_trace(
                        go.Bar(
                            x=df_delta['Delta_Prezzo'], y=df_delta['Commodity'], 
                            orientation='h', marker_color="#F57C00"
                        ),
                        row=2, col=2
                    )

            # =================================================================
            # CONFIGURAZIONE FINALE ESTETICA DELLA DASHBOARD
            # =================================================================
            fig.update_layout(
                title=dict(
                    text=f"🏢 WFP H.E.R.O. REPORT: {nome_paese.upper()}",
                    font=dict(size=24, family="Arial", weight="bold")
                ),
                height=900, # Dashboard bella verticale e leggibile
                showlegend=False,
                margin=dict(l=40, r=40, t=80, b=40),
                paper_bgcolor="white",
                plot_bgcolor="rgba(0,0,0,0)"
            )
            
            # Aggiungiamo le griglie grigie ai grafici cartesiani per leggibilità
            fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
            fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')

            # Salva il file interattivo
            fig.write_html(str(file_output), include_plotlyjs="cdn")
            
        except Exception as e:
            logger.error(f"❌ Errore durante l'esportazione di {iso3}: {e}")
            continue

    logger.info(f"✨ Report completati. Dashboard salvate in: '{output_folder}'")