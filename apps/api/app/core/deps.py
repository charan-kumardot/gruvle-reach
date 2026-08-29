"""
Shared FastAPI dependencies for authentication and tenant/role enforcement.

Every router that touches workspace-scoped data must depend on
`require_workspace_member` (or `require_workspace_role`) rather than trusting
a workspace_id supplied by the client — this is the one place tenant
isolation is enforced, and it is enforced server-side on every request.
"""
import secrets
import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.db.models.enums import OrgRole
from app.db.models.tenancy import OrganizationMember, User, Workspace
from app.db.session import get_db

_ROLE_RANK = {OrgRole.VIEWER: 0, OrgRole.MEMBER: 1, OrgRole.ADMIN: 2, OrgRole.OWNER: 3}


def get_bearer_token(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    return auth.split(" ", 1)[1].strip()


def get_current_user(
    token: Annotated[str, Depends(get_bearer_token)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    try:
        payload = decode_access_token(token)
        user_id = uuid.UUID(payload["sub"])
    except Exception as exc:  # noqa: BLE001 — any decode failure is an auth failure
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from exc

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    return user


class WorkspaceContext:
    """Resolved, authorization-checked tenant context for the current request."""

    def __init__(self, workspace: Workspace, membership: OrganizationMember, user: User):
        self.workspace = workspace
        self.membership = membership
        self.user = user

    @property
    def workspace_id(self) -> uuid.UUID:
        return self.workspace.id

    @property
    def organization_id(self) -> uuid.UUID:
        return self.workspace.organization_id

    @property
    def role(self) -> OrgRole:
        return self.membership.role


def require_workspace_member(
    workspace_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> WorkspaceContext:
    workspace = db.get(Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    membership = db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == workspace.organization_id,
            OrganizationMember.user_id == user.id,
        )
    ).scalar_one_or_none()

    if membership is None:
        # Same response as "not found" — never confirm a workspace's existence
        # to a user who isn't a member of its organization.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    return WorkspaceContext(workspace=workspace, membership=membership, user=user)


def require_cron_secret(x_cron_secret: Annotated[str | None, Header()] = None) -> None:
    """Auth for the scheduled-job trigger endpoints (`/cron/*`) — these
    replace Celery beat, so they're the one place a non-user caller (an
    external scheduler) needs to authenticate. A blank configured secret
    always rejects, rather than accepting any/no header — never "open by
    default" just because CRON_SECRET hasn't been set yet."""
    configured = get_settings().cron_secret
    if not configured or not x_cron_secret or not secrets.compare_digest(x_cron_secret, configured):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing cron secret")


def require_workspace_role(minimum_role: OrgRole):
    def _dependency(
        ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)],
    ) -> WorkspaceContext:
        if _ROLE_RANK[ctx.role] < _ROLE_RANK[minimum_role]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {minimum_role.value} role or higher",
            )
        return ctx

    return _dependency
