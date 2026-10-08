"""
TIDALIS — writes the mocked coastal district to data/geo/coastal_city.geojson.

Run: python -m scripts.generate_geo
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")

from backend.app.geospatial.city_model import as_geojson, BUILDINGS, FACILITIES, ROADS, ZONES

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "geo"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    bundle = as_geojson()

    # One file per layer + the combined bundle
    for name, layer in bundle["layers"].items():
        path = OUT_DIR / f"{name}.geojson"
        path.write_text(json.dumps(layer, indent=2), encoding="utf-8")
        print(f"✓ {path.name}: {len(layer['features'])} features")

    combined = {
        "type": "FeatureCollection",
        "features": [
            feature
            for layer in bundle["layers"].values()
            for feature in layer["features"]
        ],
        "meta": bundle["meta"],
    }
    (OUT_DIR / "coastal_city.geojson").write_text(json.dumps(combined, indent=2), encoding="utf-8")
    print(f"✓ coastal_city.geojson: {len(combined['features'])} features "
          f"({len(ZONES)} zones · {len(ROADS)} roads · {len(BUILDINGS)} buildings · "
          f"{len(FACILITIES)} facilities)")


if __name__ == "__main__":
    main()
