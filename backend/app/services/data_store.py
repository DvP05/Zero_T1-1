"""
TIDALIS — In-memory data store.

Provides a singleton-style store that holds all demo data (sensors,
observations, events, assets, forecasts) in memory, partitioned by coastal zone.
Acts as the "database" for the hackathon prototype.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional

from backend.app.models.schemas import (
    AssetType,
    CoastalAsset,
    CoastalState,
    Event,
    ExposureResult,
    Forecast,
    Observation,
    SensorReading,
    WhatIfResult,
)
from backend.app.services.collector_service import (
    ZONE_ASSETS,
    find_nearest_zone,
    get_zone,
    get_zone_assets,
    ingest_open_meteo_cache,
    ingest_tidalis_cache,
)

logger = logging.getLogger(__name__)


class DataStore:
    """In-memory data store for TIDALIS multi-location platform."""

    _instance: Optional["DataStore"] = None

    def __new__(cls) -> "DataStore":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialised = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialised:
            return
        self._initialised = True

        self.active_zone_id: str = "mumbai"

        # Global/flat backward-compatibility structures
        self.sensor_readings: List[SensorReading] = []
        self.observations: List[Observation] = []
        self.events: List[Event] = []
        self.forecasts: List[Forecast] = []
        self.exposures: List[ExposureResult] = []
        self.simulations: List[WhatIfResult] = []
        self.assets: List[CoastalAsset] = []
        self.marine_cache: dict = {}
        self.reference_time: datetime = datetime.now(timezone.utc)

        # Zone-partitioned structures
        self.zone_sensor_readings: Dict[str, List[SensorReading]] = defaultdict(list)
        self.zone_observations: Dict[str, List[Observation]] = defaultdict(list)
        self.zone_events: Dict[str, List[Event]] = defaultdict(list)
        self.zone_forecasts: Dict[str, List[Forecast]] = defaultdict(list)
        self.zone_assets: Dict[str, List[CoastalAsset]] = defaultdict(list)
        self.zone_marine_cache: Dict[str, dict] = {}

        self._seed_assets()

    def _seed_assets(self) -> None:
        """Pre-populate coastal assets across all focus zones."""
        all_assets = []
        for zid, assets in ZONE_ASSETS.items():
            self.zone_assets[zid] = list(assets)
            all_assets.extend(assets)
        self.assets = all_assets

    def load_zone(self, zone_id: str, set_active: bool = False) -> dict:
        """
        Load cached raw datasets for a zone into memory.
        Returns record counts.
        """
        zid = zone_id.lower().strip()
        obs = ingest_open_meteo_cache(zid)
        readings = ingest_tidalis_cache(zid)

        if obs:
            self.zone_observations[zid] = obs
            self.observations.extend(obs)

        if readings:
            self.zone_sensor_readings[zid] = readings
            self.sensor_readings.extend(readings)

        if zid not in self.zone_assets or not self.zone_assets[zid]:
            self.zone_assets[zid] = get_zone_assets(zid)

        if set_active:
            self.active_zone_id = zid

        logger.info("Loaded zone %s: %d observations, %d sensor readings", zid, len(obs), len(readings))
        return {
            "zone_id": zid,
            "observations_loaded": len(obs),
            "sensor_readings_loaded": len(readings),
            "assets_count": len(self.zone_assets.get(zid, [])),
        }

    # -- Sensor helpers -------------------------------------------------------

    def get_sensors(self, zone_id: Optional[str] = None) -> list[dict]:
        """
        Return unique sensor metadata from readings or simulator.
        If zone_id is specified, returns sensors for that zone.
        """
        zid = (zone_id or self.active_zone_id).lower().strip()

        # If Goa or if no specific zone data yet, check simulator for Goa
        if zid == "goa":
            from backend.app.services.sensor_simulator import get_sensor_metadata
            return get_sensor_metadata()

        # Check zone partitioned readings
        readings = self.zone_sensor_readings.get(zid, [])
        if readings:
            seen: dict[str, dict] = {}
            for r in readings:
                if r.sensor_id not in seen:
                    seen[r.sensor_id] = {
                        "sensor_id": r.sensor_id,
                        "lat": r.latitude,
                        "lon": r.longitude,
                        "name": r.sensor_id,
                        "type": r.sensor_type or "gauge",
                        "elevation_m": 5.0,
                        "zone": zid,
                        "status": "online",
                    }
            return list(seen.values())

        # If empty but zone is Goa, fallback to simulator
        from backend.app.services.sensor_simulator import get_sensor_metadata
        return get_sensor_metadata()

    def get_sensor_by_id(self, sensor_id: str, zone_id: Optional[str] = None) -> Optional[dict]:
        sensors = self.get_sensors(zone_id)
        return next((s for s in sensors if s["sensor_id"] == sensor_id), None)

    def get_sensor_observations(self, sensor_id: str, zone_id: Optional[str] = None) -> list[SensorReading]:
        zid = zone_id.lower().strip() if zone_id else None
        if zid and zid in self.zone_sensor_readings:
            return [r for r in self.zone_sensor_readings[zid] if r.sensor_id == sensor_id]
        return [r for r in self.sensor_readings if r.sensor_id == sensor_id]

    def get_latest_readings(self, zone_id: Optional[str] = None) -> list[SensorReading]:
        """Return the most recent reading per sensor for the requested zone."""
        zid = zone_id.lower().strip() if zone_id else None
        source = (
            self.zone_sensor_readings[zid]
            if zid and zid in self.zone_sensor_readings and self.zone_sensor_readings[zid]
            else self.sensor_readings
        )

        latest: dict[str, SensorReading] = {}
        for r in source:
            if r.sensor_id not in latest or r.timestamp > latest[r.sensor_id].timestamp:
                latest[r.sensor_id] = r
        return list(latest.values())

    # -- Asset helpers --------------------------------------------------------

    def get_assets(self, zone_id: Optional[str] = None) -> list[CoastalAsset]:
        """Return coastal assets for the requested zone, or all assets if None."""
        if zone_id:
            zid = zone_id.lower().strip()
            return self.zone_assets.get(zid, get_zone_assets(zid))
        return self.assets

    # -- Event helpers --------------------------------------------------------

    def get_events(self, zone_id: Optional[str] = None) -> list[Event]:
        if zone_id:
            zid = zone_id.lower().strip()
            # If zone events exist, return them
            if zid in self.zone_events and self.zone_events[zid]:
                return self.zone_events[zid]
        return self.events

    def get_event(self, event_id: str) -> Optional[Event]:
        return next((e for e in self.events if e.event_id == event_id), None)

    # -- Forecast helpers -----------------------------------------------------

    def get_forecast(self, event_id: str) -> Optional[Forecast]:
        return next((f for f in self.forecasts if f.event_id == event_id), None)

    # -- Exposure helpers -----------------------------------------------------

    def get_exposures(self, event_id: str) -> list[ExposureResult]:
        return [e for e in self.exposures if e.asset_id]

    # -- Coastal state --------------------------------------------------------

    def get_coastal_state(
        self,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        zone_id: Optional[str] = None,
    ) -> CoastalState:
        """
        Build aggregated coastal state for a specific zone or lat/lon coordinate.
        """
        if zone_id:
            zid = zone_id.lower().strip()
            z = get_zone(zid)
            target_lat = lat if lat is not None else (z.lat if z else 19.0760)
            target_lon = lon if lon is not None else (z.lon if z else 72.8777)
            zname = z.name if z else zid.title()
        elif lat is not None and lon is not None:
            zid, z = find_nearest_zone(lat, lon)
            target_lat = lat
            target_lon = lon
            zname = z.name
        else:
            zid = self.active_zone_id
            z = get_zone(zid)
            target_lat = z.lat if z else 19.0760
            target_lon = z.lon if z else 72.8777
            zname = z.name if z else zid.title()

        latest = self.get_latest_readings(zone_id=zid)
        active_events = [e for e in self.get_events(zone_id=zid) if e.status == "ACTIVE"]

        status = "NORMAL"
        if any(e.severity.value in ("HIGH", "CRITICAL") for e in active_events):
            status = "ALERT"
        elif any(e.severity.value == "MEDIUM" for e in active_events):
            status = "WARNING"
        elif active_events:
            status = "WATCH"

        marine_data = self.zone_marine_cache.get(zid, self.marine_cache)
        sensors = self.get_sensors(zone_id=zid)

        return CoastalState(
            timestamp=datetime.now(timezone.utc),
            zone_id=zid,
            zone_name=zname,
            latitude=target_lat,
            longitude=target_lon,
            status=status,
            sensor_count=len(sensors),
            active_events=len(active_events),
            marine_data=marine_data,
        )


# Singleton accessor
def get_store() -> DataStore:
    return DataStore()
