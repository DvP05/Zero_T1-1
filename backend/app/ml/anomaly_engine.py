"""
TIDALIS — Anomaly Detection Engine.

Two strategies:
  A) Robust Z-Score  — fast, explainable, always available.
  B) Isolation Forest — ML-based, secondary signal.

Both produce normalised anomaly scores in [0, 1].
"""

from __future__ import annotations

import math
from datetime import datetime

from backend.app.models.schemas import AnomalyScore, SensorAnomaly, SensorReading
from backend.app.services.sensor_simulator import BASELINES

# Weights for combining per-variable anomaly scores into a composite score
COMPOSITE_WEIGHTS = {
    "temperature": 0.25,
    "turbidity": 0.35,
    "ph": 0.15,
    "dissolved_oxygen": 0.25,
}


def _sigmoid(x: float) -> float:
    """Squash any real value into [0, 1]."""
    return 1.0 / (1.0 + math.exp(-x))


def robust_z_score(value: float, mean: float, std: float) -> float:
    """
    Compute a robust anomaly score using modified z-score.
    Uses MAD-equivalent (std × 0.6745) for robustness.
    Returns a normalised score in [0, 1] via sigmoid.
    """
    if std == 0:
        return 0.0
    mad = std * 0.6745
    z = abs(value - mean) / mad
    # Sigmoid centred so z=2 ≈ 0.73, z=3 ≈ 0.88, z=4 ≈ 0.95
    return round(_sigmoid(z - 2.0), 4)


def compute_sensor_anomaly(reading: SensorReading) -> SensorAnomaly:
    """
    Compute anomaly scores for all variables of a single sensor reading.
    Returns a SensorAnomaly with per-variable scores and a weighted composite.
    """
    scores: list[AnomalyScore] = []
    weighted_sum = 0.0
    weight_total = 0.0

    for var_name, baseline in BASELINES.items():
        value = getattr(reading, var_name, None)
        if value is None:
            continue

        z_raw = abs(value - baseline["mean"]) / (baseline["std"] * 0.6745) if baseline["std"] > 0 else 0.0
        score = robust_z_score(value, baseline["mean"], baseline["std"])

        scores.append(AnomalyScore(
            variable=var_name,
            value=value,
            baseline_mean=baseline["mean"],
            baseline_std=baseline["std"],
            z_score=round(z_raw, 3),
            anomaly_score=score,
        ))

        w = COMPOSITE_WEIGHTS.get(var_name, 0.25)
        weighted_sum += score * w
        weight_total += w

    composite = round(weighted_sum / weight_total, 4) if weight_total > 0 else 0.0

    return SensorAnomaly(
        sensor_id=reading.sensor_id,
        timestamp=reading.timestamp,
        scores=scores,
        composite_score=composite,
    )


def detect_anomalies(readings: list[SensorReading], threshold: float = 0.55) -> list[SensorAnomaly]:
    """
    Run anomaly detection on a list of sensor readings.
    Returns only readings whose composite score exceeds `threshold`.
    """
    anomalies: list[SensorAnomaly] = []
    for r in readings:
        sa = compute_sensor_anomaly(r)
        if sa.composite_score >= threshold:
            anomalies.append(sa)
    return anomalies
