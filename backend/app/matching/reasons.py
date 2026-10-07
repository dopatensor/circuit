"""One-line, human reasons built from the score components (F4)."""

from app.matching.scoring import Components


def _names(ids, cap_names: dict[str, str], limit: int = 2) -> str:
    names = [cap_names.get(c, c).lower() for c in ids][:limit]
    return " and ".join(names)


def _traits(ids, trait_names: dict[str, str], limit: int = 2) -> str:
    return ", ".join(trait_names.get(t, t).lower() for t in ids[:limit])


def match_reason(
    candidate_name: str,
    c: Components,
    *,
    is_bridge: bool,
    member_sector: str | None,
    candidate_sector: str | None,
    cap_names: dict[str, str],
    trait_names: dict[str, str],
    via_name: str | None = None,
) -> str:
    """e.g. "Kavya Menon offers marketing, which you need · both: long sales cycle,
    technical buyers · across sectors (deeptech → biotech) · you both know Nandini Rao"."""
    parts = []
    if c.gets_caps and c.gives_caps:
        parts.append(
            f"You can trade: {candidate_name} offers {_names(c.gets_caps, cap_names)}, "
            f"you offer {_names(c.gives_caps, cap_names)}"
        )
    elif c.gets_caps:
        parts.append(f"{candidate_name} offers {_names(c.gets_caps, cap_names)}, which you need")
    elif c.gives_caps:
        parts.append(f"{candidate_name} needs {_names(c.gives_caps, cap_names)}, which you offer")
    elif c.complementarity > 0:
        parts.append(f"{candidate_name}'s experience is close to what you're looking for")
    else:
        parts.append(f"{candidate_name} works on similar things")
    if c.shared_traits:
        parts.append(f"both: {_traits(c.shared_traits, trait_names)}")
    if is_bridge and member_sector and candidate_sector:
        parts.append(f"across sectors ({candidate_sector} → {member_sector})")
    if c.hops == 1:
        parts.append("you're already connected")
    elif c.hops == 2 and via_name:
        parts.append(f"you both know {via_name}")
    return " · ".join(parts)


def job_reason(
    skill_score: int, matched: list[str], distance_km: float, job_type: str, paid: bool,
    cap_names: dict[str, str],
) -> str:  # fmt: skip
    kind = {"internship": "internship", "full_time": "full-time role"}.get(job_type, job_type)
    pay = "paid" if paid else "unpaid"
    skills = f" ({_names(matched, cap_names, limit=3)})" if matched else ""
    return f"{skill_score}% skills match{skills} · {distance_km:.1f} km away · {pay} {kind}"
