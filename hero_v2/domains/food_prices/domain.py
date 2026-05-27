"""
hero_v2.domains.food_prices.domain
==================================
Implementazione del Domain Layer per i prezzi dei prodotti alimentari (World Food Prices).
"""

from typing import Dict, Any, List, Optional
import pandas as pd
from hero_v2.core.base_domain import BaseDomainLayer
from hero_v2.core.logger import get_logger

logger = get_logger(__name__)

# Metadati o colonne di sistema che non sono commodity
META_COLS = {
    'ISO3', 'country', 'adm1_name', 'adm2_name', 'mkt_name', 'currency', 
    'year', 'month', 'date', 'components', 'start_dense_data', 'last_survey_point', 
    'data_coverage', 'data_coverage_recent', 'index_confidence_score', 
    'spatially_interpolated', 'food_price_index', 'inflation_food_price_index', 
    'c_food_price_index', 'lat', 'lon', 'geo_id', 'DATES'
}

class FoodPricesDomain(BaseDomainLayer):
    """
    Gestisce il dataset dei prezzi alimentari WFP per un singolo paese.
    Implementa BaseDomainLayer.
    """

    def __init__(self, iso3: str, global_df: Optional[pd.DataFrame] = None) -> None:
        super().__init__(iso3)
        self.available_commodities: List[str] = []
        if global_df is not None:
            self.load_from_df(global_df)

    def load_data(self) -> pd.DataFrame:
        """
        Caricamento dei dati per il paese. In questo dominio l'inizializzazione
        avviene tramite load_from_df passata dal Manager (Lazy loading), ma se self.data 
        e' gia' popolato restituisce quello.
        """
        return self.data

    def load_from_df(self, global_df: pd.DataFrame) -> None:
        """Popola i dati del paese filtrando dal DataFrame globale consolidato."""
        self.data = global_df[global_df['ISO3'] == self.iso3].copy()
        
        if self.data.empty:
            logger.warning(f"Nessun dato Food Prices trovato per {self.iso3}")
            self.available_commodities = []
        else:
            self.data = self.data.sort_values(by=['adm1_name', 'date'])
            
            # Identificazione automatica delle commodity disponibili
            all_cols = set(self.data.columns)
            potential_commodities = all_cols - META_COLS
            
            self.available_commodities = sorted([
                c for c in potential_commodities 
                if not any(c.startswith(prefix) for prefix in ['o_', 'h_', 'l_', 'c_', 'inflation_', 'trust_'])
                and pd.api.types.is_numeric_dtype(self.data[c])
                and self.data[c].notna().sum() > 0
            ])
            logger.info(f"Dominio Food Prices caricato per {self.iso3}: {len(self.data)} record, {len(self.available_commodities)} commodity.")

    def get_time_series(self, metric: str, **kwargs) -> pd.DataFrame:
        """
        Estrae una serie temporale media nazionale per la metrica / commodity richiesta.
        """
        if self.data.empty:
            return pd.DataFrame()

        if metric == 'inflation_food_price_index':
            if 'inflation_food_price_index' not in self.data.columns:
                return pd.DataFrame()
            return self.data.dropna(subset=['inflation_food_price_index'])

        if metric not in self.data.columns:
            raise KeyError(f"Metrica o commodity '{metric}' non disponibile.")
            
        return self.data.dropna(subset=[metric])

    def get_summary(self) -> Dict[str, Any]:
        """Restituisce statistiche descrittive generali."""
        if self.data.empty:
            return {"status": "no_data"}
        return {
            "iso3": self.iso3,
            "total_records": len(self.data),
            "num_markets": self.data['mkt_name'].nunique() if 'mkt_name' in self.data.columns else 0,
            "num_commodities": len(self.available_commodities),
            "date_range": [str(self.data['date'].min()), str(self.data['date'].max())] if 'date' in self.data.columns else None,
            "available_commodities": self.available_commodities[:15]  # prime 15
        }

    @property
    def available_metrics(self) -> List[str]:
        """Restituisce le metriche storiche analizzabili."""
        metrics = []
        if 'inflation_food_price_index' in self.data.columns:
            metrics.append('inflation_food_price_index')
        metrics.extend(self.available_commodities)
        return metrics

    @property
    def domain_name(self) -> str:
        return "food_prices"

    # --- Metodi analitici specifici (ereditati da CountryEntity) ---
    
    def get_inflation_series(self) -> pd.DataFrame:
        """Serie storica inflazione."""
        return self.get_time_series('inflation_food_price_index')

    def get_inflation_volatility(self, window_months: int = 3) -> pd.DataFrame:
        """Calcola la volatilità rolling dell'inflazione alimentare."""
        df_inf = self.get_inflation_series()
        if df_inf.empty:
            return pd.DataFrame()
            
        df_nat = df_inf.groupby('date')['inflation_food_price_index'].mean().reset_index()
        df_nat['volatility'] = df_nat['inflation_food_price_index'].rolling(window=window_months).std()
        
        # Limiti del nastro
        df_nat['upper_band'] = df_nat['inflation_food_price_index'] + df_nat['volatility']
        df_nat['lower_band'] = df_nat['inflation_food_price_index'] - df_nat['volatility']
        
        return df_nat.dropna(subset=['volatility'])

    def get_price_momentum(self, commodity_name: str, periods: int = 1) -> pd.DataFrame:
        """Variazione percentuale di prezzo (momentum) per una commodity."""
        df_comm = self.get_time_series(commodity_name)
        if df_comm.empty:
            return pd.DataFrame()
            
        df_nat = df_comm.groupby('date')[commodity_name].mean().reset_index()
        df_nat[f'{commodity_name}_momentum'] = df_nat[commodity_name].pct_change(periods=periods)
        return df_nat.dropna()

    def get_commodity_trends(self, commodities: List[str]) -> pd.DataFrame:
        """Estrae le serie storiche medie nazionali per una lista di commodity specifiche."""
        if self.data.empty:
            return pd.DataFrame()
            
        available_cols = [c for c in commodities if c in self.data.columns]
        if not available_cols:
            return pd.DataFrame()
            
        return self.data.groupby(['date'], observed=True)[available_cols].mean().reset_index()
