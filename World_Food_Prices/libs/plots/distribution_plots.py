"""
libs/plots/distribution_plots.py
==================================
Engine dedicato alle visualizzazioni distribuzionali e di ranking del progetto H.E.R.O.

Grafici disponibili:
  - plot_commodity_ranking_bar   : classifica commodity per impatto inflazionistico
  - plot_price_distribution      : strip + box plot distribuzione prezzi per regione
  - plot_country_scatter         : scatter bi-variato paesi (es. inflaz. vs copertura)
  - plot_market_coverage_mosaic  : Mosaic/Treemap copertura dati per paese/anno
"""

import altair as alt
import pandas as pd
import numpy as np
from typing import List, Optional

from libs.logger_config import get_logger

logger = get_logger(__name__)

_COLOR_NEUTRAL = "#6b7280"
_SCHEME_MULTI  = "tableau10"


class WFPDistributionPlotter:
    """
    Engine per grafici distribuzionali, ranking e confronti cross-sezionali.
    """

    # ─────────────────────────────────────────────────────────────────────────
    # 1. RANKING BAR — commodity per inflazione media  (nuovo)
    # ─────────────────────────────────────────────────────────────────────────
    def plot_commodity_ranking_bar(
        self,
        df_country: pd.DataFrame,
        country_name: str,
        top_n: int = 15,
        reference_year: Optional[int] = None,
    ) -> alt.Chart:
        """
        Grafico a barre orizzontali: classifica le commodity per inflazione media.

        Evidenzia in rosso i beni con inflazione positiva (rincaro) e in
        verde quelli con deflazione (calo prezzi). Le barre sono ordinate
        per valore assoluto per permettere il confronto immediato.

        Parametri
        ----------
        df_country      : DataFrame del singolo paese (da CountryEntity._data)
        country_name    : stringa usata nel titolo
        top_n           : quante commodity mostrare (default 15)
        reference_year  : se fornito, filtra solo quell'anno
        """
        if df_country.empty:
            return alt.Chart()

        df = df_country.copy()
        if reference_year:
            df = df[df["year"] == reference_year]

        # Individuiamo le colonne inflazione commodity (prefix inflation_)
        exclude_global = {"inflation_food_price_index"}
        inflation_cols = [
            c for c in df.columns
            if c.startswith("inflation_") and c not in exclude_global
            and df[c].notna().any()
        ]
        if not inflation_cols:
            logger.warning(f"Nessuna colonna inflation_ trovata per {country_name}.")
            return alt.Chart()

        # Media per commodity
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
                x=alt.X(
                    "inflaz_media:Q",
                    title="Inflazione media (%)",
                    scale=alt.Scale(zero=True),
                    axis=alt.Axis(format=".1f"),
                ),
                y=alt.Y(
                    "commodity_clean:N",
                    title=None,
                    sort=alt.EncodingSortField(field="inflaz_media", order="descending"),
                ),
                color=alt.Color(
                    "direction:N",
                    scale=alt.Scale(
                        domain=["rincaro", "calo"],
                        range=["#dc2626", "#16a34a"],
                    ),
                    legend=alt.Legend(title=""),
                ),
                tooltip=[
                    alt.Tooltip("commodity_clean:N", title="Commodity"),
                    alt.Tooltip("inflaz_media:Q",    title="Inflaz. media", format=".2f"),
                ],
            )
            .properties(
                title=alt.TitleParams(
                    f"Ranking inflazione commodity — {country_name}",
                    subtitle=f"Periodo: {period_str} · Top {top_n} per valore assoluto",
                    subtitleFontStyle="italic",
                    subtitleColor=_COLOR_NEUTRAL,
                    anchor="start",
                ),
                width=600,
                height=max(250, top_n * 28),
            )
            .configure_view(stroke=None)
            .configure_axis(grid=True, gridColor="#f0f0f0", gridWidth=0.6)
        )
        return chart

    # ─────────────────────────────────────────────────────────────────────────
    # 2. STRIP + BOX PLOT  per regione  (nuovo)
    # ─────────────────────────────────────────────────────────────────────────
    def plot_price_distribution(
        self,
        df_country: pd.DataFrame,
        commodity: str,
        country_name: str,
        max_regions: int = 12,
    ) -> alt.Chart:
        """
        Distribuzione dei prezzi di una commodity per regione (adm1_name).

        Combina:
          - Strip plot (jitter orizzontale) = ogni punto è un mercato/mese
          - Box plot sovrapposto = mediana e IQR per regione

        Permette di vedere sia la forma della distribuzione sia gli outlier
        regionali che scomparirebbero in una semplice media.
        """
        if commodity not in df_country.columns or df_country.empty:
            logger.warning(f"Commodity '{commodity}' non trovata.")
            return alt.Chart()

        if "adm1_name" not in df_country.columns:
            logger.warning("Colonna adm1_name assente; impossibile stratificare per regione.")
            return alt.Chart()

        df = df_country[["adm1_name", commodity]].dropna().copy()

        # Limitiamo alle regioni con più dati per leggibilità
        top_regions = (
            df["adm1_name"].value_counts().head(max_regions).index.tolist()
        )
        df = df[df["adm1_name"].isin(top_regions)]

        # Jitter manuale tramite colonna transform_calculate in Altair
        strip = (
            alt.Chart(df)
            .mark_circle(size=18, opacity=0.35, color="#6366f1")
            .transform_calculate(jitter="random()")
            .encode(
                x=alt.X(
                    f"{commodity}:Q",
                    title=f"Prezzo {commodity} (valuta locale)",
                    scale=alt.Scale(zero=False),
                ),
                y=alt.Y(
                    "adm1_name:N",
                    title=None,
                    sort=alt.EncodingSortField(field=commodity, op="median", order="descending"),
                ),
                yOffset="jitter:Q",
                tooltip=[
                    alt.Tooltip("adm1_name:N",    title="Regione"),
                    alt.Tooltip(f"{commodity}:Q", title="Prezzo", format=".3f"),
                ],
            )
        )

        # Box plot (mediana + IQR)
        box = (
            alt.Chart(df)
            .mark_boxplot(
                extent="min-max",
                outliers=False,
                box=alt.MarkConfig(color="#1e3a5f", opacity=0.7),
                median=alt.MarkConfig(color="#f59e0b", strokeWidth=2),
                ticks=alt.MarkConfig(color="#1e3a5f"),
            )
            .encode(
                x=alt.X(f"{commodity}:Q", scale=alt.Scale(zero=False)),
                y=alt.Y("adm1_name:N",
                        sort=alt.EncodingSortField(field=commodity, op="median", order="descending")),
            )
        )

        return (
            alt.layer(strip, box)
            .properties(
                title=alt.TitleParams(
                    f"Distribuzione prezzi {commodity.upper()} per regione — {country_name}",
                    subtitle="Punti = singoli mercati · Box = mediana e IQR",
                    subtitleFontStyle="italic",
                    subtitleColor=_COLOR_NEUTRAL,
                    anchor="start",
                ),
                width=640,
                height=max(300, len(top_regions) * 42),
            )
            .configure_view(stroke=None)
            .configure_axis(grid=True, gridColor="#f0f0f0", gridWidth=0.6)
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 3. SCATTER CROSS-COUNTRY  (nuovo)
    # ─────────────────────────────────────────────────────────────────────────
    def plot_country_scatter(
        self,
        df_panel: pd.DataFrame,
        x_metric: str = "inflation_food_price_index",
        y_metric: str = "data_coverage",
        size_metric: Optional[str] = "components",
        year: Optional[int] = None,
    ) -> alt.Chart:
        """
        Scatter plot bi-variato a livello paese/anno.

        Ogni punto = un paese in un anno specifico (media nazionale).
        Utile per correlare, es., inflazione vs copertura dati oppure
        inflazione vs confidence score (utile per la validazione ML).

        Parametri
        ----------
        x_metric / y_metric   : colonne numeriche da posizionare sugli assi
        size_metric           : terza dimensione (area del punto), opzionale
        year                  : filtra l'anno; se None usa l'ultimo disponibile
        """
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

        # Aggregazione a livello paese
        agg_cols = [c for c in [x_metric, y_metric, size_metric] if c and c in df.columns]
        if "country" not in df.columns or len(agg_cols) < 2:
            logger.warning("plot_country_scatter: colonne insufficienti per lo scatter.")
            return alt.Chart()

        df_agg = df.groupby("country")[agg_cols].mean(numeric_only=True).reset_index()

        # Encoding base
        encode_kwargs: dict = dict(
            x=alt.X(
                f"{x_metric}:Q",
                title=x_metric.replace("_", " ").title(),
                scale=alt.Scale(zero=False),
            ),
            y=alt.Y(
                f"{y_metric}:Q",
                title=y_metric.replace("_", " ").title(),
                scale=alt.Scale(zero=False),
            ),
            color=alt.Color("country:N", legend=None,
                            scale=alt.Scale(scheme=_SCHEME_MULTI)),
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

        # Etichette paese
        labels = (
            alt.Chart(df_agg)
            .mark_text(align="left", dx=7, dy=-5, fontSize=9, color=_COLOR_NEUTRAL)
            .encode(
                x=alt.X(f"{x_metric}:Q"),
                y=alt.Y(f"{y_metric}:Q"),
                text="country:N",
            )
        )

        return (
            alt.layer(points, labels)
            .properties(
                title=alt.TitleParams(
                    f"Scatter cross-country — {year}",
                    subtitle=f"X: {x_metric.replace('_',' ')} · Y: {y_metric.replace('_',' ')}",
                    subtitleFontStyle="italic",
                    subtitleColor=_COLOR_NEUTRAL,
                    anchor="start",
                ),
                width=640,
                height=420,
            )
            .configure_view(stroke=None)
            .configure_axis(grid=True, gridColor="#f0f0f0", gridWidth=0.6)
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 4. TREEMAP COPERTURA DATI  (nuovo)
    # ─────────────────────────────────────────────────────────────────────────
    def plot_market_coverage_mosaic(
        self,
        df_global: pd.DataFrame,
        year: Optional[int] = None,
        top_n_countries: int = 20,
    ) -> alt.Chart:
        """
        Mosaic chart (barre normalizzate impilate) della copertura dati WFP.

        Ogni riga = un paese (top N per numero di mercati).
        Ogni segmento colorato = percentuale di record per livello di
        data_coverage (< 0.5 / 0.5–0.8 / > 0.8).

        Permette di valutare a colpo d'occhio dove i dati sono più affidabili.
        """
        if df_global.empty or "data_coverage" not in df_global.columns:
            logger.warning("plot_market_coverage_mosaic: data_coverage assente.")
            return alt.Chart()

        df = df_global.copy()
        if year and "year" in df.columns:
            df = df[df["year"] == year]

        # Classificazione copertura
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

        # Top N paesi per numero di record
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
        band_colors = ["#16a34a", "#f59e0b", "#dc2626", "#9ca3af"]

        period_label = str(year) if year else "tutti gli anni"

        chart = (
            alt.Chart(df_agg)
            .mark_bar()
            .encode(
                x=alt.X("pct:Q", title="% record", stack="normalize",
                         axis=alt.Axis(format=".0%")),
                y=alt.Y(
                    "country:N",
                    title=None,
                    sort=alt.EncodingSortField(field="count", op="sum", order="descending"),
                ),
                color=alt.Color(
                    "coverage_band:N",
                    title="Copertura dati",
                    scale=alt.Scale(domain=band_order, range=band_colors),
                    sort=band_order,
                ),
                order=alt.Order("coverage_band:N", sort="ascending"),
                tooltip=[
                    alt.Tooltip("country:N",       title="Paese"),
                    alt.Tooltip("coverage_band:N", title="Fascia"),
                    alt.Tooltip("count:Q",         title="Record"),
                    alt.Tooltip("pct:Q",           title="%", format=".1f"),
                ],
            )
            .properties(
                title=alt.TitleParams(
                    f"Copertura dati per paese — {period_label}",
                    subtitle="Verde = dati ad alta affidabilità · Rosso = dati stimati/interpolati",
                    subtitleFontStyle="italic",
                    subtitleColor=_COLOR_NEUTRAL,
                    anchor="start",
                ),
                width=620,
                height=max(300, top_n_countries * 26),
            )
            .configure_view(stroke=None)
            .configure_axis(grid=False)
        )
        return chart
