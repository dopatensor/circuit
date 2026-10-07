"""Map endpoints (F2): nearby with a hard distance filter, bbox, filters, skill match."""

import pytest

pytestmark = pytest.mark.anyio


def by_name(result: dict) -> dict[str, dict]:
    return {p["name"]: p for p in result["items"]}


async def test_ravi_sees_ledgerloop_nearby_with_a_strong_match(client, login):
    headers = await login("ravi")
    r = await client.get("/api/map/startups/nearby", headers=headers, params={"radius_km": 5})
    assert r.status_code == 200, r.text
    result = r.json()
    ledger = by_name(result)["LedgerLoop"]
    assert ledger["hiring"] and ledger["distance_km"] < 2
    assert ledger["match"]["score"] >= 80
    assert ledger["match"]["best_role"]["title"] in {
        "Backend Engineering Intern", "Junior Backend Engineer",
    }  # fmt: skip
    assert all(p["distance_km"] <= 5 for p in result["items"])  # hard filter
    distances = [p["distance_km"] for p in result["items"]]
    assert distances == sorted(distances)


async def test_sort_by_match_puts_ledgerloop_first_for_ravi(client, login):
    r = await client.get(
        "/api/map/startups/nearby",
        headers=await login("ravi"),
        params={"radius_km": 10, "hiring": True, "sort": "match"},
    )
    items = r.json()["items"]
    assert items[0]["name"] == "LedgerLoop"
    scores = [p["match"]["score"] for p in items]
    assert scores == sorted(scores, reverse=True)


async def test_same_skills_different_college_same_score(client, make_member):
    skills = {"skills": [{"capability_id": "backend_development", "level": 3},
                         {"capability_id": "data_engineering", "level": 3}]}  # fmt: skip
    scores = []
    for college in (
        "National Institute of Science & Technology",
        "Government Polytechnic, South Campus",
    ):
        _, headers = await make_member(role="student", level=1, college=college)
        await client.put("/api/members/me/skills", headers=headers, json=skills)
        r = await client.get(
            "/api/map/startups/nearby",
            headers=headers,
            params={"lat": 12.9716, "lng": 77.5946, "radius_km": 20},
        )
        scores.append({p["name"]: p["match"]["score"] for p in r.json()["items"]})
    assert scores[0] == scores[1]


async def test_filters(client, login):
    headers = await login("ravi")
    base = {"lat": 12.9716, "lng": 77.5946, "radius_km": 30}
    hiring = (
        await client.get(
            "/api/map/startups/nearby", headers=headers, params={**base, "hiring": True}
        )
    ).json()
    assert hiring["total"] > 0 and all(p["hiring"] for p in hiring["items"])
    biotech = (
        await client.get(
            "/api/map/startups/nearby", headers=headers, params={**base, "sector": "biotech"}
        )
    ).json()
    assert biotech["total"] > 0 and all(p["sector"] == "biotech" for p in biotech["items"])
    backend = (
        await client.get(
            "/api/map/startups/nearby",
            headers=headers,
            params={**base, "capability": "backend_development"},
        )
    ).json()
    assert "LedgerLoop" in by_name(backend)
    regulatory = (
        await client.get(
            "/api/map/startups/nearby",
            headers=headers,
            params={**base, "capability": "regulatory_affairs"},
        )
    ).json()
    assert "HelixRoot Biosciences" in by_name(regulatory)  # via its active need


async def test_defaults_to_profile_location_then_city_centre(client, login, make_member):
    r = await client.get("/api/map/startups/nearby", headers=await login("ravi"))
    ravi_center = r.json()["center"]
    assert ravi_center != {"lat": 12.9716, "lng": 77.5946}
    _, headers = await make_member(role="student", level=1)  # no location set
    r = await client.get("/api/map/startups/nearby", headers=headers)
    assert r.json()["center"] == {"lat": 12.9716, "lng": 77.5946}


async def test_non_students_get_no_match_score(client, login):
    r = await client.get("/api/map/startups/nearby", headers=await login("meera"))
    assert all(p["match"] is None for p in r.json()["items"])


async def test_bbox(client, login):
    headers = await login("ravi")
    near = (
        await client.get("/api/map/startups/nearby", headers=headers, params={"radius_km": 3})
    ).json()
    ledger = by_name(near)["LedgerLoop"]["location"]
    box = {
        "min_lat": ledger["lat"] - 0.005, "max_lat": ledger["lat"] + 0.005,
        "min_lng": ledger["lng"] - 0.005, "max_lng": ledger["lng"] + 0.005,
    }  # fmt: skip
    r = await client.get("/api/map/startups/bbox", headers=headers, params=box)
    assert "LedgerLoop" in by_name(r.json())
    assert r.json()["items"][0]["distance_km"] is None
    whole_city = {"min_lat": 12.7, "max_lat": 13.3, "min_lng": 77.3, "max_lng": 77.9}
    assert (await client.get("/api/map/startups/bbox", headers=headers, params=whole_city)).json()[
        "total"
    ] == 150
    bad = {**box, "min_lat": box["max_lat"]}
    assert (
        await client.get("/api/map/startups/bbox", headers=headers, params=bad)
    ).status_code == 422


async def test_radius_is_capped(client, login):
    r = await client.get(
        "/api/map/startups/nearby", headers=await login("ravi"), params={"radius_km": 500}
    )
    assert r.status_code == 422


async def test_map_requires_level_1(client, make_member):
    _, headers = await make_member(role="student", level=0)
    assert (await client.get("/api/map/startups/nearby", headers=headers)).status_code == 403
