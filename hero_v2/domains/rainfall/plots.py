"""
hero_v2.domains.rainfall.plots
=============================
Visualizzazioni grafiche Altair per i dati sulle precipitazioni (Rainfall).
"""

import altair as alt
import pandas as pd
from hero_v2.core.base_plotter import BasePlotter
from hero_v2.core.logger import get_logger

logger = get_logger(__name__)

class RainfallPlotter(BasePlotter):
    """Plotter per le visualizzazioni del dominio delle precipitazioni."""

    def plot_seasonal_climatology(self, df_rainfall: pd.DataFrame, country_name: str) -> alt.Chart:
        """
        Grafico del ciclo stagionale storico delle precipitazioni.
        Mostra le piogge storiche medie mensili (climatologia).
        """
        if df_rainfall.empty or "r1h" not in df_rainfall.columns:
            return alt.Chart()

        df = df_rainfall.copy()
        df["month"] = df["date"].dt.month
        df["month_name"] = df["date"].dt.strftime("%b")
        
        # Aggreghiamo climatologia storica
        df_cycle = df.groupby(["month", "month_name"])["r1h_avg"].mean().reset_index()
        df_cycle = df_cycle.sort_values(by="month")

        chart = (
            alt.Chart(df_cycle)
            .mark_line(point=True, color=BasePlotter.HERO_COLORS["primary"], strokeWidth=2)
            .encode(
                x=alt.X("month_name:N", title=None, sort=alt.EncodingSortField(field="month", order="ascending")),
                y=alt.Y("r1h_avg:Q", title="Precipitazioni medie mensili (mm)", scale=alt.Scale(zero=True)),
                tooltip=[
                    alt.Tooltip("month_name:N", title="Mese"),
                    alt.Tooltip("r1h_avg:Q", title="Media storica (mm)", format=".1f"),
                ],
            )
            .properties(
                title=alt.TitleParams(
                    f"Climatologia stagionale delle precipitazioni — {country_name}",
                    subtitle="Precipitazioni mensili storiche (CHIRPS)",
                    anchor="start",
                ),
                width=750,
                height=350,
            )
        )

        return BasePlotter.configure_altair_theme(chart)

    def plot_anomaly_timeline(self, df_rainfall: pd.DataFrame, country_name: str, metric: str = "rfq") -> alt.Chart:
        """
        Cronologia delle anomalie delle precipitazioni (es. rfq o r1q).
        Barre verticali dove il colore indica siccita' (rosso/arancio) o piogge sopra la media (blu).
        """
        if df_rainfall.empty or metric not in df_rainfall.columns:
            return alt.Chart()

        df = df_rainfall.copy()
        df["date"] = pd.to_datetime(df["date"])
        
        # Aggreghiamo a livello nazionale per data
        df_nat = df.groupby("date")[metric].mean().reset_index()
        
        # Sottraiamo 100 per centrare l'indice rfq / r1q intorno allo 0 (solitamente indicano % della norma)
        # Se > 100, pioggia sopra la media. Se < 100, siccita'.
        df_nat["anomaly"] = df_nat[metric] - 100
        df_nat["status"] = df_nat["anomaly"].apply(lambda x: "Sopra la media" if x >= 0 else "Sotto la media")

        chart = (
            alt.Chart(df_nat)
            .mark_bar()
            .encode(
                x=alt.X("date:T", title=None, axis=alt.Axis(format="%Y", tickCount=10)),
                y=alt.Y("anomaly:Q", title="Deviazione dalla norma (%)"),
                color=alt.Color(
                    "status:N",
                    title="Condizione",
                    scale=alt.Scale(
                        domain=["Sopra la media", "Sotto la media"],
                        range=[BasePlotter.HERO_COLORS["up_trend"], BasePlotter.HERO_COLORS["danger"]]
                    )
                ),
                tooltip=[
                    alt.Tooltip("date:T", title="Data", format="%B %Y"),
                    alt.Tooltip(metric, title="Indice", format=".1f"),
                    alt.Tooltip("anomaly:Q", title="Deviazione (%)", format="+.1f"),
                ],
            )
            .properties(
                title=alt.TitleParams(
                    f"Cronologia anomalie precipitazioni ({metric.upper()}) — {country_name}",
                    subtitle="Valori positivi = piu' umido della norma · Valori negativi = piu' secco (deficit)",
                    anchor="start",
                ),
                width=750,
                height=350,
            )
        )

        return BasePlotter.configure_altair_theme(chart)
