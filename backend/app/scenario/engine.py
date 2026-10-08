"""
TIDALIS — "Heavy Coastal Rain Event" scenario engine.

A controlled, deterministic T=0 → T+5 h storm timeline used for the
hackathon demo.  Every time step produces a full intelligence snapshot:

    environmental conditions
      → flood-model prediction per zone (probability / risk / drivers)
      → flood depth per zone
      → road-network isolation analysis
      → emergency priority board
      → GenAI command brief

The scrubber on the dashboard and the WebSocket "play" stream both read
from this engine, so scrubbing and streaming always agree.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache

from pydantic import BaseModel, Field

from backend.app.copilot.command_brief import generate_command_brief
from backend.app.geospatial.city_model import ZONES, ZONE_BY_ID, facilities_in_zone
from backend.app.ml.flood_model import classify_risk, get_flood_model
from backend.app.services.isolation_engine import IsolationReport, evaluate_isolation
from backend.app.services.priority_engine import PriorityBoard, compute_priorities


SCENARIO_ID = "SCN-RAIN-001"
SCENARIO_NAME = "Heavy Coastal Rain Event"
SCENARIO_HOURS = 5.0
STEP_MINUTES = 15
STEPS: list[float] = [round(i * STEP_MINUTES / 60, 4) for i in range(int(SCENARIO_HOURS * 60 / STEP_MINUTES) + 1)]

_START_TIME: datetime | None = None


def _scenario_start() -> datetime:
    global _START_TIME
    if _START_TIME is None:
        _START_TIME = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    return _START_TIME


# ---------------------------------------------------------------------------
# Environmental forcing
# ---------------------------------------------------------------------------

def rainfall_at(t: float) -> float:
    """mm/h — light rain that builds to a peak around T+4h, then eases."""
    if t <= 4.0:
        return round(2.0 + 40.0 * (max(t, 0.0) / 4.0) ** 1.6, 2)
    return round(42.0 - 5.0 * (t - 4.0), 2)


def tide_at(t: float) -> float:
    """metres above MSL — incoming spring tide across the window."""
    return round(0.85 + 1.30 * (max(t, 0.0) / SCENARIO_HOURS) ** 1.05, 3)


def surge_at(t: float) -> float:
    """metres — storm surge that grows quadratically with the storm."""
    return round(0.04 + 0.72 * (max(t, 0.0) / SCENARIO_HOURS) ** 2, 3)


def cumulative_rain(t: float, dt: float = 0.05) -> float:
    """mm — time integral of rainfall intensity up to hour t."""
    if t <= 0:
        return 0.0
    steps = int(t / dt)
    total = 0.0
    for i in range(steps):
        total += rainfall_at(i * dt) * dt
    total += rainfall_at(t) * (t - steps * dt)
    return round(total, 2)


def soil_saturation_at(t: float) -> float:
    return round(min(1.0, 0.25 + 0.70 * cumulative_rain(t) / 90.0), 3)


def drainage_utilisation_at(t: float) -> float:
    """How hard the drainage network is working (0..1, 1 = saturated)."""
    return round(min(0.99, 0.30 + 0.62 * cumulative_rain(t) / 120.0 + 0.20 * (t / SCENARIO_HOURS)), 3)


def water_level_at(t: float) -> float:
    """
    Reference water level in the road corridors (tide + surge + urban
    runoff, referenced to mean sea level).  Used to decide which road
    segments are submerged.
    """
    from backend.app.ml.flood_model import hydrologic_depth

    return round(
        hydrologic_depth(
            rainfall_at(t), tide_at(t), surge_at(t),
            elevation=0.0, drainage_capacity=0.70,
            soil_saturation=soil_saturation_at(t), imperviousness=0.85,
        ),
        3,
    )


# ---------------------------------------------------------------------------
# Zone water balance (shared by training data and live scenario)
# ---------------------------------------------------------------------------

def zone_depth(
    rainfall: float,
    tide: float,
    surge: float,
    elevation: float,
    drainage: float,
    soil: float,
    imperviousness: float,
) -> float:
    """Predicted still-water depth above ground level (metres, >= 0)."""
    from backend.app.ml.flood_model import hydrologic_depth

    return round(
        hydrologic_depth(rainfall, tide, surge, elevation, drainage, soil, imperviousness),
        3,
    )


def zone_features(zone, t: float) -> dict[str, float]:
    return {
        "rainfall_intensity": rainfall_at(t),
        "tide_level": tide_at(t),
        "storm_surge": surge_at(t),
        "elevation": zone.elevation_m,
        "drainage_capacity": zone.drainage_capacity,
        "soil_saturation": soil_saturation_at(t),
        "imperviousness": zone.imperviousness,
        "historical_flood_freq": zone.historical_flood_freq,
    }


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ScenarioConditions(BaseModel):
    t_hours: float
    label: str
    timestamp: datetime
    rainfall_mm_h: float
    tide_level_m: float
    storm_surge_m: float
    soil_saturation: float
    drainage_utilisation: float
    cumulative_rain_mm: float
    water_level_m: float
    headline: str


class ZoneState(BaseModel):
    zone_id: str
    zone_name: str
    elevation_m: float
    population: int
    vulnerability: float
    flood_probability: float
    risk_level: str
    risk_color: str
    confidence: float
    interval_low: float
    interval_high: float
    flood_depth_m: float
    drivers: list[dict] = Field(default_factory=list)
    facilities_threatened: list[str] = Field(default_factory=list)
    onset_hours: float | None = None
    peak_hours: float | None = None
    peak_probability: float = 0.0


class Alert(BaseModel):
    id: str
    t_hours: float
    level: str  # INFO | WATCH | WARNING | CRITICAL
    message: str


class ScenarioSnapshot(BaseModel):
    scenario_id: str
    scenario_name: str
    t_hours: float
    label: str
    timestamp: datetime
    conditions: ScenarioConditions
    zones: list[ZoneState] = Field(default_factory=list)
    priorities: PriorityBoard
    isolation: IsolationReport
    alerts: list[Alert] = Field(default_factory=list)
    brief_headline: str = ""
    brief: str = ""
    aggregate_risk: str = "LOW"
    demo_data: bool = True


# ---------------------------------------------------------------------------
# Trajectories (onset / peak), computed once
# ---------------------------------------------------------------------------

@lru_cache(maxsize=32)
def _probability_trajectory(zone_id: str) -> tuple[tuple[float, float], ...]:
    model = get_flood_model()
    zone = ZONE_BY_ID[zone_id]
    points = []
    for t in STEPS:
        prob = model.predict_probability(zone_features(zone, t))
        points.append((t, round(prob, 4)))
    return tuple(points)


def onset_and_peak(zone_id: str) -> tuple[float | None, float | None, float]:
    traj = _probability_trajectory(zone_id)
    onset = next((t for t, p in traj if p >= 0.50), None)
    peak_t, peak_p = max(traj, key=lambda pt: pt[1])
    return onset, peak_t, peak_p


def _time_label(t: float) -> str:
    stamp = _scenario_start() + timedelta(hours=t)
    return f"T+{t:.2f}h · {stamp.strftime('%H:%M')} UTC"


def _headline(risk: str) -> str:
    if risk == "CRITICAL":
        return "CRITICAL — overland flooding in progress"
    if risk == "HIGH":
        return "HIGH — floodwater entering low-lying streets"
    if risk == "MODERATE":
        return "MODERATE — ponding beginning, drains near capacity"
    return "LOW — rain building, tide still below flood thresholds"


# ---------------------------------------------------------------------------
# Snapshot builder
# ---------------------------------------------------------------------------

def build_snapshot(t: float) -> ScenarioSnapshot:
    t = round(max(0.0, min(SCENARIO_HOURS, t)), 4)
    model = get_flood_model()

    rain = rainfall_at(t)
    tide = tide_at(t)
    surge = surge_at(t)
    soil = soil_saturation_at(t)
    cum = cumulative_rain(t)
    water = water_level_at(t)

    zone_depths: dict[str, float] = {}
    predictions = {}
    zone_states: list[ZoneState] = []
    alerts: list[Alert] = []

    for zone in ZONES:
        features = zone_features(zone, t)
        prob = model.predict_probability(features)
        risk = classify_risk(prob)
        low, high = model.predict_interval(features)
        drivers = model.explain(features)
        depth = zone_depth(
            rain, tide, surge,
            zone.elevation_m, zone.drainage_capacity, soil, zone.imperviousness,
        )
        zone_depths[zone.id] = depth

        onset, peak_t, peak_p = onset_and_peak(zone.id)
        prediction = _mk_prediction(zone.id, prob, risk, low, high, drivers)
        predictions[zone.id] = prediction

        threatened = [
            f.name for f in facilities_in_zone(zone.id)
            if depth > 0.10 or prob >= 0.75
        ]
        zone_states.append(
            ZoneState(
                zone_id=zone.id,
                zone_name=zone.name,
                elevation_m=zone.elevation_m,
                population=zone.population,
                vulnerability=zone.vulnerability,
                flood_probability=round(prob, 4),
                risk_level=risk,
                risk_color={"LOW": "#34d399", "MODERATE": "#fbbf24", "HIGH": "#fb923c", "CRITICAL": "#fb7185"}[risk],
                confidence=round(min(0.99, 0.72 + 0.5 * abs(prob - 0.5)), 3),
                interval_low=low,
                interval_high=high,
                flood_depth_m=depth,
                drivers=[d.model_dump() for d in drivers],
                facilities_threatened=threatened,
                onset_hours=onset,
                peak_hours=peak_t,
                peak_probability=peak_p,
            )
        )

    aggregate = max(
        (s.risk_level for s in zone_states),
        key=lambda r: ["LOW", "MODERATE", "HIGH", "CRITICAL"].index(r),
    )

    isolation = evaluate_isolation(water, zone_depths)
    onset_by_zone = {s.zone_id: s.onset_hours for s in zone_states}
    priorities = compute_priorities(predictions, zone_depths, isolation, onset_by_zone)

    # ---- alerts ----------------------------------------------------------
    alerts.extend(_scenario_alerts(t, zone_states, isolation, water))

    conditions = ScenarioConditions(
        t_hours=t,
        label=_time_label(t),
        timestamp=_scenario_start() + timedelta(hours=t),
        rainfall_mm_h=rain,
        tide_level_m=tide,
        storm_surge_m=surge,
        soil_saturation=soil,
        drainage_utilisation=drainage_utilisation_at(t),
        cumulative_rain_mm=cum,
        water_level_m=water,
        headline=_headline(aggregate),
    )

    headline, brief = generate_command_brief(
        conditions=conditions,
        zones=zone_states,
        priorities=priorities,
        isolation=isolation,
        aggregate_risk=aggregate,
    )

    return ScenarioSnapshot(
        scenario_id=SCENARIO_ID,
        scenario_name=SCENARIO_NAME,
        t_hours=t,
        label=conditions.label,
        timestamp=conditions.timestamp,
        conditions=conditions,
        zones=zone_states,
        priorities=priorities,
        isolation=isolation,
        alerts=alerts,
        brief_headline=headline,
        brief=brief,
        aggregate_risk=aggregate,
    )


def _mk_prediction(zone_id, prob, risk, low, high, drivers):
    from backend.app.ml.flood_model import ZonePrediction

    return ZonePrediction(
        zone_id=zone_id,
        flood_probability=round(prob, 4),
        risk_level=risk,
        confidence=round(min(0.99, 0.72 + 0.5 * abs(prob - 0.5)), 3),
        interval_low=low,
        interval_high=high,
        drivers=drivers,
    )


def _scenario_alerts(
    t: float,
    zones: list[ZoneState],
    isolation: IsolationReport,
    water: float,
) -> list[Alert]:
    alerts: list[Alert] = []

    for state in zones:
        if state.risk_level == "CRITICAL" and state.flood_depth_m > 0.5:
            alerts.append(Alert(
                id=f"ALT-{state.zone_id}-CRIT",
                t_hours=t,
                level="CRITICAL",
                message=f"{state.zone_name} — {state.flood_probability:.0%} flood probability, "
                        f"{state.flood_depth_m:.2f} m standing water",
            ))
        elif state.risk_level == "HIGH":
            alerts.append(Alert(
                id=f"ALT-{state.zone_id}-HIGH",
                t_hours=t,
                level="WARNING",
                message=f"{state.zone_name} escalated to HIGH risk ({state.flood_probability:.0%})",
            ))

    for road in isolation.blocked_roads:
        if road.critical:
            alerts.append(Alert(
                id=f"ALT-{road.id}",
                t_hours=t,
                level="WARNING",
                message=f"{road.name} impassable — water {road.submersion_m:.2f} m over road surface",
            ))

    for enclave in isolation.enclaves:
        alerts.append(Alert(
            id=f"ALT-ISO-{enclave.zone_id}",
            t_hours=t,
            level="CRITICAL",
            message=f"ISOLATED ENCLAVE: {enclave.zone_name} — all egress routes severed "
                    f"({enclave.population} residents cut off)",
        ))

    order = {"CRITICAL": 0, "WARNING": 1, "WATCH": 2, "INFO": 3}
    alerts.sort(key=lambda a: order.get(a.level, 9))
    return alerts[:8]


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def scenario_meta(zone_id: Optional[str] = None) -> dict:
    zid = (zone_id or "goa").lower().strip()
    from data_collection.config import COASTAL_ZONES
    cz = COASTAL_ZONES.get(zid)
    z_name = cz.name if cz else zid.title()

    return {
        "id": f"SCN-{zid.upper()}-001" if zid != "goa" else SCENARIO_ID,
        "zone_id": zid,
        "name": f"{z_name} Storm Scenario" if zid != "goa" else SCENARIO_NAME,
        "description": (
            f"A 5-hour coastal storm for {z_name}: rainfall and marine surge push the water table up."
        ),
        "duration_hours": SCENARIO_HOURS,
        "step_minutes": STEP_MINUTES,
        "steps": [
            {
                "t_hours": t,
                "label": _time_label(t),
                "rainfall_mm_h": rainfall_at(t),
                "tide_level_m": tide_at(t),
                "risk_level": classify_risk(_probability_trajectory_zone_at(t)),
            }
            for t in STEPS
        ],
        "demo_data": True,
    }


def _probability_trajectory_zone_at(t: float) -> float:
    """Aggregate risk proxy for the step list (zone B, the canary zone)."""
    model = get_flood_model()
    zone = ZONE_BY_ID["B"]
    return model.predict_probability(zone_features(zone, t))
