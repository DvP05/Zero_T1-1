"""
TIDALIS — Pydantic models for the unified data schema.

Every data source (Open-Meteo, Copernicus, NASA, IoT sensors) is normalised
into these models before being consumed by the ML / fusion / copilot layers.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class EventStatus(str, Enum):
    ACTIVE = "ACTIVE"
    MONITORING = "MONITORING"
    RESOLVED = "RESOLVED"


class AssetType(str, Enum):
    HABITAT = "HABITAT"
    FISHERY = "FISHERY"
    PORT = "PORT"
    BEACH = "BEACH"
    POPULATION = "POPULATION"
    INDUSTRY = "INDUSTRY"
    TOURISM = "TOURISM"
    CUSTOM_ASSET = "CUSTOM_ASSET"


# ---------------------------------------------------------------------------
# Sensor / Observation
# ---------------------------------------------------------------------------

class SensorReading(BaseModel):
    sensor_id: str
    timestamp: datetime
    latitude: float
    longitude: float
    name: Optional[str] = None
    sensor_type: Optional[str] = None
    zone_id: Optional[str] = None
    temperature: float = 0.0
    turbidity: float = 0.0
    ph: float = 0.0
    dissolved_oxygen: float = 0.0
    water_level_m: Optional[float] = None
    wave_height_m: Optional[float] = None
    precipitation_mm_hr: Optional[float] = None


class Observation(BaseModel):
    id: str = Field(default_factory=lambda: f"obs-{uuid.uuid4().hex[:8]}")
    timestamp: datetime
    latitude: float
    longitude: float
    zone_id: Optional[str] = None
    source: str  # "open_meteo" | "copernicus" | "nasa" | "sensor" | "simulated"
    variables: dict[str, float] = Field(default_factory=dict)
    quality: dict[str, object] = Field(default_factory=lambda: {"valid": True, "source_confidence": 0.9})


# ---------------------------------------------------------------------------
# Anomaly
# ---------------------------------------------------------------------------

class AnomalyScore(BaseModel):
    variable: str
    value: float
    baseline_mean: float
    baseline_std: float
    z_score: float
    anomaly_score: float  # 0..1 normalised


class SensorAnomaly(BaseModel):
    sensor_id: str
    timestamp: datetime
    scores: list[AnomalyScore]
    composite_score: float  # weighted combination


# ---------------------------------------------------------------------------
# Event / Evidence
# ---------------------------------------------------------------------------

class EvidenceItem(BaseModel):
    source: str
    score: float
    reason: str


class Event(BaseModel):
    model_config = {"extra": "allow"}

    event_id: str = Field(default_factory=lambda: f"evt-{uuid.uuid4().hex[:6]}")
    event_type: str = "COASTAL_ANOMALY"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    latitude: float = 0.0
    longitude: float = 0.0
    severity: Severity = Severity.LOW
    confidence: float = 0.0
    status: EventStatus = EventStatus.ACTIVE
    radius_km: float = 5.0
    primary_sensor_id: Optional[str] = None
    affected_zones: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    description: str = ""


# ---------------------------------------------------------------------------
# Forecast
# ---------------------------------------------------------------------------

class ForecastPoint(BaseModel):
    hours_ahead: int
    timestamp: datetime
    predicted_value: float
    lower_bound: float
    upper_bound: float
    variable: str


class Forecast(BaseModel):
    event_id: str
    variable: str
    points: list[ForecastPoint]
    model_name: str = "persistence_fallback"
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Exposure / Assets
# ---------------------------------------------------------------------------

class CoastalAsset(BaseModel):
    asset_id: str
    asset_type: AssetType
    name: str
    latitude: float
    longitude: float
    sensitivity: float = 0.5  # 0..1
    description: str = ""


class ExposureResult(BaseModel):
    asset_id: str
    asset_name: str
    asset_type: AssetType
    exposure_score: float  # 0..1
    distance_km: float
    direction: str = ""


# ---------------------------------------------------------------------------
# Simulation (What-If)
# ---------------------------------------------------------------------------

class WhatIfRequest(BaseModel):
    event_id: str
    duration_hours: int = 24
    current_multiplier: float = 1.0
    wind_multiplier: float = 1.0
    wave_multiplier: float = 1.0


class SimulationStep(BaseModel):
    hours_ahead: int
    latitude: float
    longitude: float
    radius_km: float
    exposure_change_pct: float = 0.0


class WhatIfResult(BaseModel):
    event_id: str
    scenario: WhatIfRequest
    steps: list[SimulationStep]
    total_exposure_change_pct: float = 0.0
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Copilot
# ---------------------------------------------------------------------------

class CopilotRequest(BaseModel):
    message: str
    event_id: Optional[str] = None


class CopilotResponse(BaseModel):
    reply: str
    sources_used: list[str] = Field(default_factory=list)
    event_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Coastal State (aggregated view)
# ---------------------------------------------------------------------------

class CoastalState(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    zone_id: Optional[str] = "goa"
    latitude: float
    longitude: float
    status: str = "NORMAL"  # NORMAL | WATCH | WARNING | ALERT
    sensor_count: int = 0
    active_events: int = 0
    latest_observations: list[Observation] = Field(default_factory=list)
    marine_data: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Incident Report
# ---------------------------------------------------------------------------

class IncidentReport(BaseModel):
    event: Event
    forecast: Optional[Forecast] = None
    exposures: list[ExposureResult] = Field(default_factory=list)
    scenario: Optional[WhatIfResult] = None
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    summary: str = ""


# ---------------------------------------------------------------------------
# Multi-Location & Collection Models
# ---------------------------------------------------------------------------

class CoastalZoneInfo(BaseModel):
    zone_id: str
    name: str
    lat: float
    lon: float
    bbox: list[float]
    coast: str
    nearest_buoy_ids: list[str] = Field(default_factory=list)
    elevation_range_m: list[float] = Field(default_factory=list)
    has_cached_data: bool = False
    sensor_count: int = 0
    status: str = "ONLINE"


class LocationSummary(BaseModel):
    zone_id: str
    name: str
    lat: float
    lon: float
    coast: str
    has_cached_data: bool = False
    sensor_count: int = 0
    status: str = "ONLINE"


class CollectionRequest(BaseModel):
    sources: list[str] = Field(default_factory=lambda: ["open_meteo", "tidalis"])
    scenario: str = "heavy_coastal_rain"


class CollectionStatus(BaseModel):
    zone_id: str
    status: str = "idle"  # idle | running | completed | failed
    message: str = ""
    records_ingested: int = 0
    sources: list[str] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

