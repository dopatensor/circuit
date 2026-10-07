"""Place seed data around a configurable city centre."""

import math
from typing import NamedTuple


class Point(NamedTuple):
    lat: float
    lng: float


def offset(center: Point, east_km: float, north_km: float) -> Point:
    """Move east/north by a number of kilometres (accurate enough within a city)."""
    lat = center.lat + north_km / 110.574
    lng = center.lng + east_km / (111.320 * math.cos(math.radians(center.lat)))
    return Point(round(lat, 6), round(lng, 6))


class Area(NamedTuple):
    name: str
    east_km: float
    north_km: float
    startup_weight: int  # how many startups cluster here, relatively


# Neighbourhoods relative to the centre. Generic names so any city centre works.
AREAS: list[Area] = [
    Area("Central Business District", 0.0, 0.0, 6),
    Area("East Innovation Hub", 8.5, 1.0, 6),
    Area("North Tech Park", 1.5, 9.0, 5),
    Area("Lakeside", 5.0, -5.5, 4),
    Area("Old Market", -2.0, -2.5, 3),
    Area("University Quarter", -5.0, 4.5, 3),
    Area("West Industrial Estate", -8.5, -1.0, 2),
    Area("South Residential", 1.0, -9.0, 2),
    Area("Airport Road", 6.0, 13.0, 1),
]
AREA_BY_NAME = {a.name: a for a in AREAS}
