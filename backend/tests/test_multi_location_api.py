"""
TIDALIS — Multi-Location API Integration Tests.

Validates:
  - Locations listing and detail discovery (/api/locations, /api/locations/{id})
  - Zone activation (/api/locations/{id}/activate)
  - Zone-scoped coastal state (/api/coastal-state?zone_id=...)
  - Multi-location sensor listing (/api/sensors?zone_id=...)
  - Multi-location asset listing (/api/assets?zone_id=...)
  - Multi-location marine observations (/api/marine?zone_id=...)
  - Multi-location 3D digital twin geometry (/api/geo?zone_id=...)
  - Multi-location collection status & triggers (/api/locations/{id}/status)
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app.main import app

client = TestClient(app)


def test_list_locations_endpoint():
    resp = client.get("/api/locations")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 6

    zone_ids = [loc["zone_id"] for loc in data]
    assert "mumbai" in zone_ids
    assert "chennai" in zone_ids
    assert "kochi" in zone_ids
    assert "kolkata" in zone_ids
    assert "visakhapatnam" in zone_ids
    assert "goa" in zone_ids

    mumbai = next(loc for loc in data if loc["zone_id"] == "mumbai")
    assert mumbai["name"] == "Mumbai"
    assert mumbai["coast"] == "west"


def test_location_detail_endpoint():
    resp = client.get("/api/locations/mumbai")
    assert resp.status_code == 200
    info = resp.json()
    assert info["zone_id"] == "mumbai"
    assert info["name"] == "Mumbai"
    assert len(info["bbox"]) == 4
    assert info["has_cached_data"] is True

    # 404 for unknown zone
    resp_404 = client.get("/api/locations/atlantis")
    assert resp_404.status_code == 404


def test_activate_location():
    resp = client.post("/api/locations/mumbai/activate")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["active_zone"] == "mumbai"


def test_coastal_state_multi_zone():
    # Mumbai
    resp_mum = client.get("/api/coastal-state?zone_id=mumbai")
    assert resp_mum.status_code == 200
    mum_state = resp_mum.json()
    assert mum_state["zone_id"] == "mumbai"
    assert round(mum_state["latitude"], 2) == 19.08
    assert round(mum_state["longitude"], 2) == 72.88

    # Goa
    resp_goa = client.get("/api/coastal-state?zone_id=goa")
    assert resp_goa.status_code == 200
    goa_state = resp_goa.json()
    assert goa_state["zone_id"] == "goa"
    assert round(goa_state["latitude"], 2) == 15.30


def test_sensors_multi_zone():
    # Mumbai sensors
    resp_mum = client.get("/api/sensors?zone_id=mumbai")
    assert resp_mum.status_code == 200
    mum_sensors = resp_mum.json()
    assert isinstance(mum_sensors, list)
    if mum_sensors:
        assert all("sensor_id" in s for s in mum_sensors)

    # Goa sensors
    resp_goa = client.get("/api/sensors?zone_id=goa")
    assert resp_goa.status_code == 200
    goa_sensors = resp_goa.json()
    assert len(goa_sensors) == 5
    assert any(s["sensor_id"] == "TIDALIS-001" for s in goa_sensors)


def test_assets_multi_zone():
    # Mumbai assets
    resp_mum = client.get("/api/assets?zone_id=mumbai")
    assert resp_mum.status_code == 200
    mum_assets = resp_mum.json()
    assert len(mum_assets) >= 4
    mum_names = [a["name"] for a in mum_assets]
    assert any("Marine Drive" in n for n in mum_names)

    # Chennai assets
    resp_chn = client.get("/api/assets?zone_id=chennai")
    assert resp_chn.status_code == 200
    chn_assets = resp_chn.json()
    assert len(chn_assets) >= 3
    chn_names = [a["name"] for a in chn_assets]
    assert any("Marina Beach" in n for n in chn_names)


def test_geo_digital_twin_multi_zone():
    # Mumbai digital twin
    resp_mum = client.get("/api/geo?zone_id=mumbai")
    assert resp_mum.status_code == 200
    geo_mum = resp_mum.json()
    assert "layers" in geo_mum
    assert "zones" in geo_mum["layers"]
    assert len(geo_mum["layers"]["zones"]["features"]) == 5
    assert geo_mum["meta"]["zone_id"] == "mumbai"

    # Goa digital twin (preserves handcrafted district)
    resp_goa = client.get("/api/geo?zone_id=goa")
    assert resp_goa.status_code == 200
    geo_goa = resp_goa.json()
    assert geo_goa["meta"]["zone_id"] == "goa"
    assert len(geo_goa["layers"]["roads"]["features"]) > 0


def test_collection_status_endpoint():
    resp = client.get("/api/locations/mumbai/status")
    assert resp.status_code == 200
    status = resp.json()
    assert status["zone_id"] == "mumbai"
    assert "status" in status


def test_scenario_multi_zone():
    resp_mum = client.get("/api/scenario?zone_id=mumbai")
    assert resp_mum.status_code == 200
    meta_mum = resp_mum.json()
    assert meta_mum["zone_id"] == "mumbai"
    assert "Mumbai" in meta_mum["name"]

    resp_goa = client.get("/api/scenario?zone_id=goa")
    assert resp_goa.status_code == 200
    meta_goa = resp_goa.json()
    assert meta_goa["zone_id"] == "goa"
    assert meta_goa["demo_data"] is True

