"""
Tests for Phase 1 & 2: Multi-location registry, data ingestion, and collector service.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app.models.schemas import CoastalZoneInfo, LocationSummary
from backend.app.services.collector_service import (
    check_zone_cache,
    find_nearest_zone,
    get_all_zones,
    get_collection_status,
    get_zone,
    get_zone_assets,
    get_zone_info,
    ingest_open_meteo_cache,
    ingest_tidalis_cache,
    list_all_zones,
)


def test_zone_registry_includes_all_focus_zones():
    zones = get_all_zones()
    expected = {"mumbai", "chennai", "kochi", "kolkata", "visakhapatnam", "goa"}
    assert expected.issubset(set(zones.keys())), f"Missing zones: {expected - set(zones.keys())}"


def test_list_all_zones_summary():
    summaries = list_all_zones()
    assert len(summaries) >= 6
    zone_ids = [s.zone_id for s in summaries]
    assert "mumbai" in zone_ids
    assert "chennai" in zone_ids
    assert "goa" in zone_ids

    mumbai = next(s for s in summaries if s.zone_id == "mumbai")
    assert mumbai.lat == 19.0760
    assert mumbai.lon == 72.8777
    assert mumbai.coast == "west"


def test_get_zone_info_and_caching():
    info = get_zone_info("mumbai")
    assert info is not None
    assert info.name == "Mumbai"
    assert info.has_cached_data is True
    assert len(info.bbox) == 4

    goa_info = get_zone_info("goa")
    assert goa_info is not None
    assert goa_info.name.startswith("Goa")


def test_find_nearest_zone():
    # Near Mumbai coordinates
    zid, z = find_nearest_zone(19.0, 72.9)
    assert zid == "mumbai"

    # Near Chennai coordinates
    zid, z = find_nearest_zone(13.1, 80.2)
    assert zid == "chennai"

    # Near Goa coordinates
    zid, z = find_nearest_zone(15.3, 73.9)
    assert zid == "goa"


def test_get_zone_assets():
    mumbai_assets = get_zone_assets("mumbai")
    assert len(mumbai_assets) >= 4
    names = [a.name for a in mumbai_assets]
    assert any("Marine Drive" in n for n in names)
    assert any("Port" in n for n in names)

    chennai_assets = get_zone_assets("chennai")
    assert len(chennai_assets) >= 3
    names_ch = [a.name for a in chennai_assets]
    assert any("Marina Beach" in n for n in names_ch)


def test_ingest_open_meteo_mumbai_cache():
    obs = ingest_open_meteo_cache("mumbai")
    assert len(obs) > 0, "Expected observations from cached Mumbai CSVs"
    first = obs[0]
    assert first.zone_id == "mumbai"
    assert first.source in ("open_meteo_marine", "open_meteo_weather")
    assert len(first.variables) > 0


def test_ingest_tidalis_mumbai_cache():
    readings = ingest_tidalis_cache("mumbai")
    assert len(readings) > 0, "Expected readings from cached Mumbai Tidalis CSV"
    first = readings[0]
    assert first.zone_id == "mumbai"
    assert first.latitude != 0.0
    assert first.sensor_id.startswith("TDL-MUM")


def test_get_collection_status():
    status = get_collection_status("mumbai")
    assert status.zone_id == "mumbai"
    assert status.status in ("idle", "completed", "running")
