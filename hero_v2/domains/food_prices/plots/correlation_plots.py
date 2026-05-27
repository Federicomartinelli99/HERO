"""
hero_v2.domains.food_prices.plots.correlation_plots
====================================================
Visualizzazioni di correlazione Altair per il dominio Food Prices.
"""

import altair as alt
import pandas as pd
import numpy as np
from typing import List, Optional
from hero_v2.core.base_plotter import BasePlotter
from hero_v2.core.logger import get_logger

logger = get_logger(__name__)

class FoodCorrelationPlotter:
    """Contiene grafici di correlazione e momentum per il dominio dei prezzi alimentari."""

    def plot_commodity_correlation_matrix(self, df_country: pd.DataFrame, country_name: str, commodity_list: Optional[List[str]] = None, max_commodities: int = 18, method: str = "pearson") -> alt.Chart:
        """Matrice di correlazione heatmap per i prezzi delle commodity."""
        if df_country.empty:
            return alt.Chart()

        exclude = {
            "ISO3", "country", "adm1_name", "adm2_name", "mkt_name",
            "lat", "lon", "geo_id", "date", "year", "month",
            "currency", "components", "data_coverage",
            "index_confidence_score", "spatially_interpolated",
            "food_price_index", "inflation_food_price_index",
        }
        if commodity_list is None:
            numeric_cols = df_country.select_dtypes(include="number").columns.tolist()
            candidates = [
                c for c in numeric_cols
                if c not in exclude
                and not c.startswith(("o_", "h_", "l_", "c_", "inflation_", "trust_"))
            ]
            commodity_list = (
                df_country[candidates]
                .notna()
                .sum()
                .sort_values(ascending=False)
                .head(max_commodities)
                .index.tolist()
            )

        df_corr_input = df_country[commodity_list].dropna(how="all")
        if df_corr_input.shape[0] < 5:
            logger.warning("plot_commodity_correlation_matrix: troppi NaN, matrice non calcolabile.")
            return alt.Chart()

        corr_matrix = df_corr_input.corr(method=method).round(3)

        df_long = (
            corr_matrix.reset_index()
            .melt(id_vars="index", var_name="commodity_b", value_name="corr")
            .rename(columns={"index": "commodity_a"})
        )
        df_long["commodity_a_clean"] = df_long["commodity_a"].str.replace("_", " ").str.title()
        df_long["commodity_b_clean"] = df_long["commodity_b"].str.replace("_", " ").str.title()

        chart = (
            alt.Chart(df_long)
            .mark_rect()
            .encode(
                x=alt.X("commodity_a_clean:N", title=None, axis=alt.Axis(labelAngle=-45, labelFontSize=9)),
                y=alt.Y("commodity_b_clean:N", title=None, axis=alt.Axis(labelFontSize=9)),
                color=alt.Color("corr:Q", title=f"r ({method})",
                                scale=alt.Scale(scheme="redblue", domain=[-1, 1], reverse=True),
                                legend=alt.Legend(gradientLength=150, tickCount=5)),
                tooltip=[
                    alt.Tooltip("commodity_a_clean:N", title="Commodity A"),
                    alt.Tooltip("commodity_b_clean:N", title="Commodity B"),
                    alt.Tooltip("corr:Q", title=f"r ({method})", format=".3f"),
                ],
            )
        )

        text_layer = alt.layer()
        if len(commodity_list) <= 14:
            text_layer = (
                alt.Chart(df_long)
                .mark_text(fontSize=8)
                .encode(
                    x=alt.X("commodity_a_clean:N"),
                    y=alt.Y("commodity_b_clean:N"),
                    text=alt.Text("corr:Q", format=".2f"),
                    color=alt.condition(
                        "abs(datum.corr) > 0.6",
                        alt.value("white"),
                        alt.value(BasePlotter.HERO_COLORS["neutral_mid"]),
                    ),
                )
            )

        full_chart = alt.layer(chart, text_layer).properties(
            title=alt.TitleParams(
                f"Matrice di correlazione commodity — {country_name}",
                subtitle=f"Metodo: {method.title()} · Rosso = positiva · Blu = negativa",
                anchor="start",
            ),
            width=max(400, len(commodity_list) * 40),
            height=max(400, len(commodity_list) * 40),
        )
        return BasePlotter.configure_altair_theme(full_chart)

    def plot_lead_lag_cross_correlation(self, df_country: pd.DataFrame, commodity_a: str, commodity_b: str, country_name: str, max_lag: int = 12) -> alt.Chart:
        """Grafico della cross-correlazione temporale tra due commodity a diversi lag."""
        for col in [commodity_a, commodity_b]:
            if col not in df_country.columns:
                logger.warning(f"plot_lead_lag_cross_correlation: '{col}' non trovata.")
                return alt.Chart()

        df = df_country[["date", commodity_a, commodity_b]].dropna().copy()
        df = df.sort_values("date")
        s_a = df[commodity_a].values
        s_b = df[commodity_b].values

        def _std(s: np.ndarray) -> np.ndarray:
            std = s.std()
            return (s - s.mean()) / std if std > 0 else s - s.mean()

        s_a, s_b = _std(s_a), _std(s_b)
        n = len(s_a)

        lags = range(-max_lag, max_lag + 1)
        records = []
        for lag in lags:
            if lag == 0:
                corr = float(np.corrcoef(s_a, s_b)[0, 1])
            elif lag > 0:
                corr = float(np.corrcoef(s_a[:-lag], s_b[lag:])[0, 1]) if n - lag > 5 else np.nan
            else:
                k = -lag
                corr = float(np.corrcoef(s_a[k:], s_b[:-k])[0, 1]) if n - k > 5 else np.nan
            records.append({"lag": lag, "corr": corr})

        df_lags = pd.DataFrame(records).dropna()
        df_lags["direction"] = df_lags["corr"].apply(lambda v: "positiva" if v >= 0 else "negativa")

        bars = (
            alt.Chart(df_lags)
            .mark_bar()
            .encode(
                x=alt.X("lag:O", title="Lag (mesi)"),
                y=alt.Y("corr:Q", title="Correlazione", scale=alt.Scale(domain=[-1, 1])),
                color=alt.Color(
                    "direction:N",
                    scale=alt.Scale(
                        domain=["positiva", "negativa"],
                        range=["#2563eb", BasePlotter.HERO_COLORS["danger"]],
                    ),
                    legend=None,
                ),
                tooltip=[
                    alt.Tooltip("lag:O", title="Lag (mesi)"),
                    alt.Tooltip("corr:Q", title="Correlazione", format=".3f"),
                ],
            )
        )

        rules = (
            alt.Chart(pd.DataFrame({"y": [0.3, -0.3, 0]}))
            .mark_rule(strokeDash=[4, 3], color=BasePlotter.HERO_COLORS["neutral_mid"], strokeWidth=0.8)
            .encode(y="y:Q")
        )

        label_a = commodity_a.replace("_", " ").title()
        label_b = commodity_b.replace("_", " ").title()

        chart = alt.layer(rules, bars).properties(
            title=alt.TitleParams(
                f"Cross-correlazione lead-lag — {label_a} vs {label_b}",
                subtitle=f"{country_name} · Lag<0: {label_a} anticipa {label_b} · Lag>0: viceversa",
                anchor="start",
            ),
            width=660,
            height=320,
        )
        return BasePlotter.configure_altair_theme(chart)

    def plot_momentum_overview(self, df_country: pd.DataFrame, country_name: str, commodity_list: Optional[List[str]] = None, top_n: int = 12) -> alt.Chart:
        """Sparkline grid mostrando il momentum delle commodity nel tempo."""
        if df_country.empty or "date" not in df_country.columns:
            return alt.Chart()

        exclude = {
            "ISO3", "country", "adm1_name", "adm2_name", "mkt_name",
            "lat", "lon", "geo_id", "year", "month",
            "currency", "components", "data_coverage",
            "index_confidence_score", "spatially_interpolated",
            "food_price_index", "inflation_food_price_index",
        }

        if commodity_list is None:
            numeric_cols = df_country.select_dtypes(include="number").columns
            candidates = [
                c for c in numeric_cols
                if c not in exclude
                and not c.startswith(("o_", "h_", "l_", "c_", "inflation_", "trust_"))
            ]
            commodity_list = (
                df_country[candidates].notna().sum()
                .sort_values(ascending=False)
                .head(top_n)
                .index.tolist()
            )

        df = df_country[["date"] + commodity_list].copy()
        df["date"] = pd.to_datetime(df["date"])
        df_agg = df.groupby("date")[commodity_list].mean(numeric_only=True).reset_index()
        df_agg = df_agg.sort_values("date")

        records = []
        for comm in commodity_list:
            if comm not in df_agg.columns:
                continue
            s = df_agg[["date", comm]].dropna()
            s["momentum"] = s[comm].pct_change() * 100
            s["commodity"] = comm.replace("_", " ").title()
            records.append(s[["date", "momentum", "commodity"]])

        if not records:
            return alt.Chart()

        df_long = pd.concat(records, ignore_index=True).dropna(subset=["momentum"])
        df_long["direction"] = df_long["momentum"].apply(lambda v: "su" if v > 0 else "giù")

        spark = (
            alt.Chart(df_long)
            .mark_line(strokeWidth=1.4)
            .encode(
                x=alt.X("date:T", title=None, axis=alt.Axis(labels=False, ticks=False, grid=False)),
                y=alt.Y("momentum:Q", title=None, scale=alt.Scale(zero=True), axis=alt.Axis(labels=False, ticks=False, grid=False)),
                color=alt.Color(
                    "direction:N",
                    scale=alt.Scale(domain=["su", "giù"], range=[BasePlotter.HERO_COLORS["danger"], BasePlotter.HERO_COLORS["success"]]),
                    legend=None,
                ),
                facet=alt.Facet("commodity:N", columns=3, title=None),
            )
            .properties(width=200, height=80)
        )

        return (
            spark
            .resolve_scale(y="independent")
            .properties(
                title=alt.TitleParams(
                    f"Momentum mensile commodity — {country_name}",
                    subtitle="Ogni pannello = variazione % mensile · Rosso = rialzo · Verde = ribasso",
                    anchor="start",
                )
            )
            .configure_view(stroke="#e5e7eb", strokeWidth=0.5)
            .configure_header(titleFontSize=10, labelFontSize=10, labelColor="#374151")
            .configure_facet(spacing=10)
        )
