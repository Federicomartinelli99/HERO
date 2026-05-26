"""
hero_v2.core.base_domain
========================
Classe base astratta (ABC) per i diversi domini tematici di HERO (Food Prices, IPC, Rainfall, ecc.).
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import pandas as pd

class BaseDomainLayer(ABC):
    """
    Contratto che ogni dataset tematico (domain) deve implementare per integrarsi nel Paese e nella Regione.
    """

    def __init__(self, iso3: str) -> None:
        self.iso3 = iso3.upper()
        self.data: pd.DataFrame = pd.DataFrame()

    @abstractmethod
    def load_data(self) -> pd.DataFrame:
        """
        Carica i dati specifici del dominio per il paese ISO3 corrente.
        Popola self.data e restituisce il DataFrame.
        """
        pass

    @abstractmethod
    def get_time_series(self, metric: str, **kwargs) -> pd.DataFrame:
        """
        Restituisce una serie temporale per una metrica specifica del dominio.
        Deve restituire un DataFrame con almeno le colonne:
          - 'date' o 'year'/'month'
          - la metrica richiesta
        """
        pass

    @abstractmethod
    def get_summary(self) -> Dict[str, Any]:
        """
        Restituisce un dizionario con statistiche descrittive riassuntive del dominio per il paese.
        """
        pass

    @property
    @abstractmethod
    def available_metrics(self) -> List[str]:
        """
        Restituisce l'elenco delle metriche analizzabili/estraibili per questo dominio.
        """
        pass

    @property
    @abstractmethod
    def domain_name(self) -> str:
        """
        Restituisce il nome identificativo del dominio (es. 'food_prices', 'rainfall', 'ipc').
        """
        pass
