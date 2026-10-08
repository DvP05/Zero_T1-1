"""
TIDALIS — Open-Meteo Marine API connector.

Fetches real marine forecast data (wave height, SST, current velocity, etc.)
and normalises it into the TIDALIS internal observation schema.
Falls back to cached demo data if the API is unreachable.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import requests

from backend.app.models.schemas import Observation

logger = logging.getLogger(__name__)

OPEN_METEO_BASE = "https://marine-api.open-meteo.com/v1/marine"

MARINE_VARIABLES = [
    "wave_height",
    "wave_direction",
    "wave_period",
    "sea_surface_temperature",
    "ocean_current_velocity",
    "ocean_current_direction",
]

# Demo fallback data (Goa coast)
DEMO_MARINE_DATA = {
    "hourly": {
        "time": ["2026-10-06T12:00", "2026-10-06T13:00", "2026-10-06T14:00"],
        "wave_height": [1.2, 1.3, 1.4],
        "wave_direction": [245, 248, 250],
        "wave_period": [8.1, 8.0, 7.9],
        "sea_surface_temperature": [29.4, 29.5, 29.7],
        "ocean_current_velocity": [0.42, 0.45, 0.48],
        "ocean_current_direction": [210, 212, 215],
    }
}


def fetch_marine_data(latitude: float, longitude: float, forecast_hours: int = 24) -> dict:
    """
    Fetch marine data from Open-Meteo.  Returns raw JSON dict.
    Falls back to demo data on failure.
    """
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": ",".join(MARINE_VARIABLES),
        "forecast_hours": forecast_hours,
        "timezone": "UTC",
        "cell_selection": "sea",
    }
    try:
        resp = requests.get(OPEN_METEO_BASE, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        logger.info("Open-Meteo data fetched for (%.4f, %.4f)", latitude, longitude)
        return data
    except Exception as exc:
        logger.warning("Open-Meteo unavailable, using demo fallback: %s", exc)
        return DEMO_MARINE_DATA


def normalise_marine_data(raw: dict, latitude: float, longitude: float) -> list[Observation]:
    """Convert Open-Meteo hourly response into TIDALIS Observations."""
    observations: list[Observation] = []
    hourly = raw.get("hourly", {})
    times = hourly.get("time", [])

    for i, time_str in enumerate(times):
        variables: dict[str, float] = {}
        for var in MARINE_VARIABLES:
            values = hourly.get(var, [])
            if i < len(values) and values[i] is not None:
                variables[var] = float(values[i])

        if variables:
            try:
                ts = datetime.fromisoformat(time_str).replace(tzinfo=timezone.utc)
            except ValueError:
                ts = datetime.now(timezone.utc)

            observations.append(Observation(
                timestamp=ts,
                latitude=latitude,
                longitude=longitude,
                source="open_meteo",
                variables=variables,
            ))

    return observations
