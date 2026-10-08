"""
TIDALIS — Critical-path unit tests.

Covers the five highest-value functions per the README testing strategy:
anomaly score, fusion score, forecast generation, simulation movement,
and exposure calculation.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app.models.schemas import SensorReading, WhatIfRequest
from backend.app.ml.anomaly_engine import compute_sensor_anomaly, robust_z_score
from backend.app.ml.forecast_engine import generate_forecast
from backend.app.fusion.event_fusion import fuse_event
from backend.app.services.exposure_engine import compute_exposure
from backend.app.services.data_store import get_store
from backend.app.simulation.what_if import run_what_if


def _reading(
    sensor_id: str = "TEST-01",
    temperature: float = 29.2,
    turbidity: float = 8.5,
    ph: float = 8.1,
    dissolved_oxygen: float = 6.4,
) -> SensorReading:
    return SensorReading(
        sensor_id=sensor_id,
        timestamp=datetime.now(timezone.utc),
        latitude=15.276,
        longitude=73.97,
        temperature=temperature,
        turbidity=turbidity,
        ph=ph,
        dissolved_oxygen=dissolved_oxygen,
    )


# ---------------------------------------------------------------------------
# Anomaly
# ---------------------------------------------------------------------------

def test_robust_z_score_ranges():
    assert 0.0 <= robust_z_score(29.2, 29.2, 1.0) <= 1.0
    assert robust_z_score(100.0, 0.0, 1.0) > 0.9


def test_anomaly_increases_with_turbidity():
    normal = compute_sensor_anomaly(_reading(turbidity=8.0))
    abnormal = compute_sensor_anomaly(_reading(turbidity=40.0))
    assert abnormal.composite_score > normal.composite_score
    assert normal.composite_score < 0.5


# ---------------------------------------------------------------------------
# Fusion
# ---------------------------------------------------------------------------

def test_fusion_confidence_and_ordering():
    anomaly = compute_sensor_anomaly(
        _reading(temperature=31.2, turbidity=43.7, ph=7.6, dissolved_oxygen=5.0)
    )
    event = fuse_event(
        sensor_anomaly=anomaly,
        ocean_score=0.82,
        satellite_score=0.76,
        historical_score=0.83,
        weather_score=0.68,
        latitude=15.276,
        longitude=73.97,
    )
    assert 0.0 <= event.confidence <= 1.0
    assert event.confidence > 0.5
    scores = [e.score for e in event.evidence]
    assert scores == sorted(scores, reverse=True)


def test_fusion_high_severity_for_strong_signals():
    anomaly = compute_sensor_anomaly(
        _reading(temperature=31.2, turbidity=43.7, ph=7.6, dissolved_oxygen=5.0)
    )
    event = fuse_event(anomaly, 0.9, 0.9, 0.9, 0.9)
    assert event.severity.value == "HIGH"


# ---------------------------------------------------------------------------
# Forecast
# ---------------------------------------------------------------------------

def test_forecast_generates_points_and_follows_trend():
    now = datetime.now(timezone.utc)
    readings = [
        SensorReading(
            sensor_id="TEST-01",
            timestamp=now + timedelta(hours=i),
            latitude=15.276,
            longitude=73.97,
            turbidity=8.0 + i,
        )
        for i in range(12)
    ]
    forecast = generate_forecast(
        readings=readings,
        variable="turbidity",
        hours_ahead=6,
        event_id="evt-test",
    )
    assert len(forecast.points) == 6
    assert forecast.model_name == "persistence_trend"
    assert forecast.points[-1].predicted_value > readings[-1].turbidity
    assert forecast.points[-1].upper_bound >= forecast.points[-1].predicted_value


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

def test_simulation_pushes_event_downstream():
    anomaly = compute_sensor_anomaly(_reading(turbidity=43.7))
    event = fuse_event(anomaly, 0.8, 0.7, 0.8, 0.6, latitude=15.276, longitude=73.97)

    base = run_what_if(event, WhatIfRequest(event_id=event.event_id))
    boosted = run_what_if(
        event,
        WhatIfRequest(event_id=event.event_id, current_multiplier=2.0),
    )

    assert len(base.steps) == 5
    assert boosted.steps[-1].exposure_change_pct > base.steps[-1].exposure_change_pct
    # Stronger current should displace the event further from the origin
    base_end = base.steps[-1]
    boosted_end = boosted.steps[-1]
    dist_base = abs(base_end.latitude - event.latitude) + abs(base_end.longitude - event.longitude)
    dist_boosted = abs(boosted_end.latitude - event.latitude) + abs(boosted_end.longitude - event.longitude)
    assert dist_boosted > dist_base


# ---------------------------------------------------------------------------
# Exposure
# ---------------------------------------------------------------------------

def test_exposure_ranks_nearby_high_sensitivity_assets_first():
    store = get_store()
    anomaly = compute_sensor_anomaly(_reading(turbidity=43.7))
    event = fuse_event(anomaly, 0.8, 0.7, 0.8, 0.6, latitude=15.3, longitude=73.97)

    exposures = compute_exposure(event, store.assets, max_range_km=50.0)
    assert exposures == sorted(exposures, key=lambda e: e.exposure_score, reverse=True)
    assert all(0.0 <= e.exposure_score <= 1.0 for e in exposures)


def test_exposure_excludes_distant_assets():
    store = get_store()
    anomaly = compute_sensor_anomaly(_reading(turbidity=43.7))
    event = fuse_event(anomaly, 0.8, 0.7, 0.8, 0.6, latitude=15.3, longitude=73.97)
    exposures = compute_exposure(event, store.assets, max_range_km=1.0)
    # Only assets very close to the event survive a tiny range
    assert all(e.distance_km <= 1.0 for e in exposures)