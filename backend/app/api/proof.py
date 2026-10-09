"""Proof of work (R2): connect GitHub through OAuth, choose which repos to show, and
add non-code proof (portfolio, Behance, Dribbble, case studies). Students only.

Pages read what the background import saved; GitHub is only called to connect, to
import (in the background) and to revoke access on disconnect.
"""

import uuid
from typing import Annotated

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from sqlalchemy import func, select

from app.auth import LEVEL_BROWSE, CurrentUser, SessionDep, SettingsDep, require_level
from app.config import Settings
from app.db import get_sessionmaker
from app.events import record_event
from app.github import service
from app.models import GitHubRepo, ProofItem
from app.proof import MAX_FEATURED, detect_kind, github_me, load_github, load_items, repo_out
from app.schemas import (
    GitHubFinishIn,
    GitHubMe,
    GitHubRepoOut,
    GitHubRepoUpdate,
    GitHubStartOut,
    ProofItemIn,
    ProofItemOut,
    ProofItemUpdate,
    ProofMe,
)

router = APIRouter(prefix="/api/proof", tags=["proof"])
MAX_ITEMS = 20


async def require_student(
    user: Annotated[CurrentUser, Depends(require_level(LEVEL_BROWSE))],
) -> CurrentUser:
    if user.role != "student":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Proof of work is for students")
    return user


Student = Annotated[CurrentUser, Depends(require_student)]


def get_github_transport() -> httpx.AsyncBaseTransport | None:
    """The HTTP transport for GitHub calls. Tests replace it with a fake GitHub."""
    return None


Transport = Annotated[httpx.AsyncBaseTransport | None, Depends(get_github_transport)]


async def run_import(
    settings: Settings, member_id: uuid.UUID, transport: httpx.AsyncBaseTransport | None
) -> None:
    """Background task after connecting: the first import, in its own transaction."""
    async with get_sessionmaker()() as session, session.begin():
        await service.import_account(session, settings, member_id, transport)


async def _proof_me(session, settings: Settings, member_id: uuid.UUID) -> ProofMe:
    account, repos = await load_github(session, member_id)
    return ProofMe(
        github_available=settings.github_configured,
        github=github_me(account, repos) if account else None,
        items=[ProofItemOut.model_validate(i) for i in await load_items(session, member_id)],
        max_featured=MAX_FEATURED,
    )


@router.get("/me", response_model=ProofMe)
async def my_proof(user: Student, session: SessionDep, settings: SettingsDep) -> ProofMe:
    """Your proof of work: the GitHub connection with every imported repo, and your
    other items."""
    return await _proof_me(session, settings, user.member_id)


# --- GitHub ------------------------------------------------------------------------------


@router.post("/github/start", response_model=GitHubStartOut)
async def start_github(user: Student, session: SessionDep, settings: SettingsDep):
    """The GitHub page to send the student to. Asks for no scopes: read-only access to
    public data."""
    if not settings.github_configured:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Connecting GitHub isn't set up on this server yet.",
        )
    await record_event(session, "github.connect_started", actor_id=user.member_id)
    await session.commit()
    return GitHubStartOut(authorize_url=service.start_url(settings, user.member_id))


@router.post("/github/finish", response_model=GitHubMe)
async def finish_github(
    body: GitHubFinishIn,
    user: Student,
    session: SessionDep,
    settings: SettingsDep,
    transport: Transport,
    background: BackgroundTasks,
) -> GitHubMe:
    """GitHub sent the student back with a code: link the account the token belongs to
    and start the import in the background."""
    if not settings.github_configured:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Connecting GitHub isn't set up on this server yet.",
        )
    try:
        account = await service.connect(
            session, settings, user.member_id, body.code, body.state, transport
        )
    except service.ConnectError as exc:
        await session.rollback()
        raise HTTPException(exc.status, detail=exc.detail) from exc
    await session.commit()
    background.add_task(run_import, settings, user.member_id, transport)
    account, repos = await load_github(session, user.member_id)
    assert account is not None
    return github_me(account, repos)


@router.delete("/github", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_github(
    user: Student, session: SessionDep, settings: SettingsDep, transport: Transport
) -> Response:
    """Disconnect GitHub: deletes the account link, the token and every imported repo."""
    if not await service.disconnect(session, settings, user.member_id, transport):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="GitHub isn't connected")
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/github/repos/{repo_id}", response_model=GitHubRepoOut)
async def update_repo(
    repo_id: uuid.UUID, body: GitHubRepoUpdate, user: Student, session: SessionDep
) -> GitHubRepoOut:
    """Feature a repo on your profile, or hide it (hidden repos aren't shown or used
    for verified skills)."""
    repo = await session.get(GitHubRepo, repo_id)
    if repo is None or repo.member_id != user.member_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Repo not found")
    if body.hidden is not None:
        repo.hidden = body.hidden
        if body.hidden:
            repo.featured = False
    if body.featured:
        if repo.hidden:
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail="Show this repo before featuring it"
            )
        featured = await session.scalar(
            select(func.count()).where(
                GitHubRepo.member_id == user.member_id,
                GitHubRepo.featured,
                GitHubRepo.id != repo.id,
            )
        )
        if (featured or 0) >= MAX_FEATURED:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail=f"You can feature up to {MAX_FEATURED} repos. Unfeature one first.",
            )
        repo.featured = True
    elif body.featured is False:
        repo.featured = False
    await record_event(
        session, "github.repo_updated", actor_id=user.member_id, target_type="github_repo",
        target_id=repo.id, payload={"featured": repo.featured, "hidden": repo.hidden},
    )  # fmt: skip
    await session.commit()
    return repo_out(repo)


# --- non-code proof ----------------------------------------------------------------------


async def _my_item(session, user: CurrentUser, item_id: uuid.UUID) -> ProofItem:
    item = await session.get(ProofItem, item_id)
    if item is None or item.member_id != user.member_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Item not found")
    return item


@router.post("/items", response_model=ProofItemOut, status_code=status.HTTP_201_CREATED)
async def add_item(body: ProofItemIn, user: Student, session: SessionDep) -> ProofItem:
    """Add a portfolio, Behance or Dribbble link, a live site, or a case study (no link,
    a write-up instead). Shown as "Added by you"; never as verified."""
    url = str(body.url) if body.url else None
    if url is None and len(body.description.strip()) < 40:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Add a link, or describe the work in at least 40 characters.",
        )
    count = await session.scalar(select(func.count()).where(ProofItem.member_id == user.member_id))
    if (count or 0) >= MAX_ITEMS:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail=f"You can add up to {MAX_ITEMS} items."
        )
    item = ProofItem(
        member_id=user.member_id,
        kind=detect_kind(url, body.kind),
        url=url,
        title=body.title,
        description=body.description,
        capability_ids=body.capability_ids,
    )
    session.add(item)
    await session.flush()
    await record_event(
        session, "proof_item.created", actor_id=user.member_id, target_type="proof_item",
        target_id=item.id, payload={"kind": item.kind, "capabilities": len(item.capability_ids)},
    )  # fmt: skip
    await session.commit()
    await session.refresh(item)
    return item


@router.patch("/items/{item_id}", response_model=ProofItemOut)
async def update_item(
    item_id: uuid.UUID, body: ProofItemUpdate, user: Student, session: SessionDep
) -> ProofItem:
    item = await _my_item(session, user, item_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(item, field, value)
    await record_event(
        session, "proof_item.updated", actor_id=user.member_id, target_type="proof_item",
        target_id=item.id, payload={"fields": sorted(body.model_dump(exclude_unset=True))},
    )  # fmt: skip
    await session.commit()
    await session.refresh(item)
    return item


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(item_id: uuid.UUID, user: Student, session: SessionDep) -> Response:
    item = await _my_item(session, user, item_id)
    await session.delete(item)
    await record_event(
        session, "proof_item.deleted", actor_id=user.member_id, target_type="proof_item",
        target_id=item_id,
    )  # fmt: skip
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
