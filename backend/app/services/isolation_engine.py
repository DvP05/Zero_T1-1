"""
TIDALIS — Dynamic Isolation Detection.

Runs a connectivity analysis over the road graph for a given water level
and reports "isolated enclaves": neighbourhoods whose egress routes are all
impassable, cutting them off from the evacuation hub on high ground.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.app.geospatial.city_model import (
    NODE_ZONE,
    ROAD_NODES,
    ROADS,
    ZONE_BY_ID,
    facilities_in_zone,
)


class RoadStatus(BaseModel):
    id: str
    name: str
    elevation_m: float
    critical: bool
    passable: bool
    submersion_m: float  # how far water sits above / below the road surface
    reason: str


class IsolatedEnclave(BaseModel):
    zone_id: str
    zone_name: str
    population: int
    blocked_egress: list[str] = Field(default_factory=list)
    open_egress: list[str] = Field(default_factory=list)
    stranded_facilities: list[str] = Field(default_factory=list)
    flood_depth_m: float = 0.0
    reason: str = ""


class IsolationReport(BaseModel):
    water_level_m: float
    blocked_roads: list[RoadStatus] = Field(default_factory=list)
    passable_roads: list[RoadStatus] = Field(default_factory=list)
    isolated_zones: list[str] = Field(default_factory=list)
    enclaves: list[IsolatedEnclave] = Field(default_factory=list)
    network_integrity: float = 1.0  # 0..1 share of passable road length
    summary: str = ""


def _adjacency(passable_ids: set[str]) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {node.id: set() for node in ROAD_NODES}
    for road in ROADS:
        if road.id in passable_ids:
            graph[road.from_node].add(road.to_node)
            graph[road.to_node].add(road.from_node)
    return graph


def _reachable(graph: dict[str, set[str]], start: str) -> set[str]:
    seen = {start}
    stack = [start]
    while stack:
        current = stack.pop()
        for neighbour in graph.get(current, ()):
            if neighbour not in seen:
                seen.add(neighbour)
                stack.append(neighbour)
    return seen


def evaluate_isolation(water_level_m: float, zone_depths: dict[str, float]) -> IsolationReport:
    statuses: list[RoadStatus] = []
    passable_ids: set[str] = set()

    for road in ROADS:
        submerged = water_level_m - road.elevation_m
        passable = submerged < 0.05
        if passable:
            passable_ids.add(road.id)
        statuses.append(
            RoadStatus(
                id=road.id,
                name=road.name,
                elevation_m=road.elevation_m,
                critical=road.critical,
                passable=passable,
                submersion_m=round(max(submerged, 0.0), 3),
                reason=(
                    f"Water at {water_level_m:.2f} m sits {submerged:.2f} m "
                    f"{'above' if submerged > 0 else 'below'} the {road.elevation_m:.2f} m road surface"
                ),
            )
        )

    graph = _adjacency(passable_ids)
    hub_reach = _reachable(graph, "N-HUB")

    enclaves: list[IsolatedEnclave] = []
    isolated_zone_ids: list[str] = []
    for node_id, zone_id in NODE_ZONE.items():
        if zone_id is None:
            continue
        zone = ZONE_BY_ID[zone_id]
        egress = [r for r in ROADS if r.from_node == node_id or r.to_node == node_id]
        open_roads = [r for r in egress if r.id in passable_ids]
        blocked_roads = [r for r in egress if r.id not in passable_ids]
        connected = node_id in hub_reach

        if not connected:
            isolated_zone_ids.append(zone_id)
            stranded = [
                f.name
                for f in facilities_in_zone(zone_id)
                if zone_depths.get(zone_id, 0.0) > 0.1
            ]
            enclaves.append(
                IsolatedEnclave(
                    zone_id=zone_id,
                    zone_name=zone.name,
                    population=zone.population,
                    blocked_egress=[f"{r.id} {r.name}" for r in blocked_roads],
                    open_egress=[f"{r.id} {r.name}" for r in open_roads],
                    stranded_facilities=stranded,
                    flood_depth_m=round(zone_depths.get(zone_id, 0.0), 2),
                    reason=(
                        "All egress routes to the NH-48 evacuation interchange are impassable"
                        if not open_roads
                        else "Every viable path to the evacuation interchange is cut by flooded segments"
                    ),
                )
            )

    total_roads = len(ROADS) or 1
    integrity = round(len(passable_ids) / total_roads, 3)
    blocked = [s for s in statuses if not s.passable]

    if enclaves:
        names = ", ".join(e.zone_name for e in enclaves)
        summary = (
            f"{len(enclaves)} isolated enclave(s): {names} — "
            f"{len(blocked)}/{total_roads} road segments impassable "
            f"(network integrity {integrity:.0%})."
        )
    else:
        summary = (
            f"All zones remain connected to the evacuation hub — "
            f"{len(blocked)}/{total_roads} road segments impassable "
            f"(network integrity {integrity:.0%})."
        )

    return IsolationReport(
        water_level_m=round(water_level_m, 3),
        blocked_roads=[s for s in statuses if not s.passable],
        passable_roads=[s for s in statuses if s.passable],
        isolated_zones=isolated_zone_ids,
        enclaves=enclaves,
        network_integrity=integrity,
        summary=summary,
    )
