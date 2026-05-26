"""
hero_v2.domains.food_prices.plots.food_plotter
==============================================
Facade centrale e Router per le visualizzazioni del dominio Food Prices.
"""

import altair as alt
import pandas as pd
from typing import List, Optional
from hero_v2.core.base_plotter import BasePlotter
from hero_v2.core.logger import get_logger
from hero_v2.domains.food_prices.manager import FoodPricesManager

# --- Sotto-plotter degli engine grafici ---
from .geo_plots import FoodGeoPlotter
from .time_series_plots import FoodTimeSeriesPlotter
from .distribution_plots import FoodDistributionPlotter
from .correlation_plots import FoodCorrelationPlotter

logger = get_logger(__name__)

class FoodInteractivePlotter(BasePlotter):
    """
    Facade centrale per tutte le visualizzazioni del dominio Food Prices.
    Gestisce la preparazione dei dati estraendoli dal Manager e dai Domini
    e delega il rendering agli engine specializzati.
    """

    def __init__(self, manager: FoodPricesManager, world_topology=None) -> None:
        self.manager = manager
        alt.data_transformers.disable_max_rows()

        # Engine specializzati
        self._geo = FoodGeoPlotter(world_topology=world_topology)
        self._ts = FoodTimeSeriesPlotter()
        self._dist = FoodDistributionPlotter()
        self._corr = FoodCorrelationPlotter()

        logger.info("FoodInteractivePlotter inizializzato con successo.")

    def _require_global_df(self) -> Optional[pd.DataFrame]:
        if self.manager._global_df is None:
            logger.warning("Il manager non e' stato inizializzato. Chiamare initialize_pipeline() prima.")
            return None
        return self.manager._global_df

    # ═════════════════════════════════════════════════════════════════════════
    # 1. GEOGRAFICI (Plotly + Altair)
    # ═════════════════════════════════════════════════════════════════════════

    def display_geospatial_heatmap(self, iso3_list: List[str], criterion: str = "inflation_food_price_index", year: int = 2026, month: Optional[int] = None):
        """Heatmap a bolle interattiva sui mercati fisici."""
        df_global = self._require_global_df()
        if df_global is None or df_global.empty:
            return None
        mask = (df_global["ISO3"].isin(iso3_list)) & (df_global["year"] == year)
        if month:
            mask &= df_global["month"] == month
        df_filtered = df_global[mask]
        period_str = f"Mese {month}/{year}" if month else f"Anno {year}"
        label = criterion.replace("_", " ").title()
        return self._geo.plot_market_heatmap(
            df_markets=df_filtered,
            criterion=criterion,
            title=f"Mappa WFP — {label} ({period_str})",
        )

    def display_country_choropleth(self, iso3_list: List[str], criterion: str = "inflation_food_price_index", year: Optional[int] = None, diverging: bool = False):
        """Mappa coropleta a livello nazionale."""
        df_global = self._require_global_df()
        if df_global is None or df_global.empty:
            return None
        df = df_global.copy()
        if iso3_list:
            df = df[df["ISO3"].isin(iso3_list)]
        if year and "year" in df.columns:
            df = df[df["year"] == year]

        df_agg = df.groupby("ISO3")[criterion].mean().reset_index()
        period_str = str(year) if year else "tutti gli anni"
        label = criterion.replace("_", " ").title()
        return self._geo.plot_country_choropleth(
            df_aggregated=df_agg,
            criterion=criterion,
            title=f"Coropleta WFP — {label} ({period_str})",
            diverging=diverging,
        )

    def display_regional_strip_map(self, iso3: str, criterion: str = "inflation_food_price_index", year: Optional[int] = None, month: Optional[int] = None, max_regions: int = 15):
        """Mappa dei mercati affiancata dal barchart di ranking delle regioni adm1."""
        df_global = self._require_global_df()
        if df_global is None or df_global.empty:
            return None
        country = self.manager.get_country(iso3)
        mask = df_global["ISO3"] == iso3.upper()
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

    def display_market_time_animation(self, iso3: str, criterion: str = "inflation_food_price_index", year: Optional[int] = None, animate_by: str = "month"):
        """Animazione temporale interattiva sulla mappa geografica."""
        df_global = self._require_global_df()
        if df_global is None or df_global.empty:
            return None
        country = self.manager.get_country(iso3)
        mask = df_global["ISO3"] == iso3.upper()
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
    # 2. SERIE TEMPORALI (Altair)
    # ═════════════════════════════════════════════════════════════════════════

    def display_inflation_comparison(self, iso3_list: List[str], show_confidence_band: bool = True) -> alt.Chart:
        """Confronta l'inflazione alimentare di piu' paesi."""
        df_panel = self.manager.get_comparative_inflation_panel(iso3_list)
        return self._ts.plot_inflation_trend(df_panel, show_confidence_band)

    def display_commodity_cross_country(self, commodity_name: str, iso3_list: List[str]) -> alt.Chart:
        """Serie storica di una commodity in piu' paesi."""
        df_panel = self.manager.get_comparative_commodity_panel(commodity_name, iso3_list)
        if df_panel.empty:
            return alt.Chart()
        selection = alt.selection_point(fields=["country"], bind="legend")
        chart = (
            alt.Chart(df_panel)
            .mark_line(point=True)
            .encode(
                x=alt.X("date:T", title=None),
                y=alt.Y(f"{commodity_name}:Q", title=f"Prezzo: {commodity_name}", scale=alt.Scale(zero=False)),
                color=alt.Color("country:N", scale=alt.Scale(scheme="tableau10"), legend=alt.Legend(title="Paese", orient="right")),
                opacity=alt.condition(selection, alt.value(1), alt.value(0.12)),
                tooltip=[
                    "country:N",
                    alt.Tooltip("date:T", format="%Y-%m"),
                    alt.Tooltip(f"{commodity_name}:Q", format=".2f"),
                ],
            )
            .add_params(selection)
            .properties(
                title=alt.TitleParams(f"Confronto prezzo — {commodity_name.upper()}", anchor="start"),
                width=800, height=380,
            )
        )
        return BasePlotter.configure_altair_theme(chart)

    def display_commodity_candle(self, iso3: str, commodity: str) -> alt.Chart:
        """Candele OHLC mensili per una commodity."""
        country = self.manager.get_country(iso3)
        food_domain = country.get_domain("food_prices")
        return self._ts.plot_commodity_candle_monthly(
            df_country=food_domain.data,
            commodity=commodity,
            country_name=country.name,
        )

    def display_shock_heatmap(self, iso3: str) -> alt.Chart:
        """Heatmap shock inflazione."""
        country = self.manager.get_country(iso3)
        food_domain = country.get_domain("food_prices")
        return self._ts.plot_shock_heatmap(
            df_panel=food_domain.data,
            country_name=country.name,
        )

    def display_volatility_ribbon(self, iso3: str, window_months: int = 3) -> alt.Chart:
        """Ribbon di volatilita' mobile."""
        country = self.manager.get_country(iso3)
        food_domain = country.get_domain("food_prices")
        df_vol = food_domain.get_inflation_volatility(window_months)
        # Rinominiamo la colonna 'volatility' in 'inflation_volatility' come atteso dal plot engine
        if not df_vol.empty:
            df_vol = df_vol.rename(columns={"volatility": "inflation_volatility"})
        return self._ts.plot_volatility_ribbon(
            df_volatility=df_vol,
            country_name=country.name,
            window_months=window_months,
        )

    # ═════════════════════════════════════════════════════════════════════════
    # 3. DISTRIBUZIONALI (Altair)
    # ═════════════════════════════════════════════════════════════════════════

    def display_commodity_ranking(self, iso3: str, top_n: int = 15, reference_year: Optional[int] = None) -> alt.Chart:
        """Classifica le commodity del paese per tasso d'inflazione."""
        country = self.manager.get_country(iso3)
        food_domain = country.get_domain("food_prices")
        return self._dist.plot_commodity_ranking_bar(
            df_country=food_domain.data,
            country_name=country.name,
            top_n=top_n,
            reference_year=reference_year,
        )

    def display_price_distribution(self, iso3: str, commodity: str, max_regions: int = 12) -> alt.Chart:
        """Distribuzione dei prezzi di una commodity per regione."""
        country = self.manager.get_country(iso3)
        food_domain = country.get_domain("food_prices")
        return self._dist.plot_price_distribution(
            df_country=food_domain.data,
            commodity=commodity,
            country_name=country.name,
            max_regions=max_regions,
        )

    def display_country_scatter(self, iso3_list: List[str], x_metric: str = "inflation_food_price_index", y_metric: str = "data_coverage", size_metric: Optional[str] = "components", year: Optional[int] = None) -> alt.Chart:
        """Scatter plot comparativo tra paesi."""
        df_global = self._require_global_df()
        if df_global is None or df_global.empty:
            return alt.Chart()
        df_filtered = df_global[df_global["ISO3"].isin(iso3_list)]
        return self._dist.plot_country_scatter(
            df_panel=df_filtered,
            x_metric=x_metric,
            y_metric=y_metric,
            size_metric=size_metric,
            year=year,
        )

    def display_market_coverage(self, iso3_list: List[str], year: Optional[int] = None, top_n_countries: int = 20) -> alt.Chart:
        """Stacked bar chart della qualita' del dato (data coverage)."""
        df_global = self._require_global_df()
        if df_global is None or df_global.empty:
            return alt.Chart()
        df_filtered = df_global[df_global["ISO3"].isin(iso3_list)]
        return self._dist.plot_market_coverage_mosaic(
            df_global=df_filtered,
            year=year,
            top_n_countries=top_n_countries,
        )

    # ═════════════════════════════════════════════════════════════════════════
    # 4. CORRELAZIONE / MACHINE LEARNING (Altair)
    # ═════════════════════════════════════════════════════════════════════════

    def display_correlation_matrix(self, iso3: str, commodity_list: Optional[List[str]] = None, method: str = "pearson") -> alt.Chart:
        """Matrice di correlazione heatmap per i prezzi del paese."""
        country = self.manager.get_country(iso3)
        food_domain = country.get_domain("food_prices")
        return self._corr.plot_commodity_correlation_matrix(
            df_country=food_domain.data,
            country_name=country.name,
            commodity_list=commodity_list,
            method=method,
        )

    def display_lead_lag(self, iso3: str, commodity_a: str, commodity_b: str, max_lag: int = 12) -> alt.Chart:
        """Cross-correlazione a sfasamento temporale (lags) tra due beni."""
        country = self.manager.get_country(iso3)
        food_domain = country.get_domain("food_prices")
        return self._corr.plot_lead_lag_cross_correlation(
            df_country=food_domain.data,
            commodity_a=commodity_a,
            commodity_b=commodity_b,
            country_name=country.name,
            max_lag=max_lag,
        )

    def display_momentum_overview(self, iso3: str, commodity_list: Optional[List[str]] = None) -> alt.Chart:
        """Sparkline grid del momentum per le commodity."""
        country = self.manager.get_country(iso3)
        food_domain = country.get_domain("food_prices")
        return self._corr.plot_momentum_overview(
            df_country=food_domain.data,
            country_name=country.name,
            commodity_list=commodity_list,
        )
