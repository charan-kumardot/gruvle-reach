import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import WorkspaceContext, get_current_user, require_workspace_member, require_workspace_role
from app.db.models.enums import OrgRole
from app.db.models.tenancy import Organization, OrganizationMember, User, Workspace
from app.db.session import get_db
from app.schemas.tenancy import InviteMemberRequest, MemberResponse, OrganizationResponse, WorkspaceCreateRequest, WorkspaceResponse

router = APIRouter(tags=["organizations"])


@router.get("/organizations", response_model=list[OrganizationResponse])
def list_my_organizations(user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    rows = db.execute(
        select(Organization)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(OrganizationMember.user_id == user.id)
    ).scalars().all()
    return rows


@router.get("/organizations/{organization_id}/workspaces", response_model=list[WorkspaceResponse])
def list_workspaces(
    organization_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    is_member = db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id, OrganizationMember.user_id == user.id
        )
    ).scalar_one_or_none()
    if is_member is None:
        return []
    return db.execute(select(Workspace).where(Workspace.organization_id == organization_id)).scalars().all()


@router.post("/organizations/{organization_id}/workspaces", response_model=WorkspaceResponse, status_code=201)
def create_workspace(
    organization_id: uuid.UUID,
    payload: WorkspaceCreateRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    membership = db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id, OrganizationMember.user_id == user.id
        )
    ).scalar_one_or_none()
    from fastapi import HTTPException, status

    if membership is None or membership.role not in (OrgRole.OWNER, OrgRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires admin role or higher")

    ws = Workspace(organization_id=organization_id, name=payload.name, slug=payload.slug)
    db.add(ws)
    db.commit()
    db.refresh(ws)
    return ws


@router.post("/organizations/{organization_id}/members", response_model=MemberResponse, status_code=201)
def add_member(
    organization_id: uuid.UUID,
    payload: InviteMemberRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Adds an ALREADY-REGISTERED user to the organization with a role. This
    build doesn't send email invites (no required paid provider assumption
    for core flows) — the invited person must sign up first; wiring this to
    an email-invite token is a natural extension point (see docs/SETUP.md)."""
    from fastapi import HTTPException, status

    requester_membership = db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id, OrganizationMember.user_id == user.id
        )
    ).scalar_one_or_none()
    if requester_membership is None or requester_membership.role not in (OrgRole.OWNER, OrgRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires admin role or higher")

    target_user = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if target_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No registered user with that email yet — they must sign up first")

    existing = db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id, OrganizationMember.user_id == target_user.id
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already a member")

    membership = OrganizationMember(organization_id=organization_id, user_id=target_user.id, role=payload.role)
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return MemberResponse(id=membership.id, user_id=target_user.id, email=target_user.email, full_name=target_user.full_name, role=membership.role)


@router.get("/workspaces/{workspace_id}/members", response_model=list[MemberResponse])
def list_members(
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)],
    db: Annotated[Session, Depends(get_db)],
):
    rows = db.execute(
        select(OrganizationMember, User)
        .join(User, User.id == OrganizationMember.user_id)
        .where(OrganizationMember.organization_id == ctx.organization_id)
    ).all()
    return [
        MemberResponse(id=m.id, user_id=u.id, email=u.email, full_name=u.full_name, role=m.role) for m, u in rows
    ]
