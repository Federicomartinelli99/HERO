"""
hero_v2.domains.ipc.plots
=========================
Visualizzazioni grafiche Altair per i dati del dominio IPC.
"""

import altair as alt
import pandas as pd
from hero_v2.core.base_plotter import BasePlotter
from hero_v2.core.logger import get_logger

logger = get_logger(__name__)

class IpcPlotter(BasePlotter):
    """Plotter per le visualizzazioni relative alle analisi IPC."""

    def plot_phase_trend(self, df_ipc: pd.DataFrame, country_name: str, validity_period: str = "current") -> alt.Chart:
        """
        Grafico ad area o barre impilate delle percentuali di popolazione nelle diverse fasi IPC nel tempo.
        """
        if df_ipc.empty:
            return alt.Chart()

        # Filtriamo per tipo di stima
        df = df_ipc[df_ipc["Validity period"].str.lower() == validity_period.lower()].copy()
        if df.empty:
            logger.warning("Nessun dato corrispondente al validity_period richiesto.")
            return alt.Chart()

        # Aggreghiamo a livello nazionale per data e fase
        df_agg = df.groupby(["date", "Phase"])["Number"].sum().reset_index()
        df_agg["date"] = pd.to_datetime(df_agg["date"])
        
        # Mappatura dei colori classici IPC
        ipc_colors = {
            "1": "#cddc39",  # Minimal / Fase 1
            "2": "#ffeb3b",  # Stressed / Fase 2
            "3": "#ff9800",  # Crisis / Fase 3
            "4": "#e51c23",  # Emergency / Fase 4
            "5": "#b71c1c",  # Famine / Fase 5
            "3+": "#ff5722"  # Crisis or worse
        }

        phases = sorted(list(df_agg["Phase"].unique()))
        colors = [ipc_colors.get(p, "#9e9e9e") for p in phases]

        chart = (
            alt.Chart(df_agg)
            .mark_bar()
            .encode(
                x=alt.X("date:T", title=None, axis=alt.Axis(format="%Y-%b", labelAngle=-30)),
                y=alt.Y("Number:Q", title="Popolazione coinvolta", stack="normalize", axis=alt.Axis(format=".0%")),
                color=alt.Color("Phase:N", title="Fase IPC", scale=alt.Scale(domain=phases, range=colors)),
                tooltip=[
                    alt.Tooltip("date:T", title="Analisi", format="%B %Y"),
                    alt.Tooltip("Phase:N", title="Fase"),
                    alt.Tooltip("Number:Q", title="Popolazione", format=",.0f"),
                ],
            )
            .properties(
                title=alt.TitleParams(
                    f"Evoluzione fasi di insicurezza alimentare (IPC) — {country_name}",
                    subtitle=f"Stime di tipo: {validity_period.title()}",
                    anchor="start",
                ),
                width=750,
                height=350,
            )
        )

        return BasePlotter.configure_altair_theme(chart)
