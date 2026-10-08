"""
TIDALIS — Forecast Engine.

MVP approach: persistence + recent-trend extrapolation.
Produces hourly forecasts for a given variable (e.g. turbidity)
over the next 6–24 hours.

This is the fallback engine that works without scikit-learn.
When scikit-learn is available, HistGradientBoostingRegressor can be
swapped in without changing the API.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.app.models.schemas import Forecast, ForecastPoint, SensorReading


def _compute_trend(values: list[float], window: int = 6) -> float:
    """Simple linear trend over the last `window` values."""
    if len(values) < 2:
        return 0.0
    recent = values[-window:]
    n = len(recent)
    if n < 2:
        return 0.0
    # Slope via least-squares
    x_mean = (n - 1) / 2.0
    y_mean = sum(recent) / n
    num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(recent))
    den = sum((i - x_mean) ** 2 for i in range(n))
    return num / den if den != 0 else 0.0


def _compute_rolling_std(values: list[float], window: int = 12) -> float:
    """Rolling standard deviation for confidence bands."""
    recent = values[-window:]
    if len(recent) < 2:
        return 0.5
    mean = sum(recent) / len(recent)
    variance = sum((v - mean) ** 2 for v in recent) / (len(recent) - 1)
    return variance ** 0.5


def generate_forecast(
    readings: list[SensorReading],
    variable: str = "turbidity",
    hours_ahead: int = 24,
    event_id: str = "",
) -> Forecast:
    """
    Generate a simple trend-based forecast for a single variable.

    Uses the last known value + linear trend to project forward.
    Confidence bands widen over time based on recent volatility.
    """
    # Sort readings by timestamp
    sorted_readings = sorted(readings, key=lambda r: r.timestamp)

    # Extract the variable time series
    values = [getattr(r, variable, None) for r in sorted_readings]
    values = [v for v in values if v is not None]

    if not values:
        # No data — return flat forecast
        now = datetime.now(timezone.utc)
        return Forecast(
            event_id=event_id,
            variable=variable,
            model_name="no_data_fallback",
            points=[
                ForecastPoint(
                    hours_ahead=h,
                    timestamp=now + timedelta(hours=h),
                    predicted_value=0.0,
                    lower_bound=0.0,
                    upper_bound=0.0,
                    variable=variable,
                )
                for h in range(1, hours_ahead + 1)
            ],
        )

    last_value = values[-1]
    trend = _compute_trend(values)
    rolling_std = _compute_rolling_std(values)
    last_ts = sorted_readings[-1].timestamp

    points: list[ForecastPoint] = []
    for h in range(1, hours_ahead + 1):
        predicted = last_value + trend * h
        # Confidence band widens with sqrt(time)
        band = rolling_std * (h ** 0.5) * 0.5

        points.append(ForecastPoint(
            hours_ahead=h,
            timestamp=last_ts + timedelta(hours=h),
            predicted_value=round(predicted, 2),
            lower_bound=round(predicted - band, 2),
            upper_bound=round(predicted + band, 2),
            variable=variable,
        ))

    return Forecast(
        event_id=event_id,
        variable=variable,
        model_name="persistence_trend",
        points=points,
    )
