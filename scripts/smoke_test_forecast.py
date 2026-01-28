#!/usr/bin/env python3
import sys
from datetime import datetime
from typing import Any

import requests

BASE_URL = "http://localhost:8000"

SKU = sys.argv[1] if len(sys.argv) > 1 else "GS-019"
HORIZON = int(sys.argv[2]) if len(sys.argv) > 2 else 14

REQUIRED_FIELDS = ["model_version", "point_forecast", "confidence_intervals", "ttl_seconds"]


def _fail(message: str) -> None:
    print(f"[FAIL] {message}")
    sys.exit(1)


def _validate_confidence(ci: Any) -> bool:
    if not isinstance(ci, dict):
        return False
    return all(key in ci for key in ("low", "median", "high"))


def main() -> None:
    url = f"{BASE_URL}/api/forecast"
    params = {"sku": SKU, "horizon": HORIZON}
    print(f"Calling {url} with {params}")
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
    except Exception as exc:
        _fail(f"Request failed: {exc}")

    payload = response.json()
    missing = [field for field in REQUIRED_FIELDS if field not in payload]
    if missing:
        _fail(f"Missing required fields: {missing}")

    if not isinstance(payload.get("point_forecast"), list):
        _fail("point_forecast must be a list")
    if len(payload["point_forecast"]) != HORIZON:
        _fail(f"point_forecast length {len(payload['point_forecast'])} != horizon {HORIZON}")

    if not _validate_confidence(payload.get("confidence_intervals")):
        _fail("confidence_intervals must include low/median/high arrays")

    ttl = payload.get("ttl_seconds")
    if not isinstance(ttl, int) or ttl <= 0:
        _fail("ttl_seconds must be a positive integer")

    print("[PASS] Forecast smoke test succeeded")
    print(f"  SKU: {SKU}, horizon: {HORIZON}, model: {payload.get('model_version')} @ {payload.get('trained_at')}")
    print(f"  Data window: {payload.get('data_window')} / TTL: {ttl}s")


if __name__ == "__main__":
    main()
