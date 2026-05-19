"""
Minimalistic HDX COD-AB admin boundaries loader.

For each ISO3, downloads the GeoJSON resource from
https://data.humdata.org/dataset/cod-ab-{iso3}
into rainfall/data/raw_boundaries/{iso3}/.
"""
from pathlib import Path
from typing import Optional

import requests

from libs.logger_config import get_logger

logger = get_logger("hdx_boundaries_loader")

CKAN_BASE       = "https://data.humdata.org/api/3/action"
DEFAULT_RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw_boundaries"


class HDXBoundariesLoader:
    """Fetches the GeoJSON admin-boundary resource from HDX COD-AB datasets."""

    def __init__(
        self,
        raw_dir: Path = DEFAULT_RAW_DIR,
        timeout: int = 300,
    ) -> None:
        self.raw_dir = Path(raw_dir)
        self.timeout = timeout
        self._session = requests.Session()

    def fetch(self, iso3: str) -> Optional[Path]:
        """Download the GeoJSON resource for one country. Returns the output path or None."""
        iso3 = iso3.upper()
        discovered = self._discover_geojson(iso3)
        if discovered is None:
            return None
        url, filename = discovered

        out_dir = self.raw_dir / iso3.lower()
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / filename

        logger.info(f"[{iso3}] Downloading {filename}")
        resp = self._session.get(url, stream=True, timeout=self.timeout)
        resp.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        logger.info(f"[{iso3}] Saved -> {out_path}")
        return out_path

    def fetch_many(self, iso3_list: list[str]) -> dict[str, Optional[Path]]:
        return {iso3.upper(): self.fetch(iso3) for iso3 in iso3_list}

    def _discover_geojson(self, iso3: str) -> Optional[tuple[str, str]]:
        """Query CKAN package_show; return (download_url, filename) for the GeoJSON resource."""
        slug = f"cod-ab-{iso3.lower()}"
        resp = self._session.get(f"{CKAN_BASE}/package_show?id={slug}", timeout=30)
        if not resp.ok:
            logger.error(f"[{iso3}] Dataset {slug} not found (HTTP {resp.status_code})")
            return None
        payload = resp.json()
        if not payload.get("success"):
            logger.error(f"[{iso3}] CKAN API error")
            return None
        for r in payload["result"]["resources"]:
            if r.get("format", "").upper() == "GEOJSON":
                return r["url"], r["name"]
        logger.error(f"[{iso3}] No GeoJSON resource present in {slug}")
        return None
