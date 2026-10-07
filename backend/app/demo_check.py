"""Check that the five demo stories work, story by story: `make demo-check`.

Runs read-only checks against the configured database (DATABASE_URL), through the
real API where possible, and prints PASS or FAIL for each story. Run it after
`reset-demo` and before every demo. Each phase adds the checks for what it built, so
this always describes what the demo can show today.

    uv run python -m app.demo_check            # check the current database
    uv run python -m app.demo_check --reset    # reset-demo first, then check
"""

import argparse
import asyncio
import logging
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_engine, make_engine
from app.seed.ids import member_id


class StoryFailed(AssertionError):
    pass


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise StoryFailed(message)


@dataclass
class Ctx:
    client: httpx.AsyncClient
    session: AsyncSession
    _tokens: dict[str, str]

    async def as_(self, persona: str) -> dict[str, str]:
        if persona not in self._tokens:
            r = await self.client.post("/api/auth/demo/login", json={"persona": persona})
            expect(r.status_code == 200, f"demo login as {persona} failed ({r.status_code})")
            self._tokens[persona] = r.json()["access_token"]
        return {"Authorization": f"Bearer {self._tokens[persona]}"}

    async def get(self, persona: str, path: str, **params) -> dict | list:
        r = await self.client.get(path, headers=await self.as_(persona), params=params)
        expect(r.status_code == 200, f"GET {path} as {persona} returned {r.status_code}")
        return r.json()


# --- the stories --------------------------------------------------------------------------


async def story1_bridge(ctx: Ctx) -> str:
    helix = (await ctx.get("meera", "/api/startups", q="HelixRoot"))["items"]
    expect(len(helix) == 1, "HelixRoot Biosciences not found")
    helix = helix[0]
    expect(
        "marketing" in {n["capability_id"] for n in helix["needs"]},
        "HelixRoot doesn't need marketing",
    )
    kavya = await ctx.get("meera", f"/api/members/{member_id('kavya')}")
    expect(
        "marketing" in {o["capability_id"] for o in kavya["offers"]},
        "Kavya doesn't offer marketing",
    )
    expect(
        kavya["sector"] != helix["sector"],
        "Kavya and HelixRoot are in the same sector (not a bridge)",
    )
    shared = set(kavya["trait_ids"]) & set(helix["trait_ids"])
    expect(
        {"long_sales_cycle", "technical_buyers"} <= shared,
        f"missing shared traits (have {sorted(shared)})",
    )
    # Phase 4: the matching engine shows it, as a Bridge match, with a reason.
    matches = (await ctx.get("meera", "/api/matches", limit=5))["items"]
    hit = next((m for m in matches if m["title"] == "Kavya Menon"), None)
    expect(hit is not None, "Kavya isn't in Meera's top 5 matches")
    expect(hit["is_bridge"], "Kavya's match isn't flagged as a Bridge match")
    expect("long sales cycle" in hit["reason"], f"reason lacks shared traits: {hit['reason']}")
    rank = matches.index(hit) + 1
    return f"Kavya is Meera's #{rank} match, Bridge badge, reason: “{hit['reason']}”"


async def story2_circuit(ctx: Ctx) -> str:
    people = {k: await ctx.get(k, "/api/members/me") for k in ("asha", "priya", "arjun")}
    needs = {k: {n["capability_id"] for n in p["needs"]} for k, p in people.items()}
    offers = {k: {o["capability_id"] for o in p["offers"]} for k, p in people.items()}
    loop = [
        ("asha", "arjun", "hiring"),
        ("arjun", "priya", "fundraising"),
        ("priya", "asha", "marketing"),
    ]
    for giver, receiver, cap in loop:
        expect(
            cap in offers[giver] and cap in needs[receiver],
            f"{giver} can't help {receiver} with {cap}",
        )
    expect(
        all(p["circuits_opt_in"] for p in people.values()),
        "someone in the loop opted out of circuits",
    )
    return "Asha → Arjun (hiring) → Priya (fundraising) → Asha (marketing): all edges present"


async def story3_student(ctx: Ctx) -> str:
    ravi = await ctx.get("ravi", "/api/members/me")
    expect(ravi["college"] == "Shantinagar Institute of Technology", "Ravi's college changed")
    jobs = await ctx.get("ravi", "/api/jobs", radius_km=10, sort="match", limit=3)
    expect(jobs["items"], "no jobs within 10 km of Ravi")
    top = jobs["items"][0]
    expect(
        (top["startup"]["name"], top["title"]) == ("LedgerLoop", "Backend Engineering Intern"),
        f"Ravi's top job is {top['title']} at {top['startup']['name']}",
    )
    expect(top["distance_km"] < 3, f"LedgerLoop is {top['distance_km']} km away")
    matches = (await ctx.get("ravi", "/api/matches", limit=1))["items"]
    expect(
        matches and matches[0]["title"] == "Backend Engineering Intern"
        and matches[0]["subtitle"].startswith("LedgerLoop"),
        "Ravi's top match isn't the LedgerLoop internship",
    )  # fmt: skip
    pins = await ctx.get("ravi", "/api/map/startups/nearby", radius_km=5)
    pin = next((p for p in pins["items"] if p["name"] == "LedgerLoop"), None)
    expect(pin is not None and pin["hiring"], "LedgerLoop isn't a hiring pin near Ravi")
    return (
        f"top match and top job: {top['title']} at LedgerLoop, {top['match']['score']}% "
        f"skills, {top['distance_km']} km, {top['compensation']}"
    )


async def story4_warm_intro(ctx: Ctx) -> str:
    rohan, lakshmi, vikram = member_id("rohan"), member_id("lakshmi"), member_id("vikram")
    direct = await ctx.session.scalar(
        text("SELECT count(*) FROM connections WHERE (member_a, member_b) IN ((:a, :b), (:b, :a))"),
        {"a": rohan, "b": vikram},
    )
    expect(direct == 0, "Rohan and Vikram are directly connected (no intro needed)")
    weakest = await ctx.session.scalar(
        text(
            """
            SELECT LEAST(c1.strength, c2.strength) FROM connections c1, connections c2
            WHERE (c1.member_a, c1.member_b) IN ((:r, :l), (:l, :r))
              AND (c2.member_a, c2.member_b) IN ((:l, :v), (:v, :l))
            """
        ),
        {"r": rohan, "l": lakshmi, "v": vikram},
    )
    expect(weakest is not None and weakest >= 0.8, "no strong Rohan → Lakshmi → Vikram path")
    lakshmi_profile = await ctx.get("rohan", f"/api/members/{lakshmi}")
    expect(lakshmi_profile["verification_level"] == 3, "Lakshmi isn't verified level 3")
    matches = (await ctx.get("rohan", "/api/matches", limit=5))["items"]
    vikram_match = next((m for m in matches if m["title"] == "Vikram Shah"), None)
    expect(vikram_match is not None, "Vikram isn't in Rohan's top 5 matches")
    expect("Lakshmi" in vikram_match["reason"], "Vikram's match doesn't mention Lakshmi")
    terra = (await ctx.get("rohan", "/api/startups", q="TerraGrid"))["items"][0]
    stats = await ctx.get("rohan", f"/api/startups/{terra['id']}/stats")
    expect(not terra["claimed"], "TerraGrid is already claimed (run reset-demo)")
    expect(stats["interested_students"] >= 10, "TerraGrid has too little student interest")
    return (
        f"Rohan → Lakshmi → Vikram (weakest tie {weakest}); TerraGrid unclaimed with "
        f"{stats['interested_students']} interested students"
    )


async def story5_gap(ctx: Ctx) -> str:
    rows = (
        await ctx.session.execute(
            text(
                """
                SELECT id, needs, offers FROM (
                  SELECT c.id,
                    (SELECT count(*) FROM needs n WHERE n.capability_id = c.id AND n.active)
                      AS needs,
                    (SELECT count(*) FROM offers o WHERE o.capability_id = c.id AND o.active)
                      AS offers
                  FROM capabilities c
                ) t ORDER BY needs - offers DESC LIMIT 1
                """
            )
        )
    ).one()
    expect(rows.id == "regulatory_affairs", f"biggest gap is {rows.id}, not regulatory_affairs")
    return f"regulatory_affairs: {rows.needs} needs vs {rows.offers} offers"


STORIES: list[tuple[str, Callable[[Ctx], Awaitable[str]]]] = [
    ("1 Bridge match (HelixRoot ↔ Kavya)", story1_bridge),
    ("2 Exchange circuit (Asha, Priya, Arjun)", story2_circuit),
    ("3 Student matched on skills (Ravi → LedgerLoop internship)", story3_student),
    ("4 Warm intro via a mentor (Rohan → Lakshmi → Vikram)", story4_warm_intro),
    ("5 Capability gap (regulatory affairs)", story5_gap),
]


# --- runner -------------------------------------------------------------------------------


async def run_checks(settings: Settings) -> list[tuple[str, bool, str]]:
    from app.main import create_app

    # Demo logins on, request logs off: the output should be just PASS/FAIL lines.
    app = create_app(settings.model_copy(update={"demo_auth": True, "log_level": "WARNING"}))
    engine = make_engine(settings.database_url)
    results = []
    try:
        transport = httpx.ASGITransport(app=app)
        async with (
            httpx.AsyncClient(transport=transport, base_url="http://demo-check") as client,
            AsyncSession(engine) as session,
        ):
            ctx = Ctx(client, session, {})
            for name, check in STORIES:
                try:
                    results.append((name, True, await check(ctx)))
                except Exception as exc:  # a crash is a failed story, with the reason
                    results.append((name, False, f"{type(exc).__name__}: {exc}"))
    finally:
        await engine.dispose()
        await get_engine().dispose()
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.demo_check")
    parser.add_argument("--reset", action="store_true", help="run reset-demo first")
    args = parser.parse_args(argv)
    settings = get_settings()
    if settings.env == "production" and not settings.demo_public:
        sys.exit("Refusing to run demo checks with ENV=production (set DEMO_PUBLIC=true).")
    if args.reset:
        from app.cli import main as cli_main

        cli_main(["reset-demo"])

    logging.getLogger("httpx").setLevel(logging.WARNING)  # no per-request noise
    results = asyncio.run(run_checks(settings))
    width = max(len(name) for name, _, _ in results)
    for name, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  Story {name:<{width}}  {detail}")
    failed = sum(not ok for _, ok, _ in results)
    print(f"\n{len(results) - failed}/{len(results)} demo stories pass")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
