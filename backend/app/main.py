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

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# Windows consoles default to cp1252 — force UTF-8 so emoji log output works
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")

from backend.app.models.schemas import (
    CoastalZoneInfo,
    CollectionRequest,
    CollectionStatus,
    CopilotRequest,
    CopilotResponse,
    CoastalState,
    Event,
    ExposureResult,
    Forecast,
    LocationSummary,
    WhatIfRequest,
    WhatIfResult,
)
from backend.app.services.data_store import get_store
from backend.app.services.open_meteo import fetch_marine_data, normalise_marine_data
from backend.app.services.collector_service import (
    get_all_zones,
    get_collection_status,
    get_zone,
    get_zone_info,
    list_all_zones,
    run_collection_pipeline,
)
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
    """Seed demo data and load cached coastal focus zones when the server starts."""
    logger.info("🌊 TIDALIS starting up — seeding demo data...")
    try:
        from scripts.seed_demo_data import seed
        seed()
    except Exception as exc:
        logger.warning("Seed demo data failed: %s", exc)

    store = get_store()

    # Ingest cached multi-zone datasets (e.g. Mumbai)
    try:
        mumbai_res = store.load_zone("mumbai")
        logger.info("✓ Mumbai data loaded: %s", mumbai_res)
    except Exception as exc:
        logger.warning("Mumbai data load failed: %s", exc)

    # Also fetch live marine data and cache it
    try:
        raw = fetch_marine_data(15.2993, 73.9700)
        observations = normalise_marine_data(raw, 15.2993, 73.9700)
        store.observations.extend(observations)
        store.marine_cache = raw
        store.zone_marine_cache["goa"] = raw
        logger.info("✓ Marine data cached (%d observations)", len(observations))
    except Exception as exc:
        logger.warning("Marine data fetch failed (will use demo data): %s", exc)

    logger.info("✅ TIDALIS ready — %d events, %d sensors across zones", len(store.events), len(store.get_sensors()))

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
# Locations & Multi-Zone Management
# ---------------------------------------------------------------------------

@app.get("/api/locations", response_model=list[LocationSummary])
async def get_locations():
    """List all registered coastal focus zones with cache & telemetry status."""
    return list_all_zones()


@app.get("/api/locations/{zone_id}", response_model=CoastalZoneInfo)
async def get_location_details(zone_id: str):
    """Get detailed geographic bounding box and telemetry for a coastal zone."""
    info = get_zone_info(zone_id)
    if not info:
        raise HTTPException(404, f"Coastal zone '{zone_id}' not found")
    return info


@app.post("/api/locations/{zone_id}/activate")
async def activate_location(zone_id: str):
    """Set the active default coastal zone for the platform."""
    z = get_zone(zone_id)
    if not z:
        raise HTTPException(404, f"Coastal zone '{zone_id}' not found")
    store = get_store()
    store.active_zone_id = zone_id.lower().strip()
    return {"status": "ok", "active_zone": zone_id, "name": z.name}


@app.post("/api/locations/{zone_id}/collect", response_model=CollectionStatus)
async def trigger_collection(
    zone_id: str,
    background_tasks: BackgroundTasks,
    request: Optional[CollectionRequest] = None,
    sync: bool = Query(False, description="Run synchronously if True, else background task"),
):
    """
    Trigger data collection (Open-Meteo live, Tidalis IoT simulation, etc.) for a zone.
    """
    z = get_zone(zone_id)
    if not z:
        raise HTTPException(404, f"Coastal zone '{zone_id}' not found")

    req = request or CollectionRequest()
    store = get_store()

    if sync:
        status = run_collection_pipeline(zone_id, req)
        store.load_zone(zone_id)
        return status
    else:
        def _bg_task():
            run_collection_pipeline(zone_id, req)
            store.load_zone(zone_id)

        background_tasks.add_task(_bg_task)
        return CollectionStatus(
            zone_id=zone_id.lower().strip(),
            status="running",
            message=f"Collection queued in background for {z.name}",
            sources=req.sources,
            updated_at=datetime.now(timezone.utc),
        )


@app.get("/api/locations/{zone_id}/status", response_model=CollectionStatus)
async def collection_status(zone_id: str):
    """Get current data collection pipeline status for a zone."""
    z = get_zone(zone_id)
    if not z:
        raise HTTPException(404, f"Coastal zone '{zone_id}' not found")
    return get_collection_status(zone_id)


# ---------------------------------------------------------------------------
# Coastal State
# ---------------------------------------------------------------------------

@app.get("/api/coastal-state", response_model=CoastalState)
async def coastal_state(
    zone_id: Optional[str] = Query(None, description="Coastal zone ID (e.g. mumbai, chennai, goa)"),
    lat: Optional[float] = Query(None, description="Latitude"),
    lon: Optional[float] = Query(None, description="Longitude"),
):
    store = get_store()
    return store.get_coastal_state(lat=lat, lon=lon, zone_id=zone_id)


# ---------------------------------------------------------------------------
# Sensors
# ---------------------------------------------------------------------------

@app.get("/api/sensors")
async def list_sensors(
    zone_id: Optional[str] = Query(None, description="Filter sensors by coastal zone ID"),
):
    store = get_store()
    return store.get_sensors(zone_id=zone_id)


@app.get("/api/sensors/{sensor_id}")
async def get_sensor(
    sensor_id: str,
    zone_id: Optional[str] = Query(None, description="Coastal zone ID"),
):
    store = get_store()
    sensor = store.get_sensor_by_id(sensor_id, zone_id=zone_id)
    if not sensor:
        raise HTTPException(404, f"Sensor {sensor_id} not found")
    return sensor


@app.get("/api/sensors/{sensor_id}/observations")
async def sensor_observations(
    sensor_id: str,
    zone_id: Optional[str] = Query(None, description="Coastal zone ID"),
    limit: int = Query(48, ge=1, le=500),
):
    store = get_store()
    obs = store.get_sensor_observations(sensor_id, zone_id=zone_id)
    # Return the most recent `limit` readings
    sorted_obs = sorted(obs, key=lambda r: r.timestamp, reverse=True)[:limit]
    return [r.model_dump() for r in sorted_obs]


@app.get("/api/sensors/latest/readings")
async def latest_readings(
    zone_id: Optional[str] = Query(None, description="Filter readings by coastal zone ID"),
):
    store = get_store()
    return [r.model_dump() for r in store.get_latest_readings(zone_id=zone_id)]


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

@app.get("/api/events", response_model=list[Event])
async def list_events(
    zone_id: Optional[str] = Query(None, description="Filter events by coastal zone ID"),
):
    store = get_store()
    return store.get_events(zone_id=zone_id)


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
async def compute_anomalies(
    zone_id: Optional[str] = Query(None, description="Filter anomalies by coastal zone ID"),
):
    store = get_store()
    latest = store.get_latest_readings(zone_id=zone_id)
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
        raise HTTPException(404, f"No forecast for event {event_id}")
    return forecast


# ---------------------------------------------------------------------------
# Exposure
# ---------------------------------------------------------------------------

@app.get("/api/exposure", response_model=list[ExposureResult])
async def get_exposure(event_id: str = Query(..., description="Event ID")):
    store = get_store()
    event = store.get_event(event_id)
    if not event:
        raise HTTPException(404, f"Event {event_id} not found")
    return compute_exposure(event, store.assets, max_range_km=30.0)


@app.get("/api/assets")
async def list_assets(
    zone_id: Optional[str] = Query(None, description="Filter assets by coastal zone ID"),
):
    store = get_store()
    return [a.model_dump() for a in store.get_assets(zone_id=zone_id)]


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
    zone_id: Optional[str] = Query(None, description="Coastal zone ID (e.g. mumbai, chennai, goa)"),
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
):
    store = get_store()
    if zone_id:
        zid = zone_id.lower().strip()
        if zid in store.zone_marine_cache:
            return store.zone_marine_cache[zid]
        z = get_zone(zid)
        if z:
            raw = fetch_marine_data(z.lat, z.lon)
            store.zone_marine_cache[zid] = raw
            return raw
    if lat is not None and lon is not None:
        return fetch_marine_data(lat, lon)
    if store.marine_cache:
        return store.marine_cache
    raw = fetch_marine_data(15.2993, 73.9700)
    store.marine_cache = raw
    return raw


# ---------------------------------------------------------------------------
# ML Telemetry (Logging Page)
# ---------------------------------------------------------------------------

@app.get("/api/ml/telemetry")
async def ml_telemetry():
    """Return ML model diagnostics: accuracy, F1, feature importance, drift, inference log."""
    return get_ml_telemetry()


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
async def get_mitigation(event_id: str = Query(..., description="Event ID")):
    """Generate a mitigation plan for a given flood event."""
    store = get_store()
    event = store.get_event(event_id)
    if not event:
        raise HTTPException(404, f"Event {event_id} not found")
    plan = generate_mitigation_plan(event, event_id)
    return plan


# ---------------------------------------------------------------------------
# Digital twin geometry (zones, roads, buildings, facilities)
# ---------------------------------------------------------------------------

@app.get("/api/geo")
async def geo_layers(
    zone_id: Optional[str] = Query(None, description="Coastal zone ID for digital twin geometry"),
):
    """GeoJSON layers for the 3D digital-twin map."""
    store = get_store()
    target_zone = zone_id or store.active_zone_id
    return as_geojson(zone_id=target_zone)


# ---------------------------------------------------------------------------
# Scenario timeline ("Heavy Coastal Rain Event")
# ---------------------------------------------------------------------------

@app.get("/api/scenario")
async def scenario_overview(
    zone_id: Optional[str] = Query(None, description="Coastal zone ID (e.g. mumbai, goa, chennai)"),
):
    """Scenario metadata + the full T=0..T+5h step index."""
    store = get_store()
    target_zone = zone_id or store.active_zone_id
    return scenario_meta(zone_id=target_zone)


@app.get("/api/scenario/snapshot")
async def scenario_snapshot(
    t: float = Query(0.0, ge=0.0, le=SCENARIO_HOURS, description="Hours since storm onset"),
):
    """
    Full intelligence snapshot for one time step: environmental conditions,
    per-zone predictions, flood depths, isolation analysis, priority board
    and the GenAI command brief.
    """
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)


