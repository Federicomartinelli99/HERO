"""
hero_v2.domains.food_prices.plots.time_series_plots
===================================================
Visualizzazioni delle serie temporali Altair per il dominio Food Prices.
"""

import altair as alt
import pandas as pd
from typing import List, Optional
from hero_v2.core.base_plotter import BasePlotter
from hero_v2.core.logger import get_logger

logger = get_logger(__name__)

class FoodTimeSeriesPlotter:
    """Raccoglie i grafici a serie temporale per i prezzi alimentari."""

    def plot_inflation_trend(self, df_panel: pd.DataFrame, show_confidence_band: bool = True) -> alt.Chart:
        """Trend temporale dell'inflazione alimentare per piu' paesi."""
        if df_panel.empty:
            return alt.Chart()

        df = df_panel.copy()
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")
        df["mom_change"] = df.groupby("country")["inflation_food_price_index"].diff().round(2)

        selection = alt.selection_point(fields=["country"], bind="legend")

        base = alt.Chart(df).encode(
            x=alt.X("date:T", title=None, axis=alt.Axis(format="%b %Y", labelAngle=-30, tickCount=12)),
            color=alt.Color("country:N", scale=alt.Scale(scheme="tableau10"), legend=alt.Legend(title="Paese", orient="right")),
        )

        lines = base.mark_line(strokeWidth=2).encode(
            y=alt.Y("inflation_food_price_index:Q", title="Inflazione alimentare (%)", scale=alt.Scale(zero=False)),
            opacity=alt.condition(selection, alt.value(1), alt.value(0.12)),
            tooltip=[
                alt.Tooltip("country:N", title="Paese"),
                alt.Tooltip("date:T", title="Data", format="%B %Y"),
                alt.Tooltip("inflation_food_price_index:Q", title="Inflaz.", format=".2f"),
                alt.Tooltip("mom_change:Q", title="Δ vs mese prec.", format="+.2f"),
            ],
        )

        points = base.mark_circle(size=35, opacity=0).encode(
            y="inflation_food_price_index:Q",
            opacity=alt.condition(selection, alt.value(0.8), alt.value(0)),
        )

        chart_layers: List[alt.Chart] = []

        if show_confidence_band and "adm1_name" in df_panel.columns:
            df_band = (
                df_panel.groupby(["country", "date"])["inflation_food_price_index"]
                .agg(mean="mean", std="std")
                .reset_index()
            )
            df_band["upper"] = df_band["mean"] + df_band["std"].fillna(0)
            df_band["lower"] = df_band["mean"] - df_band["std"].fillna(0)
            df_band["date"] = pd.to_datetime(df_band["date"])

            band = (
                alt.Chart(df_band)
                .mark_area(opacity=0.10)
                .encode(
                    x="date:T",
                    y=alt.Y("lower:Q", scale=alt.Scale(zero=False)),
                    y2="upper:Q",
                    color=alt.Color("country:N", scale=alt.Scale(scheme="tableau10")),
                    opacity=alt.condition(selection, alt.value(0.15), alt.value(0.02)),
                )
            )
            chart_layers.append(band)

        zero_rule = (
            alt.Chart(pd.DataFrame({"y": [0]}))
            .mark_rule(strokeDash=[4, 4], color=BasePlotter.HERO_COLORS["neutral_mid"], strokeWidth=0.8)
            .encode(y="y:Q")
        )

        chart_layers += [zero_rule, lines, points]

        chart = alt.layer(*chart_layers).properties(
            title=alt.TitleParams(
                "Trend inflazione alimentare — confronto paesi",
                subtitle="Banda = ±1 std tra mercati dello stesso paese/mese",
                anchor="start",
            ),
            width=800,
            height=380,
        )

        return BasePlotter.configure_altair_theme(chart)

    def plot_commodity_candle_monthly(self, df_country: pd.DataFrame, commodity: str, country_name: str) -> alt.Chart:
        """Grafico a candele giapponesi mensile per una commodity."""
        cols_needed = [f"o_{commodity}", f"h_{commodity}", f"l_{commodity}", f"c_{commodity}", "date"]
        missing = [c for c in cols_needed if c not in df_country.columns]
        if missing or df_country.empty:
            logger.warning(f"Candlestick: colonne mancanti {missing} per {commodity}.")
            return alt.Chart()

        df = df_country[cols_needed + [commodity]].dropna(subset=cols_needed).copy()
        df["date"] = pd.to_datetime(df["date"])
        df = df.groupby("date", as_index=False).mean(numeric_only=True)
        df["direction"] = (df[f"c_{commodity}"] >= df[f"o_{commodity}"]).map({True: "rialzo", False: "ribasso"})

        color_scale = alt.Scale(
            domain=["rialzo", "ribasso"],
            range=[BasePlotter.HERO_COLORS["up_trend"], BasePlotter.HERO_COLORS["down_trend"]],
        )

        base = alt.Chart(df).encode(
            x=alt.X("date:T", title=None, axis=alt.Axis(format="%b %Y", labelAngle=-30)),
            color=alt.Color("direction:N", scale=color_scale, legend=alt.Legend(title="Direzione")),
            tooltip=[
                alt.Tooltip("date:T", title="Mese", format="%B %Y"),
                alt.Tooltip(f"o_{commodity}:Q", title="Open", format=".3f"),
                alt.Tooltip(f"h_{commodity}:Q", title="High", format=".3f"),
                alt.Tooltip(f"l_{commodity}:Q", title="Low", format=".3f"),
                alt.Tooltip(f"c_{commodity}:Q", title="Close", format=".3f"),
                alt.Tooltip(f"{commodity}:Q", title="Media", format=".3f"),
            ],
        )

        stems = base.mark_rule(strokeWidth=1).encode(
            y=alt.Y(f"l_{commodity}:Q", title=f"Prezzo {commodity} (valuta locale)", scale=alt.Scale(zero=False)),
            y2=f"h_{commodity}:Q",
        )

        bodies = base.mark_bar(width=8).encode(
            y=alt.Y(f"o_{commodity}:Q", scale=alt.Scale(zero=False)),
            y2=f"c_{commodity}:Q",
        )

        df["ma3"] = df[commodity].rolling(3, min_periods=1).mean()
        ma_line = (
            alt.Chart(df)
            .mark_line(color="#6366f1", strokeWidth=1.5, strokeDash=[4, 2])
            .encode(
                x="date:T",
                y=alt.Y("ma3:Q", scale=alt.Scale(zero=False)),
                tooltip=[alt.Tooltip("ma3:Q", title="MA-3", format=".3f")],
            )
        )

        chart = alt.layer(stems, bodies, ma_line).properties(
            title=alt.TitleParams(
                f"OHLC mensile — {commodity.upper()} · {country_name}",
                subtitle="Linea tratteggiata = media mobile 3 mesi",
                anchor="start",
            ),
            width=800,
            height=380,
        )

        return BasePlotter.configure_altair_theme(chart)

    def plot_shock_heatmap(self, df_panel: pd.DataFrame, country_name: str) -> alt.Chart:
        """Heatmap Anno x Mese per shock di inflazione."""
        if df_panel.empty or "inflation_food_price_index" not in df_panel.columns:
            return alt.Chart()

        df = df_panel.copy()
        df["date"] = pd.to_datetime(df["date"])
        df["year"] = df["date"].dt.year
        df["month"] = df["date"].dt.month

        df_agg = (
            df.groupby(["year", "month"])["inflation_food_price_index"]
            .mean()
            .reset_index()
            .rename(columns={"inflation_food_price_index": "inflaz_media"})
        )
        df_agg["mese_label"] = df_agg["month"].map({
            1: "Gen", 2: "Feb", 3: "Mar", 4: "Apr", 5: "Mag", 6: "Giu",
            7: "Lug", 8: "Ago", 9: "Set", 10: "Ott", 11: "Nov", 12: "Dic",
        })

        vmax = df_agg["inflaz_media"].abs().quantile(0.97)
        domain = [-vmax, vmax]

        heatmap = (
            alt.Chart(df_agg)
            .mark_rect(stroke="#ffffff", strokeWidth=0.5)
            .encode(
                x=alt.X("month:O", title=None, sort=list(range(1, 13)),
                        axis=alt.Axis(labelExpr="['Gen','Feb','Mar','Apr','Mag','Giu','Lug','Ago','Set','Ott','Nov','Dic'][datum.value-1]")),
                y=alt.Y("year:O", title=None, sort="descending"),
                color=alt.Color("inflaz_media:Q", title="Inflaz. (%)",
                                scale=alt.Scale(scheme="redblue", domain=domain, reverse=True)),
                tooltip=[
                    alt.Tooltip("year:O", title="Anno"),
                    alt.Tooltip("mese_label:N", title="Mese"),
                    alt.Tooltip("inflaz_media:Q", title="Inflaz.", format=".2f"),
                ],
            )
            .properties(
                title=alt.TitleParams(
                    f"Calendario shock inflazione — {country_name}",
                    subtitle="Rosso = alta inflazione · Blu = deflazione",
                    anchor="start",
                ),
                width=600,
                height=400,
            )
        )

        return BasePlotter.configure_altair_theme(heatmap)

    def plot_volatility_ribbon(self, df_volatility: pd.DataFrame, country_name: str, window_months: int = 3) -> alt.Chart:
        """Ribbon di volatilita' mobile dell'inflazione."""
        required = {"date", "inflation_food_price_index", "inflation_volatility"}
        if df_volatility.empty or not required.issubset(df_volatility.columns):
            logger.warning("plot_volatility_ribbon: dati insufficienti.")
            return alt.Chart()

        df = df_volatility.copy()
        df["date"] = pd.to_datetime(df["date"])
        df_agg = (
            df.groupby("date")[["inflation_food_price_index", "inflation_volatility"]]
            .mean()
            .reset_index()
        )
        df_agg["upper"] = df_agg["inflation_food_price_index"] + df_agg["inflation_volatility"].fillna(0)
        df_agg["lower"] = df_agg["inflation_food_price_index"] - df_agg["inflation_volatility"].fillna(0)

        band = (
            alt.Chart(df_agg)
            .mark_area(opacity=0.20, color=BasePlotter.HERO_COLORS["accent"])
            .encode(
                x=alt.X("date:T", title=None, axis=alt.Axis(format="%b %Y", labelAngle=-30)),
                y=alt.Y("lower:Q", title="Inflaz. (%)", scale=alt.Scale(zero=False)),
                y2="upper:Q",
            )
        )

        line = (
            alt.Chart(df_agg)
            .mark_line(color="#d97706", strokeWidth=2)
            .encode(
                x="date:T",
                y=alt.Y("inflation_food_price_index:Q", scale=alt.Scale(zero=False)),
                tooltip=[
                    alt.Tooltip("date:T", title="Data", format="%B %Y"),
                    alt.Tooltip("inflation_food_price_index:Q", title="Inflaz.", format=".2f"),
                    alt.Tooltip("inflation_volatility:Q", title=f"Std (W={window_months}m)", format=".2f"),
                ],
            )
        )

        zero = (
            alt.Chart(pd.DataFrame({"y": [0]}))
            .mark_rule(strokeDash=[4, 4], color=BasePlotter.HERO_COLORS["neutral_mid"], strokeWidth=0.8)
            .encode(y="y:Q")
        )

        chart = alt.layer(band, zero, line).properties(
            title=alt.TitleParams(
                f"Inflazione e volatilità — {country_name}",
                subtitle=f"Banda = ±std mobile su {window_months} mesi",
                anchor="start",
            ),
            width=800,
            height=340,
        )

        return BasePlotter.configure_altair_theme(chart)
