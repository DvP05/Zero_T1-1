"""
TIDALIS — Deterministic sensor simulator.

Generates a network of coastal sensors with normal baseline readings
and injects a timed anomaly event for demo purposes.
The simulation is fully deterministic (seeded) so the live demo tells
the same story every time.
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone

from backend.app.models.schemas import SensorReading

# ---------------------------------------------------------------------------
# Sensor network configuration — Goa coast, India
# ---------------------------------------------------------------------------

SENSORS = [
    {"sensor_id": "TIDALIS-001", "lat": 15.2993, "lon": 73.9862, "name": "Miramar Beach"},
    {"sensor_id": "TIDALIS-002", "lat": 15.2760, "lon": 73.9700, "name": "Dona Paula"},
    {"sensor_id": "TIDALIS-003", "lat": 15.2500, "lon": 73.9530, "name": "Bambolim Bay"},
    {"sensor_id": "TIDALIS-004", "lat": 15.3900, "lon": 73.8130, "name": "Calangute"},
    {"sensor_id": "TIDALIS-005", "lat": 15.5400, "lon": 73.7590, "name": "Arambol"},
]

# Baselines (typical healthy coastal values)
BASELINES = {
    "temperature":       {"mean": 29.2, "std": 0.5},
    "turbidity":         {"mean": 8.5,  "std": 2.0},
    "ph":                {"mean": 8.1,  "std": 0.1},
    "dissolved_oxygen":  {"mean": 6.4,  "std": 0.3},
}

# Anomaly injection profile (for sensor TIDALIS-002 — Dona Paula)
ANOMALY_SENSOR = "TIDALIS-002"
ANOMALY_PROFILE = {
    "temperature":       {"peak": 31.2,  "delta": 2.0},
    "turbidity":         {"peak": 43.7,  "delta": 35.0},
    "ph":                {"peak": 7.6,   "delta": -0.5},
    "dissolved_oxygen":  {"peak": 5.0,   "delta": -1.4},
}


def _noise(seed: int, scale: float = 0.1) -> float:
    """Deterministic small noise."""
    rng = random.Random(seed)
    return rng.gauss(0, scale)


def _anomaly_factor(hours_offset: float) -> float:
    """
    Returns 0.0 during normal period, ramps up to 1.0 at the peak.

    Timeline:
      T-24h to T-6h  → normal (factor ~0)
      T-6h  to T-0   → ramp up (factor 0 → 1)
      T+0   to T+24h → sustained high (factor ~1.0, slight decay)
    """
    if hours_offset < -6:
        return 0.0
    elif hours_offset < 0:
        # Ramp: -6 → 0  maps to  0.0 → 1.0
        return (hours_offset + 6) / 6.0
    else:
        # Sustained with very slight decay
        return max(0.0, 1.0 - hours_offset * 0.005)


def generate_sensor_readings(
    reference_time: datetime | None = None,
    hours_range: int = 48,
    interval_minutes: int = 60,
) -> list[SensorReading]:
    """
    Generate a full timeline of sensor readings for all sensors.

    The `reference_time` is "T-0" — the moment the anomaly fully manifests.
    Readings are generated from `reference_time - 24h` to `reference_time + 24h`
    (total 48 hours by default).
    """
    if reference_time is None:
        reference_time = datetime.now(timezone.utc)

    start = reference_time - timedelta(hours=hours_range // 2)
    readings: list[SensorReading] = []
    steps = (hours_range * 60) // interval_minutes

    for step_i in range(steps + 1):
        ts = start + timedelta(minutes=step_i * interval_minutes)
        hours_offset = (ts - reference_time).total_seconds() / 3600.0

        for sensor_cfg in SENSORS:
            sid = sensor_cfg["sensor_id"]
            seed_base = hash((sid, step_i))

            is_anomaly_sensor = sid == ANOMALY_SENSOR
            factor = _anomaly_factor(hours_offset) if is_anomaly_sensor else 0.0

            vals: dict[str, float] = {}
            for var_name, baseline in BASELINES.items():
                base_val = baseline["mean"] + _noise(seed_base + hash(var_name), baseline["std"] * 0.15)
                if is_anomaly_sensor and factor > 0:
                    delta = ANOMALY_PROFILE[var_name]["delta"]
                    base_val += delta * factor
                vals[var_name] = round(base_val, 2)

            readings.append(SensorReading(
                sensor_id=sid,
                timestamp=ts,
                latitude=sensor_cfg["lat"],
                longitude=sensor_cfg["lon"],
                temperature=vals["temperature"],
                turbidity=vals["turbidity"],
                ph=vals["ph"],
                dissolved_oxygen=vals["dissolved_oxygen"],
            ))

    return readings


def get_sensor_metadata() -> list[dict]:
    """Return metadata for all sensors in the simulated network."""
    return [
        {
            "sensor_id": s["sensor_id"],
            "name": s["name"],
            "latitude": s["lat"],
            "longitude": s["lon"],
            "status": "ONLINE",
        }
        for s in SENSORS
    ]
