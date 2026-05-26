import pandas as pd
from typing import List, Optional
from libs.logger_config import get_logger

logger = get_logger(__name__)

class CountryEntity:
    def __init__(self, iso3: str, name: str, country_data: pd.DataFrame):
        self.iso3 = iso3
        self.name = name
        
        # Filtriamo i dati globali SOLO per questo paese
        self._data = country_data[country_data['ISO3'] == iso3].copy()
        
        if self._data.empty:
            logger.warning(f"Inizializzata Entità vuota per {self.name} ({self.iso3}).")
            self.available_commodities = []
        else:
            # Ordiniamo cronologicamente (fondamentale per le feature ML)
            self._data = self._data.sort_values(by=['adm1_name', 'date'])
            
            # Troviamo dinamicamente tutte le materie prime effettivamente presenti per questo paese
            # (tutte le colonne numeriche che non sono metadati)
            meta_cols = {'ISO3', 'country', 'adm1_name', 'adm2_name', 'mkt_name', 'currency', 'year', 'month', 'date', 
                         'components', 'start_dense_data', 'last_survey_point', 'data_coverage', 'data_coverage_recent', 
                         'index_confidence_score', 'spatially_interpolated', 'food_price_index', 'inflation_food_price_index', 
                         'c_food_price_index', 'lat', 'lon', 'geo_id', 'DATES'}
                         
            # Le vere commodity sono le colonne che non sono in meta_cols e non iniziano con prefissi tecnici (o_, h_, l_, c_, inflation_, trust_)
            all_cols = set(self._data.columns)
            potential_commodities = all_cols - meta_cols
            
            self.available_commodities = [
                c for c in potential_commodities 
                if not any(c.startswith(prefix) for prefix in ['o_', 'h_', 'l_', 'c_', 'inflation_', 'trust_'])
                and pd.api.types.is_numeric_dtype(self._data[c])
                and self._data[c].notna().sum() > 0 # Almeno un valore non nullo
            ]
            
            logger.info(f"Inizializzata Entità: {self.name} ({self.iso3}) -> {len(self._data)} record. Trovate {len(self.available_commodities)} commodities.")

    def get_inflation_series(self) -> pd.DataFrame:
        if 'inflation_food_price_index' not in self._data.columns:
            return pd.DataFrame()
        return self._data.dropna(subset=['inflation_food_price_index'])

    def get_inflation_volatility(self, window_months: int = 3) -> pd.DataFrame:
        df_inf = self.get_inflation_series()
        if df_inf.empty:
            return pd.DataFrame()
            
        df_nat = df_inf.groupby('date')['inflation_food_price_index'].mean().reset_index()
        df_nat['volatility'] = df_nat['inflation_food_price_index'].rolling(window=window_months).std()
        
        # Limiti del nastro di volatilità
        df_nat['upper_band'] = df_nat['inflation_food_price_index'] + df_nat['volatility']
        df_nat['lower_band'] = df_nat['inflation_food_price_index'] - df_nat['volatility']
        
        return df_nat.dropna(subset=['volatility'])

    def get_commodity_series(self, commodity_name: str) -> pd.DataFrame:
        if commodity_name not in self._data.columns:
            raise KeyError(f"La materia prima '{commodity_name}' non è disponibile per {self.name}.")
        return self._data.dropna(subset=[commodity_name])

    def get_price_momentum(self, commodity_name: str, periods: int = 1) -> pd.DataFrame:
        df_comm = self.get_commodity_series(commodity_name)
        if df_comm.empty:
            return pd.DataFrame()
            
        df_nat = df_comm.groupby('date')[commodity_name].mean().reset_index()
        df_nat[f'{commodity_name}_momentum'] = df_nat[commodity_name].pct_change(periods=periods)
        return df_nat.dropna()

    def get_commodity_trends(self, commodities: List[str]) -> pd.DataFrame:
        """Estrae le serie storiche medie nazionali per una lista di commodity specifiche."""
        if self._data.empty:
            return pd.DataFrame()
            
        available_cols = [c for c in commodities if c in self._data.columns]
        if not available_cols:
            return pd.DataFrame()
            
        trend = self._data.groupby(['date'], observed=True)[available_cols].mean().reset_index()
        return trend