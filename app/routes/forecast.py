from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any, Dict, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from pathlib import Path

router = APIRouter()
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
CACHE: Dict[str, Dict[str, Any]] = {}
LOGGER = logging.getLogger("forecast")
TTL_SECONDS = 86_400
SKU_PRICE = {
    "GS-019": 280.0,
    "BL-101": 190.0,
    "GS-045": 140.0,
}


def _load_historic() -> pd.DataFrame:
    cleaned_dir = DATA_DIR / "cleaned"
    parquet_path = cleaned_dir / "historic.parquet"
    if parquet_path.exists():
        df = pd.read_parquet(parquet_path)
    else:
        df = pd.read_csv(DATA_DIR / "historic.csv", parse_dates=["date"])
    df = df.dropna(subset=["date", "sku"])
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[df["date"].notna()]
    return df


def _cache_key(sku: str, horizon: int, region: str, start_date: str) -> str:
    return f"{sku}|{horizon}|{region}|{start_date}"


def _get_from_cache(key: str) -> Optional[Dict[str, Any]]:
    entry = CACHE.get(key)
    if not entry:
        return None
    if entry["expiry_ts"] < pd.Timestamp.now().timestamp():
        CACHE.pop(key, None)
        return None
    return entry["value"]


def _store_cache(key: str, value: Dict[str, Any]) -> None:
    CACHE[key] = {
        "value": value,
        "expiry_ts": pd.Timestamp.now().timestamp() + TTL_SECONDS,
    }


def _ensure_sku_exists(df: pd.DataFrame, sku: str) -> pd.DataFrame:
    subset = df[df["sku"] == sku]
    if subset.empty:
        raise HTTPException(status_code=404, detail=f"SKU {sku} not found in historic data")
    return subset


def _build_weekday_multipliers(df: pd.DataFrame) -> Dict[int, float]:
    df = df.copy()
    df["weekday"] = df["date"].dt.weekday
    overall_mean = df["units"].mean() or 1.0
    daily = df.groupby("weekday")["units"].mean().fillna(overall_mean).to_dict()
    multipliers = {
        weekday: round(value / overall_mean, 2) if overall_mean else 1.0
        for weekday, value in daily.items()
    }
    for wd in range(7):
        multipliers.setdefault(wd, 1.0)
    return multipliers


def _rolling_mean(df: pd.DataFrame, window: int = 28) -> float:
    latest = df["date"].max()
    start = latest - timedelta(days=window - 1)
    subset = df[(df["date"] >= start) & (df["date"] <= latest)]
    return float(subset["units"].mean() or 1.0)


def _format_series(df: pd.DataFrame, limit: int) -> list[Dict[str, Any]]:
    df = df.sort_values("date").tail(limit)
    return [
        {"date": row["date"].strftime("%Y-%m-%d"), "units": float(row["units"]) }
        for _, row in df.iterrows()
    ]


def _generate_forecast_points(
    start: pd.Timestamp,
    horizon: int,
    rolling_mean: float,
    weekday_multipliers: Dict[int, float],
) -> list[Dict[str, Any]]:
    points = []
    for idx in range(horizon):
        target = (start + timedelta(days=idx)).normalize()
        multiplier = weekday_multipliers.get(target.weekday(), 1.0)
        value = max(1.0, rolling_mean * multiplier)
        points.append(
            {"date": target.strftime("%Y-%m-%d"), "units": round(value, 2)}
        )
    return points


def _build_confidence_intervals(points: list[Dict[str, Any]]) -> Dict[str, list[Dict[str, Any]]]:
    intervals = {"low": [], "median": [], "high": []}
    for point in points:
        val = point["units"]
        intervals["low"].append({"date": point["date"], "units": round(val * 0.7, 2)})
        intervals["median"].append({"date": point["date"], "units": val})
        intervals["high"].append({"date": point["date"], "units": round(val * 1.3, 2)})
    return intervals


def _aggregate_metrics(points: list[Dict[str, Any]], horizon: int) -> Dict[str, Any]:
    expected_units = sum(point["units"] for point in points)
    avg_price = 280.0
    expected_revenue = round(expected_units * avg_price, 2)
    stockout_risk = min(50.0, max(5.0, 10.0 + horizon * 0.5))
    return {
        "expected_units": round(expected_units, 2),
        "expected_revenue": expected_revenue,
        "stockout_risk_pct": round(stockout_risk, 2),
    }


def _fallback_stockout_risk(horizon: int) -> float:
    return min(50.0, max(5.0, 10.0 + horizon * 0.5))


def _serialize_points(points: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    return [{"date": point["date"], "units": float(point.get("units", 0))} for point in points]


def _ensure_confidence_intervals(response: Dict[str, Any], points: list[Dict[str, Any]]) -> None:
    intervals = response.setdefault("confidence_intervals", {})
    for key in ("low", "median", "high"):
        if not isinstance(intervals.get(key), list):
            intervals[key] = _serialize_points(points)


def _ensure_aggregate_metrics(response: Dict[str, Any], points: list[Dict[str, Any]], horizon: int, sku: str) -> None:
    metrics = response.setdefault("aggregate_metrics", {})
    total_units = round(sum(point.get("units", 0) for point in points), 2)
    metrics.setdefault("expected_units", total_units)
    price = SKU_PRICE.get(sku)
    metrics.setdefault("expected_revenue", round(total_units * price, 2) if price else None)
    metrics.setdefault("stockout_risk_pct", _fallback_stockout_risk(horizon))


def _ensure_meta(response: Dict[str, Any]) -> None:
    now = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    response.setdefault("model_version", "v0.1-stub")
    response.setdefault("last_updated", now)
    response.setdefault("ttl_seconds", TTL_SECONDS)


def _parse_start_date(value: Optional[str], default: pd.Timestamp) -> pd.Timestamp:
    if not value:
        return default.normalize()
    try:
        parsed = pd.to_datetime(value)
    except ValueError:
        raise HTTPException(status_code=400, detail="start_date must be YYYY-MM-DD")
    return parsed.normalize()


@router.get("/forecast")
def forecast(
    sku: str = Query(..., description="SKU identifier"),
    horizon: int = Query(14, description="Forecast horizon in days", ge=7, le=30),
    region: str = Query("global", description="Region for the forecast"),
    start_date: Optional[str] = Query(None, description="Optional start date (YYYY-MM-DD)"),
) -> Dict[str, Any]:
    historic_df = _load_historic()
    filtered = _ensure_sku_exists(historic_df, sku)
    latest = filtered["date"].max()
    data_window = {
        "start": filtered["date"].min().strftime("%Y-%m-%d"),
        "end": latest.strftime("%Y-%m-%d"),
    }

    start_ts = _parse_start_date(start_date, latest + timedelta(days=1))
    if horizon not in (7, 14, 30):
        raise HTTPException(status_code=400, detail="horizon must be one of 7, 14, or 30")
    cache_key = _cache_key(sku, horizon, region, start_ts.strftime("%Y-%m-%d"))
    cached = _get_from_cache(cache_key)
    if cached:
        return cached

    multipliers = _build_weekday_multipliers(filtered)
    rolling_mean = _rolling_mean(filtered)
    points = _generate_forecast_points(start_ts, horizon, rolling_mean, multipliers)
    if len(points) != horizon:
        LOGGER.error("forecast: generated %s points for horizon %s", len(points), horizon)
    intervals = _build_confidence_intervals(points)
    serialized_points = _serialize_points(points)
    historical = _format_series(filtered, max(28, horizon))
    metrics = _aggregate_metrics(points, horizon)

    response = {
        "sku": sku,
        "region": region,
        "horizon": horizon,
        "trained_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data_window": data_window,
        "point_forecast": serialized_points,
        "confidence_intervals": intervals,
        "aggregate_metrics": metrics,
        "notes": "stub: 28-day rolling mean + weekday multiplier",
        "historical": historical,
    }
    _ensure_confidence_intervals(response, serialized_points)
    _ensure_aggregate_metrics(response, serialized_points, horizon, sku)
    _ensure_meta(response)
    response.setdefault("notes", "stub: 28-day rolling mean + weekday multiplier")

    LOGGER.warning(
        "forecast: returning stub forecast for %s horizon=%s region=%s",
        sku,
        horizon,
        region,
    )

    _store_cache(cache_key, response)
    return response
