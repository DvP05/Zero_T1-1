import json
import time
import requests
from pathlib import Path

ROADS_DIR = Path(__file__).resolve().parent.parent / "data" / "geo" / "roads"
ROADS_DIR.mkdir(parents=True, exist_ok=True)

DISTRICTS = {
    "goa": {
        "name": "Goa Coastal District",
        "bbox": [15.22, 73.76, 15.54, 74.02], # [min_lat, min_lon, max_lat, max_lon]
        "center": [73.97, 15.30],
    },
    "mangaluru": {
        "name": "Mangaluru Coastal District",
        "bbox": [12.80, 74.79, 13.02, 74.92],
        "center": [74.86, 12.92],
    },
    "mumbai": {
        "name": "Mumbai Coastal District",
        "bbox": [18.88, 72.76, 19.15, 72.98],
        "center": [72.83, 18.97],
    }
}

def query_osm_roads(bbox):
    min_lat, min_lon, max_lat, max_lon = bbox
    overpass_query = f"""[out:json][timeout:25];
(
  way["highway"~"motorway|trunk|primary|secondary"]({min_lat},{min_lon},{max_lat},{max_lon});
);
out geom;
"""
    endpoints = [
        "https://overpass-api.de/api/interpreter",
        "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
    ]
    for url in endpoints:
        try:
            print(f"Querying {url} for bbox {bbox}...")
            resp = requests.post(url, data={"data": overpass_query}, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                elements = data.get("elements", [])
                if elements:
                    print(f"Success from {url}: {len(elements)} road elements found.")
                    return elements
        except Exception as e:
            print(f"Error querying {url}: {e}")
            time.sleep(1)
    return []

if __name__ == "__main__":
    for zid, info in DISTRICTS.items():
        print(f"\n--- Fetching real roads for {zid} ---")
        elements = query_osm_roads(info["bbox"])
        print(f"Total elements for {zid}: {len(elements)}")
