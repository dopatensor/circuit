"""Small PostGIS helpers shared by the map and jobs endpoints."""

from geoalchemy2 import Geography
from sqlalchemy import cast, func, select

from app.config import Settings
from app.models import Member
from app.profiles import lat_lng_columns


def point(lat: float, lng: float):
    """A geography point SQL expression (note PostGIS wants longitude first)."""
    return cast(func.ST_SetSRID(func.ST_MakePoint(lng, lat), 4326), Geography)


async def member_center(session, member_id, settings: Settings) -> tuple[float, float]:
    """The member's profile location, or the city centre if they haven't set one."""
    mlat, mlng = lat_lng_columns(Member.location)
    row = (await session.execute(select(mlat, mlng).where(Member.id == member_id))).one()
    if row.lat is not None:
        return row.lat, row.lng
    return settings.city_center_lat, settings.city_center_lng
