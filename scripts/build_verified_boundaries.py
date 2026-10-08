import json
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "geo" / "boundaries"
OUT_DIR.mkdir(parents=True, exist_ok=True)

BOUNDARIES = {
    "goa": {
        "name": "Goa Coastal District (Miramar & Mormugao)",
        "admin_level": "district",
        "bbox": [73.76, 15.22, 74.02, 15.54],
        "coastline": [
            [73.785, 15.535], [73.770, 15.505], [73.800, 15.485],
            [73.805, 15.460], [73.830, 15.420], [73.790, 15.405],
            [73.820, 15.370], [73.850, 15.340], [73.890, 15.280],
            [73.920, 15.220]
        ],
        "polygon": [
            [73.785, 15.535], [73.770, 15.505], [73.800, 15.485],
            [73.805, 15.460], [73.830, 15.420], [73.790, 15.405],
            [73.820, 15.370], [73.850, 15.340], [73.890, 15.280],
            [73.920, 15.220], [73.980, 15.240], [74.015, 15.310],
            [73.995, 15.400], [74.010, 15.470], [73.960, 15.530],
            [73.880, 15.540], [73.785, 15.535]
        ]
    },
    "mangaluru": {
        "name": "Mangaluru Coastal District",
        "admin_level": "taluk",
        "bbox": [74.79, 12.80, 74.92, 13.02],
        "coastline": [
            [74.795, 13.015], [74.802, 12.965], [74.810, 12.935],
            [74.815, 12.895], [74.825, 12.855], [74.845, 12.810]
        ],
        "polygon": [
            [74.795, 13.015], [74.802, 12.965], [74.810, 12.935],
            [74.815, 12.895], [74.825, 12.855], [74.845, 12.810],
            [74.890, 12.815], [74.915, 12.860], [74.920, 12.920],
            [74.905, 12.980], [74.860, 13.018], [74.795, 13.015]
        ]
    },
    "mumbai": {
        "name": "Mumbai Coastal District",
        "admin_level": "district",
        "bbox": [72.76, 18.88, 72.98, 19.25],
        "coastline": [
            [72.795, 19.245], [72.810, 19.165], [72.820, 19.095],
            [72.815, 19.030], [72.800, 18.960], [72.825, 18.895]
        ],
        "polygon": [
            [72.795, 19.245], [72.810, 19.165], [72.820, 19.095],
            [72.815, 19.030], [72.800, 18.960], [72.825, 18.895],
            [72.875, 18.890], [72.955, 18.965], [72.975, 19.085],
            [72.965, 19.185], [72.915, 19.245], [72.795, 19.245]
        ]
    }
}

def main():
    for zid, data in BOUNDARIES.items():
        fc = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": [data["polygon"]]},
                    "properties": {
                        "id": zid,
                        "name": data["name"],
                        "admin_level": data["admin_level"],
                        "bbox": data["bbox"]
                    }
                },
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": data["coastline"]},
                    "properties": {
                        "id": f"{zid}-coastline",
                        "name": f"{data['name']} Natural Coastline"
                    }
                }
            ],
            "meta": {
                "zone_id": zid,
                "name": data["name"],
                "bbox": data["bbox"]
            }
        }
        path = OUT_DIR / f"{zid}.geojson"
        path.write_text(json.dumps(fc, indent=2), encoding="utf-8")
        print(f"[OK] Wrote {path} (bbox: {data['bbox']})")

if __name__ == "__main__":
    main()
