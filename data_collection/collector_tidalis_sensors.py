"""
==============================================================================
7. TIDALIS SIMULATED SENSOR NETWORK
==============================================================================
Simulates a coastal IoT sensor network for real-time flood monitoring.

Sensor types:
  - Tide gauges: Real-time water level at key coastal points
  - Rain gauges: Precipitation intensity at distributed locations
  - Flood sensors: Binary wet/dry + depth at critical infrastructure
  - Flow sensors: Storm drain and river discharge rates
  - Water quality: Salinity, turbidity (saltwater intrusion detection)

This simulates WebSocket-like streaming data for the hackathon demo.
"""

import json
import os
import random
import time
from datetime import datetime, timedelta
from typing import Callable, Dict, Generator, List, Optional

import numpy as np
import pandas as pd

from .config import (
    COASTAL_ZONES,
    RAW_DATA_DIR,
    SCENARIO_DURATION_HOURS,
    SCENARIO_TIMESTEP_MINUTES,
    CoastalZone,
)


class TidalisSensorNetwork:
    """
    Simulates a distributed IoT sensor network for coastal flood monitoring.
    Can generate:
      - Static historical dataset (for ML training)
      - Time-series scenario data (for the demo timeline scrubber)
      - Streaming data (for real-time WebSocket simulation)
    """

    SENSOR_TYPES = {
        "tide_gauge": {
            "metrics": ["water_level_m", "water_level_rate_cm_hr"],
            "count_per_zone": 3,
        },
        "rain_gauge": {
            "metrics": ["precipitation_mm_hr", "accumulated_rain_mm"],
            "count_per_zone": 5,
        },
        "flood_sensor": {
            "metrics": ["is_flooded", "flood_depth_m", "time_since_flood_min"],
            "count_per_zone": 8,
        },
        "flow_sensor": {
            "metrics": ["discharge_m3s", "flow_velocity_ms", "capacity_pct"],
            "count_per_zone": 4,
        },
        "water_quality": {
            "metrics": ["salinity_psu", "turbidity_ntu", "ph"],
            "count_per_zone": 2,
        },
    }

    def __init__(self, seed: int = 42):
        np.random.seed(seed)
        random.seed(seed)

    def _deploy_sensors(self, zone: CoastalZone) -> List[Dict]:
        """Deploy virtual sensors across a coastal zone."""
        sensors = []
        sensor_id = 0

        for sensor_type, config in self.SENSOR_TYPES.items():
            for i in range(config["count_per_zone"]):
                lat = round(np.random.uniform(zone.bbox[1], zone.bbox[3]), 6)
                lon = round(np.random.uniform(zone.bbox[0], zone.bbox[2]), 6)
                elevation = round(np.random.uniform(*zone.elevation_range_m), 1)

                sensors.append({
                    "sensor_id": f"TDL-{zone.name[:3].upper()}-{sensor_type[:4].upper()}-{sensor_id:04d}",
                    "type": sensor_type,
                    "lat": lat,
                    "lon": lon,
                    "elevation_m": elevation,
                    "zone": zone.name,
                    "status": "online",
                    "battery_pct": round(random.uniform(60, 100), 1),
                    "last_calibration": (datetime.utcnow() - timedelta(days=random.randint(1, 90))).isoformat(),
                })
                sensor_id += 1

        return sensors

    def generate_scenario_data(
        self,
        zone: CoastalZone,
        duration_hours: int = SCENARIO_DURATION_HOURS,
        timestep_minutes: int = SCENARIO_TIMESTEP_MINUTES,
        scenario: str = "heavy_coastal_rain",
        save: bool = True,
    ) -> Dict:
        """
        Generate a complete time-series dataset for a storm scenario.
        This drives the hackathon demo's timeline scrubber.

        Args:
            zone: Target coastal zone
            duration_hours: Total scenario length
            timestep_minutes: Time between readings
            scenario: Scenario type ("heavy_coastal_rain", "cyclone", "king_tide")
        """
        print(f"  [Tidalis] Deploying sensor network for {zone.name}...")
        sensors = self._deploy_sensors(zone)
        print(f"    -> {len(sensors)} sensors deployed")

        n_steps = (duration_hours * 60) // timestep_minutes + 1
        times = pd.date_range(
            start=datetime.utcnow(),
            periods=n_steps,
            freq=f"{timestep_minutes}min",
        )

        # Scenario intensity curve (0.0 to 1.0)
        t_norm = np.linspace(0, 1, n_steps)
        if scenario == "heavy_coastal_rain":
            # Builds up, peaks at 60%, then slowly recedes
            intensity = np.where(
                t_norm < 0.6,
                t_norm / 0.6,
                1.0 - 0.5 * (t_norm - 0.6) / 0.4,
            )
        elif scenario == "cyclone":
            # Sharp ramp up, sustained peak, sharp drop
            intensity = np.clip(2 * np.sin(np.pi * t_norm) ** 2, 0, 1)
        elif scenario == "king_tide":
            # Gradual sinusoidal with elevated baseline
            intensity = 0.3 + 0.7 * np.sin(np.pi * t_norm)
        else:
            intensity = t_norm

        print(f"  [Tidalis] Generating {scenario} scenario ({n_steps} timesteps)...")

        all_readings = []

        for sensor in sensors:
            for i, (t, inten) in enumerate(zip(times, intensity)):
                reading = {
                    "timestamp": t.isoformat(),
                    "sensor_id": sensor["sensor_id"],
                    "type": sensor["type"],
                    "lat": sensor["lat"],
                    "lon": sensor["lon"],
                    "elevation_m": sensor["elevation_m"],
                    "scenario_intensity": round(inten, 3),
                }

                if sensor["type"] == "tide_gauge":
                    # Tide + storm surge
                    tide = 1.5 * np.sin(2 * np.pi * i / (12 * 60 / timestep_minutes))
                    surge = 2.0 * inten * (1 if zone.coast == "east" else 0.7)
                    level = tide + surge + np.random.normal(0, 0.05)
                    reading["water_level_m"] = round(level, 3)
                    reading["water_level_rate_cm_hr"] = round(np.random.normal(surge * 15, 2), 1)

                elif sensor["type"] == "rain_gauge":
                    # Rainfall intensity
                    base_rain = 80 * inten  # up to 80 mm/hr in extreme
                    rain = max(0, base_rain + np.random.normal(0, 5))
                    reading["precipitation_mm_hr"] = round(rain, 1)
                    reading["accumulated_rain_mm"] = round(rain * (i * timestep_minutes / 60), 1)

                elif sensor["type"] == "flood_sensor":
                    # Flooding depends on elevation vs water level
                    flood_threshold = sensor["elevation_m"] * 0.3
                    flood_level = 3.0 * inten - flood_threshold
                    is_flooded = flood_level > 0
                    reading["is_flooded"] = is_flooded
                    reading["flood_depth_m"] = round(max(0, flood_level + np.random.normal(0, 0.1)), 2)
                    reading["time_since_flood_min"] = int(i * timestep_minutes) if is_flooded else 0

                elif sensor["type"] == "flow_sensor":
                    # Storm drain flow
                    base_flow = 2.0 + 15.0 * inten
                    reading["discharge_m3s"] = round(base_flow + np.random.normal(0, 0.5), 2)
                    reading["flow_velocity_ms"] = round(0.5 + 2.5 * inten + np.random.normal(0, 0.1), 2)
                    reading["capacity_pct"] = min(100, round(30 + 70 * inten + np.random.normal(0, 3), 1))

                elif sensor["type"] == "water_quality":
                    reading["salinity_psu"] = round(5 + 30 * inten + np.random.normal(0, 1), 2)
                    reading["turbidity_ntu"] = round(10 + 200 * inten + np.random.normal(0, 10), 1)
                    reading["ph"] = round(7.5 - 0.5 * inten + np.random.normal(0, 0.1), 2)

                all_readings.append(reading)

        readings_df = pd.DataFrame(all_readings)
        sensors_df = pd.DataFrame(sensors)

        print(f"    -> Generated {len(readings_df)} total readings from {len(sensors)} sensors")

        if save:
            out_dir = os.path.join(RAW_DATA_DIR, "tidalis", zone.name.lower())
            os.makedirs(out_dir, exist_ok=True)
            sensors_df.to_csv(os.path.join(out_dir, "sensor_registry.csv"), index=False)
            readings_df.to_csv(os.path.join(out_dir, f"scenario_{scenario}.csv"), index=False)
            print(f"    -> Saved to {out_dir}/")

        return {
            "sensors": sensors_df,
            "readings": readings_df,
            "metadata": {
                "zone": zone.name,
                "scenario": scenario,
                "duration_hours": duration_hours,
                "timestep_minutes": timestep_minutes,
                "n_sensors": len(sensors),
                "n_readings": len(readings_df),
            },
        }

    def stream_readings(
        self,
        zone: CoastalZone,
        interval_seconds: float = 2.0,
        scenario: str = "heavy_coastal_rain",
    ) -> Generator[Dict, None, None]:
        """
        Generator that yields sensor readings one at a time,
        simulating a real-time WebSocket data stream.

        Usage:
            for reading in network.stream_readings(zone):
                send_to_websocket(reading)
        """
        data = self.generate_scenario_data(zone, save=False, scenario=scenario)
        readings = data["readings"].to_dict("records")

        timestamps = sorted(set(r["timestamp"] for r in readings))

        for ts in timestamps:
            batch = [r for r in readings if r["timestamp"] == ts]
            for reading in batch:
                yield reading
            time.sleep(interval_seconds)


if __name__ == "__main__":
    network = TidalisSensorNetwork()
    zone = COASTAL_ZONES["mumbai"]
    result = network.generate_scenario_data(zone, scenario="heavy_coastal_rain")

    print("\n=== Sensor Registry ===")
    print(result["sensors"][["sensor_id", "type", "lat", "lon", "elevation_m"]].head(10))
    print("\n=== Sample Readings (Tide Gauge) ===")
    tide_data = result["readings"][result["readings"]["type"] == "tide_gauge"]
    print(tide_data[["timestamp", "sensor_id", "water_level_m", "scenario_intensity"]].head(10))