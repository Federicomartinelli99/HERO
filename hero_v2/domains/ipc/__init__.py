"""
hero_v2.domains.ipc
===================
Moduli per l'analisi dell'insicurezza alimentare (IPC).
"""

from .domain import IPCDomain
from .plots import IpcPlotter

__all__ = [
    "IPCDomain",
    "IpcPlotter",
]
