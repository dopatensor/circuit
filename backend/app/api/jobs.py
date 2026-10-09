"""Jobs and applications (F11).

Students: browse and filter jobs, see their skill match, apply once per job with a
short note, track their applications. Founders (the member who claimed the startup):
post and edit jobs, see applicants ranked by skill match, update application status.

Applying to a job at an unclaimed startup works too: the application is saved and
the founder sees it as soon as they claim the page.
"""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app.auth import (
    LEVEL_BROWSE,
    CurrentUser,
    CurrentUserDep,
    SessionDep,
    SettingsDep,
    require_level,
)
from app.events import record_event
from app.geo import member_center, point
from app.jobs import job_roles, match_out, member_skills, startup_need_caps
from app.matching.scoring import applicant_rank_score, proof_bonus
from app.models import (
    Application,
    GitHubAccount,
    Job,
    JobCapability,
    Member,
    MemberSkill,
    Startup,
)
from app.profiles import lat_lng_columns
from app.proof import student_proofs
from app.schemas import (
    ApplicantMember,
    ApplicantOut,
    ApplicantProof,
    ApplicationJob,
    ApplicationOut,
    ApplicationStatusIn,
    ApplyIn,
    JobCapabilityIO,
    JobIn,
    JobOut,
    JobStartup,
    JobType,
    JobUpdate,
    LatLng,
    Page,
    SkillIn,
)

router = APIRouter(prefix="/api", tags=["jobs"])
BrowseUser = Annotated[CurrentUser, Depends(require_level(LEVEL_BROWSE))]

MAX_RADIUS_KM = 50.0
MAX_SCAN = 1000  # jobs considered per list request (plenty at MVP scale)


# --- helpers ----------------------------------------------------------------------------


async def _job_or_404(session, job_id: uuid.UUID) -> Job:
    job = await session.get(Job, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


async def _startup_for_founder(session, startup_id: uuid.UUID, user: CurrentUser) -> Startup:
    startup = await session.get(Startup, startup_id)
    if startup is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Startup not found")
    if startup.claimed_by_member_id != user.member_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Only the founder who claimed this startup can manage its jobs",
        )
    return startup


async def _job_outs(session, rows, user: CurrentUser) -> list[JobOut]:
    """rows: (Job, Startup, lat, lng, distance_km). A fixed number of queries in total."""
    startup_ids = list({r.Startup.id for r in rows})
    roles_by_startup = await job_roles(session, startup_ids, only_open=False)
    roles = {j["id"]: j for js in roles_by_startup.values() for j in js}
    applied: set[uuid.UUID] = set()
    skills: dict[str, int] = {}
    needs: dict[uuid.UUID, list[str]] = {}
    if rows:
        applied = set(
            (
                await session.scalars(
                    select(Application.job_id).where(
                        Application.member_id == user.member_id,
                        Application.job_id.in_([r.Job.id for r in rows]),
                    )
                )
            ).all()
        )
    if user.role == "student":
        skills = await member_skills(session, user.member_id)
        needs = await startup_need_caps(session, startup_ids)
    out = []
    for r in rows:
        job, startup = r.Job, r.Startup
        role = roles.get(job.id, {"capabilities": [], "min_levels": {}})
        out.append(
            JobOut(
                id=job.id,
                title=job.title,
                description=job.description,
                type=job.type,
                paid=job.paid,
                compensation=job.compensation,
                status=job.status,
                capabilities=[
                    JobCapabilityIO(capability_id=c, min_level=lvl)
                    for c, lvl in role["min_levels"].items()
                ],
                startup=JobStartup(
                    id=startup.id,
                    name=startup.name,
                    sector=startup.sector,
                    claimed=startup.claimed_by_member_id is not None,
                    location=LatLng(lat=r.lat, lng=r.lng) if r.lat is not None else None,
                    address=startup.address,
                ),
                distance_km=round(r.distance_km, 2) if r.distance_km is not None else None,
                match=match_out(skills, [role | {"title": job.title}], needs.get(startup.id, []))
                if user.role == "student"
                else None,
                has_applied=job.id in applied,
                created_at=job.created_at,
            )
        )
    return out


# --- browsing ---------------------------------------------------------------------------


@router.get("/jobs", response_model=Page[JobOut])
async def list_jobs(
    user: BrowseUser,
    session: SessionDep,
    settings: SettingsDep,
    q: Annotated[str | None, Query(max_length=100, description="Search job titles")] = None,
    capability: str | None = None,
    type: JobType | None = None,
    paid: bool | None = None,
    radius_km: Annotated[float | None, Query(gt=0, le=MAX_RADIUS_KM)] = None,
    lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    lng: Annotated[float | None, Query(ge=-180, le=180)] = None,
    sort: Literal["match", "distance", "newest"] | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[JobOut]:
    """Open jobs. Distance is measured from (lat, lng), your profile location or the
    city centre; radius_km makes it a hard filter. Students default to sort=match."""
    if (lat is None) != (lng is None):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Send both lat and lng")
    if lat is None:
        lat, lng = await member_center(session, user.member_id, settings)
    origin = point(lat, lng)
    slat, slng = lat_lng_columns(Startup.location)
    distance_km = (func.ST_Distance(Startup.location, origin) / 1000.0).label("distance_km")

    filters = [Job.status == "open"]
    if q:
        filters.append(Job.title.ilike(f"%{q}%"))
    if type:
        filters.append(Job.type == type)
    if paid is not None:
        filters.append(Job.paid == paid)
    if capability:
        filters.append(
            Job.id.in_(
                select(JobCapability.job_id).where(JobCapability.capability_id == capability)
            )
        )
    if radius_km is not None:
        filters.append(func.ST_DWithin(Startup.location, origin, radius_km * 1000.0))

    rows = (
        await session.execute(
            select(Job, Startup, slat, slng, distance_km)
            .join(Startup, Startup.id == Job.startup_id)
            .where(*filters)
            .order_by(distance_km, Job.id)
            .limit(MAX_SCAN)
        )
    ).all()
    jobs = await _job_outs(session, rows, user)

    sort = sort or ("match" if user.role == "student" else "newest")
    if sort == "match" and user.role == "student":
        jobs.sort(key=lambda j: (-(j.match.score if j.match else 0), j.distance_km or 0))
    elif sort == "newest":
        jobs.sort(key=lambda j: j.created_at, reverse=True)
    await record_event(
        session,
        "jobs.searched",
        actor_id=user.member_id,
        payload={
            "capability": capability,
            "type": type,
            "paid": paid,
            "radius_km": radius_km,
            "sort": sort,
            "results": len(jobs),
        },  # fmt: skip
    )
    await session.commit()
    return Page[JobOut](
        items=jobs[offset : offset + limit], total=len(jobs), limit=limit, offset=offset
    )


async def _one_job_out(session, job: Job, user: CurrentUser, settings) -> JobOut:
    lat, lng = await member_center(session, user.member_id, settings)
    slat, slng = lat_lng_columns(Startup.location)
    distance_km = (func.ST_Distance(Startup.location, point(lat, lng)) / 1000.0).label(
        "distance_km"
    )
    row = (
        await session.execute(
            select(Job, Startup, slat, slng, distance_km)
            .join(Startup, Startup.id == Job.startup_id)
            .where(Job.id == job.id)
        )
    ).one()
    return (await _job_outs(session, [row], user))[0]


@router.get("/jobs/{job_id}", response_model=JobOut)
async def get_job(job_id: uuid.UUID, user: BrowseUser, session: SessionDep, settings: SettingsDep):
    job = await _job_or_404(session, job_id)
    out = await _one_job_out(session, job, user, settings)
    await record_event(
        session, "job.viewed", actor_id=user.member_id, target_type="job", target_id=job.id,
        payload={"actor_role": user.role, "match": out.match.score if out.match else None},
    )  # fmt: skip
    await session.commit()
    return out


# --- applying -----------------------------------------------------------------------------


def _application_out(app: Application, job: Job, startup: Startup) -> ApplicationOut:
    return ApplicationOut(
        id=app.id,
        job=ApplicationJob(
            id=job.id,
            title=job.title,
            type=job.type,
            paid=job.paid,
            startup_id=startup.id,
            startup_name=startup.name,
            startup_claimed=startup.claimed_by_member_id is not None,
        ),
        status=app.status,
        note=app.note,
        match_score_at_apply=app.match_score_at_apply,
        created_at=app.created_at,
        status_changed_at=app.status_changed_at,
    )


@router.post(
    "/jobs/{job_id}/apply", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED
)
async def apply(
    job_id: uuid.UUID, body: ApplyIn, user: BrowseUser, session: SessionDep, settings: SettingsDep
) -> ApplicationOut:
    """Apply with a short note. One application per student per job."""
    if user.role != "student":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Only students can apply to jobs")
    job = await _job_or_404(session, job_id)
    if job.status != "open":
        raise HTTPException(status.HTTP_409_CONFLICT, detail="This job is closed")
    existing = await session.scalar(
        select(Application.id).where(
            Application.job_id == job.id, Application.member_id == user.member_id
        )
    )
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="You have already applied to this job")
    score = (await _one_job_out(session, job, user, settings)).match.score
    application = Application(
        job_id=job.id, member_id=user.member_id, note=body.note.strip(), match_score_at_apply=score
    )
    session.add(application)
    try:
        await session.flush()
    except IntegrityError as exc:  # a double click that raced past the check above
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="You have already applied to this job"
        ) from exc
    startup = await session.get_one(Startup, job.startup_id)
    await record_event(
        session, "job.applied", actor_id=user.member_id, target_type="job", target_id=job.id,
        payload={
            "application_id": str(application.id), "match": score,
            "startup_claimed": startup.claimed_by_member_id is not None,
        },
    )  # fmt: skip
    await session.commit()
    await session.refresh(application)
    return _application_out(application, job, startup)


@router.get("/applications/me", response_model=list[ApplicationOut])
async def my_applications(user: CurrentUserDep, session: SessionDep) -> list[ApplicationOut]:
    rows = (
        await session.execute(
            select(Application, Job, Startup)
            .join(Job, Job.id == Application.job_id)
            .join(Startup, Startup.id == Job.startup_id)
            .where(Application.member_id == user.member_id)
            .order_by(Application.created_at.desc())
        )
    ).all()
    return [_application_out(a, j, s) for a, j, s in rows]


@router.post("/applications/{application_id}/withdraw", response_model=ApplicationOut)
async def withdraw(application_id: uuid.UUID, user: CurrentUserDep, session: SessionDep):
    application = await session.get(Application, application_id)
    if application is None or application.member_id != user.member_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Application not found")
    if application.status in ("hired", "rejected", "withdrawn"):
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"Already {application.status}")
    previous = application.status
    application.status = "withdrawn"
    application.status_changed_at = datetime.now(UTC)
    await record_event(
        session, "application.status_changed", actor_id=user.member_id,
        target_type="application", target_id=application.id,
        payload={"from": previous, "to": "withdrawn"},
    )  # fmt: skip
    await session.commit()
    job = await session.get_one(Job, application.job_id)
    return _application_out(application, job, await session.get_one(Startup, job.startup_id))


# --- founder side ---------------------------------------------------------------------------


@router.get("/startups/{startup_id}/applicants", response_model=list[ApplicantOut])
async def applicants(
    startup_id: uuid.UUID,
    user: CurrentUserDep,
    session: SessionDep,
    job_id: uuid.UUID | None = None,
    status_filter: Annotated[
        Literal["submitted", "shortlisted", "rejected", "hired", "withdrawn"] | None,
        Query(alias="status"),
    ] = None,
) -> list[ApplicantOut]:
    """Applicants to this startup's jobs, best skill match first. Shows skills, not
    college: we rank on what people can do."""
    startup = await _startup_for_founder(session, startup_id, user)
    filters = [Job.startup_id == startup.id]
    if job_id:
        filters.append(Job.id == job_id)
    if status_filter:
        filters.append(Application.status == status_filter)
    rows = (
        await session.execute(
            select(Application, Job, Member)
            .join(Job, Job.id == Application.job_id)
            .join(Member, Member.id == Application.member_id)
            .where(*filters)
        )
    ).all()
    if not rows:
        return []
    roles = {
        j["id"]: j
        for js in (await job_roles(session, [startup.id], only_open=False)).values()
        for j in js
    }
    needs = (await startup_need_caps(session, [startup.id])).get(startup.id, [])
    skills_by_member: dict[uuid.UUID, dict[str, int]] = {}
    for mid, cap, lvl in (
        await session.execute(
            select(MemberSkill.member_id, MemberSkill.capability_id, MemberSkill.level).where(
                MemberSkill.member_id.in_([m.id for _, _, m in rows])
            )
        )
    ).all():
        skills_by_member.setdefault(mid, {})[cap] = lvl
    member_ids = [m.id for _, _, m in rows]
    proofs = await student_proofs(session, member_ids)
    github_urls = dict(
        (
            await session.execute(
                select(GitHubAccount.member_id, GitHubAccount.profile_url).where(
                    GitHubAccount.member_id.in_(member_ids)
                )
            )
        ).all()
    )
    out = []
    for application, job, member in rows:
        skills = skills_by_member.get(member.id, {})
        role = roles.get(job.id, {"capabilities": [], "min_levels": {}}) | {"title": job.title}
        match = match_out(skills, [role], needs)
        proof = proofs[member.id]
        bonus, parts = proof_bonus(proof, role["capabilities"])
        out.append(
            ApplicantOut(
                application_id=application.id,
                job_id=job.id,
                job_title=job.title,
                member=ApplicantMember(
                    id=member.id,
                    display_name=member.display_name,
                    city=member.city,
                    verification_level=member.verification_level,
                ),
                skills=[SkillIn(capability_id=c, level=lvl) for c, lvl in sorted(skills.items())],
                match=match,
                proof=ApplicantProof(
                    verified_capabilities=sorted(proof.github_caps),
                    github_profile_url=github_urls.get(member.id),
                    portfolio_items=proof.portfolio_items,
                    founder_rating_avg=round(
                        sum(proof.founder_ratings) / len(proof.founder_ratings), 2
                    )
                    if proof.founder_ratings
                    else None,
                    circuits_completed=proof.circuits_completed,
                    components=parts,
                ),
                rank_score=applicant_rank_score(match.score, bonus),
                note=application.note,
                status=application.status,
                created_at=application.created_at,
            )
        )
    out.sort(key=lambda a: (-a.rank_score, -a.match.score, a.created_at))
    return out


@router.patch("/applications/{application_id}", response_model=ApplicationOut)
async def set_application_status(
    application_id: uuid.UUID, body: ApplicationStatusIn, user: CurrentUserDep, session: SessionDep
) -> ApplicationOut:
    """Shortlist, reject or hire. Only the founder who claimed the startup."""
    application = await session.get(Application, application_id)
    if application is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Application not found")
    job = await session.get_one(Job, application.job_id)
    startup = await _startup_for_founder(session, job.startup_id, user)
    if application.status == "withdrawn":
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="The student withdrew this application"
        )
    previous = application.status
    if previous != body.status:
        application.status = body.status
        application.status_changed_at = datetime.now(UTC)
        await record_event(
            session, "application.status_changed", actor_id=user.member_id,
            target_type="application", target_id=application.id,
            payload={"from": previous, "to": body.status, "job_id": str(job.id)},
        )  # fmt: skip
        await session.commit()
        await session.refresh(application)
    return _application_out(application, job, startup)


async def _set_capabilities(session, job_id: uuid.UUID, caps: list[JobCapabilityIO]) -> None:
    await session.execute(delete(JobCapability).where(JobCapability.job_id == job_id))
    unique = {c.capability_id: c.min_level for c in caps}
    session.add_all(
        JobCapability(job_id=job_id, capability_id=c, min_level=lvl) for c, lvl in unique.items()
    )


@router.post(
    "/startups/{startup_id}/jobs", response_model=JobOut, status_code=status.HTTP_201_CREATED
)
async def create_job(
    startup_id: uuid.UUID,
    body: JobIn,
    user: CurrentUserDep,
    session: SessionDep,
    settings: SettingsDep,
) -> JobOut:
    startup = await _startup_for_founder(session, startup_id, user)
    job = Job(startup_id=startup.id, source="user", **body.model_dump(exclude={"capabilities"}))
    session.add(job)
    await session.flush()
    await _set_capabilities(session, job.id, body.capabilities)
    startup.hiring = True
    await record_event(
        session, "job.created", actor_id=user.member_id, target_type="job", target_id=job.id,
        payload={"type": job.type, "paid": job.paid},
    )  # fmt: skip
    await session.commit()
    await session.refresh(job)
    return await _one_job_out(session, job, user, settings)


@router.patch("/jobs/{job_id}", response_model=JobOut)
async def update_job(
    job_id: uuid.UUID,
    body: JobUpdate,
    user: CurrentUserDep,
    session: SessionDep,
    settings: SettingsDep,
) -> JobOut:
    job = await _job_or_404(session, job_id)
    await _startup_for_founder(session, job.startup_id, user)
    changes = body.model_dump(exclude_unset=True)
    if body.capabilities is not None:
        await _set_capabilities(session, job.id, body.capabilities)
    changes.pop("capabilities", None)
    for field, value in changes.items():
        setattr(job, field, value)
    await record_event(
        session, "job.updated", actor_id=user.member_id, target_type="job", target_id=job.id,
        payload={"fields": sorted(body.model_dump(exclude_unset=True))},
    )  # fmt: skip
    await session.commit()
    await session.refresh(job)
    return await _one_job_out(session, job, user, settings)
