import os
import re
import logging
from pathlib import Path
import pandas as pd

def setup_logger(name: str, log_file: str = "pipeline.log") -> logging.Logger:
    """Configura un logger che scrive su console e su file nella cartella logs."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    if logger.handlers:
        return logger
        
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
        datefmt="%H:%M:%S"
    )
    
    # Handler per console
    c_handler = logging.StreamHandler()
    c_handler.setFormatter(formatter)
    logger.addHandler(c_handler)
    
    # Handler per file
    log_dir = Path(__file__).resolve().parent.parent.parent / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    f_handler = logging.FileHandler(log_dir / log_file, encoding="utf-8")
    f_handler.setFormatter(formatter)
    logger.addHandler(f_handler)
    
    return logger

def normalize_name(name: str) -> str:
    """Normalizza i nomi delle regioni per correggere differenze di spelling e rimuovere suffissi."""
    if not isinstance(name, str) or pd.isna(name):
        return ""
    
    name_clean = name.lower()
    # Rimuove caratteri speciali e punteggiatura
    name_clean = re.sub(r"[^a-z0-9\s]", "", name_clean)
    # Collassa spazi consecutivi
    name_clean = re.sub(r"\s+", " ", name_clean).strip()
    # Rimuove prefissi/articoli comuni
    name_clean = re.sub(r"\b(al|el|the)\b\s*", "", name_clean)
    # Rimuove suffissi comuni usati nelle tabelle IPC (IDP, IDPs, urban, rural, ecc.)
    name_clean = re.sub(r"\b(idps|idp|urban|rural|province|district|town|city|new|returning|returnees|refugees|refugies|anciens|nouveaux)\b", "", name_clean).strip()
    
    replacements = {
        # Yemen
        "alhodeidah": "alhudaydah",
        "hodeidah": "alhudaydah",
        "saada": "saadah",
        "sanaa": "sanaacity",
        "sanaacity": "sanaacity",
        "marib": "marib",
        "maib": "marib",
        "aldhalee": "addhalee",
        "addhalea": "addhalee",
        "addhali": "addhalee",
        "hadramawt": "hadramaut",
        # Afghanistan
        "hilmand": "helmand",
        "hirat": "herat",
        "nimroz": "nimruz",
        "panjsher": "panjshir",
        "sari pul": "saripul",
        "saripol": "saripul",
        # Nigeria
        "fct": "fctabuja",
        "abuja": "fctabuja",
        "nassarawa": "nasarawa",
        "zamfora": "zamfara",
    }
    return replacements.get(name_clean, name_clean)

