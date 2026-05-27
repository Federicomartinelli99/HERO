"""
hero_v2.domains.rainfall.domain
===============================
Implementazione del Domain Layer per i dati sulle precipitazioni (CHIRPS Rainfall).
"""

from typing import Dict, Any, List, Optional
from pathlib import Path
import pandas as pd
from hero_v2.core.base_domain import BaseDomainLayer
from hero_v2.core.logger import get_logger

logger = get_logger(__name__)

DEFAULT_RAINFALL_PATH = Path(__file__).resolve().parent.parent.parent.parent / "rainfall" / "data" / "clean_rainfall" / "rainfall_monthly.parquet"

class RainfallDomain(BaseDomainLayer):
    """
    Gestisce i dati sulle precipitazioni subnazionali per un singolo paese.
    Implementa BaseDomainLayer.
    """

    def __init__(self, iso3: str, file_path: Path = DEFAULT_RAINFALL_PATH) -> None:
        super().__init__(iso3)
        self.file_path = Path(file_path)

    def load_data(self) -> pd.DataFrame:
        """Carica i dati sulle precipitazioni per il paese ISO3 corrente dal Parquet consolidato."""
        if not self.file_path.exists():
            logger.error(f"File precipitazioni non trovato in {self.file_path}")
            return pd.DataFrame()

        try:
            # Carichiamo il DataFrame
            df = pd.read_parquet(self.file_path, engine="pyarrow")
            
            # Filtriamo per ISO3 del paese corrente
            self.data = df[df["ISO3"] == self.iso3.upper()].copy()

            if self.data.empty:
                logger.warning(f"Nessun dato sulle precipitazioni trovato per {self.iso3} nel file {self.file_path.name}")
            else:
                self.data["date"] = pd.to_datetime(self.data["date"])
                self.data = self.data.sort_values(by="date")
                logger.info(f"Dominio Rainfall caricato per {self.iso3}: {len(self.data)} record.")
        except Exception as e:
            logger.error(f"Errore durante il caricamento dei dati delle precipitazioni: {e}")
            self.data = pd.DataFrame()

        return self.data

    def get_time_series(self, metric: str, **kwargs) -> pd.DataFrame:
        """
        Estrae una serie temporale media nazionale per la metrica richiesta.
        
        Parameters
        ----------
        metric : str
            Colonna da estrarre (es. 'r1h', 'r1h_avg', 'r3h', 'rfq').
        """
        if self.data.empty:
            return pd.DataFrame()

        if metric not in self.data.columns:
            raise KeyError(f"Metrica '{metric}' non disponibile nel dataset delle precipitazioni.")

        # Aggreghiamo a livello nazionale (media per data)
        df_ts = self.data.groupby("date")[metric].mean().reset_index()
        return df_ts.dropna()

    def get_summary(self) -> Dict[str, Any]:
        """Restituisce statistiche descrittive del dominio Rainfall per il paese."""
        if self.data.empty:
            return {"status": "no_data"}
        
        return {
            "iso3": self.iso3,
            "total_records": len(self.data),
            "date_range": [str(self.data["date"].min().date()), str(self.data["date"].max().date())] if "date" in self.data.columns else None,
            "available_metrics": self.available_metrics,
            "avg_historical_rainfall": float(self.data["r1h"].mean()) if "r1h" in self.data.columns else None
        }

    @property
    def available_metrics(self) -> List[str]:
        """Restituisce l'elenco delle metriche disponibili nel dataset."""
        all_metrics = ["r1h", "r1h_avg", "r3h", "r3h_avg", "rfq", "r1q", "r3q"]
        if self.data.empty:
            return all_metrics
        return [m for m in all_metrics if m in self.data.columns]

    @property
    def domain_name(self) -> str:
        return "rainfall"

    # --- Metodi analitici specifici ---

    def get_seasonal_cycle(self, metric: str = "r1h") -> pd.DataFrame:
        """Calcola la climatologia mensile (ciclo stagionale storico) vs anno corrente."""
        if self.data.empty or metric not in self.data.columns:
            return pd.DataFrame()

        df = self.data.copy()
        df["month"] = df["date"].dt.month
        
        # Climatologia storica (media storica per ciascun mese dell'anno)
        climatology = df.groupby("month")[metric].mean().reset_index().rename(columns={metric: "historical_mean"})
        return climatology
