"""
libs/plots/correlation_plots.py
=================================
Engine dedicato alle visualizzazioni correlazionali e ML-oriented del progetto H.E.R.O.

Grafici disponibili:
  - plot_commodity_correlation_matrix : heatmap di correlazione tra commodity
  - plot_lead_lag_cross_correlation   : cross-correlazione tra due serie (es. grano → pane)
  - plot_momentum_overview            : pannello momentum multi-commodity (sparkline grid)
"""

import altair as alt
import pandas as pd
import numpy as np
from typing import List, Optional

from libs.logger_config import get_logger

logger = get_logger(__name__)

_COLOR_NEUTRAL = "#6b7280"


class WFPCorrelationPlotter:
    """
    Engine per analisi di correlazione e segnali utili all'addestramento ML.
    """

    # ─────────────────────────────────────────────────────────────────────────
    # 1. CORRELATION MATRIX HEATMAP  (nuovo)
    # ─────────────────────────────────────────────────────────────────────────
    def plot_commodity_correlation_matrix(
        self,
        df_country: pd.DataFrame,
        country_name: str,
        commodity_list: Optional[List[str]] = None,
        max_commodities: int = 18,
        method: str = "pearson",
    ) -> alt.Chart:
        """
        Heatmap di correlazione (Pearson o Spearman) tra i prezzi delle commodity.

        Utile per:
          - Identificare cluster di beni con prezzi correlati (es. cereali)
          - Scoprire proxy affidabili per commodity con dati scarsi
          - Feature selection pre-ML: rimuovere variabili ridondanti

        Parametri
        ----------
        commodity_list  : lista commodity da includere; se None seleziona auto
        max_commodities : numero massimo di commodity se commodity_list è None
        method          : "pearson" (lineare) o "spearman" (rank-based)
        """
        if df_country.empty:
            return alt.Chart()

        # Auto-selezione commodity: quelle con più dati non-null
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
            # Ordiniamo per densità decrescente
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

        # Trasformiamo in formato long per Altair
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
                x=alt.X("commodity_a_clean:N", title=None,
                         axis=alt.Axis(labelAngle=-45, labelFontSize=9)),
                y=alt.Y("commodity_b_clean:N", title=None,
                         axis=alt.Axis(labelFontSize=9)),
                color=alt.Color(
                    "corr:Q",
                    title=f"r ({method})",
                    scale=alt.Scale(scheme="redblue", domain=[-1, 1], reverse=True),
                    legend=alt.Legend(gradientLength=150, tickCount=5),
                ),
                tooltip=[
                    alt.Tooltip("commodity_a_clean:N", title="Commodity A"),
                    alt.Tooltip("commodity_b_clean:N", title="Commodity B"),
                    alt.Tooltip("corr:Q",              title=f"r ({method})", format=".3f"),
                ],
            )
        )

        # Testo della correlazione nelle celle (solo se < 18 commodity per leggibilità)
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
                        alt.value(_COLOR_NEUTRAL),
                    ),
                )
            )

        return (
            alt.layer(chart, text_layer)
            .properties(
                title=alt.TitleParams(
                    f"Matrice di correlazione commodity — {country_name}",
                    subtitle=f"Metodo: {method.title()} · Rosso = correlazione positiva · Blu = negativa",
                    subtitleFontStyle="italic",
                    subtitleColor=_COLOR_NEUTRAL,
                    anchor="start",
                ),
                width=max(400, len(commodity_list) * 40),
                height=max(400, len(commodity_list) * 40),
            )
            .configure_view(stroke=None)
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 2. CROSS-CORRELAZIONE LEAD-LAG  (nuovo)
    # ─────────────────────────────────────────────────────────────────────────
    def plot_lead_lag_cross_correlation(
        self,
        df_country: pd.DataFrame,
        commodity_a: str,
        commodity_b: str,
        country_name: str,
        max_lag: int = 12,
    ) -> alt.Chart:
        """
        Grafico a barre della cross-correlazione tra due commodity a diversi lag.

        Permette di rispondere a domande come:
          "Il prezzo del grano anticipa di N mesi il prezzo del pane?"

        Lag negativo = commodity_a anticipa commodity_b.
        Lag positivo = commodity_b anticipa commodity_a.

        Utile per costruire feature lag nel dataset ML.
        """
        for col in [commodity_a, commodity_b]:
            if col not in df_country.columns:
                logger.warning(f"plot_lead_lag_cross_correlation: '{col}' non trovata.")
                return alt.Chart()

        df = df_country[["date", commodity_a, commodity_b]].dropna().copy()
        df = df.sort_values("date")
        s_a = df[commodity_a].values
        s_b = df[commodity_b].values

        # Standardizzazione
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
        df_lags["is_peak"] = df_lags["corr"].abs() == df_lags["corr"].abs().max()

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
                        range=["#2563eb", "#dc2626"],
                    ),
                    legend=None,
                ),
                tooltip=[
                    alt.Tooltip("lag:O",  title="Lag (mesi)"),
                    alt.Tooltip("corr:Q", title="Correlazione", format=".3f"),
                ],
            )
        )

        # Linee di soglia ±0.3
        rules = (
            alt.Chart(pd.DataFrame({"y": [0.3, -0.3, 0]}))
            .mark_rule(strokeDash=[4, 3], color=_COLOR_NEUTRAL, strokeWidth=0.8)
            .encode(y="y:Q")
        )

        label_a = commodity_a.replace("_", " ").title()
        label_b = commodity_b.replace("_", " ").title()

        return (
            alt.layer(rules, bars)
            .properties(
                title=alt.TitleParams(
                    f"Cross-correlazione lead-lag — {label_a} vs {label_b}",
                    subtitle=f"{country_name} · Lag<0: {label_a} anticipa {label_b} · Lag>0: viceversa",
                    subtitleFontStyle="italic",
                    subtitleColor=_COLOR_NEUTRAL,
                    anchor="start",
                ),
                width=660,
                height=320,
            )
            .configure_view(stroke=None)
            .configure_axis(grid=True, gridColor="#f0f0f0", gridWidth=0.6)
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 3. MOMENTUM OVERVIEW — sparkline grid  (nuovo)
    # ─────────────────────────────────────────────────────────────────────────
    def plot_momentum_overview(
        self,
        df_country: pd.DataFrame,
        country_name: str,
        commodity_list: Optional[List[str]] = None,
        top_n: int = 12,
    ) -> alt.Chart:
        """
        Griglia di sparkline: una mini-serie temporale del momentum (pct_change)
        per ciascuna commodity selezionata.

        Utilità immediata: identifica quali beni stanno accelerando in questo
        momento — segnale early-warning per l'insicurezza alimentare.
        """
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
                y=alt.Y("momentum:Q", title=None,
                         scale=alt.Scale(zero=True),
                         axis=alt.Axis(labels=False, ticks=False, grid=False)),
                color=alt.Color(
                    "direction:N",
                    scale=alt.Scale(domain=["su", "giù"], range=["#dc2626", "#16a34a"]),
                    legend=None,
                ),
                facet=alt.Facet("commodity:N", columns=3, title=None),
            )
            .properties(width=200, height=80)
        )

        zero_ref = (
            alt.Chart(pd.DataFrame({"y": [0]}))
            .mark_rule(strokeDash=[3, 2], color=_COLOR_NEUTRAL, strokeWidth=0.6)
            .encode(y="y:Q")
            .properties(width=200, height=80)
        )

        return (
            spark
            .resolve_scale(y="independent")
            .properties(
                title=alt.TitleParams(
                    f"Momentum mensile commodity — {country_name}",
                    subtitle="Ogni pannello = variazione % mensile del prezzo medio · Rosso = rialzo · Verde = ribasso",
                    subtitleFontStyle="italic",
                    subtitleColor=_COLOR_NEUTRAL,
                    anchor="start",
                )
            )
            .configure_view(stroke="#e5e7eb", strokeWidth=0.5)
            .configure_header(
                titleFontSize=10,
                labelFontSize=10,
                labelColor="#374151",
            )
            .configure_facet(spacing=10)
        )
