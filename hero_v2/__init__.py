"""
H.E.R.O. v2 — Humanitarian Emergency Response Observatory
==========================================================

Architettura modulare multi-dominio per l'analisi integrata di:
  - Food Prices (WFP Global Real-Time Food Prices)
  - IPC (Integrated Food Security Phase Classification)
  - Rainfall (CHIRPS subnational dekadal precipitation)

Ogni dominio implementa ``core.BaseDomainLayer`` e si registra su
un ``core.Country``, consentendo analisi cross-dominio per paese.

Quickstart
----------
>>> from hero_v2.core import Country, Region, GeoRegistry
>>> from hero_v2.domains.food_prices import FoodPricesDomain, FoodPricesManager
>>> from hero_v2.domains.ipc import IPCDomain
>>> from hero_v2.domains.rainfall import RainfallDomain
"""

from hero_v2.core.country import Country
from hero_v2.core.region import Region
from hero_v2.core.geo_registry import GeoRegistry
from hero_v2.core.base_plotter import BasePlotter
from hero_v2.core.logger import get_logger

__version__ = "2.0.0"

__all__ = [
    "Country",
    "Region",
    "GeoRegistry",
    "BasePlotter",
    "get_logger",
]
