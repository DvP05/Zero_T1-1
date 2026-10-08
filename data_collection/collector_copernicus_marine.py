"""
==============================================================================
5. COPERNICUS MARINE SERVICE COLLECTOR (FREE with registration)
==============================================================================
Accesses ocean data from the Copernicus Marine Environment Monitoring Service.

Key products for Indian coastline:
  - Global Ocean Physics (GLORYS): Currents, temperature, salinity, sea level
  - Global Ocean Waves: Significant wave height, period, direction
  - Indian Ocean regional products

Install: pip install copernicusmarine
Registration: https://marine.copernicus.eu/ (FREE)
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd

from .config import (
    COASTAL_ZONES,
    COPERNICUS_MARINE_USERNAME,
    COPERNICUS_MARINE_PASSWORD,
    RAW_DATA_DIR,
    CoastalZone,
)


class CopernicusMarineCollector:
    """
    Accesses Copernicus Marine data using the copernicusmarine Python toolbox.
    Falls back to simulated data if credentials or library are unavailable.
    """

    # Key product IDs for flood intelligence
    PRODUCTS = {
        "cmems_mod_glo_phy_anfc_0.083deg_PT1H-m": {
            "name": "Global Ocean Physics Analysis (hourly)",
            "variables": ["zos", "uo", "vo", "thetao", "so"],
            "description": "Sea level (zos), currents (uo/vo), temperature, salinity",
        },
        "cmems_mod_glo_wav_anfc_0.083deg_PT3H-i": {
            "name": "Global Ocean Waves (3-hourly)",
            "variables": ["VHM0", "VTPK", "VMDR"],
            "description": "Significant wave height, peak period, mean direction",
        },
    }

    def __init__(self):
        self._cm = None
        self._init_toolbox()

    def _init_toolbox(self):
        """Try to initialize the copernicusmarine toolbox."""
        try:
            import copernicusmarine
            self._cm = copernicusmarine
            print("  [CMEMS] copernicusmarine toolbox loaded.")

            if COPERNICUS_MARINE_USERNAME and COPERNICUS_MARINE_PASSWORD:
                print("  [CMEMS] Credentials found in environment.")
            else:
                print("  [CMEMS] WARNING: No credentials set.")
                print("           Set COPERNICUS_MARINE_USERNAME & COPERNICUS_MARINE_PASSWORD")
        except ImportError:
            print("  [CMEMS] copernicusmarine not installed.")
            print("           Install with: pip install copernicusmarine")
            print("           Falling back to simulated data.")

    def describe_products(self) -> Dict:
        """List available products and their variables."""
        if self._cm is None:
            print("  [CMEMS] Library not available. Returning product catalog only.")
            return self.PRODUCTS

        catalog = self._cm.describe()
        return catalog

    def fetch_ocean_physics(
        self,
        zone: CoastalZone,
        hours_back: int = 24,
        output_dir: Optional[str] = None,
    ) -> Optional[str]:
        """
        Download sea level, currents, and temperature data for a zone.

        Uses the copernicusmarine.subset() function for efficient data extraction.
        """
        if isinstance(zone, str):
            zone = COASTAL_ZONES[zone.lower()]
        if self._cm is None:
            print("  [CMEMS] Cannot fetch real data. Use generate_simulated() instead.")
            return None

        if output_dir is None:
            output_dir = os.path.join(RAW_DATA_DIR, "copernicus_marine", zone.name.lower())
        os.makedirs(output_dir, exist_ok=True)

        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours_back)

        product_id = "cmems_mod_glo_phy_anfc_0.083deg_PT1H-m"
        output_file = os.path.join(output_dir, "ocean_physics.nc")

        print(f"  [CMEMS] Subsetting {product_id} for {zone.name}...")
        print(f"    Bbox: {zone.bbox}, Time: {start_time} to {end_time}")

        try:
            self._cm.subset(
                dataset_id=product_id,
                variables=["zos", "uo", "vo", "thetao"],
                minimum_longitude=zone.bbox[0],
                minimum_latitude=zone.bbox[1],
                maximum_longitude=zone.bbox[2],
                maximum_latitude=zone.bbox[3],
                start_datetime=start_time.isoformat(),
                end_datetime=end_time.isoformat(),
                minimum_depth=0,
                maximum_depth=10,
                output_filename=output_file,
                output_directory=output_dir,
                force_download=True,
                username=COPERNICUS_MARINE_USERNAME,
                password=COPERNICUS_MARINE_PASSWORD,
            )
            print(f"    -> Saved to {output_file}")
            return output_file
        except Exception as e:
            print(f"    -> Error: {e}")
            print("    -> Use generate_simulated() as fallback.")
            return None

    def fetch_wave_data(
        self,
        zone: CoastalZone,
        hours_back: int = 24,
        output_dir: Optional[str] = None,
    ) -> Optional[str]:
        """Download wave data (height, period, direction) for a zone."""
        if self._cm is None:
            return None

        if output_dir is None:
            output_dir = os.path.join(RAW_DATA_DIR, "copernicus_marine", zone.name.lower())
        os.makedirs(output_dir, exist_ok=True)

        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours_back)

        product_id = "cmems_mod_glo_wav_anfc_0.083deg_PT3H-i"
        output_file = os.path.join(output_dir, "ocean_waves.nc")

        print(f"  [CMEMS] Subsetting wave data for {zone.name}...")

        try:
            self._cm.subset(
                dataset_id=product_id,
                variables=["VHM0", "VTPK", "VMDR"],
                minimum_longitude=zone.bbox[0],
                minimum_latitude=zone.bbox[1],
                maximum_longitude=zone.bbox[2],
                maximum_latitude=zone.bbox[3],
                start_datetime=start_time.isoformat(),
                end_datetime=end_time.isoformat(),
                output_filename=output_file,
                output_directory=output_dir,
                force_download=True,
                username=COPERNICUS_MARINE_USERNAME,
                password=COPERNICUS_MARINE_PASSWORD,
            )
            print(f"    -> Saved to {output_file}")
            return output_file
        except Exception as e:
            print(f"    -> Error: {e}")
            return None

    def generate_simulated(
        self,
        zone: CoastalZone,
        hours: int = 48,
        save: bool = True,
    ) -> pd.DataFrame:
        """
        Generate realistic simulated Copernicus Marine data when the real
        API is unavailable. Uses physics-informed random generation.
        """
        import numpy as np

        print(f"  [CMEMS Simulated] Generating {hours}h of ocean data for {zone.name}...")
        np.random.seed(hash(zone.name) % 2**31)

        times = pd.date_range(
            start=datetime.utcnow() - timedelta(hours=hours),
            periods=hours,
            freq="h",
        )

        # Physics-informed parameters based on Indian Ocean conditions
        base_sst = 28.5 if zone.coast == "west" else 29.0  # deg C
        base_sea_level = 0.0  # meters (anomaly from mean)
        base_current_speed = 0.3  # m/s

        # Tidal signal (semi-diurnal M2 + diurnal K1)
        t_hours = np.arange(hours)
        tide_m2 = 0.8 * np.sin(2 * np.pi * t_hours / 12.42)  # M2 tide
        tide_k1 = 0.3 * np.sin(2 * np.pi * t_hours / 23.93)  # K1 tide
        sea_level = base_sea_level + tide_m2 + tide_k1 + np.random.normal(0, 0.05, hours)

        df = pd.DataFrame({
            "time": times,
            "zone": zone.name,
            "lat": zone.lat,
            "lon": zone.lon,
            # Sea level anomaly (meters)
            "sea_level_m": np.round(sea_level, 3),
            # Sea surface temperature
            "sst_celsius": np.round(base_sst + np.random.normal(0, 0.3, hours), 2),
            # Ocean currents
            "current_speed_ms": np.round(
                np.abs(base_current_speed + 0.1 * np.sin(2 * np.pi * t_hours / 12) + np.random.normal(0, 0.05, hours)),
                3
            ),
            "current_direction_deg": np.round(
                (180 + 30 * np.sin(2 * np.pi * t_hours / 24) + np.random.normal(0, 10, hours)) % 360,
                1
            ),
            # Salinity (PSU)
            "salinity_psu": np.round(35.0 + np.random.normal(0, 0.2, hours), 2),
            # Significant wave height
            "wave_height_m": np.round(
                np.abs(1.2 + 0.5 * np.sin(2 * np.pi * t_hours / 18) + np.random.normal(0, 0.15, hours)),
                2
            ),
            # Wave period
            "wave_period_s": np.round(8 + np.random.normal(0, 1.0, hours), 1),
            # Wave direction
            "wave_direction_deg": np.round(
                (220 + np.random.normal(0, 15, hours)) % 360,
                1
            ),
        })

        if save:
            out_dir = os.path.join(RAW_DATA_DIR, "copernicus_marine", zone.name.lower())
            os.makedirs(out_dir, exist_ok=True)
            df.to_csv(os.path.join(out_dir, "simulated_ocean.csv"), index=False)
            print(f"    -> Saved to {out_dir}/simulated_ocean.csv")

        return df


if __name__ == "__main__":
    collector = CopernicusMarineCollector()
    zone = COASTAL_ZONES["mumbai"]
    # Try real data first, fall back to simulated
    result = collector.fetch_ocean_physics(zone)
    if result is None:
        df = collector.generate_simulated(zone, hours=24)
        print("\n=== Simulated Ocean Data (Mumbai) ===")
        print(df.head(10))