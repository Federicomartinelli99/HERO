"""
hero_v2.core.logger
====================
Logger centralizzato per l'intero progetto H.E.R.O.

Ogni modulo chiama ``get_logger(__name__)`` per ottenere un logger
con output sia a console sia su file rotante. Il file di log viene
salvato nella directory ``logs/`` relativa alla radice del progetto.

Esempio
-------
>>> from hero_v2.core.logger import get_logger
>>> logger = get_logger(__name__)
>>> logger.info("Pipeline avviata")
"""

import logging
import sys
from pathlib import Path

# Directory di log: HERO/hero_v2/logs/
_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Restituisce un logger configurato con handler console + file.

    Se il logger ha gia' handler configurati (chiamata ripetuta),
    viene restituito cosi' com'e' per evitare duplicazioni.

    Parameters
    ----------
    name : str
        Nome del logger (tipicamente ``__name__`` del modulo chiamante).
    level : int, optional
        Livello minimo di logging (default: ``logging.INFO``).

    Returns
    -------
    logging.Logger
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(level)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(name)-30s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # --- Console handler ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # --- File handler ---
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(
        _LOG_DIR / "hero_pipeline.log",
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
