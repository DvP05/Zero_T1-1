"""
TIDALIS — In-memory data store.

Provides a singleton-style store that holds all demo data (sensors,
observations, events, assets, forecasts) in memory.  Acts as the
"database" for the hackathon prototype so we avoid any PostgreSQL setup.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from backend.app.models.schemas import (
    CoastalAsset,
    AssetType,
    CoastalState,
    Event,
    ExposureResult,
    Forecast,
    Observation,
    SensorReading,
    WhatIfResult,
)


class DataStore:
    """In-memory data store for TIDALIS demo."""

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

        self.sensor_readings: list[SensorReading] = []
        self.observations: list[Observation] = []
        self.events: list[Event] = []
        self.forecasts: list[Forecast] = []
        self.exposures: list[ExposureResult] = []
        self.simulations: list[WhatIfResult] = []
        self.assets: list[CoastalAsset] = []
        self.marine_cache: dict = {}
        self.reference_time: datetime = datetime.now(timezone.utc)

        self._seed_assets()

    def _seed_assets(self) -> None:
        """Pre-populate demo coastal assets around Goa."""
        self.assets = [
            CoastalAsset(
                asset_id="habitat-01",
                asset_type=AssetType.HABITAT,
                name="Grande Island Reef",
                latitude=15.2150,
                longitude=73.9100,
                sensitivity=0.90,
                description="Protected marine habitat with coral formations",
            ),
            CoastalAsset(
                asset_id="fishery-01",
                asset_type=AssetType.FISHERY,
                name="Zuari Estuary Fishery",
                latitude=15.2600,
                longitude=73.9400,
                sensitivity=0.75,
                description="Active artisanal fishing zone",
            ),
            CoastalAsset(
                asset_id="beach-01",
                asset_type=AssetType.BEACH,
                name="Miramar Beach",
                latitude=15.2993,
                longitude=73.9862,
                sensitivity=0.60,
                description="Popular recreational beach",
            ),
            CoastalAsset(
                asset_id="port-01",
                asset_type=AssetType.PORT,
                name="Mormugao Port",
                latitude=15.3993,
                longitude=73.7999,
                sensitivity=0.50,
                description="Major commercial port",
            ),
            CoastalAsset(
                asset_id="tourism-01",
                asset_type=AssetType.TOURISM,
                name="Dona Paula Jetty",
                latitude=15.2760,
                longitude=73.9700,
                sensitivity=0.65,
                description="Tourist viewpoint and water sports hub",
            ),
        ]

    # -- Sensor helpers -------------------------------------------------------

    def get_sensors(self) -> list[dict]:
        """Return unique sensor metadata from readings."""
        from backend.app.services.sensor_simulator import get_sensor_metadata
        return get_sensor_metadata()

    def get_sensor_by_id(self, sensor_id: str) -> Optional[dict]:
        sensors = self.get_sensors()
        return next((s for s in sensors if s["sensor_id"] == sensor_id), None)

    def get_sensor_observations(self, sensor_id: str) -> list[SensorReading]:
        return [r for r in self.sensor_readings if r.sensor_id == sensor_id]

    def get_latest_readings(self) -> list[SensorReading]:
        """Return the most recent reading per sensor."""
        latest: dict[str, SensorReading] = {}
        for r in self.sensor_readings:
            if r.sensor_id not in latest or r.timestamp > latest[r.sensor_id].timestamp:
                latest[r.sensor_id] = r
        return list(latest.values())

    # -- Event helpers --------------------------------------------------------

    def get_events(self) -> list[Event]:
        return self.events

    def get_event(self, event_id: str) -> Optional[Event]:
        return next((e for e in self.events if e.event_id == event_id), None)

    # -- Forecast helpers -----------------------------------------------------

    def get_forecast(self, event_id: str) -> Optional[Forecast]:
        return next((f for f in self.forecasts if f.event_id == event_id), None)

    # -- Exposure helpers -----------------------------------------------------

    def get_exposures(self, event_id: str) -> list[ExposureResult]:
        return [e for e in self.exposures if e.asset_id]  # all exposures linked to event

    # -- Coastal state --------------------------------------------------------

    def get_coastal_state(self, lat: float, lon: float) -> CoastalState:
        latest = self.get_latest_readings()
        active_events = [e for e in self.events if e.status == "ACTIVE"]
        status = "NORMAL"
        if any(e.severity.value in ("HIGH", "CRITICAL") for e in active_events):
            status = "ALERT"
        elif any(e.severity.value == "MEDIUM" for e in active_events):
            status = "WARNING"
        elif active_events:
            status = "WATCH"

        return CoastalState(
            latitude=lat,
            longitude=lon,
            status=status,
            sensor_count=len(self.get_sensors()),
            active_events=len(active_events),
            marine_data=self.marine_cache,
        )


# Singleton accessor
def get_store() -> DataStore:
    return DataStore()
