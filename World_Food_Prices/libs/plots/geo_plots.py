"""
libs/plots/geo_plots.py

Backend geospaziale H.E.R.O.
Implementazione Plotly aggiornata con fix per 'size' negativo.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from typing import Optional
from libs.logger_config import get_logger

logger = get_logger(__name__)

_MAP_STYLE = "carto-positron"

def _safe_bubble_size(series: pd.Series, min_size: float = 6.0, max_size: float = 28.0) -> pd.Series:
    """
    Trasforma una serie arbitraria (anche negativa) in dimensioni 
    marker rigorosamente positive per Plotly.
    """
    x = series.abs()
    xmin = x.min()
    xmax = x.max()

    if pd.isna(xmin) or xmin == xmax:
        return pd.Series(np.repeat((min_size + max_size) / 2, len(series)), index=series.index)

    return min_size + (x - xmin) / (xmax - xmin) * (max_size - min_size)

def _robust_quantiles(series: pd.Series):
    """Calcola gli estremi robusti per la palette colori ignorando gli outlier estremi."""
    q1 = float(series.quantile(0.05))
    q2 = float(series.quantile(0.95))
    if q1 == q2:
        q1 = float(series.min())
        q2 = float(series.max())
    return q1, q2

class WFPGeoPlotter:
    def __init__(self, world_topology=None):
        self.world_topology = world_topology

    def _prepare(self, df: pd.DataFrame, criterion: str, required: set) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame()
        missing = required - set(df.columns)
        if missing:
            logger.warning(f"Colonne mancanti: {missing}")
            return pd.DataFrame()
        df = df.copy()
        for c in ["lat", "lon", criterion]:
            if c in df:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        return df.dropna(subset=list(required))

    # HEATMAP MERCATI
    def plot_market_heatmap(self, df_markets: pd.DataFrame, criterion: str, title: str) -> go.Figure:
        req = {"lat", "lon", criterion}
        df = self._prepare(df_markets, criterion, req)
        if df.empty:
            return go.Figure()

        q1, q2 = _robust_quantiles(df[criterion])
        
        # FIX PRINCIPALE: calcoliamo una colonna sicura e la passiamo a Plotly
        df["_bubble_size"] = _safe_bubble_size(df[criterion])

        fig = px.scatter_map(
            df,
            lat="lat",
            lon="lon",
            size="_bubble_size",  # <-- FIX APPLICATO QUI
            color=criterion,
            hover_name="mkt_name",
            hover_data={
                "_bubble_size": False, # Nasconde la colonna fittizia dal tooltip
                "country": True,
                "adm1_name": True,
                criterion: ":.2f"
            },
            zoom=2,
            size_max=25,
            color_continuous_scale="Turbo",
            range_color=[q1, q2]
        )

        fig.update_layout(
            map_style=_MAP_STYLE,
            height=550,
            title=title,
            margin=dict(l=0, r=0, t=60, b=0)
        )
        return fig

    # COROPLETA
    def plot_country_choropleth(self, df_aggregated: pd.DataFrame, criterion: str, title: str, diverging: bool = False) -> go.Figure:
        if df_aggregated.empty:
            return go.Figure()

        scale = "RdBu" if diverging else "OrRd"
        color_mid = 0 if diverging else None

        fig = px.choropleth(
            df_aggregated,
            locations="ISO3",
            color=criterion,
            color_continuous_scale=scale,
            color_continuous_midpoint=color_mid,
            locationmode="ISO-3",
            hover_name="ISO3"
        )
        fig.update_geos(showcountries=True, showframe=False)
        fig.update_layout(height=550, title=title, margin=dict(l=0, r=0, t=60, b=0))
        return fig

    # MAPPA + RANK REGIONI
    def plot_regional_strip_map(self, df_markets: pd.DataFrame, criterion: str, country_name: str, max_regions: int = 15):
        req = {"lat", "lon", "adm1_name", criterion}
        df = self._prepare(df_markets, criterion, req)
        if df.empty:
            return go.Figure()

        df["_bubble_size"] = _safe_bubble_size(df[criterion])
        
        # Aggregazione ordinata per il Bar Chart
        reg = df.groupby("adm1_name", as_index=False)[criterion].mean()
        reg = reg.sort_values(by=criterion, ascending=False).head(max_regions)
        reg = reg.sort_values(by=criterion, ascending=True)

        fig = make_subplots(
            rows=1, cols=2,
            column_widths=[0.65, 0.35],
            specs=[[{"type": "map"}, {"type": "xy"}]],
            horizontal_spacing=0.02
        )

        q1, q2 = _robust_quantiles(df[criterion])

        # 1. Traccia Mappa
        scatter = px.scatter_map(
            df,
            lat="lat",
            lon="lon",
            color=criterion,
            size="_bubble_size",
            hover_name="mkt_name",
            hover_data={"_bubble_size": False, criterion: ":.2f"}
        )
        
        for tr in scatter.data:
            # Forza l'uso dello stesso colorasse globale in Plotly per evitare divergenze
            tr.marker.coloraxis = "coloraxis"
            fig.add_trace(tr, row=1, col=1)

        # 2. Traccia Bar Chart
        bar = go.Bar(
            x=reg[criterion],
            y=reg["adm1_name"],
            orientation="h",
            marker=dict(
                color=reg[criterion], 
                coloraxis="coloraxis" # SINCRONIZZAZIONE PERFETTA COLORI CON LA MAPPA
            ),
            text=reg[criterion].apply(lambda x: f"{x:.2f}"),
            textposition="auto",
            hovertemplate="<b>%{y}</b><br>Media: %{x:.2f}<extra></extra>"
        )
        fig.add_trace(bar, row=1, col=2)

        # 3. Configurazione
        fig.update_layout(
            map=dict(
                style=_MAP_STYLE,
                center=dict(lat=df["lat"].mean(), lon=df["lon"].mean()),
                zoom=4.5
            )
        )

        # Layout unificato (Unico coloraxis per bar e map)
        fig.update_layout(
            title=f"Distribuzione Regionale: {country_name} - {criterion.replace('_', ' ').title()}",
            height=600,
            showlegend=False,
            coloraxis=dict(
                colorscale="Turbo", 
                cmin=q1, 
                cmax=q2, 
                showscale=True, 
                colorbar=dict(title="Valore")
            ),
            margin=dict(l=10, r=10, t=60, b=20)
        )
        
        return fig

    # ANIMAZIONE
    def plot_market_time_animation(self, df_markets: pd.DataFrame, criterion: str, country_name: str, animate_by: str = "month") -> go.Figure:
        req = {"lat", "lon", criterion, animate_by}
        df = self._prepare(df_markets, criterion, req)
        if df.empty:
            return go.Figure()

        df = df.sort_values(by=animate_by)
        df[animate_by] = df[animate_by].astype(str)

        # FIX APPLICATO ANCHE QUI
        df["_bubble_size"] = _safe_bubble_size(df[criterion])
        q1, q2 = _robust_quantiles(df[criterion])

        fig = px.scatter_map(
            df,
            lat="lat",
            lon="lon",
            color=criterion,
            size="_bubble_size", # <-- FIX
            animation_frame=animate_by,
            hover_name="mkt_name",
            hover_data={"_bubble_size": False, criterion: ":.2f"},
            zoom=4,
            size_max=25,
            color_continuous_scale="Turbo",
            range_color=[q1, q2]
        )

        fig.update_layout(
            map_style=_MAP_STYLE,
            title=f"Evoluzione {country_name}",
            height=600,
            margin=dict(l=0, r=0, t=60, b=0)
        )
        return fig
