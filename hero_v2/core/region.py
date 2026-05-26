"""
hero_v2.core.region
====================
Entita' Regione che raggruppa piu' Paesi e permette analisi comparative regionali.
"""

from typing import Dict, List, Optional
import pandas as pd
from .country import Country
from .geo_registry import GeoRegistry

class Region:
    """
    Rappresenta una macro-regione (es. Horn of Africa, East Africa) in HERO.
    Raggruppa le istanze di Country e facilita estrazioni ed analisi aggregate.
    """

    def __init__(self, name: str, countries_iso3: Optional[List[str]] = None, geo_registry: Optional[GeoRegistry] = None) -> None:
        self.name = name
        self.geo_registry = geo_registry or GeoRegistry()
        
        # Se non passata esplicitamente, proviamo a trovare i paesi per questa regione dal registry
        if countries_iso3 is None:
            countries_iso3 = self.geo_registry.get_countries_in_region(name)
            
        self.countries: Dict[str, Country] = {}
        for iso3 in countries_iso3:
            self.countries[iso3.upper()] = Country(iso3, self.geo_registry)

    def add_country(self, country: Country) -> None:
        """Aggiunge un paese all'anagrafica della regione."""
        self.countries[country.iso3] = country

    def get_country(self, iso3: str) -> Country:
        """Restituisce l'istanza Country dal codice ISO3."""
        return self.countries[iso3.upper()]

    def get_comparative_panel(self, domain_name: str, metric: str, **kwargs) -> pd.DataFrame:
        """
        Estrae e concatena le serie storiche per una data metrica e dominio
        da tutti i paesi all'interno della regione che supportano tale dominio.

        Returns
        -------
        pd.DataFrame
            Un DataFrame "long" contenente i dati di tutti i paesi con colonne:
            - 'country' (nome paese o ISO3)
            - 'date' o le colonne temporali
            - la metrica richiesta
        """
        frames = []
        for iso3, country in self.countries.items():
            if country.has_domain(domain_name):
                try:
                    domain_layer = country.get_domain(domain_name)
                    df_ts = domain_layer.get_time_series(metric, **kwargs)
                    if not df_ts.empty:
                        df_ts = df_ts.copy()
                        df_ts["country"] = country.name
                        df_ts["ISO3"] = country.iso3
                        frames.append(df_ts)
                except Exception as e:
                    # Se fallisce per un paese, continuiamo con gli altri
                    pass

        if not frames:
            return pd.DataFrame()
            
        return pd.concat(frames, ignore_index=True)

    def __repr__(self) -> str:
        return f"<Region {self.name} | Countries: {list(self.countries.keys())}>"
