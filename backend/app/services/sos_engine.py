"""
TIDALIS — SOS Triage Engine.

Handles incoming SOS distress signals from stranded individuals.
Cross-references GPS coordinates against topographical elevation data
and predicted flood depth to triage each SOS into urgency categories:

  CRITICAL  — Low ground, water rising fast, immediate rescue needed
  HIGH      — Low ground, water approaching, urgent extraction
  MODERATE  — Mid elevation, monitor closely
  SAFE      — High ground, no immediate danger, schedule pickup

This engine also suggests the optimal rescue method:
  BOAT, HELICOPTER, GROUND_VEHICLE, or WADE_TEAM.
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class SOSRequest(BaseModel):
    """Incoming SOS distress signal."""
    latitude: float
    longitude: float
    name: str = "Unknown"
    phone: str = ""
    people_count: int = 1
    has_children: bool = False
    has_elderly: bool = False
    medical_emergency: bool = False
    message: str = ""


class SOSTicket(BaseModel):
    """Triaged SOS ticket with rescue recommendation."""
    ticket_id: str = Field(default_factory=lambda: f"SOS-{uuid.uuid4().hex[:6].upper()}")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    latitude: float
    longitude: float
    name: str
    phone: str
    people_count: int
    has_children: bool
    has_elderly: bool
    medical_emergency: bool
    message: str

    # Triage results
    elevation_m: float = 0.0
    predicted_flood_depth_m: float = 0.0
    water_margin_m: float = 0.0  # elevation - flood_depth (negative = submerged)
    urgency: str = "MODERATE"  # CRITICAL | HIGH | MODERATE | SAFE
    urgency_score: float = 0.0  # 0.0 to 1.0
    rescue_method: str = "GROUND_VEHICLE"
    nearest_shelter: str = ""
    distance_to_shelter_km: float = 0.0
    eta_minutes: int = 0
    triage_reason: str = ""
    status: str = "PENDING"  # PENDING | DISPATCHED | EN_ROUTE | RESCUED


# ---------------------------------------------------------------------------
# Topographical Data (Simulated DEM for Goa coast)
# ---------------------------------------------------------------------------

# Grid of elevation data points around the Goa coastline
_ELEVATION_GRID = [
    {"lat": 15.28, "lon": 73.94, "elev": 2.1},
    {"lat": 15.29, "lon": 73.95, "elev": 1.4},
    {"lat": 15.30, "lon": 73.96, "elev": 3.8},
    {"lat": 15.31, "lon": 73.97, "elev": 5.2},
    {"lat": 15.27, "lon": 73.98, "elev": 0.9},
    {"lat": 15.26, "lon": 73.93, "elev": 7.4},
    {"lat": 15.32, "lon": 73.99, "elev": 12.6},
    {"lat": 15.25, "lon": 73.92, "elev": 4.3},
    {"lat": 15.33, "lon": 73.96, "elev": 8.1},
    {"lat": 15.29, "lon": 73.99, "elev": 1.8},
    {"lat": 15.28, "lon": 73.97, "elev": 2.5},
    {"lat": 15.30, "lon": 73.94, "elev": 3.1},
    {"lat": 15.27, "lon": 73.96, "elev": 1.1},
    {"lat": 15.31, "lon": 73.95, "elev": 6.9},
    {"lat": 15.26, "lon": 73.98, "elev": 0.6},
]

_SHELTERS = [
    {"name": "Panaji Municipal Shelter", "lat": 15.4969, "lon": 73.8278, "capacity": 200},
    {"name": "Miramar Community Hall", "lat": 15.2993, "lon": 73.9862, "capacity": 150},
    {"name": "Dona Paula Relief Camp", "lat": 15.2760, "lon": 73.9700, "capacity": 100},
    {"name": "Vasco Emergency Center", "lat": 15.3993, "lon": 73.8110, "capacity": 300},
    {"name": "Margao Relief Station", "lat": 15.2832, "lon": 73.9862, "capacity": 250},
]


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance in km between two points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _estimate_elevation(lat: float, lon: float) -> float:
    """Interpolate elevation from the DEM grid using IDW."""
    total_weight = 0.0
    weighted_elev = 0.0
    for point in _ELEVATION_GRID:
        d = _haversine(lat, lon, point["lat"], point["lon"])
        if d < 0.01:
            return point["elev"]
        w = 1.0 / (d ** 2)
        weighted_elev += w * point["elev"]
        total_weight += w
    return round(weighted_elev / total_weight, 2) if total_weight > 0 else 3.0


def _estimate_flood_depth(lat: float, lon: float) -> float:
    """
    Estimate predicted flood depth at a location.
    Uses distance from coast + elevation as proxy.
    In production, this would come from the flood prediction model.
    """
    # Approximate distance from coastline (lower lon = closer to sea in Goa)
    coast_proximity = max(0.0, 74.00 - lon) * 50  # rough km-ish scale
    base_depth = max(0.0, 3.5 - coast_proximity * 0.8)

    # Add tide-based surge
    elevation = _estimate_elevation(lat, lon)
    if elevation < 2.0:
        base_depth += 1.5
    elif elevation < 4.0:
        base_depth += 0.6

    return round(base_depth, 2)


def _find_nearest_shelter(lat: float, lon: float) -> tuple[str, float]:
    """Find nearest shelter and return (name, distance_km)."""
    best_name = _SHELTERS[0]["name"]
    best_dist = float("inf")
    for s in _SHELTERS:
        d = _haversine(lat, lon, s["lat"], s["lon"])
        if d < best_dist:
            best_dist = d
            best_name = s["name"]
    return best_name, round(best_dist, 2)


def triage_sos(request: SOSRequest) -> SOSTicket:
    """
    Process an incoming SOS request and produce a triaged ticket.
    """
    elevation = _estimate_elevation(request.latitude, request.longitude)
    flood_depth = _estimate_flood_depth(request.latitude, request.longitude)
    water_margin = round(elevation - flood_depth, 2)

    # --- Compute urgency score (0 = safe, 1 = critical) ---
    score = 0.0

    # Water margin is the primary factor
    if water_margin < 0:
        score += 0.5 + min(abs(water_margin) * 0.1, 0.3)  # submerged
    elif water_margin < 1.0:
        score += 0.35
    elif water_margin < 3.0:
        score += 0.15

    # Vulnerability multipliers
    if request.medical_emergency:
        score += 0.2
    if request.has_children:
        score += 0.1
    if request.has_elderly:
        score += 0.1
    if request.people_count > 5:
        score += 0.05

    score = round(min(score, 1.0), 3)

    # --- Determine urgency level ---
    if score >= 0.7:
        urgency = "CRITICAL"
    elif score >= 0.45:
        urgency = "HIGH"
    elif score >= 0.2:
        urgency = "MODERATE"
    else:
        urgency = "SAFE"

    # --- Determine rescue method ---
    if water_margin < -0.5:
        rescue_method = "HELICOPTER" if request.people_count > 3 else "BOAT"
    elif water_margin < 1.0:
        rescue_method = "BOAT"
    elif water_margin < 3.0:
        rescue_method = "WADE_TEAM"
    else:
        rescue_method = "GROUND_VEHICLE"

    if request.medical_emergency and rescue_method != "HELICOPTER":
        rescue_method = "HELICOPTER"

    # --- Find nearest shelter ---
    shelter_name, shelter_dist = _find_nearest_shelter(request.latitude, request.longitude)

    # --- ETA estimate ---
    if rescue_method == "HELICOPTER":
        eta = int(shelter_dist * 2.5 + 8)
    elif rescue_method == "BOAT":
        eta = int(shelter_dist * 6 + 12)
    elif rescue_method == "WADE_TEAM":
        eta = int(shelter_dist * 12 + 15)
    else:
        eta = int(shelter_dist * 4 + 5)

    # --- Build triage reason ---
    reasons = []
    if water_margin < 0:
        reasons.append(f"Location is {abs(water_margin):.1f}m below predicted flood level")
    elif water_margin < 1.0:
        reasons.append(f"Only {water_margin:.1f}m above predicted flood level")
    else:
        reasons.append(f"Located {water_margin:.1f}m above predicted flood level")

    if request.medical_emergency:
        reasons.append("Medical emergency reported")
    if request.has_children:
        reasons.append(f"Children present ({request.people_count} people)")
    if request.has_elderly:
        reasons.append("Elderly individuals present")

    return SOSTicket(
        latitude=request.latitude,
        longitude=request.longitude,
        name=request.name,
        phone=request.phone,
        people_count=request.people_count,
        has_children=request.has_children,
        has_elderly=request.has_elderly,
        medical_emergency=request.medical_emergency,
        message=request.message,
        elevation_m=elevation,
        predicted_flood_depth_m=flood_depth,
        water_margin_m=water_margin,
        urgency=urgency,
        urgency_score=score,
        rescue_method=rescue_method,
        nearest_shelter=shelter_name,
        distance_to_shelter_km=shelter_dist,
        eta_minutes=eta,
        triage_reason=" · ".join(reasons),
    )


# ---------------------------------------------------------------------------
# In-memory SOS store
# ---------------------------------------------------------------------------

_sos_tickets: list[SOSTicket] = []


def submit_sos(request: SOSRequest) -> SOSTicket:
    """Submit and triage an SOS request, storing the ticket."""
    ticket = triage_sos(request)
    _sos_tickets.append(ticket)
    # Sort by urgency score descending after insert
    _sos_tickets.sort(key=lambda t: t.urgency_score, reverse=True)
    return ticket


def get_all_sos_tickets() -> list[SOSTicket]:
    """Return all SOS tickets sorted by urgency."""
    return _sos_tickets


def update_sos_status(ticket_id: str, status: str) -> Optional[SOSTicket]:
    """Update the status of an SOS ticket."""
    for ticket in _sos_tickets:
        if ticket.ticket_id == ticket_id:
            ticket.status = status
            return ticket
    return None
