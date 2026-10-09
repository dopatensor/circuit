"""Proof of work on profiles (R2): GitHub (imported) and non-code items (added by you).

Builds the API shapes from what the import saved (GitHub is never called here), and
the per-student facts that matching and applicant ranking use.
"""

import uuid
from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.github import extract
from app.matching.scoring import StudentProof
from app.models import Circuit, CircuitLeg, GitHubAccount, GitHubRepo, Member, ProofItem
from app.schemas import (
    ExternalPROut,
    GitHubMe,
    GitHubPublic,
    GitHubRepoOut,
    ProofItemOut,
    PublicProof,
    VerifiedCapabilityOut,
)

MAX_FEATURED = 6
# A non-code item counts for matching with this much write-up: a link needs a short
# description, a case study without a link needs a real one.
MIN_LINK_DESCRIPTION = 40
MIN_CASE_STUDY_DESCRIPTION = 200

HOST_KINDS = {
    "behance.net": "behance",
    "dribbble.com": "dribbble",
    "github.com": "code",
    "gitlab.com": "code",
}


def detect_kind(url: str | None, requested: str | None) -> str:
    """The kind of a proof item. Known hosts win over what was picked, so a GitHub
    link is always a plain "code" link, never something that looks verified."""
    if url:
        host = (url.split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0]).lower()
        for domain, kind in HOST_KINDS.items():
            if host == domain or host.endswith("." + domain):
                return kind
        return requested if requested in ("portfolio", "website", "other") else "portfolio"
    return "case_study"


def item_counts(item: ProofItem) -> bool:
    if not item.capability_ids:
        return False
    if item.url:
        return len(item.description.strip()) >= MIN_LINK_DESCRIPTION
    return len(item.description.strip()) >= MIN_CASE_STUDY_DESCRIPTION


# --- GitHub ------------------------------------------------------------------------------


def _facts(repo: GitHubRepo) -> extract.RepoFacts:
    return extract.RepoFacts(
        github_repo_id=repo.github_repo_id,
        name=repo.name,
        html_url=repo.html_url,
        description=repo.description,
        homepage_url=repo.homepage_url,
        primary_language=repo.primary_language,
        languages=repo.languages,
        frameworks=repo.frameworks,
        commits_by_user=repo.commits_by_user,
        commits_total=repo.commits_total,
        readme_excerpt=repo.readme_excerpt,
        pushed_at=repo.pushed_at,
    )


def verified_capabilities(repos: Iterable[GitHubRepo]) -> list[extract.VerifiedCapability]:
    """From repos the student hasn't hidden: hiding a repo removes it everywhere."""
    return extract.verified_capabilities(_facts(r) for r in repos if not r.hidden)


def repo_out(repo: GitHubRepo) -> GitHubRepoOut:
    return GitHubRepoOut(
        id=repo.id,
        name=repo.name,
        html_url=repo.html_url,
        description=repo.description,
        homepage_url=repo.homepage_url,
        primary_language=repo.primary_language,
        languages=[k for k, _ in sorted(repo.languages.items(), key=lambda kv: -kv[1])],
        frameworks=repo.frameworks,
        commits_by_user=repo.commits_by_user,
        commits_total=repo.commits_total,
        readme_excerpt=repo.readme_excerpt,
        pushed_at=repo.pushed_at,
        featured=repo.featured,
        hidden=repo.hidden,
        counts_as_proof=extract.counts_as_proof(_facts(repo)),
    )


def _sorted_repos(repos: Iterable[GitHubRepo]) -> list[GitHubRepo]:
    return sorted(repos, key=lambda r: (-r.commits_by_user, r.name.lower()))


def github_public(account: GitHubAccount, repos: list[GitHubRepo]) -> GitHubPublic:
    visible = [r for r in repos if not r.hidden]
    return GitHubPublic(
        login=account.login,
        profile_url=account.profile_url,
        homepage_url=account.homepage_url,
        verified_capabilities=[
            VerifiedCapabilityOut(
                capability_id=v.capability_id, evidence=v.evidence, repo_count=v.repo_count
            )
            for v in verified_capabilities(repos)
        ],
        featured_repos=[repo_out(r) for r in _sorted_repos(visible) if r.featured],
        original_repos=sum(1 for r in visible if extract.counts_as_proof(_facts(r))),
        external_prs_total=account.external_prs_total,
        external_prs=[ExternalPROut(**p) for p in account.external_prs],
        active_weeks_90d=account.active_weeks_90d,
        last_active_at=account.last_active_at,
        fetched_at=account.fetched_at,
    )


def status_message(account: GitHubAccount) -> str | None:
    if account.status == "importing":
        return "Importing your public repos. This takes a minute."
    if account.status == "rate_limited":
        return "GitHub asked us to slow down. We'll try again soon; your last import still shows."
    if account.status == "error":
        if account.last_error in ("token_revoked", "account_mismatch"):
            return "GitHub access was removed. Connect again to refresh your repos."
        return "Couldn't refresh from GitHub. We'll try again within the hour."
    return None


def github_me(account: GitHubAccount, repos: list[GitHubRepo]) -> GitHubMe:
    return GitHubMe(
        **github_public(account, repos).model_dump(),
        status=account.status,
        status_message=status_message(account),
        source=account.source,
        connected_at=account.connected_at,
        next_fetch_at=account.next_fetch_at,
        repos=[repo_out(r) for r in _sorted_repos(repos)],
    )


async def load_github(
    session: AsyncSession, member_id: uuid.UUID
) -> tuple[GitHubAccount | None, list[GitHubRepo]]:
    account = await session.get(GitHubAccount, member_id)
    if account is None:
        return None, []
    repos = await session.scalars(select(GitHubRepo).where(GitHubRepo.member_id == member_id))
    return account, list(repos.all())


async def load_items(session: AsyncSession, member_id: uuid.UUID) -> list[ProofItem]:
    return list(
        (
            await session.scalars(
                select(ProofItem)
                .where(ProofItem.member_id == member_id)
                .order_by(ProofItem.created_at, ProofItem.id)
            )
        ).all()
    )


async def public_proof(session: AsyncSession, member_id: uuid.UUID) -> PublicProof:
    account, repos = await load_github(session, member_id)
    return PublicProof(
        github=github_public(account, repos) if account else None,
        items=[ProofItemOut.model_validate(i) for i in await load_items(session, member_id)],
    )


# --- scoring inputs ----------------------------------------------------------------------


async def student_proofs(
    session: AsyncSession, member_ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, StudentProof]:
    """Everything scoring needs about these students' proof of work, in a few queries."""
    ids = list(dict.fromkeys(member_ids))
    if not ids:
        return {}
    accounts = {
        a.member_id: a
        for a in await session.scalars(
            select(GitHubAccount).where(GitHubAccount.member_id.in_(ids))
        )
    }
    repos: dict[uuid.UUID, list[GitHubRepo]] = {}
    if accounts:
        for r in await session.scalars(
            select(GitHubRepo).where(GitHubRepo.member_id.in_(list(accounts)))
        ):
            repos.setdefault(r.member_id, []).append(r)
    items: dict[uuid.UUID, list[ProofItem]] = {}
    for i in await session.scalars(select(ProofItem).where(ProofItem.member_id.in_(ids))):
        items.setdefault(i.member_id, []).append(i)

    # Ratings founders gave for help the student gave them in a circuit.
    ratings: dict[uuid.UUID, list[int]] = {}
    for giver, rating in (
        await session.execute(
            select(CircuitLeg.giver_id, CircuitLeg.rating)
            .join(Member, Member.id == CircuitLeg.receiver_id)
            .where(
                CircuitLeg.giver_id.in_(ids),
                CircuitLeg.rating.is_not(None),
                Member.role == "founder",
            )
        )
    ).all():
        ratings.setdefault(giver, []).append(int(rating))
    circuits = dict(
        (
            await session.execute(
                select(CircuitLeg.giver_id, func.count(func.distinct(CircuitLeg.circuit_id)))
                .join(Circuit, Circuit.id == CircuitLeg.circuit_id)
                .where(CircuitLeg.giver_id.in_(ids), Circuit.status == "completed")
                .group_by(CircuitLeg.giver_id)
            )
        ).all()
    )

    out: dict[uuid.UUID, StudentProof] = {}
    for mid in ids:
        account = accounts.get(mid)
        visible = [r for r in repos.get(mid, []) if not r.hidden]
        counted = [i for i in items.get(mid, []) if item_counts(i)]
        out[mid] = StudentProof(
            github_caps=frozenset(v.capability_id for v in verified_capabilities(visible)),
            github_repos=sum(1 for r in visible if extract.counts_as_proof(_facts(r))),
            github_active_weeks=account.active_weeks_90d if account else 0,
            github_external_prs=account.external_prs_total if account else 0,
            portfolio_caps=frozenset(c for i in counted for c in i.capability_ids),
            portfolio_items=len(counted),
            founder_ratings=tuple(ratings.get(mid, ())),
            circuits_completed=int(circuits.get(mid, 0)),
        )
    return out
