"""
hero_v2.domains.ipc.domain
==========================
Implementazione del Domain Layer per i dati IPC (Integrated Food Security Phase Classification).
"""

from typing import Dict, Any, List, Optional
from pathlib import Path
import pandas as pd
from hero_v2.core.base_domain import BaseDomainLayer
from hero_v2.core.logger import get_logger

logger = get_logger(__name__)

DEFAULT_IPC_PATH = Path(__file__).resolve().parent.parent.parent.parent / "ipc" / "ipc_global_area_long_pcoded.csv"

class IPCDomain(BaseDomainLayer):
    """
    Gestisce i dati IPC per un singolo paese.
    Implementa BaseDomainLayer.
    """

    def __init__(self, iso3: str, file_path: Path = DEFAULT_IPC_PATH) -> None:
        super().__init__(iso3)
        self.file_path = Path(file_path)

    def load_data(self) -> pd.DataFrame:
        """Carica i dati IPC per il paese ISO3 corrente dal CSV globale."""
        if not self.file_path.exists():
            logger.error(f"File IPC non trovato in {self.file_path}")
            return pd.DataFrame()

        try:
            df = pd.read_csv(self.file_path)
            
            # Filtriamo per paese. Nel CSV IPC la colonna e' 'Country', e i valori possono essere nomi o codici ISO3.
            # Mappiamo i nomi comuni noti all'ISO3 per sicurezza.
            country_mapping = {
                "AFG": "Afghanistan",
                "YEM": "Yemen",
                "NGA": "Nigeria",
                "SOM": "Somalia",
                "ETH": "Ethiopia",
                "KEN": "Kenya",
                "SDN": "Sudan",
                "SSD": "South Sudan",
                "COD": "Democratic Republic of the Congo",
                "SYR": "Syria"
            }
            target_name = country_mapping.get(self.iso3, self.iso3).lower()
            
            df_filtered = df[
                (df["Country"].str.lower() == target_name) | 
                (df["Country"].str.lower() == self.iso3.lower())
            ].copy()

            if df_filtered.empty:
                logger.warning(f"Nessun dato IPC trovato per {self.iso3} nel file {self.file_path.name}")
                self.data = pd.DataFrame()
            else:
                # Converte le date
                df_filtered["date"] = pd.to_datetime(df_filtered["From"], format="%d/%m/%Y", errors="coerce")
                self.data = df_filtered.sort_values(by="date")
                logger.info(f"Dominio IPC caricato per {self.iso3}: {len(self.data)} record.")
        except Exception as e:
            logger.error(f"Errore durante il caricamento dei dati IPC: {e}")
            self.data = pd.DataFrame()

        return self.data

    def get_time_series(self, metric: str, validity_period: str = "current", **kwargs) -> pd.DataFrame:
        """
        Restituisce la serie temporale per una metrica IPC (es. popolazione in Phase 3+).
        
        Parameters
        ----------
        metric : str
            La metrica richiesta (es. 'Number', 'Percentage').
        validity_period : str
            Il tipo di stima: 'current', 'first projection', o 'second projection'.
        """
        if self.data.empty:
            return pd.DataFrame()

        df = self.data[self.data["Validity period"].str.lower() == validity_period.lower()].copy()
        if df.empty:
            return pd.DataFrame()

        # Aggreghiamo a livello nazionale per data e fase
        df_agg = df.groupby(["date", "Phase"])[[metric]].sum().reset_index()
        
        # Facciamo pivot sulle fasi per avere colonne separate per ciascuna fase
        df_pivot = df_agg.pivot(index="date", columns="Phase", values=metric).reset_index()
        df_pivot.columns.name = None
        
        return df_pivot

    def get_summary(self) -> Dict[str, Any]:
        """Restituisce statistiche descrittive del dominio IPC per il paese."""
        if self.data.empty:
            return {"status": "no_data"}
        
        latest_date = self.data["date"].max()
        df_latest = self.data[(self.data["date"] == latest_date) & (self.data["Validity period"] == "current")]
        
        total_pop = df_latest["Total country population"].iloc[0] if not df_latest.empty else "N/D"
        
        return {
            "iso3": self.iso3,
            "total_records": len(self.data),
            "latest_analysis_date": str(latest_date.date()) if pd.notna(latest_date) else None,
            "total_population": total_pop,
            "available_phases": list(self.data["Phase"].unique()) if "Phase" in self.data.columns else []
        }

    @property
    def available_metrics(self) -> List[str]:
        return ["Number", "Percentage"]

    @property
    def domain_name(self) -> str:
        return "ipc"
