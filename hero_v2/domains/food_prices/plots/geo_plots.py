"""
hero_v2.domains.food_prices.plots.geo_plots
===========================================
Visualizzazioni geospaziali Plotly per il dominio Food Prices.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Optional
from hero_v2.core.base_plotter import BasePlotter
from hero_v2.core.logger import get_logger

logger = get_logger(__name__)

_MAP_STYLE = "carto-positron"

class FoodGeoPlotter:
    def __init__(self, world_topology=None) -> None:
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

    def plot_market_heatmap(self, df_markets: pd.DataFrame, criterion: str, title: str) -> go.Figure:
        """Mappa scatter/bubble per i mercati fisici."""
        req = {"lat", "lon", criterion}
        df = self._prepare(df_markets, criterion, req)
        if df.empty:
            return go.Figure()

        q1, q2 = BasePlotter.robust_quantiles(df[criterion])
        df["_bubble_size"] = BasePlotter.safe_bubble_size(df[criterion])

        fig = px.scatter_map(
            df,
            lat="lat",
            lon="lon",
            size="_bubble_size",
            color=criterion,
            hover_name="mkt_name",
            hover_data={
                "_bubble_size": False,
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

    def plot_country_choropleth(self, df_aggregated: pd.DataFrame, criterion: str, title: str, diverging: bool = False) -> go.Figure:
        """Mappa coropleta a livello paese."""
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

    def plot_regional_strip_map(self, df_markets: pd.DataFrame, criterion: str, country_name: str, max_regions: int = 15) -> go.Figure:
        """Mappa + Bar chart affiancato per regioni adm1."""
        req = {"lat", "lon", "adm1_name", criterion}
        df = self._prepare(df_markets, criterion, req)
        if df.empty:
            return go.Figure()

        df["_bubble_size"] = BasePlotter.safe_bubble_size(df[criterion])
        
        reg = df.groupby("adm1_name", as_index=False)[criterion].mean()
        reg = reg.sort_values(by=criterion, ascending=False).head(max_regions)
        reg = reg.sort_values(by=criterion, ascending=True)

        fig = make_subplots(
            rows=1, cols=2,
            column_widths=[0.65, 0.35],
            specs=[[{"type": "map"}, {"type": "xy"}]],
            horizontal_spacing=0.02
        )

        q1, q2 = BasePlotter.robust_quantiles(df[criterion])

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
            tr.marker.coloraxis = "coloraxis"
            fig.add_trace(tr, row=1, col=1)

        # 2. Traccia Bar Chart
        bar = go.Bar(
            x=reg[criterion],
            y=reg["adm1_name"],
            orientation="h",
            marker=dict(
                color=reg[criterion], 
                coloraxis="coloraxis"
            ),
            text=reg[criterion].apply(lambda x: f"{x:.2f}"),
            textposition="auto",
            hovertemplate="<b>%{y}</b><br>Media: %{x:.2f}<extra></extra>"
        )
        fig.add_trace(bar, row=1, col=2)

        fig.update_layout(
            map=dict(
                style=_MAP_STYLE,
                center=dict(lat=df["lat"].mean(), lon=df["lon"].mean()),
                zoom=4.5
            )
        )

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

    def plot_market_time_animation(self, df_markets: pd.DataFrame, criterion: str, country_name: str, animate_by: str = "month") -> go.Figure:
        """Animazione temporale dei mercati sulla mappa."""
        req = {"lat", "lon", criterion, animate_by}
        df = self._prepare(df_markets, criterion, req)
        if df.empty:
            return go.Figure()

        df = df.sort_values(by=animate_by)
        df[animate_by] = df[animate_by].astype(str)

        df["_bubble_size"] = BasePlotter.safe_bubble_size(df[criterion])
        q1, q2 = BasePlotter.robust_quantiles(df[criterion])

        fig = px.scatter_map(
            df,
            lat="lat",
            lon="lon",
            color=criterion,
            size="_bubble_size",
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
