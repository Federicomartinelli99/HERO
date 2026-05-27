"""
hero_v2.core.geo_registry
==========================
Gestore delle anagrafiche geografiche dei paesi e delle macro-regioni.
"""

from typing import Dict, List, Optional
from pathlib import Path
import json

# Mappatura predefinita ISO3 -> Dettagli Paese
DEFAULT_REGISTRY = {
    "YEM": {"name": "Yemen", "region": "Middle East & North Africa", "lat": 15.552727, "lon": 48.516388},
    "AFG": {"name": "Afghanistan", "region": "South Asia", "lat": 33.93911, "lon": 67.709953},
    "NGA": {"name": "Nigeria", "region": "West Africa", "lat": 9.082012, "lon": 8.675277},
    "SOM": {"name": "Somalia", "region": "Horn of Africa", "lat": 5.152149, "lon": 46.199616},
    "ETH": {"name": "Ethiopia", "region": "Horn of Africa", "lat": 9.145, "lon": 40.489673},
    "KEN": {"name": "Kenya", "region": "Horn of Africa", "lat": -0.023559, "lon": 37.906193},
    "SDN": {"name": "Sudan", "region": "East Africa", "lat": 12.862807, "lon": 30.217636},
    "SSD": {"name": "South Sudan", "region": "East Africa", "lat": 6.876991, "lon": 31.306979},
    "COD": {"name": "Democratic Republic of the Congo", "region": "Central Africa", "lat": -4.038333, "lon": 21.758664},
    "SYR": {"name": "Syria", "region": "Middle East & North Africa", "lat": 34.802075, "lon": 38.996815},
}

class GeoRegistry:
    """Registry geografico configurabile e interrogabile."""
    
    def __init__(self, custom_registry_path: Optional[Path] = None) -> None:
        self.registry = DEFAULT_REGISTRY.copy()
        if custom_registry_path and custom_registry_path.exists():
            try:
                with open(custom_registry_path, "r", encoding="utf-8") as f:
                    custom_data = json.load(f)
                    self.registry.update(custom_data)
            except Exception as e:
                # Se c'è un errore logghiamo ma continuiamo con quello di default
                pass

    def get_country_info(self, iso3: str) -> Optional[dict]:
        """Restituisce informazioni su un paese dato il codice ISO3."""
        return self.registry.get(iso3.upper())

    def get_countries_in_region(self, region_name: str) -> List[str]:
        """Restituisce la lista di codici ISO3 appartenenti a una macro-regione."""
        return [
            iso3 for iso3, info in self.registry.items()
            if info["region"].lower() == region_name.lower()
        ]

    def get_all_regions(self) -> List[str]:
        """Restituisce l'elenco di tutte le macro-regioni uniche definite."""
        return list(set(info["region"] for info in self.registry.values()))

    def get_all_countries(self) -> Dict[str, str]:
        """Restituisce un dizionario ISO3 -> Country Name."""
        return {iso3: info["name"] for iso3, info in self.registry.items()}
