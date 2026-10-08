"""
TIDALIS — Multi-Location Data Collection & Ingestion Service.

Bridges the data collection pipeline (Open-Meteo, NOAA buoys, Tidalis IoT, etc.)
with the backend runtime. Supports:
  1. Zone registry and metadata discovery
  2. Ingesting pre-collected raw datasets from data/raw/
  3. Live on-demand API collection and virtual IoT sensor generation
  4. Background task execution and status tracking
"""

from __future__ import annotations

import logging
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from data_collection.config import (
    BASE_DATA_DIR,
    COASTAL_ZONES,
    DEFAULT_ZONE,
    RAW_DATA_DIR,
    CoastalZone,
)
from backend.app.models.schemas import (
    AssetType,
    CoastalAsset,
    CoastalZoneInfo,
    CollectionRequest,
    CollectionStatus,
    LocationSummary,
    Observation,
    SensorReading,
)

logger = logging.getLogger(__name__)

# In-memory tracking of collection tasks per zone
COLLECTION_STATUSES: Dict[str, CollectionStatus] = {}


# ---------------------------------------------------------------------------
# Predefined Coastal Assets per Focus Zone
# ---------------------------------------------------------------------------

ZONE_ASSETS: Dict[str, List[CoastalAsset]] = {
    "mumbai": [
        CoastalAsset(
            asset_id="mum-port-01",
            asset_type=AssetType.PORT,
            name="Jawaharlal Nehru & Mumbai Port",
            latitude=18.9500,
            longitude=72.9500,
            sensitivity=0.85,
            description="Major container port and maritime trade gateway",
        ),
        CoastalAsset(
            asset_id="mum-beach-01",
            asset_type=AssetType.BEACH,
            name="Marine Drive & Chowpatty",
            latitude=18.9438,
            longitude=72.8232,
            sensitivity=0.65,
            description="Iconic coastal promenade and high-density public waterfront",
        ),
        CoastalAsset(
            asset_id="mum-beach-02",
            asset_type=AssetType.BEACH,
            name="Juhu Beach Waterfront",
            latitude=19.0988,
            longitude=72.8264,
            sensitivity=0.70,
            description="Vulnerable low-lying beach front prone to monsoon surge",
        ),
        CoastalAsset(
            asset_id="mum-fish-01",
            asset_type=AssetType.FISHERY,
            name="Sassoon Docks Fishery Hub",
            latitude=18.9150,
            longitude=72.8280,
            sensitivity=0.80,
            description="Primary artisanal fishing port and wholesale market",
        ),
        CoastalAsset(
            asset_id="mum-link-01",
            asset_type=AssetType.CUSTOM_ASSET,
            name="Bandra-Worli Coastal Sea Link",
            latitude=19.0360,
            longitude=72.8170,
            sensitivity=0.90,
            description="Critical transport arterial connecting South Mumbai to Suburbs",
        ),
        CoastalAsset(
            asset_id="mum-hab-01",
            asset_type=AssetType.HABITAT,
            name="Thane Creek Mangrove Biosphere",
            latitude=19.1200,
            longitude=72.9800,
            sensitivity=0.95,
            description="Protected flamingo wetland sanctuary and flood-buffer mangroves",
        ),
    ],
    "chennai": [
        CoastalAsset(
            asset_id="chn-port-01",
            asset_type=AssetType.PORT,
            name="Chennai Port Trust",
            latitude=13.0840,
            longitude=80.2980,
            sensitivity=0.85,
            description="Primary eastern container hub vulnerable to cyclone surges",
        ),
        CoastalAsset(
            asset_id="chn-beach-01",
            asset_type=AssetType.BEACH,
            name="Marina Beach Promenade",
            latitude=13.0500,
            longitude=80.2824,
            sensitivity=0.65,
            description="Long natural urban beach and dense coastal recreational zone",
        ),
        CoastalAsset(
            asset_id="chn-fish-01",
            asset_type=AssetType.FISHERY,
            name="Kasimedu Fishing Harbour",
            latitude=13.1250,
            longitude=80.2970,
            sensitivity=0.80,
            description="Major fishing harbour and community fleet anchorage",
        ),
        CoastalAsset(
            asset_id="chn-hab-01",
            asset_type=AssetType.HABITAT,
            name="Adyar River Estuary & Creek",
            latitude=13.0070,
            longitude=80.2600,
            sensitivity=0.90,
            description="Ecologically fragile delta prone to severe urban backwater flooding",
        ),
    ],
    "kochi": [
        CoastalAsset(
            asset_id="koc-port-01",
            asset_type=AssetType.PORT,
            name="Cochin Port & Vallarpadam ICTT",
            latitude=9.9650,
            longitude=76.2650,
            sensitivity=0.85,
            description="Transshipment terminal situated in backwater estuary",
        ),
        CoastalAsset(
            asset_id="koc-beach-01",
            asset_type=AssetType.BEACH,
            name="Fort Kochi Heritage Coastline",
            latitude=9.9660,
            longitude=76.2420,
            sensitivity=0.75,
            description="Historic cultural quarter with Chinese fishing nets",
        ),
        CoastalAsset(
            asset_id="koc-hab-01",
            asset_type=AssetType.HABITAT,
            name="Vembanad Wetland System",
            latitude=9.8500,
            longitude=76.3500,
            sensitivity=0.95,
            description="Ramsar wetland site receiving runoff from major Western Ghats rivers",
        ),
    ],
    "kolkata": [
        CoastalAsset(
            asset_id="kol-port-01",
            asset_type=AssetType.PORT,
            name="Syama Prasad Mookerjee Port (Haldia/Kolkata)",
            latitude=22.0200,
            longitude=88.0600,
            sensitivity=0.80,
            description="Riverine port complex serving eastern India",
        ),
        CoastalAsset(
            asset_id="kol-hab-01",
            asset_type=AssetType.HABITAT,
            name="Sundarbans Mangrove Delta",
            latitude=21.8000,
            longitude=88.8000,
            sensitivity=0.98,
            description="UNESCO World Heritage mangrove tiger reserve and storm buffer",
        ),
        CoastalAsset(
            asset_id="kol-fish-01",
            asset_type=AssetType.FISHERY,
            name="Kakdwip & Diamond Harbour Fishery",
            latitude=21.8700,
            longitude=88.1900,
            sensitivity=0.85,
            description="High-density estuarine fishing communities vulnerable to tidal bore",
        ),
    ],
    "visakhapatnam": [
        CoastalAsset(
            asset_id="viz-port-01",
            asset_type=AssetType.PORT,
            name="Visakhapatnam Deepwater Port",
            latitude=17.6950,
            longitude=83.2950,
            sensitivity=0.85,
            description="Natural landlocked harbor on Bay of Bengal",
        ),
        CoastalAsset(
            asset_id="viz-beach-01",
            asset_type=AssetType.BEACH,
            name="Ramakrishna (RK) Beach",
            latitude=17.7120,
            longitude=83.3230,
            sensitivity=0.60,
            description="Urban seafront subject to severe beach erosion during cyclones",
        ),
        CoastalAsset(
            asset_id="viz-ind-01",
            asset_type=AssetType.INDUSTRY,
            name="Coastal Petrochemical Corridor",
            latitude=17.6500,
            longitude=83.2300,
            sensitivity=0.90,
            description="Critical energy refineries and industrial infrastructure",
        ),
    ],
    "goa": [
        CoastalAsset(
            asset_id="goa-hab-01",
            asset_type=AssetType.HABITAT,
            name="Grande Island Coral Reef",
            latitude=15.2150,
            longitude=73.9100,
            sensitivity=0.90,
            description="Protected marine habitat with coral formations",
        ),
        CoastalAsset(
            asset_id="goa-fish-01",
            asset_type=AssetType.FISHERY,
            name="Zuari Estuary Fishery",
            latitude=15.2600,
            longitude=73.9400,
            sensitivity=0.75,
            description="Active artisanal fishing zone",
        ),
        CoastalAsset(
            asset_id="goa-beach-01",
            asset_type=AssetType.BEACH,
            name="Miramar Beach",
            latitude=15.2993,
            longitude=73.9862,
            sensitivity=0.60,
            description="Popular recreational beach at Mandovi estuary",
        ),
        CoastalAsset(
            asset_id="goa-port-01",
            asset_type=AssetType.PORT,
            name="Mormugao Port Trust",
            latitude=15.3993,
            longitude=73.7999,
            sensitivity=0.50,
            description="Major commercial iron ore and cruise port",
        ),
        CoastalAsset(
            asset_id="goa-tour-01",
            asset_type=AssetType.TOURISM,
            name="Dona Paula Jetty",
            latitude=15.2760,
            longitude=73.9700,
            sensitivity=0.65,
            description="Tourist viewpoint and water sports hub",
        ),
    ],
}


# ---------------------------------------------------------------------------
# Zone Registry & Discovery
# ---------------------------------------------------------------------------

def get_all_zones() -> Dict[str, CoastalZone]:
    """Return all registered coastal zones."""
    return COASTAL_ZONES


def get_zone(zone_id: str) -> Optional[CoastalZone]:
    """Retrieve zone by id (case-insensitive)."""
    return COASTAL_ZONES.get(zone_id.lower().strip())


def find_nearest_zone(lat: float, lon: float) -> Tuple[str, CoastalZone]:
    """Find the registered zone closest to the given coordinates."""
    best_id = DEFAULT_ZONE
    best_dist = float("inf")

    for zid, z in COASTAL_ZONES.items():
        # Euclidean degree approximation for quick lookup
        d = math.hypot(z.lat - lat, z.lon - lon)
        if d < best_dist:
            best_dist = d
            best_id = zid

    return best_id, COASTAL_ZONES[best_id]


def check_zone_cache(zone_id: str) -> Dict[str, bool]:
    """Check what raw datasets are already cached on disk for this zone."""
    zid = zone_id.lower().strip()
    return {
        "open_meteo": os.path.exists(os.path.join(RAW_DATA_DIR, "open_meteo", zid, "weather.csv")),
        "marine": os.path.exists(os.path.join(RAW_DATA_DIR, "open_meteo", zid, "marine.csv")),
        "tidalis": os.path.exists(os.path.join(RAW_DATA_DIR, "tidalis", zid, "scenario_heavy_coastal_rain.csv")),
        "sensor_registry": os.path.exists(os.path.join(RAW_DATA_DIR, "tidalis", zid, "sensor_registry.csv")),
        "worldview": os.path.exists(os.path.join(RAW_DATA_DIR, "worldview", zid, "flood_extents.geojson")),
        "copernicus": os.path.exists(os.path.join(RAW_DATA_DIR, "copernicus_marine", zid)),
    }


def get_zone_info(zone_id: str) -> Optional[CoastalZoneInfo]:
    """Get full metadata and current data availability for a zone."""
    z = get_zone(zone_id)
    if not z:
        return None

    zid = zone_id.lower().strip()
    cache = check_zone_cache(zid)
    has_cache = any(cache.values())

    # Count sensors if registry exists, or estimate
    sensor_count = 0
    registry_path = os.path.join(RAW_DATA_DIR, "tidalis", zid, "sensor_registry.csv")
    if os.path.exists(registry_path):
        try:
            df = pd.read_csv(registry_path)
            sensor_count = len(df)
        except Exception:
            sensor_count = 22
    elif zid == "goa":
        sensor_count = 5

    return CoastalZoneInfo(
        zone_id=zid,
        name=z.name,
        lat=z.lat,
        lon=z.lon,
        bbox=list(z.bbox),
        coast=z.coast,
        nearest_buoy_ids=z.nearest_buoy_ids,
        elevation_range_m=list(z.elevation_range_m),
        has_cached_data=has_cache,
        sensor_count=sensor_count,
        status="ONLINE",
    )


def list_all_zones() -> List[LocationSummary]:
    """Return lightweight summary for all registered coastal zones."""
    summaries = []
    for zid, z in COASTAL_ZONES.items():
        cache = check_zone_cache(zid)
        summaries.append(
            LocationSummary(
                zone_id=zid,
                name=z.name,
                lat=z.lat,
                lon=z.lon,
                coast=z.coast,
                has_cached_data=any(cache.values()),
                sensor_count=22 if cache.get("tidalis") else (5 if zid == "goa" else 0),
                status="ONLINE",
            )
        )
    return summaries


def get_zone_assets(zone_id: str) -> List[CoastalAsset]:
    """Return predefined coastal assets for the requested zone."""
    zid = zone_id.lower().strip()
    if zid in ZONE_ASSETS:
        return ZONE_ASSETS[zid]

    # Generate a generic fallback asset if unknown
    z = get_zone(zid)
    if z:
        return [
            CoastalAsset(
                asset_id=f"{zid}-port-01",
                asset_type=AssetType.PORT,
                name=f"{z.name} Coastal Anchorage",
                latitude=z.lat,
                longitude=z.lon,
                sensitivity=0.75,
                description=f"Primary maritime facility for {z.name}",
            )
        ]
    return []


# ---------------------------------------------------------------------------
# Ingest Pre-Collected Datasets from data/raw/
# ---------------------------------------------------------------------------

def ingest_open_meteo_cache(zone_id: str) -> List[Observation]:
    """
    Load cached Open-Meteo weather and marine CSVs for a zone into Observation models.
    """
    zid = zone_id.lower().strip()
    obs_list: List[Observation] = []
    z = get_zone(zid)
    lat = z.lat if z else 0.0
    lon = z.lon if z else 0.0

    marine_csv = os.path.join(RAW_DATA_DIR, "open_meteo", zid, "marine.csv")
    weather_csv = os.path.join(RAW_DATA_DIR, "open_meteo", zid, "weather.csv")

    marine_df = pd.read_csv(marine_csv) if os.path.exists(marine_csv) else None
    weather_df = pd.read_csv(weather_csv) if os.path.exists(weather_csv) else None

    if marine_df is not None:
        try:
            marine_df["time"] = pd.to_datetime(marine_df["time"])
            for _, row in marine_df.iterrows():
                variables = {}
                for col in [
                    "wave_height", "wave_direction", "wave_period",
                    "wind_wave_height", "swell_wave_height",
                    "ocean_current_velocity", "ocean_current_direction",
                ]:
                    if col in row and pd.notna(row[col]):
                        variables[col] = float(row[col])

                ts = row["time"].to_pydatetime()
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)

                obs_list.append(Observation(
                    timestamp=ts,
                    latitude=float(row.get("lat", lat)),
                    longitude=float(row.get("lon", lon)),
                    source="open_meteo_marine",
                    zone_id=zid,
                    variables=variables,
                ))
        except Exception as exc:
            logger.warning("Error ingesting marine CSV for %s: %s", zid, exc)

    if weather_df is not None:
        try:
            weather_df["time"] = pd.to_datetime(weather_df["time"])
            for _, row in weather_df.iterrows():
                variables = {}
                for col in [
                    "temperature_2m", "relative_humidity_2m", "precipitation",
                    "rain", "pressure_msl", "surface_pressure",
                    "wind_speed_10m", "wind_direction_10m", "wind_gusts_10m",
                ]:
                    if col in row and pd.notna(row[col]):
                        variables[col] = float(row[col])

                ts = row["time"].to_pydatetime()
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)

                obs_list.append(Observation(
                    timestamp=ts,
                    latitude=float(row.get("lat", lat)),
                    longitude=float(row.get("lon", lon)),
                    source="open_meteo_weather",
                    zone_id=zid,
                    variables=variables,
                ))
        except Exception as exc:
            logger.warning("Error ingesting weather CSV for %s: %s", zid, exc)

    return obs_list


def ingest_tidalis_cache(zone_id: str) -> List[SensorReading]:
    """
    Load cached Tidalis scenario CSV for a zone into SensorReading models.
    """
    zid = zone_id.lower().strip()
    scenario_csv = os.path.join(RAW_DATA_DIR, "tidalis", zid, "scenario_heavy_coastal_rain.csv")
    if not os.path.exists(scenario_csv):
        return []

    readings: List[SensorReading] = []
    try:
        df = pd.read_csv(scenario_csv)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        for _, row in df.iterrows():
            ts = row["timestamp"].to_pydatetime()
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)

            # Map fields with fallbacks
            readings.append(SensorReading(
                sensor_id=str(row["sensor_id"]),
                timestamp=ts,
                latitude=float(row["lat"]),
                longitude=float(row["lon"]),
                temperature=float(row.get("temperature", 28.5 if pd.isna(row.get("temperature")) else row.get("temperature"))),
                turbidity=float(row.get("turbidity_ntu", 8.0) if pd.notna(row.get("turbidity_ntu")) else 8.0),
                ph=float(row.get("ph", 8.0) if pd.notna(row.get("ph")) else 8.0),
                dissolved_oxygen=6.2,
                water_level_m=float(row["water_level_m"]) if "water_level_m" in row and pd.notna(row["water_level_m"]) else None,
                precipitation_mm_hr=float(row["precipitation_mm_hr"]) if "precipitation_mm_hr" in row and pd.notna(row["precipitation_mm_hr"]) else None,
                flood_depth_m=float(row["flood_depth_m"]) if "flood_depth_m" in row and pd.notna(row["flood_depth_m"]) else None,
                sensor_type=str(row.get("type", "unknown")),
                zone_id=zid,
            ))
    except Exception as exc:
        logger.warning("Error ingesting Tidalis scenario for %s: %s", zid, exc)

    return readings


# ---------------------------------------------------------------------------
# On-Demand Live & Simulated Data Collection
# ---------------------------------------------------------------------------

def collect_open_meteo_live(zone_id: str, forecast_days: int = 3, save: bool = True) -> List[Observation]:
    """
    Fetch real-time weather and marine data from Open-Meteo for a specific zone.
    """
    from data_collection.collector_open_meteo import OpenMeteoCollector

    z = get_zone(zone_id)
    if not z:
        raise ValueError(f"Unknown zone: {zone_id}")

    collector = OpenMeteoCollector()
    weather_df = collector.fetch_weather(z, forecast_days=forecast_days)
    marine_df = collector.fetch_marine(z, forecast_days=forecast_days)

    if save:
        out_dir = os.path.join(RAW_DATA_DIR, "open_meteo", zone_id.lower())
        os.makedirs(out_dir, exist_ok=True)
        weather_df.to_csv(os.path.join(out_dir, "weather.csv"), index=False)
        marine_df.to_csv(os.path.join(out_dir, "marine.csv"), index=False)

    return ingest_open_meteo_cache(zone_id)


def generate_tidalis_sensors_live(
    zone_id: str,
    scenario: str = "heavy_coastal_rain",
    save: bool = True,
) -> List[SensorReading]:
    """
    Generate virtual IoT sensors and scenario telemetry for a specific zone.
    """
    from data_collection.collector_tidalis_sensors import TidalisSensorNetwork

    z = get_zone(zone_id)
    if not z:
        raise ValueError(f"Unknown zone: {zone_id}")

    network = TidalisSensorNetwork()
    data = network.generate_scenario_data(z, scenario=scenario)

    if save:
        out_dir = os.path.join(RAW_DATA_DIR, "tidalis", zone_id.lower())
        os.makedirs(out_dir, exist_ok=True)
        data["sensor_registry"].to_csv(os.path.join(out_dir, "sensor_registry.csv"), index=False)
        data["scenario_data"].to_csv(os.path.join(out_dir, f"scenario_{scenario}.csv"), index=False)

    return ingest_tidalis_cache(zone_id)


def run_collection_pipeline(
    zone_id: str,
    request: Optional[CollectionRequest] = None,
) -> CollectionStatus:
    """
    Execute collection pipeline for a zone and update task status.
    Can be called synchronously or as a FastAPI background task.
    """
    zid = zone_id.lower().strip()
    if request is None:
        request = CollectionRequest()

    status = CollectionStatus(
        zone_id=zid,
        status="running",
        message="Collection in progress...",
        records_ingested=0,
        sources=request.sources,
        updated_at=datetime.now(timezone.utc),
    )
    COLLECTION_STATUSES[zid] = status

    z = get_zone(zid)
    if not z:
        status.status = "failed"
        status.message = f"Invalid zone '{zone_id}'"
        status.updated_at = datetime.now(timezone.utc)
        return status

    total_records = 0
    try:
        # 1. Open-Meteo
        if "open_meteo" in request.sources:
            obs = collect_open_meteo_live(zid, forecast_days=3, save=True)
            total_records += len(obs)

        # 2. Tidalis IoT
        if "tidalis" in request.sources:
            readings = generate_tidalis_sensors_live(zid, scenario=request.scenario, save=True)
            total_records += len(readings)

        status.status = "completed"
        status.records_ingested = total_records
        status.message = f"Successfully collected {total_records} records for {z.name}"
        status.updated_at = datetime.now(timezone.utc)
        logger.info("✓ Collection finished for %s: %d records", zid, total_records)
    except Exception as exc:
        logger.error("Collection failed for %s: %s", zid, exc, exc_info=True)
        status.status = "failed"
        status.message = str(exc)
        status.updated_at = datetime.now(timezone.utc)

    return status


def get_collection_status(zone_id: str) -> CollectionStatus:
    """Retrieve the current or last collection status for a zone."""
    zid = zone_id.lower().strip()
    if zid in COLLECTION_STATUSES:
        return COLLECTION_STATUSES[zid]

    cache = check_zone_cache(zid)
    has_cache = any(cache.values())
    return CollectionStatus(
        zone_id=zid,
        status="idle",
        message="Cached data available" if has_cache else "No data collected yet",
        records_ingested=0,
        sources=[k for k, v in cache.items() if v],
        updated_at=datetime.now(timezone.utc),
    )
