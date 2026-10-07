"""Partner dashboard queries (F8): what the ecosystem lacks, where, and how it's doing.

- gaps_by_capability: active needs vs active offers per capability, biggest gap first.
- gaps_by_area: the same on a grid of ~1 km cells, for the map's heat layer. A need sits
  where its owner is (the startup, or the member); an offer where the member is.
- network_stats: counts for the stat tiles.
- intro_acceptance: accepted share of decided intros, local vs bridge matches.
"""

import math
from dataclasses import dataclass

from sqlalchemy import text

KM_PER_DEGREE_LAT = 111.32

# "Decided" intros: accepted or completed count as accepted; declined and expired as not.
# Withdrawn and still-open ones are left out of the rate.
ACCEPTED = ("accepted", "completed")
NOT_ACCEPTED = ("declined", "expired")


@dataclass(frozen=True)
class Acceptance:
    decided: int
    accepted: int

    @property
    def rate(self) -> float | None:
        return round(self.accepted / self.decided, 3) if self.decided else None


def grid_degrees(cell_km: float, center_lat: float) -> tuple[float, float]:
    """(dlat, dlng) for square cells of cell_km: a degree of longitude is shorter away
    from the equator."""
    dlat = cell_km / KM_PER_DEGREE_LAT
    dlng = cell_km / (KM_PER_DEGREE_LAT * max(math.cos(math.radians(center_lat)), 0.01))
    return dlat, dlng


# Active needs with the place they belong to (startup needs at the startup).
_NEED_PLACES = """
    SELECT n.capability_id, COALESCE(s.location, m.location) AS location
    FROM needs n
    LEFT JOIN startups s ON n.owner_type = 'startup' AND s.id = n.owner_id
    LEFT JOIN members m ON n.owner_type = 'member' AND m.id = n.owner_id
    WHERE n.active AND (s.id IS NOT NULL OR m.id IS NOT NULL)
"""
_OFFER_PLACES = """
    SELECT o.capability_id, m.location
    FROM offers o JOIN members m ON m.id = o.member_id
    WHERE o.active
"""


async def gaps_by_capability(session) -> list[dict]:
    rows = await session.execute(
        text(
            f"""
            WITH need_counts AS (
                SELECT capability_id, count(*) AS n FROM ({_NEED_PLACES}) x GROUP BY 1
            ), offer_counts AS (
                SELECT capability_id, count(*) AS n FROM ({_OFFER_PLACES}) x GROUP BY 1
            )
            SELECT c.id, c.name, c.category,
                   COALESCE(nc.n, 0) AS needs, COALESCE(oc.n, 0) AS offers
            FROM capabilities c
            LEFT JOIN need_counts nc ON nc.capability_id = c.id
            LEFT JOIN offer_counts oc ON oc.capability_id = c.id
            WHERE COALESCE(nc.n, 0) + COALESCE(oc.n, 0) > 0
            ORDER BY COALESCE(nc.n, 0) - COALESCE(oc.n, 0) DESC, COALESCE(nc.n, 0) DESC, c.id
            """
        )
    )
    return [
        {"capability_id": r.id, "name": r.name, "category": r.category,
         "needs": r.needs, "offers": r.offers, "gap": r.needs - r.offers}
        for r in rows
    ]  # fmt: skip


async def gaps_by_area(
    session, *, cell_km: float, center_lat: float, capability: str | None
) -> list[dict]:
    dlat, dlng = grid_degrees(cell_km, center_lat)
    rows = await session.execute(
        text(
            f"""
            WITH places AS (
                SELECT capability_id, location, 1 AS need, 0 AS offer FROM ({_NEED_PLACES}) n
                UNION ALL
                SELECT capability_id, location, 0, 1 FROM ({_OFFER_PLACES}) o
            ), cells AS (
                SELECT floor(ST_Y(location::geometry) / :dlat) AS gy,
                       floor(ST_X(location::geometry) / :dlng) AS gx,
                       need, offer
                FROM places
                WHERE location IS NOT NULL
                  AND (CAST(:capability AS text) IS NULL OR capability_id = :capability)
            )
            SELECT gy, gx, sum(need) AS needs, sum(offer) AS offers
            FROM cells GROUP BY gy, gx
            ORDER BY sum(need) - sum(offer) DESC, sum(need) DESC, gy, gx
            """
        ),
        {"dlat": dlat, "dlng": dlng, "capability": capability},
    )
    return [
        {
            # The centre of the cell, for a heat-layer point or a square on the map.
            "lat": round((r.gy + 0.5) * dlat, 6),
            "lng": round((r.gx + 0.5) * dlng, 6),
            "needs": int(r.needs),
            "offers": int(r.offers),
            "gap": int(r.needs - r.offers),
        }
        for r in rows
    ]


async def network_stats(session) -> dict:
    row = (
        await session.execute(
            text(
                """
                SELECT
                  (SELECT count(*) FROM members) AS members,
                  (SELECT count(*) FROM startups) AS startups,
                  (SELECT count(*) FROM startups WHERE claimed_by_member_id IS NOT NULL)
                    AS startups_claimed,
                  (SELECT count(*) FROM startups WHERE hiring) AS startups_hiring,
                  (SELECT count(*) FROM jobs WHERE status = 'open') AS open_jobs,
                  (SELECT count(*) FROM applications) AS applications,
                  (SELECT count(*) FROM needs WHERE active) AS active_needs,
                  (SELECT count(*) FROM offers WHERE active) AS active_offers,
                  (SELECT count(*) FROM connections) AS connections,
                  (SELECT count(*) FROM intro_requests) AS intros,
                  (SELECT count(*) FROM intro_requests WHERE status IN ('accepted', 'completed'))
                    AS intros_accepted,
                  (SELECT count(DISTINCT actor_id) FROM events WHERE type = 'startup.interest')
                    AS students_interested,
                  (SELECT count(*) FROM members WHERE circuits_opt_in) AS circuits_opted_in
                """
            )
        )
    ).one()
    stats = dict(row._mapping)
    stats["members_by_role"] = dict(
        (await session.execute(text("SELECT role, count(*) FROM members GROUP BY role"))).all()
    )
    stats["circuits_by_status"] = dict(
        (await session.execute(text("SELECT status, count(*) FROM circuits GROUP BY status"))).all()
    )
    return stats


async def intro_acceptance(session) -> dict[bool, Acceptance]:
    rows = await session.execute(
        text(
            """
            SELECT is_bridge,
                   count(*) FILTER (WHERE status = ANY(:decided)) AS decided,
                   count(*) FILTER (WHERE status = ANY(:accepted)) AS accepted
            FROM intro_requests GROUP BY is_bridge
            """
        ),
        {"decided": list(ACCEPTED + NOT_ACCEPTED), "accepted": list(ACCEPTED)},
    )
    out = {False: Acceptance(0, 0), True: Acceptance(0, 0)}
    for is_bridge, decided, accepted in rows:
        out[is_bridge] = Acceptance(decided, accepted)
    return out
