"""
libs/wfp_plots.py
==================
Facade centrale e Router del sistema di visualizzazione H.E.R.O.

Architettura a sotto-moduli:
  ┌─────────────────────────────────────────────────┐
  │            WFPInteractivePlotter (Facade)        │
  │  ┌──────────────┬──────────────┬──────────────┐ │
  │  │  GeoPlotter  │  TSPlotter   │  DistPlotter │ │
  │  │  geo_plots   │time_series_  │distribution_ │ │
  │  │              │    plots     │    plots     │ │
  │  └──────────────┴──────────────┴──────────────┘ │
  │  ┌──────────────────────────────────────────┐   │
  │  │          CorrPlotter                     │   │
  │  │       correlation_plots                  │   │
  │  └──────────────────────────────────────────┘   │
  └─────────────────────────────────────────────────┘

Metodi pubblici
---------------
Geografici:
  display_geospatial_heatmap(iso3_list, criterion, year, month)
  display_country_choropleth(iso3_list, criterion, year, diverging)
  display_regional_strip_map(iso3, criterion, year, month, max_regions)
  display_market_time_animation(iso3, criterion, year, animate_by)

Serie temporali:
  display_inflation_comparison(iso3_list, show_confidence_band)
  display_commodity_candle(iso3, commodity)
  display_shock_heatmap(iso3)
  display_volatility_ribbon(iso3, window_months)
  display_commodity_cross_country(commodity_name, iso3_list)   ← invariato

Distribuzionali:
  display_commodity_ranking(iso3, top_n, reference_year)
  display_price_distribution(iso3, commodity, max_regions)
  display_country_scatter(iso3_list, x_metric, y_metric, size_metric, year)
  display_market_coverage(iso3_list, year, top_n_countries)

Correlazione / ML:
  display_correlation_matrix(iso3, commodity_list, method)
  display_lead_lag(iso3, commodity_a, commodity_b, max_lag)
  display_momentum_overview(iso3, commodity_list)
"""

import altair as alt
import pandas as pd
from typing import List, Optional

from libs.multi_country_manager import MultiCountryManager
from libs.logger_config import get_logger

# ── Engine grafici specializzati ─────────────────────────────────────────────
from libs.plots.geo_plots           import WFPGeoPlotter
from libs.plots.time_series_plots   import WFPTimeSeriesPlotter
from libs.plots.distribution_plots  import WFPDistributionPlotter
from libs.plots.correlation_plots   import WFPCorrelationPlotter

logger = get_logger(__name__)


class WFPInteractivePlotter:
    """
    Facade e Router centrale per tutte le visualizzazioni del progetto H.E.R.O.

    Non contiene logica grafica: distribuisce ogni richiesta all'engine
    specializzato corrispondente. La preparazione dei dati avviene qui,
    il rendering è delegato ai sotto-moduli.
    """

    def __init__(self, manager: MultiCountryManager, world_topology=None) -> None:
        """
        Parametri
        ----------
        manager        : MultiCountryManager già inizializzato con initialize_pipeline()
        world_topology : oggetto topojson caricato con alt.topo_feature() per le mappe
                         di sfondo. Esempio:
                             from urllib.request import urlopen
                             import json
                             topo = alt.topo_feature(
                                 "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json",
                                 "countries"
                             )
                         Se None le mappe mostrano solo i punti senza sfondo cartografico.
        """
        self.manager = manager
        alt.data_transformers.disable_max_rows()

        # Istanziazione unica degli engine (pattern Singleton per sessione)
        self._geo   = WFPGeoPlotter(world_topology=world_topology)
        self._ts    = WFPTimeSeriesPlotter()
        self._dist  = WFPDistributionPlotter()
        self._corr  = WFPCorrelationPlotter()

        logger.info("WFPInteractivePlotter inizializzato con 4 engine grafici.")

    # ═════════════════════════════════════════════════════════════════════════
    # SEZIONE 1 — GEOGRAFICI
    # ═════════════════════════════════════════════════════════════════════════

    def display_geospatial_heatmap(
        self,
        iso3_list: List[str],
        criterion: str = "inflation_food_price_index",
        year: int = 2026,
        month: Optional[int] = None,
    ) -> alt.Chart:
        """
        Bubble heatmap interattiva: ogni cerchio = un mercato fisico WFP.
        Dimensione e colore codificano il valore di 'criterion'.
        Supporta zoom (rotella) e pan (trascinamento).

        Parametri
        ----------
        iso3_list : paesi da includere (lista codici ISO3)
        criterion : colonna numerica da visualizzare
        year      : anno di riferimento
        month     : se fornito, filtra il mese specifico; altrimenti media annuale
        """
        logger.info(f"[GEO] Heatmap: {iso3_list} | {criterion} | {year}/{month}")
        df_global = self._require_global_df()
        if df_global is None:
            return alt.Chart()

        mask = (df_global["ISO3"].isin(iso3_list)) & (df_global["year"] == year)
        if month:
            mask &= df_global["month"] == month
        df_filtered  = df_global[mask]
        period_str   = f"Mese {month}/{year}" if month else f"Anno {year}"
        label        = criterion.replace("_", " ").title()

        return self._geo.plot_market_heatmap(
            df_markets=df_filtered,
            criterion=criterion,
            title=f"Mappa WFP — {label} ({period_str})",
        )

    def display_country_choropleth(
        self,
        iso3_list: List[str],
        criterion: str = "inflation_food_price_index",
        year: Optional[int] = None,
        diverging: bool = False,
    ) -> alt.Chart:
        """
        Coropleta mondiale: ogni paese colorato in base alla media nazionale del criterion.

        Richiede world_topology passato al costruttore. I paesi senza dati
        appaiono in grigio neutro.

        Parametri
        ----------
        iso3_list : paesi da includere; se vuoto o None usa tutti i paesi disponibili
        criterion : metrica aggregata per paese
        year      : filtra l'anno; se None usa tutto il dataset
        diverging : True per schema rosso-bianco-blu (es. inflazione centrata in 0)
        """
        logger.info(f"[GEO] Choropleth: {iso3_list} | {criterion} | year={year}")
        df_global = self._require_global_df()
        if df_global is None:
            return alt.Chart()

        df = df_global.copy()
        if iso3_list:
            df = df[df["ISO3"].isin(iso3_list)]
        if year and "year" in df.columns:
            df = df[df["year"] == year]

        if criterion not in df.columns:
            logger.warning(f"display_country_choropleth: '{criterion}' non trovata.")
            return alt.Chart()

        df_agg = (
            df.groupby("ISO3")[criterion]
            .mean()
            .reset_index()
        )
        period_str = str(year) if year else "tutti gli anni"
        label      = criterion.replace("_", " ").title()

        return self._geo.plot_country_choropleth(
            df_aggregated=df_agg,
            criterion=criterion,
            title=f"Coropleta WFP — {label} ({period_str})",
            diverging=diverging,
        )

    def display_regional_strip_map(
        self,
        iso3: str,
        criterion: str = "inflation_food_price_index",
        year: Optional[int] = None,
        month: Optional[int] = None,
        max_regions: int = 15,
    ) -> alt.Chart:
        """
        Layout affiancato: mappa dei mercati (sinistra) + ranking regioni (destra).
        L'hover su una regione nel ranking evidenzia i mercati corrispondenti sulla mappa
        e viceversa.

        Parametri
        ----------
        iso3        : codice ISO3 del paese
        criterion   : metrica da visualizzare
        year/month  : filtro temporale opzionale
        max_regions : numero massimo di regioni nel ranking laterale
        """
        logger.info(f"[GEO] Regional strip map: {iso3} | {criterion}")
        df_global = self._require_global_df()
        if df_global is None:
            return alt.Chart()

        country = self._require_country(iso3)
        if country is None:
            return alt.Chart()

        mask = df_global["ISO3"] == iso3
        if year:
            mask &= df_global["year"] == year
        if month:
            mask &= df_global["month"] == month

        df_filtered = df_global[mask]
        return self._geo.plot_regional_strip_map(
            df_markets=df_filtered,
            criterion=criterion,
            country_name=country.name,
            max_regions=max_regions,
        )

    def display_market_time_animation(
        self,
        iso3: str,
        criterion: str = "inflation_food_price_index",
        year: Optional[int] = None,
        animate_by: str = "month",
    ) -> alt.Chart:
        """
        Mappa con slider temporale interattivo: naviga l'evoluzione della metrica
        mese per mese (o anno per anno) sui mercati fisici del paese selezionato.

        Parametri
        ----------
        iso3       : codice ISO3 del paese
        criterion  : metrica da animare
        year       : se fornito, filtra su quell'anno (utile per slider mensile)
        animate_by : "month" per slider mese · "year" per slider annuale
        """
        logger.info(f"[GEO] Time animation: {iso3} | {criterion} | by={animate_by}")
        df_global = self._require_global_df()
        if df_global is None:
            return alt.Chart()

        country = self._require_country(iso3)
        if country is None:
            return alt.Chart()

        mask = df_global["ISO3"] == iso3
        if year and animate_by == "month":
            mask &= df_global["year"] == year

        df_filtered = df_global[mask]
        return self._geo.plot_market_time_animation(
            df_markets=df_filtered,
            criterion=criterion,
            country_name=country.name,
            animate_by=animate_by,
        )

    # ═════════════════════════════════════════════════════════════════════════
    # SEZIONE 2 — SERIE TEMPORALI
    # ═════════════════════════════════════════════════════════════════════════

    def display_inflation_comparison(
        self,
        iso3_list: List[str],
        show_confidence_band: bool = True,
    ) -> alt.Chart:
        """
        Trend inflazione alimentare multi-paese con banda di incertezza opzionale.
        
        Sostituisce il metodo originale: delega la logica grafica a TSPlotter.
        """
        logger.info(f"[TS] Inflation comparison: {iso3_list}")
        df_panel = self.manager.get_comparative_inflation_panel(iso3_list)
        return self._ts.plot_inflation_trend(df_panel, show_confidence_band)

    def display_commodity_cross_country(
        self,
        commodity_name: str,
        iso3_list: List[str],
    ) -> alt.Chart:
        """
        Trend temporale di una singola commodity per più paesi.
        Metodo invariato rispetto all'originale, ora delega a TSPlotter.
        """
        logger.info(f"[TS] Commodity cross-country: {commodity_name} | {iso3_list}")
        df_panel = self.manager.get_comparative_commodity_panel(commodity_name, iso3_list)
        if df_panel.empty:
            return alt.Chart()

        # Grafico semplice diretto (la logica era già minimale)
        selection = alt.selection_point(fields=["country"], bind="legend")
        return (
            alt.Chart(df_panel)
            .mark_line(point=True)
            .encode(
                x=alt.X("date:T", title=None),
                y=alt.Y(f"{commodity_name}:Q",
                         title=f"Prezzo: {commodity_name}",
                         scale=alt.Scale(zero=False)),
                color=alt.Color("country:N",
                                scale=alt.Scale(scheme="tableau10"),
                                legend=alt.Legend(title="Paese", orient="right")),
                opacity=alt.condition(selection, alt.value(1), alt.value(0.12)),
                tooltip=[
                    "country:N",
                    alt.Tooltip("date:T",                format="%Y-%m"),
                    alt.Tooltip(f"{commodity_name}:Q",   format=".2f"),
                ],
            )
            .add_params(selection)
            .properties(
                title=alt.TitleParams(
                    f"Confronto prezzo — {commodity_name.upper()}",
                    anchor="start",
                ),
                width=820, height=380,
            )
            .configure_view(stroke=None)
            .interactive(bind_y=False)
        )

    def display_commodity_candle(
        self,
        iso3: str,
        commodity: str,
    ) -> alt.Chart:
        """
        Grafico OHLC mensile (candele giapponesi) per una commodity in un paese.

        Richiede le colonne o_, h_, l_, c_ nel dataset consolidato.
        """
        logger.info(f"[TS] Candlestick: {iso3} | {commodity}")
        country = self._require_country(iso3)
        if country is None:
            return alt.Chart()
        return self._ts.plot_commodity_candle_monthly(
            df_country=country._data,
            commodity=commodity,
            country_name=country.name,
        )

    def display_shock_heatmap(self, iso3: str) -> alt.Chart:
        """
        Heatmap Anno × Mese dell'inflazione: identifica stagionalità e shock storici.
        """
        logger.info(f"[TS] Shock heatmap: {iso3}")
        country = self._require_country(iso3)
        if country is None:
            return alt.Chart()
        df_inf = country.get_inflation_series()
        return self._ts.plot_shock_heatmap(df_panel=df_inf, country_name=country.name)

    def display_volatility_ribbon(
        self,
        iso3: str,
        window_months: int = 3,
    ) -> alt.Chart:
        """
        Ribbon inflazione ± volatilità mobile (std rolling) per un paese.
        """
        logger.info(f"[TS] Volatility ribbon: {iso3} | window={window_months}")
        country = self._require_country(iso3)
        if country is None:
            return alt.Chart()
        df_vol = country.get_inflation_volatility(window_months=window_months)
        return self._ts.plot_volatility_ribbon(
            df_volatility=df_vol,
            country_name=country.name,
            window_months=window_months,
        )

    # ═════════════════════════════════════════════════════════════════════════
    # SEZIONE 3 — DISTRIBUZIONALI
    # ═════════════════════════════════════════════════════════════════════════

    def display_commodity_ranking(
        self,
        iso3: str,
        top_n: int = 15,
        reference_year: Optional[int] = None,
    ) -> alt.Chart:
        """
        Ranking orizzontale delle commodity per inflazione media (rosso/verde).
        """
        logger.info(f"[DIST] Commodity ranking: {iso3}")
        country = self._require_country(iso3)
        if country is None:
            return alt.Chart()
        return self._dist.plot_commodity_ranking_bar(
            df_country=country._data,
            country_name=country.name,
            top_n=top_n,
            reference_year=reference_year,
        )

    def display_price_distribution(
        self,
        iso3: str,
        commodity: str,
        max_regions: int = 12,
    ) -> alt.Chart:
        """
        Strip plot + box plot distribuzione prezzi per regione (adm1_name).
        """
        logger.info(f"[DIST] Price distribution: {iso3} | {commodity}")
        country = self._require_country(iso3)
        if country is None:
            return alt.Chart()
        return self._dist.plot_price_distribution(
            df_country=country._data,
            commodity=commodity,
            country_name=country.name,
            max_regions=max_regions,
        )

    def display_country_scatter(
        self,
        iso3_list: List[str],
        x_metric: str = "inflation_food_price_index",
        y_metric: str = "data_coverage",
        size_metric: Optional[str] = "components",
        year: Optional[int] = None,
    ) -> alt.Chart:
        """
        Scatter bi-variato a livello paese: correla metriche macroeconomiche e qualità dati.
        """
        logger.info(f"[DIST] Country scatter: {x_metric} vs {y_metric}")
        df_global = self._require_global_df()
        if df_global is None:
            return alt.Chart()
        df_sel = df_global[df_global["ISO3"].isin(iso3_list)] if iso3_list else df_global
        return self._dist.plot_country_scatter(
            df_panel=df_sel,
            x_metric=x_metric,
            y_metric=y_metric,
            size_metric=size_metric,
            year=year,
        )

    def display_market_coverage(
        self,
        iso3_list: Optional[List[str]] = None,
        year: Optional[int] = None,
        top_n_countries: int = 20,
    ) -> alt.Chart:
        """
        Mosaic chart: copertura e affidabilità dei dati per paese (filtrabile per anno).
        """
        logger.info(f"[DIST] Market coverage mosaic: {year}")
        df_global = self._require_global_df()
        if df_global is None:
            return alt.Chart()
        df = df_global[df_global["ISO3"].isin(iso3_list)] if iso3_list else df_global
        return self._dist.plot_market_coverage_mosaic(
            df_global=df,
            year=year,
            top_n_countries=top_n_countries,
        )

    # ═════════════════════════════════════════════════════════════════════════
    # SEZIONE 4 — CORRELAZIONE / ML
    # ═════════════════════════════════════════════════════════════════════════

    def display_correlation_matrix(
        self,
        iso3: str,
        commodity_list: Optional[List[str]] = None,
        method: str = "pearson",
        max_commodities: int = 18,
    ) -> alt.Chart:
        """
        Heatmap di correlazione tra i prezzi delle commodity.
        Utile per feature selection pre-ML.
        """
        logger.info(f"[CORR] Correlation matrix: {iso3} | {method}")
        country = self._require_country(iso3)
        if country is None:
            return alt.Chart()
        return self._corr.plot_commodity_correlation_matrix(
            df_country=country._data,
            country_name=country.name,
            commodity_list=commodity_list,
            max_commodities=max_commodities,
            method=method,
        )

    def display_lead_lag(
        self,
        iso3: str,
        commodity_a: str,
        commodity_b: str,
        max_lag: int = 12,
    ) -> alt.Chart:
        """
        Cross-correlazione lead-lag tra due commodity: individua relazioni di anticipazione.
        Es: "Il prezzo del grano anticipa di 2 mesi il prezzo del pane?"
        """
        logger.info(f"[CORR] Lead-lag: {iso3} | {commodity_a} vs {commodity_b}")
        country = self._require_country(iso3)
        if country is None:
            return alt.Chart()
        return self._corr.plot_lead_lag_cross_correlation(
            df_country=country._data,
            commodity_a=commodity_a,
            commodity_b=commodity_b,
            country_name=country.name,
            max_lag=max_lag,
        )

    def display_momentum_overview(
        self,
        iso3: str,
        commodity_list: Optional[List[str]] = None,
        top_n: int = 12,
    ) -> alt.Chart:
        """
        Griglia di sparkline del momentum mensile per le principali commodity.
        Segnale early-warning: identifica quali beni stanno accelerando.
        """
        logger.info(f"[CORR] Momentum overview: {iso3}")
        country = self._require_country(iso3)
        if country is None:
            return alt.Chart()
        return self._corr.plot_momentum_overview(
            df_country=country._data,
            country_name=country.name,
            commodity_list=commodity_list,
            top_n=top_n,
        )

    # ═════════════════════════════════════════════════════════════════════════
    # HELPER PRIVATI
    # ═════════════════════════════════════════════════════════════════════════

    def _require_global_df(self) -> Optional[pd.DataFrame]:
        """Restituisce il DataFrame globale o loga un errore."""
        if self.manager._global_df is None:
            logger.error("DataFrame globale non inizializzato. Chiamare initialize_pipeline() prima.")
        return self.manager._global_df

    def _require_country(self, iso3: str):
        """Restituisce CountryEntity o None con log appropriato."""
        try:
            return self.manager.get_country(iso3)
        except KeyError:
            logger.error(f"Paese '{iso3}' non trovato nel registro. Verificare il codice ISO3.")
            return None
