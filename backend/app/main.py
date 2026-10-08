"""
TIDALIS — FastAPI Main Application.

Central API server that exposes all TIDALIS intelligence endpoints.
On startup, it seeds demo data so the system is ready to demonstrate
the full decision loop.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# Windows consoles default to cp1252 — force UTF-8 so emoji log output works
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")

from backend.app.models.schemas import (
    CopilotRequest,
    CopilotResponse,
    CoastalState,
    Event,
    ExposureResult,
    Forecast,
    WhatIfRequest,
    WhatIfResult,
    CollectionRequest,
)
from backend.app.services.data_store import get_store
from backend.app.services.open_meteo import fetch_marine_data, normalise_marine_data
from backend.app.ml.anomaly_engine import compute_sensor_anomaly, detect_anomalies
from backend.app.ml.forecast_engine import generate_forecast
from backend.app.fusion.event_fusion import fuse_event
from backend.app.services.exposure_engine import compute_exposure
from backend.app.simulation.what_if import run_what_if
from backend.app.copilot.copilot_engine import handle_copilot
from backend.app.ml.telemetry import get_ml_telemetry
from backend.app.services.sos_engine import (
    SOSRequest,
    SOSTicket,
    submit_sos,
    get_all_sos_tickets,
    update_sos_status,
)
from backend.app.services.mitigation_engine import (
    MitigationPlan,
    generate_mitigation_plan,
)
from backend.app.services.collector_service import (
    get_all_zones,
    get_zone,
    get_zone_info,
    list_all_zones,
    get_zone_assets,
    get_collection_status,
    run_collection_pipeline,
)
from backend.app.geospatial.city_model import as_geojson
from backend.app.scenario.engine import (
    SCENARIO_HOURS,
    STEP_MINUTES,
    build_snapshot,
    scenario_meta,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan — seed demo data on startup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Seed demo data when the server starts."""
    logger.info("🌊 TIDALIS starting up — seeding demo data...")
    from scripts.seed_demo_data import seed
    seed()

    # Also fetch live marine data and cache it
    store = get_store()
    try:
        from backend.app.services.collector_service import run_collection_pipeline
        from backend.app.models.schemas import CollectionRequest
        # Fetch real-time data for Goa
        req = CollectionRequest(sources=["open_meteo", "tidalis"], scenario="heavy_coastal_rain")
        res = run_collection_pipeline("goa", req)
        logger.info("✓ Real data collection finished: %s", res.message)
        
        from backend.app.services.open_meteo import fetch_marine_data, normalise_marine_data
        raw = fetch_marine_data(15.2993, 73.9700)
        observations = normalise_marine_data(raw, 15.2993, 73.9700)
        store.observations.extend(observations)
        store.marine_cache = raw
        logger.info("✓ Marine data cached (%d observations)", len(observations))
    except Exception as exc:
        logger.warning("Real data collection failed (will use demo data): %s", exc)

    logger.info("✅ TIDALIS ready — %d events, %d sensors", len(store.events), len(store.get_sensors()))

    # Warm the flood model + scenario caches so the first scrub is instant
    try:
        from backend.app.ml.flood_model import get_flood_model
        from backend.app.scenario.engine import build_snapshot as _snap

        model = get_flood_model()
        _snap(0.0)
        logger.info(
            "✓ Flood model warmed (%s · accuracy %.1f%%)",
            model.kind, model.metrics["accuracy"] * 100,
        )
    except Exception as exc:
        logger.warning("Flood model warm-up failed: %s", exc)

    yield
    logger.info("TIDALIS shutting down.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="TIDALIS",
    description="AI-Powered Coastal Digital Intelligence & Digital Twin",
    version="1.0.0-hackathon",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.exception("Unhandled error processing %s: %s", request.url, exc)
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": str(exc)},
        headers={"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*"},
    )



# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health():
    store = get_store()
    return {
        "status": "ok",
        "service": "TIDALIS",
        "version": "1.0.0-hackathon",
        "sensors": len(store.get_sensors()),
        "events": len(store.events),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Locations & Multi-Zone Focus
# ---------------------------------------------------------------------------

ACTIVE_ZONE = "goa"

@app.get("/api/locations")
async def list_locations():
    """List lightweight summaries for all registered coastal focus zones."""
    return list_all_zones()


@app.get("/api/locations/{zone_id}")
async def location_detail(zone_id: str):
    """Get metadata and current data availability for a focus zone."""
    info = get_zone_info(zone_id)
    if not info:
        raise HTTPException(404, f"Zone '{zone_id}' not found")
    return info


@app.post("/api/locations/{zone_id}/activate")
async def activate_location(
    zone_id: str,
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
):
    """Set the active operational zone and initialize real overlay receptors."""
    global ACTIVE_ZONE
    zid = zone_id.lower().strip()
    z = get_zone(zid)
    if not z and zid != "custom":
        raise HTTPException(404, f"Zone '{zone_id}' not found")
    ACTIVE_ZONE = zid
    target_lat = lat if lat is not None else (z.lat if z else 12.9187)
    target_lon = lon if lon is not None else (z.lon if z else 74.8598)
    z_name = z.name if z else (f"Coordinates ({target_lat:.2f}, {target_lon:.2f})" if zid == "custom" else zid.title())

    if zid != "goa" or lat is not None:
        from backend.app.services.real_overlay_service import (
            generate_digital_twin_for_location,
            sync_live_sensors_and_events,
        )
        generate_digital_twin_for_location(target_lat, target_lon, z_name, zid)
        sync_live_sensors_and_events(target_lat, target_lon, z_name, zid)

    return {"status": "ok", "active_zone": ACTIVE_ZONE, "lat": target_lat, "lon": target_lon}


@app.get("/api/locations/{zone_id}/status")
async def location_collection_status(zone_id: str):
    """Check background or cached collection status for a zone."""
    return get_collection_status(zone_id)


@app.post("/api/locations/{zone_id}/collect")
async def trigger_collection(zone_id: str, request: Optional[CollectionRequest] = None):
    """Trigger on-demand data collection for a zone."""
    return run_collection_pipeline(zone_id, request)


# ---------------------------------------------------------------------------
# Coastal State
# ---------------------------------------------------------------------------

@app.get("/api/coastal-state", response_model=CoastalState)
async def coastal_state(
    lat: Optional[float] = Query(None, description="Latitude"),
    lon: Optional[float] = Query(None, description="Longitude"),
    zone_id: Optional[str] = Query(None, description="Coastal Zone ID"),
    refresh: bool = Query(False),
):
    store = get_store()
    zid = (zone_id or ACTIVE_ZONE or "goa").lower().strip()
    target_lat = lat
    target_lon = lon

    if zone_id or (target_lat is None or target_lon is None):
        z = get_zone(zid)
        if z:
            target_lat = z.lat
            target_lon = z.lon
        else:
            target_lat = target_lat or 15.2993
            target_lon = target_lon or 73.9700

    if refresh or not store.marine_cache:
        try:
            raw = fetch_marine_data(target_lat, target_lon)
            store.marine_cache = raw
            # Sync real sea surface temperature to sensors
            sst = None
            if raw and "hourly" in raw and "sea_surface_temperature" in raw["hourly"]:
                sst_vals = [v for v in raw["hourly"]["sea_surface_temperature"] if v is not None]
                if sst_vals:
                    sst = sst_vals[0]
            if sst is not None:
                for reading in store.sensor_readings:
                    reading.temperature = round(sst + (hash(reading.sensor_id) % 10) * 0.1, 1)
        except Exception as exc:
            logger.warning("Live marine fetch failed: %s", exc)

    state = store.get_coastal_state(target_lat, target_lon)
    state.zone_id = zid
    state.latitude = target_lat
    state.longitude = target_lon
    return state


# ---------------------------------------------------------------------------
# Sensors
# ---------------------------------------------------------------------------

@app.get("/api/sensors")
async def list_sensors(
    zone_id: Optional[str] = Query(None),
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
):
    store = get_store()
    zid = (zone_id or ACTIVE_ZONE or "goa").lower().strip()
    from data_collection.config import COASTAL_ZONES
    cz = COASTAL_ZONES.get(zid)
    base_lat = lat if lat is not None else (cz.lat if cz else 15.2993)
    base_lon = lon if lon is not None else (cz.lon if cz else 73.9700)
    z_name = cz.name if cz else (f"Coordinates ({base_lat:.2f}, {base_lon:.2f})" if zid == "custom" else zid.title())

    from backend.app.services.real_overlay_service import sync_live_sensors_and_events
    sync_live_sensors_and_events(base_lat, base_lon, z_name, zid)

    return store.get_sensors()


@app.get("/api/sensors/{sensor_id}")
async def get_sensor(sensor_id: str):
    store = get_store()
    sensor = store.get_sensor_by_id(sensor_id)
    if not sensor:
        raise HTTPException(404, f"Sensor {sensor_id} not found")
    return sensor


@app.get("/api/sensors/{sensor_id}/observations")
async def sensor_observations(sensor_id: str, limit: int = Query(48, ge=1, le=500)):
    store = get_store()
    obs = store.get_sensor_observations(sensor_id)
    # Return the most recent `limit` readings
    sorted_obs = sorted(obs, key=lambda r: r.timestamp, reverse=True)[:limit]
    return [r.model_dump() for r in sorted_obs]


@app.get("/api/sensors/latest/readings")
async def latest_readings():
    store = get_store()
    return [r.model_dump() for r in store.get_latest_readings()]


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

@app.get("/api/events", response_model=list[Event])
async def list_events():
    store = get_store()
    return store.events


@app.get("/api/events/{event_id}", response_model=Event)
async def get_event(event_id: str):
    store = get_store()
    event = store.get_event(event_id)
    if not event:
        raise HTTPException(404, f"Event {event_id} not found")
    return event


# ---------------------------------------------------------------------------
# Anomalies (live compute)
# ---------------------------------------------------------------------------

@app.get("/api/anomalies")
async def compute_anomalies():
    store = get_store()
    latest = store.get_latest_readings()
    anomalies = detect_anomalies(latest, threshold=0.30)
    return [a.model_dump() for a in anomalies]


# ---------------------------------------------------------------------------
# Forecast
# ---------------------------------------------------------------------------

@app.get("/api/forecast", response_model=Optional[Forecast])
async def get_forecast(event_id: str = Query(..., description="Event ID")):
    store = get_store()
    forecast = store.get_forecast(event_id)
    if not forecast:
        from backend.app.ml.forecast_engine import generate_forecast
        evt = store.get_event(event_id)
        primary_id = getattr(evt, "primary_sensor_id", None) if evt else None
        readings = store.get_sensor_observations(primary_id) if primary_id else []
        if not readings:
            readings = store.sensor_readings
        forecast = generate_forecast(readings, variable="turbidity", hours_ahead=24, event_id=event_id)
        store.forecasts.append(forecast)
    return forecast


# ---------------------------------------------------------------------------
# Exposure
# ---------------------------------------------------------------------------

@app.get("/api/exposure", response_model=list[ExposureResult])
async def get_exposure(event_id: str = Query(..., description="Event ID")):
    store = get_store()
    event = store.get_event(event_id) or (store.events[0] if store.events else None)
    if not event:
        raise HTTPException(404, f"Event {event_id} not found")
    return compute_exposure(event, store.assets, max_range_km=30.0)


@app.get("/api/assets")
async def list_assets(zone_id: Optional[str] = Query(None)):
    store = get_store()
    if zone_id:
        assets = get_zone_assets(zone_id)
        return [a.model_dump() for a in assets]
    return [a.model_dump() for a in store.assets]


# ---------------------------------------------------------------------------
# What-If Simulation
# ---------------------------------------------------------------------------

@app.post("/api/simulation/what-if", response_model=WhatIfResult)
async def simulate_what_if(request: WhatIfRequest):
    store = get_store()
    event = store.get_event(request.event_id)
    if not event:
        raise HTTPException(404, f"Event {request.event_id} not found")
    result = run_what_if(event, request)
    store.simulations.append(result)
    return result


# ---------------------------------------------------------------------------
# Copilot
# ---------------------------------------------------------------------------

@app.post("/api/copilot", response_model=CopilotResponse)
async def copilot(request: CopilotRequest):
    return handle_copilot(request)


# ---------------------------------------------------------------------------
# Marine Data (cached)
# ---------------------------------------------------------------------------

@app.get("/api/marine")
async def marine_data(
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
    zone_id: Optional[str] = Query(None),
    refresh: bool = Query(False),
):
    store = get_store()
    target_lat = lat
    target_lon = lon
    if zone_id or (target_lat is None or target_lon is None):
        z = get_zone(zone_id or "goa")
        if z:
            target_lat = z.lat
            target_lon = z.lon
        else:
            target_lat = target_lat or 15.2993
            target_lon = target_lon or 73.9700

    if store.marine_cache and not refresh:
        return store.marine_cache
    raw = fetch_marine_data(target_lat, target_lon)
    store.marine_cache = raw
    return raw


# ---------------------------------------------------------------------------
# ML Telemetry (Logging Page)
# ---------------------------------------------------------------------------

@app.get("/api/ml/telemetry")
async def ml_telemetry():
    """Return ML model diagnostics: accuracy, F1, feature importance, drift, inference log."""
    return get_ml_telemetry()


@app.post("/api/ml/retrain")
async def ml_retrain(
    lat: Optional[float] = Query(None, description="Target Latitude"),
    lon: Optional[float] = Query(None, description="Target Longitude"),
    name: Optional[str] = Query(None, description="Target Location Name"),
):
    """
    Triggers automated real-time retraining for a specific coastal location.
    Ingests live Open-Meteo observations and elevation, recalibrates XGBoost,
    and prints full verification metrics to the server terminal.
    """
    from scripts.retrain_live import run_retraining
    result = await asyncio.to_thread(run_retraining, lat, lon, name)
    return result


# ---------------------------------------------------------------------------
# SOS Triage
# ---------------------------------------------------------------------------

@app.post("/api/sos", response_model=SOSTicket)
async def create_sos(request: SOSRequest):
    """Submit an SOS distress signal. Returns a triaged ticket with rescue recommendation."""
    ticket = submit_sos(request)
    logger.info("🆘 SOS ticket %s created — urgency=%s, rescue=%s",
                ticket.ticket_id, ticket.urgency, ticket.rescue_method)
    return ticket


@app.get("/api/sos", response_model=list[SOSTicket])
async def list_sos():
    """Return all SOS tickets sorted by urgency (most critical first)."""
    return get_all_sos_tickets()


@app.patch("/api/sos/{ticket_id}")
async def patch_sos(ticket_id: str, status: str = Query(..., description="New status")):
    """Update the status of an SOS ticket (DISPATCHED, EN_ROUTE, RESCUED)."""
    ticket = update_sos_status(ticket_id, status)
    if not ticket:
        raise HTTPException(404, f"SOS ticket {ticket_id} not found")
    return ticket


# ---------------------------------------------------------------------------
# Mitigation Suggestions
# ---------------------------------------------------------------------------

@app.get("/api/mitigation", response_model=MitigationPlan)
async def get_mitigation(
    event_id: str = Query(..., description="Event ID"),
    district_id: Optional[str] = Query(None, description="District ID"),
):
    """Generate a mitigation plan for a given flood event."""
    store = get_store()
    event = store.get_event(event_id) or (store.events[0] if store.events else None)
    if not event:
        from backend.app.models.schemas import Event
        event = Event(event_id=event_id, latitude=15.2993, longitude=73.97)
    plan = generate_mitigation_plan(event, event_id or event.event_id, district_id=district_id)
    return plan


@app.post("/api/topological/defense/{defense_id}/authorize")
async def toggle_topological_defense(
    defense_id: str,
    district_id: Optional[str] = Query(None),
    water_level: float = Query(2.0),
):
    """Authorize or toggle deployment of physical dewatering pumps or flood barriers."""
    from backend.app.services.topological_engine import authorize_defense, evaluate_district_topology
    is_active = authorize_defense(defense_id)
    zid = (district_id or "goa").lower()
    updated_topo = evaluate_district_topology(zid, ref_water_m=water_level)
    return {
        "defense_id": defense_id,
        "is_active": is_active,
        "topology": updated_topo.model_dump(mode="json"),
    }


@app.get("/api/topological/analysis")
async def get_topological_analysis(
    district_id: Optional[str] = Query("goa"),
    water_level: float = Query(2.0),
):
    """Returns NetworkX road graph analysis: bottlenecks, physical defenses, and evacuation paths."""
    from backend.app.services.topological_engine import evaluate_district_topology
    zid = (district_id or "goa").lower()
    res = evaluate_district_topology(zid, ref_water_m=water_level)
    return res.model_dump(mode="json")



# ---------------------------------------------------------------------------
# Digital twin geometry (zones, roads, buildings, facilities)
# ---------------------------------------------------------------------------

@app.get("/api/geo")
async def geo_layers(
    zone_id: Optional[str] = Query(None),
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
):
    """GeoJSON layers for the 3D digital-twin map with real terrain elevation."""
    zid = (zone_id or ACTIVE_ZONE or "goa").lower().strip()
    return as_geojson(zid, lat, lon)


# ---------------------------------------------------------------------------
# Scenario timeline ("Heavy Coastal Rain Event" / Live Telemetry)
# ---------------------------------------------------------------------------

@app.get("/api/scenario")
async def scenario_overview(zone_id: Optional[str] = Query(None)):
    """Scenario metadata + the full T=0..T+5h step index."""
    return scenario_meta(zone_id)


@app.get("/api/scenario/snapshot")
async def scenario_snapshot(
    t: float = Query(0.0, ge=0.0, le=SCENARIO_HOURS, description="Hours since storm onset"),
    zone_id: Optional[str] = Query(None),
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
    live: bool = Query(True, description="Integrate live Open-Meteo telemetry into overlays"),
):
    """
    Full intelligence snapshot for one time step: environmental conditions,
    per-zone predictions, flood depths, isolation analysis, priority board
    and the GenAI command brief.
    """
    zid = (zone_id or ACTIVE_ZONE or "goa").lower().strip()
    target_lat = lat
    target_lon = lon

    if live:
        from backend.app.services.real_overlay_service import compute_live_overlay_snapshot
        from data_collection.config import COASTAL_ZONES
        cz = COASTAL_ZONES.get(zid)
        base_lat = target_lat if target_lat is not None else (cz.lat if cz else 15.2993)
        base_lon = target_lon if target_lon is not None else (cz.lon if cz else 73.9700)
        z_name = cz.name if cz else (f"Coordinates ({base_lat:.2f}, {base_lon:.2f})" if zid == "custom" else zid.title())
        snapshot = await asyncio.to_thread(
            compute_live_overlay_snapshot,
            lat=base_lat,
            lon=base_lon,
            name=z_name,
            zone_id=zid,
            t_hours=t,
        )
        return snapshot.model_dump(mode="json")

    snapshot = await asyncio.to_thread(build_snapshot, t)
    return snapshot.model_dump(mode="json")


# ---------------------------------------------------------------------------
# WebSocket — live "Play Scenario" control-room stream
# ---------------------------------------------------------------------------

@app.websocket("/ws/scenario")
async def scenario_socket(websocket: WebSocket):
    """
    Streams scenario snapshots for the Play button.

    Client → server: {"action": "play" | "pause" | "reset" | "seek", "t": float}
    Server → client: {"type": "meta" | "snapshot" | "status", ...}
    """
    await websocket.accept()
    step_h = STEP_MINUTES / 60.0
    state = {"t": 0.0, "playing": False}
    stream_task: asyncio.Task | None = None

    async def send_snapshot(t_value: float) -> None:
        snapshot = await asyncio.to_thread(build_snapshot, t_value)
        await websocket.send_json({"type": "snapshot", "snapshot": snapshot.model_dump(mode="json")})

    async def stream() -> None:
        try:
            while state["playing"]:
                if state["t"] >= SCENARIO_HOURS:
                    state["playing"] = False
                    break
                state["t"] = round(min(SCENARIO_HOURS, state["t"] + step_h), 4)
                await send_snapshot(state["t"])
                await asyncio.sleep(0.8)
        except asyncio.CancelledError:
            # paused/reset by the client — the handler already reported status
            raise
        except Exception:
            state["playing"] = False
        else:
            # stream ran to the end of the storm on its own
            try:
                await websocket.send_json(
                    {"type": "status", "playing": False, "t": state["t"]}
                )
            except Exception:
                pass

    try:
        await websocket.send_json({"type": "meta", "scenario": scenario_meta()})
        await send_snapshot(state["t"])

        while True:
            message = await websocket.receive_json()
            action = message.get("action")
            current = stream_task if stream_task and not stream_task.done() else None

            if action == "play":
                if current is None:
                    if state["t"] >= SCENARIO_HOURS:
                        state["t"] = 0.0
                    state["playing"] = True
                    stream_task = asyncio.create_task(stream())
                    await websocket.send_json(
                        {"type": "status", "playing": True, "t": state["t"]}
                    )

            elif action == "pause":
                state["playing"] = False
                if current:
                    current.cancel()
                stream_task = None
                await websocket.send_json({"type": "status", "playing": False, "t": state["t"]})

            elif action == "seek":
                target = float(message.get("t", 0.0))
                target = max(0.0, min(SCENARIO_HOURS, target))
                state["t"] = target
                await send_snapshot(target)
                await websocket.send_json(
                    {"type": "status", "playing": state["playing"], "t": target}
                )

            elif action == "reset":
                state["playing"] = False
                if current:
                    current.cancel()
                stream_task = None
                state["t"] = 0.0
                await send_snapshot(0.0)
                await websocket.send_json({"type": "status", "playing": False, "t": 0.0})

            else:
                await websocket.send_json({"type": "error", "detail": f"unknown action: {action}"})

    except WebSocketDisconnect:
        state["playing"] = False
        if stream_task:
            stream_task.cancel()
    except Exception:
        state["playing"] = False
        if stream_task:
            stream_task.cancel()

