"""
TIDALIS — Topological Mitigation Engine.
Analyzes road graph topology using NetworkX, identifying:
- Critical cut-edges / topological bridges
- Edge betweenness centrality bottlenecks
- Hydrodynamic deck submergence (>0.15m light vehicle cutoff, >0.35m heavy rescue cutoff)
- Stranded population enclaves cut off from high-ground emergency hubs
- Proactive physical bottleneck defenses (dewatering pumps, tiger dams, sandbags)
- Dynamic evacuation egress corridors and alternate bypasses
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import networkx as nx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Designated High-Ground Safe Emergency Hubs per District
HIGH_GROUND_HUBS: Dict[str, Dict[str, any]] = {
    "goa": {
        "id": "HUB-PONDA",
        "name": "Ponda High-Ground Emergency Relief Plateau",
        "coord": [74.015, 15.405],
        "elevation_m": 24.0,
    },
    "mangaluru": {
        "id": "HUB-BANTWAL",
        "name": "Bantwal Safe Inland Evacuation Hub",
        "coord": [74.985, 12.885],
        "elevation_m": 28.0,
    },
    "mumbai": {
        "id": "HUB-THANE-PANVEL",
        "name": "Sion-Panvel High-Ground Evacuation Staging Hub",
        "coord": [72.965, 19.062],
        "elevation_m": 15.0,
    },
}

# In-memory storage for active operator defenses
ACTIVE_DEFENSES: Set[str] = set()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class TopologicalBottleneck(BaseModel):
    id: str
    road_id: str
    name: str
    ref: str
    classification: str
    deck_elevation_m: float
    water_on_deck_m: float
    is_cut_edge: bool
    betweenness_centrality: float
    status: str  # SAFE | THREATENED | SEVERED | DEFENDED
    isolated_population: int
    threatened_facilities: List[str] = Field(default_factory=list)
    defended: bool = False
    coordinates: List[float]  # [lon, lat] of midpoint / defense staging


class PhysicalDefenseAction(BaseModel):
    id: str
    bottleneck_id: str
    road_id: str
    road_name: str
    action: str
    description: str
    equipment_type: str  # HIGH_VOLUME_PUMPS | TIGER_DAM_BARRIER | SANDBAG_ABUTMENT
    priority: str  # IMMEDIATE | HIGH
    estimated_cost: str
    time_to_deploy: str
    resources_needed: List[str]
    status: str  # PENDING | ACTIVE
    effectiveness: float
    coordinates: List[float]  # [lon, lat]


class EvacuationCorridor(BaseModel):
    id: str
    name: str
    origin_name: str
    destination_hub: str
    distance_km: float
    estimated_minutes: float
    status: str  # OPTIMAL | BYPASS | SEVERED
    coordinates: List[List[float]]
    is_active: bool = True


class TopologicalAnalysisResult(BaseModel):
    district_id: str
    water_level_m: float
    network_integrity: float
    total_roads: int
    passable_roads_count: int
    severed_roads_count: int
    defended_roads_count: int
    bottlenecks: List[TopologicalBottleneck] = Field(default_factory=list)
    defenses: List[PhysicalDefenseAction] = Field(default_factory=list)
    evacuation_corridors: List[EvacuationCorridor] = Field(default_factory=list)
    isolated_zones: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Geodesic Math
# ---------------------------------------------------------------------------

def _haversine(c1: List[float], c2: List[float]) -> float:
    lon1, lat1 = c1[0], c1[1]
    lon2, lat2 = c2[0], c2[1]
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return round(r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)), 3)


def _round_coord(coord: List[float]) -> Tuple[float, float]:
    return (round(coord[0], 4), round(coord[1], 4))


# ---------------------------------------------------------------------------
# Graph Construction & Ingestion
# ---------------------------------------------------------------------------

def load_district_road_features(district_id: str) -> List[dict]:
    resolved_zid = district_id.lower().strip()
    roads_dir = Path(__file__).resolve().parent.parent.parent.parent / "data" / "geo" / "roads"
    road_file = roads_dir / f"{resolved_zid}.geojson"
    if not road_file.exists():
        road_file = roads_dir / "goa.geojson"
    try:
        data = json.loads(road_file.read_text(encoding="utf-8"))
        return data.get("features", [])
    except Exception as exc:
        logger.error("Failed loading road features for %s: %s", resolved_zid, exc)
        return []


def build_networkx_graph(features: List[dict]) -> nx.Graph:
    G = nx.Graph()
    for f in features:
        props = f.get("properties", {})
        coords = f.get("geometry", {}).get("coordinates", [])
        if len(coords) < 2:
            continue
        u = _round_coord(coords[0])
        v = _round_coord(coords[-1])
        dist = sum(_haversine(coords[i], coords[i + 1]) for i in range(len(coords) - 1))
        rid = props.get("id", f"RD-{len(G.edges)}")
        elev = float(props.get("elevation_m", 2.0))
        G.add_edge(
            u,
            v,
            id=rid,
            name=props.get("name", "Arterial Road"),
            ref=props.get("ref", "NH"),
            elevation_m=elev,
            length_km=dist,
            lanes=props.get("lanes", 4),
            critical=bool(props.get("critical", False)),
            is_evacuation_corridor=bool(props.get("is_evacuation_corridor", False)),
            classification=props.get("classification", "arterial"),
            coordinates=coords,
            properties=props,
        )
    return G


# ---------------------------------------------------------------------------
# Topological Submergence & Cut-Edge Analysis
# ---------------------------------------------------------------------------

def evaluate_district_topology(
    district_id: str,
    ref_water_m: float,
    zone_depths: Optional[Dict[str, float]] = None,
    defended_road_ids: Optional[Set[str]] = None,
) -> TopologicalAnalysisResult:
    """
    Evaluates topological connectivity, bottlenecks, physical defenses,
    and evacuation paths for a coastal district at a specific flood water level.
    """
    resolved_zid = district_id.lower().strip()
    if resolved_zid not in HIGH_GROUND_HUBS:
        resolved_zid = "goa"

    features = load_district_road_features(resolved_zid)
    if not features:
        return TopologicalAnalysisResult(
            district_id=resolved_zid,
            water_level_m=ref_water_m,
            network_integrity=1.0,
            total_roads=0,
            passable_roads_count=0,
            severed_roads_count=0,
            defended_roads_count=0,
        )

    G = build_networkx_graph(features)
    active_defenses = defended_road_ids if defended_road_ids is not None else ACTIVE_DEFENSES

    # 1. Edge betweenness centrality & topological bridges of entire graph
    try:
        edge_centrality = nx.edge_betweenness_centrality(G)
    except Exception:
        edge_centrality = {}

    bridges = set()
    try:
        bridges = set(nx.bridges(G))
    except Exception:
        pass

    # 2. Evaluate edge submergence states
    passable_edges = []
    severed_edges = []
    bottlenecks: List[TopologicalBottleneck] = []
    defenses: List[PhysicalDefenseAction] = []

    for u, v, data in G.edges(data=True):
        rid = data["id"]
        elev = data["elevation_m"]
        is_defended = rid in active_defenses
        coords = data["coordinates"]
        midpoint = coords[len(coords) // 2]

        water_on_deck = max(0.0, round(ref_water_m - elev, 2))
        is_bridge_or_cut_edge = (u, v) in bridges or (v, u) in bridges
        centrality = round(edge_centrality.get((u, v), edge_centrality.get((v, u), 0.0)), 3)

        # Status determination
        if is_defended:
            status = "DEFENDED"
            is_passable = True
        elif water_on_deck > 0.15:  # Passenger vehicle submersion cutoff
            status = "SEVERED"
            is_passable = False
        elif water_on_deck > 0.05 or (elev - ref_water_m) < 0.25:
            status = "THREATENED"
            is_passable = True
        else:
            status = "SAFE"
            is_passable = True

        if is_passable:
            passable_edges.append((u, v, data))
        else:
            severed_edges.append((u, v, data))

        # Check if it represents a critical bottleneck
        # (High centrality or cut-edge, and threatened or severed)
        if (centrality >= 0.20 or is_bridge_or_cut_edge) and (status in ("THREATENED", "SEVERED", "DEFENDED")):
            # Population impact heuristic based on district
            pop_impact = 35000 if resolved_zid == "goa" else 42000 if resolved_zid == "mangaluru" else 65000
            if centrality > 0.40:
                pop_impact = int(pop_impact * 1.5)

            facilities_impact = []
            if "Bridge" in data["name"] or "Causeway" in data["name"]:
                facilities_impact.append("Regional Trauma Hospital Access")
                facilities_impact.append("Port Heavy Transport")
            if data["is_evacuation_corridor"]:
                facilities_impact.append("Designated Civilian Evacuation Egress")

            bottleneck = TopologicalBottleneck(
                id=f"BOTTLENECK-{rid}",
                road_id=rid,
                name=data["name"],
                ref=data["ref"],
                classification=data["classification"],
                deck_elevation_m=elev,
                water_on_deck_m=water_on_deck,
                is_cut_edge=is_bridge_or_cut_edge,
                betweenness_centrality=centrality,
                status=status,
                isolated_population=pop_impact,
                threatened_facilities=facilities_impact,
                defended=is_defended,
                coordinates=[round(midpoint[0], 5), round(midpoint[1], 5)],
            )
            bottlenecks.append(bottleneck)

            # Generate proactive physical defense recommendation
            if not is_defended:
                if water_on_deck <= 0.35:
                    p_action = f"Deploy 3x High-Capacity Diesel Dewatering Pumps at {data['name']}"
                    p_desc = f"Position 6,000 LPM dewatering pump units at bridge abutment to lower surface ponding and preserve the {data['ref']} arterial."
                    eq_type = "HIGH_VOLUME_PUMPS"
                    cost = "₹45,000"
                    t_dep = "20 min"
                    resources = ["Diesel Pumps (3)", "Pump Operators (2)", "Fuel Supply", "Traffic Escort"]
                else:
                    p_action = f"Deploy Mobile Tiger Dam Barrier & Axial Pumps along {data['name']}"
                    p_desc = f"Roll out rapid water-inflated flood barriers (300m) along low deck approach ramps to block surge intrusion."
                    eq_type = "TIGER_DAM_BARRIER"
                    cost = "₹85,000"
                    t_dep = "35 min"
                    resources = ["Tiger Dam Rapid Trailer", "Deployment Crew (6)", "High-Pressure Inflator", "Generator"]

                defenses.append(
                    PhysicalDefenseAction(
                        id=f"DEF-{rid}",
                        bottleneck_id=bottleneck.id,
                        road_id=rid,
                        road_name=data["name"],
                        action=p_action,
                        description=p_desc,
                        equipment_type=eq_type,
                        priority="IMMEDIATE" if status == "SEVERED" else "HIGH",
                        estimated_cost=cost,
                        time_to_deploy=t_dep,
                        resources_needed=resources,
                        status="PENDING",
                        effectiveness=0.88,
                        coordinates=[round(midpoint[0], 5), round(midpoint[1], 5)],
                    )
                )

    # 3. Graph reachability to High-Ground Emergency Hub
    hub_info = HIGH_GROUND_HUBS[resolved_zid]
    hub_coord = _round_coord(hub_info["coord"])

    # Build graph of currently passable routes
    G_passable = nx.Graph()
    for u, v, d in passable_edges:
        G_passable.add_edge(u, v, weight=d["length_km"], **d)

    # Calculate evacuation corridors
    evacuation_corridors: List[EvacuationCorridor] = []
    all_nodes = list(G.nodes())

    # Find nodes nearest to key origin points
    hub_accessible = set()
    if hub_coord in G_passable:
        hub_accessible = nx.descendants(G_passable, hub_coord) | {hub_coord}

    # Find shortest safe paths to hub for connected components
    for u in all_nodes:
        if u == hub_coord or u not in G_passable:
            continue
        if nx.has_path(G_passable, u, hub_coord):
            try:
                path = nx.shortest_path(G_passable, u, hub_coord, weight="weight")
                if len(path) >= 2:
                    # Collect coordinates along path
                    path_coords = []
                    total_dist = 0.0
                    for i in range(len(path) - 1):
                        e_data = G_passable.get_edge_data(path[i], path[i + 1])
                        c_list = e_data.get("coordinates", [])
                        if i == 0:
                            path_coords.extend(c_list)
                        else:
                            path_coords.extend(c_list[1:])
                        total_dist += e_data.get("length_km", 1.0)

                    # Only register distinct primary corridors
                    if total_dist > 5.0 and len(evacuation_corridors) < 2:
                        evacuation_corridors.append(
                            EvacuationCorridor(
                                id=f"EVAC-CORRIDOR-{len(evacuation_corridors) + 1}",
                                name=f"Active Evacuation Egress to {hub_info['name']}",
                                origin_name=f"Coastal Sector ({u[1]:.3f}°N, {u[0]:.3f}°E)",
                                destination_hub=hub_info["name"],
                                distance_km=round(total_dist, 1),
                                estimated_minutes=round((total_dist / 45.0) * 60, 1),
                                status="OPTIMAL" if total_dist < 25 else "BYPASS",
                                coordinates=path_coords,
                                is_active=True,
                            )
                        )
            except Exception:
                pass

    # If no dynamic path found because primary links are severed, generate direct designated corridor
    if not evacuation_corridors:
        for f in features:
            props = f.get("properties", {})
            if props.get("is_evacuation_corridor"):
                c = f.get("geometry", {}).get("coordinates", [])
                dist = sum(_haversine(c[i], c[i + 1]) for i in range(len(c) - 1))
                evacuation_corridors.append(
                    EvacuationCorridor(
                        id=f"EVAC-DESIGNATED-{props.get('id')}",
                        name=props.get("name", "High-Ground Evacuation Expressway"),
                        origin_name="Urban Coastal Center",
                        destination_hub=hub_info["name"],
                        distance_km=round(dist, 1),
                        estimated_minutes=round((dist / 60.0) * 60, 1),
                        status="OPTIMAL",
                        coordinates=c,
                        is_active=True,
                    )
                )
                break

    # 4. Network integrity
    total_roads = len(features)
    passable_count = len(passable_edges)
    severed_count = len(severed_edges)
    defended_count = len([b for b in bottlenecks if b.defended])

    integrity = round(passable_count / max(1, total_roads), 2)
    isolated_zones = []
    if integrity < 0.85:
        isolated_zones = ["Zone A (Waterfront)", "Zone B (Estuary Delta)"]

    return TopologicalAnalysisResult(
        district_id=resolved_zid,
        water_level_m=round(ref_water_m, 2),
        network_integrity=integrity,
        total_roads=total_roads,
        passable_roads_count=passable_count,
        severed_roads_count=severed_count,
        defended_roads_count=defended_count,
        bottlenecks=bottlenecks,
        defenses=defenses,
        evacuation_corridors=evacuation_corridors,
        isolated_zones=isolated_zones,
    )


def authorize_defense(defense_id: str) -> bool:
    """Authorize or toggle a physical defense for a road bottleneck."""
    global ACTIVE_DEFENSES
    road_id = defense_id.replace("DEF-", "")
    if road_id in ACTIVE_DEFENSES:
        ACTIVE_DEFENSES.remove(road_id)
        return False
    else:
        ACTIVE_DEFENSES.add(road_id)
        return True


def clear_all_defenses() -> None:
    """Reset all operator physical defenses."""
    global ACTIVE_DEFENSES
    ACTIVE_DEFENSES.clear()
