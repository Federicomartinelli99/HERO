import sys
import pandas as pd
import altair as alt
from pathlib import Path

# Aggiunge il path per importare utils e plotter
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "data_plots"))
from utils import setup_logger
from plotter import generate_all_plots, load_reconciled_data

logger = setup_logger("04_plot_matches", "04_plot_matches.log")

def main():
    logger.info("==================================================")
    logger.info("AVVIO STEP 4: GENERAZIONE GRAFICO LIVELLI MATCH")
    logger.info("==================================================")
    
    workspace_dir = Path(__file__).resolve().parent.parent.parent.parent
    reconciled_dir = workspace_dir / "hero_v4" / "data" / "reconciled"
    plots_dir = workspace_dir / "hero_v4" / "data" / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)
    reconciled_csv_path = reconciled_dir / "ipc_wfp_reconciled.csv"
    
    if not reconciled_csv_path.exists():
        logger.error(f"File allineato non trovato in {reconciled_csv_path}. Eseguire lo Step 3 prima.")
        return
        
    logger.info(f"Caricamento dati allineati da {reconciled_csv_path.name}...")
    df = load_reconciled_data(reconciled_csv_path)
    
    # 1. Calcolo dei conteggi per combinazione Paese/Match Level
    logger.info("Preparazione dei dati per il grafico...")
    chart_data = df.groupby(['Country', 'wfp_match_level']).size().reset_index(name='count')
    
    # 2. Definizione colori e livelli
    domain_levels = ['Admin2', 'Admin1_Code', 'Admin1_Name', 'National', 'No_Match']
    # Ripristino della palette originale coerente dal punto di vista semantico:
    # Verde (Admin2), Verde Scuro (Admin1_Code), Blu (Admin1_Name), Arancione (National), Grigio (No_Match)
    color_range = ['#2ca02c', '#117768', '#1f3b8b', '#ffa600', '#a2a9b1'] 
    
    # Ordinamento cromatico coerente (Admin2 in alto, No_Match in basso)
    sort_map = {level: i for i, level in enumerate(domain_levels)}
    chart_data['sort_index'] = chart_data['wfp_match_level'].map(sort_map)

    
    # 3. Creazione del grafico Altair
    logger.info("Generazione del grafico Altair...")
    chart = alt.Chart(chart_data).mark_bar().encode(
        x=alt.X('Country:N', 
                title='Paese', 
                sort='ascending',
                axis=alt.Axis(labelAngle=-90)),
        
        y=alt.Y('count:Q', 
                stack='normalize', 
                title='Frazione Analisi', 
                axis=alt.Axis(format='%')),
        
        color=alt.Color('wfp_match_level:N', 
                        scale=alt.Scale(domain=domain_levels, range=color_range),
                        legend=alt.Legend(title="Risoluzione Match")),
        
        order=alt.Order('sort_index:Q'),
        tooltip=['Country', 'wfp_match_level', 'count']
    ).properties(
        width=800,
        height=400,
        title=alt.TitleParams(
            text='Distribuzione Livelli di Match Spaziale — WFP (hero_v4)',
            subtitle='Quota di righe IPC associate a ciascun livello di fallback gerarchico',
            anchor='start',
            fontSize=16,
            subtitleFontSize=12,
            subtitleColor='gray'
        )
    ).configure_axis(
        grid=False
    ).configure_view(
        strokeWidth=0
    )

    
    # 4. Salvataggio grafico
    sub_dir = plots_dir / "distributions"
    sub_dir.mkdir(parents=True, exist_ok=True)
    out_html = sub_dir / "wfp_match_distribution.html"
    logger.info(f"Salvataggio del grafico interattivo in HTML: {out_html}")
    chart.save(str(out_html))
    
    # Tentativo di salvare come PNG
    out_png = sub_dir / "wfp_match_distribution.png"
    try:
        logger.info(f"Tentativo di salvataggio del grafico in PNG: {out_png}")
        # Se vl-convert-python o selenium o altair_viewer sono configurati nel sistema
        chart.save(str(out_png))
        logger.info(f"Grafico PNG salvato correttamente in {out_png.name}")
    except Exception as e:
        logger.warning(f"Impossibile salvare direttamente in PNG (mancano le dipendenze di export di altair): {e}")
        logger.warning("Il file HTML interattivo è stato comunque creato ed è pronto per essere visualizzato.")
        
    # 5. Generazione della suite completa di grafici
    logger.info("Generazione della suite completa di grafici (correlazioni, serie temporali, mappe geografiche)...")
    try:
        generate_all_plots(df, save_dir=plots_dir)
        logger.info("Suite completa di grafici generata con successo!")
    except Exception as e:
        logger.error(f"Errore durante la generazione della suite completa di grafici: {e}")
        
    logger.info("✨ STEP 4 COMPLETATO CON SUCCESSO!")
    logger.info("==================================================")

if __name__ == "__main__":
    main()
