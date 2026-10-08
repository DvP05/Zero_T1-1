"""
TIDALIS — Demo data seeder.

Populates the in-memory data store with a full deterministic timeline:
  T-24h  → normal
  T-6h   → anomaly developing
  T-0    → high-confidence event
  T+24h  → forecast projection

Run: python -m scripts.seed_demo_data
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure the project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Windows consoles default to cp1252 — force UTF-8 so emoji output works
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")

from backend.app.services.data_store import get_store
from backend.app.services.sensor_simulator import generate_sensor_readings, ANOMALY_SENSOR
from backend.app.ml.anomaly_engine import detect_anomalies, compute_sensor_anomaly
from backend.app.ml.forecast_engine import generate_forecast
from backend.app.fusion.event_fusion import fuse_event
from backend.app.services.exposure_engine import compute_exposure


def seed() -> None:
    store = get_store()
    ref_time = datetime.now(timezone.utc)
    store.reference_time = ref_time

    print("🌊 TIDALIS Demo Data Seeder")
    print(f"   Reference time (T-0): {ref_time.isoformat()}")
    print()

    # 1. Generate sensor readings
    readings = generate_sensor_readings(reference_time=ref_time)
    store.sensor_readings = readings
    print(f"✓ Generated {len(readings)} sensor readings across {len(set(r.sensor_id for r in readings))} sensors")

    # 2. Detect anomalies
    latest_readings = store.get_latest_readings()
    anomalies = detect_anomalies(latest_readings, threshold=0.40)
    print(f"✓ Detected {len(anomalies)} anomalies (threshold 0.40)")

    for a in anomalies:
        print(f"  ⚠ {a.sensor_id}: composite={a.composite_score:.2%}")

    # 3. Fuse events from anomalies
    for anomaly in anomalies:
        sensor = next(
            (r for r in latest_readings if r.sensor_id == anomaly.sensor_id),
            None,
        )
        lat = sensor.latitude if sensor else 15.2760
        lon = sensor.longitude if sensor else 73.9700

        # Simulate correlated signals from other sources
        is_primary = anomaly.sensor_id == ANOMALY_SENSOR
        ocean_score = 0.82 if is_primary else anomaly.composite_score * 0.6
        satellite_score = 0.76 if is_primary else anomaly.composite_score * 0.4
        historical_score = 0.83 if is_primary else anomaly.composite_score * 0.5
        weather_score = 0.68 if is_primary else anomaly.composite_score * 0.3

        event = fuse_event(
            sensor_anomaly=anomaly,
            ocean_score=ocean_score,
            satellite_score=satellite_score,
            historical_score=historical_score,
            weather_score=weather_score,
            latitude=lat,
            longitude=lon,
        )
        store.events.append(event)
        print(f"✓ Event {event.event_id}: severity={event.severity.value}, confidence={event.confidence:.0%}")

        # 4. Generate forecast for primary event
        sensor_readings = store.get_sensor_observations(anomaly.sensor_id)
        forecast = generate_forecast(
            readings=sensor_readings,
            variable="turbidity",
            hours_ahead=24,
            event_id=event.event_id,
        )
        store.forecasts.append(forecast)
        print(f"✓ Forecast generated for {event.event_id} ({len(forecast.points)} points)")

        # 5. Compute exposure
        exposures = compute_exposure(event, store.assets, max_range_km=30.0)
        store.exposures.extend(exposures)
        print(f"✓ {len(exposures)} assets within exposure range")
        for exp in exposures[:3]:
            print(f"  → {exp.asset_name}: exposure={exp.exposure_score:.0%}, dist={exp.distance_km:.1f}km")

    print()
    print(f"🎯 Total events: {len(store.events)}")
    print(f"🗺️ Total exposed assets: {len(store.exposures)}")
    print("✅ Demo data ready!")


if __name__ == "__main__":
    seed()
