"""
Central Configuration for Coastal Flood Intelligence Data Collection
====================================================================
All API keys, coordinates, and shared settings live here.

INDIAN COASTLINE FOCUS ZONES:
  - Mumbai (West Coast - Arabian Sea)
  - Chennai (East Coast - Bay of Bengal)
  - Kochi (Southwest Coast - Arabian Sea)
  - Kolkata (East Coast - Bay of Bengal delta)
  - Visakhapatnam (East Coast - Bay of Bengal)
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

# -----------------------------------------------
# API Keys (set via environment variables)
# -----------------------------------------------
COPERNICUS_DATASPACE_USERNAME = os.getenv("COPERNICUS_DATASPACE_USERNAME", "")
COPERNICUS_DATASPACE_PASSWORD = os.getenv("COPERNICUS_DATASPACE_PASSWORD", "")

COPERNICUS_MARINE_USERNAME = os.getenv("COPERNICUS_MARINE_USERNAME", "")
COPERNICUS_MARINE_PASSWORD = os.getenv("COPERNICUS_MARINE_PASSWORD", "")

NASA_EARTHDATA_USERNAME = os.getenv("NASA_EARTHDATA_USERNAME", "")
NASA_EARTHDATA_PASSWORD = os.getenv("NASA_EARTHDATA_PASSWORD", "")

STORMGLASS_API_KEY = os.getenv("STORMGLASS_API_KEY", "")  # Optional - paid

# Open-Meteo: NO API KEY NEEDED (free, open-source)
# NOAA NDBC: NO API KEY NEEDED (public data)


# -----------------------------------------------
# Indian Coastline Focus Zones
# -----------------------------------------------
@dataclass
class CoastalZone:
    name: str
    lat: float
    lon: float
    bbox: Tuple[float, float, float, float]  # (min_lon, min_lat, max_lon, max_lat)
    coast: str  # "west" or "east"
    nearest_buoy_ids: List[str] = field(default_factory=list)
    elevation_range_m: Tuple[float, float] = (0, 15)


COASTAL_ZONES: Dict[str, CoastalZone] = {
    "mumbai": CoastalZone(
        name="Mumbai",
        lat=19.0760,
        lon=72.8777,
        bbox=(72.75, 18.90, 73.05, 19.25),
        coast="west",
        nearest_buoy_ids=["23226", "23168"],
        elevation_range_m=(0, 14),
    ),
    "chennai": CoastalZone(
        name="Chennai",
        lat=13.0827,
        lon=80.2707,
        bbox=(80.10, 12.90, 80.40, 13.25),
        coast="east",
        nearest_buoy_ids=["23461", "23091"],
        elevation_range_m=(0, 12),
    ),
    "kochi": CoastalZone(
        name="Kochi",
        lat=9.9312,
        lon=76.2673,
        bbox=(76.10, 9.80, 76.40, 10.10),
        coast="west",
        nearest_buoy_ids=["23226"],
        elevation_range_m=(0, 10),
    ),
    "kolkata": CoastalZone(
        name="Kolkata (Sundarbans Delta)",
        lat=21.7580,
        lon=88.3430,
        bbox=(88.00, 21.50, 88.70, 22.00),
        coast="east",
        nearest_buoy_ids=["23101"],
        elevation_range_m=(0, 8),
    ),
    "visakhapatnam": CoastalZone(
        name="Visakhapatnam",
        lat=17.6868,
        lon=83.2185,
        bbox=(83.05, 17.55, 83.40, 17.85),
        coast="east",
        nearest_buoy_ids=["23091"],
        elevation_range_m=(0, 20),
    ),
    "goa": CoastalZone(
        name="Goa (Miramar & Mormugao)",
        lat=15.2993,
        lon=73.9700,
        bbox=(73.70, 15.15, 74.05, 15.60),
        coast="west",
        nearest_buoy_ids=["23226"],
        elevation_range_m=(0, 15),
    ),
}

DEFAULT_ZONE = "mumbai"

# -----------------------------------------------
# Data Storage Paths
# -----------------------------------------------
BASE_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
RAW_DATA_DIR = os.path.join(BASE_DATA_DIR, "raw")
PROCESSED_DATA_DIR = os.path.join(BASE_DATA_DIR, "processed")
CACHE_DIR = os.path.join(BASE_DATA_DIR, "cache")

for _dir in [RAW_DATA_DIR, PROCESSED_DATA_DIR, CACHE_DIR]:
    os.makedirs(_dir, exist_ok=True)

# -----------------------------------------------
# Temporal Settings
# -----------------------------------------------
SCENARIO_DURATION_HOURS = 6
SCENARIO_TIMESTEP_MINUTES = 30

# -----------------------------------------------
# API Endpoints
# -----------------------------------------------
ENDPOINTS = {
    "copernicus_stac": "https://stac.dataspace.copernicus.eu/v1/",
    "copernicus_sentinel_hub": "https://sh.dataspace.copernicus.eu",
    "nasa_cmr": "https://cmr.earthdata.nasa.gov/search",
    "nasa_earthdata_login": "https://urs.earthdata.nasa.gov",
    "open_meteo_weather": "https://api.open-meteo.com/v1/forecast",
    "open_meteo_marine": "https://marine-api.open-meteo.com/v1/marine",
    "ndbc_realtime": "https://www.ndbc.noaa.gov/data/realtime2",
    "copernicus_marine": "https://data-be-prd.marine.copernicus.eu/api",
    "stormglass": "https://api.stormglass.io/v2",
}
