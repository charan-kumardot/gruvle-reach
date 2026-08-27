import uuid

from pydantic import BaseModel

from app.db.models.enums import OrgRole


class OrganizationResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str

    model_config = {"from_attributes": True}


class WorkspaceResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    slug: str
    is_demo: bool

    model_config = {"from_attributes": True}


class WorkspaceCreateRequest(BaseModel):
    name: str
    slug: str


class MemberResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    email: str
    full_name: str
    role: OrgRole

    model_config = {"from_attributes": True}


class InviteMemberRequest(BaseModel):
    email: str
    role: OrgRole = OrgRole.MEMBER
