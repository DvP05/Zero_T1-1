"""
==============================================================================
1. OPEN-METEO MARINE & WEATHER COLLECTOR (FREE - No API Key)
==============================================================================
Collects:
  - Hourly weather: temperature, humidity, precipitation, wind, pressure
  - Hourly marine: wave_height, wave_direction, wave_period, swell, ocean_current
  - Sea level height (tidal proxy)

This is the PRIMARY real-time data source for the hackathon demo.
"""

import json
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests
import pandas as pd

from .config import (
    COASTAL_ZONES,
    ENDPOINTS,
    RAW_DATA_DIR,
    CoastalZone,
)


class OpenMeteoCollector:
    """Collects weather + marine data from Open-Meteo (FREE, no API key)."""

    def __init__(self):
        self.weather_url = ENDPOINTS["open_meteo_weather"]
        self.marine_url = ENDPOINTS["open_meteo_marine"]
        self.session = requests.Session()

    # ------------------------------------------------------------------
    # Weather Data
    # ------------------------------------------------------------------
    def fetch_weather(
        self,
        zone: CoastalZone,
        forecast_days: int = 3,
    ) -> pd.DataFrame:
        """
        Fetch hourly atmospheric weather data for a coastal zone.

        Returns DataFrame with columns:
            time, temperature_2m, relative_humidity_2m, precipitation,
            rain, pressure_msl, surface_pressure, wind_speed_10m,
            wind_direction_10m, wind_gusts_10m, cloud_cover
        """
        params = {
            "latitude": zone.lat,
            "longitude": zone.lon,
            "hourly": ",".join([
                "temperature_2m",
                "relative_humidity_2m",
                "precipitation",
                "rain",
                "pressure_msl",
                "surface_pressure",
                "wind_speed_10m",
                "wind_direction_10m",
                "wind_gusts_10m",
                "cloud_cover",
            ]),
            "forecast_days": forecast_days,
            "timezone": "Asia/Kolkata",
        }

        print(f"  [Open-Meteo Weather] Fetching for {zone.name} ({zone.lat}, {zone.lon})...")
        resp = self.session.get(self.weather_url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        df = pd.DataFrame(data["hourly"])
        df["time"] = pd.to_datetime(df["time"])
        df["zone"] = zone.name
        df["lat"] = zone.lat
        df["lon"] = zone.lon
        print(f"    -> {len(df)} hourly records retrieved")
        return df

    # ------------------------------------------------------------------
    # Marine Data
    # ------------------------------------------------------------------
    def fetch_marine(
        self,
        zone: CoastalZone,
        forecast_days: int = 3,
    ) -> pd.DataFrame:
        """
        Fetch hourly marine/ocean data for a coastal zone.

        Returns DataFrame with columns:
            time, wave_height, wave_direction, wave_period,
            wind_wave_height, wind_wave_direction, wind_wave_period,
            swell_wave_height, swell_wave_direction, swell_wave_period,
            ocean_current_velocity, ocean_current_direction
        """
        params = {
            "latitude": zone.lat,
            "longitude": zone.lon,
            "hourly": ",".join([
                "wave_height",
                "wave_direction",
                "wave_period",
                "wind_wave_height",
                "wind_wave_direction",
                "wind_wave_period",
                "swell_wave_height",
                "swell_wave_direction",
                "swell_wave_period",
                "ocean_current_velocity",
                "ocean_current_direction",
            ]),
            "forecast_days": forecast_days,
            "timezone": "Asia/Kolkata",
        }

        print(f"  [Open-Meteo Marine] Fetching for {zone.name} ({zone.lat}, {zone.lon})...")
        resp = self.session.get(self.marine_url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        df = pd.DataFrame(data["hourly"])
        df["time"] = pd.to_datetime(df["time"])
        df["zone"] = zone.name
        df["lat"] = zone.lat
        df["lon"] = zone.lon
        print(f"    -> {len(df)} hourly records retrieved")
        return df

    # ------------------------------------------------------------------
    # Collect All Zones
    # ------------------------------------------------------------------
    def collect_all_zones(
        self,
        zone_keys: Optional[List[str]] = None,
        forecast_days: int = 3,
        save: bool = True,
    ) -> Dict[str, Dict[str, pd.DataFrame]]:
        """
        Collect weather + marine data for multiple coastal zones.

        Returns:
            {
                "mumbai": {"weather": df, "marine": df},
                "chennai": {"weather": df, "marine": df},
                ...
            }
        """
        if zone_keys is None:
            zone_keys = list(COASTAL_ZONES.keys())

        results = {}
        for key in zone_keys:
            zone = COASTAL_ZONES[key]
            weather_df = self.fetch_weather(zone, forecast_days)
            time.sleep(0.5)  # Be nice to the free API
            marine_df = self.fetch_marine(zone, forecast_days)
            time.sleep(0.5)

            results[key] = {"weather": weather_df, "marine": marine_df}

            if save:
                out_dir = os.path.join(RAW_DATA_DIR, "open_meteo", key)
                os.makedirs(out_dir, exist_ok=True)
                weather_df.to_csv(os.path.join(out_dir, "weather.csv"), index=False)
                marine_df.to_csv(os.path.join(out_dir, "marine.csv"), index=False)
                print(f"    -> Saved to {out_dir}/")

        return results


# ------------------------------------------------------------------
# Quick CLI usage
# ------------------------------------------------------------------
if __name__ == "__main__":
    collector = OpenMeteoCollector()
    # Collect just Mumbai for a quick test
    result = collector.collect_all_zones(zone_keys=["mumbai"], forecast_days=2)
    print("\n=== Sample Weather Data (Mumbai) ===")
    print(result["mumbai"]["weather"].head())
    print("\n=== Sample Marine Data (Mumbai) ===")
    print(result["mumbai"]["marine"].head())