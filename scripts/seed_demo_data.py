"""
Seed demo data for TIDALIS hackathon demo.
Populates DataStore with realistic sensor readings, an active fused event,
and predictive forecasts.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from backend.app.fusion.event_fusion import fuse_event
from backend.app.ml.anomaly_engine import compute_sensor_anomaly
from backend.app.ml.forecast_engine import generate_forecast
from backend.app.services.data_store import get_store
from backend.app.services.sensor_simulator import generate_sensor_readings

logger = logging.getLogger(__name__)


def seed() -> None:
    """Populate DataStore with initial demo readings, events, and forecasts."""
    store = get_store()

    # 1. Generate sensor readings for Goa baseline network
    readings = generate_sensor_readings(
        reference_time=datetime.now(timezone.utc),
        hours_range=48,
        interval_minutes=60,
    )
    store.sensor_readings = readings

    # 2. Find anomalous readings and fuse into an active flood/spill event
    anomalous_reading = next(
        (r for r in reversed(readings) if r.sensor_id == "TIDALIS-002" and r.turbidity > 20.0),
        readings[-1] if readings else None,
    )

    if anomalous_reading:
        anomaly = compute_sensor_anomaly(anomalous_reading)
        event = fuse_event(
            sensor_anomaly=anomaly,
            ocean_score=0.82,
            satellite_score=0.76,
            historical_score=0.85,
            weather_score=0.70,
            latitude=anomalous_reading.latitude,
            longitude=anomalous_reading.longitude,
        )
        event.description = "Severe tidal surge and turbidity anomaly detected near Dona Paula & Miramar coast"
        store.events = [event]

        # 3. Generate forecast for the anomalous event
        sensor_obs = store.get_sensor_observations("TIDALIS-002")
        if sensor_obs:
            forecast = generate_forecast(
                readings=sensor_obs[-24:],
                variable="turbidity",
                hours_ahead=12,
                event_id=event.event_id,
            )
            store.forecasts = [forecast]

    logger.info("Demo data seeded: %d readings, %d events", len(store.sensor_readings), len(store.events))


if __name__ == "__main__":
    seed()
