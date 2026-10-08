"""
==============================================================================
6. WORLDVIEW / MAXAR SATELLITE SIMULATOR (Paid API - Simulated)
==============================================================================
Maxar WorldView is a commercial satellite service (now Vantor Hub).
Since it requires a paid commercial account, we simulate realistic
high-resolution satellite metadata and derived products.

Simulates:
  - High-res optical imagery metadata (30cm resolution)
  - Building footprint extraction
  - Flood extent polygons from SAR analysis
  - Coastal erosion change detection
"""

import json
import os
import random
from datetime import datetime, timedelta
from typing import Dict, List

import pandas as pd
import numpy as np

from .config import (
    COASTAL_ZONES,
    RAW_DATA_DIR,
    CoastalZone,
)


class WorldViewSimulator:
    """
    Simulates Maxar WorldView satellite data products.
    Generates realistic metadata and derived geospatial features
    that would come from high-resolution commercial satellite imagery.
    """

    def __init__(self, seed: int = 42):
        np.random.seed(seed)
        random.seed(seed)

    def generate_imagery_catalog(
        self,
        zone: CoastalZone,
        days_back: int = 90,
        max_items: int = 15,
    ) -> List[Dict]:
        """
        Simulate a WorldView imagery catalog search result.
        Mimics what the Vantor Hub Discovery (STAC) API would return.
        """
        print(f"  [WorldView Sim] Generating imagery catalog for {zone.name}...")

        items = []
        base_time = datetime.utcnow()

        satellites = ["WorldView-3", "WorldView-Legion-1", "WorldView-Legion-2"]
        bands = ["PAN", "MS", "SWIR"]

        for i in range(max_items):
            acq_time = base_time - timedelta(
                days=random.randint(1, days_back),
                hours=random.randint(0, 23),
            )

            cloud = round(random.uniform(0, 80), 1)
            off_nadir = round(random.uniform(0, 30), 1)

            item = {
                "id": f"WV-{zone.name[:3].upper()}-{acq_time.strftime('%Y%m%d')}-{i:04d}",
                "satellite": random.choice(satellites),
                "acquisition_time": acq_time.isoformat(),
                "cloud_cover_pct": cloud,
                "off_nadir_angle": off_nadir,
                "resolution_m": 0.31 if "Legion" in satellites[0] else 0.30,
                "bands": random.choice(bands),
                "bbox": list(zone.bbox),
                "area_sqkm": round(
                    (zone.bbox[2] - zone.bbox[0]) * (zone.bbox[3] - zone.bbox[1]) * 12321,
                    2,
                ),
                "sun_elevation": round(random.uniform(30, 75), 1),
                "quality_score": round(random.uniform(0.7, 1.0), 3),
            }
            items.append(item)

        items.sort(key=lambda x: x["acquisition_time"], reverse=True)
        print(f"    -> Generated {len(items)} simulated catalog entries")
        return items

    def generate_building_footprints(
        self,
        zone: CoastalZone,
        num_buildings: int = 200,
    ) -> pd.DataFrame:
        """
        Simulate building footprint extraction from high-res imagery.
        This is a key input for the 3D digital twin.
        """
        print(f"  [WorldView Sim] Generating {num_buildings} building footprints for {zone.name}...")

        lats = np.random.uniform(zone.bbox[1], zone.bbox[3], num_buildings)
        lons = np.random.uniform(zone.bbox[0], zone.bbox[2], num_buildings)

        building_types = ["residential", "commercial", "industrial", "hospital",
                         "school", "government", "shelter", "warehouse"]
        type_weights = [0.50, 0.20, 0.10, 0.03, 0.05, 0.04, 0.03, 0.05]

        heights = []
        footprint_areas = []
        types = np.random.choice(building_types, num_buildings, p=type_weights)

        for bt in types:
            if bt == "residential":
                heights.append(round(np.random.uniform(3, 30), 1))
                footprint_areas.append(round(np.random.uniform(50, 300), 0))
            elif bt == "commercial":
                heights.append(round(np.random.uniform(10, 60), 1))
                footprint_areas.append(round(np.random.uniform(200, 2000), 0))
            elif bt == "hospital":
                heights.append(round(np.random.uniform(15, 40), 1))
                footprint_areas.append(round(np.random.uniform(500, 5000), 0))
            elif bt == "shelter":
                heights.append(round(np.random.uniform(5, 15), 1))
                footprint_areas.append(round(np.random.uniform(100, 1000), 0))
            else:
                heights.append(round(np.random.uniform(5, 25), 1))
                footprint_areas.append(round(np.random.uniform(100, 800), 0))

        df = pd.DataFrame({
            "building_id": [f"BLD-{zone.name[:3].upper()}-{i:05d}" for i in range(num_buildings)],
            "lat": np.round(lats, 6),
            "lon": np.round(lons, 6),
            "building_type": types,
            "height_m": heights,
            "footprint_area_sqm": footprint_areas,
            "floors": [max(1, int(h / 3.2)) for h in heights],
            "elevation_m": np.round(np.random.uniform(*zone.elevation_range_m, num_buildings), 1),
            "is_critical": [t in ("hospital", "shelter", "government", "school") for t in types],
            "estimated_occupancy": [int(a * h / 30) for a, h in zip(footprint_areas, heights)],
        })

        print(f"    -> {len(df)} buildings generated ({df['is_critical'].sum()} critical facilities)")
        return df

    def generate_flood_extent_polygons(
        self,
        zone: CoastalZone,
        num_zones: int = 8,
        scenario_severity: float = 0.7,
    ) -> List[Dict]:
        """
        Simulate SAR-derived flood extent polygons.
        These represent areas identified as flooded from satellite imagery.
        """
        print(f"  [WorldView Sim] Generating {num_zones} flood extent zones for {zone.name}...")

        flood_zones = []
        for i in range(num_zones):
            center_lat = np.random.uniform(zone.bbox[1], zone.bbox[3])
            center_lon = np.random.uniform(zone.bbox[0], zone.bbox[2])
            radius = np.random.uniform(0.005, 0.02) * scenario_severity

            # Generate a rough polygon around the center
            angles = np.linspace(0, 2 * np.pi, 8, endpoint=False)
            coords = []
            for angle in angles:
                r = radius * (0.7 + 0.3 * np.random.random())
                lat = center_lat + r * np.cos(angle)
                lon = center_lon + r * np.sin(angle)
                coords.append([round(lon, 6), round(lat, 6)])
            coords.append(coords[0])  # Close the polygon

            flood_zones.append({
                "zone_id": f"FLOOD-{zone.name[:3].upper()}-{i:03d}",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [coords],
                },
                "properties": {
                    "flood_depth_m": round(np.random.uniform(0.1, 3.0) * scenario_severity, 2),
                    "confidence": round(np.random.uniform(0.6, 0.98), 3),
                    "detection_time": (datetime.utcnow() - timedelta(hours=np.random.randint(1, 12))).isoformat(),
                    "water_source": np.random.choice(["coastal_surge", "rainfall_runoff", "river_overflow"]),
                    "severity": np.random.choice(["low", "moderate", "high", "critical"],
                                                 p=[0.2, 0.3, 0.3, 0.2]),
                },
            })

        print(f"    -> Generated {len(flood_zones)} flood extent polygons")
        return flood_zones

    def collect_all(
        self,
        zone: CoastalZone,
        save: bool = True,
    ) -> Dict:
        """Generate all simulated WorldView products for a zone."""
        catalog = self.generate_imagery_catalog(zone)
        buildings = self.generate_building_footprints(zone)
        flood_extents = self.generate_flood_extent_polygons(zone)

        if save:
            out_dir = os.path.join(RAW_DATA_DIR, "worldview", zone.name.lower())
            os.makedirs(out_dir, exist_ok=True)

            with open(os.path.join(out_dir, "imagery_catalog.json"), "w") as f:
                json.dump(catalog, f, indent=2, default=str)

            buildings.to_csv(os.path.join(out_dir, "building_footprints.csv"), index=False)

            geojson = {
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "geometry": fz["geometry"], "properties": fz["properties"], "id": fz["zone_id"]}
                    for fz in flood_extents
                ],
            }
            with open(os.path.join(out_dir, "flood_extents.geojson"), "w") as f:
                json.dump(geojson, f, indent=2)

            print(f"\n  -> All WorldView data saved to {out_dir}/")

        return {
            "imagery_catalog": catalog,
            "building_footprints": buildings,
            "flood_extents": flood_extents,
        }


if __name__ == "__main__":
    sim = WorldViewSimulator()
    zone = COASTAL_ZONES["mumbai"]
    results = sim.collect_all(zone)
    print("\n=== Building Footprints Sample ===")
    print(results["building_footprints"].head())