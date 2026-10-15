"""Delivery area checks, distance, fee and ETA."""
from __future__ import annotations
import math


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def is_within_delivery_area(
    customer_lat: float | None,
    customer_lng: float | None,
    *,
    center_lat: float | None,
    center_lng: float | None,
    radius_km: float,
) -> tuple[bool, float | None]:
    if center_lat is None or center_lng is None:
        return True, None
    if customer_lat is None or customer_lng is None:
        return False, None
    dist = haversine_km(center_lat, center_lng, customer_lat, customer_lng)
    return dist <= float(radius_km or 0), dist


# Typical urban speeds km/h by vehicle (for ETA estimate)
VEHICLE_SPEED_KMH = {
    "cycle": 12,
    "bike": 25,
    "scooter": 22,
    "car": 20,
}


def estimate_eta_minutes(distance_km: float | None, vehicle_type: str | None = None, prep_minutes: int = 20) -> int | None:
    """Travel time + default prep buffer."""
    if distance_km is None:
        return None
    speed = VEHICLE_SPEED_KMH.get((vehicle_type or "bike").lower(), 22)
    if speed <= 0:
        speed = 20
    travel = (float(distance_km) / speed) * 60
    return max(15, int(round(prep_minutes + travel)))


def calculate_delivery_fee_paisa(
    distance_km: float | None,
    *,
    base_paisa: int = 0,
    per_km_paisa: int = 0,
    free_within_km: float = 0,
) -> int:
    """Admin base fee + optional per-km. Free within free_within_km if set."""
    base = int(base_paisa or 0)
    per_km = int(per_km_paisa or 0)
    if distance_km is None:
        return base
    d = float(distance_km)
    if free_within_km and d <= float(free_within_km):
        return 0
    extra = 0
    if per_km > 0 and d > 0:
        billable = d
        if free_within_km:
            billable = max(0, d - float(free_within_km))
        extra = int(round(billable * per_km))
    return base + extra
