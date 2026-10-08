"""
TIDALIS — scenario, priority, isolation and brief tests.

Covers the intelligence pipeline added for the time-machine scrubber:
environmental forcing, model predictions, isolation detection,
priority ranking and the GenAI command brief.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app.copilot.command_brief import generate_command_brief
from backend.app.geospatial.city_model import ZONES, as_geojson, facilities_in_zone
from backend.app.ml.flood_model import classify_risk, get_flood_model, hydrologic_depth
from backend.app.scenario.engine import (
    SCENARIO_HOURS,
    STEPS,
    build_snapshot,
    rainfall_at,
    scenario_meta,
    tide_at,
    water_level_at,
)
from backend.app.services.isolation_engine import evaluate_isolation
from backend.app.services.priority_engine import compute_priorities


# ---------------------------------------------------------------------------
# Environmental forcing
# ---------------------------------------------------------------------------

def test_forcing_increases_across_the_storm():
    assert rainfall_at(0) < rainfall_at(4) > rainfall_at(5)
    assert tide_at(0) < tide_at(2.5) < tide_at(5)
    assert water_level_at(0) < water_level_at(2.5) < water_level_at(5)


def test_scenario_timeline_shape():
    meta = scenario_meta()
    assert meta["duration_hours"] == SCENARIO_HOURS
    assert len(meta["steps"]) == len(STEPS)
    assert len(STEPS) == 21  # 5 hours at 15-minute resolution
    assert all(0.0 <= s["t_hours"] <= SCENARIO_HOURS for s in meta["steps"])


# ---------------------------------------------------------------------------
# Flood model
# ---------------------------------------------------------------------------

def test_model_probability_and_explanation():
    model = get_flood_model()
    features = {
        "rainfall_intensity": 40.0,
        "tide_level": 2.4,
        "storm_surge": 0.8,
        "elevation": 1.0,
        "drainage_capacity": 0.55,
        "soil_saturation": 0.95,
        "imperviousness": 0.7,
        "historical_flood_freq": 0.6,
    }
    prob = model.predict_probability(features)
    assert 0.0 <= prob <= 1.0
    drivers = model.explain(features)
    assert drivers, "every prediction must carry drivers"
    assert abs(sum(d.contribution for d in drivers)) <= 1.0
    low, high = model.predict_interval(features)
    assert 0.0 <= low <= high <= 1.0


def test_metrics_are_measured_not_invented():
    metrics = get_flood_model().metrics
    assert metrics["measured"] is True
    assert metrics["validation_samples"] > 0
    assert 0.5 <= metrics["accuracy"] <= 1.0
    assert 0.5 <= metrics["auc_roc"] <= 1.0
    confusion = metrics["confusion"]
    assert confusion["tn"] + confusion["fp"] + confusion["fn"] + confusion["tp"] == metrics["validation_samples"]


def test_deeper_water_increases_probability():
    model = get_flood_model()
    base = {
        "rainfall_intensity": 10.0, "tide_level": 1.2, "storm_surge": 0.2,
        "elevation": 1.0, "drainage_capacity": 0.7, "soil_saturation": 0.4,
        "imperviousness": 0.6, "historical_flood_freq": 0.3,
    }
    stormy = dict(base, rainfall_intensity=42.0, tide_level=2.4, storm_surge=0.8, soil_saturation=0.95)
    assert model.predict_probability(stormy) > model.predict_probability(base)
    assert hydrologic_depth(**{k: stormy[k] for k in (
        "rainfall_intensity", "tide_level", "storm_surge", "elevation",
        "drainage_capacity", "soil_saturation", "imperviousness")}) > 0


def test_risk_classification_thresholds():
    assert classify_risk(0.10) == "LOW"
    assert classify_risk(0.35) == "MODERATE"
    assert classify_risk(0.60) == "HIGH"
    assert classify_risk(0.90) == "CRITICAL"


# ---------------------------------------------------------------------------
# Isolation
# ---------------------------------------------------------------------------

def test_isolation_at_start_and_peak():
    start = evaluate_isolation(water_level_at(0.0), {z.id: 0.0 for z in ZONES})
    assert start.enclaves == []
    assert start.network_integrity == 1.0

    peak = evaluate_isolation(water_level_at(SCENARIO_HOURS), {z.id: 2.0 for z in ZONES})
    assert peak.network_integrity < 1.0
    assert set(peak.isolated_zones) >= {"A", "B", "C"}
    assert {"D", "E"}.isdisjoint(peak.isolated_zones)
    assert all(not r.passable for r in peak.blocked_roads)


def test_road_status_records_submersion():
    report = evaluate_isolation(2.60, {})
    by_id = {r.id: r for r in report.blocked_roads + report.passable_roads}
    assert by_id["RD-02"].passable is False           # elevation 1.00 m
    assert by_id["RD-07"].passable is True            # elevation 8.00 m
    assert by_id["RD-02"].submersion_m > 0


# ---------------------------------------------------------------------------
# Priority engine
# ---------------------------------------------------------------------------

def test_priority_formula_and_isolation_promotion():
    snapshot = build_snapshot(SCENARIO_HOURS)
    board = snapshot.priorities
    assert len(board.items) == len(ZONES)
    assert [i.rank for i in board.items] == list(range(1, len(ZONES) + 1))

    for item in board.items:
        assert 0.0 <= item.priority_score <= 1.0
        expected = item.probability_contribution + item.severity_contribution + item.assets_contribution
        assert abs(item.priority_score - expected) < 0.005

    # every isolated enclave outranks every connected zone
    isolated = [i for i in board.items if i.isolated]
    connected = [i for i in board.items if not i.isolated]
    if isolated and connected:
        assert max(i.rank for i in isolated) < min(i.rank for i in connected)


def test_priority_reflects_asset_exposure():
    snapshot = build_snapshot(SCENARIO_HOURS)
    top = snapshot.priorities.items[0]
    zone = next(z for z in snapshot.zones if z.zone_id == top.zone_id)
    if zone.flood_depth_m > 0.1:
        assert top.affected_facility_count >= 1
        assert facilities_in_zone(top.zone_id)


# ---------------------------------------------------------------------------
# Snapshots & brief
# ---------------------------------------------------------------------------

def test_snapshot_contains_all_intelligence_layers():
    snapshot = build_snapshot(2.0)
    assert len(snapshot.zones) == len(ZONES)
    assert snapshot.priorities.items
    assert snapshot.isolation.summary
    assert snapshot.brief and snapshot.brief_headline
    assert snapshot.conditions.rainfall_mm_h > 0
    assert snapshot.aggregate_risk in {"LOW", "MODERATE", "HIGH", "CRITICAL"}
    assert all(0.0 <= z.flood_probability <= 1.0 for z in snapshot.zones)
    assert all(z.drivers for z in snapshot.zones)


def test_risk_escalates_over_time():
    early = build_snapshot(0.0)
    late = build_snapshot(SCENARIO_HOURS)
    order = {"LOW": 0, "MODERATE": 1, "HIGH": 2, "CRITICAL": 3}
    assert order[late.aggregate_risk] > order[early.aggregate_risk]
    assert late.isolation.network_integrity < early.isolation.network_integrity
    assert len(late.alerts) > 0


def test_command_brief_is_grounded_in_model_output():
    snapshot = build_snapshot(4.0)
    headline, body = generate_command_brief(
        conditions=snapshot.conditions,
        zones=snapshot.zones,
        priorities=snapshot.priorities,
        isolation=snapshot.isolation,
        aggregate_risk=snapshot.aggregate_risk,
    )
    assert headline
    assert "decision-support" in body
    assert "%" in body  # probability actually quoted


# ---------------------------------------------------------------------------
# Geo layers
# ---------------------------------------------------------------------------

def test_geo_layers_bundle():
    bundle = as_geojson()
    layers = bundle["layers"]
    assert len(layers["zones"]["features"]) == len(ZONES) == 5
    assert len(layers["roads"]["features"]) == 9
    assert len(layers["buildings"]["features"]) > 20
    assert any(f["properties"]["is_hub"] for f in layers["nodes"]["features"])
    assert bundle["meta"]["demo_data"] is True
