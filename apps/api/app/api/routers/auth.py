import re
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models.enums import OrgRole
from app.db.models.tenancy import Organization, OrganizationMember, User, Workspace
from app.db.session import get_db
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or uuid.uuid4().hex[:8]


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request, db: Annotated[Session, Depends(get_db)]):
    existing = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(email=payload.email, password_hash=hash_password(payload.password), full_name=payload.full_name)
    db.add(user)
    db.flush()

    base_slug = _slugify(payload.organization_name)
    slug = base_slug
    suffix = 1
    while db.execute(select(Organization).where(Organization.slug == slug)).scalar_one_or_none() is not None:
        suffix += 1
        slug = f"{base_slug}-{suffix}"

    org = Organization(name=payload.organization_name, slug=slug)
    db.add(org)
    db.flush()

    db.add(OrganizationMember(organization_id=org.id, user_id=user.id, role=OrgRole.OWNER))
    db.add(Workspace(organization_id=org.id, name="Default Workspace", slug="default"))

    record_audit(
        db,
        organization_id=org.id,
        user_id=user.id,
        action="user_registered",
        resource_type="user",
        resource_id=str(user.id),
        ip_address=request.client.host if request.client else "",
    )
    db.commit()

    return TokenResponse(access_token=create_access_token(user_id=user.id))


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Annotated[Session, Depends(get_db)]):
    user = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account disabled")

    membership = db.execute(select(OrganizationMember).where(OrganizationMember.user_id == user.id)).scalar_one_or_none()
    if membership is not None:
        record_audit(
            db,
            organization_id=membership.organization_id,
            user_id=user.id,
            action="login",
            resource_type="user",
            resource_id=str(user.id),
            ip_address=request.client.host if request.client else "",
        )
    db.commit()

    return TokenResponse(access_token=create_access_token(user_id=user.id))


@router.get("/me", response_model=UserResponse)
def me(user: Annotated[User, Depends(get_current_user)]):
    return user
