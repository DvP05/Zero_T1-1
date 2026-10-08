"""
==============================================================================
4. NASA EARTHDATA COLLECTOR (FREE with registration)
==============================================================================
Searches NASA's CMR (Common Metadata Repository) for flood-relevant datasets.

Key datasets:
  - GPM IMERG: Global precipitation (30-min, near real-time)
  - SMAP: Soil moisture (flood precursor)
  - MODIS NRT Flood Map: Active flood detection
  - ASTER GDEM / SRTM: Digital elevation models
  - Landsat: Long-term coastal change detection

Registration: https://urs.earthdata.nasa.gov/ (FREE)
Recommended library: pip install earthaccess
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import requests
import pandas as pd

from .config import (
    COASTAL_ZONES,
    NASA_EARTHDATA_USERNAME,
    NASA_EARTHDATA_PASSWORD,
    ENDPOINTS,
    RAW_DATA_DIR,
    CoastalZone,
)


class NASAEarthdataCollector:
    """
    Searches NASA CMR for flood-relevant Earth science datasets.
    For actual data download, use the `earthaccess` library (recommended).
    """

    # Key dataset short names for flood intelligence
    DATASETS = {
        "GPM_3IMERGHH": {
            "name": "GPM IMERG Half-Hourly Precipitation",
            "description": "Global precipitation at 0.1 deg, every 30 min",
            "use": "Real-time rainfall intensity for flood prediction",
        },
        "SPL3SMP": {
            "name": "SMAP L3 Soil Moisture",
            "description": "Global soil moisture at 9km, daily",
            "use": "Soil saturation as flood precursor",
        },
        "MCD64A1": {
            "name": "MODIS Burned Area / Land Change",
            "description": "Monthly land surface change",
            "use": "Detect land cover changes affecting runoff",
        },
        "ASTGTMV003": {
            "name": "ASTER Global DEM v3",
            "description": "30m digital elevation model",
            "use": "Elevation data for flood modeling",
        },
    }

    def __init__(self):
        self.cmr_url = ENDPOINTS["nasa_cmr"]
        self.session = requests.Session()
        self._use_earthaccess = False
        self._try_init_earthaccess()

    def _try_init_earthaccess(self):
        """Try to initialize earthaccess library for authenticated downloads."""
        try:
            import earthaccess
            if NASA_EARTHDATA_USERNAME and NASA_EARTHDATA_PASSWORD:
                os.environ["EARTHDATA_USERNAME"] = NASA_EARTHDATA_USERNAME
                os.environ["EARTHDATA_PASSWORD"] = NASA_EARTHDATA_PASSWORD
                earthaccess.login(
                    strategy="environment",
                )
                self._use_earthaccess = True
                print("  [NASA] Authenticated via earthaccess library.")
            else:
                print("  [NASA] No credentials. Using unauthenticated CMR search only.")
        except ImportError:
            print("  [NASA] earthaccess not installed. Using direct CMR API.")
            print("         Install with: pip install earthaccess")

    def search_datasets(
        self,
        keyword: str = "precipitation flood",
        bbox: Optional[Tuple[float, float, float, float]] = None,
        max_results: int = 10,
    ) -> List[Dict]:
        """
        Search NASA CMR for datasets matching a keyword.

        Args:
            keyword: Search term (e.g., "precipitation", "soil moisture", "flood")
            bbox: Bounding box (min_lon, min_lat, max_lon, max_lat)
            max_results: Number of results
        """
        params = {
            "keyword": keyword,
            "page_size": max_results,
            }

        if bbox:
            params["bounding_box"] = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"

        url = f"{self.cmr_url}/collections.json"
        print(f"  [NASA CMR] Searching for: '{keyword}'...")

        resp = self.session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        entries = data.get("feed", {}).get("entry", [])
        results = []
        for entry in entries:
            results.append({
                "id": entry.get("id"),
                "short_name": entry.get("short_name"),
                "title": entry.get("title"),
                "summary": entry.get("summary", "")[:200],
                "time_start": entry.get("time_start"),
                "time_end": entry.get("time_end"),
                "data_center": entry.get("data_center"),
            })

        print(f"    -> Found {len(results)} datasets")
        return results

    def search_granules(
        self,
        short_name: str,
        zone: CoastalZone,
        days_back: int = 7,
        max_results: int = 10,
    ) -> List[Dict]:
        if isinstance(zone, str):
            zone = COASTAL_ZONES[zone.lower()]
        """
        Search for data granules (files) within a specific dataset.

        Args:
            short_name: Dataset short name (e.g., "GPM_3IMERGHH")
            zone: Coastal zone with bounding box
            days_back: How many days back to search
            max_results: Maximum granules to return
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days_back)

        params = {
            "short_name": short_name,
            "bounding_box": f"{zone.bbox[0]},{zone.bbox[1]},{zone.bbox[2]},{zone.bbox[3]}",
            "sort_key[]": "-start_date",
            "page_size": max_results,
        }

        url = f"{self.cmr_url}/granules.json"
        print(f"  [NASA CMR] Searching granules for {short_name} over {zone.name}...")

        resp = self.session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        entries = data.get("feed", {}).get("entry", [])
        results = []
        for entry in entries:
            # Extract download links
            links = entry.get("links", [])
            download_url = None
            for link in links:
                if link.get("rel") == "http://esipfed.org/ns/fedsearch/1.1/data#":
                    download_url = link.get("href")
                    break

            results.append({
                "id": entry.get("id"),
                "title": entry.get("title"),
                "time_start": entry.get("time_start"),
                "time_end": entry.get("time_end"),
                "granule_size": entry.get("granule_size"),
                "download_url": download_url,
            })

        print(f"    -> Found {len(results)} granules")
        return results

    def search_all_flood_datasets(
        self,
        zone: CoastalZone,
        days_back: int = 7,
        save: bool = True,
    ) -> Dict[str, List[Dict]]:
        if isinstance(zone, str):
            zone = COASTAL_ZONES[zone.lower()]
        """Search all flood-relevant datasets for a coastal zone."""
        results = {}
        for short_name, info in self.DATASETS.items():
            print(f"\n  --- {info['name']} ---")
            print(f"      Use: {info['use']}")
            granules = self.search_granules(
                short_name=short_name,
                zone=zone,
                days_back=days_back,
                max_results=5,
            )
            results[short_name] = granules

        if save:
            out_dir = os.path.join(RAW_DATA_DIR, "nasa_earthdata", zone.name.lower())
            os.makedirs(out_dir, exist_ok=True)
            with open(os.path.join(out_dir, "granule_search.json"), "w") as f:
                json.dump(results, f, indent=2, default=str)
            print(f"\n  -> Saved search results to {out_dir}/")

        return results

    def download_with_earthaccess(
        self,
        short_name: str,
        zone: CoastalZone,
        days_back: int = 7,
        max_results: int = 3,
        output_dir: Optional[str] = None,
    ) -> List[str]:
        """
        Download actual data files using the earthaccess library.
        Requires: pip install earthaccess + NASA Earthdata account.
        """
        try:
            import earthaccess
        except ImportError:
            print("  [NASA] earthaccess not installed. Run: pip install earthaccess")
            return []

        if output_dir is None:
            output_dir = os.path.join(RAW_DATA_DIR, "nasa_earthdata", "downloads")
        os.makedirs(output_dir, exist_ok=True)

        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days_back)

        print(f"  [earthaccess] Searching & downloading {short_name}...")
        results = earthaccess.search_data(
            short_name=short_name,
            bounding_box=zone.bbox,
            temporal=(start_date, end_date),
            count=max_results,
        )

        if not results:
            print("    -> No results found.")
            return []

        files = earthaccess.download(results, output_dir)
        print(f"    -> Downloaded {len(files)} files to {output_dir}")
        return files


if __name__ == "__main__":
    collector = NASAEarthdataCollector()
    zone = COASTAL_ZONES["mumbai"]

    # Search CMR (no auth needed)
    results = collector.search_all_flood_datasets(zone, days_back=7)
    for ds, granules in results.items():
        print(f"\n=== {ds} ===")
        for g in granules[:2]:
            print(f"  {g['title']} | {g['time_start']}")