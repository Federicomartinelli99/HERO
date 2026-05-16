import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Union
from libs.country_entity import CountryEntity
from libs.logger_config import get_logger
from libs.data_schemas import WFPDataSchema

logger = get_logger(__name__)

class MultiCountryManager:
    def __init__(self, parquet_path: Union[str, Path]):
        self.parquet_path: Path = Path(parquet_path)
        self._countries_registry: Dict[str, CountryEntity] = {}
        self._global_df: Optional[pd.DataFrame] = None
        self._iso3_to_name: Dict[str, str] = {}

    def initialize_pipeline(self) -> "MultiCountryManager":
        if not self.parquet_path.exists():
            logger.error(f"File consolidato assente in {self.parquet_path}")
            raise FileNotFoundError("Eseguire wfp_to_parquet.py prima di avviare l'analisi.")
            
        logger.info(f"Caricamento rapido Parquet: {self.parquet_path.name}")
        self._global_df = pd.read_parquet(self.parquet_path, engine='pyarrow')
        
        # --- DATA VALIDATION ---
        if WFPDataSchema is not None:
            logger.info("Avvio validazione dello schema dati (Pandera Data Contract)...")
            try:
                self._global_df = WFPDataSchema.validate(self._global_df)
                logger.info("✅ Validazione schema superata.")
            except Exception as e:
                logger.error(f"❌ Errore critico di validazione schema: {e}")
                raise
        else:
            logger.warning("Validazione schema saltata (Pandera non attivo).")
        
        # INVECE DI ISTANZIARE SUBITO TUTTI I PAESI: Creiamo solo un dizionario ISO3 -> Nome
        logger.info("Costruzione mappa dei mercati per Lazy Loading...")
        unique_countries = self._global_df[['ISO3', 'country']].drop_duplicates().dropna()
        self._iso3_to_name = dict(zip(unique_countries['ISO3'], unique_countries['country']))
        
        logger.info(f"✅ Inizializzazione completata! {len(self._iso3_to_name)} paesi pronti per il caricamento on-demand.")
            
        return self

    def get_country(self, iso3: str) -> CountryEntity:
        """
        Recupera l'Entità Paese. Utilizza il pattern Lazy Loading: 
        istanzia la classe e filtra i dati globali SOLO la prima volta che viene richiesta.
        """
        if iso3 not in self._countries_registry:
            if iso3 not in self._iso3_to_name:
                logger.error(f"Richiesto ISO3 non valido: {iso3}")
                raise KeyError(f"Paese {iso3} non presente nel registro/dataset.")
            
            # --- LAZY LOADING ---
            logger.info(f"Istanziazione Lazy (on-demand) per il paese: {iso3}...")
            name = self._iso3_to_name[iso3]
            self._countries_registry[iso3] = CountryEntity(iso3=iso3, name=name, country_data=self._global_df)
            
        return self._countries_registry[iso3]

    def get_comparative_inflation_panel(self, iso3_list: List[str]) -> pd.DataFrame:
        panels = []
        for iso3 in iso3_list:
            try:
                df_inf = self.get_country(iso3).get_inflation_series()
                if not df_inf.empty:
                    df_national = df_inf.groupby(['ISO3', 'country', 'date'])['inflation_food_price_index'].mean().reset_index()
                    panels.append(df_national)
            except KeyError:
                continue
        return pd.concat(panels, ignore_index=True) if panels else pd.DataFrame()

    def get_comparative_commodity_panel(self, commodity_name: str, iso3_list: List[str]) -> pd.DataFrame:
        panels = []
        for iso3 in iso3_list:
            try:
                country_entity = self.get_country(iso3)
                if commodity_name in country_entity.available_commodities:
                    panels.append(country_entity.get_commodity_series(commodity_name))
            except (KeyError, ValueError):
                continue
        return pd.concat(panels, ignore_index=True) if panels else pd.DataFrame()
