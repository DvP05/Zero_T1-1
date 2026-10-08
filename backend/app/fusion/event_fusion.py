"""
TIDALIS — Event Fusion Engine.

Combines anomaly signals from multiple independent sources
(sensors, ocean state, satellite-derived, historical) into a single
high-confidence coastal event with evidence items.
"""

from __future__ import annotations

from datetime import datetime, timezone

from backend.app.models.schemas import (
    Event,
    EvidenceItem,
    Severity,
    SensorAnomaly,
)

# Source weights for fusion
FUSION_WEIGHTS = {
    "sensor": 0.30,
    "ocean": 0.20,
    "satellite": 0.20,
    "historical": 0.15,
    "weather": 0.15,
}


def _classify_severity(confidence: float) -> Severity:
    if confidence >= 0.85:
        return Severity.HIGH
    elif confidence >= 0.65:
        return Severity.MEDIUM
    elif confidence >= 0.40:
        return Severity.LOW
    return Severity.LOW


def _generate_reason(source: str, score: float) -> str:
    """Generate a human-readable evidence reason."""
    reasons = {
        "sensor": {
            "high": "Sensor readings significantly above local baseline — turbidity and temperature deviation detected",
            "medium": "Moderate sensor deviation from baseline values",
            "low": "Slight sensor readings deviation from normal range",
        },
        "ocean": {
            "high": "Ocean current behaviour differs substantially from recent baseline",
            "medium": "Moderate ocean-state deviation detected",
            "low": "Minor ocean-state variation observed",
        },
        "satellite": {
            "high": "Independent environmental signal is strongly consistent with anomaly",
            "medium": "Satellite-derived signal partially supports anomaly",
            "low": "Weak satellite-derived signal detected",
        },
        "historical": {
            "high": "Pattern is highly unusual compared to historical records for this location and season",
            "medium": "Pattern differs moderately from historical norms",
            "low": "Minor historical deviation observed",
        },
        "weather": {
            "high": "Weather conditions strongly correlate with observed anomaly",
            "medium": "Weather conditions partially support the anomaly pattern",
            "low": "Minimal weather correlation",
        },
    }

    level = "high" if score >= 0.75 else "medium" if score >= 0.50 else "low"
    return reasons.get(source, {}).get(level, f"{source} signal at {score:.0%}")


def fuse_event(
    sensor_anomaly: SensorAnomaly,
    ocean_score: float = 0.0,
    satellite_score: float = 0.0,
    historical_score: float = 0.0,
    weather_score: float = 0.0,
    latitude: float = 0.0,
    longitude: float = 0.0,
) -> Event:
    """
    Fuse multiple anomaly signals into a single Event.

    `sensor_anomaly` provides the IoT signal.
    Other scores can come from external connectors or be simulated.
    """
    signals = {
        "sensor": sensor_anomaly.composite_score,
        "ocean": ocean_score,
        "satellite": satellite_score,
        "historical": historical_score,
        "weather": weather_score,
    }

    # Weighted confidence
    confidence = sum(
        signals[name] * FUSION_WEIGHTS[name]
        for name in FUSION_WEIGHTS
    )
    confidence = round(min(confidence * 1.15, 1.0), 4)  # slight boost, cap at 1

    # Build evidence list
    evidence: list[EvidenceItem] = []
    for source, score in signals.items():
        if score > 0.1:
            evidence.append(EvidenceItem(
                source=source,
                score=round(score, 2),
                reason=_generate_reason(source, score),
            ))

    # Sort evidence by score descending
    evidence.sort(key=lambda e: e.score, reverse=True)

    severity = _classify_severity(confidence)

    description = (
        f"Multi-source coastal anomaly detected with {confidence:.0%} confidence. "
        f"{len(evidence)} independent observation streams support this event."
    )

    return Event(
        event_type="COASTAL_ANOMALY",
        timestamp=sensor_anomaly.timestamp,
        latitude=latitude or 15.2760,
        longitude=longitude or 73.9700,
        severity=severity,
        confidence=confidence,
        evidence=evidence,
        description=description,
        radius_km=round(5.0 + confidence * 5.0, 1),
    )
