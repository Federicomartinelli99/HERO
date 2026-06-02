import os
import sys
import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns

def main():
    print("==================================================")
    print("AVVIO GENERAZIONE PLOT STATICI HERO v5")
    print("==================================================")
    
    workspace_dir = Path(__file__).resolve().parent.parent.parent
    data_dir = workspace_dir / "hero_v5" / "data"
    plots_dir = workspace_dir / "hero_v5" / "plots" / "static"
    plots_dir.mkdir(parents=True, exist_ok=True)
    
    reconciled_path = data_dir / "hero_v5_reconciled_v5.parquet"
    if not reconciled_path.exists():
        print(f"File reconciled non trovato in {reconciled_path}. Eseguire la pipeline prima.")
        return
        
    print("Caricamento dataset reconciled...")
    df = pd.read_parquet(reconciled_path)
    
    # ── PLOT 1: SPATIAL MISMATCH HOTSPOTS (PEGGIORI REGIONI) ──
    print("Generazione Plot 1: Hotspot Spaziali di Mismatch...")
    indicators = ['has_geojson', 'has_rainfall', 'has_wfp', 'has_idp', 'has_acled_events', 'has_acled_fatalities']
    df['avail_score'] = df[indicators].sum(axis=1) / len(indicators) * 100
    df['mismatch_score'] = 100 - df['avail_score']
    
    # Raggruppiamo per adm2_pcode e calcoliamo il mismatch medio
    if 'adm2_pcode' in df.columns and 'Area' in df.columns:
        adm2_stats = (
            df[df['adm2_pcode'] != ""]
            .groupby('adm2_pcode')
            .agg(mismatch=('mismatch_score', 'mean'), name=('Area', 'first'), country=('Country', 'first'))
            .reset_index()
            .sort_values(by='mismatch', ascending=False)
            .head(20)
        )
        
        if not adm2_stats.empty:
            plt.figure(figsize=(12, 7))
            sns.set_theme(style="darkgrid")
            colors = sns.color_palette("flare", len(adm2_stats))
            
            # Label personalizzate: "Country - District (PCode)"
            labels = [f"{row['country']} - {row['name']} ({row['adm2_pcode']})" for _, row in adm2_stats.iterrows()]
            
            ax = sns.barplot(
                x='mismatch',
                y=labels,
                data=adm2_stats,
                hue=labels,
                palette=colors,
                legend=False
            )
            
            plt.title("Top 20 Region Admin2 (Distretti) con il Maggior Tasso di Mismatch", fontsize=14, fontweight='bold', pad=15)
            plt.xlabel("Tasso di Mismatch Medio (% di dati mancanti/scollegati)", fontsize=11)
            plt.ylabel("Regione Admin2 (Paese - Nome Distretto)", fontsize=11)
            plt.xlim(0, 105)
            
            # Aggiunge etichette di valore sulle barre
            for p in ax.patches:
                width = p.get_width()
                ax.text(width + 1, p.get_y() + p.get_height()/2, f"{width:.1f}%", 
                        va='center', ha='left', fontsize=9, fontweight='semibold')
                        
            plt.tight_layout()
            out_plot1 = plots_dir / "spatial_mismatch_hotspots.png"
            plt.savefig(out_plot1, dpi=300)
            plt.close()
            print(f"  -> Plot salvato in: {out_plot1}")
            
    # ── PLOT 2: TEMPORAL MISMATCH TRENDS ──
    print("Generazione Plot 2: Trend Temporali di Mismatch...")
    df['year_quarter'] = pd.to_datetime(df['From']).dt.to_period('Q').astype(str)
    temporal_stats = df.groupby('year_quarter')['mismatch_score'].mean().reset_index().sort_values('year_quarter')
    
    if not temporal_stats.empty:
        plt.figure(figsize=(12, 6))
        sns.lineplot(
            x='year_quarter',
            y='mismatch_score',
            data=temporal_stats,
            marker='o',
            color='#ef4444',
            linewidth=2.5,
            markersize=8
        )
        
        plt.title("Evoluzione Temporale del Tasso di Mismatch Medio", fontsize=14, fontweight='bold', pad=15)
        plt.xlabel("Anno-Trimestre", fontsize=11)
        plt.ylabel("Tasso di Mismatch Medio (%)", fontsize=11)
        plt.ylim(0, 105)
        plt.xticks(rotation=45)
        
        # Aggiunge etichette di valore sui punti principali
        for idx, row in temporal_stats.iterrows():
            plt.text(row['year_quarter'], row['mismatch_score'] + 2, f"{row['mismatch_score']:.1f}%", 
                     ha='center', va='bottom', fontsize=8, color='#334155', fontweight='semibold')
                     
        plt.tight_layout()
        out_plot2 = plots_dir / "temporal_mismatch_trends.png"
        plt.savefig(out_plot2, dpi=300)
        plt.close()
        print(f"  -> Plot salvato in: {out_plot2}")
        
    # ── PLOT 3: WFP COMMODITY COVERAGE HEATMAP ──
    print("Generazione Plot 3: Heatmap Copertura Commodity WFP...")
    # Troviamo colonne aggregate delle commodity
    commodity_cols = [c for c in df.columns if c.startswith("WFP_avg_c_") and c != "WFP_avg_c_food_price_index"]
    
    if commodity_cols:
        # Selezioniamo le 15 commodity più frequenti (con meno NaNs complessivi)
        null_rates = df[commodity_cols].isnull().mean().sort_values()
        top_commodities = null_rates.head(15).index.tolist()
        
        # Calcoliamo la copertura (1 - null_rate) per paese per ciascuna commodity
        countries = df['Country'].unique()
        coverage_data = []
        for country in countries:
            df_c = df[df['Country'] == country]
            row_cov = {}
            for col in top_commodities:
                # Copertura commodity nel paese
                cov = (1 - df_c[col].isnull().mean()) * 100 if len(df_c) > 0 else 0.0
                clean_name = col.replace("WFP_avg_c_", "").replace("_", " ").title()
                row_cov[clean_name] = cov
            row_cov['Country'] = country
            coverage_data.append(row_cov)
            
        df_cov = pd.DataFrame(coverage_data).set_index('Country')
        
        if not df_cov.empty:
            plt.figure(figsize=(14, 10))
            sns.heatmap(
                df_cov,
                cmap="YlGnBu",
                annot=True,
                fmt=".0f",
                cbar_kws={'label': 'Tasso di Copertura (%)'},
                linewidths=0.5,
                linecolor='white'
            )
            
            plt.title("Matrice di Copertura delle Top 15 Commodity Alimentari WFP per Paese (%)", fontsize=14, fontweight='bold', pad=15)
            plt.xlabel("Commodity Alimentari", fontsize=11)
            plt.ylabel("Paese (ISO3)", fontsize=11)
            plt.tight_layout()
            
            out_plot3 = plots_dir / "wfp_commodity_coverage_heatmap.png"
            plt.savefig(out_plot3, dpi=300)
            plt.close()
            print(f"  -> Plot salvato in: {out_plot3}")
            
    print("==================================================")
    print("GENERAZIONE PLOT COMPLETATA CON SUCCESSO!")
    print("==================================================")

if __name__ == "__main__":
    main()
