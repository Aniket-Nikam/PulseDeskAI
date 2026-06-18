"""
Geofence utilities — Haversine distance calculation for location-based attendance.
No external API keys required.
"""

import math
from typing import Optional, List

EARTH_RADIUS_METERS = 6_371_000  # Earth's mean radius in meters


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points on Earth
    using the Haversine formula.

    Returns distance in meters.
    """
    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_METERS * c


def is_within_geofence(
    user_lat: float,
    user_lon: float,
    fence_lat: float,
    fence_lon: float,
    radius_meters: int,
) -> bool:
    """Check if user coordinates fall within a geofence circle."""
    distance = haversine_distance(user_lat, user_lon, fence_lat, fence_lon)
    return distance <= radius_meters


def find_nearest_location(
    user_lat: float,
    user_lon: float,
    locations: List[dict],
) -> Optional[dict]:
    """
    Given a list of location dicts (each with latitude, longitude, radius_meters, id),
    return the nearest location that the user is within, or None.
    """
    best = None
    best_distance = float("inf")

    for loc in locations:
        dist = haversine_distance(
            user_lat, user_lon,
            loc["latitude"], loc["longitude"],
        )
        if dist <= loc["radius_meters"] and dist < best_distance:
            best = loc
            best_distance = dist

    return best
