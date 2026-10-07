import pytest

pytestmark = pytest.mark.anyio


async def test_admin_sets_verification_level_and_it_applies_immediately(client, login, make_member):
    member_id, headers = await make_member(role="founder", level=0)
    assert (await client.get("/api/members", headers=headers)).status_code == 403

    admin = await login("nandini")
    r = await client.put(
        f"/api/admin/members/{member_id}/verification", headers=admin, json={"level": 3}
    )
    assert r.status_code == 200 and r.json()["verification_level"] == 3
    # Same token as before: the level is read from the database, not the token.
    assert (await client.get("/api/members", headers=headers)).status_code == 200


async def test_non_admins_cannot_set_levels(client, login, make_member):
    member_id, _ = await make_member()
    for persona in ("lakshmi", "ravi"):
        r = await client.put(
            f"/api/admin/members/{member_id}/verification",
            headers=await login(persona),
            json={"level": 3},
        )
        assert r.status_code == 403


async def test_level_out_of_range_is_422(client, login, make_member):
    member_id, _ = await make_member()
    r = await client.put(
        f"/api/admin/members/{member_id}/verification",
        headers=await login("nandini"),
        json={"level": 4},
    )
    assert r.status_code == 422
