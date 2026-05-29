"""
hero_v4/libs/data_plots/advanced_plots.py

Modulo avanzato di visualizzazione per il dataset riconciliato IPC-WFP-Rainfall.
Organizzato in classi tematiche per massima modularità e riusabilità.

Ogni classe produce grafici focalizzati su un aspetto specifico dell'analisi:
  - SeverityAnalytics:    analisi della severità IPC per paese/regione
  - DataQualityDashboard: diagnostica completezza e qualità dati
  - MultivariatePlots:    relazioni tra variabili (prezzi, pioggia, IPC)
  - TemporalAnalytics:    analisi delle dinamiche temporali
  - GeographicPlots:      heatmap geografiche e confronti regionali

Autore: HERO Pipeline v4
"""

import os
import pandas as pd
import numpy as np
import altair as alt
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
from pathlib import Path
from typing import Optional, List, Dict, Tuple


# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURAZIONE GLOBALE
# ─────────────────────────────────────────────────────────────────────────────

# Palette professionale coerente con il resto del progetto
PALETTE = {
    "primary":     "#1f3b8b",
    "secondary":   "#117768",
    "accent":      "#ff7f0e",
    "danger":      "#d62728",
    "success":     "#2ca02c",
    "muted":       "#a2a9b1",
    "bg_light":    "#f8f9fa",
    "bg_dark":     "#2c3e50",
    "gradient_5":  ["#2ca02c", "#8cc63f", "#ffa600", "#e85d04", "#d62728"],
}

IPC_PHASE_COLORS = {
    "Phase 1 (Minimal)":  "#c6dbef",
    "Phase 2 (Stressed)": "#fdae6b",
    "Phase 3 (Crisis)":   "#fb6a4a",
    "Phase 4 (Emergency)":"#de2d26",
    "Phase 5 (Famine)":   "#67000d",
}

PHASE_COLS = [
    "phase_1_percentage", "phase_2_percentage", "phase_3_percentage",
    "phase_4_percentage", "phase_5_percentage",
]

PHASE_LABELS = [
    "Phase 1 (Minimal)", "Phase 2 (Stressed)", "Phase 3 (Crisis)",
    "Phase 4 (Emergency)", "Phase 5 (Famine)",
]

# Configura Altair per dataset medio-grandi
alt.data_transformers.disable_max_rows()

# Matplotlib defaults
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 11,
    "axes.titlesize": 14,
    "axes.titleweight": "bold",
    "axes.labelsize": 12,
    "figure.facecolor": "white",
    "savefig.facecolor": "white",
    "savefig.bbox": "tight",
    "savefig.dpi": 150,
})


# ─────────────────────────────────────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def _get_save_dir() -> Path:
    """Restituisce il percorso predefinito per il salvataggio dei grafici."""
    current_dir = Path(__file__).resolve().parent
    return current_dir.parent.parent / "data" / "plots"


def _ensure_dir(path: Path) -> Path:
    """Crea la directory se non esiste e la restituisce."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def _save_altair(chart: alt.Chart, directory: Path, name: str) -> Path:
    """Salva un grafico Altair come HTML e tenta PNG."""
    html_path = directory / f"{name}.html"
    chart.save(str(html_path))
    try:
        png_path = directory / f"{name}.png"
        chart.save(str(png_path))
    except Exception:
        pass
    return html_path


def _save_plotly(fig, directory: Path, name: str) -> Path:
    """Salva un grafico Plotly come HTML."""
    html_path = directory / f"{name}.html"
    fig.write_html(str(html_path))
    return html_path


def _save_matplotlib(fig: plt.Figure, directory: Path, name: str) -> Path:
    """Salva un grafico Matplotlib come PNG."""
    png_path = directory / f"{name}.png"
    fig.savefig(png_path, bbox_inches="tight", dpi=150)
    plt.close(fig)
    return png_path


def _prepare_df(df: pd.DataFrame) -> pd.DataFrame:
    """Prepara il dataframe con colonne derivate comuni."""
    df = df.copy()
    if "From" in df.columns:
        df["date_from"] = pd.to_datetime(df["From"], format="%d/%m/%Y", errors="coerce")
    if "To" in df.columns:
        df["date_to"] = pd.to_datetime(df["To"], format="%d/%m/%Y", errors="coerce")
    if "date_from" in df.columns:
        df["year"] = df["date_from"].dt.year
        df["quarter"] = df["date_from"].dt.to_period("Q").astype(str)
        df["year_month"] = df["date_from"].dt.to_period("M").astype(str)
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 1. SEVERITY ANALYTICS
# ─────────────────────────────────────────────────────────────────────────────

class SeverityAnalytics:
    """Grafici incentrati sulla distribuzione e il ranking della severità IPC."""

    @staticmethod
    def plot_phase_distribution_stacked(df: pd.DataFrame, save_dir: Optional[Path] = None) -> alt.Chart:
        """
        Stacked bar chart 100% delle 5 fasi IPC per paese.
        Mostra la composizione della popolazione per ciascuna fase di insicurezza alimentare.
        """
        out_dir = _ensure_dir((save_dir or _get_save_dir()) / "severity")

        # Aggrega medie per paese
        agg = df.groupby("Country")[PHASE_COLS].mean().reset_index()
        melted = agg.melt(id_vars="Country", var_name="phase_raw", value_name="percentage")
        phase_map = dict(zip(PHASE_COLS, PHASE_LABELS))
        melted["Phase"] = melted["phase_raw"].map(phase_map)

        sort_order = list(IPC_PHASE_COLORS.keys())
        color_values = list(IPC_PHASE_COLORS.values())

        chart = (
            alt.Chart(melted)
            .mark_bar()
            .encode(
                x=alt.X("Country:N", title="Paese",
                         sort=alt.EncodingSortField(field="percentage", op="sum", order="descending"),
                         axis=alt.Axis(labelAngle=-45, labelFontSize=9)),
                y=alt.Y("percentage:Q", stack="normalize", title="Distribuzione Popolazione",
                         axis=alt.Axis(format="%")),
                color=alt.Color("Phase:N",
                                scale=alt.Scale(domain=sort_order, range=color_values),
                                legend=alt.Legend(title="Fase IPC", orient="right")),
                order=alt.Order("phase_raw:N"),
                tooltip=["Country", "Phase", alt.Tooltip("percentage:Q", format=".1%")],
            )
            .properties(
                width=750, height=400,
                title=alt.TitleParams(
                    text="Composizione Fasi IPC per Paese",
                    subtitle="Distribuzione media della popolazione nelle 5 fasi di insicurezza alimentare",
                    fontSize=16, subtitleFontSize=11, subtitleColor="gray",
                ),
            )
            .configure_axis(grid=False)
            .configure_view(strokeWidth=0)
        )

        _save_altair(chart, out_dir, "ipc_phase_distribution")
        print(f"  [OK] IPC Phase Distribution salvato in: {out_dir}")
        return chart

    @staticmethod
    def plot_severity_ranking(df: pd.DataFrame, save_dir: Optional[Path] = None) -> alt.Chart:
        """
        Horizontal bar chart ranking tutti i paesi per severità media Phase 3+.
        Colore della barra indica la severità, punti rossi = % dati WFP mancanti.
        """
        out_dir = _ensure_dir((save_dir or _get_save_dir()) / "severity")

        agg = df.groupby("Country").agg(
            severity=("phase_3plus_percentage", "mean"),
            wfp_missing=("WFP_avg_price", lambda x: x.isna().mean()),
        ).reset_index()
        agg["severity_pct"] = agg["severity"] * 100
        agg["wfp_missing_pct"] = agg["wfp_missing"] * 100

        bars = (
            alt.Chart(agg)
            .mark_bar(cornerRadiusEnd=3)
            .encode(
                y=alt.Y("Country:N", sort="-x", title=None,
                         axis=alt.Axis(labelFontSize=10)),
                x=alt.X("severity_pct:Q", title="Severità IPC Media (% Popolazione in Fase 3+)"),
                color=alt.Color("severity_pct:Q",
                                scale=alt.Scale(scheme="orangered"),
                                legend=alt.Legend(title="Severità %")),
                tooltip=["Country", alt.Tooltip("severity_pct:Q", format=".1f", title="Severità 3+ (%)"),
                          alt.Tooltip("wfp_missing_pct:Q", format=".1f", title="Dati WFP Mancanti (%)")],
            )
        )

        dots = (
            alt.Chart(agg)
            .mark_circle(size=50, color=PALETTE["danger"], opacity=0.8)
            .encode(
                y=alt.Y("Country:N", sort="-x"),
                x=alt.X("wfp_missing_pct:Q"),
                tooltip=[alt.Tooltip("wfp_missing_pct:Q", format=".1f", title="Dati WFP Mancanti (%)")],
            )
        )

        chart = (
            (bars + dots)
            .properties(
                width=550, height=max(len(agg) * 18, 250),
                title=alt.TitleParams(
                    text="Ranking Severità Insicurezza Alimentare (IPC 3+)",
                    subtitle="Barre = severità media | Punti rossi = % dati WFP mancanti",
                    fontSize=15, subtitleFontSize=11, subtitleColor="gray",
                ),
            )
            .configure_axis(grid=False)
            .configure_view(strokeWidth=0)
        )

        _save_altair(chart, out_dir, "severity_ranking")
        print(f"  [OK] Severity Ranking salvato in: {out_dir}")
        return chart

    @staticmethod
    def plot_top_crisis_areas(df: pd.DataFrame, top_n: int = 30,
                              save_dir: Optional[Path] = None) -> alt.Chart:
        """
        Top-N aree (Level 1 / Area) con la più alta severità media Phase 3+.
        Utile per identificare i distretti critici a livello globale.
        """
        out_dir = _ensure_dir((save_dir or _get_save_dir()) / "severity")

        agg = (
            df.dropna(subset=["phase_3plus_percentage"])
            .groupby(["Country", "Level 1", "Area"])
            .agg(
                severity=("phase_3plus_percentage", "mean"),
                obs_count=("phase_3plus_percentage", "size"),
            )
            .reset_index()
            .sort_values("severity", ascending=False)
            .head(top_n)
        )
        agg["severity_pct"] = agg["severity"] * 100
        agg["label"] = agg["Country"] + " — " + agg["Area"].fillna(agg["Level 1"])

        chart = (
            alt.Chart(agg)
            .mark_bar(cornerRadiusEnd=3)
            .encode(
                y=alt.Y("label:N", sort="-x", title=None,
                         axis=alt.Axis(labelFontSize=9, labelLimit=280)),
                x=alt.X("severity_pct:Q", title="Severità Media (% Fase 3+)"),
                color=alt.Color("Country:N", legend=alt.Legend(title="Paese", columns=2)),
                tooltip=["Country", "Level 1", "Area",
                          alt.Tooltip("severity_pct:Q", format=".1f"),
                          alt.Tooltip("obs_count:Q", title="N. Osservazioni")],
            )
            .properties(
                width=500, height=max(top_n * 20, 200),
                title=alt.TitleParams(
                    text=f"Top {top_n} Aree Critiche — Severità IPC Fase 3+",
                    subtitle="Aree con la più alta percentuale media di popolazione in crisi",
                    fontSize=15, subtitleFontSize=11, subtitleColor="gray",
                ),
            )
            .configure_axis(grid=False)
            .configure_view(strokeWidth=0)
        )

        _save_altair(chart, out_dir, "top_crisis_areas")
        print(f"  [OK] Top Crisis Areas salvato in: {out_dir}")
        return chart


# ─────────────────────────────────────────────────────────────────────────────
# 2. DATA QUALITY DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────

class DataQualityDashboard:
    """Grafici per diagnosticare la completezza e la qualità dei dati."""

    @staticmethod
    def plot_null_heatmap(df: pd.DataFrame, save_dir: Optional[Path] = None) -> plt.Figure:
        """
        Heatmap (Seaborn) della percentuale di valori nulli per paese e feature.
        Permette di identificare rapidamente lacune nei dati.
        """
        out_dir = _ensure_dir((save_dir or _get_save_dir()) / "data_quality")

        feature_cols = [
            "Rain_avg_r1h", "Rain_avg_rfq",
            "WFP_avg_price", "WFP_avg_inflation",
            "phase_3plus_percentage", "phase_3plus_number",
        ]
        feature_cols = [c for c in feature_cols if c in df.columns]

        null_pct = (
            df.groupby("Country")[feature_cols]
            .apply(lambda g: g.isna().mean() * 100)
            .reset_index()
        )
        null_pivot = null_pct.set_index("Country")

        # Ordinamento per nullità media decrescente
        null_pivot = null_pivot.loc[null_pivot.mean(axis=1).sort_values(ascending=False).index]

        fig, ax = plt.subplots(figsize=(10, max(len(null_pivot) * 0.35, 6)), dpi=150)
        sns.heatmap(
            null_pivot,
            annot=True, fmt=".0f", cmap="Reds",
            linewidths=0.3, linecolor="white",
            cbar_kws={"label": "% Valori Nulli", "shrink": 0.6},
            ax=ax,
        )
        ax.set_title("Mappa dei Dati Mancanti per Paese e Feature", fontweight="bold", pad=15)
        ax.set_xlabel("Feature")
        ax.set_ylabel("")
        plt.tight_layout()

        _save_matplotlib(fig, out_dir, "null_heatmap")
        print(f"  [OK] Null Heatmap salvato in: {out_dir}")
        return fig

    @staticmethod
    def plot_observation_density(df: pd.DataFrame, save_dir: Optional[Path] = None) -> alt.Chart:
        """
        Bubble chart della densità osservazioni: ogni bolla = un paese,
        dimensione = numero totale di analisi IPC, colore = % match WFP.
        """
        out_dir = _ensure_dir((save_dir or _get_save_dir()) / "data_quality")

        agg = df.groupby("Country").agg(
            n_rows=("Country", "size"),
            wfp_coverage=("wfp_match_level", lambda x: (x != "No_Match").mean()),
            rain_coverage=("rain_match_level", lambda x: (x != "No_Match").mean()),
            n_areas=("Area", "nunique"),
        ).reset_index()
        agg["wfp_coverage_pct"] = agg["wfp_coverage"] * 100
        agg["rain_coverage_pct"] = agg["rain_coverage"] * 100

        chart = (
            alt.Chart(agg)
            .mark_circle(opacity=0.8, stroke="black", strokeWidth=0.5)
            .encode(
                x=alt.X("wfp_coverage_pct:Q", title="Copertura WFP (%)",
                         scale=alt.Scale(domain=[0, 105])),
                y=alt.Y("rain_coverage_pct:Q", title="Copertura Rainfall (%)",
                         scale=alt.Scale(domain=[0, 105])),
                size=alt.Size("n_rows:Q", title="N. Analisi IPC",
                              scale=alt.Scale(range=[50, 1500])),
                color=alt.Color("n_areas:Q", title="N. Aree Distinte",
                                scale=alt.Scale(scheme="viridis")),
                tooltip=[
                    "Country",
                    alt.Tooltip("n_rows:Q", title="Analisi IPC Totali"),
                    alt.Tooltip("n_areas:Q", title="Aree Distinte"),
                    alt.Tooltip("wfp_coverage_pct:Q", format=".1f", title="Copertura WFP (%)"),
                    alt.Tooltip("rain_coverage_pct:Q", format=".1f", title="Copertura Rainfall (%)"),
                ],
            )
            .properties(
                width=600, height=450,
                title=alt.TitleParams(
                    text="Densità Osservazioni e Copertura Dati per Paese",
                    subtitle="Dimensione bolla = N. righe IPC | Colore = N. aree distinte",
                    fontSize=15, subtitleFontSize=11, subtitleColor="gray",
                ),
            )
            .configure_axis(grid=True, gridOpacity=0.15)
            .configure_view(strokeWidth=0)
        )

        _save_altair(chart, out_dir, "observation_density")
        print(f"  [OK] Observation Density salvato in: {out_dir}")
        return chart

    @staticmethod
    def plot_match_level_sankey(df: pd.DataFrame, save_dir: Optional[Path] = None):
        """
        Diagramma Sankey (Plotly) che mostra il flusso delle righe IPC
        attraverso i livelli di match WFP e Rainfall.
        """
        out_dir = _ensure_dir((save_dir or _get_save_dir()) / "data_quality")

        wfp_levels = ["Admin2", "Admin1_Code", "Admin1_Name", "National", "No_Match"]
        rain_levels = ["Admin2", "Admin1", "National", "No_Match"]

        # Calcola i flussi
        flow_data = (
            df.groupby(["wfp_match_level", "rain_match_level"])
            .size()
            .reset_index(name="count")
        )

        # Nodi
        wfp_nodes = [f"WFP: {l}" for l in wfp_levels]
        rain_nodes = [f"Rain: {l}" for l in rain_levels]
        all_nodes = wfp_nodes + rain_nodes
        node_idx = {n: i for i, n in enumerate(all_nodes)}

        # Colori nodi (palette originale coerente)
        wfp_colors = ["#2ca02c", "#117768", "#1f3b8b", "#ffa600", "#a2a9b1"]
        rain_colors = ["#4682b4", "#1f77b4", "#aec7e8", "#d3d3d3"]
        node_colors = wfp_colors + rain_colors


        def _hex_to_rgba(hex_color, alpha=0.3):
            """Convert #RRGGBB hex color to rgba() string."""
            h = hex_color.lstrip("#")
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            return f"rgba({r},{g},{b},{alpha})"

        sources, targets, values, link_colors = [], [], [], []
        for _, row in flow_data.iterrows():
            src = f"WFP: {row['wfp_match_level']}"
            tgt = f"Rain: {row['rain_match_level']}"
            if src in node_idx and tgt in node_idx:
                sources.append(node_idx[src])
                targets.append(node_idx[tgt])
                values.append(row["count"])
                link_colors.append(_hex_to_rgba(node_colors[node_idx[src]]))

        fig = go.Figure(go.Sankey(
            node=dict(pad=15, thickness=20, line=dict(color="black", width=0.5),
                      label=all_nodes, color=node_colors),
            link=dict(source=sources, target=targets, value=values, color=link_colors),
        ))
        fig.update_layout(
            title_text="Flusso dei Livelli di Match: WFP -> Rainfall",
            title_font_size=16,
            font_size=11,
            template="plotly_white",
            height=500,
        )

        _save_plotly(fig, out_dir, "match_level_sankey")
        print(f"  [OK] Match Level Sankey salvato in: {out_dir}")
        return fig


# ─────────────────────────────────────────────────────────────────────────────
# 3. MULTIVARIATE PLOTS
# ─────────────────────────────────────────────────────────────────────────────

class MultivariatePlots:
    """Grafici per esplorare le relazioni tra le diverse variabili."""

    @staticmethod
    def plot_price_severity_bubble(df: pd.DataFrame, save_dir: Optional[Path] = None):
        """
        Bubble chart (Plotly): prezzo medio WFP vs severità IPC per paese.
        Dimensione bolla = popolazione, colore = inflazione media.
        """
        out_dir = _ensure_dir((save_dir or _get_save_dir()) / "multivariate")

        agg = df.groupby("Country").agg(
            avg_price=("WFP_avg_price", "mean"),
            avg_severity=("phase_3plus_percentage", "mean"),
            avg_inflation=("WFP_avg_inflation", "mean"),
            population=("Total country population", "max"),
        ).dropna(subset=["avg_price", "avg_severity"]).reset_index()

        agg["severity_pct"] = agg["avg_severity"] * 100
        agg["pop_millions"] = agg["population"] / 1e6

        fig = px.scatter(
            agg, x="avg_price", y="severity_pct",
            size="pop_millions", color="avg_inflation",
            hover_name="Country",
            hover_data={"avg_price": ":.2f", "severity_pct": ":.1f",
                        "avg_inflation": ":.2f", "pop_millions": ":.1f"},
            color_continuous_scale="RdYlGn_r",
            size_max=55,
            labels={
                "avg_price": "Prezzo Alimentare Medio WFP",
                "severity_pct": "Severità IPC Fase 3+ (%)",
                "avg_inflation": "Inflazione Media",
                "pop_millions": "Popolazione (M)",
            },
            title="Relazione Prezzi Alimentari, Inflazione e Severità Crisi per Paese",
        )
        fig.update_layout(template="plotly_white", height=550,
                          title_font_size=16)

        _save_plotly(fig, out_dir, "price_severity_bubble")
        print(f"  [OK] Price-Severity Bubble Chart salvato in: {out_dir}")
        return fig

    @staticmethod
    def plot_rain_severity_hexbin(df: pd.DataFrame, save_dir: Optional[Path] = None) -> plt.Figure:
        """
        Hexbin plot (Matplotlib): anomalia pioggia vs severità IPC.
        Evidenzia la densità delle osservazioni nello spazio bivariato.
        """
        out_dir = _ensure_dir((save_dir or _get_save_dir()) / "multivariate")

        df_plot = df.dropna(subset=["Rain_avg_rfq", "phase_3plus_percentage"])
        if df_plot.empty:
            print("  [!] Dati insufficienti per hexbin rain vs severity.")
            return None

        fig, ax = plt.subplots(figsize=(10, 7), dpi=150)
        hb = ax.hexbin(
            df_plot["Rain_avg_rfq"], df_plot["phase_3plus_percentage"] * 100,
            gridsize=30, cmap="YlOrRd", mincnt=1,
        )
        cb = fig.colorbar(hb, ax=ax, label="N. Osservazioni", shrink=0.8)
        ax.set_xlabel("Anomalia Frequenza Pioggia (rfq) — CHIRPS")
        ax.set_ylabel("Severità IPC Fase 3+ (% Popolazione)")
        ax.set_title("Densità Bivariata: Deficit Idrico vs Insicurezza Alimentare",
                      fontweight="bold")
        ax.grid(True, alpha=0.2)

        _save_matplotlib(fig, out_dir, "rain_severity_hexbin")
        print(f"  [OK] Rain-Severity Hexbin salvato in: {out_dir}")
        return fig

    @staticmethod
    def plot_pairplot_by_country(df: pd.DataFrame, countries: List[str] = None,
                                 save_dir: Optional[Path] = None) -> plt.Figure:
        """
        Pair plot (Seaborn) delle variabili chiave, colorato per paese.
        Se countries=None, usa i top-6 per volume dati.
        """
        out_dir = _ensure_dir((save_dir or _get_save_dir()) / "multivariate")

        cols = ["phase_3plus_percentage", "WFP_avg_price", "WFP_avg_inflation",
                "Rain_avg_rfq"]
        cols = [c for c in cols if c in df.columns]

        if countries is None:
            top = df["Country"].value_counts().head(6).index.tolist()
            countries = top

        df_sub = df[df["Country"].isin(countries)].dropna(subset=cols)[cols + ["Country"]].copy()
        df_sub["phase_3plus_percentage"] = df_sub["phase_3plus_percentage"] * 100

        rename = {
            "phase_3plus_percentage": "IPC 3+ (%)",
            "WFP_avg_price": "Prezzo WFP",
            "WFP_avg_inflation": "Inflaz. WFP",
            "Rain_avg_rfq": "Pioggia rfq",
        }
        df_sub = df_sub.rename(columns=rename)

        g = sns.pairplot(
            df_sub, hue="Country", diag_kind="kde",
            plot_kws={"alpha": 0.5, "s": 18, "edgecolor": "none"},
            height=2.2, aspect=1.1,
        )
        g.figure.suptitle("Pair Plot Multivariato — Top 6 Paesi", y=1.02, fontweight="bold")

        _save_matplotlib(g.figure, out_dir, "pairplot_top_countries")
        print(f"  [OK] Pairplot salvato in: {out_dir}")
        return g.figure


# ─────────────────────────────────────────────────────────────────────────────
# 4. TEMPORAL ANALYTICS
# ─────────────────────────────────────────────────────────────────────────────

class TemporalAnalytics:
    """Grafici per analizzare le dinamiche temporali dei dati."""

    @staticmethod
    def plot_quarterly_heatmap(df: pd.DataFrame, save_dir: Optional[Path] = None) -> plt.Figure:
        """
        Heatmap (Seaborn): severità media Phase 3+ per paese × trimestre.
        Mostra l'evoluzione temporale della crisi in tutti i paesi simultaneamente.
        """
        out_dir = _ensure_dir((save_dir or _get_save_dir()) / "temporal")

        df_t = _prepare_df(df)
        if "quarter" not in df_t.columns:
            print("  [!] Colonna date non disponibile per quarterly heatmap.")
            return None

        pivot = (
            df_t.groupby(["Country", "quarter"])["phase_3plus_percentage"]
            .mean()
            .unstack(fill_value=np.nan)
        )
        # Moltiplica per 100
        pivot = pivot * 100

        # Ordina paesi per severità media decrescente
        pivot = pivot.loc[pivot.mean(axis=1).sort_values(ascending=False).index]

        fig, ax = plt.subplots(figsize=(max(len(pivot.columns) * 0.8, 10),
                                        max(len(pivot) * 0.4, 6)), dpi=150)
        sns.heatmap(
            pivot, cmap="YlOrRd", annot=False,
            linewidths=0.2, linecolor="white",
            cbar_kws={"label": "Severità IPC 3+ (%)", "shrink": 0.7},
            ax=ax,
        )
        ax.set_title("Evoluzione Trimestrale della Severità IPC per Paese", fontweight="bold", pad=15)
        ax.set_xlabel("Trimestre")
        ax.set_ylabel("")
        plt.xticks(rotation=45, ha="right", fontsize=8)
        plt.tight_layout()

        _save_matplotlib(fig, out_dir, "quarterly_severity_heatmap")
        print(f"  [OK] Quarterly Severity Heatmap salvato in: {out_dir}")
        return fig

    @staticmethod
    def plot_global_trend_ribbon(df: pd.DataFrame, save_dir: Optional[Path] = None) -> alt.Chart:
        """
        Area chart con ribbon (Altair): trend globale della severità IPC Phase 3+
        con bande di incertezza (percentili 25-75).
        """
        out_dir = _ensure_dir((save_dir or _get_save_dir()) / "temporal")

        df_t = _prepare_df(df)
        if "year_month" not in df_t.columns:
            return None

        agg = (
            df_t.dropna(subset=["phase_3plus_percentage"])
            .groupby("year_month")["phase_3plus_percentage"]
            .agg(["mean", "median", lambda x: x.quantile(0.25), lambda x: x.quantile(0.75)])
            .reset_index()
        )
        agg.columns = ["year_month", "mean", "median", "q25", "q75"]
        agg["mean_pct"] = agg["mean"] * 100
        agg["median_pct"] = agg["median"] * 100
        agg["q25_pct"] = agg["q25"] * 100
        agg["q75_pct"] = agg["q75"] * 100

        band = (
            alt.Chart(agg)
            .mark_area(opacity=0.25, color=PALETTE["danger"])
            .encode(
                x=alt.X("year_month:O", title="Mese", axis=alt.Axis(labelAngle=-45, labelFontSize=8)),
                y=alt.Y("q25_pct:Q"),
                y2=alt.Y2("q75_pct:Q"),
            )
        )

        line_mean = (
            alt.Chart(agg)
            .mark_line(strokeWidth=2.5, color=PALETTE["danger"])
            .encode(
                x="year_month:O",
                y=alt.Y("mean_pct:Q", title="Severità IPC 3+ (%)"),
                tooltip=[
                    alt.Tooltip("year_month:O", title="Mese"),
                    alt.Tooltip("mean_pct:Q", format=".1f", title="Media (%)"),
                    alt.Tooltip("q25_pct:Q", format=".1f", title="P25 (%)"),
                    alt.Tooltip("q75_pct:Q", format=".1f", title="P75 (%)"),
                ],
            )
        )

        line_median = (
            alt.Chart(agg)
            .mark_line(strokeWidth=1.5, strokeDash=[4, 2], color=PALETTE["primary"])
            .encode(x="year_month:O", y="median_pct:Q")
        )

        chart = (
            (band + line_mean + line_median)
            .properties(
                width=750, height=350,
                title=alt.TitleParams(
                    text="Trend Globale della Severità IPC Fase 3+",
                    subtitle="Linea rossa = media | Linea blu tratteggiata = mediana | Banda = intervallo interquartile",
                    fontSize=15, subtitleFontSize=11, subtitleColor="gray",
                ),
            )
            .configure_axis(grid=True, gridOpacity=0.12)
            .configure_view(strokeWidth=0)
        )

        _save_altair(chart, out_dir, "global_trend_ribbon")
        print(f"  [OK] Global Trend Ribbon salvato in: {out_dir}")
        return chart

    @staticmethod
    def plot_country_sparklines(df: pd.DataFrame, top_n: int = 15,
                                 save_dir: Optional[Path] = None) -> plt.Figure:
        """
        Sparkline grid (Matplotlib): piccoli grafici della severità nel tempo
        per i top-N paesi. Stile dashboard compatto.
        """
        out_dir = _ensure_dir((save_dir or _get_save_dir()) / "temporal")

        df_t = _prepare_df(df)
        if "date_from" not in df_t.columns:
            return None

        # Seleziona i top-N paesi per volume dati
        top_countries = df_t["Country"].value_counts().head(top_n).index.tolist()

        ncols = 3
        nrows = (top_n + ncols - 1) // ncols
        fig, axes = plt.subplots(nrows, ncols, figsize=(14, nrows * 2.3), dpi=150,
                                  sharex=False, sharey=True)
        axes = axes.flatten()

        for i, country in enumerate(top_countries):
            ax = axes[i]
            sub = (
                df_t[df_t["Country"] == country]
                .dropna(subset=["date_from", "phase_3plus_percentage"])
                .groupby("date_from")["phase_3plus_percentage"]
                .mean()
                .sort_index()
            )
            if sub.empty:
                ax.set_visible(False)
                continue

            ax.fill_between(sub.index, sub.values * 100, alpha=0.3, color=PALETTE["danger"])
            ax.plot(sub.index, sub.values * 100, color=PALETTE["danger"], linewidth=1.5)
            ax.set_title(country, fontsize=11, fontweight="bold", pad=3)
            ax.set_ylim(0, None)
            ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))
            ax.tick_params(axis="x", labelsize=7, rotation=30)
            ax.tick_params(axis="y", labelsize=8)
            ax.grid(True, alpha=0.15)

        # Nascondi assi inutilizzati
        for j in range(len(top_countries), len(axes)):
            axes[j].set_visible(False)

        fig.suptitle("Sparklines Severità IPC Fase 3+ — Top Paesi",
                     fontweight="bold", fontsize=14, y=1.01)
        plt.tight_layout()

        _save_matplotlib(fig, out_dir, "country_sparklines")
        print(f"  [OK] Country Sparklines salvato in: {out_dir}")
        return fig


# ─────────────────────────────────────────────────────────────────────────────
# 5. GEOGRAPHIC / REGIONAL PLOTS
# ─────────────────────────────────────────────────────────────────────────────

class GeographicPlots:
    """Grafici geografici e confronti regionali."""

    @staticmethod
    def plot_severity_world_map(df: pd.DataFrame, save_dir: Optional[Path] = None):
        """
        Choropleth mondiale (Plotly): severità IPC media per paese.
        """
        out_dir = _ensure_dir((save_dir or _get_save_dir()) / "geographical")

        agg = df.groupby("Country").agg(
            severity=("phase_3plus_percentage", "mean"),
            population=("Total country population", "max"),
        ).reset_index()
        agg["severity_pct"] = agg["severity"] * 100

        fig = px.choropleth(
            agg, locations="Country", locationmode="ISO-3",
            color="severity_pct",
            hover_name="Country",
            hover_data={"severity_pct": ":.1f", "population": ":,.0f"},
            color_continuous_scale="OrRd",
            labels={
                "severity_pct": "Severità IPC 3+ (%)",
                "population": "Popolazione",
            },
            title="Mappa Mondiale della Severità dell'Insicurezza Alimentare (IPC Fase 3+)",
        )
        fig.update_layout(
            template="plotly_white",
            title_font_size=16,
            geo=dict(
                showframe=False, showcoastlines=True, coastlinecolor="#bdc3c7",
                projection_type="natural earth",
                bgcolor="white",
            ),
            height=550, margin=dict(l=0, r=0, t=50, b=0),
        )

        _save_plotly(fig, out_dir, "severity_world_map")
        print(f"  [OK] Severity World Map salvato in: {out_dir}")
        return fig

    @staticmethod
    def plot_regional_boxplots(df: pd.DataFrame, save_dir: Optional[Path] = None) -> plt.Figure:
        """
        Box plot (Seaborn): distribuzione della severità IPC Phase 3+ per paese,
        ordinato dalla mediana più alta alla più bassa.
        """
        out_dir = _ensure_dir((save_dir or _get_save_dir()) / "geographical")

        df_plot = df.dropna(subset=["phase_3plus_percentage"]).copy()
        df_plot["severity_pct"] = df_plot["phase_3plus_percentage"] * 100

        # Ordina per mediana decrescente
        order = (
            df_plot.groupby("Country")["severity_pct"]
            .median()
            .sort_values(ascending=False)
            .index.tolist()
        )

        fig, ax = plt.subplots(figsize=(14, max(len(order) * 0.38, 6)), dpi=150)
        sns.boxplot(
            data=df_plot, y="Country", x="severity_pct",
            order=order, palette="YlOrRd", linewidth=0.7,
            fliersize=2, flierprops={"alpha": 0.4}, ax=ax,
        )
        ax.set_xlabel("Severità IPC Fase 3+ (% Popolazione)")
        ax.set_ylabel("")
        ax.set_title("Distribuzione della Severità IPC per Paese", fontweight="bold", pad=10)
        ax.grid(True, axis="x", alpha=0.2)
        ax.axvline(x=df_plot["severity_pct"].median(), color=PALETTE["danger"],
                    linestyle="--", linewidth=1, alpha=0.6, label="Mediana Globale")
        ax.legend(loc="lower right", fontsize=9)
        plt.tight_layout()

        _save_matplotlib(fig, out_dir, "regional_boxplots")
        print(f"  [OK] Regional Boxplots salvato in: {out_dir}")
        return fig

    @staticmethod
    def plot_price_map(df: pd.DataFrame, save_dir: Optional[Path] = None):
        """
        Choropleth mondiale (Plotly): prezzo medio WFP per paese.
        """
        out_dir = _ensure_dir((save_dir or _get_save_dir()) / "geographical")

        agg = df.groupby("Country").agg(
            avg_price=("WFP_avg_price", "mean"),
            avg_inflation=("WFP_avg_inflation", "mean"),
        ).dropna().reset_index()

        fig = px.choropleth(
            agg, locations="Country", locationmode="ISO-3",
            color="avg_price",
            hover_name="Country",
            hover_data={"avg_price": ":.2f", "avg_inflation": ":.2f"},
            color_continuous_scale="Viridis",
            labels={
                "avg_price": "Prezzo Medio WFP",
                "avg_inflation": "Inflazione Media WFP",
            },
            title="Mappa Mondiale del Prezzo Alimentare Medio (WFP)",
        )
        fig.update_layout(
            template="plotly_white", title_font_size=16,
            geo=dict(showframe=False, showcoastlines=True, coastlinecolor="#bdc3c7",
                     projection_type="natural earth", bgcolor="white"),
            height=550, margin=dict(l=0, r=0, t=50, b=0),
        )

        _save_plotly(fig, out_dir, "price_world_map")
        print(f"  [OK] Price World Map salvato in: {out_dir}")
        return fig


# ─────────────────────────────────────────────────────────────────────────────
# RUNNER — GENERAZIONE COMPLETA
# ─────────────────────────────────────────────────────────────────────────────

def generate_advanced_plots(df: pd.DataFrame = None, save_dir: Optional[Path] = None):
    """
    Genera ed esporta l'intera suite di grafici avanzati.
    Se df=None, carica automaticamente il dataset riconciliato.
    """
    if df is None:
        from plotter import load_reconciled_data
        df = load_reconciled_data()

    if save_dir is None:
        save_dir = _get_save_dir()
    save_dir = Path(save_dir)

    print("=" * 60)
    print("GENERAZIONE SUITE AVANZATA DI GRAFICI (advanced_plots.py)")
    print("=" * 60)

    # 1. Severity Analytics
    print("\n[1/5] Severity Analytics")
    SeverityAnalytics.plot_phase_distribution_stacked(df, save_dir)
    SeverityAnalytics.plot_severity_ranking(df, save_dir)
    SeverityAnalytics.plot_top_crisis_areas(df, top_n=30, save_dir=save_dir)

    # 2. Data Quality Dashboard
    print("\n[2/5] Data Quality Dashboard")
    DataQualityDashboard.plot_null_heatmap(df, save_dir)
    DataQualityDashboard.plot_observation_density(df, save_dir)
    DataQualityDashboard.plot_match_level_sankey(df, save_dir)

    # 3. Multivariate Plots
    print("\n[3/5] Multivariate Analysis")
    MultivariatePlots.plot_price_severity_bubble(df, save_dir)
    MultivariatePlots.plot_rain_severity_hexbin(df, save_dir)
    MultivariatePlots.plot_pairplot_by_country(df, save_dir=save_dir)

    # 4. Temporal Analytics
    print("\n[4/5] Temporal Analytics")
    TemporalAnalytics.plot_quarterly_heatmap(df, save_dir)
    TemporalAnalytics.plot_global_trend_ribbon(df, save_dir)
    TemporalAnalytics.plot_country_sparklines(df, top_n=15, save_dir=save_dir)

    # 5. Geographic Plots
    print("\n[5/5] Geographic Plots")
    GeographicPlots.plot_severity_world_map(df, save_dir)
    GeographicPlots.plot_regional_boxplots(df, save_dir)
    GeographicPlots.plot_price_map(df, save_dir)

    print("\n" + "=" * 60)
    print("SUITE COMPLETA GENERATA CON SUCCESSO!")
    print(f"   Grafici salvati in: {save_dir}")
    print("=" * 60)


if __name__ == "__main__":
    generate_advanced_plots()
