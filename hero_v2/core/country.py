"""
hero_v2.core.country
====================
Entita' Paese che funge da contenitore e registry per i diversi domini di dati.
"""

from typing import Dict, Any, List, Optional
from .base_domain import BaseDomainLayer
from .geo_registry import GeoRegistry

class Country:
    """
    Rappresenta un Paese (es. Yemen, Afghanistan) nel sistema HERO.
    Contiene un registro dei domini caricati (Food Prices, IPC, Rainfall, ecc.)
    permettendo analisi cross-dominio sul singolo paese.
    """

    def __init__(self, iso3: str, geo_registry: Optional[GeoRegistry] = None) -> None:
        self.iso3 = iso3.upper()
        
        # Recupero info geografiche dal registry
        registry = geo_registry or GeoRegistry()
        info = registry.get_country_info(self.iso3)
        
        if info:
            self.name = info["name"]
            self.region_name = info["region"]
            self.lat = info["lat"]
            self.lon = info["lon"]
        else:
            self.name = self.iso3
            self.region_name = "Unknown"
            self.lat = 0.0
            self.lon = 0.0

        self._domains: Dict[str, BaseDomainLayer] = {}

    def register_domain(self, domain: BaseDomainLayer) -> None:
        """Registra un layer di dominio tematico su questo paese."""
        if domain.iso3 != self.iso3:
            raise ValueError(f"Impossibile registrare il dominio per {domain.iso3} su un paese configurato come {self.iso3}")
        self._domains[domain.domain_name] = domain

    def get_domain(self, domain_name: str) -> BaseDomainLayer:
        """Recupera un layer di dominio registrato."""
        if domain_name not in self._domains:
            raise KeyError(f"Dominio '{domain_name}' non registrato per il paese {self.iso3}")
        return self._domains[domain_name]

    def has_domain(self, domain_name: str) -> bool:
        """Verifica se un dominio e' registrato per questo paese."""
        return domain_name in self._domains

    @property
    def registered_domains(self) -> List[str]:
        """Elenco dei domini attualmente registrati per il paese."""
        return list(self._domains.keys())

    def __repr__(self) -> str:
        return f"<Country {self.name} ({self.iso3}) | Domains: {self.registered_domains}>"
