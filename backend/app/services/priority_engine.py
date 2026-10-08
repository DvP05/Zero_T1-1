"""
TIDALIS — Emergency Priority Engine.

Scores every zone with the documented formula:

    priority = (Flood Probability * 0.40)
             + (Flood Severity   * 0.30)
             + (Critical Assets Affected * 0.30)

Isolated enclaves are promoted to the top of the board automatically:
when a neighbourhood has no passable egress route, it becomes the first
place responders must act.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.app.geospatial.city_model import ZONE_BY_ID, facilities_in_zone
from backend.app.ml.flood_model import ZonePrediction, risk_score
from backend.app.services.isolation_engine import IsolationReport


class PriorityItem(BaseModel):
    rank: int
    zone_id: str
    zone_name: str
    priority_score: float            # 0..1
    flood_probability: float
    risk_level: str
    severity_contribution: float
    probability_contribution: float
    assets_contribution: float
    critical_assets_at_risk: list[str] = Field(default_factory=list)
    affected_facility_count: int = 0
    total_facility_count: int = 0
    population: int = 0
    flood_depth_m: float = 0.0
    isolated: bool = False
    onset_hours: float | None = None
    urgency: str = "MONITOR"         # MONITOR | ELEVATED | URGENT | IMMEDIATE
    reasons: list[str] = Field(default_factory=list)


class PriorityBoard(BaseModel):
    items: list[PriorityItem] = Field(default_factory=list)
    top_zone: str = ""
    formula: str = "(probability * 0.40) + (severity * 0.30) + (critical assets * 0.30)"
    generated_note: str = ""


def _urgency(score: float, isolated: bool) -> str:
    if isolated or score >= 0.80:
        return "IMMEDIATE"
    if score >= 0.62:
        return "URGENT"
    if score >= 0.42:
        return "ELEVATED"
    return "MONITOR"


def compute_priorities(
    predictions: dict[str, ZonePrediction],
    zone_depths: dict[str, float],
    isolation: IsolationReport,
    onset_by_zone: dict[str, float | None] | None = None,
) -> PriorityBoard:
    onset_by_zone = onset_by_zone or {}
    isolated_ids = set(isolation.isolated_zones)
    items: list[PriorityItem] = []

    for zone_id, prediction in predictions.items():
        zone = ZONE_BY_ID.get(zone_id)
        if zone is None:
            continue

        facilities = facilities_in_zone(zone_id)
        depth = zone_depths.get(zone_id, 0.0)
        affected = [f for f in facilities if depth > 0.10]
        total_weight = sum(f.criticality for f in facilities)
        affected_weight = sum(f.criticality for f in affected)
        critical_ratio = (affected_weight / total_weight) if total_weight > 0 else 0.0

        severity_norm = risk_score(prediction.risk_level)
        probability = prediction.flood_probability
        isolated = zone_id in isolated_ids

        score = round(
            probability * 0.40 + severity_norm * 0.30 + critical_ratio * 0.30, 4
        )

        reasons: list[str] = []
        if isolated:
            reasons.append("Egress cut — isolated enclave, automatic top priority")
        if probability >= 0.75:
            reasons.append(f"Flood probability {probability:.0%} (CRITICAL band)")
        elif probability >= 0.50:
            reasons.append(f"Flood probability {probability:.0%} (HIGH band)")
        if affected:
            names = ", ".join(f.name for f in affected[:3])
            reasons.append(
                f"{len(affected)} critical facilit{'y' if len(affected) == 1 else 'ies'} threatened: {names}"
            )
        if depth > 0.05:
            reasons.append(f"Predicted flood depth {depth:.2f} m above ground level")
        onset = onset_by_zone.get(zone_id)
        if onset is not None:
            reasons.append(f"Expected onset in {onset:.1f} h")
        if not reasons:
            reasons.append("No significant threat at this time step")

        items.append(
            PriorityItem(
                rank=0,
                zone_id=zone_id,
                zone_name=zone.name,
                priority_score=score,
                flood_probability=round(probability, 4),
                risk_level=prediction.risk_level,
                severity_contribution=round(severity_norm * 0.30, 4),
                probability_contribution=round(probability * 0.40, 4),
                assets_contribution=round(critical_ratio * 0.30, 4),
                critical_assets_at_risk=[f.name for f in affected],
                affected_facility_count=len(affected),
                total_facility_count=len(facilities),
                population=zone.population,
                flood_depth_m=round(depth, 2),
                isolated=isolated,
                onset_hours=onset,
                urgency=_urgency(score, isolated),
                reasons=reasons,
            )
        )

    # isolated enclaves first, then by score, then earliest expected onset
    items.sort(
        key=lambda i: (
            not i.isolated,
            -i.priority_score,
            i.onset_hours if i.onset_hours is not None else 99.0,
            -i.flood_depth_m,
        )
    )
    for idx, item in enumerate(items, start=1):
        item.rank = idx

    return PriorityBoard(
        items=items,
        top_zone=items[0].zone_id if items else "",
        generated_note=(
            f"{sum(1 for i in items if i.isolated)} isolated enclave(s) promoted to the top of the board."
            if any(i.isolated for i in items)
            else "No isolated enclaves at this time step."
        ),
    )
