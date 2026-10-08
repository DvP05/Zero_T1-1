"""
TIDALIS — What-If Simulation Engine.

Simplified advection-style model for scenario visualisation.
Moves an event's position based on current + wind vectors over time.
This is a scenario engine, NOT a validated hydrodynamic simulation.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

from backend.app.models.schemas import (
    Event,
    SimulationStep,
    WhatIfRequest,
    WhatIfResult,
)

# Base environmental vectors for Goa coast (demo defaults)
BASE_CURRENT = {"speed_ms": 0.42, "direction_deg": 211}  # m/s, degrees from north
BASE_WIND = {"speed_ms": 3.5, "direction_deg": 245}
WIND_FACTOR = 0.03  # wind influence on drift


def _deg_to_rad(deg: float) -> float:
    return deg * math.pi / 180.0


def _velocity_components(speed: float, direction_deg: float) -> tuple[float, float]:
    """Convert speed + compass direction to (vx, vy) in m/s."""
    rad = _deg_to_rad(direction_deg)
    vx = speed * math.sin(rad)  # east-west
    vy = speed * math.cos(rad)  # north-south
    return vx, vy


def _metres_to_deg_lat(metres: float) -> float:
    return metres / 111_320.0


def _metres_to_deg_lon(metres: float, latitude: float) -> float:
    return metres / (111_320.0 * math.cos(_deg_to_rad(latitude)))


def run_what_if(event: Event, request: WhatIfRequest) -> WhatIfResult:
    """
    Run a simplified advection simulation.

    Propagates the event location based on current and wind vectors,
    modified by the user's multipliers.
    """
    # Apply multipliers
    current_speed = BASE_CURRENT["speed_ms"] * request.current_multiplier
    wind_speed = BASE_WIND["speed_ms"] * request.wind_multiplier

    # Velocity components
    cx, cy = _velocity_components(current_speed, BASE_CURRENT["direction_deg"])
    wx, wy = _velocity_components(wind_speed, BASE_WIND["direction_deg"])

    # Combined drift velocity (m/s)
    vx = cx + WIND_FACTOR * wx
    vy = cy + WIND_FACTOR * wy

    # Time steps: 1h, 3h, 6h, 12h, 24h
    time_steps = [1, 3, 6, 12, 24]
    time_steps = [h for h in time_steps if h <= request.duration_hours]
    if request.duration_hours not in time_steps:
        time_steps.append(request.duration_hours)

    lat = event.latitude
    lon = event.longitude
    base_radius = event.radius_km
    steps: list[SimulationStep] = []

    for h in time_steps:
        dt_seconds = h * 3600
        dx = vx * dt_seconds
        dy = vy * dt_seconds

        new_lat = lat + _metres_to_deg_lat(dy)
        new_lon = lon + _metres_to_deg_lon(dx, lat)

        # Radius grows slightly with time and wave multiplier
        new_radius = base_radius * (1.0 + 0.02 * h * request.wave_multiplier)

        # Exposure change estimate (percent)
        exposure_change = (
            (request.current_multiplier - 1.0) * 50 +
            (request.wind_multiplier - 1.0) * 30 +
            (request.wave_multiplier - 1.0) * 20
        ) * (h / 24.0)

        steps.append(SimulationStep(
            hours_ahead=h,
            latitude=round(new_lat, 6),
            longitude=round(new_lon, 6),
            radius_km=round(new_radius, 2),
            exposure_change_pct=round(exposure_change, 1),
        ))

    total_change = steps[-1].exposure_change_pct if steps else 0.0

    return WhatIfResult(
        event_id=request.event_id,
        scenario=request,
        steps=steps,
        total_exposure_change_pct=total_change,
    )
