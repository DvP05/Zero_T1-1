"""
==============================================================================
MASTER DATA COLLECTION PIPELINE
==============================================================================
Orchestrates all data collectors to build a complete dataset for the
Coastal Flood Intelligence Platform.

Usage:
    python -m data_collection.pipeline --zone mumbai --all
    python -m data_collection.pipeline --zone chennai --free-only
    python -m data_collection.pipeline --all-zones --all
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

from .config import COASTAL_ZONES, RAW_DATA_DIR, PROCESSED_DATA_DIR
from .collector_open_meteo import OpenMeteoCollector
from .collector_ndbc_buoy import NDBCBuoyCollector
from .collector_copernicus_sentinel import CopernicusSentinelCollector
from .collector_nasa_earthdata import NASAEarthdataCollector
from .collector_copernicus_marine import CopernicusMarineCollector
from .collector_worldview_sim import WorldViewSimulator
from .collector_tidalis_sensors import TidalisSensorNetwork


class DataCollectionPipeline:
    """
    Master orchestrator for all data sources.
    Collects, validates, and saves data from all configured APIs.
    """

    def __init__(self):
        self.open_meteo = OpenMeteoCollector()
        self.ndbc = NDBCBuoyCollector()
        self.copernicus_sentinel = CopernicusSentinelCollector()
        self.nasa = NASAEarthdataCollector()
        self.copernicus_marine = CopernicusMarineCollector()
        self.worldview = WorldViewSimulator()
        self.tidalis = TidalisSensorNetwork()
        self.run_log = []

    def _log(self, source: str, status: str, message: str, count: int = 0):
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "source": source,
            "status": status,
            "message": message,
            "record_count": count,
        }
        self.run_log.append(entry)
        icon = "OK" if status == "success" else "WARN" if status == "warning" else "ERR"
        print(f"[{icon}] {source}: {message}")

    # ==================================================================
    # FREE API COLLECTORS (no API key required)
    # ==================================================================

    def collect_open_meteo(self, zone_keys: List[str]) -> Dict:
        """Collect Open-Meteo weather + marine data (FREE)."""
        print("\n" + "=" * 60)
        print("  OPEN-METEO: Weather + Marine Data (FREE)")
        print("=" * 60)
        try:
            results = self.open_meteo.collect_all_zones(zone_keys=zone_keys)
            total = sum(
                len(v["weather"]) + len(v["marine"])
                for v in results.values()
            )
            self._log("open_meteo", "success", f"Collected weather+marine for {len(results)} zones", total)
            return results
        except Exception as e:
            self._log("open_meteo", "error", str(e))
            return {}

    def collect_ndbc_buoys(self, zone_keys: List[str]) -> Dict:
        """Collect NOAA NDBC buoy observations (FREE)."""
        print("\n" + "=" * 60)
        print("  NOAA NDBC: Buoy Observations (FREE)")
        print("=" * 60)
        try:
            results = self.ndbc.collect_all_zones(zone_keys=zone_keys)
            total = sum(
                len(df) for zone_data in results.values() for df in zone_data.values()
            )
            self._log("ndbc_buoy", "success", f"Collected buoy data for {len(results)} zones", total)
            return results
        except Exception as e:
            self._log("ndbc_buoy", "error", str(e))
            return {}

    # ==================================================================
    # FREE WITH REGISTRATION
    # ==================================================================

    def collect_copernicus_sentinel(self, zone_keys: List[str]) -> Dict:
        """Search Copernicus Sentinel imagery (FREE with registration)."""
        print("\n" + "=" * 60)
        print("  COPERNICUS SENTINEL: Satellite Imagery Search (FREE+reg)")
        print("=" * 60)
        results = {}
        for key in zone_keys:
            zone = COASTAL_ZONES[key]
            try:
                data = self.copernicus_sentinel.search_all_sensors(zone, days_back=14)
                results[key] = data
                total = sum(len(items) for items in data.values())
                self._log("copernicus_sentinel", "success", f"{zone.name}: {total} imagery items found", total)
            except Exception as e:
                self._log("copernicus_sentinel", "warning", f"{zone.name}: {e}")
        return results

    def collect_nasa_earthdata(self, zone_keys: List[str]) -> Dict:
        """Search NASA CMR for flood datasets (FREE with registration)."""
        print("\n" + "=" * 60)
        print("  NASA EARTHDATA: Flood Dataset Search (FREE+reg)")
        print("=" * 60)
        results = {}
        for key in zone_keys:
            zone = COASTAL_ZONES[key]
            try:
                data = self.nasa.search_all_flood_datasets(zone, days_back=7)
                results[key] = data
                total = sum(len(items) for items in data.values())
                self._log("nasa_earthdata", "success", f"{zone.name}: {total} granules found", total)
            except Exception as e:
                self._log("nasa_earthdata", "warning", f"{zone.name}: {e}")
        return results

    def collect_copernicus_marine(self, zone_keys: List[str]) -> Dict:
        """Fetch Copernicus Marine ocean data (FREE+reg, falls back to simulated)."""
        print("\n" + "=" * 60)
        print("  COPERNICUS MARINE: Ocean Physics + Waves (FREE+reg)")
        print("=" * 60)
        results = {}
        for key in zone_keys:
            zone = COASTAL_ZONES[key]
            try:
                physics = self.copernicus_marine.fetch_ocean_physics(zone)
                if physics is None:
                    # Fall back to simulated
                    df = self.copernicus_marine.generate_simulated(zone, hours=48)
                    results[key] = {"simulated": df}
                    self._log("copernicus_marine", "warning",
                             f"{zone.name}: Using simulated data ({len(df)} rows)", len(df))
                else:
                    results[key] = {"real": physics}
                    self._log("copernicus_marine", "success", f"{zone.name}: Real data downloaded")
            except Exception as e:
                self._log("copernicus_marine", "error", f"{zone.name}: {e}")
        return results

    # ==================================================================
    # SIMULATED / PAID API ALTERNATIVES
    # ==================================================================

    def collect_worldview(self, zone_keys: List[str]) -> Dict:
        """Generate simulated WorldView satellite products."""
        print("\n" + "=" * 60)
        print("  WORLDVIEW: Satellite Products (SIMULATED)")
        print("=" * 60)
        results = {}
        for key in zone_keys:
            zone = COASTAL_ZONES[key]
            data = self.worldview.collect_all(zone)
            results[key] = data
            n_buildings = len(data["building_footprints"])
            n_floods = len(data["flood_extents"])
            self._log("worldview_sim", "success",
                      f"{zone.name}: {n_buildings} buildings, {n_floods} flood zones",
                      n_buildings + n_floods)
        return results

    def collect_tidalis_sensors(
        self,
        zone_keys: List[str],
        scenario: str = "heavy_coastal_rain",
    ) -> Dict:
        """Generate Tidalis sensor network data."""
        print("\n" + "=" * 60)
        print("  TIDALIS: IoT Sensor Network (SIMULATED)")
        print("=" * 60)
        results = {}
        for key in zone_keys:
            zone = COASTAL_ZONES[key]
            data = self.tidalis.generate_scenario_data(zone, scenario=scenario)
            results[key] = data
            self._log("tidalis_sensors", "success",
                      f"{zone.name}: {data['metadata']['n_sensors']} sensors, "
                      f"{data['metadata']['n_readings']} readings",
                      data["metadata"]["n_readings"])
        return results

    # ==================================================================
    # FULL PIPELINE
    # ==================================================================

    def run_full_pipeline(
        self,
        zone_keys: Optional[List[str]] = None,
        free_only: bool = False,
        scenario: str = "heavy_coastal_rain",
    ) -> Dict:
        """
        Run the complete data collection pipeline.

        Args:
            zone_keys: List of zone keys to collect for (None = all)
            free_only: If True, only use free APIs (no registration needed)
            scenario: Storm scenario for simulated data
        """
        if zone_keys is None:
            zone_keys = list(COASTAL_ZONES.keys())

        start_time = time.time()
        print("\n" + "#" * 70)
        print("  COASTAL FLOOD INTELLIGENCE - DATA COLLECTION PIPELINE")
        print(f"  Zones: {', '.join(zone_keys)}")
        print(f"  Mode: {'Free APIs only' if free_only else 'All sources (free + registered + simulated)'}")
        print(f"  Started: {datetime.utcnow().isoformat()}")
        print("#" * 70)

        all_results = {}

        # 1. Free APIs (always run)
        all_results["open_meteo"] = self.collect_open_meteo(zone_keys)
        all_results["ndbc_buoy"] = self.collect_ndbc_buoys(zone_keys)

        if not free_only:
            # 2. Free with registration
            all_results["copernicus_sentinel"] = self.collect_copernicus_sentinel(zone_keys)
            all_results["nasa_earthdata"] = self.collect_nasa_earthdata(zone_keys)
            all_results["copernicus_marine"] = self.collect_copernicus_marine(zone_keys)

            # 3. Simulated (paid alternatives)
            all_results["worldview"] = self.collect_worldview(zone_keys)
            all_results["tidalis"] = self.collect_tidalis_sensors(zone_keys, scenario)

        elapsed = time.time() - start_time

        # Save run log
        log_path = os.path.join(RAW_DATA_DIR, "pipeline_log.json")
        with open(log_path, "w") as f:
            json.dump({
                "run_time": datetime.utcnow().isoformat(),
                "elapsed_seconds": round(elapsed, 1),
                "zones": zone_keys,
                "free_only": free_only,
                "log": self.run_log,
            }, f, indent=2)

        # Summary
        print("\n" + "#" * 70)
        print("  PIPELINE COMPLETE")
        print(f"  Elapsed: {elapsed:.1f}s")
        print(f"  Log: {log_path}")
        print("#" * 70)
        print("\n  Results Summary:")
        for entry in self.run_log:
            icon = "OK" if entry["status"] == "success" else "!!" if entry["status"] == "warning" else "XX"
            print(f"    [{icon}] {entry['source']}: {entry['message']}")

        return all_results


# ==================================================================
# CLI Entry Point
# ==================================================================
def main():
    parser = argparse.ArgumentParser(
        description="Coastal Flood Intelligence Data Collection Pipeline"
    )
    parser.add_argument(
        "--zone", "-z",
        type=str,
        default=None,
        help="Specific zone key (e.g., mumbai, chennai). Default: all zones.",
    )
    parser.add_argument(
        "--all-zones",
        action="store_true",
        help="Collect data for all configured coastal zones.",
    )
    parser.add_argument(
        "--free-only",
        action="store_true",
        help="Only use free APIs (no registration required).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all collectors (free + registered + simulated).",
    )
    parser.add_argument(
        "--scenario",
        type=str,
        default="heavy_coastal_rain",
        choices=["heavy_coastal_rain", "cyclone", "king_tide"],
        help="Storm scenario for simulated data.",
    )

    args = parser.parse_args()

    zone_keys = None
    if args.zone:
        if args.zone not in COASTAL_ZONES:
            print(f"Error: Unknown zone '{args.zone}'. Available: {list(COASTAL_ZONES.keys())}")
            sys.exit(1)
        zone_keys = [args.zone]
    elif not args.all_zones:
        zone_keys = ["mumbai"]  # Default to Mumbai for quick testing

    pipeline = DataCollectionPipeline()
    pipeline.run_full_pipeline(
        zone_keys=zone_keys,
        free_only=args.free_only,
        scenario=args.scenario,
    )


if __name__ == "__main__":
    main()