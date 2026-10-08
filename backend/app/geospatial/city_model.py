"""
TIDALIS — Mocked coastal city digital twin (GeoJSON source of truth).

Defines the fictional-but-realistic coastal district used by the
"Heavy Coastal Rain Event" scenario:

  * 5 flood zones (A-E) with terrain, drainage and land-use attributes
  * a road network graph (nodes + edges) with per-segment elevation
  * building footprints with extrusion heights for the 3D map
  * critical facilities (hospital, school, shelter, substation, port...)

Everything is deterministic so the demo always renders identically.
"""

from __future__ import annotations

import random
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Zone(BaseModel):
    id: str
    name: str
    polygon: list[list[float]]  # GeoJSON ring [lon, lat]
    centroid: list[float]
    elevation_m: float          # mean ground level above MSL
    drainage_capacity: float    # 0..1 (1 = fully operational)
    historical_flood_freq: float  # 0..1
    imperviousness: float       # 0..1 (share of sealed surface)
    slope: float                # degrees
    population: int
    vulnerability: float        # 0..1


class RoadSegment(BaseModel):
    id: str
    name: str
    from_node: str
    to_node: str
    elevation_m: float
    geometry: list[list[float]]  # LineString coordinates
    lanes: int = 2
    critical: bool = False       # emergency egress route


class RoadNode(BaseModel):
    id: str
    name: str
    coordinates: list[float]
    is_hub: bool = False   # evacuation hub on high ground
    elevation_m: float = 0.0


class Building(BaseModel):
    id: str
    zone_id: str
    polygon: list[list[float]]
    height_m: float
    floors: int
    usage: str  # residential | commercial | industrial


class Facility(BaseModel):
    id: str
    name: str
    kind: str  # hospital | school | shelter | substation | port | fire_station
    zone_id: str
    coordinates: list[float]
    criticality: float  # 0..1


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def _rect(lon_min: float, lat_min: float, lon_max: float, lat_max: float) -> list[list[float]]:
    return [
        [lon_min, lat_min],
        [lon_max, lat_min],
        [lon_max, lat_max],
        [lon_min, lat_max],
        [lon_min, lat_min],
    ]


def _centroid(ring: list[list[float]]) -> list[float]:
    pts = ring[:-1] if ring[0] == ring[-1] else ring
    return [round(sum(p[0] for p in pts) / len(pts), 6),
            round(sum(p[1] for p in pts) / len(pts), 6)]


# ---------------------------------------------------------------------------
# Zones
# ---------------------------------------------------------------------------

def _zone(
    zone_id: str,
    name: str,
    lon_min: float,
    lat_min: float,
    lon_max: float,
    lat_max: float,
    **kwargs,
) -> Zone:
    poly = _rect(lon_min, lat_min, lon_max, lat_max)
    return Zone(id=zone_id, name=name, polygon=poly, centroid=_centroid(poly), **kwargs)


ZONES: list[Zone] = [
    # --- West Coast focus area ---
    _zone(
        "A", "Zone A · Coastal Waterfront",
        73.930, 15.315, 73.966, 15.345,
        elevation_m=1.40, drainage_capacity=0.74, historical_flood_freq=0.34,
        imperviousness=0.62, slope=1.6, population=14200, vulnerability=0.42,
    ),
    _zone(
        "B", "Zone B · Low-lying Estuary",
        73.930, 15.283, 73.966, 15.315,
        elevation_m=1.05, drainage_capacity=0.58, historical_flood_freq=0.61,
        imperviousness=0.71, slope=0.9, population=21800, vulnerability=0.78,
    ),
    _zone(
        "C", "Zone C · South Harbour",
        73.930, 15.251, 73.966, 15.283,
        elevation_m=1.70, drainage_capacity=0.66, historical_flood_freq=0.41,
        imperviousness=0.55, slope=1.9, population=9600, vulnerability=0.51,
    ),
    _zone(
        "D", "Zone D · Upland North",
        73.966, 15.315, 74.002, 15.345,
        elevation_m=4.60, drainage_capacity=0.88, historical_flood_freq=0.08,
        imperviousness=0.44, slope=4.7, population=11300, vulnerability=0.22,
    ),
    _zone(
        "E", "Zone E · Inland East",
        73.966, 15.283, 74.002, 15.315,
        elevation_m=3.30, drainage_capacity=0.81, historical_flood_freq=0.15,
        imperviousness=0.50, slope=3.4, population=16700, vulnerability=0.30,
    ),
    # --- Major Coastal Hubs (Simplified representative zones) ---
    _zone(
        "MUM", "Zone Mumbai · Marine Drive",
        72.80, 18.90, 72.85, 19.10,
        elevation_m=2.5, drainage_capacity=0.45, historical_flood_freq=0.85,
        imperviousness=0.95, slope=0.5, population=120000, vulnerability=0.65,
    ),
    _zone(
        "CHN", "Zone Chennai · Marina Beach",
        80.25, 13.00, 80.30, 13.10,
        elevation_m=2.0, drainage_capacity=0.55, historical_flood_freq=0.70,
        imperviousness=0.85, slope=0.8, population=85000, vulnerability=0.72,
    ),
    _zone(
        "KOC", "Zone Kochi · Fort Kochi",
        76.20, 9.90, 76.30, 10.00,
        elevation_m=1.2, drainage_capacity=0.60, historical_flood_freq=0.75,
        imperviousness=0.65, slope=0.4, population=45000, vulnerability=0.68,
    ),
    _zone(
        "VIZ", "Zone Vizag · RK Beach",
        83.25, 17.65, 83.35, 17.75,
        elevation_m=3.5, drainage_capacity=0.70, historical_flood_freq=0.30,
        imperviousness=0.70, slope=2.5, population=55000, vulnerability=0.40,
    ),
    _zone(
        "KOL", "Zone Kolkata · Haldia Port",
        88.00, 22.00, 88.15, 22.10,
        elevation_m=1.5, drainage_capacity=0.40, historical_flood_freq=0.90,
        imperviousness=0.80, slope=0.2, population=95000, vulnerability=0.82,
    ),
]

ZONE_BY_ID: dict[str, Zone] = {z.id: z for z in ZONES}


# ---------------------------------------------------------------------------
# Road network graph
# ---------------------------------------------------------------------------

# Node positions (zone centroids + the evacuation interchange on high ground)
NODE_COORDS: dict[str, list[float]] = {
    "N-A": [73.948, 15.330],
    "N-B": [73.948, 15.299],
    "N-C": [73.948, 15.267],
    "N-D": [73.984, 15.330],
    "N-E": [73.984, 15.299],
    "N-HUB": [74.022, 15.300],
}

ROAD_NODES: list[RoadNode] = [
    RoadNode(id="N-A", name="Miramar Junction", coordinates=NODE_COORDS["N-A"], elevation_m=1.6),
    RoadNode(id="N-B", name="Estuary Crossroads", coordinates=NODE_COORDS["N-B"], elevation_m=1.2),
    RoadNode(id="N-C", name="Harbour Gate", coordinates=NODE_COORDS["N-C"], elevation_m=1.9),
    RoadNode(id="N-D", name="Upland Circle", coordinates=NODE_COORDS["N-D"], elevation_m=4.8),
    RoadNode(id="N-E", name="Inland Depot", coordinates=NODE_COORDS["N-E"], elevation_m=3.5),
    RoadNode(
        id="N-HUB",
        name="NH-48 Evacuation Interchange",
        coordinates=NODE_COORDS["N-HUB"],
        is_hub=True,
        elevation_m=8.5,
    ),
]

ROADS: list[RoadSegment] = [
    RoadSegment(
        id="RD-01", name="Coastal Road North",
        from_node="N-A", to_node="N-B", elevation_m=1.15, lanes=2,
        geometry=[NODE_COORDS["N-A"], [73.940, 15.316], NODE_COORDS["N-B"]],
    ),
    RoadSegment(
        id="RD-02", name="Coastal Road South",
        from_node="N-B", to_node="N-C", elevation_m=1.00, lanes=2,
        geometry=[NODE_COORDS["N-B"], [73.939, 15.282], NODE_COORDS["N-C"]],
    ),
    RoadSegment(
        id="RD-03", name="Miramar Uplink",
        from_node="N-A", to_node="N-D", elevation_m=2.40, lanes=3, critical=True,
        geometry=[NODE_COORDS["N-A"], [73.968, 15.332], NODE_COORDS["N-D"]],
    ),
    RoadSegment(
        id="RD-04", name="Bandra Connector",
        from_node="N-B", to_node="N-E", elevation_m=1.90, lanes=3, critical=True,
        geometry=[NODE_COORDS["N-B"], [73.967, 15.301], NODE_COORDS["N-E"]],
    ),
    RoadSegment(
        id="RD-05", name="Estuary Ring Road",
        from_node="N-C", to_node="N-E", elevation_m=2.10, lanes=2, critical=True,
        geometry=[NODE_COORDS["N-C"], [73.967, 15.269], NODE_COORDS["N-E"]],
    ),
    RoadSegment(
        id="RD-06", name="Inland Bypass",
        from_node="N-D", to_node="N-E", elevation_m=5.20, lanes=4,
        geometry=[NODE_COORDS["N-D"], [73.986, 15.314], NODE_COORDS["N-E"]],
    ),
    RoadSegment(
        id="RD-07", name="NH-48 North Approach",
        from_node="N-D", to_node="N-HUB", elevation_m=8.00, lanes=4, critical=True,
        geometry=[NODE_COORDS["N-D"], [74.004, 15.316], NODE_COORDS["N-HUB"]],
    ),
    RoadSegment(
        id="RD-08", name="NH-48 East Spur",
        from_node="N-E", to_node="N-HUB", elevation_m=7.50, lanes=4, critical=True,
        geometry=[NODE_COORDS["N-E"], [74.005, 15.300], NODE_COORDS["N-HUB"]],
    ),
    RoadSegment(
        id="RD-09", name="Ridge Hill Road",
        from_node="N-B", to_node="N-D", elevation_m=2.90, lanes=2, critical=True,
        geometry=[NODE_COORDS["N-B"], [73.960, 15.312], [73.972, 15.322], NODE_COORDS["N-D"]],
    ),
]

# Which zone a road node belongs to (hub belongs to none)
NODE_ZONE: dict[str, Optional[str]] = {
    "N-A": "A", "N-B": "B", "N-C": "C", "N-D": "D", "N-E": "E", "N-HUB": None,
}


# ---------------------------------------------------------------------------
# Buildings (deterministic pseudo-random footprints inside each zone)
# ---------------------------------------------------------------------------

_USAGE_BY_ZONE = {
    "A": ["residential", "commercial", "residential"],
    "B": ["residential", "residential", "commercial"],
    "C": ["residential", "industrial", "residential"],
    "D": ["residential", "commercial", "residential"],
    "E": ["residential", "industrial", "commercial"],
    "MUM": ["commercial", "residential", "tourism"],
    "CHN": ["residential", "commercial", "port"],
    "KOC": ["tourism", "residential", "industrial"],
    "VIZ": ["industrial", "commercial", "residential"],
    "KOL": ["port", "industrial", "commercial"],
}


def _build_buildings() -> list[Building]:
    rng = random.Random(1337)
    buildings: list[Building] = []
    for zone in ZONES:
        lon_min = min(p[0] for p in zone.polygon)
        lon_max = max(p[0] for p in zone.polygon)
        lat_min = min(p[1] for p in zone.polygon)
        lat_max = max(p[1] for p in zone.polygon)

        cells = 3
        for i in range(cells):
            for j in range(cells):
                # Skip a couple of cells so the footprints do not form a perfect grid
                if rng.random() < 0.18:
                    continue
                span_lon = (lon_max - lon_min) / cells
                span_lat = (lat_max - lat_min) / cells
                w = span_lon * rng.uniform(0.45, 0.75)
                h = span_lat * rng.uniform(0.45, 0.75)
                origin_lon = lon_min + i * span_lon + span_lon * 0.15
                origin_lat = lat_min + j * span_lat + span_lat * 0.15
                floors = rng.randint(2, 9) if zone.id in ("A", "B", "E") else rng.randint(2, 12)
                buildings.append(
                    Building(
                        id=f"BLD-{zone.id}-{len(buildings) % 100:02d}",
                        zone_id=zone.id,
                        polygon=_rect(origin_lon, origin_lat, origin_lon + w, origin_lat + h),
                        height_m=round(floors * 3.2 + rng.uniform(0, 4), 1),
                        floors=floors,
                        usage=rng.choice(_USAGE_BY_ZONE[zone.id]),
                    )
                )
    return buildings


BUILDINGS: list[Building] = _build_buildings()


# ---------------------------------------------------------------------------
# Critical facilities
# ---------------------------------------------------------------------------

FACILITIES: list[Facility] = [
    Facility(id="FAC-HOSP-1", name="Coastal Central Hospital", kind="hospital",
             zone_id="B", coordinates=[73.943, 15.306], criticality=0.95),
    Facility(id="FAC-CLIN-1", name="B2 Health Clinic", kind="hospital",
             zone_id="B", coordinates=[73.958, 15.291], criticality=0.70),
    Facility(id="FAC-SCH-1", name="Miramar Public School", kind="school",
             zone_id="A", coordinates=[73.954, 15.323], criticality=0.60),
    Facility(id="FAC-SHEL-1", name="Upland Relief Shelter", kind="shelter",
             zone_id="D", coordinates=[73.980, 15.336], criticality=0.85),
    Facility(id="FAC-SHEL-2", name="Inland East Shelter", kind="shelter",
             zone_id="E", coordinates=[73.993, 15.290], criticality=0.75),
    Facility(id="FAC-SUB-1", name="5th Street Substation", kind="substation",
             zone_id="B", coordinates=[73.950, 15.303], criticality=0.88),
    Facility(id="FAC-FIRE-1", name="Harbour Fire Station", kind="fire_station",
             zone_id="C", coordinates=[73.952, 15.272], criticality=0.80),
    Facility(id="FAC-PORT-1", name="South Harbour Terminal", kind="port",
             zone_id="C", coordinates=[73.937, 15.262], criticality=0.65),
    Facility(id="FAC-SCH-2", name="Estuary Secondary School", kind="school",
             zone_id="B", coordinates=[73.936, 15.297], criticality=0.55),
    Facility(id="FAC-SUB-2", name="Upland Grid Node", kind="substation",
             zone_id="D", coordinates=[73.995, 15.325], criticality=0.72),
    Facility(id="FAC-SHEL-3", name="Miramar Evacuation Centre", kind="shelter",
             zone_id="A", coordinates=[73.936, 15.338], criticality=0.70),
    Facility(id="FAC-FIRE-2", name="Inland Fire Post", kind="fire_station",
             zone_id="E", coordinates=[73.975, 15.307], criticality=0.68),
]


# ---------------------------------------------------------------------------
# GeoJSON export
# ---------------------------------------------------------------------------

def _zone_properties(zone: Zone) -> dict:
    return {
        "id": zone.id,
        "name": zone.name,
        "elevation_m": zone.elevation_m,
        "drainage_capacity": zone.drainage_capacity,
        "historical_flood_freq": zone.historical_flood_freq,
        "imperviousness": zone.imperviousness,
        "slope": zone.slope,
        "population": zone.population,
        "vulnerability": zone.vulnerability,
    }


def as_geojson(zone_id: Optional[str] = None) -> dict:
    """Return all layers as a single GeoJSON FeatureCollection bundle."""
    zid = (zone_id or "goa").lower().strip()

    if zid != "goa":
        # Multi-location dynamic digital twin (e.g. Mumbai, Chennai, etc.)
        from data_collection.config import COASTAL_ZONES
        cz = COASTAL_ZONES.get(zid)
        base_lat = cz.lat if cz else 19.076
        base_lon = cz.lon if cz else 72.877
        z_name = cz.name if cz else zid.title()

        offsets = [
            (-0.02, -0.02, 0.015, 0.015, "A", f"Zone A · {z_name} Waterfront", 1.5, 0.65),
            (0.00, -0.02, 0.035, 0.015, "B", f"Zone B · {z_name} Lowlands", 1.1, 0.55),
            (-0.02, 0.00, 0.015, 0.035, "C", f"Zone C · {z_name} Port & Delta", 1.8, 0.70),
            (0.01, 0.01, 0.045, 0.045, "D", f"Zone D · {z_name} Heights", 4.5, 0.85),
            (0.03, -0.01, 0.065, 0.025, "E", f"Zone E · {z_name} Hinterland", 3.2, 0.80),
        ]
        zone_features = []
        for dlon, dlat, w, h, id_val, name_val, elev, drain in offsets:
            p = [
                [round(base_lon + dlon, 4), round(base_lat + dlat, 4)],
                [round(base_lon + dlon + w, 4), round(base_lat + dlat, 4)],
                [round(base_lon + dlon + w, 4), round(base_lat + dlat + h, 4)],
                [round(base_lon + dlon, 4), round(base_lat + dlat + h, 4)],
                [round(base_lon + dlon, 4), round(base_lat + dlat, 4)],
            ]
            zone_features.append({
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [p]},
                "properties": {
                    "id": id_val,
                    "name": name_val,
                    "elevation_m": elev,
                    "drainage_capacity": drain,
                    "historical_flood_freq": 0.4,
                    "imperviousness": 0.6,
                    "slope": 2.0,
                    "population": 25000,
                    "vulnerability": 0.5,
                },
            })

        return {
            "type": "FeatureCollection",
            "features": [],
            "layers": {
                "zones": {"type": "FeatureCollection", "features": zone_features},
                "roads": {"type": "FeatureCollection", "features": []},
                "buildings": {"type": "FeatureCollection", "features": []},
                "facilities": {"type": "FeatureCollection", "features": []},
                "nodes": {"type": "FeatureCollection", "features": []},
            },
            "meta": {
                "name": f"TIDALIS Coastal District ({z_name})",
                "zone_id": zid,
                "demo_data": False,
                "zone_count": len(zone_features),
                "road_count": 0,
                "building_count": 0,
                "facility_count": 0,
            },
        }

    # Default Goa digital twin
    zones = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [z.polygon]},
             "properties": _zone_properties(z)}
            for z in ZONES
        ],
    }
    roads = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature",
             "geometry": {"type": "LineString", "coordinates": r.geometry},
             "properties": {"id": r.id, "name": r.name, "elevation_m": r.elevation_m,
                            "from_node": r.from_node, "to_node": r.to_node,
                            "lanes": r.lanes, "critical": r.critical}}
            for r in ROADS
        ],
    }
    buildings = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature",
             "geometry": {"type": "Polygon", "coordinates": [b.polygon]},
             "properties": {"id": b.id, "zone_id": b.zone_id, "height_m": b.height_m,
                            "floors": b.floors, "usage": b.usage}}
            for b in BUILDINGS
        ],
    }
    facilities = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature",
             "geometry": {"type": "Point", "coordinates": f.coordinates},
             "properties": {"id": f.id, "name": f.name, "kind": f.kind,
                            "zone_id": f.zone_id, "criticality": f.criticality}}
            for f in FACILITIES
        ],
    }
    nodes = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature",
             "geometry": {"type": "Point", "coordinates": n.coordinates},
             "properties": {"id": n.id, "name": n.name, "is_hub": n.is_hub,
                            "elevation_m": n.elevation_m}}
            for n in ROAD_NODES
        ],
    }
    return {
        "type": "FeatureCollection",
        "features": [],  # required shape; layers are returned side by side
        "layers": {
            "zones": zones,
            "roads": roads,
            "buildings": buildings,
            "facilities": facilities,
            "nodes": nodes,
        },
        "meta": {
            "name": "TIDALIS Coastal District",
            "zone_id": "goa",
            "demo_data": True,
            "zone_count": len(ZONES),
            "road_count": len(ROADS),
            "building_count": len(BUILDINGS),
            "facility_count": len(FACILITIES),
        },
    }


def facilities_in_zone(zone_id: str) -> list[Facility]:
    return [f for f in FACILITIES if f.zone_id == zone_id]
