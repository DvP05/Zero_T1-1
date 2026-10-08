"""
TIDALIS — GenAI Command Brief (explainability layer).

Turns the raw prediction payload into the plain-language emergency brief
judges actually read:

    "Zone B requires immediate evacuation. Rising tides combined with
     heavy rainfall have pushed the flood probability to 87%, threatening
     Goa Coastal Hospital and severing two primary egress routes."

Deterministic template driven by the model's own SHAP-style drivers, so
every sentence is grounded in numbers the system actually produced.
"""

from __future__ import annotations

_DRIVER_OPENERS = {
    "rainfall_intensity": "heavy rainfall",
    "tide_level": "a rising tide",
    "storm_surge": "storm surge",
    "elevation": "low-lying terrain",
    "drainage_capacity": "drainage at capacity",
    "soil_saturation": "already-saturated ground",
    "imperviousness": "sealed urban surfaces",
    "historical_flood_freq": "a history of flooding here",
}


def _join(items: list[str]) -> str:
    if len(items) <= 1:
        return items[0] if items else ""
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def generate_command_brief(
    *,
    conditions,
    zones: list,
    priorities,
    isolation,
    aggregate_risk: str,
) -> tuple[str, str]:
    """Return (headline, brief body) for one scenario time step."""
    if not priorities.items:
        return "NO ACTIVE THREAT", "No zones are currently above the alerting threshold."

    top = next((i for i in priorities.items if i.isolated), None) or priorities.items[0]
    zone_state = next((z for z in zones if z.zone_id == top.zone_id), None)
    if zone_state is None:
        return "NO ACTIVE THREAT", "Zone intelligence unavailable for this time step."

    # ---- headline --------------------------------------------------------
    if top.isolated:
        headline = f"{top.zone_name} IS CUT OFF — immediate action required"
    elif aggregate_risk == "CRITICAL":
        headline = f"CRITICAL FLOOD RISK — {top.zone_name} first"
    elif aggregate_risk == "HIGH":
        headline = f"HIGH FLOOD RISK — {top.zone_name} escalating"
    elif aggregate_risk == "MODERATE":
        headline = f"MODERATE FLOOD RISK — {top.zone_name} watching"
    else:
        headline = f"LOW RISK — {conditions.label}, conditions monitored"

    # ---- drivers ---------------------------------------------------------
    drivers = [d for d in zone_state.drivers if d["contribution"] > 0][:3]
    driver_phrases = [
        _DRIVER_OPENERS.get(d["feature"], d["label"].lower()) for d in drivers
    ]
    driver_text = _join(driver_phrases) if driver_phrases else "combined environmental loading"

    # ---- body ------------------------------------------------------------
    parts: list[str] = []

    if aggregate_risk in ("HIGH", "CRITICAL"):
        action = (
            "requires immediate evacuation"
            if zone_state.flood_probability >= 0.75
            else "requires pre-emptive evacuation of its lowest sectors"
        )
        parts.append(f"{top.zone_name} {action}.")
    elif aggregate_risk == "MODERATE":
        parts.append(f"{top.zone_name} is the zone to watch.")
    else:
        parts.append(f"Conditions in {top.zone_name} remain below the intervention threshold.")

    parts.append(
        f"{driver_text[0].upper()}{driver_text[1:]} have pushed the flood probability to "
        f"{zone_state.flood_probability:.0%} "
        f"(model interval {zone_state.interval_low:.0%}–{zone_state.interval_high:.0%}), "
        f"with {zone_state.flood_depth_m:.2f} m of water predicted on the ground "
        f"against a {zone_state.elevation_m:.1f} m elevation."
    )

    if zone_state.facilities_threatened:
        parts.append(
            f"Threatening {_join(zone_state.facilities_threatened[:3])} "
            f"and {top.affected_facility_count} critical asset(s) in total."
        )

    if isolation.enclaves:
        names = _join([e.zone_name for e in isolation.enclaves])
        parts.append(
            f"{len(isolation.enclaves)} isolated enclave{'s' if len(isolation.enclaves) > 1 else ''} "
            f"detected ({names}): all egress routes are impassable, "
            f"stranding roughly {sum(e.population for e in isolation.enclaves):,} residents."
        )
    else:
        parts.append(
            f"Road network integrity is {isolation.network_integrity:.0%} — "
            "every zone still has a passable route to the evacuation interchange."
        )

    if top.onset_hours is not None and top.onset_hours <= conditions.t_hours + 0.01:
        parts.append("Onset has already begun; conditions will keep deteriorating until the tide turns.")
    elif top.onset_hours is not None:
        parts.append(f"Expected onset in {top.onset_hours:.1f} h if current trends hold.")

    parts.append(
        f"Recommended posture: {top.urgency.lower()} — "
        f"priority score {top.priority_score:.2f} "
        f"(probability {top.flood_probability:.0%} · severity {top.severity_contribution / 0.30:.2f} · "
        f"assets {top.assets_contribution / 0.30:.2f})."
    )

    parts.append(
        "TIDALIS is a decision-support system: final operational authority remains "
        "with responding agencies. Demo data — not an operational forecast."
    )

    return headline, " ".join(parts)
