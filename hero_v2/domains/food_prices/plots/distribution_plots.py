"""
hero_v2.domains.food_prices.plots.distribution_plots
=====================================================
Visualizzazioni distribuzionali Altair per il dominio Food Prices.
"""

import altair as alt
import pandas as pd
from typing import List, Optional
from hero_v2.core.base_plotter import BasePlotter
from hero_v2.core.logger import get_logger

logger = get_logger(__name__)

class FoodDistributionPlotter:
    """Contiene i grafici distribuzionali e di ranking per i prezzi dei prodotti alimentari."""

    def plot_commodity_ranking_bar(self, df_country: pd.DataFrame, country_name: str, top_n: int = 15, reference_year: Optional[int] = None) -> alt.Chart:
        """Classifica le commodity per tasso medio di inflazione."""
        if df_country.empty:
            return alt.Chart()

        df = df_country.copy()
        if reference_year:
            df = df[df["year"] == reference_year]

        exclude_global = {"inflation_food_price_index"}
        inflation_cols = [
            c for c in df.columns
            if c.startswith("inflation_") and c not in exclude_global
            and df[c].notna().any()
        ]
        if not inflation_cols:
            logger.warning(f"Nessuna colonna inflation_ trovata per {country_name}.")
            return alt.Chart()

        means = df[inflation_cols].mean(numeric_only=True).sort_values(key=abs, ascending=False)
        df_rank = (
            means.head(top_n)
            .reset_index()
            .rename(columns={"index": "commodity", 0: "inflaz_media"})
        )
        df_rank.columns = ["commodity", "inflaz_media"]
        df_rank["commodity_clean"] = (
            df_rank["commodity"]
            .str.replace("inflation_", "", regex=False)
            .str.replace("_", " ")
            .str.title()
        )
        df_rank["direction"] = df_rank["inflaz_media"].apply(
            lambda v: "rincaro" if v > 0 else "calo"
        )

        period_str = str(reference_year) if reference_year else "tutti gli anni"

        chart = (
            alt.Chart(df_rank)
            .mark_bar(cornerRadiusTopRight=3, cornerRadiusBottomRight=3)
            .encode(
                x=alt.X("inflaz_media:Q", title="Inflazione media (%)", scale=alt.Scale(zero=True), axis=alt.Axis(format=".1f")),
                y=alt.Y("commodity_clean:N", title=None, sort=alt.EncodingSortField(field="inflaz_media", order="descending")),
                color=alt.Color(
                    "direction:N",
                    scale=alt.Scale(
                        domain=["rincaro", "calo"],
                        range=[BasePlotter.HERO_COLORS["down_trend"], BasePlotter.HERO_COLORS["up_trend"]],
                    ),
                    legend=alt.Legend(title=""),
                ),
                tooltip=[
                    alt.Tooltip("commodity_clean:N", title="Commodity"),
                    alt.Tooltip("inflaz_media:Q", title="Inflaz. media", format=".2f"),
                ],
            )
            .properties(
                title=alt.TitleParams(
                    f"Ranking inflazione commodity — {country_name}",
                    subtitle=f"Periodo: {period_str} · Top {top_n} per valore assoluto",
                    anchor="start",
                ),
                width=600,
                height=max(250, top_n * 28),
            )
        )
        return BasePlotter.configure_altair_theme(chart)

    def plot_price_distribution(self, df_country: pd.DataFrame, commodity: str, country_name: str, max_regions: int = 12) -> alt.Chart:
        """Strip plot + box plot combinato per la distribuzione regionale dei prezzi."""
        if commodity not in df_country.columns or df_country.empty:
            logger.warning(f"Commodity '{commodity}' non trovata.")
            return alt.Chart()

        if "adm1_name" not in df_country.columns:
            logger.warning("Colonna adm1_name assente.")
            return alt.Chart()

        df = df_country[["adm1_name", commodity]].dropna().copy()
        top_regions = df["adm1_name"].value_counts().head(max_regions).index.tolist()
        df = df[df["adm1_name"].isin(top_regions)]

        strip = (
            alt.Chart(df)
            .mark_circle(size=18, opacity=0.35, color=BasePlotter.HERO_COLORS["secondary"])
            .transform_calculate(jitter="random()")
            .encode(
                x=alt.X(f"{commodity}:Q", title=f"Prezzo {commodity} (valuta locale)", scale=alt.Scale(zero=False)),
                y=alt.Y("adm1_name:N", title=None, sort=alt.EncodingSortField(field=commodity, op="median", order="descending")),
                yOffset="jitter:Q",
                tooltip=[
                    alt.Tooltip("adm1_name:N", title="Regione"),
                    alt.Tooltip(f"{commodity}:Q", title="Prezzo", format=".3f"),
                ],
            )
        )

        box = (
            alt.Chart(df)
            .mark_boxplot(
                extent="min-max",
                outliers=False,
                box=alt.MarkConfig(color=BasePlotter.HERO_COLORS["primary"], opacity=0.7),
                median=alt.MarkConfig(color=BasePlotter.HERO_COLORS["accent"], strokeWidth=2),
                ticks=alt.MarkConfig(color=BasePlotter.HERO_COLORS["primary"]),
            )
            .encode(
                x=alt.X(f"{commodity}:Q", scale=alt.Scale(zero=False)),
                y=alt.Y("adm1_name:N", sort=alt.EncodingSortField(field=commodity, op="median", order="descending")),
            )
        )

        chart = alt.layer(strip, box).properties(
            title=alt.TitleParams(
                f"Distribuzione prezzi {commodity.upper()} per regione — {country_name}",
                subtitle="Punti = mercati singoli · Box = mediana e IQR",
                anchor="start",
            ),
            width=640,
            height=max(300, len(top_regions) * 42),
        )
        return BasePlotter.configure_altair_theme(chart)

    def plot_country_scatter(self, df_panel: pd.DataFrame, x_metric: str = "inflation_food_price_index", y_metric: str = "data_coverage", size_metric: Optional[str] = "components", year: Optional[int] = None) -> alt.Chart:
        """Scatter plot comparativo tra paesi per un dato anno."""
        if df_panel.empty:
            return alt.Chart()

        df = df_panel.copy()
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df["year"] = df["date"].dt.year

        if year:
            df = df[df["year"] == year]
        elif "year" in df.columns:
            year = int(df["year"].max())
            df = df[df["year"] == year]

        agg_cols = [c for c in [x_metric, y_metric, size_metric] if c and c in df.columns]
        if "country" not in df.columns or len(agg_cols) < 2:
            logger.warning("plot_country_scatter: colonne insufficienti.")
            return alt.Chart()

        df_agg = df.groupby("country")[agg_cols].mean(numeric_only=True).reset_index()

        encode_kwargs = dict(
            x=alt.X(f"{x_metric}:Q", title=x_metric.replace("_", " ").title(), scale=alt.Scale(zero=False)),
            y=alt.Y(f"{y_metric}:Q", title=y_metric.replace("_", " ").title(), scale=alt.Scale(zero=False)),
            color=alt.Color("country:N", legend=None, scale=alt.Scale(scheme="tableau10")),
            tooltip=["country:N",
                     alt.Tooltip(f"{x_metric}:Q", format=".2f"),
                     alt.Tooltip(f"{y_metric}:Q", format=".2f")]
            + ([alt.Tooltip(f"{size_metric}:Q", format=".1f")] if size_metric and size_metric in df_agg.columns else []),
        )

        if size_metric and size_metric in df_agg.columns:
            encode_kwargs["size"] = alt.Size(
                f"{size_metric}:Q",
                title=size_metric.replace("_", " ").title(),
                scale=alt.Scale(range=[60, 600]),
            )

        points = alt.Chart(df_agg).mark_circle(opacity=0.8).encode(**encode_kwargs)

        labels = (
            alt.Chart(df_agg)
            .mark_text(align="left", dx=7, dy=-5, fontSize=9, color=BasePlotter.HERO_COLORS["neutral_mid"])
            .encode(
                x=alt.X(f"{x_metric}:Q"),
                y=alt.Y(f"{y_metric}:Q"),
                text="country:N",
            )
        )

        chart = alt.layer(points, labels).properties(
            title=alt.TitleParams(
                f"Scatter cross-country — {year}",
                subtitle=f"X: {x_metric.replace('_',' ')} · Y: {y_metric.replace('_',' ')}",
                anchor="start",
            ),
            width=640,
            height=420,
        )
        return BasePlotter.configure_altair_theme(chart)

    def plot_market_coverage_mosaic(self, df_global: pd.DataFrame, year: Optional[int] = None, top_n_countries: int = 20) -> alt.Chart:
        """Mosaic/stacked bar chart sulla qualita' e copertura dei dati per paese."""
        if df_global.empty or "data_coverage" not in df_global.columns:
            logger.warning("plot_market_coverage_mosaic: data_coverage assente.")
            return alt.Chart()

        df = df_global.copy()
        if year and "year" in df.columns:
            df = df[df["year"] == year]

        def coverage_band(v: float) -> str:
            if v >= 0.80:
                return "Alta (≥80%)"
            elif v >= 0.50:
                return "Media (50-79%)"
            else:
                return "Bassa (<50%)"

        df["coverage_band"] = pd.to_numeric(df["data_coverage"], errors="coerce").apply(
            lambda v: coverage_band(v) if pd.notna(v) else "N/D"
        )

        top_countries = df["country"].value_counts().head(top_n_countries).index.tolist()
        df = df[df["country"].isin(top_countries)]

        df_agg = (
            df.groupby(["country", "coverage_band"])
            .size()
            .reset_index(name="count")
        )
        df_agg["pct"] = df_agg.groupby("country")["count"].transform(
            lambda s: s / s.sum() * 100
        )

        band_order = ["Alta (≥80%)", "Media (50-79%)", "Bassa (<50%)", "N/D"]
        band_colors = [BasePlotter.HERO_COLORS["success"], BasePlotter.HERO_COLORS["accent"], BasePlotter.HERO_COLORS["danger"], BasePlotter.HERO_COLORS["neutral_mid"]]

        period_label = str(year) if year else "tutti gli anni"

        chart = (
            alt.Chart(df_agg)
            .mark_bar()
            .encode(
                x=alt.X("pct:Q", title="% record", stack="normalize", axis=alt.Axis(format=".0%")),
                y=alt.Y("country:N", title=None, sort=alt.EncodingSortField(field="count", op="sum", order="descending")),
                color=alt.Color("coverage_band:N", title="Copertura dati", scale=alt.Scale(domain=band_order, range=band_colors), sort=band_order),
                order=alt.Order("coverage_band:N", sort="ascending"),
                tooltip=[
                    alt.Tooltip("country:N", title="Paese"),
                    alt.Tooltip("coverage_band:N", title="Fascia"),
                    alt.Tooltip("count:Q", title="Record"),
                    alt.Tooltip("pct:Q", title="%", format=".1f"),
                ],
            )
            .properties(
                title=alt.TitleParams(
                    f"Copertura dati per paese — {period_label}",
                    subtitle="Verde = dati ad alta affidabilità · Rosso = dati stimati/interpolati",
                    anchor="start",
                ),
                width=620,
                height=max(300, top_n_countries * 26),
            )
        )
        return BasePlotter.configure_altair_theme(chart)
