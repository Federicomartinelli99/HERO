import os
import sys
import logging
import requests
import zipfile
from pathlib import Path
from typing import Optional, Tuple, Dict, List

# Setup standard logger
def get_logger(name: str, log_file: str = "boundaries_downloader.log") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # File handler
        log_dir = Path(__file__).resolve().parent.parent.parent / "data" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_dir / log_file, encoding='utf-8')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        
        # Console handler
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(formatter)
        logger.addHandler(ch)
    return logger

logger = get_logger("hdx_boundaries_loader")

CKAN_BASE = "https://data.humdata.org/api/3/action"
DEFAULT_RAW_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "boundaries"

class HDXBoundariesLoader:
    """Scarica i confini amministrativi da HDX COD-AB (GeoJSON o ZIP) e li estrae se necessario."""

    def __init__(self, raw_dir: Path = DEFAULT_RAW_DIR, timeout: int = 300) -> None:
        self.raw_dir = Path(raw_dir)
        self.timeout = timeout
        self._session = requests.Session()

    def fetch(self, iso3: str) -> Optional[Path]:
        """Scarica e unzippa i confini per un dato paese (ISO3)."""
        iso3 = iso3.upper()
        discovered = self._discover_resource(iso3)
        if discovered is None:
            return None
        
        url, filename = discovered
        out_dir = self.raw_dir / iso3.lower()
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / filename

        # 1. Controllo cache: se la cartella contiene già file geojson o shp, saltiamo
        # A volte il file scaricato ha un nome diverso da quello estratti. Quindi controlliamo
        # se c'è già materiale nella cartella del paese.
        existing_geojson = list(out_dir.glob("*.geojson"))
        existing_shp = list(out_dir.glob("*.shp"))
        if (existing_geojson or existing_shp) and out_path.exists():
            logger.info(f"[{iso3}] Confini già presenti in locale, salto download -> {out_dir}")
            return out_dir

        # 2. Download
        logger.info(f"[{iso3}] Download risorsa in corso: {filename} da {url}")
        try:
            resp = self._session.get(url, stream=True, timeout=self.timeout)
            resp.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            logger.info(f"[{iso3}] File salvato -> {out_path}")
            
            # 3. Unzip se è un file zip
            if filename.lower().endswith(".zip"):
                self._unzip_file(out_path, out_dir, iso3)
                
            return out_dir
        except Exception as e:
            logger.error(f"[{iso3}] Errore durante il download o estrazione: {e}")
            return None

    def fetch_many(self, iso3_list: List[str]) -> Dict[str, Optional[Path]]:
        """Scarica i confini per una lista di paesi in parallelo/sequenza."""
        return {iso3.upper(): self.fetch(iso3) for iso3 in iso3_list}

    def _unzip_file(self, zip_path: Path, extract_to: Path, iso3: str):
        """Estrae l'archivio zip e cancella il file zip originale per fare pulizia."""
        logger.info(f"[{iso3}] Estrazione dell'archivio zip in corso -> {extract_to}")
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_to)
            logger.info(f"[{iso3}] Estrazione completata con successo.")
            
            # Rimuoviamo il file zip per non sprecare spazio se l'estrazione è andata a buon fine
            os.remove(zip_path)
            logger.info(f"[{iso3}] File ZIP originale rimosso: {zip_path.name}")
        except Exception as e:
            logger.error(f"[{iso3}] Errore durante l'estrazione del file zip: {e}")

    def _discover_resource(self, iso3: str) -> Optional[Tuple[str, str]]:
        """Interroga l'API CKAN di HDX per trovare l'URL del dataset cod-ab-{iso3}."""
        slug = f"cod-ab-{iso3.lower()}"
        api_url = f"{CKAN_BASE}/package_show?id={slug}"
        try:
            resp = self._session.get(api_url, timeout=30)
            if not resp.ok:
                logger.error(f"[{iso3}] Dataset {slug} non trovato (HTTP {resp.status_code})")
                return None
                
            payload = resp.json()
            if not payload.get("success"):
                logger.error(f"[{iso3}] Errore risposta CKAN API")
                return None
            
            resources = payload["result"]["resources"]
            geojson_resource = None
            zip_resource = None

            for r in resources:
                fmt = r.get("format", "").upper()
                name = r.get("name", "")
                url = r.get("url", "")
                
                # Priorità 1: GeoJSON
                if fmt == "GEOJSON":
                    geojson_resource = (url, name)
                # Priorità 2: ZIP o Shapefile
                elif "ZIP" in fmt or "SHP" in fmt or "SHAPEFILE" in fmt or name.lower().endswith(".zip"):
                    zip_resource = (url, name)

            if geojson_resource:
                return geojson_resource
            if zip_resource:
                logger.warning(f"[{iso3}] Nessun file GeoJSON trovato direttamente. Utilizzo archivio ZIP/Shapefile come fallback.")
                return zip_resource
                
            logger.error(f"[{iso3}] Nessun formato compatibile (GeoJSON o ZIP) trovato nel dataset {slug}")
            return None
        except Exception as e:
            logger.error(f"[{iso3}] Errore durante la ricerca della risorsa: {e}")
            return None
