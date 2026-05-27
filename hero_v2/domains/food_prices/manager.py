"""
hero_v2.domains.food_prices.manager
===================================
Manager per i dati di Food Prices multivariati.
Gestisce il caricamento del parquet e l'istanziazione lazy delle entita' paese con il relativo dominio.
"""

from pathlib import Path
from typing import Dict, List, Optional, Union
import pandas as pd
from hero_v2.core.country import Country
from hero_v2.core.logger import get_logger
from hero_v2.domains.food_prices.domain import FoodPricesDomain

logger = get_logger(__name__)

# Tenta di importare Pandera per la validazione dello schema (se disponibile)
try:
    from World_Food_Prices.libs.data_schemas import WFPDataSchema
except ImportError:
    WFPDataSchema = None

class FoodPricesManager:
    """
    Manager centrale per caricare i dati dei prezzi alimentari WFP
    e popolarli on-demand come dominio all'interno del modello Country di HERO.
    """

    def __init__(self, parquet_path: Union[str, Path]) -> None:
        self.parquet_path = Path(parquet_path)
        self._global_df: Optional[pd.DataFrame] = None
        self._iso3_to_name: Dict[str, str] = {}
        self._countries: Dict[str, Country] = {}

    def initialize_pipeline(self) -> "FoodPricesManager":
        """Carica il Parquet e inizializza i dizionari per il lazy loading."""
        if not self.parquet_path.exists():
            logger.error(f"File consolidato assente in {self.parquet_path}")
            raise FileNotFoundError("Consolidamento prezzi non presente. Esegui prima wfp_to_parquet.")
            
        logger.info(f"Caricamento Parquet: {self.parquet_path.name}")
        self._global_df = pd.read_parquet(self.parquet_path, engine='pyarrow')
        
        # Validazione schema
        if WFPDataSchema is not None:
            logger.info("Avvio validazione dello schema dati...")
            try:
                self._global_df = WFPDataSchema.validate(self._global_df)
                logger.info("[OK] Validazione schema superata.")
            except Exception as e:
                logger.error(f"[ERRORE] Errore di validazione schema: {e}")
                raise
        else:
            logger.warning("Validazione schema saltata (modulo schema non disponibile).")
            
        # Costruzione mappa dei paesi per Lazy Loading
        unique_countries = self._global_df[['ISO3', 'country']].drop_duplicates().dropna()
        self._iso3_to_name = dict(zip(unique_countries['ISO3'], unique_countries['country']))
        logger.info(f"[OK] Inizializzazione completata! {len(self._iso3_to_name)} paesi pronti.")
        
        return self

    def get_country(self, iso3: str) -> Country:
        """
        Recupera o crea l'oggetto Country per l'ISO3 richiesto,
        e carica il dominio food_prices in modalita' lazy (on-demand).
        """
        iso3_upper = iso3.upper()
        if iso3_upper not in self._countries:
            if iso3_upper not in self._iso3_to_name:
                raise KeyError(f"Paese '{iso3_upper}' non presente nel dataset consolidato.")
            
            # Istanziamo il Paese generico del core
            logger.info(f"Istanziazione Lazy Paese + Dominio Food Prices per: {iso3_upper}...")
            country = Country(iso3_upper)
            
            # Creiamo il dominio specifico e lo registriamo
            food_domain = FoodPricesDomain(iso3_upper)
            food_domain.load_from_df(self._global_df)
            country.register_domain(food_domain)
            
            self._countries[iso3_upper] = country
            
        return self._countries[iso3_upper]

    def get_comparative_inflation_panel(self, iso3_list: List[str]) -> pd.DataFrame:
        """Estrae un panel comparativo dell'inflazione per piu' paesi."""
        panels = []
        for iso3 in iso3_list:
            try:
                country = self.get_country(iso3)
                food_domain = country.get_domain("food_prices")
                df_inf = food_domain.get_inflation_series()
                if not df_inf.empty:
                    df_national = df_inf.groupby(['ISO3', 'country', 'date'])['inflation_food_price_index'].mean().reset_index()
                    panels.append(df_national)
            except (KeyError, ValueError):
                continue
        return pd.concat(panels, ignore_index=True) if panels else pd.DataFrame()

    def get_comparative_commodity_panel(self, commodity_name: str, iso3_list: List[str]) -> pd.DataFrame:
        """Estrae le serie storiche per una commodity per piu' paesi."""
        panels = []
        for iso3 in iso3_list:
            try:
                country = self.get_country(iso3)
                food_domain = country.get_domain("food_prices")
                if commodity_name in food_domain.available_commodities:
                    panels.append(food_domain.get_time_series(commodity_name))
            except (KeyError, ValueError):
                continue
        return pd.concat(panels, ignore_index=True) if panels else pd.DataFrame()
