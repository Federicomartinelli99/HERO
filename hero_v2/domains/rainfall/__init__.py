"""
hero_v2.domains.rainfall
========================
Moduli per l'analisi delle precipitazioni (CHIRPS Rainfall).
"""

from .domain import RainfallDomain
from .plots import RainfallPlotter

__all__ = [
    "RainfallDomain",
    "RainfallPlotter",
]
