"""
==============================================================================
3. COPERNICUS SENTINEL SATELLITE COLLECTOR (FREE with registration)
==============================================================================
Searches & downloads Sentinel satellite imagery via the Copernicus Data
Space Ecosystem (CDSE) STAC API.

Relevant collections for flood intelligence:
  - Sentinel-1 (SAR): Flood extent mapping (works through clouds!)
  - Sentinel-2 (Optical): Coastal land use, vegetation, water bodies
  - Sentinel-3 (Ocean): Sea surface temperature, ocean color

Registration: https://dataspace.copernicus.eu/ (FREE)
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests
import pandas as pd

from .config import (
    COASTAL_ZONES,
    COPERNICUS_DATASPACE_USERNAME,
    COPERNICUS_DATASPACE_PASSWORD,
    ENDPOINTS,
    RAW_DATA_DIR,
    CoastalZone,
)


class CopernicusSentinelCollector:
    """
    Searches Sentinel satellite data via the Copernicus STAC API.
    Downloads metadata and thumbnail previews for the hackathon demo.
    Full image download requires authentication.
    """

    # Relevant Sentinel collections for flood monitoring
    COLLECTIONS = {
        "sentinel-1-grd": "Sentinel-1 SAR GRD (flood extent through clouds)",
        "sentinel-2-l2a": "Sentinel-2 L2A (optical, land/water classification)",
    }

    def __init__(self):
        self.stac_url = ENDPOINTS["copernicus_stac"]
        self.session = requests.Session()
        self._token = None

    def _get_auth_token(self) -> Optional[str]:
        """Get OAuth2 token for Copernicus Data Space (needed for downloads)."""
        if not COPERNICUS_DATASPACE_USERNAME or not COPERNICUS_DATASPACE_PASSWORD:
            print("  [Copernicus] WARNING: No credentials set. Search works, downloads won't.")
            return None

        token_url = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
        resp = self.session.post(token_url, data={
            "grant_type": "password",
            "username": COPERNICUS_DATASPACE_USERNAME,
            "password": COPERNICUS_DATASPACE_PASSWORD,
            "client_id": "cdse-public",
        })
        resp.raise_for_status()
        self._token = resp.json()["access_token"]
        print("  [Copernicus] Authentication successful.")
        return self._token

    def search_imagery(
        self,
        zone: CoastalZone,
        collection: str = "sentinel-1-grd",
        days_back: int = 30,
        max_items: int = 10,
        max_cloud_cover: float = 50.0,
    ) -> List[Dict]:
        """
        Search for satellite imagery over a coastal zone using STAC API.

        Args:
            zone: Target coastal zone
            collection: Sentinel collection ID
            days_back: How many days back to search
            max_items: Maximum results to return
            max_cloud_cover: Max cloud cover % (only for optical like S2)

        Returns:
            List of STAC item metadata dicts
        """
        if isinstance(zone, str):
            zone = COASTAL_ZONES[zone.lower()]
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days_back)

        search_body = {
            "collections": [collection],
            "bbox": list(zone.bbox),
            "datetime": f"{start_date.isoformat()}Z/{end_date.isoformat()}Z",
            "limit": max_items,
        }

        # Add cloud cover filter for optical sensors
        if "sentinel-2" in collection:
            search_body["query"] = {
                "eo:cloud_cover": {"lte": max_cloud_cover}
            }

        url = f"{self.stac_url}search"
        print(f"  [Copernicus STAC] Searching {collection} over {zone.name}...")
        print(f"    Bbox: {zone.bbox}, Date range: {start_date.date()} to {end_date.date()}")

        resp = self.session.post(url, json=search_body, timeout=30)
        resp.raise_for_status()
        result = resp.json()

        features = result.get("features", [])
        print(f"    -> Found {len(features)} items")

        # Extract key metadata
        items = []
        for feat in features:
            props = feat.get("properties", {})
            item = {
                "id": feat.get("id"),
                "collection": collection,
                "datetime": props.get("datetime"),
                "cloud_cover": props.get("eo:cloud_cover"),
                "bbox": feat.get("bbox"),
                "thumbnail": None,
                "download_link": None,
            }

            # Extract thumbnail and download links
            assets = feat.get("assets", {})
            if "thumbnail" in assets:
                item["thumbnail"] = assets["thumbnail"].get("href")
            if "data" in assets:
                item["download_link"] = assets["data"].get("href")

            items.append(item)

        return items

    def search_all_sensors(
        self,
        zone: CoastalZone,
        days_back: int = 30,
        max_items_per_sensor: int = 5,
        save: bool = True,
    ) -> Dict[str, List[Dict]]:
        """Search all relevant Sentinel collections for a zone."""
        results = {}
        for coll_id, description in self.COLLECTIONS.items():
            print(f"\n  --- {description} ---")
            try:
                items = self.search_imagery(
                    zone=zone,
                    collection=coll_id,
                    days_back=days_back,
                    max_items=max_items_per_sensor,
                )
                results[coll_id] = items
            except Exception as e:
                print(f"  [Copernicus STAC] Warning for {coll_id}: {e}")
                results[coll_id] = []

        if save:
            out_dir = os.path.join(RAW_DATA_DIR, "copernicus_sentinel", zone.name.lower())
            os.makedirs(out_dir, exist_ok=True)
            with open(os.path.join(out_dir, "search_results.json"), "w") as f:
                json.dump(results, f, indent=2, default=str)
            print(f"\n  -> Saved search results to {out_dir}/search_results.json")

        return results

    def download_thumbnail(self, item: Dict, output_dir: str) -> Optional[str]:
        """Download a thumbnail preview image for a STAC item."""
        if not item.get("thumbnail"):
            return None

        filename = f"{item['id']}_thumb.png"
        filepath = os.path.join(output_dir, filename)

        resp = self.session.get(item["thumbnail"], timeout=30)
        resp.raise_for_status()
        with open(filepath, "wb") as f:
            f.write(resp.content)

        print(f"    -> Downloaded thumbnail: {filename}")
        return filepath


if __name__ == "__main__":
    from .config import COASTAL_ZONES
    collector = CopernicusSentinelCollector()
    zone = COASTAL_ZONES["mumbai"]
    results = collector.search_all_sensors(zone, days_back=14, max_items_per_sensor=3)
    for coll, items in results.items():
        print(f"\n=== {coll} ===")
        for item in items:
            print(f"  {item['id']} | {item['datetime']} | cloud: {item['cloud_cover']}")