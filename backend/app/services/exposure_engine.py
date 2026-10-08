"""
TIDALIS — Exposure Engine.

Calculates which coastal assets (habitats, fisheries, beaches, ports)
are potentially exposed to a detected event, based on spatial proximity,
asset sensitivity, and event severity.
"""

from __future__ import annotations

import math

from backend.app.models.schemas import (
    CoastalAsset,
    Event,
    ExposureResult,
)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in kilometres."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> str:
    """Rough compass direction from event to asset."""
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    angle = math.degrees(math.atan2(dlon, dlat)) % 360

    directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    idx = int((angle + 22.5) // 45) % 8
    return directions[idx]


def compute_exposure(
    event: Event,
    assets: list[CoastalAsset],
    max_range_km: float = 50.0,
) -> list[ExposureResult]:
    """
    Compute exposure scores for assets within range of an event.

    Exposure = event_severity × spatial_overlap × asset_sensitivity

    Spatial overlap decays with distance: overlap = max(0, 1 - dist/max_range).
    """
    severity_map = {"LOW": 0.3, "MEDIUM": 0.5, "HIGH": 0.8, "CRITICAL": 1.0}
    severity_factor = severity_map.get(event.severity.value, 0.5)

    results: list[ExposureResult] = []
    for asset in assets:
        dist = _haversine_km(event.latitude, event.longitude, asset.latitude, asset.longitude)
        if dist > max_range_km:
            continue

        spatial_overlap = max(0.0, 1.0 - dist / max_range_km)
        exposure = severity_factor * spatial_overlap * asset.sensitivity
        direction = _bearing(event.latitude, event.longitude, asset.latitude, asset.longitude)

        results.append(ExposureResult(
            asset_id=asset.asset_id,
            asset_name=asset.name,
            asset_type=asset.asset_type,
            exposure_score=round(exposure, 3),
            distance_km=round(dist, 2),
            direction=direction,
        ))

    # Sort by exposure score descending
    results.sort(key=lambda r: r.exposure_score, reverse=True)
    return results
