"""
TIDALIS — Deterministic Copilot (no LLM required).

Provides evidence-grounded natural-language responses by querying
the TIDALIS data store.  All answers are derived from actual system
data — the copilot never invents values.
"""

from __future__ import annotations

from backend.app.models.schemas import CopilotRequest, CopilotResponse, Event, Forecast, ExposureResult
from backend.app.services.data_store import get_store


def _format_evidence(event: Event) -> str:
    lines = []
    for ev in event.evidence:
        lines.append(f"  • [{ev.source.upper()}] Score: {ev.score:.0%} — {ev.reason}")
    return "\n".join(lines)


def _format_exposures(exposures: list[ExposureResult]) -> str:
    if not exposures:
        return "  No assets currently within estimated exposure range."
    lines = []
    for exp in exposures:
        lines.append(
            f"  • {exp.asset_name} ({exp.asset_type.value}) — "
            f"exposure: {exp.exposure_score:.0%}, "
            f"distance: {exp.distance_km:.1f} km {exp.direction}"
        )
    return "\n".join(lines)


def _format_forecast_summary(forecast: Forecast | None) -> str:
    if not forecast or not forecast.points:
        return "  No forecast data available."
    first = forecast.points[0]
    last = forecast.points[-1]
    trend = "increasing" if last.predicted_value > first.predicted_value else "decreasing"
    return (
        f"  {forecast.variable} forecast ({forecast.model_name}):\n"
        f"  +1h: {first.predicted_value:.1f} → +{last.hours_ahead}h: {last.predicted_value:.1f} ({trend})\n"
        f"  Confidence band at +{last.hours_ahead}h: [{last.lower_bound:.1f}, {last.upper_bound:.1f}]"
    )


def handle_copilot(request: CopilotRequest) -> CopilotResponse:
    """
    Process a copilot question and return a data-grounded response.
    """
    store = get_store()
    message = request.message.lower().strip()
    event_id = request.event_id
    sources_used: list[str] = []

    # Find the event (or the most recent one)
    event: Event | None = None
    if event_id:
        event = store.get_event(event_id)
    if not event and store.events:
        event = max(store.events, key=lambda e: e.confidence)
        event_id = event.event_id

    # ---- Route by intent ----

    # What is happening?
    if any(kw in message for kw in ["what is happening", "status", "current", "coast", "overview"]):
        state = store.get_coastal_state(15.2993, 73.9700)
        reply = (
            f"🌊 TIDALIS Coastal Status: **{state.status}**\n\n"
            f"• Active sensors: {state.sensor_count}\n"
            f"• Active events: {state.active_events}\n"
        )
        if event:
            reply += (
                f"\n**Highest-confidence event: {event.event_id}**\n"
                f"• Severity: {event.severity.value}\n"
                f"• Confidence: {event.confidence:.0%}\n"
                f"• Location: ({event.latitude:.4f}, {event.longitude:.4f})\n"
                f"• {event.description}"
            )
        sources_used = ["coastal_state", "events"]

    # Why was this detected?
    elif any(kw in message for kw in ["why", "evidence", "explain", "detected", "reason"]):
        if event:
            reply = (
                f"⚠️ **Event {event.event_id}** — {event.severity.value} severity ({event.confidence:.0%} confidence)\n\n"
                f"**Evidence supporting this detection:**\n"
                f"{_format_evidence(event)}\n\n"
                f"These independent observation streams are consistent with an abnormal coastal condition. "
                f"This does not by itself establish the specific cause of the anomaly."
            )
            sources_used = ["event_evidence"]
        else:
            reply = "No active events found. The coastal state appears normal."

    # Forecast
    elif any(kw in message for kw in ["forecast", "predict", "next", "future", "hours"]):
        forecast = store.get_forecast(event_id) if event_id else None
        if forecast:
            reply = (
                f"🔮 **Forecast for event {event_id}**\n\n"
                f"{_format_forecast_summary(forecast)}"
            )
            sources_used = ["forecast"]
        else:
            reply = "No forecast data currently available for this event."

    # Exposure
    elif any(kw in message for kw in ["exposure", "affect", "impact", "asset", "habitat", "risk"]):
        exposures = store.get_exposures(event_id) if event_id else []
        reply = (
            f"🗺️ **Exposure Assessment**\n\n"
            f"Assets potentially exposed to the current event:\n"
            f"{_format_exposures(exposures)}"
        )
        sources_used = ["exposure"]

    # Highest confidence event
    elif any(kw in message for kw in ["highest", "strongest", "worst", "biggest", "top"]):
        if event:
            reply = (
                f"🔴 **Highest-confidence event: {event.event_id}**\n\n"
                f"• Type: {event.event_type}\n"
                f"• Severity: {event.severity.value}\n"
                f"• Confidence: {event.confidence:.0%}\n"
                f"• Location: ({event.latitude:.4f}, {event.longitude:.4f})\n"
                f"• Radius: {event.radius_km} km\n\n"
                f"**Evidence:**\n{_format_evidence(event)}"
            )
            sources_used = ["events", "event_evidence"]
        else:
            reply = "No events currently detected. Coastal conditions appear normal."

    # Investigation priority
    elif any(kw in message for kw in ["investigate", "priority", "first", "should"]):
        if event:
            exposures = store.get_exposures(event_id) if event_id else []
            top_exposure = exposures[0] if exposures else None
            reply = (
                f"🎯 **Investigation Priority**\n\n"
                f"The highest-priority area for investigation is near "
                f"**({event.latitude:.4f}, {event.longitude:.4f})** "
                f"(event {event.event_id}, confidence {event.confidence:.0%}).\n\n"
                f"**Reason:** {event.evidence[0].reason if event.evidence else 'Multi-source anomaly detected'}\n\n"
            )
            if top_exposure:
                reply += (
                    f"**Nearest high-sensitivity asset:** {top_exposure.asset_name} "
                    f"({top_exposure.distance_km:.1f} km {top_exposure.direction})\n"
                )
            sources_used = ["events", "exposure"]
        else:
            reply = "No events require investigation at this time."

    # Generate report
    elif any(kw in message for kw in ["report", "generate", "summary", "document"]):
        if event:
            forecast = store.get_forecast(event_id) if event_id else None
            exposures = store.get_exposures(event_id) if event_id else []
            reply = (
                f"📄 **TIDALIS COASTAL INCIDENT REPORT**\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"**Incident ID:** {event.event_id}\n"
                f"**Detected:** {event.timestamp.strftime('%d %b %Y %H:%M UTC')}\n"
                f"**Location:** ({event.latitude:.4f}, {event.longitude:.4f})\n"
                f"**Severity:** {event.severity.value}\n"
                f"**Confidence:** {event.confidence:.0%}\n\n"
                f"**PRIMARY EVIDENCE**\n{_format_evidence(event)}\n\n"
                f"**FORECAST**\n{_format_forecast_summary(forecast)}\n\n"
                f"**POTENTIAL EXPOSURE**\n{_format_exposures(exposures)}\n\n"
                f"**DATA SOURCES**\n"
                f"  • TIDALIS Simulated Sensors\n"
                f"  • Open-Meteo Marine\n"
                f"  • Historical baselines\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            )
            sources_used = ["events", "forecast", "exposure"]
        else:
            reply = "No active events to generate a report for."

    # Default
    else:
        reply = (
            "I can help you understand the current coastal situation. Try asking:\n\n"
            "• *\"What is happening near the coast?\"*\n"
            "• *\"Why was this event detected?\"*\n"
            "• *\"What is the forecast for the next 12 hours?\"*\n"
            "• *\"Which assets are potentially exposed?\"*\n"
            "• *\"Which area should be investigated first?\"*\n"
            "• *\"Generate an incident report.\"*"
        )

    return CopilotResponse(
        reply=reply,
        sources_used=sources_used,
        event_id=event_id,
    )
