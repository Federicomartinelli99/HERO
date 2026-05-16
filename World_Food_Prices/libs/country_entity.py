import pandas as pd
from typing import List
from libs.logger_config import get_logger

logger = get_logger(__name__)

class CountryEntity:
    """
    Entità Paese: isola lo stato locale e introduce Feature Engineering
    direttamente predisposta per l'addestramento ML.
    """
    def __init__(self, iso3: str, name: str, country_data: pd.DataFrame):
        self.iso3 = iso3
        self.name = name
        self._data = country_data[country_data['ISO3'] == iso3].copy()
        
        if 'date' in self._data.columns:
            self._data = self._data.sort_values(by=['adm1_name', 'date'])
        
        logger.info(f"Inizializzata Entità: {self.name} ({self.iso3}) -> {len(self._data)} record.")

    @property
    def available_commodities(self) -> List[str]:
        exclude = ['ISO3', 'country', 'adm1_name', 'adm2_name', 'mkt_name', 'lat', 'lon', 'geo_id', 'date', 'year', 'month']
        commodity_cols = [c for c in self._data.columns if c not in exclude and not c.startswith(('o_', 'h_', 'l_', 'c_', 'inflation_', 'trust_'))]
        return [col for col in commodity_cols if self._data[col].notna().any()]

    def get_inflation_series(self) -> pd.DataFrame:
        if 'inflation_food_price_index' not in self._data.columns:
            return pd.DataFrame()
        return (self._data.dropna(subset=['inflation_food_price_index'])
                .groupby(['ISO3', 'country', 'adm1_name', 'date'], observed=True)['inflation_food_price_index']
                .mean().reset_index())

    def get_commodity_series(self, commodity_name: str) -> pd.DataFrame:
        if commodity_name not in self._data.columns:
            raise ValueError(f"Commodity '{commodity_name}' assente in {self.name}.")
        return (self._data.dropna(subset=[commodity_name])
                .groupby(['ISO3', 'country', 'date'], observed=True)[commodity_name]
                .mean().reset_index())

    # --- NUOVI METODI DI FEATURE ENGINEERING ---
    
    def get_inflation_volatility(self, window_months: int = 3) -> pd.DataFrame:
        """Calcola la volatilità (incertezza di mercato) tramite std dev mobile dell'inflazione."""
        df_inf = self.get_inflation_series()
        if df_inf.empty:
            logger.warning(f"Dati inflazione assenti per la volatilità in {self.name}.")
            return pd.DataFrame()
            
        df_inf['inflation_volatility'] = (
            df_inf.groupby(['ISO3', 'country', 'adm1_name'])['inflation_food_price_index']
            .rolling(window=window_months, min_periods=1)
            .std()
            .reset_index(level=[0, 1, 2], drop=True)
        )
        return df_inf

    def get_price_momentum(self, commodity_name: str, periods: int = 1) -> pd.DataFrame:
        """Calcola il momentum (variazione % / derivata prima) di una commodity."""
        try:
            df_comm = self.get_commodity_series(commodity_name)
        except ValueError as e:
            logger.warning(str(e))
            return pd.DataFrame()
            
        df_comm = df_comm.sort_values(by='date')
        df_comm[f'{commodity_name}_momentum'] = df_comm[commodity_name].pct_change(periods=periods)
        return df_comm
