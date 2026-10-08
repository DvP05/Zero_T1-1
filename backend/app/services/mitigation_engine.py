"""
TIDALIS — Mitigation Suggestion Engine.

Analyses predicted flood threats per zone and prescribes specific,
actionable mitigation measures based on the dominant threat vector:
  - Tidal surge → barrier deployment, pump activation
  - Rainfall overflow → drainage unclogging, sandbag placement
  - Low elevation → pre-evacuation, asset relocation
  - Infrastructure stress → traffic rerouting, power grid isolation

Each suggestion includes priority, estimated cost, and time-to-deploy.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class MitigationSuggestion(BaseModel):
    """A single actionable mitigation suggestion."""
    model_config = {"extra": "allow"}

    id: str
    zone: str
    action: str
    description: str
    priority: str  # IMMEDIATE | HIGH | MEDIUM | LOW
    threat_vector: str  # tidal_surge | rainfall | drainage | low_elevation | infrastructure
    estimated_cost: str  # e.g. "₹50,000" or "LOW"
    time_to_deploy: str  # e.g. "30 min" or "2 hours"
    resources_needed: list[str]
    effectiveness: float  # 0-1, estimated risk reduction
    status: str = "PENDING"  # PENDING | IN_PROGRESS | COMPLETED | SKIPPED | ACTIVE
    coordinates: Optional[list[float]] = None
    is_topological: bool = False
    road_id: Optional[str] = None


class MitigationPlan(BaseModel):
    """Complete mitigation plan for a flood event."""
    event_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_suggestions: int = 0
    immediate_actions: int = 0
    estimated_risk_reduction: float = 0.0
    suggestions: list[MitigationSuggestion] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Mitigation knowledge base (rule-based expert system)
# ---------------------------------------------------------------------------

_MITIGATION_RULES = {
    "tidal_surge": [
        {
            "action": "Deploy storm barriers at coastal entry points",
            "description": "Activate temporary flood barriers at the 3 primary tidal entry channels to reduce surge volume by up to 40%.",
            "priority": "IMMEDIATE",
            "cost": "₹2,50,000",
            "time": "45 min",
            "resources": ["Barrier deployment crew (6)", "Mobile crane", "Flood barriers (12 units)"],
            "effectiveness": 0.40,
        },
        {
            "action": "Activate high-capacity pumps at Node 4",
            "description": "Deploy and activate 3 high-capacity pumps at drainage Node 4 to preemptively lower water table before surge arrives.",
            "priority": "IMMEDIATE",
            "cost": "₹75,000",
            "time": "30 min",
            "resources": ["Pump operators (2)", "Diesel pumps (3)", "Fuel supply"],
            "effectiveness": 0.25,
        },
        {
            "action": "Close tidal gates on Zuari Channel",
            "description": "Coordinate with port authority to close the Zuari estuary tidal gates to prevent backflow into residential areas.",
            "priority": "HIGH",
            "cost": "₹10,000",
            "time": "20 min",
            "resources": ["Port authority coordination", "Gate operators (2)"],
            "effectiveness": 0.35,
        },
    ],
    "rainfall": [
        {
            "action": "Pre-position sandbags at 5th Street substation",
            "description": "Deploy 200 sandbags around the electrical substation at 5th Street to protect critical power infrastructure.",
            "priority": "IMMEDIATE",
            "cost": "₹30,000",
            "time": "1 hour",
            "resources": ["Volunteers (8)", "Sandbags (200)", "Transport vehicle"],
            "effectiveness": 0.30,
        },
        {
            "action": "Clear debris from primary drainage channels",
            "description": "Emergency clearing of drainage channels D1–D4 to restore full flow capacity before peak rainfall.",
            "priority": "HIGH",
            "cost": "₹45,000",
            "time": "2 hours",
            "resources": ["Municipal drainage crew (4)", "Excavator", "Debris truck"],
            "effectiveness": 0.35,
        },
        {
            "action": "Open secondary overflow channels",
            "description": "Redirect excess surface water through agricultural overflow channels to reduce urban ponding.",
            "priority": "MEDIUM",
            "cost": "₹15,000",
            "time": "45 min",
            "resources": ["Field engineers (2)", "Channel gates"],
            "effectiveness": 0.20,
        },
    ],
    "low_elevation": [
        {
            "action": "Issue pre-evacuation advisory for Zone B low-lying sectors",
            "description": "Alert residents in sectors B1–B3 (elevation < 2m) to prepare for possible evacuation. Begin voluntary relocation of vulnerable populations.",
            "priority": "IMMEDIATE",
            "cost": "₹5,000",
            "time": "15 min",
            "resources": ["Emergency broadcast system", "Local wardens (6)", "SMS alert system"],
            "effectiveness": 0.50,
        },
        {
            "action": "Relocate medical supplies from ground floor of Clinic B2",
            "description": "Move all critical medical supplies and equipment to the second floor of the B2 Health Clinic before floodwaters arrive.",
            "priority": "HIGH",
            "cost": "₹8,000",
            "time": "1.5 hours",
            "resources": ["Clinic staff (4)", "Moving crew (3)"],
            "effectiveness": 0.15,
        },
    ],
    "drainage": [
        {
            "action": "Deploy mobile pumping stations at intersection C-7",
            "description": "Set up 2 mobile pumping stations at the critical intersection C-7 where drainage capacity is at 90% and overflow is imminent.",
            "priority": "IMMEDIATE",
            "cost": "₹60,000",
            "time": "40 min",
            "resources": ["Mobile pump units (2)", "Operators (2)", "Power generator"],
            "effectiveness": 0.30,
        },
        {
            "action": "Activate backup drainage valve at Station 3",
            "description": "Open the backup drainage valve at pumping station 3 to increase outflow capacity by 35%.",
            "priority": "HIGH",
            "cost": "₹5,000",
            "time": "10 min",
            "resources": ["Station operator (1)", "Remote valve control"],
            "effectiveness": 0.25,
        },
    ],
    "infrastructure": [
        {
            "action": "Reroute traffic away from NH-17 low-lying section",
            "description": "Coordinate with traffic police to close NH-17 between KM 12-15 and redirect traffic via the elevated bypass.",
            "priority": "IMMEDIATE",
            "cost": "₹12,000",
            "time": "20 min",
            "resources": ["Traffic police (6)", "Barrier units (8)", "Digital signage update"],
            "effectiveness": 0.20,
        },
        {
            "action": "Isolate Zone C power grid segment",
            "description": "Preemptively disconnect the Zone C low-voltage grid segment to prevent electrical hazards in flood-prone areas.",
            "priority": "HIGH",
            "cost": "₹3,000",
            "time": "15 min",
            "resources": ["Power utility dispatch", "Grid operator (1)"],
            "effectiveness": 0.15,
        },
    ],
}


def _detect_threat_vectors(event) -> list[str]:
    """
    Determine dominant threat vectors from event evidence.
    In production, this would analyse real-time sensor data.
    """
    vectors = []

    if not event:
        return ["rainfall", "tidal_surge"]

    # Derive from evidence sources and scores
    for ev in getattr(event, "evidence", []):
        if ev.source == "ocean" and ev.score > 0.5:
            if "tidal_surge" not in vectors:
                vectors.append("tidal_surge")
        if ev.source == "weather" and ev.score > 0.4:
            if "rainfall" not in vectors:
                vectors.append("rainfall")
        if ev.source == "sensor" and ev.score > 0.5:
            if "drainage" not in vectors:
                vectors.append("drainage")
        if ev.source == "historical" and ev.score > 0.5:
            if "low_elevation" not in vectors:
                vectors.append("low_elevation")

    # If severity is HIGH/CRITICAL, always include infrastructure
    severity = getattr(event, "severity", None)
    if severity and severity.value in ("HIGH", "CRITICAL"):
        vectors.append("infrastructure")

    # Fallback
    if not vectors:
        vectors = ["rainfall", "tidal_surge"]

    return vectors


def generate_mitigation_plan(event, event_id: str = "", district_id: Optional[str] = None, ref_water_m: float = 2.0) -> MitigationPlan:
    """
    Generate a full mitigation plan for a given flood event,
    incorporating topological bottleneck defense operations.
    """
    from backend.app.services.topological_engine import evaluate_district_topology

    # Infer district from event coordinates if not explicitly supplied
    resolved_zid = (district_id or "goa").lower()
    if event and hasattr(event, "latitude") and event.latitude:
        lat, lon = event.latitude, event.longitude
        if abs(lat - 12.9) < 1.0:
            resolved_zid = "mangaluru"
        elif abs(lat - 18.9) < 1.5:
            resolved_zid = "mumbai"
        else:
            resolved_zid = "goa"

    vectors = _detect_threat_vectors(event)
    suggestions: list[MitigationSuggestion] = []
    idx = 1

    # 1. Topological Bottleneck Defenses (Highest Priority Physical Defenses)
    try:
        topo_res = evaluate_district_topology(resolved_zid, ref_water_m=ref_water_m)
        for d in topo_res.defenses:
            suggestions.append(MitigationSuggestion(
                id=d.id,
                zone=d.road_name,
                action=d.action,
                description=d.description,
                priority=d.priority,
                threat_vector="infrastructure",
                estimated_cost=d.estimated_cost,
                time_to_deploy=d.time_to_deploy,
                resources_needed=d.resources_needed,
                effectiveness=d.effectiveness,
                status=d.status,
                coordinates=d.coordinates,
                is_topological=True,
                road_id=d.road_id,
            ))
    except Exception as exc:
        logger.warning("Could not evaluate topological defenses for %s: %s", resolved_zid, exc)

    # 2. Vector-based rules
    for vector in vectors:
        rules = _MITIGATION_RULES.get(vector, [])
        for rule in rules:
            suggestions.append(MitigationSuggestion(
                id=f"MIT-{idx:03d}",
                zone=f"Zone {chr(64 + idx)}" if idx <= 5 else "Zone A",
                action=rule["action"],
                description=rule["description"],
                priority=rule["priority"],
                threat_vector=vector,
                estimated_cost=rule["cost"],
                time_to_deploy=rule["time"],
                resources_needed=rule["resources"],
                effectiveness=rule["effectiveness"],
                is_topological=False,
            ))
            idx += 1

    # Sort by priority
    priority_order = {"IMMEDIATE": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    suggestions.sort(key=lambda s: priority_order.get(s.priority, 99))

    immediate = sum(1 for s in suggestions if s.priority == "IMMEDIATE")
    total_reduction = round(min(sum(s.effectiveness for s in suggestions), 0.95), 3)

    return MitigationPlan(
        event_id=event_id or (event.event_id if event else "unknown"),
        total_suggestions=len(suggestions),
        immediate_actions=immediate,
        estimated_risk_reduction=total_reduction,
        suggestions=suggestions,
    )

