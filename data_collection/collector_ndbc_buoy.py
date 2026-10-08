"""
==============================================================================
2. NOAA NDBC BUOY COLLECTOR (FREE - No API Key)
==============================================================================
Collects real-time ocean buoy observations from NOAA's National Data Buoy
Center. For India, these buoys are operated by NIOT/INCOIS but catalogued
by NDBC.

Data includes:
  - Wind speed/direction, gusts
  - Wave height, dominant period, average period
  - Atmospheric pressure, air/water temperature
  - Dew point, visibility
"""

import io
import os
from typing import Dict, List, Optional

import requests
import pandas as pd

from .config import (
    COASTAL_ZONES,
    ENDPOINTS,
    RAW_DATA_DIR,
    CoastalZone,
)


class NDBCBuoyCollector:
    """Collects real-time buoy data from NOAA NDBC (FREE, public)."""

    # NDBC text data column names for standard meteorological data
    MET_COLUMNS = [
        "YY", "MM", "DD", "hh", "mm",
        "WDIR", "WSPD", "GST", "WVHT", "DPD",
        "APD", "MWD", "PRES", "ATMP", "WTMP",
        "DEWP", "VIS", "PTDY", "TIDE",
    ]

    def __init__(self):
        self.base_url = ENDPOINTS["ndbc_realtime"]
        self.session = requests.Session()

    def fetch_station(self, station_id: str) -> Optional[pd.DataFrame]:
        """
        Fetch real-time meteorological data for a single NDBC station.
        Returns last 45 days of hourly observations.

        Args:
            station_id: NDBC station ID (e.g., "23226" for Arabian Sea buoy)
        """
        url = f"{self.base_url}/{station_id}.txt"
        print(f"  [NDBC] Fetching station {station_id} from {url}...")

        try:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
        except requests.exceptions.HTTPError as e:
            if resp.status_code == 404:
                print(f"    -> Station {station_id} not found (404). Skipping.")
                return None
            raise

        # Parse the whitespace-delimited text file
        # First two lines are headers (column names + units)
        lines = resp.text.strip().split("\n")
        if len(lines) < 3:
            print(f"    -> Station {station_id}: no data rows found.")
            return None

        # Read into DataFrame, skip header rows
        df = pd.read_csv(
            io.StringIO(resp.text),
            sep=r"\s+",
            skiprows=[1],  # Skip the units row
            na_values=["MM", "99.00", "999", "9999", "9999.0", "99.0"],
        )

        # Build proper datetime column
        if "#YY" in df.columns:
            df = df.rename(columns={"#YY": "YY"})

        if all(c in df.columns for c in ["YY", "MM", "DD", "hh", "mm"]):
            df["time"] = pd.to_datetime(
                df[["YY", "MM", "DD", "hh", "mm"]].rename(
                    columns={"YY": "year", "MM": "month", "DD": "day", "hh": "hour", "mm": "minute"}
                )
            )
            df = df.drop(columns=["YY", "MM", "DD", "hh", "mm"], errors="ignore")

        df["station_id"] = station_id
        print(f"    -> {len(df)} observations retrieved")
        return df

    def fetch_spectral(self, station_id: str) -> Optional[pd.DataFrame]:
        """Fetch spectral wave summary data for a station."""
        url = f"{self.base_url}/{station_id}.spec"
        print(f"  [NDBC] Fetching spectral data for station {station_id}...")

        try:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
        except requests.exceptions.HTTPError:
            print(f"    -> Spectral data not available for {station_id}.")
            return None

        df = pd.read_csv(
            io.StringIO(resp.text),
            sep=r"\s+",
            skiprows=[1],
            na_values=["MM", "99.00", "999", "9999"],
        )
        df["station_id"] = station_id
        print(f"    -> {len(df)} spectral records retrieved")
        return df

    def collect_for_zone(
        self,
        zone: CoastalZone,
        save: bool = True,
    ) -> Dict[str, pd.DataFrame]:
        """Collect buoy data from all stations near a coastal zone."""
        results = {}
        for station_id in zone.nearest_buoy_ids:
            df = self.fetch_station(station_id)
            if df is not None:
                results[station_id] = df

                if save:
                    out_dir = os.path.join(RAW_DATA_DIR, "ndbc", zone.name.lower().replace(" ", "_"))
                    os.makedirs(out_dir, exist_ok=True)
                    df.to_csv(os.path.join(out_dir, f"station_{station_id}.csv"), index=False)
                    print(f"    -> Saved to {out_dir}/station_{station_id}.csv")

        return results

    def collect_all_zones(
        self,
        zone_keys: Optional[List[str]] = None,
        save: bool = True,
    ) -> Dict[str, Dict[str, pd.DataFrame]]:
        """Collect buoy data for all configured coastal zones."""
        if zone_keys is None:
            zone_keys = list(COASTAL_ZONES.keys())

        all_results = {}
        for key in zone_keys:
            zone = COASTAL_ZONES[key]
            print(f"\n--- Collecting buoy data for {zone.name} ---")
            all_results[key] = self.collect_for_zone(zone, save=save)

        return all_results


if __name__ == "__main__":
    collector = NDBCBuoyCollector()
    results = collector.collect_all_zones(zone_keys=["mumbai"])
    for station_id, df in results.get("mumbai", {}).items():
        print(f"\n=== Station {station_id} Sample ===")
        print(df.head())